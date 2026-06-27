"""Pre-export integration gate: uncapped sitemap scale, real OAuth/PSI preflight, mocked crawl."""

from __future__ import annotations

import asyncio
import os
import subprocess
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from rich.table import Table

from hype_frog.config import PROJECT_ROOT, load_environment
from hype_frog.core import configure_logging, get_logger
from hype_frog.core.logger import console
from hype_frog.diagnostics.full_smoke_fixtures import (
    build_full_smoke_fixture,
    full_smoke_network_patches,
)
from hype_frog.diagnostics.integration_validator import (
    PSI_DEFAULT_PROBE_URL,
    CheckStatus,
    IntegrationCheck,
    check_gsc_api,
    check_gsc_client_secrets,
    check_gsc_token_file,
    check_psi_api_key_present,
    check_psi_api_live,
    format_validation_report,
)
from hype_frog.diagnostics.quick_test import (
    QuickTestPhaseResult,
    QuickTestReport,
    _audit_phase,
    _crawl_property_url,
    _run_pipeline,
    _validate_crawl_rows,
)
from hype_frog.core.run_config import (
    FULL_SMOKE_SYNTHETIC_URL_COUNT,
    RunConfig,
    full_smoke_run_config,
)
from hype_frog.orchestration.crawl_runner import CrawlExecutionResult

logger = get_logger(__name__)

_DEFAULT_PYTEST_TARGETS: tuple[str, ...] = (
    "tests/orchestration/test_sitemapqa_rows.py",
    "tests/orchestration/test_crawl_runner.py",
    "tests/reporter/test_excel_engine.py",
    "tests/reporter/test_merged_sheet_builders.py",
    "tests/reporter/test_executive_dashboard.py",
    "tests/reporter/test_main_performance_columns.py",
    "tests/crawler/test_extraction_contract.py",
    "tests/crawler/test_psi_engine.py",
    "tests/pipeline/test_psi_assemble.py",
)


@dataclass(frozen=True)
class FullSmokeOptions:
    """CLI-tunable full-smoke gate behaviour."""

    skip_preflight: bool = False
    skip_pytest: bool = False
    skip_workbook_audit: bool = False


def _apply_full_smoke_env(config: RunConfig) -> None:
    if config.bfs_max_depth is not None:
        os.environ.setdefault("HF_MAX_DEPTH", str(config.bfs_max_depth))
    if not os.getenv("HF_OUTPUT_FILENAME", "").strip():
        out_dir = PROJECT_ROOT / "reports" / "full_smoke_test"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        os.environ["HF_OUTPUT_FILENAME"] = str(
            out_dir
            / f"SEO_AEO_Audit_africanmarketingconfederation.org_fullsmoke_{stamp}.xlsx"
        )


async def run_full_smoke_preflight(target_input: str) -> list[IntegrationCheck]:
    """Require PSI key, OAuth token, live PSI probe, and GSC property match."""
    load_environment()
    checks: list[IntegrationCheck] = [
        check_gsc_client_secrets(),
        check_gsc_token_file(),
        check_psi_api_key_present(),
    ]
    token_check = checks[1]
    property_url = _crawl_property_url(target_input)
    if token_check.status != CheckStatus.PASS:
        checks.append(
            IntegrationCheck(
                name="GSC property match (crawl target)",
                status=CheckStatus.FAIL,
                message="OAuth token missing — run `uv run hype-frog --gsc-auth` first.",
                details={"target_url": property_url},
            )
        )
        return checks

    checks.append(check_gsc_api(property_url))
    psi_key_check = checks[2]
    if psi_key_check.status == CheckStatus.PASS:
        # Validate API key with a fast stable URL — not the crawl homepage (can PSI-timeout).
        checks.append(await check_psi_api_live(PSI_DEFAULT_PROBE_URL))
    else:
        checks.append(
            IntegrationCheck(
                name="PSI API live probe",
                status=CheckStatus.FAIL,
                message="PSI_API_KEY missing — full-smoke requires PSI credentials.",
                details={},
            )
        )
    return checks


def _preflight_phase(checks: list[IntegrationCheck]) -> QuickTestPhaseResult:
    required = {
        "GSC client_secrets.json",
        "GSC OAuth token",
        "PSI API key",
        "PSI API live probe",
        "GSC Search Console API",
    }
    for check in checks:
        if check.name in required and check.status == CheckStatus.FAIL:
            return QuickTestPhaseResult(
                name="Preflight",
                status="FAIL",
                detail=f"{check.name}: {check.message}",
            )
    warns = sum(1 for c in checks if c.status == CheckStatus.WARN)
    passes = sum(1 for c in checks if c.status == CheckStatus.PASS)
    return QuickTestPhaseResult(
        name="Preflight",
        status="WARN" if warns else "PASS",
        detail=f"{passes} passed, {warns} warnings (PSI key + OAuth + live probe)",
    )


