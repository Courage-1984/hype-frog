"""GSC URL Inspection API field projection for export rows (B4)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from hype_frog.core.url_normalization import normalize_url_key

GSC_INSPECTION_LIMIT_DEFAULT = 50


def _norm_index_status(verdict: object) -> str | None:
    if verdict is None:
        return None
    token = str(verdict).strip().upper()
    if token == "PASS":
        return "INDEXED"
    if token == "FAIL":
        return "NOT_INDEXED"
    if token == "NEUTRAL":
        return "NEUTRAL"
    return str(verdict).strip() or None


def _norm_usability(verdict: object) -> str | None:
    if verdict is None:
        return None
    token = str(verdict).strip().upper()
    if token == "PASS":
        return "MOBILE_FRIENDLY"
    if token == "FAIL":
        return "NOT_MOBILE_FRIENDLY"
    return str(verdict).strip() or None


def _norm_rich_results(verdict: object) -> str | None:
    if verdict is None:
        return None
    token = str(verdict).strip().upper()
    if token in {"PASS", "VALID"}:
        return "VALID"
    if token in {"FAIL", "INVALID"}:
        return "INVALID"
    if token in {"NEUTRAL", "NONE", ""}:
        return "NONE"
    return str(verdict).strip() or None


def _parse_last_crawl_date(raw: object) -> tuple[str | None, int | None]:
    if raw is None or str(raw).strip() == "":
        return None, None
    text = str(raw).strip()
    parsed: datetime | None = None
    for fmt in (
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
    ):
        try:
            parsed = datetime.strptime(text.replace("+00:00", "Z"), fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            break
        except ValueError:
            continue
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return text, None
    date_only = parsed.date().isoformat()
    days = max(0, (datetime.now(timezone.utc).date() - parsed.date()).days)
    return date_only, days


def parse_gsc_inspection_payload(payload: dict[str, Any]) -> dict[str, str | int | None]:
    """Map raw URL Inspection JSON to export-friendly B4 columns."""
    result = payload.get("inspectionResult") or {}
    idx = result.get("indexStatusResult") or {}
    mobile = result.get("mobileUsabilityResult") or {}
    rich = result.get("richResultsResult") or {}
    verdict = idx.get("verdict")
    coverage_state = idx.get("coverageState")
    last_crawl_raw = idx.get("lastCrawlTime") or idx.get("last_crawl_time")
    last_crawl_date, days_since = _parse_last_crawl_date(last_crawl_raw)
    index_status = _norm_index_status(verdict)
    return {
        "GSC Inspection Coverage": "Inspected",
        "GSC Inspection Verdict": str(verdict) if verdict is not None else None,
        "GSC Inspection Coverage State": str(coverage_state) if coverage_state is not None else None,
        "GSC Inspection Google Canonical": (
            str(idx.get("googleCanonical")) if idx.get("googleCanonical") is not None else None
        ),
        "GSC Inspection Crawl State": (
            str(idx.get("pageFetchState")) if idx.get("pageFetchState") is not None else None
        ),
        "GSC Inspection Robots State": (
            str(idx.get("robotsTxtState")) if idx.get("robotsTxtState") is not None else None
        ),
        "GSC Inspection Last Crawl": str(last_crawl_raw).strip() if last_crawl_raw else None,
        "GSC Index Status": index_status,
        "GSC Last Crawl Date": last_crawl_date,
        "GSC Mobile Usability": _norm_usability(mobile.get("verdict")),
        "GSC Rich Result Status": _norm_rich_results(rich.get("verdict")),
        "GSC Coverage Reason": str(coverage_state).strip() if coverage_state else None,
        "Days Since Last Crawl": days_since,
    }


def apply_gsc_inspection_fields(
    row_values: dict[str, Any],
    inspection_fields: dict[str, str | int | None] | None,
) -> None:
    """Merge parsed inspection columns onto a row dict in place."""
    if not inspection_fields:
        return
    row_values.update(inspection_fields)


def select_gsc_inspection_urls(
    candidates: list[str],
    *,
    mode: str,
    limit: int = GSC_INSPECTION_LIMIT_DEFAULT,
) -> list[str]:
    """Dedupe and cap inspection targets per B4 gating rules."""
    unique = list(dict.fromkeys(url for url in candidates if str(url or "").strip()))
    if mode == "full":
        return unique
    return unique[: max(1, limit)] if mode == "limited" else []


def inspection_url_candidates_from_rows(
    main_rows: list[Any],
    extra_rows: list[Any],
    *,
    analytics_query_succeeded: bool,
    gsc_metrics: dict[str, dict[str, float]],
    gate_fn: Any,
) -> list[str]:
    """Build smart-gate inspection URL list (indexable + 200 + zero impressions)."""
    if not analytics_query_succeeded:
        return []
    targets: list[str] = []
    for main_row, extra_row in zip(main_rows, extra_rows, strict=False):
        ev = extra_row.values if hasattr(extra_row, "values") else extra_row
        mv = main_row.values if hasattr(main_row, "values") else main_row
        url_key = str(ev.get("Final URL") or ev.get("URL") or "").strip()
        if not url_key:
            continue
        nk = normalize_url_key(url_key)
        if gate_fn(
            analytics_query_succeeded=analytics_query_succeeded,
            main_values=mv,
            extra_values=ev,
            url_key=url_key,
            normalized_key=nk,
            gsc_metrics=gsc_metrics,
        ):
            targets.append(url_key)
    return targets


__all__ = [
    "GSC_INSPECTION_LIMIT_DEFAULT",
    "apply_gsc_inspection_fields",
    "inspection_url_candidates_from_rows",
    "parse_gsc_inspection_payload",
    "select_gsc_inspection_urls",
]
