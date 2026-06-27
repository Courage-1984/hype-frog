from __future__ import annotations

import asyncio
import math
import random
import re
import time
from typing import TYPE_CHECKING, Any, TypedDict
from urllib.parse import urlparse

import aiohttp

from hype_frog.config import PLAYWRIGHT_MAX_SESSIONS
from hype_frog.core import get_logger

if TYPE_CHECKING:  # pragma: no cover - import only for type hints
    from playwright.async_api import Browser, BrowserContext, Page

logger = get_logger(__name__)
_PLAYWRIGHT_SEMAPHORE = asyncio.Semaphore(max(1, int(PLAYWRIGHT_MAX_SESSIONS)))
_SUBPROCESS_PROBE_RESULT: bool | None = None


class HttpFetchResult(TypedDict):
    status_code: int | str | None
    final_url: str | None
    response_headers: dict[str, str]
    redirect_hops: list[str]
    redirect_hop_details: list[dict[str, int | str]]
    html: str | None
    ttfb_ms: float | None
    total_request_ms: float | None
    error_kind: str | None


# ---------------------------------------------------------------------------
# Sprint 2: rendering diagnostics, field-style web vitals, and Poisson jitter.
# All helpers below are pure (no Playwright dependency) so they can be unit
# tested in isolation without spinning up Chromium.
# ---------------------------------------------------------------------------

_TAG_RE: re.Pattern[str] = re.compile(r"<[^>]+>")
_WS_RE: re.Pattern[str] = re.compile(r"\s+")
_SCRIPT_STYLE_RE: re.Pattern[str] = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)

# JS-dependence heuristic thresholds: a page is flagged when the rendered DOM
# either materialises ``>= _JS_DEPENDENT_ABS_DELTA`` extra words versus raw,
# or exceeds raw by ``>= _JS_DEPENDENT_REL_DELTA`` of the raw word count.
_JS_DEPENDENT_ABS_DELTA: int = 100
_JS_DEPENDENT_REL_DELTA: float = 0.5
_JS_DEPENDENT_RAW_EMPTY_FLOOR: int = 50

# Smart-wait knobs: hydration buffer for JS-heavy themes (Elementor, etc.) is
# applied after ``networkidle`` to let post-load mutations settle before we
# read ``document.body.innerText`` and the ``PerformanceObserver``.
_HYDRATION_SETTLE_MS: int = 400
_FIELD_METRICS_OBSERVATION_MS: int = 1200


def _strip_html_to_text(html: str | None) -> str:
    """Return whitespace-collapsed visible text from HTML; safe on ``None``."""
    if not html:
        return ""
    cleaned = _SCRIPT_STYLE_RE.sub(" ", html)
    cleaned = _TAG_RE.sub(" ", cleaned)
    cleaned = _WS_RE.sub(" ", cleaned).strip()
    return cleaned


def _word_count(html: str | None) -> int:
    """Lightweight word counter on stripped HTML; ``None``/empty -> 0."""
    text = _strip_html_to_text(html)
    return len(text.split()) if text else 0


def _compute_is_js_dependent(
    raw_count: int | None,
    rendered_count: int | None,
) -> bool:
    """Return True when the rendered DOM materially exceeds the raw payload."""
    raw = int(raw_count or 0)
    rendered = int(rendered_count or 0)
    if rendered <= 0:
        return False
    if raw <= 0:
        return rendered >= _JS_DEPENDENT_RAW_EMPTY_FLOOR
    delta = rendered - raw
    if delta <= 0:
        return False
    return delta >= _JS_DEPENDENT_ABS_DELTA or (delta / raw) >= _JS_DEPENDENT_REL_DELTA


def _poisson_jitter_seconds(mean_seconds: float) -> float:
    """Sample an exponential (Poisson-arrival) delay; ``<=0`` mean disables it.

    Test-safe by construction: callers passing ``0.0`` (the default in
    :func:`fetch_rendered`) always receive ``0.0`` and never block on
    ``asyncio.sleep``.
    """
    try:
        mean = float(mean_seconds)
    except (TypeError, ValueError):
        return 0.0
    if mean <= 0.0:
        return 0.0
    return random.expovariate(1.0 / mean)


async def _apply_jitter_delay(mean_seconds: float) -> float:
    """Sleep for a Poisson-distributed delay; bypasses entirely when mean<=0."""
    delay = _poisson_jitter_seconds(mean_seconds)
    if delay > 0.0:
        await asyncio.sleep(delay)
    return delay


