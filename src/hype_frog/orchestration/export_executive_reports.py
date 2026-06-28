"""Executive PDF/HTML report generation after workbook export."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hype_frog.config import resolve_project_relative_path
from hype_frog.core import get_logger
from hype_frog.core.env_vars import (
    get_hf_export_html,
    get_hf_export_pdf,
    get_hf_pdf_brand_colour,
    get_hf_pdf_client_name,
    get_hf_pdf_logo_path,
    get_hf_pdf_prepared_by,
    get_hf_report_accent_colour,
    get_hf_report_accent_colour_override,
    get_hf_report_brand_colour,
    get_hf_report_client_name,
    get_hf_report_logo_path,
    get_hf_report_prepared_by,
    get_hf_report_theme,
)
from hype_frog.core.models import SummaryMetricsPayload
from hype_frog.orchestration.crawl_runner import CrawlExecutionResult
from hype_frog.orchestration.run_setup import RunSetup
from hype_frog.reporter.mocha_theme import (
    THEME_NAME,
    resolve_accent_colour,
    resolve_brand_colour,
)
from hype_frog.reporter.pdf_exporter import export_executive_summary_pdf

logger = get_logger(__name__)


def write_executive_reports(
    *,
    setup: RunSetup,
    crawl_result: CrawlExecutionResult,
    output_filename: str,
    main_rows: list[dict[str, Any]],
    extra_rows: list[dict[str, Any]],
    summary_rows: list[dict[str, Any]],
    fixplan_rows: list[dict[str, Any]],
    priority_rows: list[dict[str, Any]],
    broken_link_impact_rows: list[dict[str, Any]],
    quick_wins_rows: list[dict[str, Any]],
    run_timestamp: str,
    summary_metrics: SummaryMetricsPayload | None,
) -> None:
    """Write optional PDF and HTML executive reports (non-fatal on failure)."""
    export_pdf = setup.export_pdf or get_hf_export_pdf()
    export_html = get_hf_export_html()
    if not export_pdf and not export_html:
        return

    from hype_frog.reporter.html_report_data import build_report_context
    from hype_frog.reporter.html_report_writer import _load_logo_base64

    shared_brand_colour = get_hf_report_brand_colour() or get_hf_pdf_brand_colour()
    report_theme = get_hf_report_theme()
    if report_theme == THEME_NAME:
        shared_brand_colour = resolve_brand_colour(shared_brand_colour or None)
        shared_accent_colour = resolve_accent_colour(
            get_hf_report_accent_colour_override() or None
        )
    else:
        shared_brand_colour = shared_brand_colour or "#1e293b"
        shared_accent_colour = get_hf_report_accent_colour()
    shared_prepared_by = get_hf_report_prepared_by() or get_hf_pdf_prepared_by()
    shared_client_name = get_hf_report_client_name() or get_hf_pdf_client_name()

    report_ctx = None
    try:
        report_ctx = build_report_context(
            main_rows=main_rows,
            extra_rows=extra_rows,
            fixplan_rows=fixplan_rows,
            priority_rows=priority_rows,
            summary_rows=summary_rows,
            broken_link_impact_rows=broken_link_impact_rows,
            quick_win_rows=quick_wins_rows,
            run_timestamp=run_timestamp,
            summary_metrics=summary_metrics,
            domain=crawl_result.source_label,
            prepared_by=shared_prepared_by,
            client_name=shared_client_name,
            logo_base64=_load_logo_base64(),
            brand_colour=shared_brand_colour,
            accent_colour=shared_accent_colour,
            theme=report_theme,
        )
    except Exception as exc:
        logger.warning("Could not build executive report context (non-fatal): %s", exc)

    if export_pdf and report_ctx is not None:
        try:
            raw_logo = get_hf_pdf_logo_path() or get_hf_report_logo_path()
            resolved_logo = (
                str(resolve_project_relative_path(raw_logo)) if raw_logo else None
            )
            export_executive_summary_pdf(
                workbook_path=output_filename,
                ctx=report_ctx,
                run_date="",
                logo_path=resolved_logo,
            )
        except Exception as exc:
            logger.warning("Could not export executive summary PDF: %s", exc)

    if export_html and report_ctx is not None:
        try:
            from hype_frog.reporter.html_report_writer import write_html_report as _write_html

            _html_path = Path(output_filename).with_suffix(".html")
            _write_html(report_ctx, _html_path)
        except Exception as exc:
            logger.warning("HTML report generation failed (non-fatal): %s", exc)
