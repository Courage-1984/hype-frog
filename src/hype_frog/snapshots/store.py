"""SQLite persistence for post-crawl replay snapshots."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from hype_frog.config import PROJECT_ROOT
from hype_frog.config_defaults import CRAWL_SNAPSHOTS_DB_RELATIVE
from hype_frog.core import get_logger
from hype_frog.core.env_vars import (
    get_hf_snapshot_retention_per_domain,
    get_hf_snapshots_db_path,
)
from hype_frog.snapshots.models import (
    CRAWL_SNAPSHOT_SCHEMA_VERSION,
    CrawlReplaySnapshot,
    SnapshotMeta,
    SnapshotSchemaError,
)

logger = get_logger(__name__)


def resolve_snapshots_db_path() -> Path:
    override = get_hf_snapshots_db_path()
    if override:
        return Path(override).expanduser().resolve()
    return (PROJECT_ROOT / CRAWL_SNAPSHOTS_DB_RELATIVE).resolve()


def open_snapshots_db(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or resolve_snapshots_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crawl_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            domain TEXT NOT NULL,
            run_timestamp TEXT NOT NULL,
            schema_version INTEGER NOT NULL,
            row_count INTEGER NOT NULL,
            source_output_path TEXT,
            target_input TEXT NOT NULL,
            full_suite INTEGER NOT NULL,
            payload_json TEXT NOT NULL,
            created_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_snapshots_domain_created
        ON crawl_snapshots(domain, created_at DESC)
        """
    )
    conn.commit()
    return conn


def _row_to_meta(row: sqlite3.Row) -> SnapshotMeta:
    return SnapshotMeta(
        snapshot_id=str(row["snapshot_id"]),
        domain=str(row["domain"]),
        run_timestamp=str(row["run_timestamp"]),
        schema_version=int(row["schema_version"]),
        row_count=int(row["row_count"]),
        source_output_path=str(row["source_output_path"] or "") or None,
        target_input=str(row["target_input"]),
        full_suite=bool(row["full_suite"]),
        created_at=float(row["created_at"]),
    )


def _deserialize_payload(payload_json: str, *, snapshot_id: str) -> CrawlReplaySnapshot | None:
    try:
        raw = json.loads(payload_json)
    except json.JSONDecodeError:
        logger.warning("Corrupt snapshot payload for %s; skipping.", snapshot_id)
        return None
    if not isinstance(raw, dict):
        logger.warning("Invalid snapshot payload type for %s; skipping.", snapshot_id)
        return None
    try:
        return CrawlReplaySnapshot.from_dict(raw)
    except SnapshotSchemaError as exc:
        logger.warning("Snapshot %s schema error: %s", snapshot_id, exc)
        return None


def save_crawl_snapshot(
    snapshot: CrawlReplaySnapshot,
    *,
    conn: sqlite3.Connection | None = None,
) -> str:
    """Persist a crawl replay snapshot and enforce per-domain retention."""
    owns_conn = conn is None
    db_conn = conn or open_snapshots_db()
    try:
        if not snapshot.snapshot_id:
            snapshot.snapshot_id = str(uuid.uuid4())

        target_input = str(snapshot.crawl_context.get("target_input") or snapshot.domain)
        full_suite = bool(snapshot.crawl_context.get("full_suite", True))
        created_at = time.time()
        payload_json = json.dumps(snapshot.to_dict(), ensure_ascii=False, separators=(",", ":"))

        db_conn.execute(
            """
            INSERT INTO crawl_snapshots (
                snapshot_id, domain, run_timestamp, schema_version, row_count,
                source_output_path, target_input, full_suite, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.snapshot_id,
                snapshot.domain,
                snapshot.run_timestamp,
                snapshot.schema_version,
                len(snapshot.main_rows),
                snapshot.source_output_path,
                target_input,
                1 if full_suite else 0,
                payload_json,
                created_at,
            ),
        )
        db_conn.commit()
        prune_snapshots_for_domain(snapshot.domain, conn=db_conn)
        logger.info(
            "Crawl snapshot saved: %s (domain=%s, rows=%d, db=%s)",
            snapshot.snapshot_id,
            snapshot.domain,
            len(snapshot.main_rows),
            resolve_snapshots_db_path(),
        )
        return snapshot.snapshot_id
    finally:
        if owns_conn:
            db_conn.close()


def load_crawl_snapshot_by_id(
    snapshot_id: str,
    *,
    conn: sqlite3.Connection | None = None,
) -> CrawlReplaySnapshot | None:
    owns_conn = conn is None
    db_conn = conn or open_snapshots_db()
    try:
        row = db_conn.execute(
            "SELECT payload_json, snapshot_id FROM crawl_snapshots WHERE snapshot_id = ?",
            (snapshot_id.strip(),),
        ).fetchone()
        if row is None:
            return None
        return _deserialize_payload(str(row["payload_json"]), snapshot_id=str(row["snapshot_id"]))
    finally:
        if owns_conn:
            db_conn.close()


def load_latest_crawl_snapshot_for_domain(
    domain: str,
    *,
    conn: sqlite3.Connection | None = None,
) -> CrawlReplaySnapshot | None:
    owns_conn = conn is None
    db_conn = conn or open_snapshots_db()
    try:
        row = db_conn.execute(
            """
            SELECT payload_json, snapshot_id
            FROM crawl_snapshots
            WHERE domain = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (domain.strip().lower(),),
        ).fetchone()
        if row is None:
            return None
        return _deserialize_payload(str(row["payload_json"]), snapshot_id=str(row["snapshot_id"]))
    finally:
        if owns_conn:
            db_conn.close()


def list_crawl_snapshots(
    domain: str | None = None,
    *,
    conn: sqlite3.Connection | None = None,
) -> list[SnapshotMeta]:
    owns_conn = conn is None
    db_conn = conn or open_snapshots_db()
    try:
        if domain:
            rows = db_conn.execute(
                """
                SELECT * FROM crawl_snapshots
                WHERE domain = ?
                ORDER BY created_at DESC
                """,
                (domain.strip().lower(),),
            ).fetchall()
        else:
            rows = db_conn.execute(
                "SELECT * FROM crawl_snapshots ORDER BY created_at DESC"
            ).fetchall()
        return [_row_to_meta(row) for row in rows]
    finally:
        if owns_conn:
            db_conn.close()


def prune_snapshots_for_domain(
    domain: str,
    *,
    keep_n: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> int:
    """Delete snapshots beyond the retention cap for a domain. Returns rows deleted."""
    retention = keep_n if keep_n is not None else get_hf_snapshot_retention_per_domain()
    if retention <= 0:
        return 0

    owns_conn = conn is None
    db_conn = conn or open_snapshots_db()
    try:
        cursor = db_conn.execute(
            """
            DELETE FROM crawl_snapshots
            WHERE domain = ?
              AND snapshot_id NOT IN (
                  SELECT snapshot_id FROM crawl_snapshots
                  WHERE domain = ?
                  ORDER BY created_at DESC
                  LIMIT ?
              )
            """,
            (domain.strip().lower(), domain.strip().lower(), retention),
        )
        db_conn.commit()
        deleted = int(cursor.rowcount)
        if deleted:
            logger.info(
                "Pruned %d crawl snapshot(s) for domain %s (retention=%d).",
                deleted,
                domain,
                retention,
            )
        return deleted
    finally:
        if owns_conn:
            db_conn.close()
