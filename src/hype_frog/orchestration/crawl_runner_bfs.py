"""BFS crawl loop — checkpoint resume, seed phase, frontier expansion."""

from __future__ import annotations

import asyncio
import os
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from hype_frog.checkpoint import delete_checkpoint, load_checkpoint, save_checkpoint
from hype_frog.core import get_logger
from hype_frog.core.console import log_phase_banner
from hype_frog.core.crawl_log import CrawlLogCollector
from hype_frog.core.logger import console
from hype_frog.core.memory_guard import check_memory_limit, warn_if_large_crawl
from hype_frog.core.models import CrawlResult, CrawlRowPayload
from hype_frog.extractors.semantic_engine import IntentAnalyzer
from hype_frog.orchestration.crawl_runner_frontier import (
    ExcludedCmsActionUrl,
    candidate_internal_links,
    normalize_url_key,
)
from hype_frog.orchestration.crawl_runner_interactive import CrawlRuntimeOptions
from hype_frog.orchestration.run_setup import RunSetup

import hype_frog.orchestration.crawl_runner as _crawl_runner

logger = get_logger(__name__)


@dataclass(frozen=True)
class CrawlExecutionResult:
    output_filename: str
    crawl_rows: list[CrawlRowPayload]
    target_input: str
    max_psi_urls: int | None
    crawl_urls: list[str]
    sitemap_meta: dict[str, dict[str, str | None]]
    sitemap_files_meta: dict[str, dict[str, Any]]
    source_label: str
    workers: int
    request_delay: float
    full_suite: bool
    previous_audit_path: str
    checkpoint_every: int
    crawl_completed: bool
    check_external_link_status: bool
    check_og_images: bool = False
    check_content_images: bool = False
    crawl_duration_seconds: float = 0.0
    excluded_cms_action_urls: tuple[ExcludedCmsActionUrl, ...] = ()
    gsc_url_inspection: str | None = None
    max_memory_mb: int | None = None
    streaming: bool = False
    crawl_log_entries: list[Any] | None = None
    robots_by_domain: dict[str, dict[str, Any]] | None = None
    competitor_domains: tuple[str, ...] = ()


