# Hype Frog — Auto-Generated HTML Executive Report
## Cursor IDE Agent Instructions — LI-HF-HTMLRPT-P0 | 27 June 2026

---

## WHAT THIS IS

A self-contained, white-label HTML executive report generated alongside every xlsx audit. One file, zero external dependencies, printable to PDF from any browser, shareable by URL if hosted. This is the deliverable that goes to stakeholders who never open spreadsheets.

---

## CRITICAL RULES

1. **No Hype Frog branding in the output.** The HTML is white-label. The tool name, GitHub URL, and internal terminology must not appear in the rendered report. The "Prepared by" field and logo are configurable — default to blank.
2. **Self-contained HTML.** All CSS inline in a `<style>` block. No external stylesheets, no CDN links, no JavaScript dependencies. The file must render identically when opened from disk or served over HTTP.
3. **Print-safe.** CSS `@media print` rules must produce a clean 4–6 page PDF from any browser's Print → Save as PDF. Page breaks must be explicit between sections. No cut-off tables, no orphan headings.
4. **Data-driven.** Every number in the report comes from the same enriched row data that builds the xlsx. No hardcoded values. The report must be accurate for any site crawled, not just AMC.
5. **Respect codebase governance.** The HTML reporter is a new module under `src/hype_frog/reporter/`. It reads enriched data as read-only (per `.cursorrules` Rule 3). It uses `core/` logging (per `architecture.mdc`). It follows the uv toolchain. British English throughout.
6. **Run `uv run pytest` after implementation.** Write at least one unit test.

---

## STEP 0 — Context extraction (before writing any code)

```bash
# 1. How does the export pipeline currently work?
grep -n "def execute_export\|def run_export\|html\|HTML" src/hype_frog/orchestration/export_flow.py | head -20

# 2. What data is available at export time?
grep -n "main_rows\|extra_rows\|summary_rules\|fixplan\|priority\|link_inventory\|enriched" src/hype_frog/orchestration/export_flow.py | head -30

# 3. How is the output filename/path determined?
grep -n "output_filename\|output_path\|HF_OUTPUT" src/hype_frog/orchestration/export_flow.py | head -10

# 4. Where are Audit Run Details assembled?
grep -rn "Audit Run Details\|audit_run_details\|run_timestamp\|Run Timestamp" src/hype_frog/ --include="*.py" | head -15

# 5. Where are summary stats (severity counts, status code counts) computed?
grep -rn "severity_counts\|status_code_counts\|build_summary\|Summary" src/hype_frog/reporter/ --include="*.py" | head -15

# 6. Where are Priority URLs assembled?
grep -rn "build_priority\|Priority URLs\|priority_urls" src/hype_frog/reporter/ --include="*.py" | head -10

# 7. Where are FixPlan rows assembled?
grep -rn "build_fixplan_rows" src/hype_frog/reporter/ --include="*.py" | head -5

# 8. Where is the AEO Readiness Score calculated?
grep -rn "AEO Readiness Score\|aeo_readiness" src/hype_frog/ --include="*.py" | head -15

# 9. Content readiness percentages (Good H1, Meta desc present, etc.)
grep -rn "Good H1\|Meta description\|Answer paragraphs\|Schema present\|Content readiness" src/hype_frog/reporter/ --include="*.py" | head -15

# 10. How is the Executive Dashboard currently assembled?
grep -rn "executive_dashboard\|Executive Dashboard\|health_comparison\|chart.source" src/hype_frog/reporter/ --include="*.py" | head -15

# 11. Check .env for any existing report config variables
grep -rn "REPORT\|BRAND\|LOGO\|CLIENT\|PREPARED_BY" .env.example 2>/dev/null || echo "No .env.example found"

# 12. Where does the CLI entrypoint live?
grep -n "def run\|def main\|argparse\|click\|typer" src/hype_frog/main.py | head -10
```

Document all findings in `AUDIT_FIX_LOG.md` under `## HTML Report — Context Map`.

---

## PART 1 — Report Data Collector

### 1A — New module: `src/hype_frog/reporter/html_report_data.py`

This module collects and aggregates all data needed for the HTML report from the enriched row data. It is a **read-only consumer** of the enriched data — it must not mutate any row dictionaries.

