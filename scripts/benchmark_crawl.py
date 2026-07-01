#!/usr/bin/env python3
"""Profile crawl memory and wall time on a capped URL subset (offline-safe)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from dataclasses import replace

from hype_frog.core.path_bootstrap import bootstrap_src_path, repo_root

bootstrap_src_path(anchor=Path(__file__))
ROOT = repo_root()

from hype_frog.core.memory_guard import get_process_rss_mb, memory_circuit_breaker
from hype_frog.orchestration.crawl_payload_loader import (
    crawl_row_count,
    load_enrichment_row_pairs,
)
from hype_frog.orchestration.run_setup import RunSetup
from hype_frog.orchestration.crawl_runner import execute_crawl


def _synthetic_urls(count: int) -> list[str]:
    return [f"https://benchmark.example/page-{index}/" for index in range(count)]


async def _run_benchmark(
    *,
    url_count: int,
    workers: int,
    include_enrichment: bool,
    include_export: bool,
) -> dict[str, object]:
    from unittest.mock import AsyncMock, MagicMock, patch

    rss_start = get_process_rss_mb()
    started = time.perf_counter()

    payloads: list[dict[str, object]] = []

    async def fake_fetch_and_parse(
        url: str,
        *_args: object,
        **_kwargs: object,
    ) -> object:
        from hype_frog.core.models import CrawlRowPayload, ExtraRowPayload, MainRowPayload

        links = [
            {
                "Target URL": f"https://benchmark.example/target-{index}/",
                "Anchor Text": f"link {index}",
                "Rel Attribute": "",
                "Link Type": "Internal",
                "Status Code": 200,
                "Generic Anchor": False,
            }
            for index in range(25)
        ]
        return CrawlRowPayload(
            main=MainRowPayload.model_validate(
                {"values": {"URL": url, "Extraction State": "complete"}}
            ),
            extra=ExtraRowPayload.model_validate(
                {
                    "values": {
                        "URL": url,
                        "Extraction State": "complete",
                        "Link Details": links,
                    }
                }
            ),
        )

    setup = RunSetup(
        target_input="https://benchmark.example/sitemap.xml",
        max_urls=url_count,
        max_psi_urls=0,
        high_value_slugs=[],
        crawl_mode="fast",
        render_wait_ms=1000,
        selector_wait_ms=500,
        workers_preset=workers,
        request_delay_preset=0.0,
        full_suite_preset=False,
        previous_audit_path_preset="",
        checkpoint_every_preset=0,
        resume_checkpoint_mode="no",
        check_external_link_status=False,
        output_filename=str(ROOT / "reports" / "benchmark_audit.xlsx"),
        streaming=include_export,
    )

    urls = _synthetic_urls(url_count)

    with (
        patch(
            "hype_frog.orchestration.crawl_runner.parse_sitemap",
            AsyncMock(
                return_value=(urls, {url: {} for url in urls}, {}),
            ),
        ),
        patch(
            "hype_frog.orchestration.crawl_runner.fetch_and_parse",
            fake_fetch_and_parse,
        ),
        patch(
            "hype_frog.orchestration.crawl_runner.create_session",
        ) as session_cm,
    ):
        session_cm.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        session_cm.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await execute_crawl(setup)
        if include_export and include_enrichment:
            result = replace(result, streaming=True, full_suite=False)

    rss_after_crawl = get_process_rss_mb()
    enrichment_report: dict[str, object] = {}
    export_report: dict[str, object] = {}
    if include_enrichment:
        from hype_frog.orchestration.enrichment_flow import run_enrichment

        with (
            patch(
                "hype_frog.orchestration.enrichment_flow.load_gsc_enrichment_context",
                return_value=__import__(
                    "hype_frog.crawler.gsc_engine", fromlist=["GSCEnrichmentContext"]
                ).GSCEnrichmentContext({}, False, None, None),
            ),
            patch(
                "hype_frog.orchestration.enrichment_flow.create_session",
            ) as enrich_session_cm,
            patch(
                "hype_frog.orchestration.enrichment_flow.sniff_external_domains_head",
                AsyncMock(return_value={}),
            ),
        ):
            enrich_session_cm.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            enrich_session_cm.return_value.__aexit__ = AsyncMock(return_value=False)
            rss_before_enrichment = get_process_rss_mb()
            enrichment = await run_enrichment(result)
            rss_after_enrichment = get_process_rss_mb()
            memory_circuit_breaker()
            enrichment_report = {
                "enrichment_main_rows": len(enrichment.typed_main_rows),
                "enrichment_extra_rows": len(enrichment.typed_extra_rows),
                "rss_before_enrichment_mb": rss_before_enrichment,
                "rss_after_enrichment_mb": rss_after_enrichment,
            }
            if include_export:
                from hype_frog.orchestration.export_flow import execute_export
                from hype_frog.orchestration.export_row_builders import (
                    build_aeo_rows,
                    build_aioseo_rows,
                )
                from hype_frog.pipeline.enrich import value_or_default

                export_setup = replace(setup, streaming=True)
                rss_before_export = get_process_rss_mb()
                execute_export(
                    export_setup,
                    replace(result, streaming=True),
                    enrichment,
                    value_or_default_fn=value_or_default,
                    extract_subfolder_fn=lambda url: (
                        f"/{url.split('/')[3]}/" if len(url.split('/')) > 3 else "/"
                    ),
                    build_aeo_rows_fn=build_aeo_rows,
                    build_aioseo_rows_fn=build_aioseo_rows,
                )
                rss_after_export = get_process_rss_mb()
                memory_circuit_breaker()
                export_report = {
                    "rss_before_export_mb": rss_before_export,
                    "rss_after_export_mb": rss_after_export,
                    "export_streaming": True,
                }
    else:
        main_rows, extra_rows = load_enrichment_row_pairs(result)
        rss_after_load = get_process_rss_mb()
        memory_circuit_breaker()
        enrichment_report = {
            "materialised_main_rows": len(main_rows),
            "materialised_extra_rows": len(extra_rows),
            "rss_after_stream_load_mb": rss_after_load,
        }
        main_rows.clear()
        extra_rows.clear()

    rss_after_gc = get_process_rss_mb()
    elapsed = round(time.perf_counter() - started, 3)

    return {
        "url_count": crawl_row_count(result),
        "workers": workers,
        "elapsed_seconds": elapsed,
        "rss_start_mb": rss_start,
        "rss_after_crawl_mb": rss_after_crawl,
        "rss_after_gc_mb": rss_after_gc,
        **enrichment_report,
        **export_report,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark crawl RSS and throughput")
    parser.add_argument("--urls", type=int, default=100)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument(
        "--enrichment",
        action="store_true",
        help="Run offline enrichment after crawl and report enrichment-phase RSS",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Run streaming export after enrichment (implies --enrichment)",
    )
    args = parser.parse_args()
    include_enrichment = args.enrichment or args.export
    report = asyncio.run(
        _run_benchmark(
            url_count=args.urls,
            workers=args.workers,
            include_enrichment=include_enrichment,
            include_export=args.export,
        )
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
