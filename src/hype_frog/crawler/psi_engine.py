from __future__ import annotations

import asyncio
import json
import os
import random
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import aiohttp

from hype_frog.config import (
    get_psi_base_delay_seconds,
    get_psi_jitter_fraction,
    get_psi_strategy_gap_seconds,
)
from hype_frog.core import get_logger
from hype_frog.core.url_normalization import normalize_url

logger = get_logger(__name__)

_CACHE_TTL_SECONDS = 24 * 60 * 60
_PSI_BASE = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
_DEFAULT_CONCURRENT_REQUESTS = 3
_MAX_RETRY_ATTEMPTS = 6
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
_INITIAL_BACKOFF_S = 1.0
_MAX_BACKOFF_S = 60.0
_MAX_CLIENT_ERROR_RETRIES = 3

_API_KEY_ERROR_RE = re.compile(
    r"API[_\s-]?key|invalid.*key|permission denied|API has not been used",
    re.IGNORECASE,
)
_RETRYABLE_ERROR_RE = re.compile(
    r"quota|rate.?limit|timeout|timed.?out|unavailable|failed_document_request|"
    r"lighthouse.*error|could not load|chrome crashed|renderer|dns|socket",
    re.IGNORECASE,
)


def _jittered_seconds(base_seconds: float, jitter_fraction: float) -> float:
    """Return ``base_seconds`` ± ``jitter_fraction`` × ``base_seconds``."""
    jitter = random.uniform(-jitter_fraction, jitter_fraction) * base_seconds
    return max(0.0, base_seconds + jitter)


async def _jittered_delay(
    base_seconds: float | None = None,
    jitter_fraction: float | None = None,
) -> None:
    """Wait for a jittered interval (defaults to PSI base delay settings)."""
    base = base_seconds if base_seconds is not None else get_psi_base_delay_seconds()
    fraction = jitter_fraction if jitter_fraction is not None else get_psi_jitter_fraction()
    await asyncio.sleep(_jittered_seconds(base, fraction))


class _PsiRequestPacer:
    """Serialises minimum spacing between outbound PSI HTTP requests."""

    def __init__(self, base_seconds: float, jitter_fraction: float) -> None:
        self._base_seconds = base_seconds
        self._jitter_fraction = jitter_fraction
        self._lock = asyncio.Lock()
        self._last_request_at: float | None = None

    async def wait(self) -> None:
        async with self._lock:
            if self._last_request_at is not None:
                elapsed = time.monotonic() - self._last_request_at
                target = _jittered_seconds(self._base_seconds, self._jitter_fraction)
                remaining = target - elapsed
                if remaining > 0:
                    await asyncio.sleep(remaining)
            self._last_request_at = time.monotonic()


def get_psi_api_key() -> str | None:
    return os.getenv("PSI_API_KEY") or None


def psi_index_key(url: object) -> str:
    """Canonical key for PSI map lookups (matches crawl ``normalize_url_key``)."""
    return normalize_url(url, keep_query=True)


@dataclass
class _BatchAbortState:
    api_key_rejected: bool = False
    reject_reason: str = ""


def _project_root() -> Path:
    # psi_engine.py -> crawler -> hype_frog -> src -> repo root
    return Path(__file__).resolve().parents[3]


def _cache_db_path() -> Path:
    cache_dir = _project_root() / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "psi_metrics.sqlite"


def _open_cache_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_cache_db_path(), timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS psi_cache (
            url TEXT NOT NULL,
            strategy TEXT NOT NULL,
            response_body TEXT NOT NULL,
            fetched_at REAL NOT NULL,
            PRIMARY KEY (url, strategy)
        )
        """
    )
    conn.commit()
    return conn


def _cache_get(conn: sqlite3.Connection, url: str, strategy: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT response_body, fetched_at FROM psi_cache WHERE url = ? AND strategy = ?",
        (url, strategy),
    ).fetchone()
    if not row:
        return None
    body, fetched_at = row
    if time.time() - float(fetched_at) > _CACHE_TTL_SECONDS:
        conn.execute("DELETE FROM psi_cache WHERE url = ? AND strategy = ?", (url, strategy))
        conn.commit()
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        conn.execute("DELETE FROM psi_cache WHERE url = ? AND strategy = ?", (url, strategy))
        conn.commit()
        return None


def _cache_put(conn: sqlite3.Connection, url: str, strategy: str, payload: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO psi_cache (url, strategy, response_body, fetched_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(url, strategy) DO UPDATE SET
            response_body = excluded.response_body,
            fetched_at = excluded.fetched_at
        """,
        (url, strategy, json.dumps(payload, separators=(",", ":"), sort_keys=True), time.time()),
    )
    conn.commit()