```python
"""
Aggregate enriched crawl data into a flat report context dict
for the HTML executive report renderer.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime


@dataclass
class ReportContext:
    """All data needed to render the HTML executive report."""

    # ── IDENTITY ─────────────────────────────────────────────────────────────
    domain: str = ""
    crawl_date: str = ""
    crawl_duration_minutes: float = 0.0
    total_urls: int = 0
    crawl_mode: str = ""

    # ── BRANDING (white-label) ───────────────────────────────────────────────
    prepared_by: str = ""
    client_name: str = ""
    logo_base64: str = ""          # base64-encoded image data URI, or ""
    brand_colour: str = "#1e293b"  # dark navy default — used for headers
    accent_colour: str = "#2563eb" # blue default — used for links/accents

    # ── KPIs ─────────────────────────────────────────────────────────────────
    seo_health_mean: float = 0.0
    seo_health_projected: float = 0.0
    aeo_readiness_mean: float = 0.0
    psi_mobile_mean: float = 0.0
    psi_desktop_mean: float = 0.0
    critical_url_count: int = 0
    warning_url_count: int = 0
    observation_url_count: int = 0

    # ── STATUS CODES ─────────────────────────────────────────────────────────
    status_200_count: int = 0
    status_3xx_count: int = 0
    status_4xx_count: int = 0
    status_5xx_count: int = 0
    status_timeout_count: int = 0

    # ── GSC ───────────────────────────────────────────────────────────────────
    gsc_available: bool = False
    gsc_clicks_total: int = 0
    gsc_impressions_total: int = 0
    gsc_avg_position: float = 0.0
    gsc_pages_with_clicks: int = 0
    gsc_data_freshness: str = ""

    # ── TOP ISSUES (list of dicts) ───────────────────────────────────────────
    top_issues: list[dict[str, Any]] = field(default_factory=list)
    # Each: {"name": str, "severity": str, "affected_count": int, "scope": str}

    # ── SPRINT PLAN (list of dicts) ──────────────────────────────────────────
    sprint_plan: list[dict[str, Any]] = field(default_factory=list)
    # Each: {"sprint": str, "issue_count": int, "hours": float, "owner": str, "priority": str}
    total_fix_hours: float = 0.0

    # ── PRIORITY PAGES (list of dicts, top 10) ───────────────────────────────
    priority_pages: list[dict[str, Any]] = field(default_factory=list)
    # Each: {"url_slug": str, "seo_health": float, "gsc_clicks": int, "severity": str, "action": str}

    # ── CONTENT READINESS (list of dicts) ────────────────────────────────────
    content_readiness: list[dict[str, Any]] = field(default_factory=list)
    # Each: {"factor": str, "percent": float, "status": str, "target": str}

    # ── AEO BREAKDOWN (list of dicts) ────────────────────────────────────────
    aeo_breakdown: list[dict[str, Any]] = field(default_factory=list)
    # Each: {"factor": str, "current": str, "target": str, "gap": str}

    # ── BROKEN LINK IMPACT (list of dicts, top 5) ────────────────────────────
    broken_link_impact: list[dict[str, Any]] = field(default_factory=list)
    # Each: {"broken_url_slug": str, "inbound_count": int, "source_clicks": int, "status": int}

    # ── NARRATIVE ────────────────────────────────────────────────────────────
    executive_narrative: str = ""


def build_report_context(
    main_rows: list[dict[str, Any]],
    extra_rows: list[dict[str, Any]],
    fixplan_rows: list[dict[str, Any]],
    priority_rows: list[dict[str, Any]],
    audit_run_details: dict[str, Any],
    content_readiness_rows: list[dict[str, Any]],
    summary_rows: list[dict[str, Any]],
    broken_link_impact_rows: list[dict[str, Any]] | None = None,
    domain: str = "",
    prepared_by: str = "",
    client_name: str = "",
    logo_base64: str = "",
    brand_colour: str = "#1e293b",
    accent_colour: str = "#2563eb",
) -> ReportContext:
    """
    Build the ReportContext from enriched crawl data.

    IMPORTANT: Read the actual parameter names from the export pipeline
    (Step 0 investigation). The parameter names above are indicative —
    the actual data structures may be dicts, Pydantic models, or lists
    of dicts depending on the pipeline stage. Adapt accordingly.
    """
    ctx = ReportContext()

    # ── IDENTITY ─────────────────────────────────────────────────────────────
    ctx.domain = domain or _extract_domain(main_rows)
    ctx.crawl_date = str(audit_run_details.get("Run Timestamp", ""))
    duration_s = float(audit_run_details.get("Duration (s)", 0) or 0)
    ctx.crawl_duration_minutes = round(duration_s / 60, 1)
    ctx.total_urls = int(audit_run_details.get("Total URLs", len(main_rows)))
    ctx.crawl_mode = str(audit_run_details.get("Crawl Mode", ""))

    # ── BRANDING ─────────────────────────────────────────────────────────────
    ctx.prepared_by = prepared_by
    ctx.client_name = client_name or ctx.domain
    ctx.logo_base64 = logo_base64
    ctx.brand_colour = brand_colour
    ctx.accent_colour = accent_colour

    # ── KPIs ─────────────────────────────────────────────────────────────────
    health_scores = [float(r.get("SEO Health Score", 0) or 0) for r in main_rows]
    ctx.seo_health_mean = round(sum(health_scores) / max(len(health_scores), 1), 1)

    severity_counts = _count_values(main_rows, "Severity Badge")
    ctx.critical_url_count = severity_counts.get("Critical", 0)
    ctx.warning_url_count = severity_counts.get("Warning", 0)
    ctx.observation_url_count = severity_counts.get("Observation", 0)

    # AEO — check extra_rows or content_readiness_rows for the score
    aeo_scores = [float(r.get("AEO Readiness Score", 0) or 0) for r in extra_rows if r.get("AEO Readiness Score") is not None]
    ctx.aeo_readiness_mean = round(sum(aeo_scores) / max(len(aeo_scores), 1), 1) if aeo_scores else 0.0

    # PSI
    mobile_psi = [float(r.get("Mobile PSI Score", 0) or 0) for r in main_rows if r.get("Mobile PSI Score")]
    ctx.psi_mobile_mean = round(sum(mobile_psi) / max(len(mobile_psi), 1), 1) if mobile_psi else 0.0
    desktop_psi = [float(r.get("Desktop PSI Score", 0) or 0) for r in main_rows if r.get("Desktop PSI Score")]
    ctx.psi_desktop_mean = round(sum(desktop_psi) / max(len(desktop_psi), 1), 1) if desktop_psi else 0.0

    # ── STATUS CODES ─────────────────────────────────────────────────────────
    for row in main_rows:
        sc = row.get("Status Code")
        if sc == 200: ctx.status_200_count += 1
        elif isinstance(sc, int) and 300 <= sc < 400: ctx.status_3xx_count += 1
        elif isinstance(sc, int) and 400 <= sc < 500: ctx.status_4xx_count += 1
        elif isinstance(sc, int) and sc >= 500: ctx.status_5xx_count += 1
        elif str(sc).lower() == "timeout": ctx.status_timeout_count += 1

    # ── GSC ───────────────────────────────────────────────────────────────────
    clicks_list = [float(r.get("GSC Clicks") or 0) for r in main_rows if r.get("GSC Clicks") is not None]
    ctx.gsc_clicks_total = int(sum(clicks_list))
    ctx.gsc_available = ctx.gsc_clicks_total > 0 or any(r.get("GSC Coverage Note") for r in main_rows)
    imp_list = [float(r.get("GSC Impressions") or 0) for r in main_rows if r.get("GSC Impressions") is not None]
    ctx.gsc_impressions_total = int(sum(imp_list))
    pos_list = [float(r.get("GSC Avg Position") or 0) for r in main_rows if r.get("GSC Avg Position") and float(r.get("GSC Avg Position") or 0) > 0]
    ctx.gsc_avg_position = round(sum(pos_list) / max(len(pos_list), 1), 1) if pos_list else 0.0
    ctx.gsc_pages_with_clicks = sum(1 for r in main_rows if (r.get("GSC Clicks") or 0) > 0)
    ctx.gsc_data_freshness = str(audit_run_details.get("GSC Data Freshness", ""))

    # ── TOP ISSUES ───────────────────────────────────────────────────────────
    issue_counts: dict[str, dict] = {}
    for row in summary_rows:
        name = str(row.get("Issue Name", row.get("Issue", "")))
        severity = str(row.get("Severity", ""))
        count = int(row.get("Affected URL Count", row.get("Affected Count", 0)) or 0)
        if name and count > 0:
            issue_counts[name] = {"name": name, "severity": severity, "affected_count": count}
    ctx.top_issues = sorted(issue_counts.values(), key=lambda x: x["affected_count"], reverse=True)[:10]

    # ── SPRINT PLAN ──────────────────────────────────────────────────────────
    # Read from Step 0 investigation: what is the exact column name for sprint?
    sprint_groups: dict[str, dict] = {}
    for row in fixplan_rows:
        sprint = str(row.get("Aging/Priority", "Backlog"))  # VERIFY column name
        hours = float(row.get("Est. Hours", 0) or 0)
        owner = str(row.get("Owner", ""))

        if sprint not in sprint_groups:
            sprint_groups[sprint] = {"sprint": sprint, "issue_count": 0, "hours": 0.0, "owners": set(), "priority": sprint}
        sprint_groups[sprint]["issue_count"] += 1
        sprint_groups[sprint]["hours"] += hours
        sprint_groups[sprint]["owners"].add(owner)

    # Sort by priority order
    priority_order = {"Immediate (Current Sprint)": 0, "Next Sprint": 1, "Backlog": 2}
    sorted_sprints = sorted(sprint_groups.values(), key=lambda x: priority_order.get(x["sprint"], 99))
    for sp in sorted_sprints:
        sp["owner"] = ", ".join(sorted(sp.pop("owners")))  # convert set to string
    ctx.sprint_plan = sorted_sprints
    ctx.total_fix_hours = sum(sp["hours"] for sp in sorted_sprints)

    # ── PRIORITY PAGES ───────────────────────────────────────────────────────
    # Top 10 by Business Risk Score
    scored_pages = sorted(priority_rows, key=lambda r: float(r.get("Business Risk Score", 0) or 0), reverse=True)[:10]
    for row in scored_pages:
        url = str(row.get("URL", ""))
        slug = url.replace(f"https://{ctx.domain}", "").replace(f"http://{ctx.domain}", "") or "/"
        ctx.priority_pages.append({
            "url_slug": slug[:60],
            "seo_health": float(row.get("SEO Health Score", 0) or 0),
            "gsc_clicks": int(float(row.get("GSC Impressions", 0) or 0)),  # Check: might be Impressions in Priority URLs
            "severity": str(row.get("Severity Badge", "")),
            "action": str(row.get("Action Needed", ""))[:80],
        })

    # ── CONTENT READINESS ────────────────────────────────────────────────────
    # Calculate from extra_rows (Content & AI Readiness data)
    ok_pages = [r for r in extra_rows if r.get("Status Code") == 200 or str(r.get("Status Code", "")).isdigit() and int(r.get("Status Code", 0)) == 200]
    total_ok = max(len(ok_pages), 1)

    def pct(field: str, good_fn) -> float:
        return round(sum(1 for r in ok_pages if good_fn(r)) / total_ok * 100, 1)

    readiness_items = [
        {"factor": "Good H1 Tag", "percent": pct("H1 Count", lambda r: (r.get("H1 Count") or 0) == 1), "target": "100%"},
        {"factor": "Meta Description Present", "percent": pct("Meta Description Missing", lambda r: not r.get("Meta Description Missing")), "target": "100%"},
        {"factor": "Answer Paragraphs (40–60 word)", "percent": pct("Answer Blocks", lambda r: (r.get("Answer Blocks") or 0) > 0), "target": "80%+"},
        {"factor": "Schema Markup", "percent": pct("Schema Types Count", lambda r: (r.get("Schema Types Count") or 0) > 0), "target": "80%+"},
        {"factor": "Image Alt Coverage ≥ 80%", "percent": pct("Image Alt Coverage (%)", lambda r: (r.get("Image Alt Coverage (%)") or 0) >= 80), "target": "100%"},
        {"factor": "Question-Style Headings", "percent": pct("Question Heading Count", lambda r: (r.get("Question Heading Count") or 0) > 0), "target": "80%+"},
    ]
    for item in readiness_items:
        p = item["percent"]
        item["status"] = "good" if p >= 80 else "warning" if p >= 50 else "critical"
    ctx.content_readiness = readiness_items

    # ── NARRATIVE ────────────────────────────────────────────────────────────
    ctx.executive_narrative = _generate_narrative(ctx)

    return ctx


def _extract_domain(main_rows: list[dict]) -> str:
    from urllib.parse import urlparse
    for row in main_rows:
        url = str(row.get("URL", ""))
        if url.startswith("http"):
            return urlparse(url).netloc
    return "unknown"


def _count_values(rows: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        val = str(row.get(key, ""))
        counts[val] = counts.get(val, 0) + 1
    return counts


def _generate_narrative(ctx: ReportContext) -> str:
    """Generate a plain-language executive summary paragraph."""
    parts = []
    parts.append(
        f"This audit crawled {ctx.total_urls} URLs on {ctx.domain} "
        f"on {ctx.crawl_date[:10] if len(ctx.crawl_date) >= 10 else ctx.crawl_date}."
    )

    if ctx.seo_health_mean < 30:
        parts.append(
            f"The site's average SEO health score is {ctx.seo_health_mean}% — "
            f"significantly below the target of 80%+."
        )
    elif ctx.seo_health_mean < 70:
        parts.append(
            f"The site's average SEO health score is {ctx.seo_health_mean}% — "
            f"below the recommended 80%+ threshold."
        )
    else:
        parts.append(
            f"The site's average SEO health score is {ctx.seo_health_mean}%, "
            f"meeting the 80%+ target."
        )

    if ctx.critical_url_count > 0:
        crit_pct = round(ctx.critical_url_count / max(ctx.total_urls, 1) * 100, 1)
        parts.append(
            f"{ctx.critical_url_count} pages ({crit_pct}%) carry a Critical severity badge."
        )

    if ctx.status_4xx_count > 0:
        parts.append(f"{ctx.status_4xx_count} pages return 4xx errors.")

    if ctx.aeo_readiness_mean < 50:
        parts.append(
            f"AI search readiness (AEO) averages {ctx.aeo_readiness_mean}% — "
            f"below the 70% threshold required for AI search engines to extract content reliably."
        )

    if ctx.total_fix_hours > 0:
        parts.append(
            f"The FixPlan identifies {len(ctx.sprint_plan)} sprint categories "
            f"totalling {ctx.total_fix_hours:.0f} estimated hours of remediation work."
        )

    return " ".join(parts)
```

