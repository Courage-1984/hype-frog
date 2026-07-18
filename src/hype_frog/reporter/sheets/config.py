from __future__ import annotations

from hype_frog.core.env_vars import (
    get_hf_debug_excel_isolation_mode,
    get_hf_disable_conditional_formatting,
    get_hf_disable_data_validation,
    get_hf_disable_external_links_and_images,
    get_hf_disable_non_core_freeze_panes,
    get_hf_disable_tooltips,
    get_hf_excel_theme,
)

# ── Modern workbook theme (Phase 1 UI/UX refurbishment) ─────────────────────
THEME_HEADER_BG: str = "222A35"   # slate/charcoal table headers
THEME_HEADER_TEXT: str = "FFFFFF"
GRID_BORDER: str = "E0E0E0"       # light grid lines (large inventory sheets)
ZEBRA_FAINT: str = "FAFAFA"       # CF zebra anchor (sheets > 500 rows; Phase 4C)
LARGE_SHEET_ROW_THRESHOLD: int = 500

# Legacy brand aliases — prefer THEME_HEADER_* for new layout code.
STD_NAVY: str = THEME_HEADER_BG
STD_WHITE: str = THEME_HEADER_TEXT
STD_BLUE: str = "2F6FA3"
STD_FROG_GREEN: str = "92D050"

# ── Canonical RAG palette (single source of truth) ───────────────────────────
# Muted pastel fills with dark text for contrast compliance. Prefer importing
# these over inline hex literals across conditional formatting passes.
RAG_RED: str = "FCE8E6"        # critical / fail fill
RAG_RED_FONT: str = "A51D24"   # legible text on a red fill
RAG_AMBER: str = "FEF3D6"      # warning fill
RAG_AMBER_FONT: str = "8F6B00"
RAG_GREEN: str = "E6F4EA"      # pass / good fill
RAG_GREEN_FONT: str = "137333"
RAG_RED_SOFT: str = "FFF0F0"   # softer critical (severity row striping) — lighter than RAG_RED
RAG_AMBER_SOFT: str = "FFFAED" # softer warning striping — lighter than RAG_AMBER
RAG_NEUTRAL: str = "D9D9D9"    # not-applicable / to-do
ZEBRA_BAND: str = "F7F7F7"     # CF zebra anchor (≤500 data rows)

# Office-style 3-stop heatmap scale (low → mid → high), reused by colour scales.
HEATMAP_LOW: str = "F8696B"
HEATMAP_MID: str = "FFEB84"
HEATMAP_HIGH: str = "63BE7B"
DATA_BAR_BLUE: str = "638EC6"  # canonical data-bar colour

# Navigation (Phase 3) — row-1 return strips land on the Executive Briefing tab.
RETURN_TO_BRIEFING_LABEL: str = "← Return to Executive Briefing"
WORKBOOK_NAV_TARGET_SHEET: str = "Executive Briefing"
DATA_SHEET_FREEZE_PANES: str = "C3"  # return strip row + header row above data grid

# Severity badge fills beyond core RAG (Main sheet).
SEVERITY_OBSERVATION_FILL: str = "DBEAFE"
SEVERITY_UNMEASURED_FILL: str = "E5E7EB"
HTTP_STATUS_ERROR_FONT: str = "991B1B"
HTTP_STATUS_TIMEOUT_FONT: str = "924012"

# Unified workflow Status column (Phase 5) — FixPlan, Hub, AIOSEO, IssueInventory.
STATUS_OPTIONS: tuple[str, ...] = ("To Do", "In Progress", "In Review", "Done")
STATUS_TODO_FILL: str = "E2E8F0"   # visible slate background (was near-white F8F9FA)
STATUS_TODO_FONT: str = "222A35"   # legible text on todo fill
STATUS_REVIEW_FILL: str = SEVERITY_OBSERVATION_FILL  # blue — distinct from amber "In Progress"
STATUS_REVIEW_FONT: str = "1E40AF"
# Hub grid: row 1 banner, row 2 headers, row 3+ data (Phase 4A — no scope-note row).
CONTENT_HUB_DATA_START_ROW: int = 3

# Marks a column HEADER (not its data cells) as an editable workflow input the
# tool never overwrites on re-export — e.g. Priority URLs "Status"/"Sprint".
EDITABLE_INPUT_HEADER_FILL: str = "FFF2CC"   # soft input-yellow
EDITABLE_INPUT_HEADER_FONT: str = "7F6000"


