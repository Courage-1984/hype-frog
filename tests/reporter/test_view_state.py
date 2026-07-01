"""View-state and bespoke freeze contracts."""

from __future__ import annotations

from openpyxl import Workbook

from hype_frog.reporter.engine_guardrails import apply_bespoke_freeze_panes
from hype_frog.reporter.sheets.config import CONTENT_PLANNER_SHEET
from hype_frog.reporter.sheets.view_state import apply_optimal_view_state


def test_content_planner_optimal_view_state_freezes_e2() -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = CONTENT_PLANNER_SHEET
    ws.append(["Primary", "Secondary", "Tertiary", "Page link", "Copy Doc"])
    ws.append(["Home", "", "", "https://example.com/", ""])

    apply_optimal_view_state(ws, CONTENT_PLANNER_SHEET)
    assert ws.freeze_panes == "E2"


def test_bespoke_freeze_repairs_corrupted_content_planner_pane() -> None:
    """Regression: production workbooks showed freeze at E194 after formatting passes."""
    wb = Workbook()
    ws = wb.active
    ws.title = CONTENT_PLANNER_SHEET
    ws.append(["Primary", "Secondary", "Tertiary", "Page link"])
    ws.freeze_panes = "E194"

    apply_bespoke_freeze_panes(wb)
    assert wb[CONTENT_PLANNER_SHEET].freeze_panes == "E2"
