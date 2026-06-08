"""Canonical broken internal link metrics (single source of truth).

All executive surfaces (Dashboard KPI, narratives, FixPlan instance totals,
Link Intelligence summary formulas, and per-URL ``Broken Internal Links Count``)
must align with anchor-level rows on the Link Inventory sheet: one count per
internal ``<a>`` whose target returned HTTP 4xx/5xx when checked.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_LINK_INVENTORY_DATA_END_ROW = 50_000


def is_internal_link_type(link_type: object) -> bool:
    return str(link_type or "").strip().lower() == "internal"


def parse_http_status_code(status: object) -> int | None:
    if status is None or status == "":
        return None
    if isinstance(status, (int, float)):
        code = int(status)
        return code if 100 <= code < 600 else None
    text = str(status).strip()
    if not text:
        return None
    token = text.split()[0]
    try:
        code = int(token)
    except ValueError:
        return None
    return code if 100 <= code < 600 else None


def is_broken_http_status(status: object) -> bool:
    code = parse_http_status_code(status)
    return code is not None and 400 <= code < 600


@dataclass(frozen=True)
class BrokenInternalLinkMetrics:
    """Aggregate broken-internal metrics derived from flat Link Inventory rows."""

    instances: int
    affected_urls: int


def summarize_broken_internal_links(
    link_rows: list[dict[str, Any]],
) -> BrokenInternalLinkMetrics:
    instances = 0
    sources: set[str] = set()
    for row in link_rows:
        if not is_internal_link_type(row.get("Link Type")):
            continue
        if not is_broken_http_status(row.get("Status Code")):
            continue
        instances += 1
        source = str(row.get("Source URL") or "").strip()
        if source:
            sources.add(source)
    return BrokenInternalLinkMetrics(instances=instances, affected_urls=len(sources))


def count_broken_internal_instances(link_rows: list[dict[str, Any]]) -> int:
    return summarize_broken_internal_links(link_rows).instances


def count_broken_internal_from_link_details(
    link_details: list[dict[str, Any]],
) -> int:
    count = 0
    for item in link_details:
        if not is_internal_link_type(item.get("Link Type")):
            continue
        if is_broken_http_status(item.get("Status Code")):
            count += 1
    return count


def link_inventory_broken_internal_total_formula() -> str:
    """Excel formula: total broken internal link instances on Link Inventory."""
    end = _LINK_INVENTORY_DATA_END_ROW
    return (
        f"=SUMPRODUCT(('Link Inventory'!$E$2:$E${end}=\"Internal\")*"
        f"('Link Inventory'!$F$2:$F${end}>=400)*"
        f"('Link Inventory'!$F$2:$F${end}<600))"
    )


def link_inventory_broken_per_source_formula(source_cell_ref: str) -> str:
    """Excel formula: broken internal instances for one source URL (Link Intelligence)."""
    end = _LINK_INVENTORY_DATA_END_ROW
    inv = "'Link Inventory'"
    return (
        f"=SUMPRODUCT(({inv}!$A$2:$A${end}={source_cell_ref})*"
        f"({inv}!$E$2:$E${end}=\"Internal\")*"
        f"({inv}!$F$2:$F${end}>=400)*"
        f"({inv}!$F$2:$F${end}<600))"
    )


__all__ = [
    "BrokenInternalLinkMetrics",
    "count_broken_internal_from_link_details",
    "count_broken_internal_instances",
    "is_broken_http_status",
    "is_internal_link_type",
    "link_inventory_broken_internal_total_formula",
    "link_inventory_broken_per_source_formula",
    "parse_http_status_code",
    "summarize_broken_internal_links",
]
