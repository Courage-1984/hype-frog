from __future__ import annotations

import asyncio
import random
import time
from typing import Any
from urllib.parse import urlparse

import aiohttp

from hype_frog.config import (
    CONNECT_TIMEOUT_SECONDS,
    DELAY_BETWEEN_REQUESTS,
    MAX_RETRIES,
    READ_TIMEOUT_SECONDS,
    REQUEST_JITTER_SECONDS,
    RETRY_BACKOFF_FACTOR,
    RETRY_BASE_DELAY_SECONDS,
    RETRY_MAX_DELAY_SECONDS,
    RETRYABLE_STATUS_CODES,
    TIMEOUT_SECONDS,
)
from hype_frog.core import get_logger
from hype_frog.crawler.data_assembler import (
    assemble_from_html,
    finalize_row_state,
    init_rows,
)
from hype_frog.crawler.network_engine import (
    PlaywrightSessionManager,
    RenderedFetchDiagnostics,
    fetch_http,
    fetch_rendered_with_diagnostics,
)
from hype_frog.core.models import CrawlRowPayload
from hype_frog.pipeline.content_hub_metrics import backfill_extra_content_hub_metrics
from hype_frog.core.text_utils import status_class
from hype_frog.core.url_normalization import normalize_url

logger = get_logger(__name__)


def normalize_url_key(url: object, keep_query: bool = True) -> str:
    return normalize_url(url, keep_query=keep_query)


_AEO_ENGINE_BOTS: tuple[str, ...] = ("gptbot", "perplexitybot", "ccbot")
_LEGACY_AI_BOTS: tuple[str, ...] = ("gptbot", "claudebot", "perplexitybot")
_RENDER_RETRY_RENDER_WAIT_BUMP_MS = 2000
_RENDER_RETRY_SELECTOR_WAIT_BUMP_MS = 1000
_MAX_RENDER_WAIT_MS = 15000
_MAX_SELECTOR_WAIT_MS = 10000


async def _fetch_render_diagnostics(
    render_url: str,
    *,
    render_wait_ms: int,
    selector_wait_ms: int,
    playwright_session_manager: PlaywrightSessionManager | None,
) -> RenderedFetchDiagnostics:
    return await fetch_rendered_with_diagnostics(
        render_url,
        render_wait_ms=render_wait_ms,
        selector_wait_ms=selector_wait_ms,
        session_manager=playwright_session_manager,
    )


async def _fetch_render_with_retries(
    *,
    primary_url: str,
    fallback_url: str | None,
    render_wait_ms: int,
    selector_wait_ms: int,
    playwright_session_manager: PlaywrightSessionManager | None,
) -> RenderedFetchDiagnostics:
    """Attempt rendered capture on the final URL with one extended retry."""
    diagnostics = await _fetch_render_diagnostics(
        primary_url,
        render_wait_ms=render_wait_ms,
        selector_wait_ms=selector_wait_ms,
        playwright_session_manager=playwright_session_manager,
    )
    if diagnostics["html"]:
        return diagnostics

    retry_render_wait = min(render_wait_ms + _RENDER_RETRY_RENDER_WAIT_BUMP_MS, _MAX_RENDER_WAIT_MS)
    retry_selector_wait = min(
        selector_wait_ms + _RENDER_RETRY_SELECTOR_WAIT_BUMP_MS,
        _MAX_SELECTOR_WAIT_MS,
    )
    if retry_render_wait != render_wait_ms or retry_selector_wait != selector_wait_ms:
        diagnostics = await _fetch_render_diagnostics(
            primary_url,
            render_wait_ms=retry_render_wait,
            selector_wait_ms=retry_selector_wait,
            playwright_session_manager=playwright_session_manager,
        )
        if diagnostics["html"]:
            return diagnostics

    if fallback_url and fallback_url != primary_url:
        diagnostics = await _fetch_render_diagnostics(
            fallback_url,
            render_wait_ms=retry_render_wait,
            selector_wait_ms=retry_selector_wait,
            playwright_session_manager=playwright_session_manager,
        )
    return diagnostics


async def _populate_robots_cache(
    *,
    session: aiohttp.ClientSession,
    timeout: aiohttp.ClientTimeout,
    robots_cache: dict[str, Any],
    domain_key: str,
) -> None:
    llms_present = False
    ai_allowed = None
    aeo_engine_bot_coverage: float | None = None
    try:
        async with session.get(f"{domain_key}/llms.txt", timeout=timeout) as llms_resp:
            llms_present = llms_resp.status == 200
    except Exception:
        llms_present = False
    try:
        async with session.get(f"{domain_key}/robots.txt", timeout=timeout) as robots_resp:
            if robots_resp.status == 200:
                robots_text = (await robots_resp.text()).lower()
                ai_allowed = all(bot in robots_text for bot in _LEGACY_AI_BOTS)
                hits = sum(1 for bot in _AEO_ENGINE_BOTS if bot in robots_text)
                aeo_engine_bot_coverage = hits / float(len(_AEO_ENGINE_BOTS))
    except Exception:
        ai_allowed = None
        aeo_engine_bot_coverage = None
    robots_cache[domain_key] = {
        "llms_present": llms_present,
        "ai_allowed": ai_allowed,
        "aeo_engine_bot_coverage": aeo_engine_bot_coverage,
    }


