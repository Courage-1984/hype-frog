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
from hype_frog.crawler.network_engine import fetch_http, fetch_rendered
from hype_frog.models import CrawlRowPayload
from hype_frog.utils import normalize_url_key, status_class

logger = get_logger(__name__)


async def _populate_robots_cache(
    *,
    session: aiohttp.ClientSession,
    timeout: aiohttp.ClientTimeout,
    robots_cache: dict[str, Any],
    domain_key: str,
) -> None:
    llms_present = False
    ai_allowed = None
    try:
        async with session.get(f"{domain_key}/llms.txt", timeout=timeout) as llms_resp:
            llms_present = llms_resp.status == 200
    except Exception:
        llms_present = False
    try:
        async with session.get(f"{domain_key}/robots.txt", timeout=timeout) as robots_resp:
            if robots_resp.status == 200:
                robots_text = (await robots_resp.text()).lower()
                ai_allowed = all(
                    bot.lower() in robots_text
                    for bot in ["gptbot", "claudebot", "perplexitybot"]
                )
    except Exception:
        ai_allowed = None
    robots_cache[domain_key] = {"llms_present": llms_present, "ai_allowed": ai_allowed}


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
) -> CrawlRowPayload:
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

        if isinstance(status_code, int) and status_code == 200 and html is not None:
            extraction_source = "raw_http"
            extraction_state_hint = "complete"
            rendered_headers: dict[str, str] = {}
            if crawl_mode == "accurate":
                rendered_html, rendered_source, rendered_state, rendered_headers_raw = (
                    await fetch_rendered(
                        url,
                        render_wait_ms=render_wait_ms,
                        selector_wait_ms=selector_wait_ms,
                    )
                )
                if rendered_html:
                    html = rendered_html
                    extraction_source = rendered_source
                    extraction_state_hint = rendered_state
                    rendered_headers = {
                        str(k).lower(): str(v)
                        for k, v in (rendered_headers_raw or {}).items()
                    }
                else:
                    extraction_state_hint = "partial"
            main_values["Extraction Source"] = extraction_source
            extra_values["Extraction Source"] = extraction_source
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
            )
            main_values["Extraction State"] = extraction_state_hint
        else:
            main_values["Extraction State"] = "skipped"

        if main_values["Load Time (s)"] is None:
            main_values["Load Time (s)"] = round(time.time() - start_time, 3)
        finalize_row_state(main_data, extra)
        logger.info("[%s] Crawled: %s", main_values["Status Code"], url)
        delay_seconds = (
            request_delay if request_delay is not None else DELAY_BETWEEN_REQUESTS
        )
        await asyncio.sleep(delay_seconds + random.uniform(0, REQUEST_JITTER_SECONDS))
        return CrawlRowPayload(main=main_data, extra=extra)
