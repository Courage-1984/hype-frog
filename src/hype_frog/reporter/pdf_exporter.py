"""Executive summary PDF export for client-facing deliverables (C2).

This renderer is a *presentation-only* consumer of the shared
:class:`~hype_frog.reporter.html_report_data.ReportContext`. All aggregation
(KPIs, top issues, sprint plan, quick wins) is computed once in
``build_report_context`` so the PDF and the HTML executive report always show
identical figures. Do not re-aggregate pipeline rows here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from hype_frog.core import get_logger
from hype_frog.config import resolve_project_relative_path

if TYPE_CHECKING:
    from hype_frog.reporter.html_report_data import ReportContext

logger = get_logger(__name__)

DEFAULT_BRAND_COLOUR = "#1e293b"


def executive_summary_pdf_path(workbook_path: str) -> str:
    base = workbook_path.replace(".xlsx", "")
    return f"{base}_executive_summary.pdf"


def _safe_text(value: object, default: str = "—") -> str:
    text = str(value or "").strip()
    return text or default


def _rag_label(kind: str, value: str) -> tuple[str, tuple[float, float, float]]:
    """Return a (word, rgb) status for the KPI table.

    ``kind`` is one of:
    - ``"score"`` — higher is better (e.g. health/readiness percentages).
    - ``"issues"`` — lower is better (issue/page counts).
    - ``"info"`` — descriptive metric with no pass/fail status (renders "—").

    A textual word is used instead of a coloured glyph so the status survives
    PDF text extraction and greyscale printing.
    """
    green = (0.18, 0.55, 0.34)
    amber = (0.85, 0.65, 0.13)
    red = (0.75, 0.22, 0.17)
    grey = (0.45, 0.45, 0.45)
    if kind == "info":
        return ("—", grey)
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return ("—", grey)
    if kind == "issues":
        if numeric == 0:
            return ("Good", green)
        if numeric <= 5:
            return ("Watch", amber)
        return ("Critical", red)
    if kind == "psi":
        if numeric >= 90:
            return ("Good", green)
        if numeric >= 50:
            return ("Watch", amber)
        return ("Critical", red)
    if numeric >= 80:
        return ("Good", green)
    if numeric >= 60:
        return ("Watch", amber)
    return ("Critical", red)


def _format_audit_date(ctx_date: str, override: str) -> str:
    """Resolve the audit date shown in the PDF.

    Prefer the crawl ``run_timestamp`` (so regenerating the PDF later does not
    silently re-date the audit); fall back to today only when nothing parses.
    """
    if override:
        return override
    raw = (ctx_date or "")[:10]
    try:
        return datetime.strptime(raw, "%Y-%m-%d").strftime("%d %B %Y")
    except ValueError:
        return datetime.now(tz=timezone.utc).strftime("%d %B %Y")


def export_executive_summary_pdf(
    *,
    workbook_path: str,
    ctx: ReportContext,
    run_date: str = "",
    logo_path: str | None = None,
) -> str | None:
    """Generate a one-page executive summary PDF from the shared ReportContext."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            Image,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        logger.warning(
            "reportlab is not available; skipping PDF export (%s).",
            exc,
        )
        return None

    brand_colour = ctx.brand_colour or DEFAULT_BRAND_COLOUR
    client_name = ctx.client_name or ctx.domain
    prepared_by = ctx.prepared_by or "Your agency team"
    audit_date = _format_audit_date(ctx.crawl_date, run_date)

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

    story: list[Any] = []

    resolved_logo = resolve_project_relative_path(logo_path or "")
    if resolved_logo and resolved_logo.is_file():
        try:
            story.append(Image(str(resolved_logo), width=4 * cm, height=1.5 * cm))
            story.append(Spacer(1, 0.3 * cm))
        except Exception as exc:
            logger.warning("Could not embed logo in PDF: %s", exc)

    story.append(Paragraph("SEO & AEO Executive Summary", title_style))
    story.append(
        Paragraph(
            f"<b>Client:</b> {_safe_text(client_name)}<br/>"
            f"<b>Domain:</b> {_safe_text(ctx.domain)}<br/>"
            f"<b>Audit date:</b> {audit_date}<br/>"
            f"<b>Prepared by:</b> {_safe_text(prepared_by, 'Your agency team')}",
            body_style,
        )
    )
    story.append(Spacer(1, 0.4 * cm))

    # ── Key metrics (sourced entirely from ctx) ───────────────────────────────
    kpi_specs: list[tuple[str, str, str]] = [
        ("Pages crawled", str(ctx.total_urls), "info"),
        ("Average SEO health", f"{ctx.seo_health_mean:.0f}", "score"),
        ("Average AEO readiness", f"{ctx.aeo_readiness_mean:.0f}", "score"),
        ("Critical pages", str(ctx.critical_url_count), "issues"),
        ("Warning pages", str(ctx.warning_url_count), "issues"),
    ]
    if ctx.psi_mobile_mean > 0:
        kpi_specs.append(("Mobile PSI", f"{ctx.psi_mobile_mean:.0f}", "psi"))
    if ctx.seo_health_projected > ctx.seo_health_mean and ctx.seo_health_projected > 0:
        kpi_specs.append(("Projected SEO health", f"{ctx.seo_health_projected:.0f}", "score"))
    kpi_table_data = [["Metric", "Value", "Status"]]
    status_colours: list[tuple[float, float, float]] = []
    for label, value, kind in kpi_specs:
        status_text, status_rgb = _rag_label(kind, value)
        kpi_table_data.append([label, value, status_text])
        status_colours.append(status_rgb)

    kpi_table = Table(kpi_table_data, colWidths=[8 * cm, 3 * cm, 3 * cm])
    kpi_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(brand_colour)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for row_idx in range(1, len(kpi_table_data)):
        rgb = status_colours[row_idx - 1]
        kpi_style.append(("TEXTCOLOR", (2, row_idx), (2, row_idx), colors.Color(*rgb)))
        kpi_style.append(("FONTNAME", (2, row_idx), (2, row_idx), "Helvetica-Bold"))
    kpi_table.setStyle(TableStyle(kpi_style))
    story.append(Paragraph("Key metrics", h2_style))
    story.append(kpi_table)
    story.append(
        Paragraph(
            '<font size="8" color="#666666">Status key &mdash; scores: '
            "Good \u2265 80, Watch 60&ndash;79, Critical &lt; 60 "
            "(Mobile PSI: Good \u2265 90). "
            "Page counts: Good = 0, Watch \u2264 5, Critical &gt; 5.</font>",
            body_style,
        )
    )
    story.append(Spacer(1, 0.4 * cm))

    # ── Search visibility (shared GSC figures) ────────────────────────────────
    if ctx.gsc_available:
        story.append(Paragraph("Search visibility (Search Console)", h2_style))
        story.append(
            Paragraph(
                f"<b>{ctx.gsc_clicks_total:,}</b> clicks and "
                f"<b>{ctx.gsc_impressions_total:,}</b> impressions over the last 30 days; "
                f"average position <b>{ctx.gsc_avg_position}</b> across "
                f"<b>{ctx.gsc_pages_with_clicks}</b> page(s) with clicks.",
                body_style,
            )
        )
        if ctx.gsc_data_freshness:
            story.append(
                Paragraph(
                    f'<font size="8" color="#666666">{_safe_text(ctx.gsc_data_freshness)}</font>',
                    body_style,
                )
            )
        story.append(Spacer(1, 0.3 * cm))

    # ── Top issues (shared with HTML report) ──────────────────────────────────
    story.append(Paragraph("Top issues", h2_style))
    if ctx.top_issues:
        for issue in ctx.top_issues[:5]:
            story.append(
                Paragraph(
                    f"&bull; <b>{_safe_text(issue.get('name'))}</b> "
                    f"({_safe_text(issue.get('severity'))}, "
                    f"{int(float(issue.get('affected_count') or 0))} pages)",
                    body_style,
                )
            )
    else:
        story.append(Paragraph("No open issues were detected in this crawl.", body_style))

    # ── Quick wins (shared with HTML report) ──────────────────────────────────
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Quick wins", h2_style))
    if ctx.quick_wins:
        for win in ctx.quick_wins[:5]:
            story.append(
                Paragraph(
                    f"&bull; {_safe_text(win.get('name'))} &mdash; "
                    f"effort {float(win.get('effort_hours') or 0):.1f} hrs",
                    body_style,
                )
            )
    else:
        story.append(Paragraph("No quick wins identified for this run.", body_style))

    # ── Sprint & resource plan (identical to HTML report) ─────────────────────
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Sprint & resource plan", h2_style))
    if ctx.sprint_plan:
        sprint_data = [["Sprint", "Issues", "Hours", "Owner"]]
        for sprint in ctx.sprint_plan:
            sprint_data.append(
                [
                    _safe_text(sprint.get("sprint")),
                    str(int(sprint.get("issue_count") or 0)),
                    f"{float(sprint.get('hours') or 0):.0f}h",
                    _safe_text(sprint.get("owner")),
                ]
            )
        sprint_data.append(
            [
                "Total",
                str(sum(int(s.get("issue_count") or 0) for s in ctx.sprint_plan)),
                f"{ctx.total_fix_hours:.0f}h",
                "",
            ]
        )
        sprint_table = Table(sprint_data, colWidths=[6 * cm, 2 * cm, 2 * cm, 4.5 * cm])
        sprint_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(brand_colour)),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e2e8f0")),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ]
            )
        )
        story.append(sprint_table)
    else:
        story.append(Paragraph("Maintain current technical and content hygiene.", body_style))

    doc.build(story)
    logger.info("Executive summary PDF saved to %s", output_path)
    return output_path