# Native ``PerformanceObserver`` payload. Wrapped in try/catch so CSP, older
# browsers, or unsupported entry types degrade to ``null`` rather than throw.
_FIELD_METRICS_JS: str = (
    "(observationMs) => new Promise((resolve) => {\n"
    "  const out = { lcp: null, cls: null };\n"
    "  let lcpObs = null;\n"
    "  let clsObs = null;\n"
    "  let lcpValue = 0;\n"
    "  let lcpObserved = false;\n"
    "  let clsValue = 0;\n"
    "  let clsObserved = false;\n"
    "  try {\n"
    "    lcpObs = new PerformanceObserver((list) => {\n"
    "      for (const entry of list.getEntries()) {\n"
    "        if (typeof entry.startTime === 'number' && entry.startTime > lcpValue) {\n"
    "          lcpValue = entry.startTime;\n"
    "          lcpObserved = true;\n"
    "        }\n"
    "      }\n"
    "    });\n"
    "    lcpObs.observe({ type: 'largest-contentful-paint', buffered: true });\n"
    "  } catch (err) { /* CSP / unsupported: leave lcp null */ }\n"
    "  try {\n"
    "    clsObs = new PerformanceObserver((list) => {\n"
    "      for (const entry of list.getEntries()) {\n"
    "        if (entry && !entry.hadRecentInput && typeof entry.value === 'number') {\n"
    "          clsValue += entry.value;\n"
    "          clsObserved = true;\n"
    "        }\n"
    "      }\n"
    "    });\n"
    "    clsObs.observe({ type: 'layout-shift', buffered: true });\n"
    "  } catch (err) { /* CSP / unsupported: leave cls null */ }\n"
    "  setTimeout(() => {\n"
    "    try { if (lcpObs) lcpObs.disconnect(); } catch (e) {}\n"
    "    try { if (clsObs) clsObs.disconnect(); } catch (e) {}\n"
    "    if (lcpObserved) out.lcp = lcpValue;\n"
    "    if (clsObserved) out.cls = clsValue;\n"
    "    resolve(out);\n"
    "  }, observationMs);\n"
    "})"
)


class RenderedFetchDiagnostics(TypedDict):
    """Rich return shape for :func:`fetch_rendered_with_diagnostics`."""

    html: str | None
    raw_html: str | None
    extraction_source: str
    extraction_state: str
    response_headers: dict[str, str]
    field_lcp_ms: float | None
    field_cls: float | None
    raw_word_count: int
    rendered_word_count: int
    is_js_dependent: bool


def _coerce_field_metric(value: Any) -> float | None:
    """Accept JS numbers, reject ``None``/``NaN``/``inf``/non-numeric inputs."""
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, (int, float)):
        return None
    out = float(value)
    if math.isnan(out) or out in (float("inf"), float("-inf")):
        return None
    return out


def _compute_render_diagnostics(
    *,
    raw_html: str | None,
    rendered_html: str | None,
    field_metrics: dict[str, Any] | None,
    extraction_source: str,
    extraction_state: str,
    response_headers: dict[str, str] | None,
) -> RenderedFetchDiagnostics:
    """Pure aggregator: tolerates ``None`` everywhere, never raises.

    Used by :func:`fetch_rendered_with_diagnostics` to assemble the final
    payload from whichever pieces survived the rendering pipeline.
    """
    raw_count = _word_count(raw_html)
    rendered_count = _word_count(rendered_html)
    js_dependent = _compute_is_js_dependent(raw_count, rendered_count)

    metrics_dict = field_metrics if isinstance(field_metrics, dict) else {}
    field_lcp_ms = _coerce_field_metric(metrics_dict.get("lcp"))
    field_cls = _coerce_field_metric(metrics_dict.get("cls"))

    return RenderedFetchDiagnostics(
        html=rendered_html,
        raw_html=raw_html,
        extraction_source=extraction_source,
        extraction_state=extraction_state,
        response_headers=dict(response_headers or {}),
        field_lcp_ms=field_lcp_ms,
        field_cls=field_cls,
        raw_word_count=raw_count,
        rendered_word_count=rendered_count,
        is_js_dependent=js_dependent,
    )


