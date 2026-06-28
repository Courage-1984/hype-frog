"""Comprehensive non-interactive smoke gate for ``--quick-test``."""

from __future__ import annotations

import subprocess
import time
from collections import Counter
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

from rich.table import Table

from hype_frog.config import PROJECT_ROOT, load_environment
from hype_frog.core import configure_logging, get_logger
from hype_frog.core.logger import console
from hype_frog.diagnostics.integration_validator import (
    CheckStatus,
    IntegrationCheck,
    check_gsc_api,
    check_gsc_client_secrets,
    check_gsc_token_file,
    check_psi_api_key_present,
    format_validation_report,
)
from hype_frog.core.run_config import RunConfig, quick_test_run_config
from hype_frog.orchestration.crawl_runner import CrawlExecutionResult, execute_crawl
from hype_frog.orchestration.enrichment_flow import run_enrichment
from hype_frog.orchestration.export_flow import execute_export
from hype_frog.orchestration.run_setup import resolve_run_setup
from hype_frog.reporter.workbook_audit import audit_workbook, count_main_rows

logger = get_logger(__name__)

_EXTRACTION_STATES = frozenset({"complete", "partial", "skipped"})

_DEFAULT_PYTEST_TARGETS: tuple[str, ...] = (
    "tests/reporter/test_toc_sync.py",
    "tests/reporter/test_content_hub_columns.py",
    "tests/reporter/test_excel_engine.py",
    "tests/crawler/test_extraction_contract.py",
    "tests/crawler/test_gsc_auth_paths.py",
    "tests/extractors/test_heading_outline.py",
)


@dataclass(frozen=True)
class QuickTestOptions:
    """CLI-tunable quick-test gate behaviour."""

    skip_preflight: bool = False
    skip_pytest: bool = False
    skip_workbook_audit: bool = False


@dataclass
class QuickTestPhaseResult:
    name: str
    status: Literal["PASS", "WARN", "FAIL", "SKIP"]
    detail: str


@dataclass
class QuickTestReport:
    phases: list[QuickTestPhaseResult]
    output_filename: str | None = None
    urls_crawled: int = 0
    extraction_counts: dict[str, int] | None = None

    @property
    def ok(self) -> bool:
        return not any(p.status == "FAIL" for p in self.phases)


def _crawl_property_url(target_input: str) -> str:
    if target_input.lower().endswith(".xml"):
        parsed = urlparse(target_input)
        return f"{parsed.scheme}://{parsed.netloc}/"
    parsed = urlparse(target_input)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}/"
    return target_input



async def run_quick_test_preflight(target_input: str) -> list[IntegrationCheck]:
    """Fast integration checks relevant to a crawl (no live PSI probe)."""
    load_environment()
    checks: list[IntegrationCheck] = [
        check_gsc_client_secrets(),
        check_gsc_token_file(),
        check_psi_api_key_present(),
    ]
    token_check = checks[1]
    property_url = _crawl_property_url(target_input)
    if token_check.status == CheckStatus.PASS:
        gsc_match = check_gsc_api(property_url)
        match_status = (
            CheckStatus.PASS
            if gsc_match.status == CheckStatus.PASS
            else CheckStatus.WARN
        )
        checks.append(
            IntegrationCheck(
                name="GSC property match (crawl target)",
                status=match_status,
                message=gsc_match.message,
                details={**gsc_match.details, "target_url": property_url},
            )
        )
    else:
        checks.append(
            IntegrationCheck(
                name="GSC property match (crawl target)",
                status=CheckStatus.SKIP,
                message="Skipped — OAuth token not ready (crawl continues without GSC metrics).",
                details={},
            )
        )
    return checks


def _preflight_phase(checks: list[IntegrationCheck]) -> QuickTestPhaseResult:
    hard_fail = any(
        c.status == CheckStatus.FAIL
        for c in checks
        if c.name == "GSC client_secrets.json"
    )
    if hard_fail:
        return QuickTestPhaseResult(
            name="Preflight",
            status="FAIL",
            detail="GSC client_secrets.json missing or invalid",
        )
    warns = sum(1 for c in checks if c.status == CheckStatus.WARN)
    passes = sum(1 for c in checks if c.status == CheckStatus.PASS)
    return QuickTestPhaseResult(
        name="Preflight",
        status="WARN" if warns else "PASS",
        detail=f"{passes} passed, {warns} warnings (see log)",
    )


def run_quick_test_pytest(targets: tuple[str, ...] = _DEFAULT_PYTEST_TARGETS) -> QuickTestPhaseResult:
    """Run a focused pytest subset (subprocess — mirrors developer CLI)."""
    cmd = ["uv", "run", "pytest", *targets, "-q", "--tb=line"]
    started = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    elapsed = time.perf_counter() - started
    if proc.returncode != 0:
        tail = (proc.stdout or "") + (proc.stderr or "")
        lines = [ln for ln in tail.strip().splitlines() if ln.strip()][-8:]
        detail = "; ".join(lines) if lines else f"exit code {proc.returncode}"
        return QuickTestPhaseResult(
            name="Pytest regression",
            status="FAIL",
            detail=detail[:500],
        )
    summary = (proc.stdout or "").strip().splitlines()[-1] if proc.stdout else "ok"
    return QuickTestPhaseResult(
        name="Pytest regression",
        status="PASS",
        detail=f"{summary} ({elapsed:.1f}s)",
    )


