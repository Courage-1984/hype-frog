"""Async crawl execution orchestration."""

from __future__ import annotations

import asyncio
import os
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
from hype_frog.crawler import create_session, fetch_and_parse, parse_sitemap
from hype_frog.core.models import CrawlResult, CrawlRowPayload
from hype_frog.orchestration.run_setup import RunSetup

logger = get_logger(__name__)


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
        urls = list(dict.fromkeys(urls))
        if len(urls) != original_count:
            logger.info("Removed %s duplicate URLs.", original_count - len(urls))
        if setup.max_urls is not None and len(urls) > setup.max_urls:
            urls = urls[: setup.max_urls]
            logger.info("Applied crawl cap: limiting run to first %s URLs.", len(urls))

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
            profile_choice = input("Select crawl profile (1, 2, or 3): ").strip()
            if profile_choice == "1":
                workers = 2
                request_delay = 4.0
            elif profile_choice == "3":
                workers = 4
                request_delay = 1.5
            else:
                workers = MAX_WORKERS
                request_delay = DELAY_BETWEEN_REQUESTS

            suite_choice = input(
                "Run mode - 1) Main tab only  2) Full SEO suite (all tabs): "
            ).strip()
            full_suite = suite_choice == "2"
            previous_audit_path = input(
                "Optional previous audit .xlsx path for comparison (leave blank to skip): "
            ).strip()
            checkpoint_raw = input(
                "Checkpoint save every N completed URLs (0 to disable): "
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

        tasks = [
            asyncio.create_task(
                fetch_and_parse(
                    url,
                    session,
                    semaphore,
                    full_suite,
                    robots_cache,
                    request_delay,
                    sitemap_meta,
                    crawl_mode=setup.crawl_mode,
                    render_wait_ms=setup.render_wait_ms,
                    selector_wait_ms=setup.selector_wait_ms,
                )
            )
            for url in urls
        ]

        completed_urls_runtime = set(checkpoint_completed_urls)
        pending_batch: list[CrawlResult] = []
        typed_results: list[CrawlRowPayload] = []
        crawled_count = len(checkpoint_completed_urls)
        total_urls = len(urls) + len(checkpoint_completed_urls)
        for done_task in asyncio.as_completed(tasks):
            result_payload: CrawlRowPayload = await done_task
            typed_results.append(result_payload)
            main_row, extra_row = result_payload.model_dump_rows()
            result: CrawlResult = {"main": main_row, "extra": extra_row}
            pending_batch.append(result)
            crawled_count += 1
            url_done = main_row.get("URL")
            if url_done:
                completed_urls_runtime.add(url_done)
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
                    checkpoint_file, checkpoint_results, urls, checkpoint_completed_urls
                )
                logger.info(
                    "Checkpoint saved: %s/%s -> %s",
                    done_count,
                    total_urls,
                    checkpoint_file,
                )
        if pending_batch:
            cache.upsert_results(pending_batch)
        if checkpoint_every > 0:
            checkpoint_results = cache.all_results()
            save_checkpoint(
                checkpoint_file, checkpoint_results, urls, checkpoint_completed_urls
            )

        logger.info("Generating Excel report...")
        cache.close(cleanup_file=True)
        return CrawlExecutionResult(
            output_filename=output_filename,
            crawl_rows=typed_results,
            target_input=setup.target_input,
            max_psi_urls=setup.max_psi_urls,
            crawl_urls=urls,
            sitemap_meta=sitemap_meta,
            source_label=source_label,
            workers=workers,
            request_delay=request_delay,
            full_suite=full_suite,
            previous_audit_path=previous_audit_path,
            checkpoint_every=checkpoint_every,
            crawl_completed=True,
        )
