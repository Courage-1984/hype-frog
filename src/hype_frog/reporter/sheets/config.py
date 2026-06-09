from __future__ import annotations

import os

STD_NAVY: str = "2F3A4A"
STD_WHITE: str = "FFFFFF"
STD_BLUE: str = "2F6FA3"
STD_FROG_GREEN: str = "92D050"

# Canonical UK spelling for the Content Hub worksheet title (must match workbook-wide).
CONTENT_OPTIMISATION_HUB_SHEET: str = "Content Optimisation Hub"
# Companion sheet: per-URL crawl metrics and executive ROI fields split from the Hub.
CONTENT_HUB_METRICS_SHEET: str = "Content Hub Metrics"
AIOSEO_RECOMMENDATIONS_SHEET: str = "AIOSEO Recommendations"
AUDIT_RUN_DETAILS_SHEET: str = "Audit Run Details"
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


def env_bool(name: str, default: bool) -> bool:
    raw: str | None = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


DEBUG_EXCEL_ISOLATION_MODE: bool = env_bool("HF_DEBUG_EXCEL_ISOLATION_MODE", False)
DISABLE_DATA_VALIDATION: bool = env_bool("HF_DISABLE_DATA_VALIDATION", False)
DISABLE_CONDITIONAL_FORMATTING: bool = env_bool("HF_DISABLE_CONDITIONAL_FORMATTING", False)
DISABLE_EXTERNAL_LINKS_AND_IMAGES: bool = env_bool(
    "HF_DISABLE_EXTERNAL_LINKS_AND_IMAGES", False
)
DISABLE_NON_CORE_FREEZE_PANES: bool = env_bool("HF_DISABLE_NON_CORE_FREEZE_PANES", False)


__all__ = [
    "STD_NAVY",
    "STD_WHITE",
    "STD_BLUE",
    "STD_FROG_GREEN",
    "CONTENT_OPTIMISATION_HUB_SHEET",
    "CONTENT_HUB_METRICS_SHEET",
    "AIOSEO_RECOMMENDATIONS_SHEET",
    "AUDIT_RUN_DETAILS_SHEET",
    "EXECUTIVE_DASHBOARD_SHEET",
    "CHART_DATA_SHEET",
    "CONTENT_HUB_FREEZE_PANES",
    "DATA_HEAVY_TABS",
    "env_bool",
    "DEBUG_EXCEL_ISOLATION_MODE",
    "DISABLE_DATA_VALIDATION",
    "DISABLE_CONDITIONAL_FORMATTING",
    "DISABLE_EXTERNAL_LINKS_AND_IMAGES",
    "DISABLE_NON_CORE_FREEZE_PANES",
]