async def apply_search_intent(
    row: CrawlRowPayload,
    *,
    analyzer: IntentAnalyzer,
    crawl_log: CrawlLogCollector | None = None,
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
        logger.warning(
            "Search intent classification failed for %s: %s",
            main_values.get("URL"),
            exc,
        )
        extra_values["Search Intent"] = "Unknown"
        if crawl_log is not None:
            crawl_log.record(
                url=str(main_values.get("URL") or ""),
                phase="intent",
                error_type="Intent Classification Failed",
                error_detail=str(exc),
                recovery_action="Search Intent set to Unknown.",
            )


async def run_bfs_crawl_loop(
    *,
    setup: RunSetup,
    session: Any,
    urls: list[str],
    sitemap_meta: dict[str, dict[str, str | None]],
    sitemap_files_meta: dict[str, dict[str, Any]],
    source_label: str,
    cms_exclusions: dict[str, ExcludedCmsActionUrl],
    runtime: CrawlRuntimeOptions,
    output_filename: str,
    max_depth: int,
) -> CrawlExecutionResult:
    """Drive seed-phase and BFS expansion; persist rows via ``AuditCache``."""
    workers = runtime.workers
    request_delay = runtime.request_delay
    full_suite = runtime.full_suite
    previous_audit_path = runtime.previous_audit_path
    checkpoint_every = runtime.checkpoint_every

    checkpoint_file = output_filename.replace(".xlsx", "_checkpoint.json")
    cache_file = output_filename.replace(".xlsx", "_temp_cache.db")
    cache = _crawl_runner.AuditCache(cache_file)
    flush_batch_size = 250
    output_dir = os.path.dirname(output_filename)
    os.makedirs(output_dir, exist_ok=True)

    crawl_started = time.perf_counter()
    if setup.streaming:
        logger.info(
            "Streaming mode: crawl rows persist to SQLite cache during fetch "
            "(reduces in-memory duplication)."
        )

    semaphore = asyncio.Semaphore(workers)
    robots_cache: dict[str, dict[str, object]] = {}
    crawl_log = CrawlLogCollector()
    playwright_manager: Any | None = None
    accurate_render_available = setup.crawl_mode == "accurate"
    if accurate_render_available:
        playwright_manager = _crawl_runner.PlaywrightSessionManager()
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
    bfs_state: dict[str, object] = {}
    if os.path.exists(checkpoint_file):
        if setup.resume_checkpoint_mode == "prompt":
            resume_choice = (
                await asyncio.to_thread(
                    input,
                    "Checkpoint found for this source. Resume from checkpoint? (y/N): ",
                )
            ).strip().lower()
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
                resumed_results, checkpoint_completed_urls, bfs_state = load_checkpoint(
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
                bfs_state = {}

    completed_urls_runtime = set(checkpoint_completed_urls)
    pending_batch: list[CrawlResult] = []
    total_crawl_urls = len(urls) + len(checkpoint_completed_urls)
    warn_if_large_crawl(total_crawl_urls)
    crawled_count = len(checkpoint_completed_urls)
    completed_normalized = {
        normalize_url_key(url) for url in completed_urls_runtime if url
    }
    seed_queue: deque[tuple[str, int, str | None]] = deque()
    bfs_queue: deque[tuple[str, int, str | None]] = deque()
    queued_urls: set[str] = set(completed_normalized)
    crawl_urls_runtime: list[str] = []
    sitemap_seed_urls: set[str] = set()
    restored_runtime = bfs_state.get("crawl_urls_runtime") if bfs_state else None
    if isinstance(restored_runtime, list) and restored_runtime:
        crawl_urls_runtime = [str(url) for url in restored_runtime]
        seed_queue.extend(
            tuple(item)  # type: ignore[misc]
            for item in (bfs_state.get("seed_queue_pending") or [])
        )
        bfs_queue.extend(
            tuple(item)  # type: ignore[misc]
            for item in (bfs_state.get("queue_pending") or [])
        )
        restored_queued = bfs_state.get("queued_set") or []
        queued_urls.update(str(url) for url in restored_queued)
        seed_phase_value = bfs_state.get("seed_phase_active")
        seed_phase_active = (
            bool(seed_phase_value) if seed_phase_value is not None else bool(seed_queue)
        )
    else:
        seed_phase_active = False
        for url in urls:
            normalized = normalize_url_key(url)
            if not normalized or normalized in queued_urls:
                continue
            seed_queue.append((normalized, 0, None))
            queued_urls.add(normalized)
            crawl_urls_runtime.append(normalized)
            sitemap_seed_urls.add(normalized)
        seed_phase_active = bool(seed_queue)
    if not sitemap_seed_urls:
        for url in crawl_urls_runtime:
            sitemap_seed_urls.add(url)
    total_urls = len(crawl_urls_runtime) + len(checkpoint_completed_urls)
    in_flight: dict[
        asyncio.Task[CrawlRowPayload], tuple[str, int, str | None, str]
    ] = {}
    intent_analyzer = _crawl_runner.IntentAnalyzer()

    def _checkpoint_bfs_state() -> dict[str, object]:
        return {
            "queue_pending": list(bfs_queue),
            "queued_set": list(queued_urls),
            "seed_queue_pending": list(seed_queue),
            "seed_phase_active": seed_phase_active,
            "crawl_urls_runtime": list(crawl_urls_runtime),
        }

    def _can_enqueue() -> bool:
        return setup.max_urls is None or len(queued_urls) < setup.max_urls

    def _ready_for_bfs_phase() -> bool:
        return (
            seed_phase_active
            and not seed_queue
            and all(meta[3] != "seed" for meta in in_flight.values())
        )

    if seed_phase_active:
        log_phase_banner(
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
                _crawl_runner.fetch_and_parse(
                    next_url,
                    session,
                    semaphore,
                    robots_cache,
                    request_delay,
                    sitemap_meta,
                    crawl_mode=setup.crawl_mode,
                    render_wait_ms=setup.render_wait_ms,
                    selector_wait_ms=setup.selector_wait_ms,
                    depth=next_depth,
                    render_pages=accurate_render_available,
                    playwright_session_manager=playwright_manager,
                    crawl_log=crawl_log,
                )
            )
            in_flight[task] = (next_url, next_depth, discovered_on_url, phase)

    _crawl_progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.description}"),
        BarColumn(bar_width=40),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    )
    _crawl_task = _crawl_progress.add_task(
        "Crawling", total=total_urls, completed=crawled_count
    )
    _crawl_progress.start()
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
                await apply_search_intent(
                    result_payload, analyzer=intent_analyzer, crawl_log=crawl_log
                )
                main_row, extra_row = result_payload.model_dump_rows()
                result: CrawlResult = {"main": main_row, "extra": extra_row}
                pending_batch.append(result)
                crawled_count += 1
                url_done = main_row.get("URL")
                if url_done:
                    completed_urls_runtime.add(url_done)
                    completed_normalized.add(normalize_url_key(url_done))
                if scheduled_depth < max_depth:
                    for discovered_url in candidate_internal_links(
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
                _crawl_progress.update(_crawl_task, completed=crawled_count, total=total_urls)
                if len(pending_batch) >= flush_batch_size:
                    cache.upsert_results(pending_batch)
                    pending_batch = []
                    check_memory_limit(setup.max_memory_mb)
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
                        bfs_state=_checkpoint_bfs_state(),
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
                    log_phase_banner(
                        f"PHASE 2/2: BFS expansion from discovered internal links ({len(bfs_queue)} queued)"
                    )
                _schedule_available()
    finally:
        _crawl_progress.stop()
        if playwright_manager is not None:
            await playwright_manager.aclose()
    if pending_batch:
        cache.upsert_results(pending_batch)
    if checkpoint_every > 0:
        delete_checkpoint(checkpoint_file)

    typed_results: list[CrawlRowPayload] = []
    for cached in cache.iter_results():
        typed_results.append(
            CrawlRowPayload.model_validate(
                {"main": cached.get("main", {}), "extra": cached.get("extra", {})}
            )
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
    log_phase_banner("FINALIZE: Crawl complete, generating Excel report")
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
        sitemap_files_meta=sitemap_files_meta,
        source_label=source_label,
        workers=workers,
        request_delay=request_delay,
        full_suite=full_suite,
        previous_audit_path=previous_audit_path,
        checkpoint_every=checkpoint_every,
        crawl_completed=True,
        check_external_link_status=setup.check_external_link_status,
        check_og_images=setup.check_og_images,
        check_content_images=setup.check_content_images,
        crawl_duration_seconds=crawl_duration_seconds,
        excluded_cms_action_urls=tuple(cms_exclusions.values()),
        gsc_url_inspection=setup.gsc_url_inspection,
        max_memory_mb=setup.max_memory_mb,
        streaming=setup.streaming,
        crawl_log_entries=crawl_log.entries,
        robots_by_domain=dict(robots_cache),
        competitor_domains=setup.competitor_domains,
    )