async def _capture_field_metrics(page: Page) -> dict[str, Any] | None:
    """Run the ``PerformanceObserver`` snippet inside the page; ``None`` on failure."""
    try:
        result = await page.evaluate(_FIELD_METRICS_JS, _FIELD_METRICS_OBSERVATION_MS)
    except Exception as exc:  # CSP, navigation churn, evaluator timeouts
        logger.debug("PerformanceObserver evaluate failed: %s", exc)
        return None
    return result if isinstance(result, dict) else None


async def _capture_raw_response_text(nav_response: Any | None) -> str | None:
    """Best-effort raw HTML capture from the Playwright navigation response."""
    if nav_response is None:
        return None
    try:
        body = await nav_response.text()
    except Exception as exc:  # body unavailable for some redirect chains
        logger.debug("nav_response.text() failed: %s", exc)
        return None
    return body if isinstance(body, str) else None


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


async def _probe_subprocess_supported() -> bool:
    """Detect Windows ``ProactorEventLoop`` quirks before spawning Playwright.

    Some Windows event loops (notably the Selector loop pytest may install)
    cannot spawn subprocesses; Playwright launch then deadlocks. We probe
    once per process and fall back to the pure-HTTP path on
    ``NotImplementedError``.
    """
    global _SUBPROCESS_PROBE_RESULT
    if _SUBPROCESS_PROBE_RESULT is not None:
        return _SUBPROCESS_PROBE_RESULT
    try:
        probe = await asyncio.create_subprocess_exec(
            "python",
            "-c",
            "print('ok')",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await probe.communicate()
        _SUBPROCESS_PROBE_RESULT = True
    except NotImplementedError:
        logger.warning(
            "Accurate mode requested but this asyncio event loop cannot spawn subprocesses. "
            "Falling back to HTTP mode."
        )
        _SUBPROCESS_PROBE_RESULT = False
    return _SUBPROCESS_PROBE_RESULT


def _empty_diagnostics(extraction_state: str = "partial") -> RenderedFetchDiagnostics:
    """Fallback payload returned when rendering can't even begin."""
    return RenderedFetchDiagnostics(
        html=None,
        raw_html=None,
        extraction_source="raw_http",
        extraction_state=extraction_state,
        response_headers={},
        field_lcp_ms=None,
        field_cls=None,
        raw_word_count=0,
        rendered_word_count=0,
        is_js_dependent=False,
    )


async def fetch_rendered_with_diagnostics(
    target_url: str,
    render_wait_ms: int,
    selector_wait_ms: int,
    *,
    jitter_mean_seconds: float = 0.0,
    session_manager: PlaywrightSessionManager | None = None,
) -> RenderedFetchDiagnostics:
    """Render ``target_url`` and return a rich raw-vs-rendered diagnostics dict.

    Pipeline: optional Poisson jitter -> per-domain isolated browser context
    -> ``page.goto(wait_until='domcontentloaded')`` -> ``networkidle`` smart
    wait -> hydration settle delay -> selector readiness probe -> rendered
    HTML capture -> ``PerformanceObserver`` LCP/CLS evaluation -> raw HTML
    capture from the navigation response. Every step degrades gracefully:
    a failure at any stage yields the best-available payload rather than
    propagating an exception.

    ``session_manager`` is exposed for dependency-injected tests; production
    callers should leave it ``None`` so a fresh per-call manager is used
    (per-domain isolation within the call still applies).
    """
    if jitter_mean_seconds and jitter_mean_seconds > 0:
        await _apply_jitter_delay(jitter_mean_seconds)

    async with _PLAYWRIGHT_SEMAPHORE:
        if not await _probe_subprocess_supported():
            return _empty_diagnostics("skipped")

        try:
            from playwright.async_api import Error as PlaywrightError
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        except Exception:
            logger.warning(
                "Accurate mode requested but Playwright is unavailable. "
                "Install with: uv add playwright && uv run playwright install chromium"
            )
            return _empty_diagnostics("partial")

        owned_manager = session_manager is None
        manager = session_manager or PlaywrightSessionManager()
        try:
            context = await manager.get_context(target_url)
            if context is None:
                return _empty_diagnostics("skipped")
            try:
                page = await context.new_page()
            except PlaywrightError:
                return _empty_diagnostics("partial")

            extraction_state = "complete"
            rendered_html: str | None = None
            raw_html: str | None = None
            response_headers: dict[str, str] = {}
            field_metrics: dict[str, Any] | None = None
            nav_response: Any | None = None

            try:
                try:
                    nav_response = await page.goto(
                        target_url,
                        wait_until="domcontentloaded",
                        timeout=max(3000, render_wait_ms),
                    )
                except PlaywrightTimeoutError:
                    extraction_state = "partial"
                except PlaywrightError as exc:
                    logger.debug("page.goto failed for %s: %s", target_url, exc)
                    return _empty_diagnostics("partial")

                if nav_response is not None:
                    try:
                        response_headers = dict(nav_response.headers)
                    except Exception:
                        response_headers = {}

                # Smart wait state: networkidle, hydration buffer, then
                # selector readiness checks. Every wait downgrades the
                # state to ``partial`` on timeout instead of aborting.
                try:
                    await page.wait_for_load_state(
                        "networkidle", timeout=max(1000, render_wait_ms)
                    )
                except PlaywrightTimeoutError:
                    extraction_state = "partial"
                except PlaywrightError as exc:
                    logger.debug("networkidle wait raised: %s", exc)
                    extraction_state = "partial"

                try:
                    await page.wait_for_timeout(_HYDRATION_SETTLE_MS)
                except Exception:
                    pass

                for selector in (
                    "title",
                    "meta[name='description']",
                    "link[rel='canonical']",
                    "script[type='application/ld+json']",
                    "h1",
                    "[role='heading'][aria-level='1']",
                    "h1.elementor-heading-title",
                ):
                    try:
                        await page.wait_for_selector(
                            selector, timeout=max(1000, selector_wait_ms)
                        )
                    except PlaywrightTimeoutError:
                        extraction_state = "partial"
                    except PlaywrightError:
                        extraction_state = "partial"

                # Capture rendered DOM first so a later observer failure
                # still leaves us with the post-JS HTML.
                try:
                    rendered_html = await page.content()
                except Exception as exc:
                    logger.debug("page.content() failed: %s", exc)
                    rendered_html = None
                    extraction_state = "partial"

                field_metrics = await _capture_field_metrics(page)
                raw_html = await _capture_raw_response_text(nav_response)
            finally:
                try:
                    await page.close()
                except Exception:
                    pass

            extraction_source = "rendered_browser" if rendered_html else "raw_http"
            return _compute_render_diagnostics(
                raw_html=raw_html,
                rendered_html=rendered_html,
                field_metrics=field_metrics,
                extraction_source=extraction_source,
                extraction_state=extraction_state,
                response_headers=response_headers,
            )
        except Exception as exc:  # final safety net: never propagate
            logger.debug("Unhandled rendering failure for %s: %s", target_url, exc)
            return _empty_diagnostics("partial")
        finally:
            if owned_manager:
                await manager.aclose()


async def fetch_rendered(
    target_url: str,
    render_wait_ms: int,
    selector_wait_ms: int,
    *,
    jitter_mean_seconds: float = 0.0,
    session_manager: PlaywrightSessionManager | None = None,
) -> tuple[str | None, str, str, dict[str, str] | None]:
    """Backward-compatible 4-tuple wrapper around the diagnostics pipeline.

    Returns ``(html, extraction_source, extraction_state, response_headers)``
    so existing callers in :mod:`hype_frog.crawler.fetcher` keep working.
    For the rich raw-vs-rendered diff, field web vitals, and word-count
    payload, call :func:`fetch_rendered_with_diagnostics` directly.
    """
    diagnostics = await fetch_rendered_with_diagnostics(
        target_url,
        render_wait_ms=render_wait_ms,
        selector_wait_ms=selector_wait_ms,
        jitter_mean_seconds=jitter_mean_seconds,
        session_manager=session_manager,
    )
    return (
        diagnostics["html"],
        diagnostics["extraction_source"],
        diagnostics["extraction_state"],
        diagnostics["response_headers"] or None,
    )


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
                headers_received_at = time.time()
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
                hop_details = [
                    {"url": str(hop.url), "status": int(hop.status)}
                    for hop in response.history
                ]
                return {
                    "status_code": status,
                    "final_url": str(response.url),
                    "response_headers": headers,
                    "redirect_hops": [str(h.url) for h in response.history],
                    "redirect_hop_details": hop_details,
                    "html": html,
                    "ttfb_ms": round((headers_received_at - request_start) * 1000, 2),
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
                "redirect_hop_details": [],
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
                "redirect_hop_details": [],
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
                "redirect_hop_details": [],
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
        "redirect_hop_details": [],
        "html": None,
        "ttfb_ms": None,
        "total_request_ms": None,
        "error_kind": "connection_error",
    }
