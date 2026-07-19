"""End-user description banner text per workbook sheet (no I/O).

These are the human-readable "what is this tab" blurbs surfaced in the row-1
return strip of each data sheet. Source of record for the prose is
``workbook_tabs.md`` (British spelling preferred for user-facing copy).

Keys must match canonical sheet names so the 3-way sheet-name lock
(``sheets/config.py`` + ``engine_guardrails._TOC_FRIENDLY_DESCRIPTIONS`` +
``sheets/workbook_layout.py``) stays consistent.
"""

from __future__ import annotations

from hype_frog.reporter.sheets.config import (
    AIOSEO_RECOMMENDATIONS_SHEET,
    AUDIT_RUN_DETAILS_SHEET,
    COMPETITOR_BENCHMARKS_SHEET,
    CONTENT_OPTIMISATION_HUB_SHEET,
    CONTENT_PLANNER_SHEET,
    CRAWL_LOG_SHEET,
    IMAGE_INVENTORY_SHEET,
    ROBOTS_ANALYSIS_SHEET,
    SCRIPT_INVENTORY_SHEET,
    SNIPPET_OPPORTUNITIES_SHEET,
)

# Longer "End-user description" prose (contrast with the one-line TOC blurbs in
# ``engine_guardrails._TOC_FRIENDLY_DESCRIPTIONS``).
SHEET_END_USER_DESCRIPTIONS: dict[str, str] = {
    "Priority URLs": (
        "High-value pages that need attention first, scored by issues, health, "
        "and commercial intent. Use Status and Sprint to triage ownership "
        "without leaving the sheet."
    ),
    "FixPlan": (
        "The master remediation plan: each row is an issue type (not one URL), "
        "with how many pages are affected, who should fix it, estimated effort, "
        "and links into Playbook and detail sheets. Track Status as work "
        "progresses."
    ),
    "Quick Wins": (
        "Fastest wins: concrete page-level fixes that score well on impact "
        "versus effort. Start here when you need early delivery momentum before "
        "tackling systemic FixPlan items."
    ),
    CONTENT_OPTIMISATION_HUB_SHEET: (
        "Day-to-day content workspace: see what each page needs (copy vs "
        "optimisation), edit titles/meta/headings with live health checks, and "
        "track workflow Status and owner. Pair with Content Hub Metrics for "
        "traffic and CWV context."
    ),
    CONTENT_PLANNER_SHEET: (
        "Production checklist for every page in the site tree. Use the sign-off "
        "columns to track copy, design, and client approval through to go-live."
    ),
    "Main": (
        "Complete URL inventory from the crawl. Use the left-hand triage columns "
        "for filtering; expand column groups or open Technical Diagnostics when "
        "you need deep performance and indexability detail."
    ),
    AIOSEO_RECOMMENDATIONS_SHEET: (
        "Actionable recommendations mapped to All in One SEO panels, with direct "
        "edit links and current vs target values. Use when the site is managed "
        "in WordPress with AIOSEO."
    ),
    "Broken Link Impact": (
        "Broken links ordered by how many pages point to them and how much "
        "Search Console traffic those sources earn. Fix high-priority rows first "
        "to recover the most value."
    ),
    "SitemapQA": (
        "Quality assurance for your XML sitemaps: which URLs are in the sitemap "
        "versus the crawl, redirects and non-200 entries, missing sitemap tags, "
        "and pages crawled but absent from the sitemap."
    ),
    "Template & Duplication Risks": (
        "Systemic content risks: duplicate titles and descriptions, draft/copy "
        "pages, and template-wide defects (for example missing H1 across a "
        "folder). Prefer one template fix over dozens of one-off edits."
    ),
    "Playbook": (
        "In-workbook education: editorial standards, answer-engine guidance, and "
        "a how-to playbook for each issue type — what it is, why it matters, how "
        "to fix it, and how to verify."
    ),
    "Issue Register": (
        "Single backlog of tracked issues with history (first seen, days open) "
        "and assignment fields. Use this as the living register; FixPlan remains "
        "the remediation plan by issue type."
    ),
    "Technical Diagnostics": (
        "Full technical profile per URL: HTTP and indexability, security "
        "headers, redirects, PageSpeed/Core Web Vitals, and Search Console "
        "signals. Prefer this over Main for PSI and CWV detail."
    ),
    "Content & AI Readiness": (
        "How ready each page is for search and answer engines: content depth, "
        "structure, schema, media alt coverage, and AEO extractability scores, "
        "plus intent/ROI signals and inbound anchor-text quality."
    ),
    "Link Intelligence": (
        "Link health at page level: inlinks and outlinks, orphans, click depth, "
        "equity, and broken or generic anchors — with enough detail to plan "
        "internal-linking fixes."
    ),
    "CMS Action URLs": (
        "Cart, add-to-cart, and similar CMS action URLs discovered but not "
        "crawled as pages. Review handlers and canonicals in the CMS; they "
        "appear here for audit visibility only."
    ),
    "Redirects": (
        "Every redirect path found in the crawl, hop by hop, with loops, "
        "temporary redirects, and SEO risk notes so you can shorten or correct "
        "chains."
    ),
    ROBOTS_ANALYSIS_SHEET: (
        "How robots.txt treats key crawlers and AI bots, which paths are "
        "blocked, and where rules conflict with sitemap or crawl expectations."
    ),
    CRAWL_LOG_SHEET: (
        "Operational diary of fetch, render, PSI, and GSC problems during this "
        "audit — useful when results look incomplete or a URL failed "
        "unexpectedly."
    ),
    SNIPPET_OPPORTUNITIES_SHEET: (
        "Pages with the best chance of featured snippets or AI-style answers, "
        "plus suggested restructuring and effort level."
    ),
    COMPETITOR_BENCHMARKS_SHEET: (
        "Side-by-side snapshot of key on-page metrics versus configured "
        "competitor domains (sampled pages). Absent when no competitors were "
        "supplied for the run."
    ),
    SCRIPT_INVENTORY_SHEET: (
        "Detected third-party tags and trackers (analytics, ads, chat, consent, "
        "etc.), where they load, transfer size, and whether they are "
        "render-blocking. Not a complete script catalogue."
    ),
    IMAGE_INVENTORY_SHEET: (
        "Every significant image found: broken or oversized files, alt-text "
        "coverage, dimensions, and which pages use them."
    ),
    "DeltaFromPreviousRun": (
        "What improved, what regressed, and what is new since the previous "
        "audit. On a first run with no prior export, this sheet records the "
        "baseline only."
    ),
    AUDIT_RUN_DETAILS_SHEET: (
        "Technical provenance for this workbook: how the crawl was configured, "
        "how long it took, and which enrichment sources (GSC, render, external "
        "sniff) were active. Use when reproducing or comparing runs."
    ),
}


def sheet_end_user_description(sheet_name: str) -> str:
    """Return the banner description for ``sheet_name`` (``""`` when unknown)."""
    return SHEET_END_USER_DESCRIPTIONS.get(sheet_name, "")


__all__ = [
    "SHEET_END_USER_DESCRIPTIONS",
    "sheet_end_user_description",
]
