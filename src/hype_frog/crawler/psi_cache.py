"""SQLite TTL cache for raw PageSpeed Insights API responses."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

CACHE_TTL_SECONDS = 24 * 60 * 60


def _project_root() -> Path:
    from hype_frog.config import PROJECT_ROOT  # lazy import avoids circular at module level
    return PROJECT_ROOT


def _cache_db_path() -> Path:
    cache_dir = _project_root() / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "psi_metrics.sqlite"


def open_cache_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_cache_db_path(), timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS psi_cache (
            url TEXT NOT NULL,
            strategy TEXT NOT NULL,
            response_body TEXT NOT NULL,
            fetched_at REAL NOT NULL,
            PRIMARY KEY (url, strategy)
        )
        """
    )
    conn.commit()
    return conn


def cache_get(conn: sqlite3.Connection, url: str, strategy: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT response_body, fetched_at FROM psi_cache WHERE url = ? AND strategy = ?",
        (url, strategy),
    ).fetchone()
    if not row:
        return None
    body, fetched_at = row
    if time.time() - float(fetched_at) > CACHE_TTL_SECONDS:
        conn.execute("DELETE FROM psi_cache WHERE url = ? AND strategy = ?", (url, strategy))
        conn.commit()
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        conn.execute("DELETE FROM psi_cache WHERE url = ? AND strategy = ?", (url, strategy))
        conn.commit()
        return None


def cache_put(conn: sqlite3.Connection, url: str, strategy: str, payload: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO psi_cache (url, strategy, response_body, fetched_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(url, strategy) DO UPDATE SET
            response_body = excluded.response_body,
            fetched_at = excluded.fetched_at
        """,
        (url, strategy, json.dumps(payload, separators=(",", ":"), sort_keys=True), time.time()),
    )
    conn.commit()
