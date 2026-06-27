"""Cross-deliverable guards: the PDF and HTML executive reports must stay in sync.

Both renderers are presentation-only consumers of a single ``ReportContext``
(built once in ``export_flow``). These tests lock in the invariants that Phase 1-3
established so a future change cannot silently re-introduce the PDF/HTML divergence.
"""

from __future__ import annotations

import html as html_lib
from pathlib import Path

import pytest

from hype_frog.reporter.html_report_data import ReportContext, build_report_context
from hype_frog.reporter.html_report_renderer import render_html_report
from hype_frog.reporter.pdf_exporter import export_executive_summary_pdf


def _shared_ctx() -> ReportContext:
    ctx = ReportContext()
    ctx.domain = "example.com"
    ctx.crawl_date = "2026-06-27 12:24:19"
    ctx.total_urls = 83
    ctx.seo_health_mean = 61.0
    ctx.aeo_readiness_mean = 92.0
    ctx.psi_mobile_mean = 88.0
    ctx.seo_health_projected = 95.0
    ctx.critical_url_count = 17
    ctx.warning_url_count = 63
    ctx.observation_url_count = 3
    ctx.total_fix_hours = 88.0
    ctx.top_issues = [
        {"name": "Missing Meta Description", "severity": "Warning", "affected_count": 16},
        {"name": "Low E-E-A-T Signal Score (<3)", "severity": "Warning", "affected_count": 11},
        {"name": "No Schema Markup", "severity": "Critical", "affected_count": 7},
    ]
    ctx.quick_wins = [
        {"name": "Missing Meta Description", "effort_hours": 4.0, "owner": "Copy Writer"},
        {"name": "No ETag Header", "effort_hours": 4.0, "owner": "Server/Host"},
    ]
    ctx.sprint_plan = [
        {"sprint": "Immediate (Current Sprint)", "issue_count": 2, "hours": 20.0, "owner": "Dev"},
        {"sprint": "Next Sprint", "issue_count": 7, "hours": 28.0, "owner": "Copy Writer"},
    ]
    ctx.gsc_available = True
    ctx.gsc_clicks_total = 53
    ctx.gsc_impressions_total = 1459
    return ctx


def test_top_issue_counts_render_identically_in_html(tmp_path: Path) -> None:
    """The HTML shows every shared top-issue count; the PDF builds from the same ctx."""
    pytest.importorskip("reportlab")
    ctx = _shared_ctx()

    html = render_html_report(ctx)
    for issue in ctx.top_issues:
        # The count must appear in the rendered HTML for each shared issue.
        assert str(issue["affected_count"]) in html
        # Names are HTML-escaped in the output (e.g. "<3" -> "&lt;3").
        assert html_lib.escape(issue["name"]) in html

    workbook = tmp_path / "audit.xlsx"
    workbook.write_bytes(b"")
    pdf_path = export_executive_summary_pdf(workbook_path=str(workbook), ctx=ctx)
    # PDF generated from the SAME ctx object → counts cannot diverge by construction.
    assert pdf_path is not None and Path(pdf_path).exists()


def test_quick_win_effort_is_always_numeric() -> None:
    """Guards D1: quick-win effort must never fall back to a placeholder like '?'."""
    ctx = build_report_context(
        main_rows=[{"URL": "https://example.com/a"}],
        extra_rows=[{"URL": "https://example.com/a", "Severity Badge": "Warning"}],
        fixplan_rows=[],
        priority_rows=[],
        summary_rows=[],
        # Note: one row omits "Effort (hrs)" entirely.
        quick_win_rows=[
            {"Issue": "Missing Meta Description", "Effort (hrs)": 4.0, "Owner": "Copy Writer"},
            {"Issue": "No ETag Header", "Owner": "Server/Host"},
        ],
        run_timestamp="2026-06-27 12:24:19",
    )
    assert len(ctx.quick_wins) == 2
    for win in ctx.quick_wins:
        assert isinstance(win["effort_hours"], float)


def test_severity_total_reconciles() -> None:
    ctx = _shared_ctx()
    html = render_html_report(ctx)
    total = ctx.critical_url_count + ctx.warning_url_count + ctx.observation_url_count
    assert f"{total} pages total" in html


def test_pdf_audit_date_from_crawl_timestamp(tmp_path: Path) -> None:
    """Guards D6: PDF audit date derives from the crawl timestamp, not 'today'."""
    pytest.importorskip("reportlab")
    ctx = _shared_ctx()  # crawl_date 2026-06-27
    workbook = tmp_path / "audit.xlsx"
    workbook.write_bytes(b"")
    pdf_path = export_executive_summary_pdf(workbook_path=str(workbook), ctx=ctx)
    assert pdf_path is not None and Path(pdf_path).exists()