**IMPORTANT:** The parameter names (`main_rows`, `extra_rows`, etc.) above are indicative. Read your Step 0 investigation output to determine:
- What data structures are available at export time in `execute_export`
- Whether they are lists of dicts, lists of Pydantic models, or DataFrames
- What the exact column/key names are

Adapt the `build_report_context` function accordingly. The logic is correct; the accessor patterns may need adjustment.

---

## PART 2 — HTML Template Renderer

### 2A — New module: `src/hype_frog/reporter/html_report_renderer.py`

This module takes a `ReportContext` and renders it to a self-contained HTML string.

The full template is below. Read it in its entirety before implementing — the CSS and HTML are tightly coupled and must be kept together.

```python
"""
Render a ReportContext into a self-contained HTML executive report.
"""
from __future__ import annotations
from typing import Any
from hype_frog.reporter.html_report_data import ReportContext
import html as html_lib


def render_html_report(ctx: ReportContext) -> str:
    """Return a complete HTML document string ready for file write."""
    return _TEMPLATE.format(
        brand_colour=ctx.brand_colour,
        accent_colour=ctx.accent_colour,
        logo_block=_logo_block(ctx.logo_base64),
        client_name=_esc(ctx.client_name or ctx.domain),
        domain=_esc(ctx.domain),
        crawl_date=_esc(ctx.crawl_date[:10] if len(ctx.crawl_date) >= 10 else ctx.crawl_date),
        prepared_by_block=_prepared_by_block(ctx.prepared_by),
        total_urls=ctx.total_urls,
        crawl_duration=ctx.crawl_duration_minutes,
        crawl_mode=_esc(ctx.crawl_mode),
        narrative=_esc(ctx.executive_narrative),
        kpi_cards=_render_kpi_cards(ctx),
        severity_bar=_render_severity_bar(ctx),
        status_table=_render_status_table(ctx),
        top_issues_table=_render_top_issues(ctx),
        sprint_table=_render_sprint_table(ctx),
        priority_pages_table=_render_priority_pages(ctx),
        content_readiness_table=_render_content_readiness(ctx),
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


def _rag_class(value: float, good: float = 80, warning: float = 50, invert: bool = False) -> str:
    """Return CSS class: 'good', 'warning', or 'critical'."""
    if invert:
        if value <= good: return "good"
        if value <= warning: return "warning"
        return "critical"
    if value >= good: return "good"
    if value >= warning: return "warning"
    return "critical"


def _render_kpi_cards(ctx: ReportContext) -> str:
    cards = [
        ("SEO Health", f"{ctx.seo_health_mean}%", _rag_class(ctx.seo_health_mean)),
        ("AEO Readiness", f"{ctx.aeo_readiness_mean}%", _rag_class(ctx.aeo_readiness_mean, good=70)),
        ("Mobile PSI", f"{ctx.psi_mobile_mean}", _rag_class(ctx.psi_mobile_mean, good=90, warning=50)),
        ("Critical Pages", f"{ctx.critical_url_count}", "critical" if ctx.critical_url_count > 0 else "good"),
        ("Total URLs", f"{ctx.total_urls}", "neutral"),
        ("Fix Hours", f"{ctx.total_fix_hours:.0f}h", "neutral"),
    ]
    html_parts = []
    for label, value, cls in cards:
        html_parts.append(f'<div class="kpi-card {cls}"><div class="kpi-value">{value}</div><div class="kpi-label">{label}</div></div>')
    return "\n".join(html_parts)


def _render_severity_bar(ctx: ReportContext) -> str:
    total = max(ctx.critical_url_count + ctx.warning_url_count + ctx.observation_url_count, 1)
    c_pct = round(ctx.critical_url_count / total * 100, 1)
    w_pct = round(ctx.warning_url_count / total * 100, 1)
    o_pct = round(ctx.observation_url_count / total * 100, 1)
    return (
        f'<div class="severity-bar">'
        f'<div class="sev-seg critical" style="width:{c_pct}%">{ctx.critical_url_count}</div>'
        f'<div class="sev-seg warning" style="width:{w_pct}%">{ctx.warning_url_count}</div>'
        f'<div class="sev-seg observation" style="width:{o_pct}%">{ctx.observation_url_count}</div>'
        f'</div>'
        f'<div class="sev-legend">'
        f'<span class="dot critical"></span> Critical ({ctx.critical_url_count}) '
        f'<span class="dot warning"></span> Warning ({ctx.warning_url_count}) '
        f'<span class="dot observation"></span> Observation ({ctx.observation_url_count})'
        f'</div>'
    )


def _render_status_table(ctx: ReportContext) -> str:
    rows = [
        ("200 OK", ctx.status_200_count, "good"),
        ("3xx Redirects", ctx.status_3xx_count, "neutral"),
        ("4xx Client Errors", ctx.status_4xx_count, "critical" if ctx.status_4xx_count > 0 else "good"),
        ("5xx Server Errors", ctx.status_5xx_count, "critical" if ctx.status_5xx_count > 0 else "good"),
        ("Timeout", ctx.status_timeout_count, "warning" if ctx.status_timeout_count > 0 else "good"),
    ]
    html_rows = "".join(
        f'<tr class="{cls}"><td>{label}</td><td>{count}</td></tr>' for label, count, cls in rows
    )
    return f'<table class="data-table compact"><thead><tr><th>Status</th><th>Pages</th></tr></thead><tbody>{html_rows}</tbody></table>'


def _render_top_issues(ctx: ReportContext) -> str:
    if not ctx.top_issues:
        return "<p>No issues detected.</p>"
    rows = []
    for issue in ctx.top_issues:
        sev_cls = issue["severity"].lower() if issue["severity"] in ("Critical", "Warning", "Observation") else "neutral"
        rows.append(
            f'<tr>'
            f'<td><span class="badge {sev_cls}">{_esc(issue["severity"])}</span></td>'
            f'<td>{_esc(issue["name"])}</td>'
            f'<td class="num">{issue["affected_count"]}</td>'
            f'</tr>'
        )
    return (
        f'<table class="data-table"><thead><tr><th>Severity</th><th>Issue</th><th>Pages</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )


def _render_sprint_table(ctx: ReportContext) -> str:
    if not ctx.sprint_plan:
        return "<p>No FixPlan available.</p>"
    rows = []
    for sp in ctx.sprint_plan:
        priority = sp.get("priority", sp.get("sprint", ""))
        cls = "critical" if "Immediate" in priority else "warning" if "Next" in priority else "neutral"
        rows.append(
            f'<tr class="{cls}">'
            f'<td>{_esc(sp["sprint"])}</td>'
            f'<td class="num">{sp["issue_count"]}</td>'
            f'<td class="num">{sp["hours"]:.0f}h</td>'
            f'<td>{_esc(sp["owner"])}</td>'
            f'</tr>'
        )
    rows.append(
        f'<tr class="total-row"><td>Total</td>'
        f'<td class="num">{sum(s["issue_count"] for s in ctx.sprint_plan)}</td>'
        f'<td class="num">{ctx.total_fix_hours:.0f}h</td>'
        f'<td></td></tr>'
    )
    return (
        f'<table class="data-table"><thead><tr><th>Sprint</th><th>Issues</th><th>Hours</th><th>Owner</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )


def _render_priority_pages(ctx: ReportContext) -> str:
    if not ctx.priority_pages:
        return "<p>No priority pages identified.</p>"
    rows = []
    for pg in ctx.priority_pages:
        health_cls = _rag_class(pg["seo_health"])
        rows.append(
            f'<tr>'
            f'<td class="url-cell">{_esc(pg["url_slug"])}</td>'
            f'<td class="num {health_cls}">{pg["seo_health"]:.0f}%</td>'
            f'<td class="num">{pg["gsc_clicks"]}</td>'
            f'<td>{_esc(pg["action"])}</td>'
            f'</tr>'
        )
    return (
        f'<table class="data-table"><thead><tr><th>Page</th><th>Health</th><th>Impressions</th><th>Action</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )


def _render_content_readiness(ctx: ReportContext) -> str:
    if not ctx.content_readiness:
        return ""
    rows = []
    for item in ctx.content_readiness:
        cls = item.get("status", "neutral")
        rows.append(
            f'<tr>'
            f'<td>{_esc(item["factor"])}</td>'
            f'<td class="num {cls}">{item["percent"]:.1f}%</td>'
            f'<td>{_esc(item.get("target", ""))}</td>'
            f'</tr>'
        )
    return (
        f'<table class="data-table"><thead><tr><th>Factor</th><th>Current</th><th>Target</th></tr></thead>'
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
# FULL HTML TEMPLATE
# ─────────────────────────────────────────────────────────────────────────────

_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SEO &amp; AEO Audit — {client_name}</title>
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
  h2 {{ font-size: 1.15em; color: {brand_colour}; margin: 28px 0 10px; padding: 6px 10px; background: {brand_colour}; color: #fff; border-radius: 3px; }}
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
</style>
</head>
<body>

<div class="header">
  {logo_block}
  <h1>SEO &amp; AEO Audit Report</h1>
  <div class="subtitle">{domain} &mdash; {crawl_date} &mdash; {total_urls} URLs crawled ({crawl_mode} mode, {crawl_duration} min)</div>
  {prepared_by_block}
</div>

<div class="narrative">{narrative}</div>

<h2>Site Health Overview</h2>
<div class="kpi-row">
  {kpi_cards}
</div>

<h3>Severity Distribution</h3>
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
{top_issues_table}

<h2>Sprint &amp; Resource Plan</h2>
{sprint_table}

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
```

