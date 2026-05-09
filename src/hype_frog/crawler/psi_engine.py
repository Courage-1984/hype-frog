from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import aiohttp

from hype_frog.core import get_logger

logger = get_logger(__name__)

_CACHE_TTL_SECONDS = 24 * 60 * 60
_PSI_BASE = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
_DEFAULT_CONCURRENT_REQUESTS = 4
_MAX_RETRY_ATTEMPTS = 6
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
_INITIAL_BACKOFF_S = 1.0
_MAX_BACKOFF_S = 60.0


def get_psi_api_key() -> str | None:
    return os.getenv("PSI_API_KEY") or None


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

    # INP (CrUX): INTERACTION_TO_NEXT_PAINT percentile is in milliseconds.
    for inp_key in ("INTERACTION_TO_NEXT_PAINT", "EXPERIMENTAL_INTERACTION_TO_NEXT_PAINT"):
        inp_m = metrics.get(inp_key)
        if isinstance(inp_m, dict) and inp_m.get("percentile") is not None:
            out["inp_ms"] = round(float(inp_m["percentile"]), 2)
            break

    # Legacy FID — only if INP missing (pre-INP CrUX snapshots).
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
    # Repeated category= limits payload vs full Lighthouse run.
    q = (
        f"url={quote(url, safe='')}"
        f"&strategy={quote(strategy, safe='')}"
        "&category=performance&category=seo"
        f"&key={quote(api_key, safe='')}"
    )
    return f"{_PSI_BASE}?{q}"


