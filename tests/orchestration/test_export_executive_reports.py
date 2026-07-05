"""Exercises `export_executive_reports.write_executive_reports` for real.

Every existing test that could trigger this orchestration glue
(`test_export_flow.py`) explicitly `monkeypatch.delenv`s `HF_EXPORT_PDF` /
`HF_EXPORT_HTML`, so the PDF/HTML generation wiring after a real crawl+export
was never exercised, even indirectly. This file enables both flags and asserts
the real output files are produced.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

import pytest

from hype_frog.app_orchestrator import (
    _build_aeo_rows,
    _build_aioseo_rows,
    _extract_subfolder,
    _value_or_default,
)
from hype_frog.crawler.gsc_engine import GSCEnrichmentContext
from hype_frog.diagnostics.full_smoke_fixtures import (
    FullSmokeFixture,
    build_full_smoke_fixture,
    build_smoke_crawl_payload,
    full_smoke_network_patches,
)
from hype_frog.orchestration.crawl_runner import CrawlExecutionResult
from hype_frog.orchestration.enrichment_flow import run_enrichment
from hype_frog.orchestration.export_flow import execute_export
from hype_frog.orchestration.run_setup import RunSetup
from hype_frog.reporter.pdf_exporter import executive_summary_pdf_path


def _empty_gsc_context(_target: str) -> GSCEnrichmentContext:
    return GSCEnrichmentContext({}, False, None, None)


@contextmanager
def _offline_enrichment_patches(fixture: FullSmokeFixture) -> Iterator[None]:
    with (
        full_smoke_network_patches(fixture),
        patch(
            "hype_frog.orchestration.enrichment_flow.load_gsc_enrichment_context",
            new=_empty_gsc_context,
        ),
    ):
        yield


def _build_run_setup(*, target_input: str) -> RunSetup:
    return RunSetup(
        target_input=target_input,
        max_urls=3,
        max_psi_urls=2,
        high_value_slugs=[],
        crawl_mode="fast",
        render_wait_ms=1000,
        selector_wait_ms=500,
        workers_preset=2,
        request_delay_preset=0.0,
        full_suite_preset=True,
        hide_advanced_tabs_preset=None,
        previous_audit_path_preset="",
        checkpoint_every_preset=0,
        resume_checkpoint_mode="no",
        check_external_link_status=True,
        check_og_images=False,
        check_content_images=False,
    )


async def _run_real_export(tmp_path: Path, output_name: str) -> str:
    fixture = build_full_smoke_fixture(url_count=5)
    urls = list(fixture.urls[:3])
    crawl_rows = [build_smoke_crawl_payload(fixture, url) for url in urls]
    output_path = tmp_path / output_name
    crawl_result = CrawlExecutionResult(
        output_filename=str(output_path),
        crawl_rows=crawl_rows,
        target_input=fixture.sitemap_url,
        max_psi_urls=2,
        crawl_urls=urls,
        sitemap_meta=fixture.sitemap_meta,
        sitemap_files_meta=fixture.sitemap_files_meta,
        source_label="example.com",
        workers=2,
        request_delay=0.0,
        full_suite=True,
        previous_audit_path="",
        checkpoint_every=0,
        crawl_completed=True,
        check_external_link_status=True,
        check_og_images=False,
        check_content_images=False,
    )
    setup = _build_run_setup(target_input=fixture.sitemap_url)

    with _offline_enrichment_patches(fixture):
        enrichment = await run_enrichment(crawl_result)

    execute_export(
        setup,
        crawl_result,
        enrichment,
        value_or_default_fn=_value_or_default,
        extract_subfolder_fn=_extract_subfolder,
        build_aeo_rows_fn=_build_aeo_rows,
        build_aioseo_rows_fn=_build_aioseo_rows,
    )
    return str(output_path)


@pytest.mark.asyncio
async def test_html_export_flag_produces_real_html_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HF_EXPORT_HTML", "1")
    monkeypatch.delenv("HF_EXPORT_PDF", raising=False)

    output_path = await _run_real_export(tmp_path, "html_export.xlsx")

    html_path = Path(output_path).with_suffix(".html")
    assert html_path.is_file()
    html = html_path.read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>")
    assert "example.com" in html


@pytest.mark.asyncio
async def test_pdf_export_flag_produces_real_pdf_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("reportlab")
    monkeypatch.setenv("HF_EXPORT_PDF", "1")
    monkeypatch.delenv("HF_EXPORT_HTML", raising=False)

    output_path = await _run_real_export(tmp_path, "pdf_export.xlsx")

    pdf_path = Path(executive_summary_pdf_path(output_path))
    assert pdf_path.is_file()
    assert pdf_path.stat().st_size > 0


@pytest.mark.asyncio
async def test_export_flags_disabled_by_default_produce_no_reports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HF_EXPORT_PDF", raising=False)
    monkeypatch.delenv("HF_EXPORT_HTML", raising=False)

    output_path = await _run_real_export(tmp_path, "no_reports.xlsx")

    assert not Path(output_path).with_suffix(".html").exists()
    assert not Path(executive_summary_pdf_path(output_path)).exists()
