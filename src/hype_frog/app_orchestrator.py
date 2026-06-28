from __future__ import annotations

import asyncio
import os
import sys
import time
from urllib.parse import urlparse

from hype_frog.core import get_logger
from hype_frog.core.console import log_completion_panel
from hype_frog.core.run_config import CliRunOverrides, RunConfig
from hype_frog.core.url_normalization import normalize_url_key
from hype_frog.orchestration.crawl_runner import execute_crawl
from hype_frog.orchestration.enrichment_flow import run_enrichment
from hype_frog.orchestration.export_flow import execute_export
from hype_frog.orchestration.export_row_builders import build_aeo_rows, build_aioseo_rows
from hype_frog.orchestration.run_setup import resolve_run_setup
from hype_frog.pipeline.enrich import value_or_default as _value_or_default_pipeline

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


async def main(
    run: RunConfig | None = None,
    cli_overrides: CliRunOverrides | None = None,
) -> None:
    _start = time.perf_counter()
    setup = resolve_run_setup(run, cli_overrides=cli_overrides)
    crawl_result = await execute_crawl(setup)
    enrichment_result = await run_enrichment(crawl_result)
    execute_export(
        setup,
        crawl_result,
        enrichment_result,
        value_or_default_fn=_value_or_default,
        extract_subfolder_fn=_extract_subfolder,
        build_aeo_rows_fn=_build_aeo_rows,
        build_aioseo_rows_fn=_build_aioseo_rows,
    )
    _pdf = crawl_result.output_filename.replace(".xlsx", "_executive_summary.pdf")
    log_completion_panel(
        output_filename=crawl_result.output_filename,
        url_count=len(crawl_result.crawl_rows),
        elapsed_seconds=time.perf_counter() - _start,
        pdf_filename=_pdf if os.path.exists(_pdf) else None,
    )


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