async def _fetch_strategy_raw(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    conn: sqlite3.Connection,
    cache_lock: threading.Lock,
    url: str,
    api_key: str,
    strategy: str,
) -> dict[str, Any]:
    with cache_lock:
        cached = _cache_get(conn, url, strategy)
    if cached is not None:
        return cached

    endpoint = _build_endpoint(url, strategy, api_key)
    delay = _INITIAL_BACKOFF_S
    last_status: int | None = None

    for attempt in range(_MAX_RETRY_ATTEMPTS):
        payload: dict[str, Any] | None = None
        try:
            async with semaphore:
                async with session.get(
                    endpoint,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as response:
                    last_status = response.status
                    if response.status in _RETRY_STATUSES:
                        if attempt + 1 >= _MAX_RETRY_ATTEMPTS:
                            logger.warning(
                                "PSI gave %s for %s (%s) after retries.",
                                response.status,
                                strategy,
                                url,
                            )
                            return {}
                        await asyncio.sleep(delay)
                        delay = min(delay * 2.0, _MAX_BACKOFF_S)
                        continue
                    if response.status >= 400:
                        logger.warning(
                            "PSI HTTP %s for %s (%s).",
                            response.status,
                            strategy,
                            url,
                        )
                        return {}
                    payload = await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as exc:
            if attempt + 1 >= _MAX_RETRY_ATTEMPTS:
                logger.warning("PSI request failed for %s (%s): %s", strategy, url, exc)
                return {}
            await asyncio.sleep(delay)
            delay = min(delay * 2.0, _MAX_BACKOFF_S)
            continue

        if payload is None or not isinstance(payload, dict) or "lighthouseResult" not in payload:
            logger.warning("PSI malformed JSON for %s (%s).", strategy, url)
            return {}

        with cache_lock:
            _cache_put(conn, url, strategy, payload)
        return payload

    if last_status is not None:
        logger.warning("PSI exhausted retries (%s) for %s (%s).", last_status, strategy, url)
    return {}


def _score_or_zero(raw: int | None) -> int:
    return int(raw or 0)


def _float_or_zero(raw: float | None) -> float:
    return float(raw or 0.0)


def _merge_url_results(
    target_url: str,
    mobile_raw: dict[str, Any],
    desktop_raw: dict[str, Any],
) -> dict[str, Any]:
    mobile = _parse_pagespeed_payload(mobile_raw) if mobile_raw else {"lab": {}, "field": None}
    desktop = _parse_pagespeed_payload(desktop_raw) if desktop_raw else {"lab": {}, "field": None}

    m_lab = mobile["lab"] or {}
    d_lab = desktop["lab"] or {}
    field_mobile = mobile.get("field")

    has_field = bool(field_mobile)
    field_vs_lab = "Field" if has_field else "Lab"
    cwv_source = "PSI API (CrUX)" if has_field else "PSI API (Lighthouse Lab)"

    lab_mobile_inp = m_lab.get("inp_ms")
    lab_desktop_inp = d_lab.get("inp_ms")

    # Prefer CrUX for dashboard CWV columns when the URL has field data; else lab mobile.
    cwv_lcp = (
        field_mobile.get("lcp_seconds")
        if has_field and field_mobile.get("lcp_seconds") is not None
        else m_lab.get("lcp_seconds")
    )
    cwv_cls = (
        field_mobile.get("cls")
        if has_field and field_mobile.get("cls") is not None
        else m_lab.get("cls")
    )
    cwv_inp = (
        field_mobile.get("inp_ms")
        if has_field and field_mobile.get("inp_ms") is not None
        else lab_mobile_inp
    )

    merged_flat: dict[str, Any] = {
        "URL": target_url,
        "Desktop Score": _score_or_zero(d_lab.get("performance_score")),
        "Mobile Score": _score_or_zero(m_lab.get("performance_score")),
        "Desktop SEO Score": _score_or_zero(d_lab.get("seo_score")),
        "Mobile SEO Score": _score_or_zero(m_lab.get("seo_score")),
        "Mobile LCP": _float_or_zero(m_lab.get("lcp_seconds")),
        "Mobile CLS": _float_or_zero(m_lab.get("cls")),
        "Mobile TTFB": round(_float_or_zero(m_lab.get("ttfb_seconds")), 3),
        "Desktop LCP": _float_or_zero(d_lab.get("lcp_seconds")),
        "Desktop CLS": _float_or_zero(d_lab.get("cls")),
        "Desktop TTFB": round(_float_or_zero(d_lab.get("ttfb_seconds")), 3),
        "Lab Mobile INP (ms)": _float_or_zero(lab_mobile_inp),
        "Lab Desktop INP (ms)": _float_or_zero(lab_desktop_inp),
        "Field Mobile LCP (s)": field_mobile.get("lcp_seconds") if field_mobile else None,
        "Field Mobile CLS": field_mobile.get("cls") if field_mobile else None,
        "Field Mobile INP (ms)": field_mobile.get("inp_ms") if field_mobile else None,
        "has_field_crux": has_field,
        "CWV LCP (s)": _float_or_zero(cwv_lcp),
        "CWV CLS": _float_or_zero(cwv_cls),
        "CWV INP (ms)": _float_or_zero(cwv_inp),
        "Field vs Lab": field_vs_lab,
        "CWV Data Source": cwv_source,
        "psi_metrics": {
            "lab": {"mobile": m_lab, "desktop": d_lab},
            "field": {"mobile": field_mobile} if field_mobile else None,
        },
    }
    return merged_flat


async def fetch_psi_metrics_batch(
    session: aiohttp.ClientSession,
    urls: list[str],
    max_parallel: int = _DEFAULT_CONCURRENT_REQUESTS,
    max_urls: int | None = None,
) -> dict[str, dict[str, Any]]:
    """Fetch PSI metrics per URL (mobile + desktop lab; CrUX field when available).

    Results are keyed by crawled URL string. Each value includes backward-compatible
    flat keys consumed by ``row_with_psi_gsc_harden`` plus nested ``psi_metrics`` lab/field data.
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
    completed = 0
    total = len(unique_urls)
    progress_lock = asyncio.Lock()

    conn = _open_cache_db()
    cache_lock = threading.Lock()
    try:
        logger.info(
            "PSI batch started: %s URLs (concurrent_requests=%s, cache_ttl=%sh).",
            total,
            max_parallel,
            _CACHE_TTL_SECONDS // 3600,
        )

        async def _worker(target_url: str) -> None:
            nonlocal completed
            mobile_raw = await _fetch_strategy_raw(
                session, semaphore, conn, cache_lock, target_url, api_key, "mobile"
            )
            desktop_raw = await _fetch_strategy_raw(
                session, semaphore, conn, cache_lock, target_url, api_key, "desktop"
            )
            if not mobile_raw and not desktop_raw:
                logger.warning("PSI unavailable for URL: %s", target_url)
            else:
                results[target_url] = _merge_url_results(target_url, mobile_raw, desktop_raw)
            async with progress_lock:
                completed += 1
                logger.info("PSI progress: %s/%s URLs processed.", completed, total)

        await asyncio.gather(*[_worker(url) for url in unique_urls])
    finally:
        conn.close()

    logger.info("PSI batch complete: %s/%s URLs returned metrics.", len(results), total)
    return results
