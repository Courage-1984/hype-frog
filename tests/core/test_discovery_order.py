"""Tests for sitemap-first / BFS-second URL ordering."""

from __future__ import annotations

from hype_frog.core.discovery_order import order_main_and_extra_rows
from hype_frog.core.models import ExtraRowPayload, MainRowPayload


def _pair(url: str) -> tuple[MainRowPayload, ExtraRowPayload]:
    return (
        MainRowPayload.model_validate({"URL": url}),
        ExtraRowPayload.model_validate({"URL": url}),
    )


def test_order_main_and_extra_rows_places_sitemap_seeds_before_bfs() -> None:
    seed_a, seed_b = "https://example.com/a", "https://example.com/b"
    discovered = "https://example.com/discovered"
    crawl_urls = [seed_a, seed_b, discovered]

    main_rows = [pair[0] for pair in (_pair(discovered), _pair(seed_b), _pair(seed_a))]
    extra_rows = [pair[1] for pair in (_pair(discovered), _pair(seed_b), _pair(seed_a))]

    ordered_main, ordered_extra = order_main_and_extra_rows(
        main_rows, extra_rows, crawl_urls
    )

    assert [row.values["URL"] for row in ordered_main] == [seed_a, seed_b, discovered]
    assert [row.values["URL"] for row in ordered_extra] == [seed_a, seed_b, discovered]
    assert [row.values["Discovery Rank"] for row in ordered_main] == [1, 2, 3]
    assert [row.values["Discovery Rank"] for row in ordered_extra] == [1, 2, 3]
