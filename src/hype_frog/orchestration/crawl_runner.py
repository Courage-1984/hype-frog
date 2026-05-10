"""Async crawl execution orchestration."""

from __future__ import annotations

import asyncio
import os
from collections import deque
from dataclasses import dataclass
from urllib.parse import urlparse

from hype_frog.checkpoint import AuditCache, load_checkpoint, save_checkpoint
from hype_frog.config import (
    DELAY_BETWEEN_REQUESTS,
    MAX_RETRIES,
    MAX_WORKERS,
    TIMEOUT_SECONDS,
)
from hype_frog.core import get_logger
from hype_frog.core.file_utils import build_output_filename
from hype_frog.core.url_normalization import normalize_url
from hype_frog.crawler import create_session, fetch_and_parse, parse_sitemap
from hype_frog.core.models import CrawlResult, CrawlRowPayload
from hype_frog.extractors.semantic_engine import IntentAnalyzer
from hype_frog.orchestration.run_setup import RunSetup

logger = get_logger(__name__)


def _normalize_url_key(url: object) -> str:
    return normalize_url(url)


def _max_depth_from_env(default: int = 3) -> int:
    raw = os.getenv("HF_MAX_DEPTH", "").strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        logger.warning("Invalid HF_MAX_DEPTH=%r; using default %s.", raw, default)
        return default


def _candidate_internal_links(row: CrawlRowPayload) -> list[str]:
    links = row.extra.values.get("Internal Links List Full") or []
    if not isinstance(links, list):
        return []
    out: list[str] = []
    for link in links:
        normalized = _normalize_url_key(link)
        if normalized:
            out.append(normalized)
    return out


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


async def execute_crawl(setup: RunSetup) -> CrawlExecutionResult:
    urls: list[str] = []
    sitemap_meta: dict[str, dict[str, str | None]] = {}
    workers = MAX_WORKERS
    request_delay = DELAY_BETWEEN_REQUESTS
    source_label = "manual_input"

    async with create_session() as session:
        if setup.target_input.lower().endswith(".xml"):
            urls, sitemap_meta = await parse_sitemap(setup.target_input, session)
            parsed_source = urlparse(setup.target_input)
            source_label = parsed_source.netloc or "sitemap"
        else:
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

        original_count = len(urls)
        urls = list(dict.fromkeys(_normalize_url_key(url) for url in urls if url))
        if sitemap_meta:
            sitemap_meta = {
                _normalize_url_key(url): meta for url, meta in sitemap_meta.items()
            }
        if len(urls) != original_count:
            logger.info("Removed %s duplicate URLs.", original_count - len(urls))
        if setup.max_urls is not None and len(urls) > setup.max_urls:
            urls = urls[: setup.max_urls]
            logger.info(
                "Applied initial seed cap: limiting run to first %s URLs.",
                len(urls),
            )
        max_depth = _max_depth_from_env(default=3)

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
            logger.info("Crawl safety profile: preset (Faster: 4 workers, 1.5s delay)")
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
        logger.info("Starting crawl of %s URLs...", len(urls))
        logger.info(
            f"Max Workers: {workers} | Delay: {request_delay}s | "
            f"Retries: {MAX_RETRIES} | Timeout: {TIMEOUT_SECONDS}s | "
            f"Mode: {'Full Suite' if full_suite else 'Main Only'}"
        )

        semaphore = asyncio.Semaphore(workers)
        robots_cache: dict[str, dict[str, object]] = {}
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
        crawl_queue: deque[tuple[str, int]] = deque()
        queued_urls: set[str] = set(completed_normalized)
        crawl_urls_runtime: list[str] = []
        for url in urls:
            normalized = _normalize_url_key(url)
            if not normalized or normalized in queued_urls:
                continue
            crawl_queue.append((normalized, 0))
            queued_urls.add(normalized)
            crawl_urls_runtime.append(normalized)
        total_urls = len(crawl_urls_runtime) + len(checkpoint_completed_urls)
        in_flight: dict[asyncio.Task[CrawlRowPayload], tuple[str, int]] = {}
        intent_analyzer = IntentAnalyzer()

        def _can_enqueue() -> bool:
            return setup.max_urls is None or len(queued_urls) < setup.max_urls

        def _schedule_available() -> None:
            while crawl_queue and len(in_flight) < workers:
                next_url, next_depth = crawl_queue.popleft()
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
                    )
                )
                in_flight[task] = (next_url, next_depth)

        _schedule_available()
        while in_flight:
            done_tasks, _pending = await asyncio.wait(
                set(in_flight),
                return_when=asyncio.FIRST_COMPLETED,
            )
            for done_task in done_tasks:
                _scheduled_url, scheduled_depth = in_flight.pop(done_task)
                result_payload: CrawlRowPayload = await done_task
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
                    for discovered_url in _candidate_internal_links(result_payload):
                        if discovered_url in queued_urls:
                            continue
                        if not _can_enqueue():
                            break
                        queued_urls.add(discovered_url)
                        crawl_queue.append((discovered_url, scheduled_depth + 1))
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
            _schedule_available()
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

        logger.info("Generating Excel report...")
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
        )
