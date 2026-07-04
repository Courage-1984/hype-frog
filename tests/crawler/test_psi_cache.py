"""Tests for the on-disk SQLite TTL cache backing PSI response reuse.

Previously untested: no test file referenced `cache_get`/`cache_put`/
`open_cache_db` anywhere, and this module isn't re-exported through the
`psi_engine` facade that other PSI tests go through.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Iterator

import pytest

from hype_frog.crawler import psi_cache


@pytest.fixture
def cache_conn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[sqlite3.Connection]:
    monkeypatch.setattr(psi_cache, "_project_root", lambda: tmp_path)
    conn = psi_cache.open_cache_db()
    yield conn
    conn.close()


def test_open_cache_db_creates_cache_dir_and_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(psi_cache, "_project_root", lambda: tmp_path)
    conn = psi_cache.open_cache_db()
    try:
        db_path = tmp_path / ".cache" / "psi_metrics.sqlite"
        assert db_path.is_file()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='psi_cache'"
        ).fetchall()
        assert tables
    finally:
        conn.close()


def test_open_cache_db_is_idempotent_across_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(psi_cache, "_project_root", lambda: tmp_path)
    first = psi_cache.open_cache_db()
    psi_cache.cache_put(first, "https://example.com/", "mobile", {"score": 90})
    first.close()

    second = psi_cache.open_cache_db()
    try:
        assert psi_cache.cache_get(second, "https://example.com/", "mobile") == {"score": 90}
    finally:
        second.close()


def test_cache_get_returns_none_for_missing_entry(cache_conn: sqlite3.Connection) -> None:
    assert psi_cache.cache_get(cache_conn, "https://example.com/missing", "mobile") is None


def test_cache_put_then_get_round_trip(cache_conn: sqlite3.Connection) -> None:
    payload = {"lighthouseResult": {"categories": {"performance": {"score": 0.9}}}}
    psi_cache.cache_put(cache_conn, "https://example.com/page", "desktop", payload)
    assert psi_cache.cache_get(cache_conn, "https://example.com/page", "desktop") == payload


def test_cache_put_upserts_existing_key(cache_conn: sqlite3.Connection) -> None:
    psi_cache.cache_put(cache_conn, "https://example.com/page", "mobile", {"score": 50})
    psi_cache.cache_put(cache_conn, "https://example.com/page", "mobile", {"score": 99})

    result = psi_cache.cache_get(cache_conn, "https://example.com/page", "mobile")
    assert result == {"score": 99}

    row_count = cache_conn.execute(
        "SELECT COUNT(*) FROM psi_cache WHERE url = ? AND strategy = ?",
        ("https://example.com/page", "mobile"),
    ).fetchone()[0]
    assert row_count == 1


def test_cache_get_expires_entries_older_than_ttl(cache_conn: sqlite3.Connection) -> None:
    stale_timestamp = time.time() - psi_cache.CACHE_TTL_SECONDS - 1
    cache_conn.execute(
        "INSERT INTO psi_cache (url, strategy, response_body, fetched_at) VALUES (?, ?, ?, ?)",
        ("https://example.com/stale", "mobile", '{"score": 10}', stale_timestamp),
    )
    cache_conn.commit()

    assert psi_cache.cache_get(cache_conn, "https://example.com/stale", "mobile") is None
    remaining = cache_conn.execute(
        "SELECT COUNT(*) FROM psi_cache WHERE url = ?", ("https://example.com/stale",)
    ).fetchone()[0]
    assert remaining == 0


def test_cache_get_treats_entry_at_ttl_boundary_as_fresh(cache_conn: sqlite3.Connection) -> None:
    fresh_timestamp = time.time() - psi_cache.CACHE_TTL_SECONDS + 5
    cache_conn.execute(
        "INSERT INTO psi_cache (url, strategy, response_body, fetched_at) VALUES (?, ?, ?, ?)",
        ("https://example.com/fresh", "mobile", '{"score": 42}', fresh_timestamp),
    )
    cache_conn.commit()

    assert psi_cache.cache_get(cache_conn, "https://example.com/fresh", "mobile") == {"score": 42}


def test_cache_get_deletes_malformed_json_entry(cache_conn: sqlite3.Connection) -> None:
    cache_conn.execute(
        "INSERT INTO psi_cache (url, strategy, response_body, fetched_at) VALUES (?, ?, ?, ?)",
        ("https://example.com/corrupt", "mobile", "{not valid json", time.time()),
    )
    cache_conn.commit()

    assert psi_cache.cache_get(cache_conn, "https://example.com/corrupt", "mobile") is None
    remaining = cache_conn.execute(
        "SELECT COUNT(*) FROM psi_cache WHERE url = ?", ("https://example.com/corrupt",)
    ).fetchone()[0]
    assert remaining == 0


def test_cache_is_keyed_by_url_and_strategy_independently(
    cache_conn: sqlite3.Connection,
) -> None:
    psi_cache.cache_put(cache_conn, "https://example.com/page", "mobile", {"score": 1})
    psi_cache.cache_put(cache_conn, "https://example.com/page", "desktop", {"score": 2})

    assert psi_cache.cache_get(cache_conn, "https://example.com/page", "mobile") == {"score": 1}
    assert psi_cache.cache_get(cache_conn, "https://example.com/page", "desktop") == {"score": 2}
