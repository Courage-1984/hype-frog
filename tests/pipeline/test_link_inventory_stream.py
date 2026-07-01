"""Tests for streaming Link Inventory materialisation."""

from __future__ import annotations

from hype_frog.checkpoint.link_inventory_cache import LinkInventoryCache
from hype_frog.pipeline.link_inventory_stream import populate_link_inventory_cache
from hype_frog.reporter.sheets.merged_builders import build_link_inventory_rows


def _extra_row(url: str, link_count: int) -> dict[str, object]:
    return {
        "URL": url,
        "Link Details": [
            {
                "Target URL": f"https://example.com/target-{index}/",
                "Anchor Text": f"anchor {index}",
                "Rel Attribute": "",
                "Link Type": "Internal",
                "Status Code": 200,
                "Generic Anchor": False,
            }
            for index in range(link_count)
        ],
    }


def test_populate_link_inventory_cache_dedupes_and_streams(tmp_path) -> None:
    cache = LinkInventoryCache(str(tmp_path / "links.db"))
    try:
        extra_rows = [
            _extra_row("https://example.com/a/", 3),
            _extra_row("https://example.com/b/", 2),
        ]
        count = populate_link_inventory_cache(cache, extra_rows, batch_size=2)
        assert count == 5
        materialised = list(cache.iter_rows_flat())
        assert len(materialised) == 5
    finally:
        cache.close(cleanup_file=True)


def test_build_link_inventory_rows_matches_streaming_cache(tmp_path) -> None:
    extra_rows = [_extra_row("https://example.com/", 4)]
    list_rows = build_link_inventory_rows(extra_rows)
    cache = LinkInventoryCache(str(tmp_path / "links.db"))
    try:
        populate_link_inventory_cache(cache, extra_rows)
        stream_rows = list(cache.iter_rows_flat())
        assert list_rows == stream_rows
    finally:
        cache.close(cleanup_file=True)
