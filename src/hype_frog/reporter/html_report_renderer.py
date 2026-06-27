"""
Render a ReportContext into a self-contained HTML executive report.
No external dependencies, no I/O — pure string transformation.
"""
from __future__ import annotations

import html as html_lib

from hype_frog.reporter.html_report_data import ReportContext
from hype_frog.reporter.mocha_theme import (
    THEME_NAME,
    html_font_links,
    html_theme_css,
    resolve_accent_colour,
    resolve_brand_colour,
)


def render_html_report(ctx: ReportContext) -> str:
    """Return a complete HTML document string ready for file write."""
    crawl_mode_block = f" ({_esc(ctx.crawl_mode)} mode)" if ctx.crawl_mode else ""
    use_mocha = (ctx.theme or "").strip().lower() == THEME_NAME
    brand_colour = resolve_brand_colour(ctx.brand_colour) if use_mocha else ctx.brand_colour
    accent_colour = resolve_accent_colour(ctx.accent_colour) if use_mocha else ctx.accent_colour
    font_links = html_font_links() if use_mocha else ""
    theme_css = html_theme_css(brand_colour, accent_colour) if use_mocha else ""
    # Replace crawl_mode_block before .format() to avoid KeyError from Python format parser
    template = _TEMPLATE.replace("{crawl_mode_block}", crawl_mode_block)
    return template.format(
        font_links=font_links,
        theme_css=theme_css,
        brand_colour=brand_colour,
        accent_colour=accent_colour,
        logo_block=_logo_block(ctx.logo_base64),
        client_name=_esc(ctx.client_name or ctx.domain),
        domain=_esc(ctx.domain),
        crawl_date=_esc(ctx.crawl_date[:10] if len(ctx.crawl_date) >= 10 else ctx.crawl_date),
        prepared_by_block=_prepared_by_block(ctx.prepared_by),
        total_urls=ctx.total_urls,
        narrative=_esc(ctx.executive_narrative),
        kpi_cards=_render_kpi_cards(ctx),
        severity_bar=_render_severity_bar(ctx),
        status_table=_render_status_table(ctx),
        top_issues_table=_render_top_issues(ctx),
        sprint_table=_render_sprint_table(ctx),
        priority_pages_table=_render_priority_pages(ctx),
        content_readiness_table=_render_content_readiness(ctx),
        quick_wins_table=_render_quick_wins(ctx),
        gsc_section=_render_gsc_section(ctx),
        year=ctx.crawl_date[:4] if len(ctx.crawl_date) >= 4 else "2026",
    )


def _esc(text: str) -> str:
    return html_lib.escape(str(text))


def _logo_block(logo_b64: str) -> str:
    if not logo_b64:
        return ""
    return f'<img src="{logo_b64}" alt="Logo" style="max-height:48px;max-width:200px;margin-bottom:8px;">'


def _prepared_by_block(name: str) -> str:
    if not name:
        return ""
    return f'<div class="prepared-by">Prepared by {_esc(name)}</div>'


def _rag_class(value: float, good: float = 80, warning: float = 50) -> str:
    if value >= good:
        return "good"
    if value >= warning:
        return "warning"
    return "critical"


def _render_kpi_cards(ctx: ReportContext) -> str:
    psi_value = f"{ctx.psi_mobile_mean}" if ctx.psi_mobile_mean > 0 else "N/A"
    psi_cls = _rag_class(ctx.psi_mobile_mean, good=90, warning=50) if ctx.psi_mobile_mean > 0 else "neutral"
    cards = [
        ("SEO Health", f"{ctx.seo_health_mean}%", _rag_class(ctx.seo_health_mean)),
        ("AEO Readiness", f"{ctx.aeo_readiness_mean}%", _rag_class(ctx.aeo_readiness_mean, good=70)),
        ("Mobile PSI", psi_value, psi_cls),
        ("Critical Pages", f"{ctx.critical_url_count}", "critical" if ctx.critical_url_count > 0 else "good"),
        ("Total URLs", f"{ctx.total_urls}", "neutral"),
        ("Fix Hours", f"{ctx.total_fix_hours:.0f}h", "neutral"),
    ]
    if ctx.seo_health_projected > ctx.seo_health_mean and ctx.seo_health_projected > 0:
        cards.append(("Projected Health", f"{ctx.seo_health_projected}%", _rag_class(ctx.seo_health_projected)))
    return "\n".join(
        f'<div class="kpi-card {cls}"><div class="kpi-value">{value}</div><div class="kpi-label">{label}</div></div>'
        for label, value, cls in cards
    )


