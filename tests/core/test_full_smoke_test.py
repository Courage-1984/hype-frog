"""Full-smoke preset, fixtures, and offline pipeline gate."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from hype_frog.core.full_smoke_fixtures import (
    build_full_smoke_fixture,
    build_smoke_crawl_payload,
)
from hype_frog.core.full_smoke_test import _validate_full_smoke_rows
from hype_frog.core.run_config import (
    FULL_SMOKE_SYNTHETIC_URL_COUNT,
    full_smoke_run_config,
)
from hype_frog.orchestration.crawl_runner import CrawlExecutionResult


def test_full_smoke_config_has_no_url_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PSI_API_KEY", "test-key")
    config = full_smoke_run_config()
    assert config.max_urls is None
    assert config.max_psi_urls is None
    assert config.full_suite is True
    assert config.target_input.lower().endswith(".xml")


def test_full_smoke_fixture_includes_timeout_rows() -> None:
    fixture = build_full_smoke_fixture(url_count=FULL_SMOKE_SYNTHETIC_URL_COUNT)
    assert fixture.sitemap_url_count == FULL_SMOKE_SYNTHETIC_URL_COUNT
    statuses = {
        build_smoke_crawl_payload(fixture, url).extra.values.get("Status Code")
        for url in fixture.urls
    }
    assert "Timeout" in statuses


def test_validate_full_smoke_rows_requires_timeout_mix() -> None:
    fixture = build_full_smoke_fixture(url_count=20)
    rows = [build_smoke_crawl_payload(fixture, url) for url in fixture.urls]
    crawl_result = CrawlExecutionResult(
        output_filename="out.xlsx",
        crawl_rows=rows,
        target_input=fixture.sitemap_url,
        max_psi_urls=None,
        crawl_urls=list(fixture.urls),
        sitemap_meta=fixture.sitemap_meta,
        sitemap_files_meta=fixture.sitemap_files_meta,
        source_label="example.com",
        workers=4,
        request_delay=0.0,
        full_suite=True,
        previous_audit_path="",
        checkpoint_every=0,
        crawl_completed=True,
        check_external_link_status=True,
        check_og_images=True,
    )
    phase = _validate_full_smoke_rows(crawl_result, expected_sitemap_urls=20)
    assert phase.status == "PASS"


@pytest.mark.asyncio
async def test_full_smoke_pipeline_export_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hype_frog.core.full_smoke_test import _run_full_smoke_pipeline
    from hype_frog.core.run_config import full_smoke_run_config

    monkeypatch.setenv("PSI_API_KEY", "test-key")
    monkeypatch.setenv(
        "HF_OUTPUT_FILENAME",
        str(tmp_path / "full_smoke_offline.xlsx"),
    )
    config = full_smoke_run_config()
    crawl_result = await _run_full_smoke_pipeline(config)
    assert Path(crawl_result.output_filename).is_file()
    assert len(crawl_result.crawl_rows) >= FULL_SMOKE_SYNTHETIC_URL_COUNT
    assert any(
        row.extra.values.get("Status Code") == "Timeout" for row in crawl_result.crawl_rows
    )
