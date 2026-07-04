"""Tests for the `--full-smoke-test` gate driver in `diagnostics/full_smoke_test.py`.

Before this file, `tests/core/test_full_smoke_test.py` only exercised
`_validate_full_smoke_rows` (1 of 6 public functions in this module) via a
thin re-export; the real driver (`_apply_full_smoke_env`, `_preflight_phase`,
`run_full_smoke_gate`, `_print_report`) had zero direct coverage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from hype_frog.core.models import CrawlRowPayload, ExtraRowPayload, MainRowPayload
from hype_frog.core.run_config import RunConfig
from hype_frog.diagnostics.full_smoke_test import (
    FullSmokeOptions,
    _apply_full_smoke_env,
    _preflight_phase,
    _validate_full_smoke_rows,
    run_full_smoke_gate,
    run_full_smoke_pytest,
)
from hype_frog.diagnostics.integration_validator import CheckStatus, IntegrationCheck
from hype_frog.diagnostics.quick_test import QuickTestPhaseResult
from hype_frog.orchestration.crawl_runner import CrawlExecutionResult


def _row(url: str, extraction_state: str, status_code: object = 200) -> CrawlRowPayload:
    return CrawlRowPayload(
        main=MainRowPayload.model_validate(
            {"values": {"URL": url, "Extraction State": extraction_state}}
        ),
        extra=ExtraRowPayload.model_validate(
            {"values": {"URL": url, "Status Code": status_code}}
        ),
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


def _run_config(**overrides: Any) -> RunConfig:
    base = dict(
        target_input="https://example.com/sitemap.xml",
        max_urls=None,
        max_psi_urls=None,
        high_value_slugs=[],
        crawl_mode="fast",
        render_wait_ms=1000,
        selector_wait_ms=500,
        workers=1,
        request_delay=0.0,
        full_suite=True,
        previous_audit_path="",
        checkpoint_every=0,
        resume_checkpoint="no",
        check_external_link_status=False,
    )
    base.update(overrides)
    return RunConfig(**base)


# ---------------------------------------------------------------------------
# _apply_full_smoke_env
# ---------------------------------------------------------------------------

def test_apply_full_smoke_env_sets_bfs_depth_from_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("HF_MAX_DEPTH", raising=False)
    monkeypatch.setenv("HF_OUTPUT_FILENAME", str(tmp_path / "preset.xlsx"))
    config = _run_config(bfs_max_depth=3)

    _apply_full_smoke_env(config)

    assert __import__("os").environ["HF_MAX_DEPTH"] == "3"


def test_apply_full_smoke_env_respects_preexisting_output_filename(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    preset_path = str(tmp_path / "already_set.xlsx")
    monkeypatch.setenv("HF_OUTPUT_FILENAME", preset_path)
    config = _run_config(bfs_max_depth=1)

    _apply_full_smoke_env(config)

    assert __import__("os").environ["HF_OUTPUT_FILENAME"] == preset_path


# ---------------------------------------------------------------------------
# _preflight_phase
# ---------------------------------------------------------------------------

def test_preflight_phase_fails_on_any_required_check_failure() -> None:
    checks = [
        IntegrationCheck(name="GSC client_secrets.json", status=CheckStatus.PASS, message="", details={}),
        IntegrationCheck(name="PSI API live probe", status=CheckStatus.FAIL, message="timed out", details={}),
    ]
    result = _preflight_phase(checks)
    assert result.status == "FAIL"
    assert "PSI API live probe" in result.detail


def test_preflight_phase_passes_when_all_required_checks_pass() -> None:
    checks = [
        IntegrationCheck(name="GSC client_secrets.json", status=CheckStatus.PASS, message="", details={}),
        IntegrationCheck(name="PSI API live probe", status=CheckStatus.PASS, message="", details={}),
    ]
    result = _preflight_phase(checks)
    assert result.status == "PASS"


# ---------------------------------------------------------------------------
# _validate_full_smoke_rows
# ---------------------------------------------------------------------------

def test_validate_full_smoke_rows_fails_without_timeout_status() -> None:
    rows = [_row("https://example.com/a", "complete", status_code=200)]
    result = _validate_full_smoke_rows(_crawl_result(rows), expected_sitemap_urls=1)
    assert result.status == "FAIL"
    assert "Timeout" in result.detail


def test_validate_full_smoke_rows_fails_below_expected_url_count() -> None:
    rows = [_row("https://example.com/a", "partial", status_code="Timeout")]
    result = _validate_full_smoke_rows(_crawl_result(rows), expected_sitemap_urls=5)
    assert result.status == "FAIL"
    assert "expected at least 5" in result.detail


def test_validate_full_smoke_rows_passes_with_timeout_and_enough_urls() -> None:
    rows = [
        _row("https://example.com/a", "partial", status_code="Timeout"),
        _row("https://example.com/b", "complete", status_code=200),
    ]
    result = _validate_full_smoke_rows(_crawl_result(rows), expected_sitemap_urls=2)
    assert result.status == "PASS"
    assert "status mix includes Timeout" in result.detail


# ---------------------------------------------------------------------------
# run_full_smoke_pytest (real subprocess, fast target)
# ---------------------------------------------------------------------------

def test_run_full_smoke_pytest_fails_on_nonexistent_target() -> None:
    result = run_full_smoke_pytest(targets=("tests/does_not_exist_at_all.py",))
    assert result.status == "FAIL"


# ---------------------------------------------------------------------------
# run_full_smoke_gate — control-flow contract
# ---------------------------------------------------------------------------

@pytest.fixture
def _passing_full_smoke_collaborators(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> CrawlExecutionResult:
    rows = [_row("https://example.com/a", "partial", status_code="Timeout")]
    crawl_result = _crawl_result(rows, output_filename=str(tmp_path / "gate.xlsx"))

    # run_full_smoke_gate calls build_full_smoke_fixture() itself (not just inside
    # the mocked _run_full_smoke_pipeline) to compute expected_sitemap_urls for the
    # crawl-contracts check; pin it to 1 URL to match the single mocked row above.
    from hype_frog.diagnostics.full_smoke_fixtures import build_full_smoke_fixture

    monkeypatch.setattr(
        "hype_frog.diagnostics.full_smoke_test.build_full_smoke_fixture",
        lambda: build_full_smoke_fixture(url_count=1),
    )
    monkeypatch.setenv("HF_OUTPUT_FILENAME", str(tmp_path / "preset.xlsx"))
    monkeypatch.setattr(
        "hype_frog.diagnostics.full_smoke_test.run_full_smoke_preflight",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "hype_frog.diagnostics.full_smoke_test.run_full_smoke_pytest",
        lambda *a, **k: QuickTestPhaseResult(name="Pytest regression", status="PASS", detail="ok"),
    )
    monkeypatch.setattr(
        "hype_frog.diagnostics.full_smoke_test._run_full_smoke_pipeline",
        AsyncMock(return_value=crawl_result),
    )
    monkeypatch.setattr(
        "hype_frog.diagnostics.full_smoke_test._audit_phase",
        lambda _path: QuickTestPhaseResult(name="Workbook audit", status="PASS", detail="ok"),
    )
    return crawl_result


@pytest.mark.asyncio
async def test_run_full_smoke_gate_returns_zero_when_all_phases_pass(
    _passing_full_smoke_collaborators: CrawlExecutionResult,
) -> None:
    exit_code = await run_full_smoke_gate()
    assert exit_code == 0


@pytest.mark.asyncio
async def test_run_full_smoke_gate_preflight_failure_short_circuits_before_pytest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HF_OUTPUT_FILENAME", str(tmp_path / "preset.xlsx"))
    monkeypatch.setattr(
        "hype_frog.diagnostics.full_smoke_test.run_full_smoke_preflight",
        AsyncMock(
            return_value=[
                IntegrationCheck(
                    name="GSC client_secrets.json",
                    status=CheckStatus.FAIL,
                    message="missing",
                    details={},
                )
            ]
        ),
    )
    pytest_called = False

    def _pytest_spy(*_a: Any, **_k: Any) -> QuickTestPhaseResult:
        nonlocal pytest_called
        pytest_called = True
        return QuickTestPhaseResult(name="Pytest regression", status="PASS", detail="ok")

    monkeypatch.setattr(
        "hype_frog.diagnostics.full_smoke_test.run_full_smoke_pytest", _pytest_spy
    )

    exit_code = await run_full_smoke_gate()
    assert exit_code == 1
    assert pytest_called is False


@pytest.mark.asyncio
async def test_run_full_smoke_gate_pipeline_exception_aborts_with_fail(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HF_OUTPUT_FILENAME", str(tmp_path / "preset.xlsx"))
    monkeypatch.setattr(
        "hype_frog.diagnostics.full_smoke_test.run_full_smoke_preflight",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "hype_frog.diagnostics.full_smoke_test.run_full_smoke_pytest",
        lambda *a, **k: QuickTestPhaseResult(name="Pytest regression", status="PASS", detail="ok"),
    )

    async def _boom(_config: Any) -> CrawlExecutionResult:
        raise RuntimeError("simulated crawl failure")

    monkeypatch.setattr(
        "hype_frog.diagnostics.full_smoke_test._run_full_smoke_pipeline", _boom
    )

    exit_code = await run_full_smoke_gate()
    assert exit_code == 1


@pytest.mark.asyncio
async def test_run_full_smoke_gate_skip_flags_produce_skip_phases(
    _passing_full_smoke_collaborators: CrawlExecutionResult,
) -> None:
    exit_code = await run_full_smoke_gate(
        FullSmokeOptions(skip_preflight=True, skip_pytest=True, skip_workbook_audit=True)
    )
    assert exit_code == 0
