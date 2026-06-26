"""Async crawl execution orchestration."""

from __future__ import annotations

import asyncio
import os
import time
from collections import deque
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from hype_frog.checkpoint import AuditCache, load_checkpoint, save_checkpoint
from hype_frog.config import (
    DELAY_BETWEEN_REQUESTS,
    EXCLUDED_CMS_ACTION_QUERY_PARAMS,
    MAX_RETRIES,
    MAX_WORKERS,
    TIMEOUT_SECONDS,
)
from hype_frog.core import get_logger
from hype_frog.core.file_utils import build_output_filename
from hype_frog.core.url_normalization import normalize_url
from hype_frog.crawler import create_session, fetch_and_parse, parse_sitemap
from hype_frog.crawler.network_engine import PlaywrightSessionManager
from hype_frog.core.models import CrawlResult, CrawlRowPayload
from hype_frog.extractors.semantic_engine import IntentAnalyzer
from hype_frog.orchestration.run_setup import RunSetup

logger = get_logger(__name__)

_NON_HTML_PATH_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".svg",
        ".ico",
        ".bmp",
        ".tif",
        ".tiff",
        ".avif",
        ".pdf",
        ".zip",
        ".rar",
        ".7z",
        ".gz",
        ".tar",
        ".mp3",
        ".wav",
        ".ogg",
        ".m4a",
        ".mp4",
        ".mov",
        ".avi",
        ".wmv",
        ".mkv",
        ".webm",
        ".doc",
        ".docx",
        ".ppt",
        ".pptx",
        ".xls",
        ".xlsx",
        ".csv",
        ".json",
        ".xml",
        ".txt",
        ".js",
        ".css",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".eot",
        ".map",
    }
)


_EXCLUDED_CMS_QUERY_KEYS_LOWER: frozenset[str] = frozenset(
    key.lower() for key in EXCLUDED_CMS_ACTION_QUERY_PARAMS
)


@dataclass(frozen=True)
class ExcludedCmsActionUrl:
    """A URL withheld from the crawl queue because of CMS action query parameters."""

    url: str
    excluded_query_params: tuple[str, ...]
    discovered_on_url: str
    exclusion_reason: str = (
        "CMS / WooCommerce action parameter — not crawled as a distinct page"
    )


def cms_action_exclusion_keys(url: str) -> frozenset[str]:
    """Return matched CMS action query-parameter names, or an empty set."""
    parsed = urlparse(str(url or "").strip())
    if not parsed.query:
        return frozenset()
    query_keys = {str(key).lower() for key in parse_qs(parsed.query).keys()}
    return frozenset(
        key for key in query_keys if key in _EXCLUDED_CMS_QUERY_KEYS_LOWER
    )


def _register_cms_exclusion(
    registry: dict[str, ExcludedCmsActionUrl],
    url: str,
    discovered_on_url: str,
) -> None:
    keys = cms_action_exclusion_keys(url)
    if not keys:
        return
    normalized = _normalize_url_key(url)
    if not normalized or normalized in registry:
        return
    registry[normalized] = ExcludedCmsActionUrl(
        url=normalized,
        excluded_query_params=tuple(sorted(keys)),
        discovered_on_url=discovered_on_url,
    )


def _normalize_url_key(url: object) -> str:
    return normalize_url(url)


