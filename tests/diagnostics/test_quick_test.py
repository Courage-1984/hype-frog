"""Tests for the `--quick-test` gate driver in `diagnostics/quick_test.py`.

Note: `tests/core/test_quick_test.py` is a same-named but unrelated file — it
tests `core/run_config.py::quick_test_run_config`, not anything in
`diagnostics/quick_test.py`. Before this file, the real gate driver
(`run_quick_test_gate`, `_preflight_phase`, `_audit_phase`, `_validate_crawl_rows`,
`run_quick_test_pytest`) had zero test coverage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from openpyxl import Workbook

from hype_frog.core.models import CrawlRowPayload, ExtraRowPayload, MainRowPayload
from hype_frog.diagnostics.integration_validator import CheckStatus, IntegrationCheck
from hype_frog.diagnostics.quick_test import (
    QuickTestOptions,
    QuickTestPhaseResult,
    QuickTestReport,
    _audit_phase,
    _crawl_property_url,
    _preflight_phase,
    _validate_crawl_rows,
    run_quick_test_gate,
    run_quick_test_pytest,
)
from hype_frog.orchestration.crawl_runner import CrawlExecutionResult


def _row(url: str, extraction_state: str) -> CrawlRowPayload:
    return CrawlRowPayload(
        main=MainRowPayload.model_validate(
            {"values": {"URL": url, "Extraction State": extraction_state}}
        ),
        extra=ExtraRowPayload.model_validate({"values": {"URL": url}}),
    )


def _crawl_result(rows: list[CrawlRowPayload], *, output_filename: str = "audit.xlsx") -> CrawlExecutionResult:
    return CrawlExecutionResult(
        output_filename=output_filename,
        crawl_rows=rows,
        target_input="https://example.com/sitemap.xml",
        max_psi_urls=0,
        crawl_urls=[r.main.values["URL"] for r in rows],
        sitemap_meta={},
        sitemap_files_meta={},
        source_label="example.com",
        workers=1,
        request_delay=0.0,
        full_suite=False,
        previous_audit_path="",
        checkpoint_every=0,
        crawl_completed=True,
        check_external_link_status=False,
    )


# ---------------------------------------------------------------------------
# _crawl_property_url
# ---------------------------------------------------------------------------

def test_crawl_property_url_from_sitemap_xml() -> None:
    assert _crawl_property_url("https://example.com/sitemap.xml") == "https://example.com/"


def test_crawl_property_url_from_plain_url() -> None:
    assert _crawl_property_url("https://example.com/some/page/") == "https://example.com/"


def test_crawl_property_url_passthrough_for_bare_string() -> None:
    assert _crawl_property_url("example.com") == "example.com"


# ---------------------------------------------------------------------------
# _preflight_phase
# ---------------------------------------------------------------------------

def test_preflight_phase_fails_hard_on_missing_client_secrets() -> None:
    checks = [
        IntegrationCheck(
            name="GSC client_secrets.json", status=CheckStatus.FAIL, message="missing", details={}
        ),
    ]
    result = _preflight_phase(checks)
    assert result.status == "FAIL"
    assert "client_secrets" in result.detail


def test_preflight_phase_warns_when_any_check_warns() -> None:
    checks = [
        IntegrationCheck(name="GSC OAuth token", status=CheckStatus.WARN, message="", details={}),
        IntegrationCheck(name="PSI API key", status=CheckStatus.PASS, message="", details={}),
    ]
    result = _preflight_phase(checks)
    assert result.status == "WARN"
    assert result.detail == "1 passed, 1 warnings (see log)"


def test_preflight_phase_passes_when_all_checks_pass() -> None:
    checks = [
        IntegrationCheck(name="GSC OAuth token", status=CheckStatus.PASS, message="", details={}),
        IntegrationCheck(name="PSI API key", status=CheckStatus.PASS, message="", details={}),
    ]
    result = _preflight_phase(checks)
    assert result.status == "PASS"
    assert result.detail == "2 passed, 0 warnings (see log)"


# ---------------------------------------------------------------------------
# _validate_crawl_rows
# ---------------------------------------------------------------------------

def test_validate_crawl_rows_fails_on_zero_urls() -> None:
    result = _validate_crawl_rows(_crawl_result([]))
    assert result.status == "FAIL"
    assert result.detail == "Zero URLs crawled"


def test_validate_crawl_rows_fails_on_invalid_extraction_state() -> None:
    rows = [_row("https://example.com/", "bogus-state")]
    result = _validate_crawl_rows(_crawl_result(rows))
    assert result.status == "FAIL"
    assert "Invalid Extraction State" in result.detail


def test_validate_crawl_rows_warns_when_below_sitemap_preset_minimum() -> None:
    rows = [_row("https://example.com/", "complete")]
    result = _validate_crawl_rows(_crawl_result(rows))
    assert result.status == "WARN"
    assert "expected at least" in result.detail


def test_validate_crawl_rows_passes_and_counts_states() -> None:
    rows = [
        _row("https://example.com/a", "complete"),
        _row("https://example.com/b", "complete"),
        _row("https://example.com/c", "partial"),
    ]
    result = _validate_crawl_rows(_crawl_result(rows))
    assert result.status == "PASS"
    assert "complete=2" in result.detail
    assert "partial=1" in result.detail


# ---------------------------------------------------------------------------
# _audit_phase
# ---------------------------------------------------------------------------

def test_audit_phase_fails_when_required_sheets_missing(tmp_path: Path) -> None:
    output_path = tmp_path / "main_only.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Main"
    ws.append(["URL"])
    ws.append(["https://example.com/"])
    wb.save(output_path)

    result = _audit_phase(str(output_path))
    assert result.status == "FAIL"
    assert "issue(s)" in result.detail


def test_audit_phase_passes_on_a_real_full_suite_workbook(tmp_path: Path) -> None:
    from hype_frog.diagnostics.full_smoke_fixtures import (
        build_full_smoke_fixture,
        build_smoke_crawl_payload,
    )
    from hype_frog.orchestration.export_flow import execute_export
    from hype_frog.orchestration.run_setup import RunSetup
    from hype_frog.app_orchestrator import (
        _build_aeo_rows,
        _build_aioseo_rows,
        _extract_subfolder,
        _value_or_default,
    )
    from hype_frog.orchestration.enrichment_flow import EnrichmentResult

    fixture = build_full_smoke_fixture(url_count=2)
    payload = build_smoke_crawl_payload(fixture, fixture.urls[0])
    output_path = tmp_path / "full_suite.xlsx"
    crawl_result = CrawlExecutionResult(
        output_filename=str(output_path),
        crawl_rows=[payload],
        target_input=fixture.sitemap_url,
        max_psi_urls=0,
        crawl_urls=[fixture.urls[0]],
        sitemap_meta=fixture.sitemap_meta,
        sitemap_files_meta=fixture.sitemap_files_meta,
        source_label="example.com",
        workers=1,
        request_delay=0.0,
        full_suite=True,
        previous_audit_path="",
        checkpoint_every=0,
        crawl_completed=True,
        check_external_link_status=False,
    )
    enrichment = EnrichmentResult(
        typed_main_rows=[payload.main],
        typed_extra_rows=[payload.extra],
        status_by_url={},
        sitemap_url_keys=set(),
    )
    setup = RunSetup(
        target_input=fixture.sitemap_url,
        max_urls=1,
        max_psi_urls=0,
        high_value_slugs=[],
        crawl_mode="fast",
        render_wait_ms=1000,
        selector_wait_ms=500,
        workers_preset=1,
        request_delay_preset=0.0,
        full_suite_preset=True,
        hide_advanced_tabs_preset=None,
        previous_audit_path_preset="",
        checkpoint_every_preset=0,
        resume_checkpoint_mode="no",
        check_external_link_status=False,
    )
    execute_export(
        setup,
        crawl_result,
        enrichment,
        value_or_default_fn=_value_or_default,
        extract_subfolder_fn=_extract_subfolder,
        build_aeo_rows_fn=_build_aeo_rows,
        build_aioseo_rows_fn=_build_aioseo_rows,
    )

    result = _audit_phase(str(output_path))
    assert result.status == "PASS"
    assert "Main rows=1" in result.detail


# ---------------------------------------------------------------------------
# run_quick_test_pytest (real subprocess, fast targets)
# ---------------------------------------------------------------------------

def test_run_quick_test_pytest_passes_on_fast_real_target() -> None:
    result = run_quick_test_pytest(targets=("tests/core/test_text_utils.py",))
    assert result.status == "PASS"
    assert "100%" in result.detail


def test_run_quick_test_pytest_fails_on_nonexistent_target() -> None:
    result = run_quick_test_pytest(targets=("tests/does_not_exist_at_all.py",))
    assert result.status == "FAIL"


# ---------------------------------------------------------------------------
# run_quick_test_gate — control-flow contract (collaborators mocked at the
# module boundary; assertions target the real report/exit-code logic, not call
# counts alone).
# ---------------------------------------------------------------------------

@pytest.fixture
def _passing_collaborators(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> CrawlExecutionResult:
    rows = [_row("https://example.com/", "complete")]
    crawl_result = _crawl_result(rows, output_filename=str(tmp_path / "gate.xlsx"))

    monkeypatch.setattr(
        "hype_frog.diagnostics.quick_test.run_quick_test_preflight",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "hype_frog.diagnostics.quick_test.run_quick_test_pytest",
        lambda *a, **k: QuickTestPhaseResult(name="Pytest regression", status="PASS", detail="ok"),
    )
    monkeypatch.setattr(
        "hype_frog.diagnostics.quick_test._run_pipeline",
        AsyncMock(return_value=crawl_result),
    )
    monkeypatch.setattr(
        "hype_frog.diagnostics.quick_test._audit_phase",
        lambda _path: QuickTestPhaseResult(name="Workbook audit", status="PASS", detail="ok"),
    )
    return crawl_result


@pytest.mark.asyncio
async def test_run_quick_test_gate_returns_zero_when_all_phases_pass(
    _passing_collaborators: CrawlExecutionResult,
) -> None:
    exit_code = await run_quick_test_gate()
    assert exit_code == 0


@pytest.mark.asyncio
async def test_run_quick_test_gate_skip_flags_produce_skip_phases(
    _passing_collaborators: CrawlExecutionResult,
) -> None:
    exit_code = await run_quick_test_gate(
        QuickTestOptions(skip_preflight=True, skip_pytest=True, skip_workbook_audit=True)
    )
    assert exit_code == 0


@pytest.mark.asyncio
async def test_run_quick_test_gate_pipeline_exception_aborts_with_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _boom(_config: Any) -> CrawlExecutionResult:
        raise RuntimeError("simulated crawl failure")

    monkeypatch.setattr(
        "hype_frog.diagnostics.quick_test.run_quick_test_preflight",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "hype_frog.diagnostics.quick_test.run_quick_test_pytest",
        lambda *a, **k: QuickTestPhaseResult(name="Pytest regression", status="PASS", detail="ok"),
    )
    monkeypatch.setattr("hype_frog.diagnostics.quick_test._run_pipeline", _boom)

    exit_code = await run_quick_test_gate()
    assert exit_code == 1


@pytest.mark.asyncio
async def test_run_quick_test_gate_pipeline_failure_result_reflected_in_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the pipeline raises, no further phases (e.g. workbook audit) should run."""
    audit_called = False

    def _audit_spy(_path: str) -> QuickTestPhaseResult:
        nonlocal audit_called
        audit_called = True
        return QuickTestPhaseResult(name="Workbook audit", status="PASS", detail="ok")

    async def _boom(_config: Any) -> CrawlExecutionResult:
        raise RuntimeError("simulated crawl failure")

    monkeypatch.setattr(
        "hype_frog.diagnostics.quick_test.run_quick_test_preflight",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "hype_frog.diagnostics.quick_test.run_quick_test_pytest",
        lambda *a, **k: QuickTestPhaseResult(name="Pytest regression", status="PASS", detail="ok"),
    )
    monkeypatch.setattr("hype_frog.diagnostics.quick_test._run_pipeline", _boom)
    monkeypatch.setattr("hype_frog.diagnostics.quick_test._audit_phase", _audit_spy)

    exit_code = await run_quick_test_gate()
    assert exit_code == 1
    assert audit_called is False