def status_validation_list_formula() -> str:
    """Excel ``DataValidation`` list literal for workflow ``Status`` columns."""
    return '"' + ",".join(STATUS_OPTIONS) + '"'


# Priority URLs seeds every row "Open" (export_registry.py::build_priority_rows) — a
# lightweight triage flag, not the FixPlan/Hub workflow above, so it gets its own list.
TRIAGE_STATUS_OPTIONS: tuple[str, ...] = ("Open", "In Progress", "Resolved", "Won't Fix")


def triage_status_validation_list_formula() -> str:
    """Excel ``DataValidation`` list literal for lightweight triage ``Status`` columns."""
    return '"' + ",".join(TRIAGE_STATUS_OPTIONS) + '"'


# Content Hub banner / workflow accents (non-RAG but canonicalised).
HUB_BANNER_FILL: str = "BFE9E4"
HUB_SCOPE_NOTE_FONT: str = "666666"
HUB_STATUS_COMPLETED_BG: str = "137333"
HUB_STATUS_PROGRESS_BG: str = "FFC000"
HUB_OWNER_COPYWRITER_FILL: str = "92D050"
HUB_OWNER_DEVELOPER_FILL: str = "5B9BD5"
HUB_OWNER_SERVER_FILL: str = "ED7D31"

# Main sheet triage columns visible by default (A–K).
MAIN_TRIAGE_VISIBLE_HEADERS: tuple[str, ...] = (
    "Health Icon",
    "URL",
    "Status Code",
    "Indexability",
    "Load Time (s)",
    "Title",
    "Meta Description",
    "Word Count (Body)",
    "SEO Health Score",
    "Severity Badge",
    "Action Needed",
)
MAIN_TRIAGE_COLUMN_COUNT: int = len(MAIN_TRIAGE_VISIBLE_HEADERS)
CONTENT_OPTIMISATION_HUB_SHEET: str = "Content Optimisation Hub"
CONTENT_PLANNER_SHEET: str = "Content Planner"
# Companion sheet: per-URL crawl metrics and executive ROI fields split from the Hub.
CONTENT_HUB_METRICS_SHEET: str = "Content Hub Metrics"
AIOSEO_RECOMMENDATIONS_SHEET: str = "AIOSEO Recommendations"
AUDIT_RUN_DETAILS_SHEET: str = "Audit Run Details"
ROBOTS_ANALYSIS_SHEET: str = "Robots.txt Analysis"
CRAWL_LOG_SHEET: str = "Crawl Log"
SCRIPT_INVENTORY_SHEET: str = "Script Inventory"
IMAGE_INVENTORY_SHEET: str = "Image Inventory"
LINK_EQUITY_MAP_SHEET: str = "Link Equity Map"
ANCHOR_TEXT_AUDIT_SHEET: str = "Anchor Text Audit"
SNIPPET_OPPORTUNITIES_SHEET: str = "Snippet Opportunities"
COMPETITOR_BENCHMARKS_SHEET: str = "Competitor Benchmarks"
EXECUTIVE_BRIEFING_SHEET: str = "Executive Briefing"
# Freeze just the title + KPI (both rows) + key-insights band (rows 1–11) so the
# KPI summary stays visible while scrolling through the taller, non-overlapping
# chart grid.
EXECUTIVE_BRIEFING_FREEZE_PANES: str = "A12"
LEGACY_DASHBOARD_SHEET: str = "Dashboard"
# Deprecated alias — Executive Dashboard tab removed in Phase 2.
EXECUTIVE_DASHBOARD_SHEET: str = "Executive Dashboard"
CHART_DATA_SHEET: str = "Chart Data"
# Freeze through Assigned Owner + URL Slug Normalization; URL scrolls from column I.
CONTENT_HUB_FREEZE_PANES: str = "I3"

