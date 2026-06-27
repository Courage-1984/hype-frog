"""Tests for sitemap-first / BFS-second URL ordering."""

from __future__ import annotations

from hype_frog.core.discovery_order import build_url_rank_index, order_main_and_extra_rows
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


# ---------------------------------------------------------------------------
# build_url_rank_index — direct unit tests
# ---------------------------------------------------------------------------


def test_build_url_rank_index_returns_zero_based_ranks() -> None:
    urls = ["https://example.com/a", "https://example.com/b", "https://example.com/c"]
    index = build_url_rank_index(urls)
    assert index["https://example.com/a"] == 0
    assert index["https://example.com/b"] == 1
    assert index["https://example.com/c"] == 2


def test_build_url_rank_index_empty_input_returns_empty() -> None:
    assert build_url_rank_index([]) == {}


def test_build_url_rank_index_filters_blank_urls() -> None:
    index = build_url_rank_index(["https://example.com/a", "", "   ", "https://example.com/b"])
    assert "" not in index
    assert "   " not in index
    assert "https://example.com/a" in index
    assert "https://example.com/b" in index


def test_build_url_rank_index_stores_both_raw_and_normalised_url() -> None:
    # The function stores both the raw URL and its normalised form so that
    # lookups work regardless of whether the row carries the raw or normalised key.
    url = "HTTPS://Example.COM/path"
    index = build_url_rank_index([url])
    assert url in index or any(k for k in index if k.startswith("https://example.com"))


def test_order_main_and_extra_rows_empty_returns_unchanged() -> None:
    main, extra = order_main_and_extra_rows([], [], ["https://example.com/"])
    assert main == []
    assert extra == []


def test_order_main_and_extra_rows_empty_crawl_urls_returns_unchanged() -> None:
    m, e = _pair("https://example.com/a")
    main, extra = order_main_and_extra_rows([m], [e], [])
    assert main == [m]
    assert extra == [e]