def _extract_api_error_message(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    error_block = payload.get("error")
    if not isinstance(error_block, dict):
        return None
    message = str(error_block.get("message") or "").strip()
    return message or None


def _is_api_key_error(http_status: int, message: str | None) -> bool:
    if http_status == 403:
        return True
    if http_status == 400 and message and _API_KEY_ERROR_RE.search(message):
        return True
    return False


def _is_retryable_psi_error(http_status: int, message: str | None) -> bool:
    if http_status in _RETRY_STATUSES:
        return True
    if http_status == 400 and message and _RETRYABLE_ERROR_RE.search(message):
        return True
    return False


_PSI_CATEGORIES: tuple[str, ...] = (
    "performance",
    "accessibility",
    "best-practices",
    "seo",
)

PSI_LIGHTHOUSE_EXPORT_KEYS: tuple[str, ...] = (
    "Lighthouse Performance (Mobile)",
    "Lighthouse Accessibility (Mobile)",
    "Lighthouse Best Practices (Mobile)",
    "Lighthouse SEO Score (Mobile)",
    "Lab LCP (Mobile) (s)",
    "Lab CLS (Mobile)",
    "Lab TBT (Mobile) (ms)",
    "Lab INP (Mobile) (ms)",
    "Lab FCP (Mobile) (s)",
    "Lab Speed Index (Mobile) (s)",
    "Lab TTI (Mobile) (s)",
    "Lab TTFB (Mobile) (ms)",
    "Lighthouse Performance (Desktop)",
    "Lighthouse Accessibility (Desktop)",
    "Lighthouse Best Practices (Desktop)",
    "Lighthouse SEO Score (Desktop)",
    "Lab LCP (Desktop) (s)",
    "Lab CLS (Desktop)",
    "Lab TBT (Desktop) (ms)",
    "Lab INP (Desktop) (ms)",
    "Lab FCP (Desktop) (s)",
    "Lab Speed Index (Desktop) (s)",
    "Lab TTI (Desktop) (s)",
    "Lab TTFB (Desktop) (ms)",
    "Page Size (KB)",
    "DOM Size (nodes)",
    "JS Execution (ms)",
    "Network Request Count",
    "Has Text Compression",
    "Has Long Cache TTL Issues",
    "Has Render Blocking Resources",
    "Uses Modern Image Formats",
)


def _audit_numeric(payload: dict[str, Any], audit_id: str) -> float | None:
    try:
        raw = payload["lighthouseResult"]["audits"][audit_id]["numericValue"]
        if raw is None:
            return None
        return float(raw)
    except (KeyError, TypeError, ValueError):
        return None


def _category_score(payload: dict[str, Any], category: str) -> int | None:
    try:
        score = payload["lighthouseResult"]["categories"][category]["score"]
        if score is None:
            return None
        return int(round(float(score) * 100))
    except (KeyError, TypeError, ValueError):
        return None


def _lab_strategy_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload.get("lighthouseResult"), dict):
        return {
            "performance_score": None,
            "seo_score": None,
            "lcp_seconds": None,
            "cls": None,
            "inp_ms": None,
            "ttfb_seconds": None,
        }
    lcp_ms = _audit_numeric(payload, "largest-contentful-paint")
    cls_raw = _audit_numeric(payload, "cumulative-layout-shift")
    inp_ms = _audit_numeric(payload, "interaction-to-next-paint")
    ttfb_seconds: float | None = None
    for key in ("server-response-time", "network-server-latency"):
        ms = _audit_numeric(payload, key)
        if ms is not None:
            ttfb_seconds = ms / 1000.0
            break
    return {
        "performance_score": _category_score(payload, "performance"),
        "seo_score": _category_score(payload, "seo"),
        "lcp_seconds": round(lcp_ms / 1000.0, 3) if lcp_ms is not None else None,
        "cls": round(float(cls_raw), 4) if cls_raw is not None else None,
        "inp_ms": round(float(inp_ms), 2) if inp_ms is not None else None,
        "ttfb_seconds": round(float(ttfb_seconds), 4) if ttfb_seconds is not None else None,
    }


def _extract_lighthouse_data(
    lighthouse_result: dict[str, Any],
    prefix: str = "mobile",
) -> dict[str, Any]:
    """Extract comprehensive Lighthouse lab data for export columns."""
    out: dict[str, Any] = {}
    if not lighthouse_result:
        return out

    audits = lighthouse_result.get("audits", {})
    categories = lighthouse_result.get("categories", {})

    def audit_score(key: str) -> int | None:
        audit = audits.get(key, {})
        if not isinstance(audit, dict):
            return None
        score = audit.get("score")
        if score is None:
            return None
        return int(round(float(score) * 100))

    def audit_ms(key: str) -> float | None:
        audit = audits.get(key, {})
        if not isinstance(audit, dict):
            return None
        value = audit.get("numericValue")
        if value is None:
            return None
        return round(float(value), 1)

    def audit_s(key: str) -> float | None:
        ms_value = audit_ms(key)
        return round(ms_value / 1000.0, 3) if ms_value is not None else None

    def cat_score(key: str) -> int | None:
        category = categories.get(key, {})
        if not isinstance(category, dict):
            return None
        score = category.get("score")
        if score is None:
            return None
        return int(round(float(score) * 100))

    label = prefix.capitalize()

    out[f"Lighthouse Performance ({label})"] = cat_score("performance")
    out[f"Lighthouse Accessibility ({label})"] = cat_score("accessibility")
    out[f"Lighthouse Best Practices ({label})"] = cat_score("best-practices")
    out[f"Lighthouse SEO Score ({label})"] = cat_score("seo")

    out[f"Lab LCP ({label}) (s)"] = audit_s("largest-contentful-paint")
    cls_audit = audits.get("cumulative-layout-shift", {})
    cls_val = cls_audit.get("numericValue") if isinstance(cls_audit, dict) else None
    out[f"Lab CLS ({label})"] = round(float(cls_val), 4) if cls_val is not None else None
    out[f"Lab TBT ({label}) (ms)"] = audit_ms("total-blocking-time")
    out[f"Lab INP ({label}) (ms)"] = audit_ms("interaction-to-next-paint")
    out[f"Lab FCP ({label}) (s)"] = audit_s("first-contentful-paint")
    out[f"Lab Speed Index ({label}) (s)"] = audit_s("speed-index")
    out[f"Lab TTI ({label}) (s)"] = audit_s("interactive")

    ttfb_ms = audit_ms("server-response-time")
    if ttfb_ms is None:
        ttfb_ms = audit_ms("network-server-latency")
    out[f"Lab TTFB ({label}) (ms)"] = ttfb_ms

    if prefix == "mobile":
        total_bytes = audits.get("total-byte-weight", {}).get("numericValue")
        out["Page Size (KB)"] = (
            round(float(total_bytes) / 1024.0, 1) if total_bytes is not None else None
        )
        dom_size = audits.get("dom-size", {}).get("numericValue")
        out["DOM Size (nodes)"] = int(dom_size) if dom_size is not None else None
        js_exec = audits.get("bootup-time", {}).get("numericValue")
        out["JS Execution (ms)"] = round(float(js_exec), 1) if js_exec is not None else None
        net_req = audits.get("network-requests", {})
        items = (net_req.get("details") or {}).get("items", []) if isinstance(net_req, dict) else []
        out["Network Request Count"] = len(items) if items else None

        compression_score = audit_score("uses-text-compression")
        cache_score = audit_score("uses-long-cache-ttl")
        render_score = audit_score("render-blocking-resources")
        webp_score = audit_score("uses-webp-images")
        modern_score = audit_score("modern-image-formats")
        out["Has Text Compression"] = compression_score == 100
        out["Has Long Cache TTL Issues"] = (
            cache_score is not None and cache_score < 100
        )
        out["Has Render Blocking Resources"] = (
            render_score is not None and render_score < 100
        )
        out["Uses Modern Image Formats"] = webp_score == 100 or modern_score == 100

    return out