# Sheets that benefit from a reduced zoom level so dense card/triage layouts fit on
# screen without horizontal scrolling (applied once, late, in workbook finalisation).
# Tiered for laptop-sized displays (~1366-1920px wide): 85% for the two densest
# card/triage layouts, 90% for all other operational/data tabs. "Table of Contents"
# and Audit Run Details are simple/small pages and are left at Excel's default 100%.
SHEET_ZOOM_OVERRIDES: dict[str, int] = {
    EXECUTIVE_BRIEFING_SHEET: 85,
    "Main": 85,
    "Summary": 90,
    "Priority URLs": 90,
    "FixPlan": 90,
    "Quick Wins": 90,
    CONTENT_OPTIMISATION_HUB_SHEET: 90,
    CONTENT_PLANNER_SHEET: 90,
    CONTENT_HUB_METRICS_SHEET: 90,
    AIOSEO_RECOMMENDATIONS_SHEET: 90,
    "Link Inventory": 90,
    "Broken Link Impact": 90,
    "SitemapQA": 90,
    "Template & Duplication Risks": 90,
    "Playbook": 90,
    "Issue Register": 90,
    "Technical Diagnostics": 90,
    "Content & AI Readiness": 90,
    "Link Intelligence": 90,
    "CMS Action URLs": 90,
    "Redirects": 90,
    ROBOTS_ANALYSIS_SHEET: 90,
    CRAWL_LOG_SHEET: 90,
    LINK_EQUITY_MAP_SHEET: 90,
    ANCHOR_TEXT_AUDIT_SHEET: 90,
    SNIPPET_OPPORTUNITIES_SHEET: 90,
    COMPETITOR_BENCHMARKS_SHEET: 90,
    SCRIPT_INVENTORY_SHEET: 90,
    IMAGE_INVENTORY_SHEET: 90,
    "ResolvedIssues": 90,
    "DeltaFromPreviousRun": 90,
}

# Actionable workflow / triage sheets always receive autofilter headers (Phase 3).
AUTO_FILTER_SHEETS: frozenset[str] = frozenset(
    {
        "Summary",
        "Priority URLs",
        "FixPlan",
        "Quick Wins",
        AIOSEO_RECOMMENDATIONS_SHEET,
        "Technical Diagnostics",
        CONTENT_HUB_METRICS_SHEET,
        "Broken Link Impact",
        "Issue Register",
        "Content & AI Readiness",
        "Link Intelligence",
        "Template & Duplication Risks",
        "SitemapQA",
    }
)

DATA_HEAVY_TABS: set[str] = {
    "Main",
    AIOSEO_RECOMMENDATIONS_SHEET,
    "FixPlan",
    "Summary",
    "Schema & Metadata",
    CONTENT_OPTIMISATION_HUB_SHEET,
    CONTENT_HUB_METRICS_SHEET,
}


DEBUG_EXCEL_ISOLATION_MODE: bool = get_hf_debug_excel_isolation_mode()
DISABLE_DATA_VALIDATION: bool = get_hf_disable_data_validation()
# Dedicated control for header/cell tooltips (Excel comments). Kept separate from
# data-validation dropdowns so operators can suppress one without the other.
DISABLE_TOOLTIPS: bool = get_hf_disable_tooltips()
DISABLE_CONDITIONAL_FORMATTING: bool = get_hf_disable_conditional_formatting()
DISABLE_EXTERNAL_LINKS_AND_IMAGES: bool = get_hf_disable_external_links_and_images()
DISABLE_NON_CORE_FREEZE_PANES: bool = get_hf_disable_non_core_freeze_panes()

# Optional Catppuccin Mocha palette for Excel (HF_EXCEL_THEME=mocha).
if get_hf_excel_theme() == "mocha":
    from hype_frog.reporter.mocha_theme import excel_palette_overrides

    _mocha = excel_palette_overrides()
    THEME_HEADER_BG = _mocha["THEME_HEADER_BG"]
    THEME_HEADER_TEXT = _mocha["THEME_HEADER_TEXT"]
    STD_NAVY = _mocha["STD_NAVY"]
    STD_WHITE = _mocha["STD_WHITE"]
    STD_BLUE = _mocha["STD_BLUE"]
    STD_FROG_GREEN = _mocha["STD_FROG_GREEN"]
    RAG_RED = _mocha["RAG_RED"]
    RAG_RED_FONT = _mocha["RAG_RED_FONT"]
    RAG_AMBER = _mocha["RAG_AMBER"]
    RAG_AMBER_FONT = _mocha["RAG_AMBER_FONT"]
    RAG_GREEN = _mocha["RAG_GREEN"]
    RAG_GREEN_FONT = _mocha["RAG_GREEN_FONT"]
    RAG_RED_SOFT = _mocha["RAG_RED_SOFT"]
    RAG_AMBER_SOFT = _mocha["RAG_AMBER_SOFT"]
    RAG_NEUTRAL = _mocha["RAG_NEUTRAL"]
    ZEBRA_BAND = _mocha["ZEBRA_BAND"]
    HEATMAP_LOW = _mocha["HEATMAP_LOW"]
    HEATMAP_MID = _mocha["HEATMAP_MID"]
    HEATMAP_HIGH = _mocha["HEATMAP_HIGH"]
    DATA_BAR_BLUE = _mocha["DATA_BAR_BLUE"]