---

## PART 3 — File Writer & Pipeline Integration

### 3A — New module: `src/hype_frog/reporter/html_report_writer.py`

```python
"""
Write the HTML executive report to disk alongside the xlsx.
"""
from __future__ import annotations
from pathlib import Path
from hype_frog.reporter.html_report_data import ReportContext, build_report_context
from hype_frog.reporter.html_report_renderer import render_html_report

# Use core logging — per architecture.mdc
try:
    from hype_frog.core import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


def write_html_report(
    ctx: ReportContext,
    output_path: str | Path,
) -> Path:
    """Render and write HTML report to disk. Returns the output path."""
    path = Path(output_path)
    html_content = render_html_report(ctx)
    path.write_text(html_content, encoding="utf-8")
    logger.info("HTML executive report written to %s (%d bytes)", path, len(html_content))
    return path
```

### 3B — Integrate into export pipeline

**File:** `src/hype_frog/orchestration/export_flow.py`

Find `execute_export` (or the equivalent function that produces the xlsx). Read it fully before modifying.

**At the end of `execute_export`, after the xlsx is written and saved, add:**

```python
# ── HTML EXECUTIVE REPORT ────────────────────────────────────────────────
from hype_frog.reporter.html_report_data import build_report_context
from hype_frog.reporter.html_report_writer import write_html_report

try:
    # Derive HTML path from xlsx path
    xlsx_path = Path(output_filename)
    html_path = xlsx_path.with_suffix(".html")

    # Build report context from the same enriched data used for xlsx
    # ADAPT THESE PARAMETER NAMES to match your actual variables:
    report_ctx = build_report_context(
        main_rows=main_rows,           # list of main row dicts
        extra_rows=extra_rows,         # list of extra row dicts
        fixplan_rows=fixplan_rows,     # list of FixPlan row dicts
        priority_rows=priority_rows,   # list of Priority URL row dicts
        audit_run_details=audit_run_details_dict,  # dict of key:value
        content_readiness_rows=extra_rows,  # C&AI data is usually in extra
        summary_rows=summary_rows,     # list of Summary row dicts
        domain=target_domain,          # crawl target domain
        prepared_by=os.environ.get("HF_REPORT_PREPARED_BY", ""),
        client_name=os.environ.get("HF_REPORT_CLIENT_NAME", ""),
        logo_base64=_load_logo_base64(),
        brand_colour=os.environ.get("HF_REPORT_BRAND_COLOUR", "#1e293b"),
        accent_colour=os.environ.get("HF_REPORT_ACCENT_COLOUR", "#2563eb"),
    )

    write_html_report(report_ctx, html_path)
except Exception as e:
    logger.warning("HTML report generation failed (non-fatal): %s", e)
    # HTML report failure must NOT prevent the xlsx from being delivered
```