def _is_crawlable_html_candidate(url: str) -> bool:
    """Allow likely HTML document URLs and exclude binary/static assets."""
    parsed = urlparse(str(url or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return False
    if cms_action_exclusion_keys(url):
        return False
    path = (parsed.path or "").strip().lower()
    if not path:
        return True
    return not any(path.endswith(ext) for ext in _NON_HTML_PATH_EXTENSIONS)


def _candidate_internal_links(
    row: CrawlRowPayload,
    cms_exclusions: dict[str, ExcludedCmsActionUrl] | None = None,
) -> list[str]:
    links = row.extra.values.get("Internal Links List Full") or []
    if not isinstance(links, list):
        return []
    parent_url = str(row.main.values.get("URL") or row.extra.values.get("URL") or "")
    out: list[str] = []
    for link in links:
        normalized = _normalize_url_key(link)
        if not normalized:
            continue
        if cms_action_exclusion_keys(normalized):
            if cms_exclusions is not None:
                _register_cms_exclusion(
                    cms_exclusions,
                    normalized,
                    parent_url or "Internal link",
                )
            continue
        if _is_crawlable_html_candidate(normalized):
            out.append(normalized)
    return out


def _log_phase_banner(title: str) -> None:
    bar = "=" * 72
    logger.info("")
    logger.info(bar)
    logger.info(" %s", title)
    logger.info(bar)
    logger.info("")


def _max_depth_from_env(default: int = 3) -> int:
    raw = os.getenv("HF_MAX_DEPTH", "").strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        logger.warning("Invalid HF_MAX_DEPTH=%r; using default %s.", raw, default)
        return default


async def _apply_search_intent(
    row: CrawlRowPayload,
    *,
    analyzer: IntentAnalyzer,
) -> None:
    main_values = row.main.values
    extra_values = row.extra.values
    text_parts = [
        main_values.get("Title"),
        main_values.get("Meta Description"),
        extra_values.get("Current H-Tag Structure"),
        extra_values.get("Current Page Copy Snippet"),
    ]
    rendered_text = " ".join(str(part or "").strip() for part in text_parts if part)
    try:
        extra_values["Search Intent"] = await analyzer.analyze_intent(rendered_text)
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.warning("Search intent classification failed for %s: %s", main_values.get("URL"), exc)
        extra_values["Search Intent"] = "Unknown"


@dataclass(frozen=True)
class CrawlExecutionResult:
    output_filename: str
    crawl_rows: list[CrawlRowPayload]
    target_input: str
    max_psi_urls: int | None
    crawl_urls: list[str]
    sitemap_meta: dict[str, dict[str, str | None]]
    source_label: str
    workers: int
    request_delay: float
    full_suite: bool
    previous_audit_path: str
    checkpoint_every: int
    crawl_completed: bool
    check_external_link_status: bool
    crawl_duration_seconds: float = 0.0
    excluded_cms_action_urls: tuple[ExcludedCmsActionUrl, ...] = ()


async def execute_crawl(setup: RunSetup) -> CrawlExecutionResult:
    urls: list[str] = []
    sitemap_meta: dict[str, dict[str, str | None]] = {}
    workers = MAX_WORKERS
    request_delay = DELAY_BETWEEN_REQUESTS
    source_label = "manual_input"

    async with create_session() as session:
        if setup.target_input.lower().endswith(".xml"):
            _log_phase_banner("SETUP: Parsing provided sitemap seed list")
            urls, sitemap_meta = await parse_sitemap(setup.target_input, session)
            parsed_source = urlparse(setup.target_input)
            source_label = parsed_source.netloc or "sitemap"
        else:
            _log_phase_banner("SETUP: Single URL seed mode")
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
            _register_cms_exclusion(cms_exclusions, str(url), "Sitemap")
        urls = list(
            dict.fromkeys(
                _normalize_url_key(url)
                for url in urls
                if url and _is_crawlable_html_candidate(str(url))
            )
        )
        if cms_exclusions:
            logger.info(
                "Withheld %s CMS action URL(s) from crawl queue (see CMS Action URLs tab).",
                len(cms_exclusions),
            )
        if sitemap_meta:
            sitemap_meta = {
                _normalize_url_key(url): meta
                for url, meta in sitemap_meta.items()
                if _is_crawlable_html_candidate(str(url))
            }
        if len(urls) != original_count:
            logger.info("Removed %s duplicate URLs.", original_count - len(urls))
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

        if setup.workers_preset is not None:
            workers = setup.workers_preset
            request_delay = (
                setup.request_delay_preset
                if setup.request_delay_preset is not None
                else DELAY_BETWEEN_REQUESTS
            )
            full_suite = bool(setup.full_suite_preset)
            previous_audit_path = (setup.previous_audit_path_preset or "").strip()
            checkpoint_every = int(setup.checkpoint_every_preset or 0)
            logger.info(
                "Crawl safety profile: preset (%s workers, %ss delay)",
                workers,
                request_delay,
            )
            logger.info("Run mode: Full SEO suite (preset)")
            logger.info("Checkpoint save: disabled (preset)")
        else:
            logger.info("Crawl safety profile:")
            logger.info("1. Gentle (fewer workers, longer delay)")
            logger.info("2. Balanced (default)")
            logger.info("3. Faster (more workers, shorter delay)")
            profile_choice = input(
                "Select Crawl Safety Profile [1:Gentle | 2:Balanced | 3:Faster]: "
            ).strip()
            if profile_choice == "1":
                workers = 2
                request_delay = 4.0
            elif profile_choice == "3":
                workers = 4
                request_delay = 1.5
            elif profile_choice == "2" or profile_choice == "":
                workers = MAX_WORKERS
                request_delay = DELAY_BETWEEN_REQUESTS
            else:
                logger.info("> Invalid input, defaulting to Balanced.")
                workers = MAX_WORKERS
                request_delay = DELAY_BETWEEN_REQUESTS

            suite_choice = input(
                "Audit Depth: [1] Main Inventory Only | [2] Full AEO/SEO Suite: "
            ).strip()
            if suite_choice == "1":
                full_suite = False
            elif suite_choice == "2":
                full_suite = True
            elif suite_choice == "":
                full_suite = False
            else:
                logger.info("> Invalid input, defaulting to Full AEO/SEO Suite.")
                full_suite = True

            previous_audit_path = input(
                "Previous Audit Path (.xlsx) for Delta Analysis [leave blank to skip]: "
            ).strip()
            checkpoint_raw = input(
                "Auto-Save Checkpoint Frequency (N URLs) [0 to disable]: "
            ).strip()
            try:
                checkpoint_every = int(checkpoint_raw or "0")
            except ValueError:
                checkpoint_every = 0

        output_filename = os.getenv("HF_OUTPUT_FILENAME") or build_output_filename(
            source_label, full_suite
        )
        checkpoint_file = output_filename.replace(".xlsx", "_checkpoint.json")
        cache_file = output_filename.replace(".xlsx", "_temp_cache.db")
        cache = AuditCache(cache_file)
        flush_batch_size = 250
        output_dir = os.path.dirname(output_filename)
        os.makedirs(output_dir, exist_ok=True)

        logger.info("Output file: %s", output_filename)
        print("\n" + "=" * 30)
        crawl_started = time.perf_counter()
        logger.info("Starting crawl of %s URLs...", len(urls))
        logger.info(
            f"Max Workers: {workers} | Delay: {request_delay}s | "
            f"Retries: {MAX_RETRIES} | Timeout: {TIMEOUT_SECONDS}s | "
            f"Mode: {'Full Suite' if full_suite else 'Main Only'}"
        )

        semaphore = asyncio.Semaphore(workers)
        robots_cache: dict[str, dict[str, object]] = {}
        playwright_manager: PlaywrightSessionManager | None = None
        accurate_render_available = setup.crawl_mode == "accurate"
        if accurate_render_available:
            playwright_manager = PlaywrightSessionManager()
            probe_url = urls[0] if urls else setup.target_input
            if await playwright_manager.get_context(str(probe_url)) is None:
                logger.warning(
                    "Accurate crawl mode requested but Playwright is unavailable; "
                    "using raw_http extraction for all URLs in this run."
                )
                accurate_render_available = False
            else:
                logger.info(
                    "Accurate crawl mode: shared Playwright session active for rendered_browser extraction."
                )
        resumed_results: list[CrawlResult] = []
        checkpoint_completed_urls: set[str] = set()
        if os.path.exists(checkpoint_file):
            if setup.resume_checkpoint_mode == "prompt":
                resume_choice = (
                    input(
                        "Checkpoint found for this source. Resume from checkpoint? (y/N): "
                    )
                    .strip()
                    .lower()
                )
                want_resume = resume_choice in {"y", "yes"}
            elif setup.resume_checkpoint_mode == "yes":
                want_resume = True
            else:
                want_resume = False
                logger.warning(
                    "Checkpoint file present; starting fresh (non-interactive preset)."
                )
            if want_resume:
                try:
                    resumed_results, checkpoint_completed_urls = load_checkpoint(
                        checkpoint_file
                    )
                    cache.upsert_results(resumed_results)
                    urls = [u for u in urls if u not in checkpoint_completed_urls]
                    logger.info(
                        "Resuming crawl. Completed: %s | Remaining: %s",
                        len(checkpoint_completed_urls),
                        len(urls),
                    )
                except Exception as exc:
                    logger.warning("Could not load checkpoint. Starting fresh. (%s)", exc)
                    resumed_results = []
                    checkpoint_completed_urls = set()

        completed_urls_runtime = set(checkpoint_completed_urls)
        pending_batch: list[CrawlResult] = []
        typed_results: list[CrawlRowPayload] = []
        crawled_count = len(checkpoint_completed_urls)
        completed_normalized = {
            _normalize_url_key(url) for url in completed_urls_runtime if url
        }
        seed_queue: deque[tuple[str, int, str | None]] = deque()
        bfs_queue: deque[tuple[str, int, str | None]] = deque()
        queued_urls: set[str] = set(completed_normalized)
        crawl_urls_runtime: list[str] = []
        sitemap_seed_urls: set[str] = set()
        for url in urls:
            normalized = _normalize_url_key(url)
            if not normalized or normalized in queued_urls:
                continue
            seed_queue.append((normalized, 0, None))
            queued_urls.add(normalized)
            crawl_urls_runtime.append(normalized)
            sitemap_seed_urls.add(normalized)
        total_urls = len(crawl_urls_runtime) + len(checkpoint_completed_urls)
        in_flight: dict[
            asyncio.Task[CrawlRowPayload], tuple[str, int, str | None, str]
        ] = {}
        intent_analyzer = IntentAnalyzer()
        seed_phase_active = bool(seed_queue)

        def _can_enqueue() -> bool:
            return setup.max_urls is None or len(queued_urls) < setup.max_urls

        def _ready_for_bfs_phase() -> bool:
            return (
                seed_phase_active
                and not seed_queue
                and all(meta[3] != "seed" for meta in in_flight.values())
            )

        if seed_phase_active:
            _log_phase_banner(
                f"PHASE 1/2: Crawling sitemap seed URLs first ({len(seed_queue)} URLs)"
            )

        def _schedule_available() -> None:
            while len(in_flight) < workers:
                if seed_phase_active:
                    if not seed_queue:
                        break
                    next_url, next_depth, discovered_on_url = seed_queue.popleft()
                    phase = "seed"
                else:
                    if not bfs_queue:
                        break
                    next_url, next_depth, discovered_on_url = bfs_queue.popleft()
                    phase = "bfs"
                task = asyncio.create_task(
                    fetch_and_parse(
                        next_url,
                        session,
                        semaphore,
                        full_suite,
                        robots_cache,
                        request_delay,
                        sitemap_meta,
                        crawl_mode=setup.crawl_mode,
                        render_wait_ms=setup.render_wait_ms,
                        selector_wait_ms=setup.selector_wait_ms,
                        depth=next_depth,
                        render_pages=accurate_render_available,
                        playwright_session_manager=playwright_manager,
                    )
                )
                in_flight[task] = (next_url, next_depth, discovered_on_url, phase)

        try:
            _schedule_available()
            while in_flight:
                done_tasks, _pending = await asyncio.wait(
                    set(in_flight),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for done_task in done_tasks:
                    (
                        scheduled_url,
                        scheduled_depth,
                        discovered_on_url,
                        scheduled_phase,
                    ) = in_flight.pop(done_task)
                    result_payload: CrawlRowPayload = await done_task
                    discovered_from = discovered_on_url or ""
                    if scheduled_url in sitemap_seed_urls:
                        result_payload.main.values["Discovered On URL"] = ""
                        result_payload.extra.values["Discovered On URL"] = ""
                    else:
                        result_payload.main.values["Discovered On URL"] = discovered_from
                        result_payload.extra.values["Discovered On URL"] = discovered_from
                    await _apply_search_intent(result_payload, analyzer=intent_analyzer)
                    typed_results.append(result_payload)
                    main_row, extra_row = result_payload.model_dump_rows()
                    result: CrawlResult = {"main": main_row, "extra": extra_row}
                    pending_batch.append(result)
                    crawled_count += 1
                    url_done = main_row.get("URL")
                    if url_done:
                        completed_urls_runtime.add(url_done)
                        completed_normalized.add(_normalize_url_key(url_done))
                    if scheduled_depth < max_depth:
                        for discovered_url in _candidate_internal_links(
                            result_payload,
                            cms_exclusions,
                        ):
                            if discovered_url in queued_urls:
                                continue
                            if not _can_enqueue():
                                break
                            queued_urls.add(discovered_url)
                            bfs_queue.append(
                                (discovered_url, scheduled_depth + 1, scheduled_url)
                            )
                            crawl_urls_runtime.append(discovered_url)
                        total_urls = len(crawl_urls_runtime) + len(checkpoint_completed_urls)
                    if len(pending_batch) >= flush_batch_size:
                        cache.upsert_results(pending_batch)
                        pending_batch = []
                    done_count = crawled_count
                    if checkpoint_every > 0 and done_count % checkpoint_every == 0:
                        if pending_batch:
                            cache.upsert_results(pending_batch)
                            pending_batch = []
                        checkpoint_results = cache.all_results()
                        save_checkpoint(
                            checkpoint_file,
                            checkpoint_results,
                            crawl_urls_runtime,
                            checkpoint_completed_urls,
                        )
                        logger.info(
                            "Checkpoint saved: %s/%s -> %s",
                            done_count,
                            total_urls,
                            checkpoint_file,
                        )
                    if (
                        seed_phase_active
                        and scheduled_phase == "seed"
                        and _ready_for_bfs_phase()
                    ):
                        seed_phase_active = False
                        _log_phase_banner(
                            f"PHASE 2/2: BFS expansion from discovered internal links ({len(bfs_queue)} queued)"
                        )
                    _schedule_available()
        finally:
            if playwright_manager is not None:
                await playwright_manager.aclose()
        if pending_batch:
            cache.upsert_results(pending_batch)
        if checkpoint_every > 0:
            checkpoint_results = cache.all_results()
            save_checkpoint(
                checkpoint_file,
                checkpoint_results,
                crawl_urls_runtime,
                checkpoint_completed_urls,
            )

        rendered_rows = sum(
            1
            for row in typed_results
            if row.main.values.get("Extraction Source") == "rendered_browser"
        )
        raw_rows = sum(
            1
            for row in typed_results
            if row.main.values.get("Extraction Source") == "raw_http"
        )
        fallback_rows = sum(
            1 for row in typed_results if row.extra.values.get("Extraction Source Fallback")
        )
        crawl_duration_seconds = round(time.perf_counter() - crawl_started, 1)
        _log_phase_banner("FINALIZE: Crawl complete, generating Excel report")
        logger.info(
            "Crawl finished in %.1fs (%s URLs, %s workers).",
            crawl_duration_seconds,
            len(typed_results),
            workers,
        )
        logger.info(
            "Extraction sources: rendered_browser=%s raw_http=%s render_fallback=%s (crawl_mode=%s).",
            rendered_rows,
            raw_rows,
            fallback_rows,
            setup.crawl_mode,
        )
        cache.close(cleanup_file=True)
        return CrawlExecutionResult(
            output_filename=output_filename,
            crawl_rows=typed_results,
            target_input=setup.target_input,
            max_psi_urls=setup.max_psi_urls,
            crawl_urls=crawl_urls_runtime,
            sitemap_meta=sitemap_meta,
            source_label=source_label,
            workers=workers,
            request_delay=request_delay,
            full_suite=full_suite,
            previous_audit_path=previous_audit_path,
            checkpoint_every=checkpoint_every,
            crawl_completed=True,
            check_external_link_status=setup.check_external_link_status,
            crawl_duration_seconds=crawl_duration_seconds,
            excluded_cms_action_urls=tuple(cms_exclusions.values()),
        )