def _render_severity_bar(ctx: ReportContext) -> str:
    total_pages = ctx.critical_url_count + ctx.warning_url_count + ctx.observation_url_count
    total = max(total_pages, 1)
    segs = []
    for count, css_cls in (
        (ctx.critical_url_count, "critical"),
        (ctx.warning_url_count, "warning"),
        (ctx.observation_url_count, "observation"),
    ):
        if count > 0:  # only render segments that have pages — avoids "0" labels at min-width
            pct = round(count / total * 100, 1)
            segs.append(f'<div class="sev-seg {css_cls}" style="width:{pct}%">{count}</div>')
    return (
        f'<div class="severity-bar">{"".join(segs)}</div>'
        f'<div class="sev-legend">'
        f'<span class="dot critical"></span> Critical ({ctx.critical_url_count}) '
        f'<span class="dot warning"></span> Warning ({ctx.warning_url_count}) '
        f'<span class="dot observation"></span> Observation ({ctx.observation_url_count}) '
        f'&mdash; {total_pages} pages total'
        f'</div>'
        f'<p class="muted">Each page is counted once by its highest-severity issue. '
        f'See &ldquo;Top Issues by Impact&rdquo; below for per-issue page counts.</p>'
    )


def _render_status_table(ctx: ReportContext) -> str:
    total_resolved = (
        ctx.status_200_count
        + ctx.status_3xx_count
        + ctx.status_4xx_count
        + ctx.status_5xx_count
        + ctx.status_timeout_count
    )
    # When no HTTP status was resolved for any row, a table of zeros is misleading
    # (it implies "0 pages returned 200"). Show an explicit not-measured affordance.
    if total_resolved == 0:
        return '<p class="muted">HTTP status codes were not captured for this crawl.</p>'
    rows = [
        ("200 OK", ctx.status_200_count, "good"),
        ("3xx Redirects", ctx.status_3xx_count, "neutral"),
        ("4xx Client Errors", ctx.status_4xx_count, "critical" if ctx.status_4xx_count > 0 else "good"),
        ("5xx Server Errors", ctx.status_5xx_count, "critical" if ctx.status_5xx_count > 0 else "good"),
        ("Timeout", ctx.status_timeout_count, "warning" if ctx.status_timeout_count > 0 else "good"),
    ]
    html_rows = "".join(
        f'<tr class="{cls}"><td>{label}</td><td class="num">{count}</td></tr>'
        for label, count, cls in rows
    )
    return (
        f'<table class="data-table compact">'
        f'<thead><tr><th>Status</th><th>Pages</th></tr></thead>'
        f'<tbody>{html_rows}</tbody></table>'
    )


