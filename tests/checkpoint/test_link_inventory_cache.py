"""LinkInventoryCache SQLite spill store tests."""
from __future__ import annotations

from pathlib import Path

from hype_frog.checkpoint.link_inventory_cache import LinkInventoryCache


def _row(source: str, target: str, anchor: str = "Home") -> dict:
    return {
        "Source URL": source,
        "Target URL": target,
        "Anchor Text": anchor,
        "Link Type": "Internal",
    }


class TestInit:
    def test_creates_db_file(self, tmp_path: Path) -> None:
        db = str(tmp_path / "link_inventory.db")
        cache = LinkInventoryCache(db)
        cache.close()
        assert Path(db).exists()

    def test_creates_table_idempotent(self, tmp_path: Path) -> None:
        db = str(tmp_path / "link_inventory.db")
        cache1 = LinkInventoryCache(db)
        cache1.close()
        # Second open must not raise (IF NOT EXISTS guards)
        cache2 = LinkInventoryCache(db)
        cache2.close()


class TestUpsertRows:
    def test_empty_list_is_noop(self, tmp_path: Path) -> None:
        cache = LinkInventoryCache(str(tmp_path / "cache.db"))
        cache.upsert_rows([])
        assert cache.row_count() == 0
        cache.close()

    def test_inserts_single_row(self, tmp_path: Path) -> None:
        cache = LinkInventoryCache(str(tmp_path / "cache.db"))
        cache.upsert_rows([_row("https://example.com/", "https://example.com/about")])
        assert cache.row_count() == 1
        cache.close()

    def test_inserts_multiple_rows(self, tmp_path: Path) -> None:
        cache = LinkInventoryCache(str(tmp_path / "cache.db"))
        cache.upsert_rows(
            [
                _row("https://example.com/", "https://example.com/a"),
                _row("https://example.com/", "https://example.com/b"),
            ]
        )
        assert cache.row_count() == 2
        cache.close()

    def test_dedupes_on_source_target_anchor_conflict(self, tmp_path: Path) -> None:
        cache = LinkInventoryCache(str(tmp_path / "cache.db"))
        row = _row("https://example.com/", "https://example.com/about", "About Us")
        cache.upsert_rows([row])
        cache.upsert_rows([row])
        assert cache.row_count() == 1
        cache.close()

    def test_same_source_target_different_anchor_not_deduped(
        self, tmp_path: Path
    ) -> None:
        cache = LinkInventoryCache(str(tmp_path / "cache.db"))
        cache.upsert_rows(
            [
                _row("https://example.com/", "https://example.com/about", "About"),
                _row("https://example.com/", "https://example.com/about", "Learn more"),
            ]
        )
        assert cache.row_count() == 2
        cache.close()

    def test_missing_keys_default_to_empty_string(self, tmp_path: Path) -> None:
        cache = LinkInventoryCache(str(tmp_path / "cache.db"))
        cache.upsert_rows([{"Link Type": "Internal"}])
        assert cache.row_count() == 1
        cache.close()


class TestIterRows:
    def test_iter_rows_chunked_order_preserved(self, tmp_path: Path) -> None:
        cache = LinkInventoryCache(str(tmp_path / "cache.db"))
        rows = [_row("https://example.com/", f"https://example.com/{i}") for i in range(5)]
        cache.upsert_rows(rows)
        chunks = list(cache.iter_rows(chunk_size=2))
        assert sum(len(c) for c in chunks) == 5
        flattened = [r["Target URL"] for chunk in chunks for r in chunk]
        assert flattened == [r["Target URL"] for r in rows]
        cache.close()

    def test_iter_rows_empty_db(self, tmp_path: Path) -> None:
        cache = LinkInventoryCache(str(tmp_path / "cache.db"))
        assert list(cache.iter_rows()) == []
        cache.close()

    def test_iter_rows_flat(self, tmp_path: Path) -> None:
        cache = LinkInventoryCache(str(tmp_path / "cache.db"))
        cache.upsert_rows(
            [
                _row("https://example.com/", "https://example.com/a"),
                _row("https://example.com/", "https://example.com/b"),
            ]
        )
        flat = list(cache.iter_rows_flat())
        assert len(flat) == 2
        assert {r["Target URL"] for r in flat} == {
            "https://example.com/a",
            "https://example.com/b",
        }
        cache.close()


class TestClose:
    def test_close_default_keeps_file(self, tmp_path: Path) -> None:
        db = str(tmp_path / "cache.db")
        cache = LinkInventoryCache(db)
        cache.close(cleanup_file=False)
        assert Path(db).exists()

    def test_close_with_cleanup_removes_file(self, tmp_path: Path) -> None:
        db = str(tmp_path / "cache.db")
        cache = LinkInventoryCache(db)
        cache.close(cleanup_file=True)
        assert not Path(db).exists()

    def test_close_cleanup_is_safe_when_db_already_missing(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        db = str(tmp_path / "cache.db")
        cache = LinkInventoryCache(db)
        monkeypatch.setattr(
            "hype_frog.checkpoint.link_inventory_cache.path_exists",
            lambda _path: False,
        )
        cache.close(cleanup_file=True)  # must not raise even though "missing"