**CRITICAL:** The HTML report generation is **non-fatal**. If it fails for any reason, catch the exception, log it, and let the xlsx delivery succeed. The xlsx is the primary deliverable; the HTML is supplementary.

### 3C — Logo loader helper

Add to `html_report_writer.py`:

```python
import base64

def _load_logo_base64() -> str:
    """Load logo from HF_REPORT_LOGO_PATH env var. Returns data URI or empty string."""
    logo_path = os.environ.get("HF_REPORT_LOGO_PATH", "")
    if not logo_path:
        return ""
    try:
        path = Path(logo_path)
        if not path.exists():
            return ""
        data = path.read_bytes()
        ext = path.suffix.lower()
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "svg": "image/svg+xml", "webp": "image/webp"}.get(ext.lstrip("."), "image/png")
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return ""
```

---

## PART 4 — Configuration

### 4A — Environment variables

Add these to `.env.example` (create if it doesn't exist, otherwise append):

```bash
# ── HTML Executive Report (optional) ────────────────────────────────────
# HF_REPORT_PREPARED_BY=Logi-Ink Digital Services
# HF_REPORT_CLIENT_NAME=African Marketing Confederation
# HF_REPORT_LOGO_PATH=./assets/client_logo.png
# HF_REPORT_BRAND_COLOUR=#1e293b
# HF_REPORT_ACCENT_COLOUR=#2563eb
```

### 4B — Add assets directory

Create `assets/` directory at project root if it doesn't exist. Add to `.cursorignore`:
```
assets/
```

This directory is for client logos and brand assets — not code.

---

## PART 5 — Tests

### 5A — Unit test for report data collector

Create `tests/reporter/test_html_report_data.py`:

```python
"""Test HTML report data collection from mock crawl data."""
import pytest
from hype_frog.reporter.html_report_data import build_report_context


def _mock_main_rows(n: int = 10) -> list[dict]:
    rows = []
    for i in range(n):
        rows.append({
            "URL": f"https://example.com/page-{i}",
            "Status Code": 200 if i < 8 else 404,
            "SEO Health Score": 10 + i * 5,
            "Severity Badge": "Critical" if i < 3 else "Warning" if i < 6 else "Observation",
            "Mobile PSI Score": 40 + i * 3,
            "Desktop PSI Score": 50 + i * 3,
            "GSC Clicks": i * 2 if i < 5 else None,
            "GSC Impressions": i * 20 if i < 5 else None,
            "GSC Avg Position": 5.0 + i if i < 5 else None,
            "GSC Coverage Note": "Matched" if i < 5 else None,
        })
    return rows


def _mock_extra_rows(n: int = 10) -> list[dict]:
    rows = []
    for i in range(n):
        rows.append({
            "URL": f"https://example.com/page-{i}",
            "Status Code": 200 if i < 8 else 404,
            "AEO Readiness Score": 20 + i * 5,
            "H1 Count": 1 if i < 7 else 0,
            "Meta Description Missing": i >= 8,
            "Answer Blocks": 1 if i < 3 else 0,
            "Schema Types Count": 1 if i < 2 else 0,
            "Image Alt Coverage (%)": 80 + i if i < 5 else 20,
            "Question Heading Count": 2 if i < 4 else 0,
        })
    return rows


def _mock_fixplan() -> list[dict]:
    return [
        {"Issue Type": "Broken Links", "Severity": "Critical", "Owner": "Dev", "Est. Hours": 10, "Aging/Priority": "Immediate (Current Sprint)"},
        {"Issue Type": "Missing Meta", "Severity": "Warning", "Owner": "Copy Writer", "Est. Hours": 4, "Aging/Priority": "Next Sprint"},
        {"Issue Type": "Low Alt Coverage", "Severity": "Warning", "Owner": "Copy Writer", "Est. Hours": 8, "Aging/Priority": "Backlog"},
    ]


def _mock_audit_run_details() -> dict:
    return {
        "Run Timestamp": "2026-06-27 01:33:36",
        "Total URLs": 10,
        "Duration (s)": 120.5,
        "Crawl Mode": "accurate",
        "GSC Data Freshness": "2026-05-28 to 2026-06-26",
    }


def test_build_report_context_basic():
    ctx = build_report_context(
        main_rows=_mock_main_rows(),
        extra_rows=_mock_extra_rows(),
        fixplan_rows=_mock_fixplan(),
        priority_rows=_mock_main_rows(),
        audit_run_details=_mock_audit_run_details(),
        content_readiness_rows=_mock_extra_rows(),
        summary_rows=[],
    )
    assert ctx.domain == "example.com"
    assert ctx.total_urls == 10
    assert ctx.seo_health_mean > 0
    assert ctx.critical_url_count == 3
    assert ctx.warning_url_count == 3
    assert ctx.observation_url_count == 4
    assert ctx.status_200_count == 8
    assert ctx.status_4xx_count == 2
    assert len(ctx.sprint_plan) == 3
    assert ctx.total_fix_hours == 22.0
    assert ctx.gsc_available is True
    assert ctx.gsc_clicks_total > 0
    assert len(ctx.content_readiness) == 6
    assert ctx.executive_narrative != ""


def test_build_report_context_no_gsc():
    rows = _mock_main_rows()
    for r in rows:
        r["GSC Clicks"] = None
        r["GSC Impressions"] = None
        r["GSC Avg Position"] = None
        r["GSC Coverage Note"] = None
    ctx = build_report_context(
        main_rows=rows,
        extra_rows=_mock_extra_rows(),
        fixplan_rows=[],
        priority_rows=[],
        audit_run_details=_mock_audit_run_details(),
        content_readiness_rows=_mock_extra_rows(),
        summary_rows=[],
    )
    assert ctx.gsc_available is False
    assert ctx.gsc_clicks_total == 0


def test_narrative_content():
    ctx = build_report_context(
        main_rows=_mock_main_rows(),
        extra_rows=_mock_extra_rows(),
        fixplan_rows=_mock_fixplan(),
        priority_rows=[],
        audit_run_details=_mock_audit_run_details(),
        content_readiness_rows=_mock_extra_rows(),
        summary_rows=[],
    )
    assert "example.com" in ctx.executive_narrative
    assert "10 URLs" in ctx.executive_narrative
```

### 5B — Unit test for HTML renderer

Create `tests/reporter/test_html_report_renderer.py`:

```python
"""Test HTML report rendering produces valid self-contained HTML."""
import pytest
from hype_frog.reporter.html_report_data import ReportContext
from hype_frog.reporter.html_report_renderer import render_html_report


def test_render_produces_valid_html():
    ctx = ReportContext(
        domain="example.com",
        crawl_date="2026-06-27",
        total_urls=100,
        seo_health_mean=45.0,
        aeo_readiness_mean=30.0,
        psi_mobile_mean=52.0,
        critical_url_count=20,
        warning_url_count=30,
        observation_url_count=50,
        status_200_count=90,
        status_4xx_count=10,
        executive_narrative="Test narrative.",
        total_fix_hours=40.0,
    )
    html = render_html_report(ctx)

    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html
    assert "example.com" in html
    assert "45.0%" in html  # SEO health
    assert "30.0%" in html  # AEO readiness
    assert 'class="kpi-card critical"' in html  # Critical card
    assert "<style>" in html  # CSS is inline
    assert "http://" not in html.split("<style>")[1].split("</style>")[0]  # No external CSS refs
    assert ".js" not in html  # No JS file references


def test_render_no_branding_leaks():
    ctx = ReportContext(domain="example.com", crawl_date="2026-06-27", total_urls=1)
    html = render_html_report(ctx)
    html_lower = html.lower()
    assert "hype-frog" not in html_lower
    assert "hype_frog" not in html_lower
    assert "hypefrog" not in html_lower
    assert "github.com" not in html_lower


def test_render_white_label_branding():
    ctx = ReportContext(
        domain="client.com",
        crawl_date="2026-06-27",
        total_urls=50,
        prepared_by="Logi-Ink Digital",
        client_name="Client Corp",
        brand_colour="#0a5c36",
        accent_colour="#e8a317",
    )
    html = render_html_report(ctx)
    assert "Client Corp" in html
    assert "Logi-Ink Digital" in html
    assert "#0a5c36" in html
    assert "#e8a317" in html


def test_render_print_safe():
    ctx = ReportContext(domain="example.com", crawl_date="2026-06-27", total_urls=1)
    html = render_html_report(ctx)
    assert "@media print" in html
    assert "page-break-before" in html
```

---

## PART 6 — Documentation Updates

### 6A — Update `docs/system_architecture.md`

Add under the "Workbook integrity" section or as a new section:

```markdown
## HTML executive report

Every crawl produces an HTML executive report alongside the xlsx workbook. The HTML report is a self-contained single file (all CSS inline, no external dependencies) suitable for browser viewing or Print → Save as PDF.

The report is white-label: branding, logo, and colours are configurable via environment variables (`HF_REPORT_PREPARED_BY`, `HF_REPORT_CLIENT_NAME`, `HF_REPORT_LOGO_PATH`, `HF_REPORT_BRAND_COLOUR`, `HF_REPORT_ACCENT_COLOUR`). No tool-internal naming appears in the output.

**Module structure:**
- `reporter/html_report_data.py` — collects and aggregates enriched data into a `ReportContext` dataclass (read-only consumer of pipeline data).
- `reporter/html_report_renderer.py` — renders `ReportContext` to self-contained HTML.
- `reporter/html_report_writer.py` — writes HTML to disk.

HTML report generation is **non-fatal**: failures are logged but do not prevent xlsx delivery.
```

### 6B — Update `README.md`

Add under "What it does":
```markdown
- Generates a **white-label HTML executive report** alongside the xlsx workbook — self-contained, printable to PDF, configurable branding.
```

Add under "Configuration":
```markdown
- **HTML Report branding:** set `HF_REPORT_PREPARED_BY`, `HF_REPORT_CLIENT_NAME`, `HF_REPORT_LOGO_PATH`, `HF_REPORT_BRAND_COLOUR`, `HF_REPORT_ACCENT_COLOUR` in `.env` to customise the executive report. All are optional; defaults produce an unbranded report.
```

### 6C — Update `docs/excel_reporting_standards.md`

Add a new section:

```markdown
## HTML executive report

The reporter layer also produces a parallel HTML executive report via `html_report_data.py`, `html_report_renderer.py`, and `html_report_writer.py`. This report reads the same enriched data as the xlsx but produces a self-contained HTML file for stakeholder distribution.

The HTML report follows the same data-integrity principles: it reads pipeline data as read-only, applies sanitisation (HTML entity encoding via `html.escape`), and must not mutate upstream row dictionaries.

New data points added to the xlsx output should also be reflected in `html_report_data.py` → `ReportContext` where relevant to the executive summary.
```

### 6D — Update `.cursor/rules/excel_engine.mdc`

Add under "Reporter module ownership":
```
- `html_report_data.py` — HTML report data aggregation (read-only consumer).
- `html_report_renderer.py` — HTML template rendering.
- `html_report_writer.py` — HTML file I/O.
```

---

## TEST CRAWL

After implementation, run:

```bash
uv run hype-frog  # crawl AMC with PSI key and GSC OAuth
```

**Verify:**
- An `.html` file is created alongside the `.xlsx` with the same base filename
- Open the HTML in a browser — it renders correctly
- Print → Save as PDF — produces a clean 4–6 page PDF with page breaks between sections
- No "hype-frog" text appears anywhere in the rendered output
- If `HF_REPORT_PREPARED_BY` is set in `.env`, it appears in the header
- All numbers match the xlsx (spot-check SEO Health, URL count, Critical count, GSC clicks)
- The HTML file is self-contained — disconnect from the internet and reload — it still renders

```bash
uv run pytest tests/reporter/test_html_report_data.py tests/reporter/test_html_report_renderer.py -v
```

---

## UPDATE AUDIT_FIX_LOG.md

```markdown
## HTML Executive Report — LI-HF-HTMLRPT-P0

### Implementation status
- [ ] Part 1: Report data collector (`html_report_data.py`)
- [ ] Part 2: HTML template renderer (`html_report_renderer.py`)
- [ ] Part 3: File writer + pipeline integration (`html_report_writer.py` + `export_flow.py`)
- [ ] Part 4: Configuration (`.env.example` + `assets/`)
- [ ] Part 5: Tests (2 test files, 6 test cases)
- [ ] Part 6: Documentation updates (4 files)

### Test results
- HTML file generated: [Yes/No]
- Renders in browser: [Yes/No]
- Prints to PDF cleanly: [Yes/No]
- No branding leaks: [Yes/No]
- pytest passes: [Yes/No]
```

