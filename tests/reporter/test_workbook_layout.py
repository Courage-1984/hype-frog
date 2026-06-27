"""Workbook tab order, colours, and default visibility."""

from __future__ import annotations

from openpyxl import Workbook

from hype_frog.reporter.sheets.config import (
    AIOSEO_RECOMMENDATIONS_SHEET,
    ANCHOR_TEXT_AUDIT_SHEET,
    AUDIT_RUN_DETAILS_SHEET,
    COMPETITOR_BENCHMARKS_SHEET,
    CONTENT_OPTIMISATION_HUB_SHEET,
    IMAGE_INVENTORY_SHEET,
    LINK_EQUITY_MAP_SHEET,
    SCRIPT_INVENTORY_SHEET,
    SNIPPET_OPPORTUNITIES_SHEET,
)
from hype_frog.reporter.sheets.workbook_layout import (
    ADVANCED_WORKBOOK_TAB_ORDER,
    HIDDEN_SHEETS_BY_DEFAULT,
    PREFERRED_WORKBOOK_TAB_ORDER,
    TAB_COLOR_EXECUTIVE,
    VISIBLE_WORKBOOK_TAB_ORDER,
    _SHEET_TAB_COLORS,
    apply_workbook_tab_layout,
)


def test_visible_tab_order_matches_workflow_spec() -> None:
    visible = [n for n in VISIBLE_WORKBOOK_TAB_ORDER if n != "Table of Contents"]
    assert visible[:7] == [
        "Dashboard",
        "Executive Dashboard",
        "Summary",
        "Priority URLs",
        "FixPlan",
        "Quick Wins",
        CONTENT_OPTIMISATION_HUB_SHEET,
    ]
    assert visible[8] == "Main"
    assert visible[10] == "Link Inventory"
    assert visible[11] == "Broken Link Impact"
    assert visible[12] == "SitemapQA"
    assert AIOSEO_RECOMMENDATIONS_SHEET in visible
    assert visible[-1] == "Playbook"


def test_advanced_tabs_hidden_by_default() -> None:
    assert "Technical Diagnostics" in HIDDEN_SHEETS_BY_DEFAULT
    assert AUDIT_RUN_DETAILS_SHEET in HIDDEN_SHEETS_BY_DEFAULT
    assert "Dashboard" not in HIDDEN_SHEETS_BY_DEFAULT
    assert "Summary" not in HIDDEN_SHEETS_BY_DEFAULT


def test_apply_workbook_tab_layout_orders_colors_and_hides() -> None:
    wb = Workbook()
    wb.active.title = "Main"
    for name in (
        "Dashboard",
        "Technical Diagnostics",
        AUDIT_RUN_DETAILS_SHEET,
        "Playbook",
    ):
        wb.create_sheet(name)
    apply_workbook_tab_layout(wb)
    titles = [ws.title for ws in wb.worksheets]
    assert titles.index("Dashboard") < titles.index("Main")
    assert titles.index("Playbook") < titles.index("Technical Diagnostics")
    dash_color = str(wb["Dashboard"].sheet_properties.tabColor.rgb or "")
    assert dash_color.upper().endswith(TAB_COLOR_EXECUTIVE.upper())
    assert wb["Technical Diagnostics"].sheet_state == "hidden"
    assert len(PREFERRED_WORKBOOK_TAB_ORDER) == len(set(PREFERRED_WORKBOOK_TAB_ORDER))


def test_all_ordered_tabs_have_a_tab_colour() -> None:
    """Every preferred tab except the TOC must carry a group tab colour (P1.6)."""
    for name in PREFERRED_WORKBOOK_TAB_ORDER:
        if name == "Table of Contents":
            continue
        assert name in _SHEET_TAB_COLORS, f"{name!r} has no tab colour"


def test_advanced_inventory_sheets_have_tab_colours() -> None:
    """The six advanced inventory sheets previously defaulted to grey (P1.6)."""
    for name in (
        LINK_EQUITY_MAP_SHEET,
        ANCHOR_TEXT_AUDIT_SHEET,
        SNIPPET_OPPORTUNITIES_SHEET,
        COMPETITOR_BENCHMARKS_SHEET,
        SCRIPT_INVENTORY_SHEET,
        IMAGE_INVENTORY_SHEET,
    ):
        assert name in ADVANCED_WORKBOOK_TAB_ORDER
        assert name in _SHEET_TAB_COLORS
