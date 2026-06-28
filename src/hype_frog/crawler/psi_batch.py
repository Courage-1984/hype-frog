"""PSI HTTP batch fetch, pacing, retries, and API-key probe."""

from __future__ import annotations

import asyncio
import json
import random
import re
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import aiohttp

from hype_frog.config import (
    get_psi_base_delay_seconds,
    get_psi_jitter_fraction,
    get_psi_strategy_gap_seconds,
)
from hype_frog.core import get_logger
from hype_frog.core.env_vars import get_psi_api_key
from hype_frog.crawler.psi_cache import CACHE_TTL_SECONDS, cache_get, cache_put, open_cache_db
from hype_frog.crawler.psi_merge import (
    lab_strategy_metrics,
    merge_url_results,
    psi_index_key,
    store_psi_result,
    strategy_ok,
)

logger = get_logger(__name__)

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
_PSI_CATEGORIES: tuple[str, ...] = (
    "performance",
    "accessibility",
    "best-practices",
    "seo",
)


def jittered_seconds(base_seconds: float, jitter_fraction: float) -> float:
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
    await asyncio.sleep(jittered_seconds(base, fraction))


class PsiRequestPacer:
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
                target = jittered_seconds(self._base_seconds, self._jitter_fraction)
                remaining = target - elapsed
                if remaining > 0:
                    await asyncio.sleep(remaining)
            self._last_request_at = time.monotonic()


@dataclass
class _BatchAbortState:
    api_key_rejected: bool = False
    reject_reason: str | None = None


def extract_api_error_message(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    error_block = payload.get("error")
    if not isinstance(error_block, dict):
        return None
    message = str(error_block.get("message") or "").strip()
    return message or None


def is_api_key_error(http_status: int, message: str | None) -> bool:
    if http_status == 403:
        return True
    if http_status == 400 and message and _API_KEY_ERROR_RE.search(message):
        return True
    return False


def is_retryable_psi_error(http_status: int, message: str | None) -> bool:
    if http_status in _RETRY_STATUSES:
        return True
    if http_status == 400 and message and _RETRYABLE_ERROR_RE.search(message):
        return True
    return False
def build_endpoint(url: str, strategy: str, api_key: str) -> str:
    category_params = "".join(f"&category={quote(cat, safe='')}" for cat in _PSI_CATEGORIES)
    q = (
        f"url={quote(url, safe='')}"
        f"&strategy={quote(strategy, safe='')}"
        f"{category_params}"
        f"&key={quote(api_key, safe='')}"
    )
    return f"{_PSI_BASE}?{q}"


async def fetch_strategy_raw(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    conn: sqlite3.Connection,
    cache_lock: threading.Lock,
    url: str,
    api_key: str,
    strategy: str,
    abort_state: _BatchAbortState,
    *,
    pacer: PsiRequestPacer | None = None,
) -> tuple[dict[str, Any], str | None]:
    if abort_state.api_key_rejected:
        return {}, abort_state.reject_reason or "PSI API key rejected"

    with cache_lock:
        cached = cache_get(conn, url, strategy)
    if cached is not None:
        return cached, None

    endpoint = build_endpoint(url, strategy, api_key)
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
                        and is_retryable_psi_error(response.status, extract_api_error_message(body))
                    ):
                        last_error = extract_api_error_message(body) or f"HTTP {response.status}"
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
                        last_error = extract_api_error_message(body) or f"HTTP {response.status}"
                        if is_api_key_error(response.status, last_error):
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
            cache_put(conn, url, strategy, payload)
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

@dataclass
class PsiBatchSummary:
    total: int = 0
    complete: int = 0
    partial: int = 0
    lab_only: int = 0
    unavailable: int = 0


def classify_psi_status(status: str) -> str:
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

    conn = open_cache_db()
    cache_lock = threading.Lock()
    pacer = PsiRequestPacer(get_psi_base_delay_seconds(), get_psi_jitter_fraction())
    try:
        logger.info(
            "PSI batch started: %s URLs (concurrent_requests=%s, cache_ttl=%sh).",
            summary.total,
            max_parallel,
            CACHE_TTL_SECONDS // 3600,
        )

        async def _worker(target_url: str) -> None:
            nonlocal completed
            if abort_state.api_key_rejected:
                unavailable = merge_url_results(
                    target_url,
                    {},
                    {},
                    mobile_error=abort_state.reject_reason,
                    desktop_error=abort_state.reject_reason,
                )
                store_psi_result(results, target_url, unavailable)
                summary.unavailable += 1
            else:
                mobile_raw, mobile_error = await fetch_strategy_raw(
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
                desktop_raw, desktop_error = await fetch_strategy_raw(
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
                mobile_ok = strategy_ok(mobile_raw)
                desktop_ok = strategy_ok(desktop_raw)
                if not mobile_ok and not desktop_ok:
                    logger.warning(
                        "PSI unavailable for URL %s (mobile: %s; desktop: %s).",
                        target_url,
                        mobile_error or "no data",
                        desktop_error or "no data",
                    )
                    merged = merge_url_results(
                        target_url,
                        mobile_raw,
                        desktop_raw,
                        mobile_error=mobile_error,
                        desktop_error=desktop_error,
                    )
                    store_psi_result(results, target_url, merged)
                    summary.unavailable += 1
                else:
                    merged = merge_url_results(
                        target_url,
                        mobile_raw,
                        desktop_raw,
                        mobile_error=mobile_error if not mobile_ok else None,
                        desktop_error=desktop_error if not desktop_ok else None,
                    )
                    store_psi_result(results, target_url, merged)
                    bucket = classify_psi_status(str(merged.get("PSI Data Status") or ""))
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


def format_probe_transport_error(exc: BaseException, *, timeout_seconds: float) -> str:
    """Human-readable transport error (``TimeoutError`` often has an empty ``str()``)."""
    name = type(exc).__name__
    detail = str(exc).strip()
    if detail:
        return f"{name}: {detail}"
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return f"{name} (no response within {timeout_seconds:.0f}s)"
    return name


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

    endpoint = build_endpoint(test_url, "mobile", api_key)
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
                    lab = lab_strategy_metrics(payload)
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

                error_message = extract_api_error_message(payload)
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
    except (aiohttp.ClientError, asyncio.TimeoutError, TimeoutError) as exc:
        transport = format_probe_transport_error(exc, timeout_seconds=timeout_seconds)
        return False, f"PSI request failed: {transport}", details