def _validate_crawl_rows(crawl_result: CrawlExecutionResult) -> QuickTestPhaseResult:
    rows = crawl_result.crawl_rows
    if not rows:
        return QuickTestPhaseResult(
            name="Crawl contracts",
            status="FAIL",
            detail="Zero URLs crawled",
        )
    counts: Counter[str] = Counter()
    for row in rows:
        state = str(row.main.values.get("Extraction State") or "").strip().lower()
        if state not in _EXTRACTION_STATES:
            return QuickTestPhaseResult(
                name="Crawl contracts",
                status="FAIL",
                detail=f"Invalid Extraction State {state!r} on {row.main.values.get('URL')}",
            )
        counts[state] += 1
    config = quick_test_run_config()
    min_expected = min(3, config.max_urls or 3)
    status: Literal["PASS", "WARN", "FAIL"] = "PASS"
    detail = (
        f"{len(rows)} URLs | "
        f"complete={counts.get('complete', 0)} "
        f"partial={counts.get('partial', 0)} "
        f"skipped={counts.get('skipped', 0)}"
    )
    if len(rows) < min_expected:
        status = "WARN"
        detail += f" (expected at least {min_expected} for sitemap preset)"
    return QuickTestPhaseResult(name="Crawl contracts", status=status, detail=detail)


def _audit_phase(output_path: str) -> QuickTestPhaseResult:
    errors = audit_workbook(output_path, require_full_suite_sheets=True)
    main_rows = count_main_rows(output_path)
    if errors:
        return QuickTestPhaseResult(
            name="Workbook audit",
            status="FAIL",
            detail=f"{len(errors)} issue(s): {errors[0]}",
        )
    return QuickTestPhaseResult(
        name="Workbook audit",
        status="PASS",
        detail=f"PASS — Main rows={main_rows}",
    )


def _print_report(report: QuickTestReport) -> None:
    _STATUS_STYLE = {"PASS": "green", "WARN": "yellow", "FAIL": "bold red", "SKIP": "dim"}

    table = Table(
        title="QUICK TEST SUMMARY",
        title_style="bold",
        show_header=True,
        header_style="bold",
        show_lines=False,
        padding=(0, 1),
    )
    table.add_column("Phase", min_width=22)
    table.add_column("Status", justify="center", width=8)
    table.add_column("Detail")

    for phase in report.phases:
        s = _STATUS_STYLE[phase.status]
        table.add_row(phase.name, f"[{s}]{phase.status}[/{s}]", phase.detail)

    console.print("")
    console.print(table)
    if report.urls_crawled:
        console.print(f"  URLs crawled: {report.urls_crawled}")
    if report.extraction_counts:
        parts = ", ".join(f"{k}={v}" for k, v in sorted(report.extraction_counts.items()))
        console.print(f"  Extraction states: {parts}")
    if report.output_filename:
        console.print(f"  Workbook: {report.output_filename}")
    overall_style = "green" if report.ok else "bold red"
    console.print(f"  [{overall_style}]Overall: {'PASS' if report.ok else 'FAIL'}[/{overall_style}]")
    console.print("")


async def _run_pipeline(config: RunConfig) -> CrawlExecutionResult:
    setup = resolve_run_setup(config)
    crawl_result = await execute_crawl(setup)
    enrichment_result = await run_enrichment(crawl_result)
    from hype_frog.app_orchestrator import (  # local import avoids circular dependency
        _build_aeo_rows,
        _build_aioseo_rows,
        _extract_subfolder,
        _value_or_default,
    )

    execute_export(
        setup,
        crawl_result,
        enrichment_result,
        value_or_default_fn=_value_or_default,
        extract_subfolder_fn=_extract_subfolder,
        build_aeo_rows_fn=_build_aeo_rows,
        build_aioseo_rows_fn=_build_aioseo_rows,
    )
    return crawl_result


async def run_quick_test_gate(options: QuickTestOptions | None = None) -> int:
    """Execute the full quick-test gate; return process exit code."""
    opts = options or QuickTestOptions()
    configure_logging()
    load_environment()
    config = quick_test_run_config()

    report = QuickTestReport(phases=[])

    if opts.skip_preflight:
        report.phases.append(
            QuickTestPhaseResult(name="Preflight", status="SKIP", detail="skipped by flag")
        )
    else:
        checks = await run_quick_test_preflight(config.target_input)
        logger.info("%s", format_validation_report(checks))
        report.phases.append(_preflight_phase(checks))

    if opts.skip_pytest:
        report.phases.append(
            QuickTestPhaseResult(
                name="Pytest regression", status="SKIP", detail="skipped by flag"
            )
        )
    else:
        report.phases.append(run_quick_test_pytest())

    try:
        crawl_result = await _run_pipeline(config)
    except Exception as exc:
        report.phases.append(
            QuickTestPhaseResult(
                name="Pipeline",
                status="FAIL",
                detail=f"{type(exc).__name__}: {exc}",
            )
        )
        _print_report(report)
        return 1

    contract_phase = _validate_crawl_rows(crawl_result)
    report.phases.append(contract_phase)
    report.urls_crawled = len(crawl_result.crawl_rows)
    report.output_filename = crawl_result.output_filename
    if contract_phase.detail:
        counts: Counter[str] = Counter()
        for row in crawl_result.crawl_rows:
            state = str(row.main.values.get("Extraction State") or "").strip().lower()
            counts[state] += 1
        report.extraction_counts = dict(counts)

    report.phases.append(
        QuickTestPhaseResult(
            name="Export",
            status="PASS",
            detail=crawl_result.output_filename,
        )
    )

    if opts.skip_workbook_audit:
        report.phases.append(
            QuickTestPhaseResult(
                name="Workbook audit", status="SKIP", detail="skipped by flag"
            )
        )
    else:
        report.phases.append(_audit_phase(crawl_result.output_filename))

    _print_report(report)
    return 0 if report.ok else 1


__all__ = [
    "QuickTestOptions",
    "QuickTestReport",
    "run_quick_test_gate",
    "run_quick_test_preflight",
    "run_quick_test_pytest",
]
