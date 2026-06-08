from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import aiohttp

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
_STRATEGY_GAP_S = 0.35
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


def _crux_cls_from_percentile(raw: float) -> float:
    """CrUX CLS percentiles are often stored as hundredths (e.g. 12 → 0.12)."""
    v = float(raw)
    if v > 1.0:
        return round(v / 100.0, 4)
    return round(v, 4)


def _field_experience_metrics(payload: dict[str, Any]) -> dict[str, Any] | None:
    exp = payload.get("loadingExperience") or payload.get("originLoadingExperience")
    if not isinstance(exp, dict):
        return None
    metrics = exp.get("metrics")
    if not isinstance(metrics, dict):
        return None

    out: dict[str, Any] = {}
    lcp = metrics.get("LARGEST_CONTENTFUL_PAINT_MS")
    if isinstance(lcp, dict) and lcp.get("percentile") is not None:
        out["lcp_seconds"] = round(float(lcp["percentile"]) / 1000.0, 3)

    cls_metric = metrics.get("CUMULATIVE_LAYOUT_SHIFT_SCORE")
    if isinstance(cls_metric, dict) and cls_metric.get("percentile") is not None:
        out["cls"] = _crux_cls_from_percentile(float(cls_metric["percentile"]))

    for inp_key in ("INTERACTION_TO_NEXT_PAINT", "EXPERIMENTAL_INTERACTION_TO_NEXT_PAINT"):
        inp_m = metrics.get(inp_key)
        if isinstance(inp_m, dict) and inp_m.get("percentile") is not None:
            out["inp_ms"] = round(float(inp_m["percentile"]), 2)
            break

    if "inp_ms" not in out:
        fid = metrics.get("FIRST_INPUT_DELAY_MS")
        if isinstance(fid, dict) and fid.get("percentile") is not None:
            out["inp_ms"] = round(float(fid["percentile"]), 2)

    return out if out else None


def _parse_pagespeed_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Split Lighthouse lab metrics vs CrUX field metrics when present."""
    lab = _lab_strategy_metrics(payload)
    field = _field_experience_metrics(payload)
    return {"lab": lab, "field": field}


def _build_endpoint(url: str, strategy: str, api_key: str) -> str:
    q = (
        f"url={quote(url, safe='')}"
        f"&strategy={quote(strategy, safe='')}"
        "&category=performance&category=seo"
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


async def _fetch_strategy_raw(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    conn: sqlite3.Connection,
    cache_lock: threading.Lock,
    url: str,
    api_key: str,
    strategy: str,
    abort_state: _BatchAbortState,
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
                        await asyncio.sleep(delay)
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
                        await asyncio.sleep(delay)
                        delay = min(delay * 2.0, _MAX_BACKOFF_S)
                        continue

                    payload = body
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            last_error = str(exc)
            if attempt + 1 >= _MAX_RETRY_ATTEMPTS:
                logger.warning("PSI request failed for %s (%s): %s", strategy, url, exc)
                return {}, last_error
            await asyncio.sleep(delay)
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

    mobile = _parse_pagespeed_payload(mobile_raw) if mobile_ok else {"lab": {}, "field": None}
    desktop = _parse_pagespeed_payload(desktop_raw) if desktop_ok else {"lab": {}, "field": None}

    m_lab = mobile["lab"] or {}
    d_lab = desktop["lab"] or {}
    field_mobile = mobile.get("field")

    has_field = bool(field_mobile)
    field_vs_lab = "Field" if has_field else "Lab"
    cwv_source = "PSI API (CrUX)" if has_field else "PSI API (Lighthouse Lab)"

    lab_mobile_inp = m_lab.get("inp_ms")
    lab_desktop_inp = d_lab.get("inp_ms")

    cwv_lcp = (
        field_mobile.get("lcp_seconds")
        if has_field and field_mobile and field_mobile.get("lcp_seconds") is not None
        else m_lab.get("lcp_seconds") if mobile_ok else None
    )
    cwv_cls = (
        field_mobile.get("cls")
        if has_field and field_mobile and field_mobile.get("cls") is not None
        else m_lab.get("cls") if mobile_ok else None
    )
    cwv_inp = (
        field_mobile.get("inp_ms")
        if has_field and field_mobile and field_mobile.get("inp_ms") is not None
        else lab_mobile_inp if mobile_ok else None
    )

    psi_data_status = _resolve_psi_data_status(
        mobile_ok=mobile_ok,
        desktop_ok=desktop_ok,
        has_field=has_field,
        mobile_error=mobile_error,
        desktop_error=desktop_error,
    )

    merged_flat: dict[str, Any] = {
        "URL": target_url,
        "PSI Data Status": psi_data_status,
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
        "Field Mobile LCP (s)": field_mobile.get("lcp_seconds") if field_mobile else None,
        "Field Mobile CLS": field_mobile.get("cls") if field_mobile else None,
        "Field Mobile INP (ms)": field_mobile.get("inp_ms") if field_mobile else None,
        "has_field_crux": has_field,
        "CWV LCP (s)": _optional_float(cwv_lcp),
        "CWV CLS": _optional_float(cwv_cls),
        "CWV INP (ms)": _optional_float(cwv_inp),
        "Field vs Lab": field_vs_lab,
        "CWV Data Source": cwv_source,
        "psi_metrics": {
            "lab": {"mobile": m_lab, "desktop": d_lab},
            "field": {"mobile": field_mobile} if field_mobile else None,
        },
    }
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
    if status.startswith("Complete"):
        return "complete"
    if status.startswith("Partial"):
        return "partial"
    if status == "Lab only":
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
                )
                if _STRATEGY_GAP_S > 0:
                    await asyncio.sleep(_STRATEGY_GAP_S)
                desktop_raw, desktop_error = await _fetch_strategy_raw(
                    session,
                    semaphore,
                    conn,
                    cache_lock,
                    target_url,
                    api_key,
                    "desktop",
                    abort_state,
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
    timeout_seconds: float = 45.0,
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
        return False, f"PSI request failed: {exc}", details
