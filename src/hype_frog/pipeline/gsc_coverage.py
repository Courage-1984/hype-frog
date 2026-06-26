"""GSC Search Analytics match status, freshness labels, and coverage notes."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from hype_frog.core.url_normalization import normalize_url as normalize_url_key

_LOW_IMPRESSIONS_CTR_THRESHOLD = 10


def format_gsc_data_freshness(
    period_start: date | None,
    period_end: date | None,
) -> str | None:
    """Human-readable GSC reporting window (bulk Search Analytics query)."""
    if period_start is None or period_end is None:
        return None
    return (
        f"{period_start.isoformat()} to {period_end.isoformat()} "
        "(30-day window; excludes today; typical GSC lag ~48h)"
    )


def lookup_gsc_metrics(
    gsc_map: Mapping[str, Any],
    *,
    url_key: str,
    normalized_key: str,
    seed_url: str,
    final_url: str | None,
) -> dict[str, Any] | None:
    """Resolve GSC bulk analytics for a crawled row using URL variants."""
    candidates = (
        url_key,
        normalized_key,
        normalize_url_key(seed_url),
        normalize_url_key(final_url or ""),
        normalize_url_key(url_key, keep_query=False),
        normalize_url_key(final_url or "", keep_query=False),
    )
    seen: set[str] = set()
    for key in candidates:
        if not key or key in seen:
            continue
        seen.add(key)
        entry = gsc_map.get(key)
        if isinstance(entry, dict):
            return entry
    return None


def _to_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def resolve_gsc_coverage_note(
    *,
    analytics_succeeded: bool,
    matched: bool,
    impressions: float,
    clicks: float,
) -> str:
    """Per-URL note explaining GSC metric completeness and CTR confidence."""
    if not analytics_succeeded:
        return (
            "GSC unavailable — missing credentials, property mismatch, or Search Analytics API error"
        )
    if not matched:
        return (
            "No Search Analytics row matched this URL in the 30-day export "
            "(compare Final URL with the page URL shown in GSC)"
        )
    if impressions <= 0.0 and clicks <= 0.0:
        return "Matched in GSC — zero impressions in period (CTR not meaningful)"
    if impressions < _LOW_IMPRESSIONS_CTR_THRESHOLD:
        return (
            f"Matched in GSC — low impressions ({int(impressions)}); "
            "CTR is directional only"
        )
    return "Matched in GSC — Search Analytics (30-day window)"


def apply_gsc_coverage_fields(
    row_values: dict[str, Any],
    *,
    gsc_map: Mapping[str, Any],
    url_key: str,
    normalized_key: str,
    analytics_succeeded: bool,
    gsc_data_freshness: str | None,
) -> None:
    """Set GSC metrics, freshness, and coverage note on an extra/main row dict."""
    seed_url = str(row_values.get("URL") or url_key or "").strip()
    final_url = str(row_values.get("Final URL") or url_key or "").strip() or None
    gsc = lookup_gsc_metrics(
        gsc_map,
        url_key=url_key,
        normalized_key=normalized_key,
        seed_url=seed_url,
        final_url=final_url,
    )
    if gsc_data_freshness:
        row_values["GSC Data Freshness"] = gsc_data_freshness

    if gsc:
        impressions = _to_float(gsc.get("GSC Impressions"))
        clicks = _to_float(gsc.get("GSC Clicks"))
        row_values["GSC Clicks"] = clicks
        row_values["GSC Impressions"] = impressions
        row_values["GSC CTR"] = _to_float(gsc.get("GSC CTR"))
        row_values["GSC Avg Position"] = _to_float(gsc.get("GSC Average Position"))
        row_values["GSC Coverage Note"] = resolve_gsc_coverage_note(
            analytics_succeeded=analytics_succeeded,
            matched=True,
            impressions=impressions,
            clicks=clicks,
        )
    else:
        row_values["GSC Clicks"] = None
        row_values["GSC Impressions"] = None
        row_values["GSC CTR"] = None
        row_values["GSC Avg Position"] = None
        row_values["GSC Coverage Note"] = resolve_gsc_coverage_note(
            analytics_succeeded=analytics_succeeded,
            matched=False,
            impressions=0.0,
            clicks=0.0,
        )


__all__ = [
    "apply_gsc_coverage_fields",
    "format_gsc_data_freshness",
    "lookup_gsc_metrics",
    "resolve_gsc_coverage_note",
]
