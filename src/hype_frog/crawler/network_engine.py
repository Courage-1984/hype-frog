from __future__ import annotations

import asyncio
import random
import time
from typing import TypedDict

import aiohttp

from hype_frog.config import PLAYWRIGHT_MAX_SESSIONS
from hype_frog.core import get_logger

logger = get_logger(__name__)
_PLAYWRIGHT_SEMAPHORE = asyncio.Semaphore(max(1, int(PLAYWRIGHT_MAX_SESSIONS)))


class HttpFetchResult(TypedDict):
    status_code: int | str | None
    final_url: str | None
    response_headers: dict[str, str]
    redirect_hops: list[str]
    html: str | None
    ttfb_ms: float | None
    total_request_ms: float | None
    error_kind: str | None


async def fetch_rendered(
    target_url: str,
    render_wait_ms: int,
    selector_wait_ms: int,
) -> tuple[str | None, str, str, dict[str, str] | None]:
    async with _PLAYWRIGHT_SEMAPHORE:
        try:
            probe = await asyncio.create_subprocess_exec(
                "python",
                "-c",
                "print('ok')",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await probe.communicate()
        except NotImplementedError:
            logger.warning(
                "Accurate mode requested but this asyncio event loop cannot spawn subprocesses. "
                "Falling back to HTTP mode."
            )
            return None, "raw_http", "partial", None

        try:
            from playwright.async_api import Error as PlaywrightError
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            from playwright.async_api import async_playwright
        except Exception:
            logger.warning(
                "Accurate mode requested but Playwright is unavailable. "
                "Install with: uv add playwright && uv run playwright install chromium"
            )
            return None, "raw_http", "partial", None

        browser = None
        try:
            async with async_playwright() as p:
                try:
                    browser = await p.chromium.launch(headless=True)
                except Exception:
                    logger.warning(
                        "Chromium browser binaries are missing. Run: uv run playwright install chromium"
                    )
                    return None, "raw_http", "partial", None
                context = await browser.new_context()
                page = await context.new_page()
                try:
                    nav_response = await page.goto(
                        target_url,
                        wait_until="domcontentloaded",
                        timeout=max(3000, render_wait_ms),
                    )
                    try:
                        await page.wait_for_load_state(
                            "networkidle", timeout=max(1000, render_wait_ms)
                        )
                    except PlaywrightTimeoutError:
                        pass
                    extraction_state = "complete"
                    selectors = [
                        "title",
                        "meta[name='description']",
                        "link[rel='canonical']",
                        "script[type='application/ld+json']",
                    ]
                    for selector in selectors:
                        try:
                            await page.wait_for_selector(
                                selector, timeout=max(1000, selector_wait_ms)
                            )
                        except PlaywrightTimeoutError:
                            extraction_state = "partial"
                    html = await page.content()
                    response_headers = dict(nav_response.headers) if nav_response else {}
                    await context.close()
                    return html, "rendered_browser", extraction_state, response_headers
                except PlaywrightTimeoutError:
                    html = await page.content()
                    response_headers = (
                        dict(nav_response.headers)
                        if "nav_response" in locals() and nav_response
                        else {}
                    )
                    await context.close()
                    return html, "rendered_browser", "partial", response_headers
                except PlaywrightError:
                    await context.close()
                    return None, "raw_http", "partial", None
        except Exception:
            return None, "raw_http", "partial", None
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass


async def fetch_http(
    *,
    session: aiohttp.ClientSession,
    url: str,
    timeout: aiohttp.ClientTimeout,
    max_retries: int,
    retryable_status_codes: set[int] | frozenset[int],
    retry_base_delay_seconds: float,
    retry_backoff_factor: float,
    retry_max_delay_seconds: float,
    request_jitter_seconds: float,
) -> HttpFetchResult:
    for attempt in range(max_retries + 1):
        request_start = time.time()
        try:
            async with session.get(url, timeout=timeout) as response:
                headers = {str(k): str(v) for k, v in response.headers.items()}
                status = int(response.status)
                if status in retryable_status_codes and attempt < max_retries:
                    wait_time = min(
                        retry_max_delay_seconds,
                        retry_base_delay_seconds * (retry_backoff_factor**attempt),
                    ) + random.uniform(0, request_jitter_seconds)
                    logger.warning(
                        "[%s] Retrying %s (attempt %s/%s) in %.1fs",
                        status,
                        url,
                        attempt + 2,
                        max_retries + 1,
                        wait_time,
                    )
                    await asyncio.sleep(wait_time)
                    continue
                html: str | None = None
                content_type = (response.headers.get("Content-Type", "") or "").lower()
                if status == 200 and "text/html" in content_type:
                    html = await response.text()
                return {
                    "status_code": status,
                    "final_url": str(response.url),
                    "response_headers": headers,
                    "redirect_hops": [str(h.url) for h in response.history],
                    "html": html,
                    "ttfb_ms": round((time.time() - request_start) * 1000, 2),
                    "total_request_ms": round((time.time() - request_start) * 1000, 2),
                    "error_kind": None,
                }
        except asyncio.TimeoutError:
            if attempt < max_retries:
                wait_time = min(
                    retry_max_delay_seconds,
                    retry_base_delay_seconds * (retry_backoff_factor**attempt),
                ) + random.uniform(0, request_jitter_seconds)
                logger.warning(
                    "[Timeout] Retrying %s (attempt %s/%s) in %.1fs",
                    url,
                    attempt + 2,
                    max_retries + 1,
                    wait_time,
                )
                await asyncio.sleep(wait_time)
                continue
            return {
                "status_code": "Timeout",
                "final_url": None,
                "response_headers": {},
                "redirect_hops": [],
                "html": None,
                "ttfb_ms": None,
                "total_request_ms": None,
                "error_kind": "timeout",
            }
        except aiohttp.ClientError:
            if attempt < max_retries:
                wait_time = min(
                    retry_max_delay_seconds,
                    retry_base_delay_seconds * (retry_backoff_factor**attempt),
                ) + random.uniform(0, request_jitter_seconds)
                logger.warning(
                    "[Connection Error] Retrying %s (attempt %s/%s) in %.1fs",
                    url,
                    attempt + 2,
                    max_retries + 1,
                    wait_time,
                )
                await asyncio.sleep(wait_time)
                continue
            return {
                "status_code": "Connection Error",
                "final_url": None,
                "response_headers": {},
                "redirect_hops": [],
                "html": None,
                "ttfb_ms": None,
                "total_request_ms": None,
                "error_kind": "connection_error",
            }
        except Exception as error:
            return {
                "status_code": f"Error: {error}",
                "final_url": None,
                "response_headers": {},
                "redirect_hops": [],
                "html": None,
                "ttfb_ms": None,
                "total_request_ms": None,
                "error_kind": "unexpected_error",
            }

    return {
        "status_code": "Connection Error",
        "final_url": None,
        "response_headers": {},
        "redirect_hops": [],
        "html": None,
        "ttfb_ms": None,
        "total_request_ms": None,
        "error_kind": "connection_error",
    }