def _extract_psi_network_payload(
    raw_payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Extract Lighthouse network-requests and render-blocking URLs for A2."""
    lh = raw_payload.get("lighthouseResult")
    if not isinstance(lh, dict):
        return [], []
    audits = lh.get("audits", {})
    if not isinstance(audits, dict):
        return [], []

    net_req = audits.get("network-requests", {})
    raw_items: list[Any] = []
    if isinstance(net_req, dict):
        details = net_req.get("details") or {}
        if isinstance(details, dict):
            raw_items = details.get("items") or []

    items: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        items.append(
            {
                "url": url,
                "transferSize": item.get("transferSize"),
                "resourceType": item.get("resourceType"),
            }
        )

    blocking: list[str] = []
    rb_audit = audits.get("render-blocking-resources", {})
    if isinstance(rb_audit, dict):
        rb_details = rb_audit.get("details") or {}
        if isinstance(rb_details, dict):
            for rb_item in rb_details.get("items") or []:
                if isinstance(rb_item, dict) and rb_item.get("url"):
                    blocking.append(str(rb_item["url"]))

    return items, blocking


def _apply_lighthouse_extraction(
    merged_flat: dict[str, Any],
    *,
    mobile_raw: dict[str, Any],
    desktop_raw: dict[str, Any],
    mobile_ok: bool,
    desktop_ok: bool,
) -> None:
    """Merge Lighthouse lab columns and sync legacy PSI score/LCP keys."""
    if mobile_ok:
        mobile_lh = mobile_raw.get("lighthouseResult")
        if isinstance(mobile_lh, dict):
            merged_flat.update(_extract_lighthouse_data(mobile_lh, prefix="mobile"))
    if desktop_ok:
        desktop_lh = desktop_raw.get("lighthouseResult")
        if isinstance(desktop_lh, dict):
            merged_flat.update(_extract_lighthouse_data(desktop_lh, prefix="desktop"))

    mobile_perf = merged_flat.get("Lighthouse Performance (Mobile)")
    if mobile_perf is not None:
        merged_flat["Mobile Score"] = mobile_perf
    desktop_perf = merged_flat.get("Lighthouse Performance (Desktop)")
    if desktop_perf is not None:
        merged_flat["Desktop Score"] = desktop_perf

    if merged_flat.get("Mobile LCP") is None:
        lab_lcp = merged_flat.get("Lab LCP (Mobile) (s)")
        if lab_lcp is not None:
            merged_flat["Mobile LCP"] = lab_lcp
    if merged_flat.get("Mobile CLS") is None:
        lab_cls = merged_flat.get("Lab CLS (Mobile)")
        if lab_cls is not None:
            merged_flat["Mobile CLS"] = lab_cls
    if merged_flat.get("Mobile TTFB") is None:
        ttfb_ms = merged_flat.get("Lab TTFB (Mobile) (ms)")
        if ttfb_ms is not None:
            merged_flat["Mobile TTFB"] = round(float(ttfb_ms) / 1000.0, 3)


def _crux_cls_from_percentile(raw: float) -> float:
    """CrUX CLS percentiles are often stored as hundredths (e.g. 12 → 0.12)."""
    v = float(raw)
    if v > 1.0:
        return round(v / 100.0, 4)
    return round(v, 4)


def _detect_crux_level(
    payload: dict[str, Any],
    requested_url: str,
) -> tuple[dict[str, Any] | None, str]:
    """Return CrUX metrics and level: ``URL``, ``Origin``, or ``None``."""
    url_exp = payload.get("loadingExperience")
    origin_exp = payload.get("originLoadingExperience")

    if url_exp:
        if url_exp.get("origin_fallback") is True:
            if isinstance(origin_exp, dict) and origin_exp.get("metrics"):
                return origin_exp.get("metrics"), "Origin"
            if isinstance(url_exp.get("metrics"), dict):
                return url_exp.get("metrics"), "Origin"
            return None, "Origin"

        exp_id = str(url_exp.get("id") or "")
        if exp_id:
            exp_parsed = urlparse(exp_id.rstrip("/"))
            req_parsed = urlparse(str(requested_url or "").rstrip("/"))
            if exp_parsed.path in ("", "/") and req_parsed.path not in ("", "/"):
                if isinstance(origin_exp, dict) and origin_exp.get("metrics"):
                    return origin_exp.get("metrics"), "Origin"
                if isinstance(url_exp.get("metrics"), dict):
                    return url_exp.get("metrics"), "Origin"
                return None, "Origin"

        if isinstance(url_exp.get("metrics"), dict) and url_exp.get("metrics"):
            return url_exp.get("metrics"), "URL"

    if isinstance(origin_exp, dict) and origin_exp.get("metrics"):
        return origin_exp.get("metrics"), "Origin"

    return None, "None"


def _extract_crux_metric(
    metrics: dict[str, Any],
    metric_key: str,
    *,
    to_seconds: bool = False,
) -> float | None:
    """Extract the 75th percentile value from a CrUX metrics dict."""
    metric = metrics.get(metric_key, {})
    if not isinstance(metric, dict):
        return None
    percentile = metric.get("percentile")
    if percentile is None:
        return None
    val = float(percentile)
    if metric_key == "CUMULATIVE_LAYOUT_SHIFT_SCORE":
        return _crux_cls_from_percentile(val)
    if to_seconds:
        return round(val / 1000.0, 3)
    return round(val, 2)


def _extract_crux_category(metrics: dict[str, Any], metric_key: str) -> str | None:
    metric = metrics.get(metric_key, {})
    if not isinstance(metric, dict):
        return None
    category = metric.get("category")
    return str(category) if category is not None else None


def _parsed_crux_snapshot(metrics: dict[str, Any]) -> dict[str, Any]:
    """Flatten raw CrUX metrics into legacy ``lcp_seconds`` / ``cls`` / ``inp_ms`` keys."""
    out: dict[str, Any] = {}
    lcp = _extract_crux_metric(metrics, "LARGEST_CONTENTFUL_PAINT_MS", to_seconds=True)
    if lcp is not None:
        out["lcp_seconds"] = lcp
    cls_val = _extract_crux_metric(metrics, "CUMULATIVE_LAYOUT_SHIFT_SCORE")
    if cls_val is not None:
        out["cls"] = cls_val
    inp = _extract_crux_metric(metrics, "INTERACTION_TO_NEXT_PAINT")
    if inp is None:
        inp = _extract_crux_metric(metrics, "EXPERIMENTAL_INTERACTION_TO_NEXT_PAINT")
    if inp is None:
        inp = _extract_crux_metric(metrics, "FIRST_INPUT_DELAY_MS")
    if inp is not None:
        out["inp_ms"] = inp
    return out


def _field_experience_metrics(
    payload: dict[str, Any],
    requested_url: str = "",
) -> dict[str, Any] | None:
    """Legacy CrUX snapshot helper retained for unit tests and nested ``psi_metrics``."""
    metrics, level = _detect_crux_level(payload, requested_url)
    if not metrics:
        return None
    out = _parsed_crux_snapshot(metrics)
    if not out:
        return None
    out["crux_data_level"] = (
        "origin" if level == "Origin" else "url" if level == "URL" else "none"
    )
    return out


def _apply_crux_columns(
    merged_flat: dict[str, Any],
    *,
    crux_metrics: dict[str, Any] | None,
    crux_level: str,
) -> None:
    """Populate URL-level vs origin-level CrUX columns on the merged PSI flat dict."""
    null_cwv_keys = (
        "CWV LCP (s)",
        "CWV CLS",
        "CWV INP (ms)",
        "CWV FCP (ms)",
        "CWV TTFB (ms)",
        "CrUX LCP Category",
        "CrUX CLS Category",
        "CrUX INP Category",
        "Origin CrUX LCP (s)",
        "Origin CrUX CLS",
        "Origin CrUX INP (ms)",
    )
    for key in null_cwv_keys:
        merged_flat[key] = None

    if crux_level == "URL" and crux_metrics:
        merged_flat["CWV LCP (s)"] = _extract_crux_metric(
            crux_metrics, "LARGEST_CONTENTFUL_PAINT_MS", to_seconds=True
        )
        merged_flat["CWV CLS"] = _extract_crux_metric(
            crux_metrics, "CUMULATIVE_LAYOUT_SHIFT_SCORE"
        )
        merged_flat["CWV INP (ms)"] = _extract_crux_metric(
            crux_metrics, "INTERACTION_TO_NEXT_PAINT"
        )
        if merged_flat["CWV INP (ms)"] is None:
            merged_flat["CWV INP (ms)"] = _extract_crux_metric(
                crux_metrics, "EXPERIMENTAL_INTERACTION_TO_NEXT_PAINT"
            )
        if merged_flat["CWV INP (ms)"] is None:
            merged_flat["CWV INP (ms)"] = _extract_crux_metric(
                crux_metrics, "FIRST_INPUT_DELAY_MS"
            )
        merged_flat["CWV FCP (ms)"] = _extract_crux_metric(
            crux_metrics, "FIRST_CONTENTFUL_PAINT_MS"
        )
        merged_flat["CWV TTFB (ms)"] = _extract_crux_metric(
            crux_metrics, "EXPERIMENTAL_TIME_TO_FIRST_BYTE"
        )
        merged_flat["CrUX LCP Category"] = _extract_crux_category(
            crux_metrics, "LARGEST_CONTENTFUL_PAINT_MS"
        )
        merged_flat["CrUX CLS Category"] = _extract_crux_category(
            crux_metrics, "CUMULATIVE_LAYOUT_SHIFT_SCORE"
        )
        merged_flat["CrUX INP Category"] = _extract_crux_category(
            crux_metrics, "INTERACTION_TO_NEXT_PAINT"
        )
    elif crux_level == "Origin" and crux_metrics:
        merged_flat["Origin CrUX LCP (s)"] = _extract_crux_metric(
            crux_metrics, "LARGEST_CONTENTFUL_PAINT_MS", to_seconds=True
        )
        merged_flat["Origin CrUX CLS"] = _extract_crux_metric(
            crux_metrics, "CUMULATIVE_LAYOUT_SHIFT_SCORE"
        )
        merged_flat["Origin CrUX INP (ms)"] = _extract_crux_metric(
            crux_metrics, "INTERACTION_TO_NEXT_PAINT"
        )
        if merged_flat["Origin CrUX INP (ms)"] is None:
            merged_flat["Origin CrUX INP (ms)"] = _extract_crux_metric(
                crux_metrics, "EXPERIMENTAL_INTERACTION_TO_NEXT_PAINT"
            )
        if merged_flat["Origin CrUX INP (ms)"] is None:
            merged_flat["Origin CrUX INP (ms)"] = _extract_crux_metric(
                crux_metrics, "FIRST_INPUT_DELAY_MS"
            )


def _parse_pagespeed_payload(
    payload: dict[str, Any],
    requested_url: str = "",
) -> dict[str, Any]:
    """Split Lighthouse lab metrics vs CrUX field metrics when present."""
    lab = _lab_strategy_metrics(payload)
    field = _field_experience_metrics(payload, requested_url)
    return {"lab": lab, "field": field}


def _build_endpoint(url: str, strategy: str, api_key: str) -> str:
    category_params = "".join(f"&category={quote(cat, safe='')}" for cat in _PSI_CATEGORIES)
    q = (
        f"url={quote(url, safe='')}"
        f"&strategy={quote(strategy, safe='')}"
        f"{category_params}"
        f"&key={quote(api_key, safe='')}"
    )
    return f"{_PSI_BASE}?{q}"


def _strategy_ok(raw: dict[str, Any]) -> bool:
    return bool(raw and isinstance(raw, dict) and "lighthouseResult" in raw)


def _optional_int(raw: int | None) -> int | None:
    return int(raw) if raw is not None else None


def _optional_float(raw: float | None) -> float | None:
    return float(raw) if raw is not None else None


def _resolve_psi_data_status(
    *,
    mobile_ok: bool,
    desktop_ok: bool,
    has_field: bool,
    mobile_error: str | None,
    desktop_error: str | None,
) -> str:
    if mobile_ok and desktop_ok:
        return "Complete (Lab + Field)" if has_field else "Lab only"
    if mobile_ok and not desktop_ok:
        detail = f": {desktop_error}" if desktop_error else ""
        return f"Partial (desktop unavailable{detail})"
    if desktop_ok and not mobile_ok:
        detail = f": {mobile_error}" if mobile_error else ""
        return f"Partial (mobile unavailable{detail})"
    parts: list[str] = []
    if mobile_error:
        parts.append(f"mobile: {mobile_error}")
    if desktop_error:
        parts.append(f"desktop: {desktop_error}")
    if parts:
        return "Unavailable (" + "; ".join(parts) + ")"
    return "Unavailable"


def _resolve_cwv_labelling(
    *,
    has_lab: bool,
    crux_level: str,
) -> tuple[str, str, str]:
    """Return ``(PSI Data Status, Field vs Lab, CWV Data Source)``."""
    if crux_level == "URL":
        if has_lab:
            return (
                "PSI + CrUX Field (URL)",
                "Field (URL-level CrUX)",
                "CrUX API (URL-level)",
            )
        return (
            "CrUX Field (URL)",
            "Field (URL-level CrUX)",
            "CrUX API (URL-level)",
        )

    if crux_level == "Origin":
        if has_lab:
            return (
                "PSI + CrUX Field (Origin)",
                "Lab (Origin CrUX available)",
                "CrUX API (Origin-level)",
            )
        return (
            "CrUX Field (Origin)",
            "Field (Origin)",
            "CrUX API (Origin-level)",
        )

    if has_lab:
        return ("PSI Lab", "Lab only", "None")

    return ("Not available", "N/A", "None")


async def _fetch_strategy_raw(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    conn: sqlite3.Connection,
    cache_lock: threading.Lock,
    url: str,
    api_key: str,
    strategy: str,
    abort_state: _BatchAbortState,
    *,
    pacer: _PsiRequestPacer | None = None,
) -> tuple[dict[str, Any], str | None]:
    if abort_state.api_key_rejected:
        return {}, abort_state.reject_reason or "PSI API key rejected"

    with cache_lock:
        cached = _cache_get(conn, url, strategy)
    if cached is not None:
        return cached, None

    endpoint = _build_endpoint(url, strategy, api_key)
    delay = _INITIAL_BACKOFF_S
    last_status: int | None = None
    last_error: str | None = None
    client_error_attempts = 0

    for attempt in range(_MAX_RETRY_ATTEMPTS):
        payload: dict[str, Any] | None = None
        try:
            async with semaphore:
                if pacer is not None:
                    await pacer.wait()
                async with session.get(
                    endpoint,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as response:
                    last_status = response.status
                    try:
                        body = await response.json()
                    except json.JSONDecodeError:
                        body = None

                    if response.status in _RETRY_STATUSES or (
                        response.status == 400
                        and _is_retryable_psi_error(response.status, _extract_api_error_message(body))
                    ):
                        last_error = _extract_api_error_message(body) or f"HTTP {response.status}"
                        if response.status == 400:
                            client_error_attempts += 1
                            if client_error_attempts >= _MAX_CLIENT_ERROR_RETRIES:
                                logger.warning(
                                    "PSI HTTP %s for %s (%s) after client-error retries: %s",
                                    response.status,
                                    strategy,
                                    url,
                                    last_error,
                                )
                                return {}, last_error
                        elif attempt + 1 >= _MAX_RETRY_ATTEMPTS:
                            logger.warning(
                                "PSI gave %s for %s (%s) after retries: %s",
                                response.status,
                                strategy,
                                url,
                                last_error,
                            )
                            return {}, last_error
                        await _jittered_delay(delay, get_psi_jitter_fraction())
                        delay = min(delay * 2.0, _MAX_BACKOFF_S)
                        continue

                    if response.status >= 400:
                        last_error = _extract_api_error_message(body) or f"HTTP {response.status}"
                        if _is_api_key_error(response.status, last_error):
                            abort_state.api_key_rejected = True
                            abort_state.reject_reason = last_error
                            logger.error(
                                "PSI API key rejected (HTTP %s). Aborting remaining PSI requests: %s",
                                response.status,
                                last_error,
                            )
                            return {}, last_error
                        logger.warning(
                            "PSI HTTP %s for %s (%s): %s",
                            response.status,
                            strategy,
                            url,
                            last_error,
                        )
                        return {}, last_error

                    if not isinstance(body, dict):
                        last_error = "Malformed JSON response"
                        if attempt + 1 >= _MAX_RETRY_ATTEMPTS:
                            logger.warning("PSI malformed JSON for %s (%s).", strategy, url)
                            return {}, last_error
                        await _jittered_delay(delay, get_psi_jitter_fraction())
                        delay = min(delay * 2.0, _MAX_BACKOFF_S)
                        continue

                    payload = body
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            last_error = str(exc)
            if attempt + 1 >= _MAX_RETRY_ATTEMPTS:
                logger.warning("PSI request failed for %s (%s): %s", strategy, url, exc)
                return {}, last_error
            await _jittered_delay(delay, get_psi_jitter_fraction())
            delay = min(delay * 2.0, _MAX_BACKOFF_S)
            continue

        if payload is None or not isinstance(payload, dict) or "lighthouseResult" not in payload:
            last_error = "Missing lighthouseResult in PSI response"
            logger.warning("PSI malformed JSON for %s (%s).", strategy, url)
            return {}, last_error

        with cache_lock:
            _cache_put(conn, url, strategy, payload)
        return payload, None

    if last_status is not None:
        logger.warning(
            "PSI exhausted retries (%s) for %s (%s): %s",
            last_status,
            strategy,
            url,
            last_error or "unknown",
        )
    return {}, last_error or f"HTTP {last_status}" if last_status else "PSI request failed"


def _merge_url_results(
    target_url: str,
    mobile_raw: dict[str, Any],
    desktop_raw: dict[str, Any],
    *,
    mobile_error: str | None = None,
    desktop_error: str | None = None,
) -> dict[str, Any]:
    mobile_ok = _strategy_ok(mobile_raw)
    desktop_ok = _strategy_ok(desktop_raw)

    mobile = (
        _parse_pagespeed_payload(mobile_raw, target_url)
        if mobile_ok
        else {"lab": {}, "field": None}
    )
    desktop = (
        _parse_pagespeed_payload(desktop_raw, target_url)
        if desktop_ok
        else {"lab": {}, "field": None}
    )

    m_lab = mobile["lab"] or {}
    d_lab = desktop["lab"] or {}

    crux_metrics: dict[str, Any] | None = None
    crux_level = "None"
    for raw in (mobile_raw, desktop_raw):
        if isinstance(raw, dict) and raw:
            crux_metrics, crux_level = _detect_crux_level(raw, target_url)
            if crux_level != "None":
                break
    else:
        crux_metrics, crux_level = None, "None"
    field_mobile = mobile.get("field")
    if crux_level == "URL" and crux_metrics:
        field_mobile = _parsed_crux_snapshot(crux_metrics)
        field_mobile["crux_data_level"] = "url"
    elif crux_level == "Origin" and crux_metrics:
        field_mobile = _parsed_crux_snapshot(crux_metrics)
        field_mobile["crux_data_level"] = "origin"

    has_lab = mobile_ok or desktop_ok
    has_crux = crux_level in {"URL", "Origin"} and bool(crux_metrics)

    if has_lab or has_crux:
        psi_data_status, field_vs_lab, cwv_source = _resolve_cwv_labelling(
            has_lab=has_lab,
            crux_level=crux_level,
        )
    else:
        psi_data_status = _resolve_psi_data_status(
            mobile_ok=mobile_ok,
            desktop_ok=desktop_ok,
            has_field=False,
            mobile_error=mobile_error,
            desktop_error=desktop_error,
        )
        field_vs_lab = "N/A"
        cwv_source = "None"

    lab_mobile_inp = m_lab.get("inp_ms")
    lab_desktop_inp = d_lab.get("inp_ms")

    merged_flat: dict[str, Any] = {
        "URL": target_url,
        "PSI Data Status": psi_data_status,
        "CrUX Level": crux_level,
        "Desktop Score": _optional_int(d_lab.get("performance_score")) if desktop_ok else None,
        "Mobile Score": _optional_int(m_lab.get("performance_score")) if mobile_ok else None,
        "Desktop SEO Score": _optional_int(d_lab.get("seo_score")) if desktop_ok else None,
        "Mobile SEO Score": _optional_int(m_lab.get("seo_score")) if mobile_ok else None,
        "Mobile LCP": _optional_float(m_lab.get("lcp_seconds")) if mobile_ok else None,
        "Mobile CLS": _optional_float(m_lab.get("cls")) if mobile_ok else None,
        "Mobile TTFB": (
            round(float(m_lab["ttfb_seconds"]), 3)
            if mobile_ok and m_lab.get("ttfb_seconds") is not None
            else None
        ),
        "Desktop LCP": _optional_float(d_lab.get("lcp_seconds")) if desktop_ok else None,
        "Desktop CLS": _optional_float(d_lab.get("cls")) if desktop_ok else None,
        "Desktop TTFB": (
            round(float(d_lab["ttfb_seconds"]), 3)
            if desktop_ok and d_lab.get("ttfb_seconds") is not None
            else None
        ),
        "Lab Mobile INP (ms)": _optional_float(lab_mobile_inp) if mobile_ok else None,
        "Lab Desktop INP (ms)": _optional_float(lab_desktop_inp) if desktop_ok else None,
        "Field Mobile LCP (s)": (
            field_mobile.get("lcp_seconds") if field_mobile and crux_level == "URL" else None
        ),
        "Field Mobile CLS": (
            field_mobile.get("cls") if field_mobile and crux_level == "URL" else None
        ),
        "Field Mobile INP (ms)": (
            field_mobile.get("inp_ms") if field_mobile and crux_level == "URL" else None
        ),
        "has_field_crux": has_crux,
        "Field vs Lab": field_vs_lab,
        "CWV Data Source": cwv_source,
        "psi_metrics": {
            "lab": {"mobile": m_lab, "desktop": d_lab},
            "field": {"mobile": field_mobile} if field_mobile else None,
        },
    }
    _apply_crux_columns(merged_flat, crux_metrics=crux_metrics, crux_level=crux_level)
    _apply_lighthouse_extraction(
        merged_flat,
        mobile_raw=mobile_raw,
        desktop_raw=desktop_raw,
        mobile_ok=mobile_ok,
        desktop_ok=desktop_ok,
    )
    network_source = mobile_raw if mobile_ok else desktop_raw if desktop_ok else {}
    network_items, blocking_urls = _extract_psi_network_payload(network_source)
    merged_flat["PSI Network Items"] = network_items
    merged_flat["PSI Render Blocking URLs"] = blocking_urls
    return merged_flat


def _store_psi_result(results: dict[str, dict[str, Any]], target_url: str, merged: dict[str, Any]) -> None:
    """Index PSI rows under raw and normalized URL keys for enrichment lookup."""
    results[target_url] = merged
    norm = psi_index_key(target_url)
    if norm and norm != target_url:
        results[norm] = merged


@dataclass
class PsiBatchSummary:
    total: int = 0
    complete: int = 0
    partial: int = 0
    lab_only: int = 0
    unavailable: int = 0


def _classify_psi_status(status: str) -> str:
    normalized = str(status or "").strip()
    if normalized.startswith("PSI + CrUX") or normalized.startswith("CrUX Field"):
        return "complete"
    if normalized == "PSI Lab":
        return "lab_only"
    if normalized.startswith("Complete"):
        return "complete"
    if normalized.startswith("Partial"):
        return "partial"
    if normalized in {"Lab only"}:
        return "lab_only"
    return "unavailable"


async def fetch_psi_metrics_batch(
    session: aiohttp.ClientSession,
    urls: list[str],
    max_parallel: int = _DEFAULT_CONCURRENT_REQUESTS,
    max_urls: int | None = None,
) -> dict[str, dict[str, Any]]:
    """Fetch PSI metrics per URL (mobile + desktop lab; CrUX field when available).

    Results are keyed by crawled URL string and normalized URL. Each value includes
    flat keys consumed by ``row_with_psi_gsc_harden`` plus nested ``psi_metrics``.
  """
    api_key = get_psi_api_key()
    if not api_key:
        logger.warning("PSI API key missing. Skipping PSI enrichment.")
        return {}

    unique_urls = [u for u in dict.fromkeys([str(url or "").strip() for url in urls]) if u]
    if max_urls is not None and max_urls > 0:
        unique_urls = unique_urls[:max_urls]
    if not unique_urls:
        logger.info("PSI batch skipped: no URLs provided.")
        return {}

    semaphore = asyncio.Semaphore(max(1, min(max_parallel, 8)))
    results: dict[str, dict[str, Any]] = {}
    summary = PsiBatchSummary(total=len(unique_urls))
    completed = 0
    progress_lock = asyncio.Lock()
    abort_state = _BatchAbortState()

    conn = _open_cache_db()
    cache_lock = threading.Lock()
    pacer = _PsiRequestPacer(get_psi_base_delay_seconds(), get_psi_jitter_fraction())
    try:
        logger.info(
            "PSI batch started: %s URLs (concurrent_requests=%s, cache_ttl=%sh).",
            summary.total,
            max_parallel,
            _CACHE_TTL_SECONDS // 3600,
        )

        async def _worker(target_url: str) -> None:
            nonlocal completed
            if abort_state.api_key_rejected:
                unavailable = _merge_url_results(
                    target_url,
                    {},
                    {},
                    mobile_error=abort_state.reject_reason,
                    desktop_error=abort_state.reject_reason,
                )
                _store_psi_result(results, target_url, unavailable)
                summary.unavailable += 1
            else:
                mobile_raw, mobile_error = await _fetch_strategy_raw(
                    session,
                    semaphore,
                    conn,
                    cache_lock,
                    target_url,
                    api_key,
                    "mobile",
                    abort_state,
                    pacer=pacer,
                )
                strategy_gap = get_psi_strategy_gap_seconds()
                if strategy_gap > 0:
                    await _jittered_delay(strategy_gap, get_psi_jitter_fraction())
                desktop_raw, desktop_error = await _fetch_strategy_raw(
                    session,
                    semaphore,
                    conn,
                    cache_lock,
                    target_url,
                    api_key,
                    "desktop",
                    abort_state,
                    pacer=pacer,
                )
                mobile_ok = _strategy_ok(mobile_raw)
                desktop_ok = _strategy_ok(desktop_raw)
                if not mobile_ok and not desktop_ok:
                    logger.warning(
                        "PSI unavailable for URL %s (mobile: %s; desktop: %s).",
                        target_url,
                        mobile_error or "no data",
                        desktop_error or "no data",
                    )
                    merged = _merge_url_results(
                        target_url,
                        mobile_raw,
                        desktop_raw,
                        mobile_error=mobile_error,
                        desktop_error=desktop_error,
                    )
                    _store_psi_result(results, target_url, merged)
                    summary.unavailable += 1
                else:
                    merged = _merge_url_results(
                        target_url,
                        mobile_raw,
                        desktop_raw,
                        mobile_error=mobile_error if not mobile_ok else None,
                        desktop_error=desktop_error if not desktop_ok else None,
                    )
                    _store_psi_result(results, target_url, merged)
                    bucket = _classify_psi_status(str(merged.get("PSI Data Status") or ""))
                    if bucket == "complete":
                        summary.complete += 1
                    elif bucket == "partial":
                        summary.partial += 1
                    elif bucket == "lab_only":
                        summary.lab_only += 1
                    else:
                        summary.unavailable += 1

            async with progress_lock:
                completed += 1
                logger.info("PSI progress: %s/%s URLs processed.", completed, summary.total)

        await asyncio.gather(*[_worker(url) for url in unique_urls])
    finally:
        conn.close()

    logger.info(
        "PSI batch complete: %s URL(s) indexed; complete=%s partial=%s lab_only=%s unavailable=%s.",
        len({psi_index_key(url) for url in unique_urls}),
        summary.complete,
        summary.partial,
        summary.lab_only,
        summary.unavailable,
    )
    return results


async def probe_psi_api_key(
    test_url: str = "https://example.com",
    *,
    timeout_seconds: float = 90.0,
) -> tuple[bool, str, dict[str, Any] | None]:
    """Verify ``PSI_API_KEY`` with a single mobile Lighthouse request.

    Returns:
        ``(ok, message, details)`` where ``details`` may include HTTP status,
        parsed lab scores, and any Google API error payload.
    """
    api_key = get_psi_api_key()
    if not api_key:
        return False, "PSI_API_KEY is not set in .env.", None

    endpoint = _build_endpoint(test_url, "mobile", api_key)
    details: dict[str, Any] = {"test_url": test_url, "strategy": "mobile"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                endpoint,
                timeout=aiohttp.ClientTimeout(total=timeout_seconds),
            ) as response:
                details["http_status"] = response.status
                try:
                    payload = await response.json()
                except json.JSONDecodeError:
                    payload = None

                if response.status == 200 and isinstance(payload, dict):
                    if "lighthouseResult" not in payload:
                        return (
                            False,
                            "PSI responded with HTTP 200 but no lighthouseResult was present.",
                            details,
                        )
                    lab = _lab_strategy_metrics(payload)
                    details["lab_metrics"] = lab
                    perf = lab.get("performance_score")
                    seo = lab.get("seo_score")
                    return (
                        True,
                        (
                            "PageSpeed Insights API is reachable and returned Lighthouse data "
                            f"(mobile performance={perf}, seo={seo})."
                        ),
                        details,
                    )

                error_message = _extract_api_error_message(payload)
                if isinstance(payload, dict):
                    error_block = payload.get("error") or {}
                    if isinstance(error_block, dict):
                        details["api_error"] = error_block

                if response.status == 400:
                    if error_message and not _API_KEY_ERROR_RE.search(error_message):
                        return (
                            False,
                            (
                                f"PSI rejected the request for the test URL (HTTP 400). "
                                f"{error_message} "
                                "Your API key may still be valid — batch failures for specific URLs "
                                "often mean Google could not load that page."
                            ),
                            details,
                        )
                    hint = (
                        "Check that PSI_API_KEY is correct and belongs to an active Google Cloud project."
                    )
                    return (
                        False,
                        f"PSI rejected the API key (HTTP 400). {error_message or hint}",
                        details,
                    )
                if response.status == 403:
                    hint = (
                        "Enable the PageSpeed Insights API for this key's Google Cloud project "
                        "and confirm the key is not over-restricted."
                    )
                    return False, f"PSI access denied (HTTP 403). {error_message or hint}", details
                if response.status == 429:
                    return (
                        True,
                        "PSI API key is valid but quota/rate limit was hit (HTTP 429). Retry later.",
                        details,
                    )

                return (
                    False,
                    f"PSI request failed with HTTP {response.status}. {error_message or 'No error detail returned.'}",
                    details,
                )
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        detail = str(exc).strip() or type(exc).__name__
        if isinstance(exc, TimeoutError):
            detail = f"request timed out after {timeout_seconds:.0f}s"
        return False, f"PSI request failed: {detail}", details
