"""Redirect chain parsing, display, and SEO risk signals (A3)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from hype_frog.core.url_normalization import normalize_url

PERMANENT_REDIRECT_STATUSES: frozenset[int] = frozenset({301, 308})
TEMPORARY_REDIRECT_STATUSES: frozenset[int] = frozenset({302, 303, 307})
REDIRECT_MAP_MAX_HOP_COLUMNS = 3


@dataclass(frozen=True)
class RedirectHopRecord:
    url: str
    status: int


def hops_from_history(history: list[Any]) -> list[RedirectHopRecord]:
    """Build hop records from aiohttp ``response.history`` entries."""
    records: list[RedirectHopRecord] = []
    for entry in history:
        try:
            records.append(
                RedirectHopRecord(
                    url=str(entry.url),
                    status=int(entry.status),
                )
            )
        except (AttributeError, TypeError, ValueError):
            continue
    return records


def format_redirect_chain_display(
    source_url: str,
    hop_records: list[RedirectHopRecord],
    *,
    final_url: str | None,
) -> str:
    """Human-readable chain: ``A → [301] → B → [302] → C``."""
    if not hop_records:
        return ""
    parts: list[str] = [source_url.strip()]
    for index, hop in enumerate(hop_records):
        parts.append(f"[{hop.status}]")
        if index + 1 < len(hop_records):
            parts.append(hop_records[index + 1].url)
        elif final_url:
            parts.append(final_url)
    return " → ".join(parts)


def redirect_chain_hops_json(hop_records: list[RedirectHopRecord]) -> str | None:
    if not hop_records:
        return None
    payload = [{"url": hop.url, "status": hop.status} for hop in hop_records]
    return json.dumps(payload, ensure_ascii=False)


def has_temporary_redirect(hop_records: list[RedirectHopRecord]) -> bool:
    return any(hop.status in TEMPORARY_REDIRECT_STATUSES for hop in hop_records)


def has_mixed_redirect_types(hop_records: list[RedirectHopRecord]) -> bool:
    permanent = any(hop.status in PERMANENT_REDIRECT_STATUSES for hop in hop_records)
    temporary = has_temporary_redirect(hop_records)
    return permanent and temporary


def is_redirect_loop(
    source_url: str,
    final_url: str | None,
    hop_records: list[RedirectHopRecord],
) -> bool:
    if not hop_records or not final_url:
        return False
    src = source_url.strip()
    dst = final_url.strip()
    if src == dst:
        return True
    # Differ only by trailing slash → trailing-slash redirect, never a loop
    if src.rstrip("/") == dst.rstrip("/"):
        return False
    try:
        return normalize_url(src, keep_query=True) == normalize_url(dst, keep_query=True)
    except Exception:
        return False


def redirect_seo_risk(
    *,
    hop_records: list[RedirectHopRecord],
    redirect_loop: bool,
    source_url: str = "",
    final_url: str | None = None,
) -> str:
    if redirect_loop:
        return "Redirect loop"
    if has_mixed_redirect_types(hop_records):
        return "Mixed permanent/temporary redirects"
    if has_temporary_redirect(hop_records):
        return "Temporary redirect (302/303/307) in chain"
    if len(hop_records) > 1:
        return "Multi-hop chain"
    if hop_records:
        if (
            source_url
            and final_url
            and hop_records[0].status in PERMANENT_REDIRECT_STATUSES
            and source_url.strip().rstrip("/") == final_url.strip().rstrip("/")
        ):
            return "Trailing slash redirect (301)"
        return "Single redirect"
    return ""


def build_redirect_chain_fields(
    *,
    source_url: str,
    hop_records: list[RedirectHopRecord],
    final_url: str | None,
) -> dict[str, Any]:
    """Return extra/main row fragments for redirect chain columns."""
    chain_length = len(hop_records)
    loop_flag = is_redirect_loop(source_url, final_url, hop_records)
    has_302 = has_temporary_redirect(hop_records)
    mixed = has_mixed_redirect_types(hop_records)
    legacy_hops = None
    if hop_records and final_url:
        legacy_hops = " -> ".join([hop.url for hop in hop_records] + [final_url])

    return {
        "Redirect Chain Length": chain_length,
        "Redirect Chain": format_redirect_chain_display(
            source_url, hop_records, final_url=final_url
        )
        or None,
        "Redirect Chain Hops": redirect_chain_hops_json(hop_records),
        "Has 302 in Chain": has_302,
        "Has Mixed Redirect Types": mixed,
        "Redirect Loop Flag": loop_flag,
        "Redirect Hops": legacy_hops,
        "Redirect Target": final_url if hop_records else None,
        "Final URL": final_url.strip() if final_url else None,
        "Redirect SEO Risk": redirect_seo_risk(
            hop_records=hop_records,
            redirect_loop=loop_flag,
            source_url=source_url,
            final_url=final_url,
        ),
    }


def normalize_url_key_safe(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return normalize_url(url, keep_query=True)
    except Exception:
        return url.strip() or None


def build_redirect_map_row(
    *,
    source_url: str,
    hop_records: list[RedirectHopRecord],
    final_url: str | None,
    fields: dict[str, Any],
) -> dict[str, Any]:
    """One Redirect Map sheet row for a source URL with redirects."""
    row: dict[str, Any] = {
        "Source URL": source_url,
        "Final URL": fields.get("Final URL") or final_url,
        "Chain Length": fields.get("Redirect Chain Length", 0),
        "Has 302": fields.get("Has 302 in Chain", False),
        "SEO Risk": fields.get("Redirect SEO Risk") or "",
        "Redirect Chain": fields.get("Redirect Chain") or "",
    }
    for index in range(REDIRECT_MAP_MAX_HOP_COLUMNS):
        hop_num = index + 1
        hop = hop_records[index] if index < len(hop_records) else None
        row[f"Hop {hop_num} URL"] = hop.url if hop else None
        row[f"Hop {hop_num} Status"] = hop.status if hop else None
    if len(hop_records) > REDIRECT_MAP_MAX_HOP_COLUMNS:
        row["SEO Risk"] = (
            f"{row['SEO Risk']} (+{len(hop_records) - REDIRECT_MAP_MAX_HOP_COLUMNS} more hops)"
            if row["SEO Risk"]
            else f"Chain exceeds {REDIRECT_MAP_MAX_HOP_COLUMNS} hops"
        )
    return row


__all__ = [
    "REDIRECT_MAP_MAX_HOP_COLUMNS",
    "RedirectHopRecord",
    "build_redirect_chain_fields",
    "build_redirect_map_row",
    "format_redirect_chain_display",
    "has_mixed_redirect_types",
    "has_temporary_redirect",
    "hops_from_history",
    "is_redirect_loop",
    "redirect_seo_risk",
]
