"""Top-level application orchestration — crawl, enrichment, export, and replay."""

from __future__ import annotations

import asyncio
import sys
import time
from urllib.parse import urlparse

from hype_frog.core.path_utils import path_exists

from hype_frog.core import get_logger
from hype_frog.core.console import log_completion_panel
from hype_frog.core.file_utils import build_regen_output_filename
from hype_frog.core.run_config import CliRunOverrides, RunConfig
from hype_frog.core.url_normalization import normalize_url_key
from hype_frog.orchestration.crawl_runner import execute_crawl
from hype_frog.orchestration.enrichment_flow import run_enrichment
from hype_frog.orchestration.export_flow import execute_export
from hype_frog.orchestration.export_row_builders import build_aeo_rows, build_aioseo_rows
from hype_frog.orchestration.crawl_payload_loader import crawl_row_count, release_audit_cache
from hype_frog.orchestration.run_setup import RunSetup, resolve_run_setup
from hype_frog.pipeline.enrich import value_or_default as _value_or_default_pipeline
from hype_frog.snapshots import (
    load_crawl_snapshot_by_id,
    load_latest_crawl_snapshot_for_domain,
    save_crawl_snapshot,
)
from hype_frog.core.env_vars import get_hf_refetch_skipped
from hype_frog.crawler.skipped_render_refetch import refetch_skipped_render_urls
from hype_frog.snapshots.replay import (
    ReplaySnapshotError,
    assert_snapshot_domain_matches,
    build_crawl_replay_snapshot,
    merge_setup_from_snapshot,
    recompute_composite_scores_for_replay,
    replay_from_snapshot,
    resolve_snapshot_domain,
)

logger = get_logger(__name__)

# Backward-compatible aliases for tests and quick_test imports.
_build_aeo_rows = build_aeo_rows
_build_aioseo_rows = build_aioseo_rows


_normalize_url_key = normalize_url_key  # backward-compat alias for tests


def _extract_subfolder(url: str) -> str:
    parsed = urlparse(str(url or ""))
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    return f"/{parts[0]}/" if parts else "/"


def _value_or_default(value: object, default: float = 0.0) -> float:
    return _value_or_default_pipeline(value, default)


def _execute_export_bundle(
    setup: RunSetup,
    crawl_result,
    enrichment_result,
) -> str:
    execute_export(
        setup,
        crawl_result,
        enrichment_result,
        value_or_default_fn=_value_or_default,
        extract_subfolder_fn=_extract_subfolder,
        build_aeo_rows_fn=_build_aeo_rows,
        build_aioseo_rows_fn=_build_aioseo_rows,
    )
    return crawl_result.output_filename


async def _run_replay_export(setup: RunSetup) -> tuple[str, int]:
    domain = resolve_snapshot_domain(setup.target_input)
    if setup.snapshot_id:
        snapshot = load_crawl_snapshot_by_id(setup.snapshot_id)
        if snapshot is None:
            raise ReplaySnapshotError(
                f"No crawl snapshot found with id {setup.snapshot_id!r}."
            )
        assert_snapshot_domain_matches(snapshot, setup.target_input)
    else:
        snapshot = load_latest_crawl_snapshot_for_domain(domain)
        if snapshot is None:
            raise ReplaySnapshotError(
                f"No crawl snapshots stored for domain {domain!r}. "
                "Run a full crawl first or pass --snapshot-id."
            )

    logger.info(
        "REPLAY RUN: loading snapshot %s from %s (%d URLs)",
        snapshot.snapshot_id,
        snapshot.run_timestamp,
        len(snapshot.main_rows),
    )

    setup = merge_setup_from_snapshot(setup, snapshot)
    source_path = snapshot.source_output_path or ""
    output_filename = build_regen_output_filename(
        source_path or f"replay_{domain}.xlsx",
        snapshot.snapshot_id,
    )
    crawl_result, enrichment_result = replay_from_snapshot(
        snapshot,
        setup,
        output_filename=output_filename,
    )
    if get_hf_refetch_skipped():
        logger.info(
            "REPLAY RUN: HF_REFETCH_SKIPPED set — re-rendering skipped HTTP-200 URLs."
        )
        await refetch_skipped_render_urls(
            enrichment_result.typed_main_rows,
            enrichment_result.typed_extra_rows,
            render_wait_ms=setup.render_wait_ms,
            selector_wait_ms=setup.selector_wait_ms,
        )
        recompute_composite_scores_for_replay(
            enrichment_result.typed_main_rows,
            enrichment_result.typed_extra_rows,
        )
    elif setup.re_enrich:
        logger.info(
            "REPLAY RUN: --re-enrich set, recomputing scores from snapshot signals "
            "(no network calls)."
        )
        recompute_composite_scores_for_replay(
            enrichment_result.typed_main_rows,
            enrichment_result.typed_extra_rows,
        )
    _execute_export_bundle(setup, crawl_result, enrichment_result)
    return output_filename, len(snapshot.main_rows)


async def main(
    run: RunConfig | None = None,
    cli_overrides: CliRunOverrides | None = None,
) -> None:
    _start = time.perf_counter()
    setup = resolve_run_setup(run, cli_overrides=cli_overrides)

    if setup.regen_report:
        try:
            output_filename, url_count = await _run_replay_export(setup)
        except ReplaySnapshotError as exc:
            logger.error("%s", exc)
            raise SystemExit(1) from exc
        _pdf = output_filename.replace(".xlsx", "_executive_summary.pdf")
        log_completion_panel(
            output_filename=output_filename,
            url_count=url_count,
            elapsed_seconds=time.perf_counter() - _start,
            pdf_filename=_pdf if path_exists(_pdf) else None,
        )
        return

    crawl_result = await execute_crawl(setup)
    enrichment_result = await run_enrichment(crawl_result)
    snapshot = build_crawl_replay_snapshot(setup, crawl_result, enrichment_result)
    save_crawl_snapshot(snapshot)
    output_filename = _execute_export_bundle(setup, crawl_result, enrichment_result)
    release_audit_cache(crawl_result)
    _pdf = output_filename.replace(".xlsx", "_executive_summary.pdf")
    log_completion_panel(
        output_filename=output_filename,
        url_count=crawl_row_count(crawl_result),
        elapsed_seconds=time.perf_counter() - _start,
        pdf_filename=_pdf if path_exists(_pdf) else None,
    )


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
