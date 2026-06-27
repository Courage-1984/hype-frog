"""Workbook tab order, colours, and default visibility (single source of truth)."""

from __future__ import annotations

from openpyxl.workbook.workbook import Workbook

from hype_frog.reporter.sheets.config import (
    AIOSEO_RECOMMENDATIONS_SHEET,
    ANCHOR_TEXT_AUDIT_SHEET,
    AUDIT_RUN_DETAILS_SHEET,
    CONTENT_HUB_METRICS_SHEET,
    CONTENT_OPTIMISATION_HUB_SHEET,
    CRAWL_LOG_SHEET,
    COMPETITOR_BENCHMARKS_SHEET,
    EXECUTIVE_DASHBOARD_SHEET,
    IMAGE_INVENTORY_SHEET,
    LINK_EQUITY_MAP_SHEET,
    REDIRECT_MAP_SHEET,
    ROBOTS_ANALYSIS_SHEET,
    SCRIPT_INVENTORY_SHEET,
    SNIPPET_OPPORTUNITIES_SHEET,
    STD_NAVY,
)

# Excel tab colours (RRGGBB — openpyxl ``tabColor``).
TAB_COLOR_EXECUTIVE = "4472C4"
TAB_COLOR_ACTIONABLE = "ED7D31"
TAB_COLOR_CONTENT = "70AD47"
TAB_COLOR_INVENTORY = "A6A6A6"
TAB_COLOR_DIAGNOSTIC = "FFC000"
TAB_COLOR_HISTORICAL = "D9D9D9"
TAB_COLOR_REFERENCE = STD_NAVY
TAB_COLOR_PLUGIN = "7030A0"
TAB_COLOR_ADVANCED = "BFBFBF"

# Visible left-to-right (after Table of Contents).
VISIBLE_WORKBOOK_TAB_ORDER: tuple[str, ...] = (
    "Table of Contents",
    "Dashboard",
    EXECUTIVE_DASHBOARD_SHEET,
    "Summary",
    "Priority URLs",
    "FixPlan",
    "Quick Wins",
    CONTENT_OPTIMISATION_HUB_SHEET,
    CONTENT_HUB_METRICS_SHEET,
    "Main",
    AIOSEO_RECOMMENDATIONS_SHEET,
    "Link Inventory",
    "Broken Link Impact",
    "SitemapQA",
    "Template & Duplication Risks",
    "Playbook",
)

# Technical / historical tabs (hidden by default; linked from Dashboard + TOC).
ADVANCED_WORKBOOK_TAB_ORDER: tuple[str, ...] = (
    "Issue Register",
    "Technical Diagnostics",
    "Content & AI Readiness",
    "Link Intelligence",
    "CMS Action URLs",
    "IssueInventory",
    "Redirects",
    REDIRECT_MAP_SHEET,
    ROBOTS_ANALYSIS_SHEET,
    CRAWL_LOG_SHEET,
    LINK_EQUITY_MAP_SHEET,
    ANCHOR_TEXT_AUDIT_SHEET,
    SNIPPET_OPPORTUNITIES_SHEET,
    COMPETITOR_BENCHMARKS_SHEET,
    SCRIPT_INVENTORY_SHEET,
    IMAGE_INVENTORY_SHEET,
    "ResolvedIssues",
    "DeltaFromPreviousRun",
    AUDIT_RUN_DETAILS_SHEET,
)

PREFERRED_WORKBOOK_TAB_ORDER: tuple[str, ...] = (
    VISIBLE_WORKBOOK_TAB_ORDER + ADVANCED_WORKBOOK_TAB_ORDER
)

_PREFERRED_TAB_SET: frozenset[str] = frozenset(PREFERRED_WORKBOOK_TAB_ORDER)

HIDDEN_SHEETS_BY_DEFAULT: frozenset[str] = frozenset(ADVANCED_WORKBOOK_TAB_ORDER)

SHEETS_EXCLUDED_FROM_TOC: frozenset[str] = frozenset()

TOC_PRIMARY_SECTION_LABEL = "Primary workflow"
TOC_ADVANCED_SECTION_LABEL = (
    "Technical & Historical (Advanced) — tabs hidden; use Open links or "
    "right-click tab bar → Unhide Sheet"
)

DASHBOARD_ADVANCED_SHEETS_NOTE = (
    "Technical & historical tabs are hidden to reduce clutter. Use the links below or "
    "Home → Format → Hide & Unhide → Unhide Sheet."
)

# (sheet_name, dashboard_label) — hyperlinks work even when the tab is hidden.
DASHBOARD_ADVANCED_SHEET_LINKS: tuple[tuple[str, str], ...] = (
    ("Issue Register", "Issue Register"),
    ("Technical Diagnostics", "Technical Diagnostics"),
    ("Content & AI Readiness", "Content & AI Readiness"),
    ("Link Intelligence", "Link Intelligence"),
    ("CMS Action URLs", "CMS Action URLs"),
    ("IssueInventory", "Issue Inventory"),
    ("Redirects", "Redirects"),
    (REDIRECT_MAP_SHEET, "Redirect Map"),
    (ROBOTS_ANALYSIS_SHEET, "Robots.txt Analysis"),
    (CRAWL_LOG_SHEET, "Crawl Log"),
    (AUDIT_RUN_DETAILS_SHEET, "Audit Run Details"),
    ("ResolvedIssues", "Resolved Issues"),
    ("DeltaFromPreviousRun", "Delta From Previous Run"),
)

