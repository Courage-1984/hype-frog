"""
Aggregate enriched crawl data into a flat ReportContext dataclass
for the HTML executive report renderer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    pass


@dataclass
class ReportContext:
    """All data needed to render the HTML executive report."""

    # ── IDENTITY ──────────────────────────────────────────────────────────────
    domain: str = ""
    crawl_date: str = ""
    crawl_duration_minutes: float = 0.0
    total_urls: int = 0
    crawl_mode: str = ""

    # ── BRANDING (white-label) ─────────────────────────────────────────────────
    prepared_by: str = ""
    client_name: str = ""
    logo_base64: str = ""
    brand_colour: str = "#1e293b"
    accent_colour: str = "#2563eb"
    theme: str = ""  # e.g. "mocha" for Catppuccin Mocha styling

    # ── KPIs ──────────────────────────────────────────────────────────────────
    seo_health_mean: float = 0.0
    seo_health_projected: float = 0.0
    aeo_readiness_mean: float = 0.0
    psi_mobile_mean: float = 0.0
    psi_desktop_mean: float = 0.0
    critical_url_count: int = 0
    warning_url_count: int = 0
    observation_url_count: int = 0

    # ── STATUS CODES ──────────────────────────────────────────────────────────
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

    # ── TOP ISSUES ────────────────────────────────────────────────────────────
    top_issues: list[dict[str, Any]] = field(default_factory=list)
    # Each: {"name": str, "severity": str, "affected_count": int}

    # ── SPRINT PLAN ───────────────────────────────────────────────────────────
    sprint_plan: list[dict[str, Any]] = field(default_factory=list)
    # Each: {"sprint": str, "issue_count": int, "hours": float, "owner": str}
    total_fix_hours: float = 0.0

    # ── PRIORITY PAGES ────────────────────────────────────────────────────────
    priority_pages: list[dict[str, Any]] = field(default_factory=list)
    # Each: {"url_slug": str, "seo_health": float, "gsc_impressions": int, "severity": str, "action": str}

    # ── QUICK WINS ────────────────────────────────────────────────────────────
    quick_wins: list[dict[str, Any]] = field(default_factory=list)
    # Each (subset of the Quick Wins sheet): {"name": str, "effort_hours": float, "owner": str}

    # ── CONTENT READINESS ─────────────────────────────────────────────────────
    content_readiness: list[dict[str, Any]] = field(default_factory=list)
    # Each: {"factor": str, "percent": float, "status": str, "target": str}

    # ── NARRATIVE ─────────────────────────────────────────────────────────────
    executive_narrative: str = ""


def build_report_context(
    main_rows: list[dict[str, Any]],
    extra_rows: list[dict[str, Any]],
    fixplan_rows: list[dict[str, Any]],
    priority_rows: list[dict[str, Any]],
    summary_rows: list[dict[str, Any]],
    broken_link_impact_rows: list[dict[str, Any]] | None = None,
    quick_win_rows: list[dict[str, Any]] | None = None,
    run_timestamp: str = "",
    summary_metrics: Any | None = None,  # SummaryMetricsPayload or None
    domain: str = "",
    prepared_by: str = "",
    client_name: str = "",
    logo_base64: str = "",
    brand_colour: str = "#1e293b",
    accent_colour: str = "#2563eb",
    theme: str = "",
) -> ReportContext:
    """Build a ReportContext from enriched crawl pipeline data. Read-only."""
    ctx = ReportContext()

    # ── BRANDING ──────────────────────────────────────────────────────────────
    ctx.prepared_by = prepared_by
    ctx.brand_colour = brand_colour
    ctx.accent_colour = accent_colour
    ctx.theme = theme
    ctx.logo_base64 = logo_base64

    # ── IDENTITY ──────────────────────────────────────────────────────────────
    ctx.domain = domain or _extract_domain(main_rows) or _extract_domain(extra_rows)
    ctx.client_name = client_name or ctx.domain
    ctx.crawl_date = run_timestamp

    # ── KPIs — prefer pre-computed SummaryMetricsPayload ──────────────────────
    if summary_metrics is not None:
        ctx.total_urls = int(getattr(summary_metrics, "urls_crawled", 0) or 0)
        ctx.seo_health_mean = round(float(getattr(summary_metrics, "health_score_pct", 0.0) or 0.0), 1)
        ctx.seo_health_projected = round(float(getattr(summary_metrics, "projected_health_score_pct", 0.0) or 0.0), 1)
        ctx.critical_url_count = int(getattr(summary_metrics, "critical_url_count", 0) or 0)
        ctx.warning_url_count = int(getattr(summary_metrics, "warning_url_count", 0) or 0)
    else:
        ctx.total_urls = len(main_rows) or len(extra_rows)
        health_vals = [_to_float(r.get("SEO Health Score")) for r in extra_rows if r.get("SEO Health Score") is not None]
        ctx.seo_health_mean = round(sum(health_vals) / max(len(health_vals), 1), 1) if health_vals else 0.0
        ctx.seo_health_projected = 0.0
        sev_counts = _count_values(extra_rows, "Severity Badge")
        ctx.critical_url_count = sev_counts.get("Critical", 0)
        ctx.warning_url_count = sev_counts.get("Warning", 0)

    # Observation count always derived (not stored in SummaryMetricsPayload)
    sev_counts_all = _count_values(extra_rows, "Severity Badge")
    ctx.observation_url_count = sev_counts_all.get("Observation", 0)

    # ── AEO ───────────────────────────────────────────────────────────────────
    aeo_vals = [
        _to_float(r.get("AEO Readiness Score"))
        for r in extra_rows
        if str(r.get("AEO Badge") or "").strip() != "Unmeasured"
        and r.get("AEO Readiness Score") is not None
    ]
    ctx.aeo_readiness_mean = round(sum(aeo_vals) / max(len(aeo_vals), 1), 1) if aeo_vals else 0.0

    # ── PSI — extra_rows (Technical Diagnostics) carries PSI columns ───────────
    all_rows = extra_rows or main_rows  # prefer extra_rows; fall back to main
    mob_vals = [_to_float(r.get("Mobile PSI Score")) for r in all_rows if r.get("Mobile PSI Score") not in (None, 0, 0.0, "")]
    ctx.psi_mobile_mean = round(sum(mob_vals) / max(len(mob_vals), 1), 1) if mob_vals else 0.0
    desk_vals = [_to_float(r.get("Desktop PSI Score")) for r in all_rows if r.get("Desktop PSI Score") not in (None, 0, 0.0, "")]
    ctx.psi_desktop_mean = round(sum(desk_vals) / max(len(desk_vals), 1), 1) if desk_vals else 0.0

    # ── STATUS CODES — read from extra_rows (Technical Diagnostics source) ────
    # main_rows Status Code defaults to None; extra_rows carries the real HTTP codes
    _sc_rows = extra_rows if extra_rows else main_rows
    for row in _sc_rows:
        sc = row.get("Status Code")
        if sc is None:
            continue  # unset means crawl didn't resolve HTTP yet; skip
        if str(sc).lower() == "timeout":
            ctx.status_timeout_count += 1
            continue
        try:
            sc_int = int(sc)
        except (TypeError, ValueError):
            continue
        if sc_int == 200:
            ctx.status_200_count += 1
        elif 300 <= sc_int < 400:
            ctx.status_3xx_count += 1
        elif 400 <= sc_int < 500:
            ctx.status_4xx_count += 1
        elif sc_int >= 500:
            ctx.status_5xx_count += 1
        # sc_int == 0 (fetch-failed placeholder) is intentionally ignored

    # ── GSC ───────────────────────────────────────────────────────────────────
    clicks_list = [_to_float(r.get("GSC Clicks")) for r in main_rows if r.get("GSC Clicks") is not None]
    ctx.gsc_clicks_total = int(sum(clicks_list))
    imp_list = [_to_float(r.get("GSC Impressions")) for r in main_rows if r.get("GSC Impressions") is not None]
    ctx.gsc_impressions_total = int(sum(imp_list))
    pos_list = [_to_float(r.get("GSC Avg Position")) for r in main_rows
                if r.get("GSC Avg Position") is not None and _to_float(r.get("GSC Avg Position")) > 0]
    ctx.gsc_avg_position = round(sum(pos_list) / max(len(pos_list), 1), 1) if pos_list else 0.0
    ctx.gsc_pages_with_clicks = sum(1 for r in main_rows if _to_float(r.get("GSC Clicks")) > 0)
    ctx.gsc_available = ctx.gsc_clicks_total > 0 or any(r.get("GSC Coverage Note") for r in main_rows)
    freshness_vals = [str(r.get("GSC Data Freshness", "")) for r in main_rows if r.get("GSC Data Freshness")]
    ctx.gsc_data_freshness = freshness_vals[0] if freshness_vals else ""

    # ── TOP ISSUES ────────────────────────────────────────────────────────────
    # summary_rows uses "Issue" (not "Issue Name") and "Affected URL Count" (not "Affected Count")
    seen_issues: dict[str, dict[str, Any]] = {}
    for row in summary_rows:
        name = str(row.get("Issue") or row.get("Issue Name") or "").strip()
        severity = str(row.get("Severity") or "").strip()
        count = int(_to_float(row.get("Affected URL Count") or row.get("Affected Count") or 0))
        if name and count > 0 and name not in seen_issues:
            seen_issues[name] = {"name": name, "severity": severity, "affected_count": count}
    ctx.top_issues = sorted(seen_issues.values(), key=lambda x: x["affected_count"], reverse=True)[:10]

    # ── SPRINT PLAN ───────────────────────────────────────────────────────────
    # "Aging/Priority" values: "Immediate (Current Sprint)", "Next Sprint", "Backlog"
    sprint_groups: dict[str, dict[str, Any]] = {}
    for row in fixplan_rows:
        sprint = str(row.get("Aging/Priority") or "Backlog").strip()
        hours = _to_float(row.get("Est. Hours"))
        owner = str(row.get("Owner") or "").strip()
        if sprint not in sprint_groups:
            sprint_groups[sprint] = {"sprint": sprint, "issue_count": 0, "hours": 0.0, "owners": set()}
        sprint_groups[sprint]["issue_count"] += 1
        sprint_groups[sprint]["hours"] += hours
        if owner:
            sprint_groups[sprint]["owners"].add(owner)

    _priority_order = {"Immediate (Current Sprint)": 0, "Next Sprint": 1, "Backlog": 2}
    sorted_sprints = sorted(sprint_groups.values(), key=lambda x: _priority_order.get(x["sprint"], 99))
    ctx.sprint_plan = [
        {
            "sprint": sp["sprint"],
            "issue_count": sp["issue_count"],
            "hours": sp["hours"],
            "owner": ", ".join(sorted(sp["owners"])),
        }
        for sp in sorted_sprints
    ]
    ctx.total_fix_hours = sum(sp["hours"] for sp in ctx.sprint_plan)

    # ── PRIORITY PAGES ────────────────────────────────────────────────────────
    scored_pages = sorted(
        priority_rows,
        key=lambda r: _to_float(r.get("Business Risk Score")),
        reverse=True,
    )[:10]
    domain_prefix_http = f"http://{ctx.domain}"
    domain_prefix_https = f"https://{ctx.domain}"
    for row in scored_pages:
        url = str(row.get("URL") or "")
        slug = url.replace(domain_prefix_https, "").replace(domain_prefix_http, "") or "/"
        ctx.priority_pages.append({
            "url_slug": slug[:60],
            "seo_health": _to_float(row.get("SEO Health Score")),
            "gsc_impressions": int(_to_float(row.get("GSC Impressions"))),
            "severity": str(row.get("Severity Badge") or ""),
            # "Action Needed" is a Yes/No flag; "Why Prioritized" is the human-readable reason
            "action": str(row.get("Why Prioritized") or row.get("Recommended Fix") or "")[:80],
        })

    # ── QUICK WINS ────────────────────────────────────────────────────────────
    # Read-only projection of the Quick Wins sheet rows (keys: "Issue", "Effort (hrs)", "Owner").
    for row in (quick_win_rows or [])[:10]:
        name = str(row.get("Issue") or "").strip()
        if not name:
            continue
        ctx.quick_wins.append({
            "name": name,
            "effort_hours": _to_float(row.get("Effort (hrs)")),
            "owner": str(row.get("Owner") or "").strip(),
        })

    # ── CONTENT READINESS ─────────────────────────────────────────────────────
    # Compute over all extra_rows — Status Code defaults to None for many rows
    # so a strict == 200 filter returns 0 rows and breaks the section.
    # A "content health" denominator of all crawled pages is more meaningful
    # for executive reporting anyway.
    cr_pages = extra_rows if extra_rows else main_rows
    total_cr = max(len(cr_pages), 1)

    def _pct(good_fn: Any) -> float:
        return round(sum(1 for r in cr_pages if good_fn(r)) / total_cr * 100, 1)

    readiness_items = [
        {
            "factor": "Good H1 Tag",
            "percent": _pct(lambda r: _to_float(r.get("H1 Count")) == 1),
            "target": "100%",
        },
        {
            "factor": "Meta Description Present",
            "percent": _pct(lambda r: not r.get("Meta Description Missing")),
            "target": "100%",
        },
        {
            "factor": "Answer Paragraphs (40–60 word)",
            "percent": _pct(lambda r: _to_float(r.get("Paragraphs 40-60 Words Count")) > 0),
            "target": "80%+",
        },
        {
            "factor": "Schema Markup",
            "percent": _pct(lambda r: _to_float(r.get("Schema Types Count")) > 0),
            "target": "80%+",
        },
        {
            "factor": "Image Alt Coverage ≥ 80%",
            "percent": _pct(lambda r: _to_float(r.get("Image Alt Coverage (%)")) >= 80),
            "target": "100%",
        },
        {
            "factor": "Question-Style Headings",
            "percent": _pct(lambda r: _to_float(r.get("Question Heading Count")) > 0),
            "target": "80%+",
        },
    ]
    for item in readiness_items:
        p = item["percent"]
        item["status"] = "good" if p >= 80 else "warning" if p >= 50 else "critical"
    ctx.content_readiness = readiness_items

    # ── NARRATIVE ─────────────────────────────────────────────────────────────
    ctx.executive_narrative = _generate_narrative(ctx)

    return ctx


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_domain(rows: list[dict[str, Any]]) -> str:
    for row in rows:
        url = str(row.get("URL") or "")
        if url.startswith("http"):
            return urlparse(url).netloc
    return ""


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _count_values(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        val = str(row.get(key) or "")
        counts[val] = counts.get(val, 0) + 1
    return counts


def _generate_narrative(ctx: ReportContext) -> str:
    parts: list[str] = []
    date_str = ctx.crawl_date[:10] if len(ctx.crawl_date) >= 10 else ctx.crawl_date
    parts.append(f"This audit crawled {ctx.total_urls} URLs on {ctx.domain}{f' on {date_str}' if date_str else ''}.")

    if ctx.seo_health_mean < 30:
        parts.append(
            f"The site's average SEO health score is {ctx.seo_health_mean}% — significantly below the target of 80%+."
        )
    elif ctx.seo_health_mean < 70:
        parts.append(
            f"The site's average SEO health score is {ctx.seo_health_mean}% — below the recommended 80%+ threshold."
        )
    else:
        parts.append(
            f"The site's average SEO health score is {ctx.seo_health_mean}%, meeting the 80%+ target."
        )

    if ctx.critical_url_count > 0:
        crit_pct = round(ctx.critical_url_count / max(ctx.total_urls, 1) * 100, 1)
        parts.append(f"{ctx.critical_url_count} pages ({crit_pct}%) carry a Critical severity badge.")

    if ctx.status_4xx_count > 0:
        parts.append(f"{ctx.status_4xx_count} pages return 4xx errors.")

    if ctx.aeo_readiness_mean > 0 and ctx.aeo_readiness_mean < 50:
        parts.append(
            f"AI search readiness (AEO) averages {ctx.aeo_readiness_mean}% — below the 70% threshold required for AI search engines to extract content reliably."
        )

    if ctx.total_fix_hours > 0:
        parts.append(
            f"The FixPlan identifies {len(ctx.sprint_plan)} sprint categories totalling {ctx.total_fix_hours:.0f} estimated hours of remediation work."
        )

    if ctx.seo_health_projected > ctx.seo_health_mean and ctx.seo_health_projected > 0:
        uplift = round(ctx.seo_health_projected - ctx.seo_health_mean, 1)
        parts.append(
            f"Completing all FixPlan items is projected to lift SEO health to {ctx.seo_health_projected}% (+{uplift}pp)."
        )

    return " ".join(parts)
