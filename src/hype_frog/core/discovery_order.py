"""Canonical URL ordering: sitemap seeds first, then BFS discoveries."""

from __future__ import annotations

from typing import Callable, Iterable

from hype_frog.core.models import ExtraRowPayload, MainRowPayload
from hype_frog.core.url_normalization import normalize_url

_FALLBACK_RANK = 10**9


def build_url_rank_index(
    crawl_urls: Iterable[str],
    *,
    normalize_fn: Callable[[object], str] = normalize_url,
) -> dict[str, int]:
    """Map normalised URL keys to zero-based discovery sequence ranks."""
    ranks: dict[str, int] = {}
    for index, raw_url in enumerate(crawl_urls):
        cleaned = str(raw_url or "").strip()
        if not cleaned:
            continue
        for candidate in (cleaned, normalize_fn(cleaned)):
            if candidate and candidate not in ranks:
                ranks[candidate] = index
    return ranks


def _row_rank(
    row: MainRowPayload | ExtraRowPayload,
    *,
    rank_by_url: dict[str, int],
    normalize_fn=normalize_url,
) -> int:
    values = row.values
    url = str(values.get("URL") or values.get("Final URL") or "").strip()
    if not url:
        return _FALLBACK_RANK
    return rank_by_url.get(url, rank_by_url.get(normalize_fn(url), _FALLBACK_RANK))


def order_main_and_extra_rows(
    main_rows: list[MainRowPayload],
    extra_rows: list[ExtraRowPayload],
    crawl_urls: list[str],
) -> tuple[list[MainRowPayload], list[ExtraRowPayload]]:
    """Reorder paired crawl rows to match ``crawl_urls`` discovery sequence.

    Sitemap seed URLs appear first (in sitemap order), followed by URLs
    discovered via breadth-first internal-link expansion.
    """
    if not main_rows or not extra_rows:
        return main_rows, extra_rows

    rank_by_url = build_url_rank_index(crawl_urls)
    if not rank_by_url:
        return main_rows, extra_rows

    indexed_pairs = list(enumerate(zip(main_rows, extra_rows, strict=True)))
    indexed_pairs.sort(
        key=lambda item: (
            _row_rank(item[1][0], rank_by_url=rank_by_url),
            _row_rank(item[1][1], rank_by_url=rank_by_url),
            item[0],
        )
    )

    ordered_main: list[MainRowPayload] = []
    ordered_extra: list[ExtraRowPayload] = []
    for display_rank, (_original_index, (main_row, extra_row)) in enumerate(
        indexed_pairs, start=1
    ):
        main_values = dict(main_row.values)
        extra_values = dict(extra_row.values)
        main_values["Discovery Rank"] = display_rank
        extra_values["Discovery Rank"] = display_rank
        ordered_main.append(MainRowPayload.model_validate(main_values))
        ordered_extra.append(ExtraRowPayload.model_validate(extra_values))

    return ordered_main, ordered_extra


__all__ = [
    "build_url_rank_index",
    "order_main_and_extra_rows",
]
