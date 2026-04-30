from __future__ import annotations

import asyncio
import os
from typing import Any
from urllib.parse import quote

import aiohttp


def get_psi_api_key() -> str | None:
    return os.getenv("PSI_API_KEY") or None


def _extract_metric_block(payload: dict[str, Any], key: str) -> float | None:
    try:
        return float(payload["loadingExperience"]["metrics"][key]["percentile"]) / 1000.0
    except Exception:
        return None


def _extract_lab_metric(payload: dict[str, Any], key: str, unit_divisor: float = 1000.0) -> float | None:
    try:
        return float(payload["lighthouseResult"]["audits"][key]["numericValue"]) / unit_divisor
    except Exception:
        return None


async def fetch_psi_for_url(
    session: aiohttp.ClientSession,
    url: str,
    api_key: str,
    max_retries: int = 3,
) -> dict[str, Any]:
    endpoint = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={quote(url, safe='')}&strategy=mobile&key={api_key}"
    backoff = 1.0
    for attempt in range(max_retries + 1):
        try:
            async with session.get(endpoint, timeout=aiohttp.ClientTimeout(total=25)) as resp:
                if resp.status == 429 and attempt < max_retries:
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue
                if resp.status >= 400:
                    return {"URL": url, "CWV Data Source": "Lab", "Field vs Lab": "Lab"}
                data = await resp.json()
                field_lcp = _extract_metric_block(data, "LARGEST_CONTENTFUL_PAINT_MS")
                field_inp = _extract_metric_block(data, "INTERACTION_TO_NEXT_PAINT")
                field_cls = _extract_metric_block(data, "CUMULATIVE_LAYOUT_SHIFT_SCORE")
                lab_lcp = _extract_lab_metric(data, "largest-contentful-paint", 1000.0)
                lab_inp = _extract_lab_metric(data, "interaction-to-next-paint", 1.0)
                lab_cls = _extract_lab_metric(data, "cumulative-layout-shift", 1.0)
                use_field = any(v is not None for v in [field_lcp, field_inp, field_cls])
                return {
                    "URL": url,
                    "CWV LCP (s)": field_lcp if field_lcp is not None else lab_lcp,
                    "CWV INP (ms)": field_inp if field_inp is not None else lab_inp,
                    "CWV CLS": field_cls if field_cls is not None else lab_cls,
                    "CWV Data Source": "Field" if use_field else "Lab",
                    "Field vs Lab": "Field" if use_field else "Lab",
                }
        except Exception:
            if attempt < max_retries:
                await asyncio.sleep(backoff)
                backoff *= 2
                continue
            return {"URL": url, "CWV Data Source": "Lab", "Field vs Lab": "Lab"}
    return {"URL": url, "CWV Data Source": "Lab", "Field vs Lab": "Lab"}


async def fetch_psi_metrics_batch(
    session: aiohttp.ClientSession,
    urls: list[str],
    max_parallel: int = 4,
) -> dict[str, dict[str, Any]]:
    api_key = get_psi_api_key()
    if not api_key:
        return {}
    semaphore = asyncio.Semaphore(max_parallel)

    async def _worker(target: str) -> dict[str, Any]:
        async with semaphore:
            return await fetch_psi_for_url(session, target, api_key)

    results = await asyncio.gather(*[_worker(u) for u in urls])
    return {str(item.get("URL")): item for item in results if item.get("URL")}