def _render_top_issues(ctx: ReportContext) -> str:
    if not ctx.top_issues:
        return "<p>No issues detected.</p>"
    rows = []
    for issue in ctx.top_issues:
        sev = str(issue.get("severity") or "").strip()
        sev_cls = sev.lower() if sev in ("Critical", "Warning", "Observation") else "neutral"
        rows.append(
            f'<tr>'
            f'<td><span class="badge {sev_cls}">{_esc(sev)}</span></td>'
            f'<td>{_esc(str(issue.get("name", "")))}</td>'
            f'<td class="num">{issue.get("affected_count", 0)}</td>'
            f'</tr>'
        )
    return (
        f'<table class="data-table">'
        f'<thead><tr><th>Severity</th><th>Issue</th><th>Pages</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )


def _render_sprint_table(ctx: ReportContext) -> str:
    if not ctx.sprint_plan:
        return "<p>No FixPlan available.</p>"
    rows = []
    for sp in ctx.sprint_plan:
        sprint = str(sp.get("sprint") or "")
        cls = "critical" if "Immediate" in sprint else "warning" if "Next" in sprint else "neutral"
        rows.append(
            f'<tr class="{cls}">'
            f'<td>{_esc(sprint)}</td>'
            f'<td class="num">{sp.get("issue_count", 0)}</td>'
            f'<td class="num">{sp.get("hours", 0):.0f}h</td>'
            f'<td>{_esc(str(sp.get("owner", "")))}</td>'
            f'</tr>'
        )
    rows.append(
        f'<tr class="total-row"><td>Total</td>'
        f'<td class="num">{sum(s.get("issue_count", 0) for s in ctx.sprint_plan)}</td>'
        f'<td class="num">{ctx.total_fix_hours:.0f}h</td>'
        f'<td></td></tr>'
    )
    return (
        f'<table class="data-table">'
        f'<thead><tr><th>Sprint</th><th>Issues</th><th>Hours</th><th>Owner</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )


def _render_quick_wins(ctx: ReportContext) -> str:
    if not ctx.quick_wins:
        return '<p class="muted">No quick wins identified for this run.</p>'
    rows = []
    for win in ctx.quick_wins:
        rows.append(
            f'<tr>'
            f'<td>{_esc(str(win.get("name", "")))}</td>'
            f'<td class="num">{float(win.get("effort_hours") or 0):.1f}h</td>'
            f'<td>{_esc(str(win.get("owner", "")))}</td>'
            f'</tr>'
        )
    return (
        f'<table class="data-table">'
        f'<thead><tr><th>Issue</th><th>Effort</th><th>Owner</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )


def _render_priority_pages(ctx: ReportContext) -> str:
    if not ctx.priority_pages:
        return "<p>No priority pages identified.</p>"
    rows = []
    for pg in ctx.priority_pages:
        health_cls = _rag_class(float(pg.get("seo_health") or 0))
        rows.append(
            f'<tr>'
            f'<td class="url-cell">{_esc(str(pg.get("url_slug", "")))}</td>'
            f'<td class="num {health_cls}">{float(pg.get("seo_health") or 0):.0f}%</td>'
            f'<td class="num">{pg.get("gsc_impressions", 0)}</td>'
            f'<td>{_esc(str(pg.get("action", "")))}</td>'
            f'</tr>'
        )
    return (
        f'<table class="data-table">'
        f'<thead><tr><th>Page</th><th>Health</th><th>Impressions</th><th>Why Prioritised</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )


def _render_content_readiness(ctx: ReportContext) -> str:
    if not ctx.content_readiness:
        return ""
    rows = []
    for item in ctx.content_readiness:
        cls = str(item.get("status") or "neutral")
        rows.append(
            f'<tr>'
            f'<td>{_esc(str(item.get("factor", "")))}</td>'
            f'<td class="num {cls}">{float(item.get("percent") or 0):.1f}%</td>'
            f'<td>{_esc(str(item.get("target", "")))}</td>'
            f'</tr>'
        )
    return (
        f'<table class="data-table">'
        f'<thead><tr><th>Factor</th><th>Current</th><th>Target</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )


def _render_gsc_section(ctx: ReportContext) -> str:
    if not ctx.gsc_available:
        return '<p class="muted">Google Search Console data was not available for this crawl.</p>'
    return (
        f'<div class="kpi-row">'
        f'<div class="kpi-card neutral"><div class="kpi-value">{ctx.gsc_clicks_total:,}</div><div class="kpi-label">Clicks (30d)</div></div>'
        f'<div class="kpi-card neutral"><div class="kpi-value">{ctx.gsc_impressions_total:,}</div><div class="kpi-label">Impressions</div></div>'
        f'<div class="kpi-card neutral"><div class="kpi-value">{ctx.gsc_avg_position}</div><div class="kpi-label">Avg Position</div></div>'
        f'<div class="kpi-card neutral"><div class="kpi-value">{ctx.gsc_pages_with_clicks}</div><div class="kpi-label">Pages with Clicks</div></div>'
        f'</div>'
        f'<p class="muted">{_esc(ctx.gsc_data_freshness)}</p>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# SELF-CONTAINED HTML TEMPLATE — all CSS inline, no external deps
# ─────────────────────────────────────────────────────────────────────────────

_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SEO &amp; AEO Audit — {client_name}</title>
{font_links}
<style>
  @page {{ size: A4; margin: 16mm 14mm; }}
  @media print {{
    body {{ font-size: 9pt; }}
    .page-break {{ page-break-before: always; }}
    .no-print {{ display: none; }}
    .kpi-card {{ break-inside: avoid; }}
    table {{ break-inside: avoid; }}
    h2 {{ break-after: avoid; }}
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; line-height: 1.55; color: #1e293b; max-width: 800px; margin: 0 auto; padding: 24px 20px; background: #fff; }}
  h1 {{ font-size: 1.5em; color: {brand_colour}; margin-bottom: 4px; }}
  h2 {{ font-size: 1.15em; margin: 28px 0 10px; padding: 6px 10px; background: {brand_colour}; color: #fff; border-radius: 3px; }}
  h3 {{ font-size: 0.95em; color: {brand_colour}; margin: 16px 0 6px; }}
  p {{ margin-bottom: 10px; font-size: 0.92em; }}

  .header {{ border-bottom: 3px solid {brand_colour}; padding-bottom: 12px; margin-bottom: 16px; }}
  .header .subtitle {{ color: #64748b; font-size: 0.85em; }}
  .prepared-by {{ color: #94a3b8; font-size: 0.8em; margin-top: 4px; }}

  .kpi-row {{ display: flex; gap: 10px; flex-wrap: wrap; margin: 14px 0; }}
  .kpi-card {{ flex: 1 1 120px; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px 8px; text-align: center; min-width: 110px; }}
  .kpi-card.good {{ background: #f0fdf4; border-color: #86efac; }}
  .kpi-card.warning {{ background: #fefce8; border-color: #fde047; }}
  .kpi-card.critical {{ background: #fef2f2; border-color: #fca5a5; }}
  .kpi-card.neutral {{ background: #f8fafc; border-color: #e2e8f0; }}
  .kpi-value {{ font-size: 1.6em; font-weight: 700; color: {brand_colour}; }}
  .kpi-label {{ font-size: 0.75em; color: #64748b; margin-top: 2px; text-transform: uppercase; letter-spacing: 0.5px; }}

  .severity-bar {{ display: flex; border-radius: 4px; overflow: hidden; height: 22px; margin: 8px 0 4px; }}
  .sev-seg {{ display: flex; align-items: center; justify-content: center; font-size: 0.72em; font-weight: 600; color: #fff; min-width: 24px; }}
  .sev-seg.critical {{ background: #ef4444; }}
  .sev-seg.warning {{ background: #f59e0b; }}
  .sev-seg.observation {{ background: #3b82f6; }}
  .sev-legend {{ font-size: 0.75em; color: #64748b; margin-bottom: 12px; }}
  .dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 2px; vertical-align: middle; }}
  .dot.critical {{ background: #ef4444; }}
  .dot.warning {{ background: #f59e0b; }}
  .dot.observation {{ background: #3b82f6; }}

  .data-table {{ width: 100%; border-collapse: collapse; margin: 8px 0 16px; font-size: 0.85em; }}
  .data-table th, .data-table td {{ border: 1px solid #e2e8f0; padding: 6px 8px; text-align: left; }}
  .data-table th {{ background: {brand_colour}; color: #fff; font-weight: 600; font-size: 0.82em; text-transform: uppercase; letter-spacing: 0.3px; }}
  .data-table .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .data-table tr.good td {{ background: #f0fdf4; }}
  .data-table tr.warning td {{ background: #fefce8; }}
  .data-table tr.critical td {{ background: #fef2f2; }}
  .data-table tr.neutral td {{ background: #f8fafc; }}
  .data-table tr.total-row td {{ background: #e2e8f0; font-weight: 700; }}
  .data-table td.good {{ background: #f0fdf4; color: #166534; font-weight: 600; }}
  .data-table td.warning {{ background: #fefce8; color: #854d0e; font-weight: 600; }}
  .data-table td.critical {{ background: #fef2f2; color: #991b1b; font-weight: 600; }}
  .data-table .url-cell {{ font-family: 'SF Mono', 'Cascadia Code', Consolas, monospace; font-size: 0.88em; word-break: break-all; }}
  .data-table.compact {{ max-width: 340px; }}

  .badge {{ display: inline-block; padding: 1px 7px; border-radius: 3px; font-size: 0.78em; font-weight: 600; }}
  .badge.critical {{ background: #fecaca; color: #991b1b; }}
  .badge.warning {{ background: #fef08a; color: #854d0e; }}
  .badge.observation {{ background: #dbeafe; color: #1e40af; }}

  .narrative {{ background: #f8fafc; border-left: 4px solid {accent_colour}; padding: 12px 16px; margin: 12px 0; border-radius: 0 4px 4px 0; font-size: 0.9em; }}
  .muted {{ color: #94a3b8; font-size: 0.8em; font-style: italic; }}

  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  @media (max-width: 600px) {{ .two-col {{ grid-template-columns: 1fr; }} }}

  footer {{ margin-top: 32px; padding-top: 12px; border-top: 1px solid #e2e8f0; font-size: 0.72em; color: #94a3b8; text-align: center; }}
{theme_css}
</style>
</head>
<body>

<div class="header">
  {logo_block}
  <h1>SEO &amp; AEO Audit Report</h1>
  <div class="subtitle">{domain} &mdash; {crawl_date} &mdash; {total_urls} URLs crawled{crawl_mode_block}</div>
  {prepared_by_block}
</div>

<div class="narrative">{narrative}</div>

<h2>Site Health Overview</h2>
<div class="kpi-row">
  {kpi_cards}
</div>

<h3>Pages by Worst Severity</h3>
{severity_bar}

<div class="two-col">
  <div>
    <h3>HTTP Status Codes</h3>
    {status_table}
  </div>
  <div>
    <h3>Google Search Console</h3>
    {gsc_section}
  </div>
</div>

<div class="page-break"></div>
<h2>Top Issues by Impact</h2>
<p class="muted">Counts are pages affected by each individual issue (a page may appear under several issues), distinct from the worst-severity page tally above.</p>
{top_issues_table}

<h2>Sprint &amp; Resource Plan</h2>
{sprint_table}

<h2>Quick Wins</h2>
<p>High-impact, low-effort fixes worth tackling first.</p>
{quick_wins_table}

<div class="page-break"></div>
<h2>Priority Pages</h2>
<p>Top 10 pages ranked by business risk score &mdash; highest-impact pages to fix first.</p>
{priority_pages_table}

<h2>Content Readiness</h2>
{content_readiness_table}

<footer>
  Audit of {domain} &mdash; {crawl_date} &mdash; {total_urls} URLs &mdash; &copy; {year}
</footer>

</body>
</html>'''