async def fetch_and_parse(
    url: str,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    full_suite: bool = True,
    robots_cache: dict[str, Any] | None = None,
    request_delay: float | None = None,
    sitemap_meta: dict[str, dict[str, Any]] | None = None,
    crawl_mode: str = "fast",
    render_wait_ms: int = 4000,
    selector_wait_ms: int = 3000,
    depth: int = 0,
    render_pages: bool = False,
    playwright_session_manager: PlaywrightSessionManager | None = None,
) -> CrawlRowPayload:
    """Crawl a single URL and return a populated row payload.

    ``depth`` is the BFS hop distance from the seed URL when the caller
    is operating a true spider (``0`` for the seed). The current
    sitemap-driven runner in :mod:`hype_frog.orchestration.crawl_runner`
    does not maintain BFS state, so it leaves the default; the kwarg
    exists here so a future spider entrypoint can plug in without
    further fetcher edits.
    """
    del full_suite
    async with semaphore:
        start_time = time.time()
        main_data, extra = init_rows(url, sitemap_meta)
        main_values = main_data.values
        extra_values = extra.values
        timeout = aiohttp.ClientTimeout(
            total=TIMEOUT_SECONDS,
            connect=CONNECT_TIMEOUT_SECONDS,
            sock_read=READ_TIMEOUT_SECONDS,
        )
        result = await fetch_http(
            session=session,
            url=url,
            timeout=timeout,
            max_retries=MAX_RETRIES,
            retryable_status_codes=RETRYABLE_STATUS_CODES,
            retry_base_delay_seconds=RETRY_BASE_DELAY_SECONDS,
            retry_backoff_factor=RETRY_BACKOFF_FACTOR,
            retry_max_delay_seconds=RETRY_MAX_DELAY_SECONDS,
            request_jitter_seconds=REQUEST_JITTER_SECONDS,
        )
        status_code = result["status_code"]
        final_url = result["final_url"]
        resolved_url = final_url or url
        response_headers = result["response_headers"]
        redirect_targets = result["redirect_hops"]
        html = result["html"]

        main_values["Load Time (s)"] = round(time.time() - start_time, 3)
        main_values["Status Code"] = status_code
        extra_values["Status Code"] = status_code
        if final_url:
            extra_values["Final URL"] = normalize_url_key(final_url)
            extra_values["Protocol"] = urlparse(final_url).scheme
            parsed_final = urlparse(final_url)
            domain_key = f"{parsed_final.scheme}://{parsed_final.netloc}"
        else:
            domain_key = ""
        extra_values["Redirect Chain Length"] = len(redirect_targets)
        extra_values["Status Class"] = status_class(status_code)
        extra_values["TTFB (ms)"] = result["ttfb_ms"]
        extra_values["Total Request Time (ms)"] = result["total_request_ms"]
        extra_values["Content-Type"] = response_headers.get("Content-Type")
        extra_values["Cache-Control"] = response_headers.get("Cache-Control")
        extra_values["ETag"] = response_headers.get("ETag")
        extra_values["X-Robots-Tag"] = response_headers.get("X-Robots-Tag")
        extra_values["Strict-Transport-Security"] = response_headers.get(
            "Strict-Transport-Security"
        )
        extra_values["Content-Security-Policy"] = response_headers.get("Content-Security-Policy")
        extra_values["X-Content-Type-Options"] = response_headers.get("X-Content-Type-Options")
        extra_values["X-Frame-Options"] = response_headers.get("X-Frame-Options")
        extra_values["Referrer-Policy"] = response_headers.get("Referrer-Policy")
        extra_values["Permissions-Policy"] = response_headers.get("Permissions-Policy")
        content_encoding = (response_headers.get("Content-Encoding") or "").lower()
        extra_values["Compression Enabled"] = any(
            token in content_encoding for token in ("gzip", "br", "deflate")
        )
        if redirect_targets:
            final_target = final_url or url
            extra_values["Redirect Hops"] = " -> ".join(redirect_targets + [final_target])
            extra_values["Redirect Target"] = final_target
            first_scheme = urlparse(redirect_targets[0]).scheme.lower()
            final_scheme = urlparse(final_target).scheme.lower()
            extra_values["HTTP->HTTPS Redirect"] = (
                first_scheme == "http" and final_scheme == "https"
            )

        if robots_cache is not None and domain_key:
            if domain_key not in robots_cache:
                await _populate_robots_cache(
                    session=session,
                    timeout=timeout,
                    robots_cache=robots_cache,
                    domain_key=domain_key,
                )
            extra_values["llms.txt Present"] = robots_cache.get(domain_key, {}).get(
                "llms_present"
            )
            extra_values["AI Crawlers Allowed (GPTBot/ClaudeBot/PerplexityBot)"] = (
                robots_cache.get(domain_key, {}).get("ai_allowed")
            )
            extra_values["AEO Robots AI Bot Coverage"] = robots_cache.get(
                domain_key, {}
            ).get("aeo_engine_bot_coverage")

        ct_lower = (response_headers.get("Content-Type") or "").lower()
        unsupported_mime = (
            isinstance(status_code, int)
            and status_code == 200
            and html is None
            and "text/html" not in ct_lower
        )
        if unsupported_mime:
            main_values["Extraction Source"] = "raw_http"
            extra_values["Extraction Source"] = "raw_http"
            main_values["Extraction State"] = "skipped"
            extra_values["Extraction State"] = "skipped"
            extra_values["skip_reason"] = "unsupported_mime"
        elif isinstance(status_code, int) and status_code == 200 and html is not None:
            extraction_source = "raw_http"
            extraction_state_hint = "complete"
            rendered_headers: dict[str, str] = {}
            if render_pages or crawl_mode == "accurate":
                # Render the post-redirect final URL so extraction aligns with the
                # HTTP payload we already fetched. A shared Playwright session per
                # crawl (when provided) keeps browser startup consistent across URLs.
                render_target = resolved_url or url
                diagnostics = await _fetch_render_with_retries(
                    primary_url=render_target,
                    fallback_url=url if render_target != url else None,
                    render_wait_ms=render_wait_ms,
                    selector_wait_ms=selector_wait_ms,
                    playwright_session_manager=playwright_session_manager,
                )
                rendered_html = diagnostics["html"]
                if rendered_html:
                    html = rendered_html
                    extraction_source = diagnostics["extraction_source"]
                    extraction_state_hint = diagnostics["extraction_state"]
                    rendered_headers = {
                        str(k).lower(): str(v)
                        for k, v in (diagnostics["response_headers"] or {}).items()
                    }
                else:
                    extraction_state_hint = diagnostics["extraction_state"]
                    extra_values["Extraction Source Fallback"] = True
                    logger.info(
                        "Render unavailable for %s; using raw_http HTML for extraction.",
                        render_target,
                    )
                # Always surface the Sprint 2 ghost data — even when
                # ``rendered_html`` was empty the raw_word_count /
                # is_js_dependent values are still meaningful (and the
                # SQLite cache stores raw JSON, so these new keys
                # round-trip without a Pydantic schema bump).
                extra_values["JS Dependent"] = bool(diagnostics["is_js_dependent"])
                extra_values["Raw Words"] = int(diagnostics["raw_word_count"] or 0)
                extra_values["Rendered Words"] = int(
                    diagnostics["rendered_word_count"] or 0
                )
                extra_values["Field LCP (ms)"] = diagnostics["field_lcp_ms"]
                extra_values["Field CLS"] = diagnostics["field_cls"]
            main_values["Extraction Source"] = extraction_source
            extra_values["Extraction Source"] = extraction_source
            if extraction_source == "rendered_browser":
                extra_values["Extraction Source Fallback"] = False
            if rendered_headers:
                extra_values["Cache-Control"] = rendered_headers.get(
                    "cache-control", extra_values["Cache-Control"]
                )
                extra_values["ETag"] = rendered_headers.get("etag", extra_values["ETag"])
                extra_values["X-Robots-Tag"] = rendered_headers.get(
                    "x-robots-tag", extra_values["X-Robots-Tag"]
                )
                extra_values["Strict-Transport-Security"] = rendered_headers.get(
                    "strict-transport-security", extra_values["Strict-Transport-Security"]
                )
                extra_values["Content-Security-Policy"] = rendered_headers.get(
                    "content-security-policy", extra_values["Content-Security-Policy"]
                )
                extra_values["X-Content-Type-Options"] = rendered_headers.get(
                    "x-content-type-options", extra_values["X-Content-Type-Options"]
                )
                extra_values["X-Frame-Options"] = rendered_headers.get(
                    "x-frame-options", extra_values["X-Frame-Options"]
                )
                extra_values["Referrer-Policy"] = rendered_headers.get(
                    "referrer-policy", extra_values["Referrer-Policy"]
                )
                extra_values["Permissions-Policy"] = rendered_headers.get(
                    "permissions-policy", extra_values["Permissions-Policy"]
                )
                rendered_encoding = (
                    rendered_headers.get("content-encoding") or ""
                ).lower()
                if rendered_encoding:
                    extra_values["Compression Enabled"] = any(
                        token in rendered_encoding for token in ("gzip", "br", "deflate")
                    )
            assemble_from_html(
                main_data=main_data,
                extra=extra,
                html=html,
                resolved_url=resolved_url,
                depth=depth,
            )
            main_values["Extraction State"] = extraction_state_hint
        else:
            main_values["Extraction State"] = "skipped"

        if main_values["Load Time (s)"] is None:
            main_values["Load Time (s)"] = round(time.time() - start_time, 3)
        finalize_row_state(main_data, extra)
        backfill_extra_content_hub_metrics(extra_values, main_values)
        logger.info("[%s] Crawled: %s", main_values["Status Code"], url)
        delay_seconds = (
            request_delay if request_delay is not None else DELAY_BETWEEN_REQUESTS
        )
        await asyncio.sleep(delay_seconds + random.uniform(0, REQUEST_JITTER_SECONDS))
        return CrawlRowPayload(main=main_data, extra=extra)