def run_full_smoke_pytest(
    targets: tuple[str, ...] = _DEFAULT_PYTEST_TARGETS,
) -> QuickTestPhaseResult:
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
        lines = [ln for ln in tail.strip().splitlines() if ln.strip()][-10:]
        detail = "; ".join(lines) if lines else f"exit code {proc.returncode}"
        return QuickTestPhaseResult(
            name="Pytest regression",
            status="FAIL",
            detail=detail[:600],
        )
    summary = (proc.stdout or "").strip().splitlines()[-1] if proc.stdout else "ok"
    return QuickTestPhaseResult(
        name="Pytest regression",
        status="PASS",
        detail=f"{summary} ({elapsed:.1f}s)",
    )


def _validate_full_smoke_rows(
    crawl_result: CrawlExecutionResult,
    *,
    expected_sitemap_urls: int,
) -> QuickTestPhaseResult:
    base = _validate_crawl_rows(crawl_result)
    if base.status == "FAIL":
        return QuickTestPhaseResult(name="Crawl contracts", status="FAIL", detail=base.detail)

    rows = crawl_result.crawl_rows
    status_values = {
        str(row.extra.values.get("Status Code"))
        for row in rows
        if row.extra.values.get("Status Code") is not None
    }
    if "Timeout" not in status_values:
        return QuickTestPhaseResult(
            name="Crawl contracts",
            status="FAIL",
            detail="Fixture must include transport Timeout rows for export guardrails",
        )

    crawled = len(rows)
    min_expected = expected_sitemap_urls
    status: Literal["PASS", "WARN", "FAIL"] = "PASS"
    detail = (
        f"{crawled} URLs (sitemap seeds={expected_sitemap_urls}, no max_urls cap) | "
        f"status mix includes Timeout | {base.detail}"
    )
    if crawled < min_expected:
        status = "FAIL"
        detail += f" — expected at least {min_expected} crawled URLs"
    return QuickTestPhaseResult(name="Crawl contracts", status=status, detail=detail)


def _print_report(report: QuickTestReport) -> None:
    _STATUS_STYLE = {"PASS": "green", "WARN": "yellow", "FAIL": "bold red", "SKIP": "dim"}

    table = Table(
        title="FULL SMOKE TEST SUMMARY",
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


async def _run_full_smoke_pipeline(config: RunConfig) -> CrawlExecutionResult:
    fixture = build_full_smoke_fixture()
    with full_smoke_network_patches(fixture):
        return await _run_pipeline(config)


async def run_full_smoke_gate(options: FullSmokeOptions | None = None) -> int:
    """Execute the full-smoke gate; return process exit code."""
    opts = options or FullSmokeOptions()
    configure_logging()
    load_environment()
    config = full_smoke_run_config()
    _apply_full_smoke_env(config)
    fixture = build_full_smoke_fixture()

    report = QuickTestReport(phases=[])

    if opts.skip_preflight:
        report.phases.append(
            QuickTestPhaseResult(name="Preflight", status="SKIP", detail="skipped by flag")
        )
    else:
        checks = await run_full_smoke_preflight(config.target_input)
        logger.info("%s", format_validation_report(checks))
        report.phases.append(_preflight_phase(checks))
        if report.phases[-1].status == "FAIL":
            _print_report(report)
            return 1

    if opts.skip_pytest:
        report.phases.append(
            QuickTestPhaseResult(
                name="Pytest regression", status="SKIP", detail="skipped by flag"
            )
        )
    else:
        report.phases.append(run_full_smoke_pytest())

    try:
        crawl_result = await _run_full_smoke_pipeline(config)
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

    contract_phase = _validate_full_smoke_rows(
        crawl_result,
        expected_sitemap_urls=fixture.sitemap_url_count,
    )
    report.phases.append(contract_phase)
    report.urls_crawled = len(crawl_result.crawl_rows)
    report.output_filename = crawl_result.output_filename
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
    "FullSmokeOptions",
    "FULL_SMOKE_SYNTHETIC_URL_COUNT",
    "run_full_smoke_gate",
    "run_full_smoke_preflight",
    "run_full_smoke_pytest",
]
