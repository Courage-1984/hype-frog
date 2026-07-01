"""Streaming Link Inventory flattening without holding all anchors in RAM."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

from hype_frog.checkpoint.link_inventory_cache import LinkInventoryCache
from hype_frog.core.memory_guard import memory_circuit_breaker
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


__all__ = [
    "anchor_row_from_link_item",
    "build_link_inventory_rows_list",
    "iter_anchor_rows_from_extra_rows",
    "populate_link_inventory_cache",
]
