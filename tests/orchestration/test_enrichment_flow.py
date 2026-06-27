"""Unit and integration tests for enrichment orchestration."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

import pytest

from hype_frog.core.models import ExtraRowPayload
from hype_frog.crawler.gsc_engine import GSCEnrichmentContext
from hype_frog.diagnostics.full_smoke_fixtures import (
    FullSmokeFixture,
    build_full_smoke_fixture,
    build_smoke_crawl_payload,
    full_smoke_network_patches,
)
from hype_frog.orchestration.crawl_runner import CrawlExecutionResult
from hype_frog.orchestration.enrichment_flow import (
    EnrichmentResult,
    _extra_status_is_200,
    _merge_gsc_url_inspection_row,
    _url_passes_gsc_inspection_smart_gate,
    normalize_url_key,
    run_enrichment,
)


def _empty_gsc_context(_target: str) -> GSCEnrichmentContext:
    return GSCEnrichmentContext({}, False, None, None)


def _build_crawl_result(
    tmp_path: Path,
    fixture: FullSmokeFixture,
    *,
    url_count: int = 3,
) -> CrawlExecutionResult:
    urls = list(fixture.urls[:url_count])
    crawl_rows = [build_smoke_crawl_payload(fixture, url) for url in urls]
    return CrawlExecutionResult(
        output_filename=str(tmp_path / "enrichment_test.xlsx"),
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


def test_normalize_url_key_strips_trailing_slash() -> None:
    assert normalize_url_key("https://Example.com/page/") == "https://example.com/page"


def test_extra_status_is_200_accepts_int_and_string() -> None:
    assert _extra_status_is_200(200) is True
    assert _extra_status_is_200("200") is True
    assert _extra_status_is_200(404) is False


def test_gsc_inspection_gate_requires_analytics_success() -> None:
    assert (
        _url_passes_gsc_inspection_smart_gate(
            analytics_query_succeeded=False,
            main_values={"Indexability": "Indexable"},
            extra_values={"Status Code": 200},
            url_key="https://example.com/",
            normalized_key="https://example.com/",
            gsc_metrics={},
        )
        is False
    )


def test_gsc_inspection_gate_passes_zero_impression_indexable_url() -> None:
    assert (
        _url_passes_gsc_inspection_smart_gate(
            analytics_query_succeeded=True,
            main_values={"Indexability": "Indexable"},
            extra_values={"Status Code": 200},
            url_key="https://example.com/",
            normalized_key="https://example.com/",
            gsc_metrics={"https://example.com/": {"GSC Impressions": 0.0}},
        )
        is True
    )


def test_gsc_inspection_gate_blocks_urls_with_impressions() -> None:
    assert (
        _url_passes_gsc_inspection_smart_gate(
            analytics_query_succeeded=True,
            main_values={"Indexability": "Indexable"},
            extra_values={"Status Code": 200},
            url_key="https://example.com/",
            normalized_key="https://example.com/",
            gsc_metrics={"https://example.com/": {"GSC Impressions": 12.0}},
        )
        is False
    )


def test_merge_gsc_url_inspection_row_noop_without_fields() -> None:
    row = ExtraRowPayload.model_validate({"URL": "https://example.com/", "Status Code": 200})
    merged = _merge_gsc_url_inspection_row(row, None)
    assert merged.values["URL"] == row.values["URL"]


def test_merge_gsc_url_inspection_row_applies_inspection_fields() -> None:
    row = ExtraRowPayload.model_validate({"URL": "https://example.com/", "Status Code": 200})
    merged = _merge_gsc_url_inspection_row(
        row,
        {"GSC Inspection Verdict": "PASS", "GSC Inspection Coverage State": "Submitted and indexed"},
    )
    assert merged.values.get("GSC Inspection Verdict") == "PASS"


@pytest.mark.asyncio
async def test_run_enrichment_offline_pipeline(tmp_path: Path) -> None:
    fixture = build_full_smoke_fixture(url_count=5)
    crawl_result = _build_crawl_result(tmp_path, fixture, url_count=3)

    with _offline_enrichment_patches(fixture):
        result = await run_enrichment(crawl_result)

    assert isinstance(result, EnrichmentResult)
    assert len(result.typed_main_rows) == 3
    assert len(result.typed_extra_rows) == 3
    assert result.status_by_url
    for extra in result.typed_extra_rows:
        assert extra.values.get("Extraction State") in {"complete", "partial", "skipped"}
        assert extra.values.get("Severity Badge") is not None
        assert extra.values.get("SEO Health Score") is not None
    for main in result.typed_main_rows:
        assert main.values.get("SEO Health Score") is not None
