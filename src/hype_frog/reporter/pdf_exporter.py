"""Executive summary PDF export for client-facing deliverables (C2)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from hype_frog.core import get_logger

logger = get_logger(__name__)


def executive_summary_pdf_path(workbook_path: str) -> str:
    base = workbook_path.replace(".xlsx", "")
    return f"{base}_executive_summary.pdf"


def _safe_text(value: object, default: str = "—") -> str:
    text = str(value or "").strip()
    return text or default


def _top_issues(fixplan_rows: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    severity_rank = {"Critical": 0, "Warning": 1, "Observation": 2}
    ranked = sorted(
        fixplan_rows,
        key=lambda row: (
            severity_rank.get(str(row.get("Severity") or ""), 9),
            -int(float(row.get("Affected Count") or 0)),
        ),
    )
    return ranked[:limit]


def _aggregate_kpis(
    main_rows: list[dict[str, Any]],
    extra_rows: list[dict[str, Any]],
    summary_rows: list[dict[str, Any]],
) -> dict[str, str]:
    extra_by_url = {
        str(row.get("URL") or "").strip(): row
        for row in extra_rows
        if row.get("URL")
    }
    seo_scores: list[float] = []
    aeo_scores: list[float] = []
    for row in main_rows:
        url = str(row.get("URL") or "").strip()
        extra = extra_by_url.get(url, {})
        try:
            seo_scores.append(float(row.get("SEO Health Score") or extra.get("SEO Health Score") or 0))
        except (TypeError, ValueError):
            pass
        try:
            aeo_scores.append(float(extra.get("AEO Readiness Score") or 0))
        except (TypeError, ValueError):
            pass

    issue_counts = [
        int(float(row.get("Affected URL Count") or 0))
        for row in summary_rows
        if str(row.get("Section") or "") == "Issue Counts"
    ]
    total_issues = sum(issue_counts)
    critical = sum(
        int(float(row.get("Affected URL Count") or 0))
        for row in summary_rows
        if str(row.get("Severity") or "") == "Critical"
    )
    warning = sum(
        int(float(row.get("Affected URL Count") or 0))
        for row in summary_rows
        if str(row.get("Severity") or "") == "Warning"
    )

    avg_seo = sum(seo_scores) / len(seo_scores) if seo_scores else 0.0
    avg_aeo = sum(aeo_scores) / len(aeo_scores) if aeo_scores else 0.0
    return {
        "pages_crawled": str(len(main_rows)),
        "avg_seo_health": f"{avg_seo:.0f}",
        "avg_aeo_readiness": f"{avg_aeo:.0f}",
        "total_issue_instances": str(total_issues),
        "critical_instances": str(critical),
        "warning_instances": str(warning),
    }


def _rag_colour(metric_label: str, value: str) -> tuple[float, float, float]:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return (0.45, 0.45, 0.45)
    if "issue" in metric_label.lower() or "critical" in metric_label.lower():
        if numeric == 0:
            return (0.18, 0.55, 0.34)
        if numeric <= 5:
            return (0.85, 0.65, 0.13)
        return (0.75, 0.22, 0.17)
    if numeric >= 80:
        return (0.18, 0.55, 0.34)
    if numeric >= 60:
        return (0.85, 0.65, 0.13)
    return (0.75, 0.22, 0.17)


def export_executive_summary_pdf(
    *,
    workbook_path: str,
    client_domain: str,
    summary_rows: list[dict[str, Any]],
    fixplan_rows: list[dict[str, Any]],
    main_rows: list[dict[str, Any]],
    extra_rows: list[dict[str, Any]],
    quick_win_rows: list[dict[str, Any]] | None = None,
    client_name: str = "",
    prepared_by: str = "",
    brand_colour: str = "#1a365d",
    logo_path: str | None = None,
) -> str | None:
    """Generate a two-page executive summary PDF alongside the workbook."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        logger.warning("reportlab is not installed; skipping PDF export.")
        return None

    output_path = executive_summary_pdf_path(workbook_path)
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title="Executive Summary",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ExecTitle",
        parent=styles["Heading1"],
        fontSize=20,
        textColor=colors.HexColor(brand_colour),
        spaceAfter=10,
    )
    h2_style = ParagraphStyle(
        "ExecH2",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor(brand_colour),
        spaceBefore=8,
        spaceAfter=6,
    )
    body_style = ParagraphStyle("ExecBody", parent=styles["BodyText"], fontSize=10, leading=14)

    run_date = datetime.now().astimezone().strftime("%d %B %Y")
    story: list[Any] = []
    if logo_path and Path(logo_path).exists():
        try:
            story.append(Image(logo_path, width=4 * cm, height=1.5 * cm))
            story.append(Spacer(1, 0.3 * cm))
        except Exception as exc:
            logger.warning("Could not embed logo in PDF: %s", exc)

    story.append(Paragraph("SEO & AEO Executive Summary", title_style))
    story.append(
        Paragraph(
            f"<b>Client:</b> {_safe_text(client_name or client_domain)}<br/>"
            f"<b>Domain:</b> {_safe_text(client_domain)}<br/>"
            f"<b>Audit date:</b> {run_date}<br/>"
            f"<b>Prepared by:</b> {_safe_text(prepared_by, 'Your agency team')}",
            body_style,
        )
    )
    story.append(Spacer(1, 0.4 * cm))

    kpis = _aggregate_kpis(main_rows, extra_rows, summary_rows)
    kpi_table_data = [["Metric", "Value", "Status"]]
    for label, key in (
        ("Pages crawled", "pages_crawled"),
        ("Average SEO health", "avg_seo_health"),
        ("Average AEO readiness", "avg_aeo_readiness"),
        ("Critical issue instances", "critical_instances"),
        ("Warning issue instances", "warning_instances"),
    ):
        value = kpis[key]
        rag = _rag_colour(label, value)
        kpi_table_data.append([label, value, "●"])

    kpi_table = Table(kpi_table_data, colWidths=[8 * cm, 3 * cm, 1.5 * cm])
    kpi_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(brand_colour)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for row_idx in range(1, len(kpi_table_data)):
        rag = _rag_colour(kpi_table_data[row_idx][0], kpi_table_data[row_idx][1])
        kpi_style.append(("TEXTCOLOR", (2, row_idx), (2, row_idx), colors.Color(*rag)))
    kpi_table.setStyle(TableStyle(kpi_style))
    story.append(Paragraph("Key metrics", h2_style))
    story.append(kpi_table)
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph("Top issues", h2_style))
    for issue in _top_issues(fixplan_rows):
        story.append(
            Paragraph(
                f"• <b>{_safe_text(issue.get('Issue Type'))}</b> "
                f"({_safe_text(issue.get('Severity'))}, "
                f"{int(float(issue.get('Affected Count') or 0))} URLs)",
                body_style,
            )
        )
    if not fixplan_rows:
        story.append(Paragraph("No open issues were detected in this crawl.", body_style))

    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Quick wins", h2_style))
    quick_rows = quick_win_rows or []
    for row in quick_rows[:5]:
        story.append(
            Paragraph(
                f"• {_safe_text(row.get('Issue'))} — "
                f"effort {_safe_text(row.get('Effort (hrs)'), '?')} hrs",
                body_style,
            )
        )
    if not quick_rows:
        story.append(Paragraph("No quick wins identified for this run.", body_style))

    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Recommended sprint focus", h2_style))
    sprint_rows = [
        [
            _safe_text(row.get("Issue Type")),
            _safe_text(row.get("Severity")),
            _safe_text(row.get("Effort")),
            _safe_text(row.get("Owner")),
        ]
        for row in _top_issues(fixplan_rows, limit=6)
    ]
    if sprint_rows:
        sprint_table = Table(
            [["Issue", "Severity", "Effort", "Owner"], *sprint_rows],
            colWidths=[7 * cm, 2.5 * cm, 2 * cm, 3 * cm],
        )
        sprint_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(brand_colour)),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                ]
            )
        )
        story.append(sprint_table)
    else:
        story.append(Paragraph("Maintain current technical and content hygiene.", body_style))

    doc.build(story)
    logger.info("Executive summary PDF saved to %s", output_path)
    return output_path
