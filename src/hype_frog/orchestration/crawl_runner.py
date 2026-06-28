"""Async crawl execution orchestration."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from hype_frog.checkpoint import AuditCache
from hype_frog.core import get_logger
from hype_frog.core.console import log_phase_banner, log_startup_panel
from hype_frog.core.url_normalization import normalize_url_key
from hype_frog.core.env_vars import get_hf_max_depth, get_hf_output_filename
from hype_frog.core.file_utils import build_output_filename
from hype_frog.crawler import create_session, fetch_and_parse, parse_sitemap
from hype_frog.crawler.network_engine import PlaywrightSessionManager
from hype_frog.extractors.semantic_engine import IntentAnalyzer
from hype_frog.orchestration.crawl_runner_bfs import CrawlExecutionResult, run_bfs_crawl_loop
from hype_frog.orchestration.crawl_runner_frontier import (
    ExcludedCmsActionUrl,
    cms_action_exclusion_keys,
    is_crawlable_html_candidate,
    register_cms_exclusion,
)
from hype_frog.orchestration.crawl_runner_interactive import resolve_crawl_runtime_options
from hype_frog.orchestration.run_setup import RunSetup

logger = get_logger(__name__)

# Re-export collaborators so tests can patch ``hype_frog.orchestration.crawl_runner.*``.
__all__ = [
    "AuditCache",
    "CrawlExecutionResult",
    "ExcludedCmsActionUrl",
    "IntentAnalyzer",
    "build_output_filename",
    "cms_action_exclusion_keys",
    "create_session",
    "execute_crawl",
    "fetch_and_parse",
    "parse_sitemap",
    "PlaywrightSessionManager",
]

# Private aliases preserved for unit tests and internal callers.
_is_crawlable_html_candidate = is_crawlable_html_candidate
_normalize_url_key = normalize_url_key
_register_cms_exclusion = register_cms_exclusion


def _candidate_internal_links(
    row: Any,
    cms_exclusions: dict[str, ExcludedCmsActionUrl] | None = None,
) -> list[str]:
    from hype_frog.orchestration.crawl_runner_frontier import candidate_internal_links

    return candidate_internal_links(row, cms_exclusions)


def _max_depth_from_env(default: int = 3) -> int:
    depth = get_hf_max_depth()
    if depth is None:
        return default
    return max(0, depth)


async def execute_crawl(setup: RunSetup) -> CrawlExecutionResult:
    urls: list[str] = []
    sitemap_meta: dict[str, dict[str, str | None]] = {}
    sitemap_files_meta: dict[str, dict[str, Any]] = {}
    source_label = "manual_input"

    async with create_session() as session:
        if setup.target_input.lower().endswith(".xml"):
            log_phase_banner("SETUP: Parsing provided sitemap seed list")
            urls, sitemap_meta, sitemap_files_meta = await parse_sitemap(
                setup.target_input, session
            )
            parsed_source = urlparse(setup.target_input)
            source_label = parsed_source.netloc or "sitemap"
        else:
            log_phase_banner("SETUP: Single URL seed mode")
            parsed_target = urlparse(setup.target_input)
            if parsed_target.scheme and parsed_target.netloc:
                urls = [setup.target_input]
                source_label = parsed_target.netloc
            else:
                raise ValueError(
                    "Invalid target input. Provide a full URL or a sitemap XML URL."
                )

        if not urls:
            raise ValueError("No URLs to crawl. Exiting.")

        cms_exclusions: dict[str, ExcludedCmsActionUrl] = {}
        original_count = len(urls)
        for url in urls:
            register_cms_exclusion(cms_exclusions, str(url), "Sitemap")
        urls = list(
            dict.fromkeys(
                normalize_url_key(url)
                for url in urls
                if url and is_crawlable_html_candidate(str(url))
            )
        )
        if cms_exclusions:
            logger.info(
                "Withheld %s CMS action URL(s) from crawl queue (see CMS Action URLs tab).",
                len(cms_exclusions),
            )
        if sitemap_meta:
            sitemap_meta = {
                normalize_url_key(url): meta
                for url, meta in sitemap_meta.items()
                if is_crawlable_html_candidate(str(url))
            }
        if len(urls) != original_count:
            logger.debug("Removed %s duplicate URLs.", original_count - len(urls))
        if setup.max_urls is not None and len(urls) > setup.max_urls:
            urls = urls[: setup.max_urls]
            logger.info(
                "Applied initial seed cap: limiting run to first %s URLs.",
                len(urls),
            )

        max_depth = (
            setup.bfs_max_depth
            if setup.bfs_max_depth is not None
            else _max_depth_from_env(default=3)
        )

        runtime = await resolve_crawl_runtime_options(setup)
        output_filename = (
            setup.output_filename
            or get_hf_output_filename()
            or build_output_filename(source_label, runtime.full_suite)
        )

        log_startup_panel(
            target_input=setup.target_input,
            url_count=len(urls),
            workers=runtime.workers,
            request_delay=runtime.request_delay,
            mode="Full AEO/SEO Suite" if runtime.full_suite else "Main Inventory Only",
            crawl_mode=setup.crawl_mode,
            output_filename=output_filename,
        )

        return await run_bfs_crawl_loop(
            setup=setup,
            session=session,
            urls=urls,
            sitemap_meta=sitemap_meta,
            sitemap_files_meta=sitemap_files_meta,
            source_label=source_label,
            cms_exclusions=cms_exclusions,
            runtime=runtime,
            output_filename=output_filename,
            max_depth=max_depth,
        )
