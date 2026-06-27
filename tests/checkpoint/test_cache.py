"""AuditCache SQLite store tests — full class coverage."""
from __future__ import annotations

from pathlib import Path

from hype_frog.checkpoint.cache import AuditCache


def _result(url: str, status: int = 200) -> dict:
    return {
        "main": {"URL": url, "Status Code": status},
        "extra": {"URL": url, "Extraction State": "complete"},
    }


class TestAuditCacheInit:
    def test_creates_db_file(self, tmp_path: Path) -> None:
        db = str(tmp_path / "cache.db")
        cache = AuditCache(db)
        cache.close()
        assert Path(db).exists()

    def test_creates_table_and_index_idempotent(self, tmp_path: Path) -> None:
        db = str(tmp_path / "cache.db")
        cache1 = AuditCache(db)
        cache1.close()
        # Second open must not raise (IF NOT EXISTS guards)
        cache2 = AuditCache(db)
        cache2.close()


class TestUpsertResults:
    def test_empty_list_is_noop(self, tmp_path: Path) -> None:
        cache = AuditCache(str(tmp_path / "cache.db"))
        cache.upsert_results([])
        assert cache.all_results() == []
        cache.close()

    def test_inserts_single_result(self, tmp_path: Path) -> None:
        cache = AuditCache(str(tmp_path / "cache.db"))
        cache.upsert_results([_result("https://example.com/")])
        rows = cache.all_results()
        assert len(rows) == 1
        assert rows[0]["main"]["URL"] == "https://example.com/"
        cache.close()

    def test_inserts_multiple_results(self, tmp_path: Path) -> None:
        cache = AuditCache(str(tmp_path / "cache.db"))
        cache.upsert_results([_result("https://a.com/"), _result("https://b.com/")])
        assert len(cache.all_results()) == 2
        cache.close()

    def test_upsert_replaces_on_url_conflict(self, tmp_path: Path) -> None:
        cache = AuditCache(str(tmp_path / "cache.db"))
        cache.upsert_results([_result("https://example.com/", status=200)])
        cache.upsert_results([_result("https://example.com/", status=301)])
        rows = cache.all_results()
        assert len(rows) == 1
        assert rows[0]["main"]["Status Code"] == 301
        cache.close()

    def test_url_falls_back_to_extra_when_main_url_missing(self, tmp_path: Path) -> None:
        cache = AuditCache(str(tmp_path / "cache.db"))
        result = {"main": {}, "extra": {"URL": "https://fallback.com/"}}
        cache.upsert_results([result])
        rows = cache.all_results()
        assert len(rows) == 1
        assert rows[0]["extra"]["URL"] == "https://fallback.com/"
        cache.close()


class TestIterResults:
    def test_iter_results_order_preserved(self, tmp_path: Path) -> None:
        cache = AuditCache(str(tmp_path / "cache.db"))
        urls = [f"https://example.com/{i}" for i in range(5)]
        cache.upsert_results([_result(u) for u in urls])
        yielded = [r["main"]["URL"] for r in cache.iter_results()]
        assert yielded == urls
        cache.close()

    def test_iter_results_empty_db(self, tmp_path: Path) -> None:
        cache = AuditCache(str(tmp_path / "cache.db"))
        assert list(cache.iter_results()) == []
        cache.close()


class TestIterResultsChunked:
    def test_chunk_size_one(self, tmp_path: Path) -> None:
        cache = AuditCache(str(tmp_path / "cache.db"))
        cache.upsert_results([_result("https://a.com/"), _result("https://b.com/")])
        chunks = list(cache.iter_results_chunked(chunk_size=1))
        assert len(chunks) == 2
        assert all(len(c) == 1 for c in chunks)
        cache.close()

    def test_chunk_size_larger_than_row_count(self, tmp_path: Path) -> None:
        cache = AuditCache(str(tmp_path / "cache.db"))
        cache.upsert_results([_result("https://a.com/")])
        chunks = list(cache.iter_results_chunked(chunk_size=100))
        assert len(chunks) == 1
        assert len(chunks[0]) == 1
        cache.close()

    def test_empty_db_yields_nothing(self, tmp_path: Path) -> None:
        cache = AuditCache(str(tmp_path / "cache.db"))
        assert list(cache.iter_results_chunked()) == []
        cache.close()


class TestClose:
    def test_close_default_keeps_file(self, tmp_path: Path) -> None:
        db = str(tmp_path / "cache.db")
        cache = AuditCache(db)
        cache.close(cleanup_file=False)
        assert Path(db).exists()

    def test_close_with_cleanup_removes_file(self, tmp_path: Path) -> None:
        db = str(tmp_path / "cache.db")
        cache = AuditCache(db)
        cache.close(cleanup_file=True)
        assert not Path(db).exists()

    def test_close_cleanup_false_is_default(self, tmp_path: Path) -> None:
        db = str(tmp_path / "cache.db")
        cache = AuditCache(db)
        cache.close()  # default cleanup_file=False
        assert Path(db).exists()
