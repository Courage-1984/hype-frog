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

STD_NAVY: str = "2F3A4A"
STD_WHITE: str = "FFFFFF"
STD_BLUE: str = "2F6FA3"
STD_FROG_GREEN: str = "92D050"

# ── Canonical RAG palette (single source of truth) ───────────────────────────
# Prefer these over inline hex literals so status colours read consistently
# across every sheet and degrade acceptably in greyscale / for colour-blind
# users. Fills pair with the matching *_FONT colour for legible text.
RAG_RED: str = "FFC7CE"        # critical / fail fill
RAG_RED_FONT: str = "9C0006"   # legible text on a red fill
RAG_AMBER: str = "FFEB9C"      # warning fill
RAG_AMBER_FONT: str = "9C6500"
RAG_GREEN: str = "C6EFCE"      # pass / good fill
RAG_GREEN_FONT: str = "006100"
RAG_RED_SOFT: str = "FFC1C1"   # softer critical (e.g. severity row striping)
RAG_AMBER_SOFT: str = "FFCC99" # softer warning (e.g. severity row striping)
RAG_NEUTRAL: str = "D9D9D9"    # not-applicable / to-do
ZEBRA_BAND: str = "F7F7F7"     # alternating-row striping

# Office-style 3-stop heatmap scale (low → mid → high), reused by colour scales.
HEATMAP_LOW: str = "F8696B"
HEATMAP_MID: str = "FFEB84"
HEATMAP_HIGH: str = "63BE7B"
DATA_BAR_BLUE: str = "638EC6"  # canonical data-bar colour

# Canonical UK spelling for the Content Hub worksheet title (must match workbook-wide).
CONTENT_OPTIMISATION_HUB_SHEET: str = "Content Optimisation Hub"
CONTENT_PLANNER_SHEET: str = "Content Planner"
# Companion sheet: per-URL crawl metrics and executive ROI fields split from the Hub.
CONTENT_HUB_METRICS_SHEET: str = "Content Hub Metrics"
AIOSEO_RECOMMENDATIONS_SHEET: str = "AIOSEO Recommendations"
AUDIT_RUN_DETAILS_SHEET: str = "Audit Run Details"
REDIRECT_MAP_SHEET: str = "Redirect Map"
ROBOTS_ANALYSIS_SHEET: str = "Robots.txt Analysis"
CRAWL_LOG_SHEET: str = "Crawl Log"
SCRIPT_INVENTORY_SHEET: str = "Script Inventory"
IMAGE_INVENTORY_SHEET: str = "Image Inventory"
LINK_EQUITY_MAP_SHEET: str = "Link Equity Map"
ANCHOR_TEXT_AUDIT_SHEET: str = "Anchor Text Audit"
SNIPPET_OPPORTUNITIES_SHEET: str = "Snippet Opportunities"
COMPETITOR_BENCHMARKS_SHEET: str = "Competitor Benchmarks"
EXECUTIVE_DASHBOARD_SHEET: str = "Executive Dashboard"
CHART_DATA_SHEET: str = "Chart Data"
# Freeze through Assigned Owner + URL Slug Normalization; URL scrolls from column I.
CONTENT_HUB_FREEZE_PANES: str = "I3"

DATA_HEAVY_TABS: set[str] = {
    "Main",
    "Technical",
    "AEO",
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
    "CONTENT_OPTIMISATION_HUB_SHEET",
    "CONTENT_PLANNER_SHEET",
    "CONTENT_HUB_METRICS_SHEET",
    "AIOSEO_RECOMMENDATIONS_SHEET",
    "AUDIT_RUN_DETAILS_SHEET",
    "REDIRECT_MAP_SHEET",
    "ROBOTS_ANALYSIS_SHEET",
    "CRAWL_LOG_SHEET",
    "SCRIPT_INVENTORY_SHEET",
    "IMAGE_INVENTORY_SHEET",
    "LINK_EQUITY_MAP_SHEET",
    "ANCHOR_TEXT_AUDIT_SHEET",
    "SNIPPET_OPPORTUNITIES_SHEET",
    "COMPETITOR_BENCHMARKS_SHEET",
    "EXECUTIVE_DASHBOARD_SHEET",
    "CHART_DATA_SHEET",
    "CONTENT_HUB_FREEZE_PANES",
    "DATA_HEAVY_TABS",
    "env_bool",
    "DEBUG_EXCEL_ISOLATION_MODE",
    "DISABLE_DATA_VALIDATION",
    "DISABLE_TOOLTIPS",
    "DISABLE_CONDITIONAL_FORMATTING",
    "DISABLE_EXTERNAL_LINKS_AND_IMAGES",
    "DISABLE_NON_CORE_FREEZE_PANES",
]
