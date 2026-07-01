"""SQLite spill for Link Inventory anchor rows (streaming export)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterator

from hype_frog.core.path_utils import path_exists


class LinkInventoryCache:
    """Deduped anchor-level rows keyed by (source, target, anchor text)."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS link_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_url TEXT NOT NULL,
                target_url TEXT NOT NULL,
                anchor_text TEXT NOT NULL,
                row_json TEXT NOT NULL,
                UNIQUE(source_url, target_url, anchor_text)
            )
            """
        )
        self.conn.commit()

    def upsert_rows(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        payload = [
            (
                str(row.get("Source URL") or ""),
                str(row.get("Target URL") or ""),
                str(row.get("Anchor Text") or ""),
                json.dumps(row, ensure_ascii=True),
            )
            for row in rows
        ]
        self.conn.executemany(
            """
            INSERT INTO link_inventory(source_url, target_url, anchor_text, row_json)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(source_url, target_url, anchor_text) DO NOTHING
            """,
            payload,
        )
        self.conn.commit()

    def iter_rows(self, *, chunk_size: int = 500) -> Iterator[list[dict[str, Any]]]:
        cur = self.conn.execute(
            "SELECT row_json FROM link_inventory ORDER BY id ASC"
        )
        while True:
            raw_chunk = cur.fetchmany(chunk_size)
            if not raw_chunk:
                break
            chunk: list[dict[str, Any]] = []
            for (row_json,) in raw_chunk:
                chunk.append(json.loads(row_json))
            yield chunk

    def iter_rows_flat(self) -> Iterator[dict[str, Any]]:
        for chunk in self.iter_rows():
            yield from chunk
            chunk.clear()

    def row_count(self) -> int:
        cur = self.conn.execute("SELECT COUNT(*) FROM link_inventory")
        return int(cur.fetchone()[0])

    def close(self, *, cleanup_file: bool = False) -> None:
        try:
            self.conn.close()
        finally:
            if cleanup_file and path_exists(self.db_path):
                Path(self.db_path).unlink()


__all__ = ["LinkInventoryCache"]
