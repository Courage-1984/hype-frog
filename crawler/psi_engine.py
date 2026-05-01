from __future__ import annotations

import asyncio
import os
from typing import Any
from urllib.parse import quote

import aiohttp
from core import get_logger

logger = get_logger(__name__)


def get_psi_api_key() -> str | None:
    return os.getenv("PSI_API_KEY") or None


def _extract_metric(payload: dict[str, Any], metric_key: str) -> float | None:
    try:
        return float(payload["lighthouseResult"]["audits"][metric_key]["numericValue"])
    except Exception:
        return None


def _extract_score(payload: dict[str, Any]) -> int | None:
    try:
        return int(round(float(payload["lighthouseResult"]["categories"]["performance"]["score"]) * 100))
    except Exception:
        return None


def _extract_ttfb(payload: dict[str, Any]) -> float | None:
    # Prefer explicit TTFB audit, then fallback to server response time.
    for key in ("server-response-time", "network-server-latency"):
        metric = _extract_metric(payload, key)
        if metric is not None:
            return metric / 1000.0
    return None


async def _fetch_strategy(
    session: aiohttp.ClientSession,
    url: str,
    api_key: str,
    strategy: str,
    max_retries: int = 2,
) -> dict[str, Any]:
    endpoint = (
        "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
        f"?url={quote(url, safe='')}&strategy={strategy}&category=performance&key={api_key}"
    )
    delay = 1.0
    for attempt in range(max_retries + 1):
        try:
            async with session.get(endpoint, timeout=aiohttp.ClientTimeout(total=45)) as response:
                if response.status in {429, 500, 502, 503, 504} and attempt < max_retries:
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                if response.status >= 400:
                    return {}
                payload = await response.json()
                lcp_ms = _extract_metric(payload, "largest-contentful-paint")
                cls = _extract_metric(payload, "cumulative-layout-shift")
                return {
                    "score": _extract_score(payload),
                    "lcp_seconds": round((lcp_ms or 0.0) / 1000.0, 3) if lcp_ms is not None else None,
                    "cls": round(float(cls), 3) if cls is not None else None,
                    "ttfb_seconds": _extract_ttfb(payload),
                }
        except Exception:
            if attempt < max_retries:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            return {}
    return {}


async def fetch_psi_metrics_batch(
    session: aiohttp.ClientSession,
    urls: list[str],
    max_parallel: int = 3,
    max_urls: int | None = None,
) -> dict[str, dict[str, Any]]:
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

    semaphore = asyncio.Semaphore(max_parallel)
    results: dict[str, dict[str, Any]] = {}
    completed = 0
    total = len(unique_urls)
    progress_lock = asyncio.Lock()

    logger.info("PSI batch started: %s URLs (max_parallel=%s).", total, max_parallel)

    async def _worker(target_url: str) -> None:
        nonlocal completed
        async with semaphore:
            mobile = await _fetch_strategy(session, target_url, api_key, "mobile")
            desktop = await _fetch_strategy(session, target_url, api_key, "desktop")
            if not mobile and not desktop:
                logger.warning("PSI unavailable for URL: %s", target_url)
            else:
                results[target_url] = {
                    "URL": target_url,
                    "Desktop Score": desktop.get("score", 0) if desktop else 0,
                    "Mobile Score": mobile.get("score", 0) if mobile else 0,
                    "Mobile LCP": mobile.get("lcp_seconds", 0.0) if mobile else 0.0,
                    "Mobile CLS": mobile.get("cls", 0.0) if mobile else 0.0,
                    "Mobile TTFB": round(float(mobile.get("ttfb_seconds") or 0.0), 3) if mobile else 0.0,
                    "Desktop LCP": desktop.get("lcp_seconds", 0.0) if desktop else 0.0,
                    "Desktop CLS": desktop.get("cls", 0.0) if desktop else 0.0,
                    "Desktop TTFB": round(float(desktop.get("ttfb_seconds") or 0.0), 3) if desktop else 0.0,
                }
            async with progress_lock:
                completed += 1
                logger.info("PSI progress: %s/%s URLs processed.", completed, total)

    await asyncio.gather(*[_worker(url) for url in unique_urls])
    logger.info("PSI batch complete: %s/%s URLs returned metrics.", len(results), total)
    return results