_SHEET_TAB_COLORS: dict[str, str] = {
    "Dashboard": TAB_COLOR_EXECUTIVE,
    EXECUTIVE_DASHBOARD_SHEET: TAB_COLOR_EXECUTIVE,
    "Summary": TAB_COLOR_EXECUTIVE,
    "Priority URLs": TAB_COLOR_ACTIONABLE,
    "FixPlan": TAB_COLOR_ACTIONABLE,
    "Quick Wins": TAB_COLOR_ACTIONABLE,
    CONTENT_OPTIMISATION_HUB_SHEET: TAB_COLOR_CONTENT,
    CONTENT_HUB_METRICS_SHEET: TAB_COLOR_CONTENT,
    "Main": TAB_COLOR_INVENTORY,
    AIOSEO_RECOMMENDATIONS_SHEET: TAB_COLOR_PLUGIN,
    "Link Inventory": TAB_COLOR_INVENTORY,
    "Broken Link Impact": TAB_COLOR_INVENTORY,
    "SitemapQA": TAB_COLOR_DIAGNOSTIC,
    "Template & Duplication Risks": TAB_COLOR_DIAGNOSTIC,
    "Playbook": TAB_COLOR_REFERENCE,
    "Issue Register": TAB_COLOR_ADVANCED,
    "Technical Diagnostics": TAB_COLOR_ADVANCED,
    "Content & AI Readiness": TAB_COLOR_ADVANCED,
    "Link Intelligence": TAB_COLOR_ADVANCED,
    "CMS Action URLs": TAB_COLOR_ADVANCED,
    "IssueInventory": TAB_COLOR_ADVANCED,
    "Redirects": TAB_COLOR_ADVANCED,
    REDIRECT_MAP_SHEET: TAB_COLOR_ADVANCED,
    ROBOTS_ANALYSIS_SHEET: TAB_COLOR_ADVANCED,
    CRAWL_LOG_SHEET: TAB_COLOR_HISTORICAL,
    "ResolvedIssues": TAB_COLOR_HISTORICAL,
    "DeltaFromPreviousRun": TAB_COLOR_HISTORICAL,
    AUDIT_RUN_DETAILS_SHEET: TAB_COLOR_HISTORICAL,
}


def excel_sheet_link_target(name: str) -> str:
    """Escape single quotes for internal ``HYPERLINK("#'…'!A1")`` targets."""
    return str(name).replace("'", "''")


def reorder_workbook_tabs(wb: Workbook) -> None:
    """Move tabs into ``PREFERRED_WORKBOOK_TAB_ORDER``; unknown tabs append at the end."""
    desired_order = list(PREFERRED_WORKBOOK_TAB_ORDER)
    for tab_name in wb.sheetnames:
        if tab_name not in _PREFERRED_TAB_SET:
            desired_order.append(tab_name)
    for idx, tab_name in enumerate(desired_order):
        if tab_name in wb.sheetnames:
            wb.move_sheet(wb[tab_name], offset=-wb.index(wb[tab_name]) + idx)


def apply_workbook_tab_colors(wb: Workbook) -> None:
    """Apply group tab colours; Table of Contents stays default."""
    for name, rgb in _SHEET_TAB_COLORS.items():
        if name not in wb.sheetnames:
            continue
        wb[name].sheet_properties.tabColor = rgb


def apply_workbook_tab_visibility(wb: Workbook) -> None:
    """Hide advanced / historical tabs by default."""
    for name in wb.sheetnames:
        ws = wb[name]
        if name in HIDDEN_SHEETS_BY_DEFAULT:
            ws.sheet_state = "hidden"
        elif ws.sheet_state == "hidden" and name in VISIBLE_WORKBOOK_TAB_ORDER:
            ws.sheet_state = "visible"


def apply_workbook_tab_layout(wb: Workbook) -> None:
    """Reorder tabs, apply colours, and set default visibility."""
    reorder_workbook_tabs(wb)
    apply_workbook_tab_colors(wb)
    apply_workbook_tab_visibility(wb)


__all__ = [
    "ADVANCED_WORKBOOK_TAB_ORDER",
    "DASHBOARD_ADVANCED_SHEET_LINKS",
    "DASHBOARD_ADVANCED_SHEETS_NOTE",
    "HIDDEN_SHEETS_BY_DEFAULT",
    "PREFERRED_WORKBOOK_TAB_ORDER",
    "TOC_ADVANCED_SECTION_LABEL",
    "TOC_PRIMARY_SECTION_LABEL",
    "SHEETS_EXCLUDED_FROM_TOC",
    "VISIBLE_WORKBOOK_TAB_ORDER",
    "apply_workbook_tab_colors",
    "apply_workbook_tab_layout",
    "apply_workbook_tab_visibility",
    "excel_sheet_link_target",
    "reorder_workbook_tabs",
]
