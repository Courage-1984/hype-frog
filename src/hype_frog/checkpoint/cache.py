from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterator

from hype_frog.core.models import CrawlResult
from hype_frog.core.path_utils import path_exists


class AuditCache:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS crawl_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                main_json TEXT NOT NULL,
                extra_json TEXT NOT NULL
            )
            """
        )
        self.conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_crawl_results_url ON crawl_results(url)"
        )
        self.conn.commit()

    def upsert_results(self, results: list[CrawlResult]) -> None:
        if not results:
            return
        rows = []
        for result in results:
            main = result.get("main", {})
            extra = result.get("extra", {})
            url = str(main.get("URL") or extra.get("URL") or "")
            rows.append(
                (
                    url,
                    json.dumps(main, ensure_ascii=True),
                    json.dumps(extra, ensure_ascii=True),
                )
            )
        self.conn.executemany(
            """
            INSERT INTO crawl_results(url, main_json, extra_json)
            VALUES(?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                main_json=excluded.main_json,
                extra_json=excluded.extra_json
            """,
            rows,
        )
        self.conn.commit()

    def row_count(self) -> int:
        cur = self.conn.execute("SELECT COUNT(*) FROM crawl_results")
        return int(cur.fetchone()[0])

    def iter_results(self) -> Iterator[CrawlResult]:
        cur = self.conn.execute(
            "SELECT main_json, extra_json FROM crawl_results ORDER BY id ASC"
        )
        for main_json, extra_json in cur:
            yield {
                "main": json.loads(main_json),
                "extra": json.loads(extra_json),
            }

    def iter_results_chunked(self, chunk_size: int = 500) -> Iterator[list[CrawlResult]]:
        cur = self.conn.execute(
            "SELECT main_json, extra_json FROM crawl_results ORDER BY id ASC"
        )
        while True:
            rows = cur.fetchmany(chunk_size)
            if not rows:
                break
            chunk: list[CrawlResult] = []
            for main_json, extra_json in rows:
                chunk.append({"main": json.loads(main_json), "extra": json.loads(extra_json)})
            yield chunk

    def all_results(self) -> list[CrawlResult]:
        return list(self.iter_results())

    def close(self, cleanup_file: bool = False) -> None:
        try:
            self.conn.close()
        finally:
            if cleanup_file and path_exists(self.db_path):
                Path(self.db_path).unlink()