__all__ = [
    "THEME_HEADER_BG",
    "THEME_HEADER_TEXT",
    "GRID_BORDER",
    "ZEBRA_FAINT",
    "LARGE_SHEET_ROW_THRESHOLD",
    "STD_NAVY",
    "STD_WHITE",
    "STD_BLUE",
    "STD_FROG_GREEN",
    "RAG_RED",
    "RAG_RED_FONT",
    "RAG_AMBER",
    "RAG_AMBER_FONT",
    "RAG_GREEN",
    "RAG_GREEN_FONT",
    "RAG_RED_SOFT",
    "RAG_AMBER_SOFT",
    "RAG_NEUTRAL",
    "ZEBRA_BAND",
    "HEATMAP_LOW",
    "HEATMAP_MID",
    "HEATMAP_HIGH",
    "DATA_BAR_BLUE",
    "RETURN_TO_BRIEFING_LABEL",
    "WORKBOOK_NAV_TARGET_SHEET",
    "DATA_SHEET_FREEZE_PANES",
    "status_validation_list_formula",
    "TRIAGE_STATUS_OPTIONS",
    "triage_status_validation_list_formula",
    "STATUS_OPTIONS",
    "STATUS_TODO_FILL",
    "STATUS_TODO_FONT",
    "STATUS_REVIEW_FILL",
    "STATUS_REVIEW_FONT",
    "CONTENT_HUB_DATA_START_ROW",
    "EDITABLE_INPUT_HEADER_FILL",
    "EDITABLE_INPUT_HEADER_FONT",
    "SEVERITY_OBSERVATION_FILL",
    "SEVERITY_UNMEASURED_FILL",
    "HTTP_STATUS_ERROR_FONT",
    "HTTP_STATUS_TIMEOUT_FONT",
    "HUB_BANNER_FILL",
    "HUB_SCOPE_NOTE_FONT",
    "HUB_STATUS_COMPLETED_BG",
    "HUB_STATUS_PROGRESS_BG",
    "HUB_OWNER_COPYWRITER_FILL",
    "HUB_OWNER_DEVELOPER_FILL",
    "HUB_OWNER_SERVER_FILL",
    "MAIN_TRIAGE_VISIBLE_HEADERS",
    "MAIN_TRIAGE_COLUMN_COUNT",
    "CONTENT_OPTIMISATION_HUB_SHEET",
    "CONTENT_PLANNER_SHEET",
    "CONTENT_HUB_METRICS_SHEET",
    "AIOSEO_RECOMMENDATIONS_SHEET",
    "AUDIT_RUN_DETAILS_SHEET",
    "ROBOTS_ANALYSIS_SHEET",
    "CRAWL_LOG_SHEET",
    "SCRIPT_INVENTORY_SHEET",
    "IMAGE_INVENTORY_SHEET",
    "LINK_EQUITY_MAP_SHEET",
    "ANCHOR_TEXT_AUDIT_SHEET",
    "SNIPPET_OPPORTUNITIES_SHEET",
    "COMPETITOR_BENCHMARKS_SHEET",
    "EXECUTIVE_BRIEFING_SHEET",
    "EXECUTIVE_BRIEFING_FREEZE_PANES",
    "LEGACY_DASHBOARD_SHEET",
    "EXECUTIVE_DASHBOARD_SHEET",
    "CHART_DATA_SHEET",
    "CONTENT_HUB_FREEZE_PANES",
    "SHEET_ZOOM_OVERRIDES",
    "AUTO_FILTER_SHEETS",
    "DATA_HEAVY_TABS",
    "env_bool",
    "DEBUG_EXCEL_ISOLATION_MODE",
    "DISABLE_DATA_VALIDATION",
    "DISABLE_TOOLTIPS",
    "DISABLE_CONDITIONAL_FORMATTING",
    "DISABLE_EXTERNAL_LINKS_AND_IMAGES",
    "DISABLE_NON_CORE_FREEZE_PANES",
]
