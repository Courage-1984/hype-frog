"""Streaming Link Inventory flattening without holding all anchors in RAM."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

from hype_frog.checkpoint.link_inventory_cache import LinkInventoryCache
from hype_frog.core.memory_guard import memory_circuit_breaker
from hype_frog.core.url_normalization import normalize_url_key
from hype_frog.reporter.sheets.merged_builders import LINK_INVENTORY_COLUMNS


def _to_str(value: object) -> str:
    return str(value or "").strip()


def anchor_row_from_link_item(
    source_url: str,
    item: dict[str, Any],
) -> dict[str, Any]:
    code_raw = item.get("Status Code")
    code_out: int | str = ""
    if isinstance(code_raw, int):
        code_out = code_raw
    elif code_raw is not None and str(code_raw).strip() != "":
        try:
            code_out = int(float(code_raw))
        except (TypeError, ValueError):
            code_out = ""
    gen = item.get("Generic Anchor")
    row_dict: dict[str, Any] = {
        "Source URL": source_url,
        "Target URL": _to_str(item.get("Target URL")),
        "Anchor Text": _to_str(item.get("Anchor Text")),
        "Rel Attribute": _to_str(item.get("Rel Attribute") or item.get("Rel")),
        "Link Type": _to_str(item.get("Link Type")),
        "Status Code": code_out,
        "Generic Anchor": (
            "TRUE" if gen is True else "FALSE" if gen is False else ""
        ),
    }
    return {col: row_dict[col] for col in LINK_INVENTORY_COLUMNS}


def iter_anchor_rows_from_extra_rows(
    extra_rows: Iterable[dict[str, Any]],
) -> Iterator[dict[str, Any]]:
    for row in extra_rows:
        source = _to_str(row.get("URL"))
        for item in row.get("Link Details") or []:
            if isinstance(item, dict):
                yield anchor_row_from_link_item(source, item)


def populate_link_inventory_cache(
    cache: LinkInventoryCache,
    extra_rows: Iterable[dict[str, Any]],
    *,
    batch_size: int = 500,
) -> int:
    """Stream anchors into SQLite; returns deduped row count."""
    batch: list[dict[str, Any]] = []
    for anchor in iter_anchor_rows_from_extra_rows(extra_rows):
        batch.append(anchor)
        if len(batch) >= batch_size:
            cache.upsert_rows(batch)
            batch.clear()
            memory_circuit_breaker()
    if batch:
        cache.upsert_rows(batch)
    return cache.row_count()


def build_link_inventory_rows_list(
    extra_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Backward-compatible list materialisation (small audits / unit tests)."""
    cache = LinkInventoryCache(":memory:")
    try:
        populate_link_inventory_cache(cache, extra_rows)
        return list(cache.iter_rows_flat())
    finally:
        cache.close()


def _decorate_anchor_row(
    row: dict[str, Any], status_by_url: dict[str, Any]
) -> dict[str, Any]:
    """Add Link Intelligence's Detail-row decoration to one cached anchor row.

    Remaps ``Source URL`` -> ``URL`` (Link Intelligence's row-key column name) and
    resolves ``Target Status (if crawled)``/``Crawlable`` exactly as the export
    pipeline's now-removed inline decoration block did.
    """
    own_status = row.get("Status Code")
    if own_status is not None and own_status != "":
        target_status = own_status
    else:
        target_status = status_by_url.get(normalize_url_key(row.get("Target URL", "")))
    crawlable = target_status is None or (
        isinstance(target_status, (int, float)) and target_status < 400
    )
    return {
        "URL": row.get("Source URL"),
        "Target URL": row.get("Target URL"),
        "Anchor Text": row.get("Anchor Text"),
        "Rel Attribute": row.get("Rel Attribute"),
        "Link Type": row.get("Link Type"),
        "Status Code": row.get("Status Code"),
        "Generic Anchor": row.get("Generic Anchor"),
        "Target Status (if crawled)": target_status,
        "Crawlable": crawlable,
    }


def iter_rows_decorated(
    cache: LinkInventoryCache,
    status_by_url: dict[str, Any],
    *,
    chunk_size: int = 500,
) -> Iterator[list[dict[str, Any]]]:
    """Wrap the cache's chunked anchor-row iterator for Link Intelligence's Detail block.

    Each row is decorated with ``Target Status (if crawled)``/``Crawlable`` and its
    ``Source URL`` key is remapped to ``URL`` — folded in from the former standalone
    "Link Inventory" sheet, whose raw rows use ``Source URL`` as the key instead.
    """
    for chunk in cache.iter_rows(chunk_size=chunk_size):
        yield [_decorate_anchor_row(row, status_by_url) for row in chunk]


__all__ = [
    "anchor_row_from_link_item",
    "build_link_inventory_rows_list",
    "iter_anchor_rows_from_extra_rows",
    "iter_rows_decorated",
    "populate_link_inventory_cache",
]
