"""Executive summary PDF export (C2).

The PDF is a presentation-only consumer of the shared ``ReportContext``; these
tests build a context and assert the PDF renders from it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hype_frog.reporter.html_report_data import ReportContext
from hype_frog.reporter.pdf_exporter import _rag_label, export_executive_summary_pdf


def _sample_ctx() -> ReportContext:
    ctx = ReportContext()
    ctx.domain = "example.com"
    ctx.client_name = "Example Co"
    ctx.prepared_by = "QA"
    ctx.crawl_date = "2026-06-27 12:24:19"
    ctx.total_urls = 3
    ctx.seo_health_mean = 72.0
    ctx.aeo_readiness_mean = 65.0
    ctx.critical_url_count = 1
    ctx.warning_url_count = 2
    ctx.top_issues = [
        {"name": "Missing Meta Description", "severity": "Warning", "affected_count": 2},
        {"name": "Missing Title", "severity": "Critical", "affected_count": 1},
    ]
    ctx.quick_wins = [
        {"name": "Missing Meta Description", "effort_hours": 4.0, "owner": "Copy Writer"},
    ]
    ctx.sprint_plan = [
        {"sprint": "Immediate (Current Sprint)", "issue_count": 1, "hours": 10.0, "owner": "Dev"},
        {"sprint": "Next Sprint", "issue_count": 2, "hours": 8.0, "owner": "Copy Writer"},
    ]
    ctx.total_fix_hours = 18.0
    return ctx


def _extract_pdf_text(pdf_path: str) -> str:
    from pypdf import PdfReader

    reader = PdfReader(pdf_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def test_export_executive_summary_pdf_writes_file(tmp_path: Path) -> None:
    pytest.importorskip("reportlab")
    workbook = tmp_path / "audit.xlsx"
    workbook.write_bytes(b"")
    pdf_path = export_executive_summary_pdf(
        workbook_path=str(workbook),
        ctx=_sample_ctx(),
    )
    assert pdf_path is not None
    assert Path(pdf_path).exists()
    assert Path(pdf_path).stat().st_size > 0


def test_export_executive_summary_pdf_content_reflects_real_ctx_values(
    tmp_path: Path,
) -> None:
    """Beyond file-exists/non-empty: extract real PDF text and assert the
    actual KPI values, client name, and issue names from ReportContext appear
    in the rendered document — not just that something got written."""
    pytest.importorskip("reportlab")
    workbook = tmp_path / "audit.xlsx"
    workbook.write_bytes(b"")
    pdf_path = export_executive_summary_pdf(
        workbook_path=str(workbook),
        ctx=_sample_ctx(),
    )
    assert pdf_path is not None
    text = _extract_pdf_text(pdf_path)

    assert "example.com" in text
    assert "Example Co" in text
    assert "Missing Meta Description" in text
    assert "Missing Title" in text
    assert "72" in text  # seo_health_mean
    assert "65" in text  # aeo_readiness_mean


def test_export_handles_empty_context(tmp_path: Path) -> None:
    pytest.importorskip("reportlab")
    workbook = tmp_path / "audit.xlsx"
    workbook.write_bytes(b"")
    pdf_path = export_executive_summary_pdf(
        workbook_path=str(workbook),
        ctx=ReportContext(domain="example.com"),
    )
    assert pdf_path is not None
    assert Path(pdf_path).exists()


def test_pdf_export_skips_empty_logo_path(tmp_path: Path) -> None:
    """Empty logo_path must not resolve to cwd ('.') and break ReportLab."""
    pytest.importorskip("reportlab")
    workbook = tmp_path / "audit.xlsx"
    workbook.write_bytes(b"")
    pdf_path = export_executive_summary_pdf(
        workbook_path=str(workbook),
        ctx=_sample_ctx(),
        logo_path="",
    )
    assert pdf_path is not None and Path(pdf_path).exists()


def test_rag_label_semantics() -> None:
    # Descriptive metric never carries a pass/fail status.
    assert _rag_label("info", "83") == ("—", (0.45, 0.45, 0.45))
    # Scores: higher is better.
    assert _rag_label("score", "90")[0] == "Good"
    assert _rag_label("score", "65")[0] == "Watch"
    assert _rag_label("score", "10")[0] == "Critical"
    # Issue/page counts: lower is better.
    assert _rag_label("issues", "0")[0] == "Good"
    assert _rag_label("issues", "3")[0] == "Watch"
    assert _rag_label("issues", "20")[0] == "Critical"
    # Non-numeric degrades gracefully.
    assert _rag_label("score", "n/a") == ("—", (0.45, 0.45, 0.45))
