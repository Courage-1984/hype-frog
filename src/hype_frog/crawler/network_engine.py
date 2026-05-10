from __future__ import annotations

import asyncio
import random
import time
from typing import TYPE_CHECKING, Any, TypedDict
from urllib.parse import urlparse

import aiohttp

from hype_frog.config import PLAYWRIGHT_MAX_SESSIONS
from hype_frog.core import get_logger

if TYPE_CHECKING:  # pragma: no cover - import only for type hints
    from playwright.async_api import Browser, BrowserContext

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


def _domain_key(url: str) -> str:
    """Return a normalised ``host[:port]`` key for context isolation.

    Empty/relative URLs collapse to ``"_default"`` so that calls without a
    parsable origin still receive an isolated context (rather than colliding
    with everything else).
    """
    try:
        parsed = urlparse(str(url or "").strip())
    except (ValueError, AttributeError):
        return "_default"
    netloc = (parsed.netloc or "").lower()
    return netloc or "_default"


class PlaywrightSessionManager:
    """Per-instance manager that maps base domains to isolated browser contexts.

    Encapsulates the ``BrowserContext`` lifecycle so cookies, local storage,
    and HTTP cache stay strictly siloed across domains during a single
    rendered-fetch session. Use as an ``async with`` context manager:

    .. code-block:: python

        async with PlaywrightSessionManager() as manager:
            context = await manager.get_context("https://example.com/")

    Concurrency: an internal :class:`asyncio.Lock` serialises lazy launch and
    per-domain context creation so sibling crawl tasks cannot race on the
    same ``Browser`` instance.
    """

    def __init__(
        self,
        *,
        browser_factory: Any | None = None,
        headless: bool = True,
        context_kwargs: dict[str, Any] | None = None,
    ) -> None:
        self._browser_factory = browser_factory
        self._headless = headless
        self._context_kwargs: dict[str, Any] = dict(context_kwargs or {})
        self._playwright_cm: Any | None = None
        self._playwright: Any | None = None
        self._browser: Browser | None = None
        self._contexts: dict[str, BrowserContext] = {}
        self._lock = asyncio.Lock()
        self._closed = False

    async def __aenter__(self) -> PlaywrightSessionManager:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.aclose()

    async def _ensure_browser(self) -> Browser | None:
        if self._browser is not None:
            return self._browser
        if self._closed:
            return None

        if self._browser_factory is None:
            try:
                from playwright.async_api import async_playwright
            except Exception:
                logger.warning(
                    "Accurate mode requested but Playwright is unavailable. "
                    "Install with: uv add playwright && uv run playwright install chromium"
                )
                return None
            self._playwright_cm = async_playwright()
            self._playwright = await self._playwright_cm.__aenter__()
            chromium = self._playwright.chromium
        else:
            chromium = self._browser_factory

        try:
            self._browser = await chromium.launch(headless=self._headless)
        except Exception:
            logger.warning(
                "Chromium browser binaries are missing. Run: uv run playwright install chromium"
            )
            await self._teardown_playwright()
            return None
        return self._browser

    async def get_context(self, url: str) -> BrowserContext | None:
        """Return the cached context for ``url``'s base domain (lazy-create)."""
        if self._closed:
            raise RuntimeError("PlaywrightSessionManager is closed")
        domain = _domain_key(url)
        async with self._lock:
            cached = self._contexts.get(domain)
            if cached is not None:
                return cached
            browser = await self._ensure_browser()
            if browser is None:
                return None
            context = await browser.new_context(**self._context_kwargs)
            self._contexts[domain] = context
            logger.debug("Playwright context created for domain=%s", domain)
            return context

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        for domain, context in list(self._contexts.items()):
            try:
                await context.close()
            except Exception as exc:
                logger.debug("Failed to close context %s: %s", domain, exc)
        self._contexts.clear()
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception as exc:
                logger.debug("Failed to close browser: %s", exc)
            self._browser = None
        await self._teardown_playwright()

    async def _teardown_playwright(self) -> None:
        if self._playwright_cm is None:
            self._playwright = None
            return
        try:
            await self._playwright_cm.__aexit__(None, None, None)
        except Exception as exc:
            logger.debug("Failed to close playwright runtime: %s", exc)
        finally:
            self._playwright_cm = None
            self._playwright = None


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
        except Exception:
            logger.warning(
                "Accurate mode requested but Playwright is unavailable. "
                "Install with: uv add playwright && uv run playwright install chromium"
            )
            return None, "raw_http", "partial", None

        async with PlaywrightSessionManager() as manager:
            context = await manager.get_context(target_url)
            if context is None:
                return None, "raw_http", "partial", None
            try:
                page = await context.new_page()
            except PlaywrightError:
                return None, "raw_http", "partial", None

            try:
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
                    return html, "rendered_browser", extraction_state, response_headers
                except PlaywrightTimeoutError:
                    html = await page.content()
                    response_headers = (
                        dict(nav_response.headers)
                        if "nav_response" in locals() and nav_response
                        else {}
                    )
                    return html, "rendered_browser", "partial", response_headers
                except PlaywrightError:
                    return None, "raw_http", "partial", None
            except Exception:
                return None, "raw_http", "partial", None
            finally:
                try:
                    await page.close()
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
