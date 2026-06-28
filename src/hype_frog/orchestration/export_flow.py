"""Historical comparison and workbook export orchestration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from hype_frog.analysis.delta_engine import (
    RunSnapshot,
    delta_summary_path_for_workbook,
    load_run_snapshot,
    save_run_snapshot_json,
)
from hype_frog.core import get_logger
from hype_frog.core.console import log_phase_banner
from hype_frog.core.models import SummaryMetricsPayload
from hype_frog.orchestration.crawl_runner import CrawlExecutionResult
from hype_frog.orchestration.enrichment_flow import EnrichmentResult
from hype_frog.orchestration.export_executive_reports import write_executive_reports
from hype_frog.orchestration.export_registry import (
    ExportRegistryConfig,
    get_finalization_steps,
    get_sheet_sequence,
)
from hype_frog.orchestration.export_workbook import (
    FullSuiteExportResult,
    WorkbookExportContext,
    write_full_suite_workbook,
)
from hype_frog.orchestration.run_setup import RunSetup
from hype_frog.pipeline.export import sanitize_rows
from hype_frog.reporter import adjust_sheet_format, apply_tab_hyperlinks
from hype_frog.reporter.chart_compat import patch_xlsx_app_xml_for_excel_compatibility
from hype_frog.reporter.excel_engine import apply_workbook_export_guardrails, write_dict_rows_sheet
from hype_frog.reporter.sheets.config import COMPETITOR_BENCHMARKS_SHEET
from hype_frog.core.url_normalization import normalize_url_key  # noqa: F401 — re-exported for tests
from hype_frog.rules import get_summary_rules

logger = get_logger(__name__)

_OPTIONAL_FORMAT_SHEETS: frozenset[str] = frozenset({COMPETITOR_BENCHMARKS_SHEET})


@dataclass(frozen=True)
class ExportSummary:
    output_filename: str
    main_rows_written: int
    extra_rows_written: int
    full_suite: bool


def _load_previous_snapshot(previous_audit_path: str) -> RunSnapshot | None:
    previous_audit_exists = bool(previous_audit_path) and os.path.exists(previous_audit_path)
    if previous_audit_exists:
        previous_snapshot = load_run_snapshot(previous_audit_path)
        if previous_snapshot is not None:
            logger.info(
                "Loaded previous run snapshot from %s (%s issues).",
                previous_audit_path,
                len(previous_snapshot.issue_ids),
            )
            return previous_snapshot
        logger.warning(
            "Could not parse previous audit snapshot at %s; delta compare degraded.",
            previous_audit_path,
        )
        return None
    if previous_audit_path:
        logger.warning(
            "Previous audit file not found: %s. Delta compare will mark all current issues as New.",
            previous_audit_path,
        )
    return None


def _finalize_workbook(writer: pd.ExcelWriter, *, full_suite: bool) -> None:
    registry_config = ExportRegistryConfig(full_suite=full_suite)
    logger.info("Applying workbook formatting...")
    for final_step in get_finalization_steps():
        if final_step == "apply_tab_hyperlinks":
            apply_tab_hyperlinks(writer)
        elif final_step == "format_sheets":
            for sname in get_sheet_sequence(registry_config):
                if sname in writer.sheets:
                    adjust_sheet_format(writer, sname)
                elif sname in _OPTIONAL_FORMAT_SHEETS:
                    logger.debug(
                        "Optional sheet not present; skipping formatting: %s",
                        sname,
                    )
                else:
                    logger.warning(
                        "Skipping sheet formatting for missing sheet: %s", sname
                    )
        elif final_step == "apply_workbook_export_guardrails":
            apply_workbook_export_guardrails(writer.book)


def _persist_delta_snapshot(output_filename: str, current_snapshot: RunSnapshot | None) -> None:
    if current_snapshot is None:
        return
    try:
        summary_path = delta_summary_path_for_workbook(output_filename)
        save_run_snapshot_json(summary_path, current_snapshot)
        logger.info("Delta summary saved to %s", summary_path)
    except Exception as exc:
        logger.warning("Could not save delta summary JSON: %s", exc)


def execute_export(
    setup: RunSetup,
    crawl_result: CrawlExecutionResult,
    enrichment: EnrichmentResult,
    *,
    value_or_default_fn: Callable[[object, float], float],
    extract_subfolder_fn: Callable[[str], str],
    build_aeo_rows_fn: Callable[[list[dict[str, object]]], list[dict[str, object]]],
    build_aioseo_rows_fn: Callable[
        [list[dict[str, object]], dict[str, dict[str, object]], dict[str, str]],
        list[dict[str, object]],
    ],
) -> ExportSummary:
    del build_aeo_rows_fn  # reserved for export_registry schema rows; kept for API stability

    output_filename = crawl_result.output_filename
    full_suite = crawl_result.full_suite
    previous_audit_path = crawl_result.previous_audit_path
    high_value_slugs = setup.high_value_slugs

    typed_main_rows = list(enrichment.typed_main_rows)
    typed_extra_rows = list(enrichment.typed_extra_rows)
    main_rows = sanitize_rows([row.values for row in typed_main_rows])
    extra_rows = sanitize_rows([row.values for row in typed_extra_rows])
    status_by_url = dict(enrichment.status_by_url)
    main_by_url = {
        str(row.get("URL") or "").strip(): row for row in main_rows if row.get("URL")
    }
    summary_rules = get_summary_rules()
    previous_snapshot = _load_previous_snapshot(previous_audit_path)

    summary_rows: list[dict[str, Any]] = []
    fixplan_rows: list[dict[str, Any]] = []
    quick_wins_rows: list[dict[str, Any]] = []
    priority_rows: list[dict[str, Any]] = []
    broken_link_impact_rows: list[dict[str, Any]] = []
    run_timestamp = ""
    summary_metrics: SummaryMetricsPayload | None = None
    current_snapshot: RunSnapshot | None = None

    log_phase_banner("EXPORT: Building workbook")
    writer: pd.ExcelWriter | None = None
    try:
        writer = pd.ExcelWriter(output_filename, engine="openpyxl")
        main_cols = list(main_rows[0].keys()) if main_rows else []
        logger.info("Writing Main sheet (%d rows)...", len(main_rows))
        write_dict_rows_sheet(writer, "Main", main_cols, typed_main_rows)
        adjust_sheet_format(writer, "Main")

        if full_suite:
            suite_result: FullSuiteExportResult = write_full_suite_workbook(
                writer,
                WorkbookExportContext(
                    setup=setup,
                    crawl_result=crawl_result,
                    enrichment=enrichment,
                    output_filename=output_filename,
                    main_rows=main_rows,
                    extra_rows=extra_rows,
                    typed_main_rows=typed_main_rows,
                    typed_extra_rows=typed_extra_rows,
                    status_by_url=status_by_url,
                    main_by_url=main_by_url,
                    summary_rules=summary_rules,
                    previous_snapshot=previous_snapshot,
                    high_value_slugs=high_value_slugs,
                    value_or_default_fn=value_or_default_fn,
                    extract_subfolder_fn=extract_subfolder_fn,
                    build_aioseo_rows_fn=build_aioseo_rows_fn,
                ),
            )
            summary_rows = suite_result.summary_rows
            fixplan_rows = suite_result.fixplan_rows
            quick_wins_rows = suite_result.quick_wins_rows
            priority_rows = suite_result.priority_rows
            broken_link_impact_rows = suite_result.broken_link_impact_rows
            run_timestamp = suite_result.run_timestamp
            summary_metrics = suite_result.summary_metrics
            current_snapshot = suite_result.current_snapshot

        _finalize_workbook(writer, full_suite=full_suite)
        logger.info("Audit complete! Report saved to %s", output_filename)
        _persist_delta_snapshot(output_filename, current_snapshot)
    finally:
        if writer is not None:
            writer.close()

    patch_xlsx_app_xml_for_excel_compatibility(output_filename)
    write_executive_reports(
        setup=setup,
        crawl_result=crawl_result,
        output_filename=output_filename,
        main_rows=main_rows,
        extra_rows=extra_rows,
        summary_rows=summary_rows,
        fixplan_rows=fixplan_rows,
        priority_rows=priority_rows,
        broken_link_impact_rows=broken_link_impact_rows,
        quick_wins_rows=quick_wins_rows,
        run_timestamp=run_timestamp,
        summary_metrics=summary_metrics,
    )

    return ExportSummary(
        output_filename=output_filename,
        main_rows_written=len(main_rows),
        extra_rows_written=len(extra_rows),
        full_suite=full_suite,
    )
