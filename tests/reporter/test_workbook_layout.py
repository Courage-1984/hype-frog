"""Workbook tab order, colours, and default visibility."""

from __future__ import annotations

from openpyxl import Workbook

from hype_frog.reporter.sheets.config import (
    AIOSEO_RECOMMENDATIONS_SHEET,
    AUDIT_RUN_DETAILS_SHEET,
    CONTENT_HUB_METRICS_SHEET,
    CONTENT_OPTIMISATION_HUB_SHEET,
)
from hype_frog.reporter.sheets.workbook_layout import (
    HIDDEN_SHEETS_BY_DEFAULT,
    PREFERRED_WORKBOOK_TAB_ORDER,
    TAB_COLOR_ACTIONABLE,
    TAB_COLOR_EXECUTIVE,
    VISIBLE_WORKBOOK_TAB_ORDER,
    apply_workbook_tab_layout,
)


def test_visible_tab_order_matches_workflow_spec() -> None:
    visible = [n for n in VISIBLE_WORKBOOK_TAB_ORDER if n != "Table of Contents"]
    assert visible[:6] == [
        "Dashboard",
        "Executive Dashboard",
        "Summary",
        "Priority URLs",
        "FixPlan",
        CONTENT_OPTIMISATION_HUB_SHEET,
    ]
    assert visible[7] == "Main"
    assert visible[9] == "Link Inventory"
    assert visible[10] == "SitemapQA"
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
