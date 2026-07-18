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
    """Regression: production workbooks showed freeze at E194 after formatting passes.

    ``apply_bespoke_freeze_panes`` runs late in the export, after the row-1 return
    strip has been inserted and the column headers pushed to row 2, so the contract
    is ``E3`` — columns A–D plus the banner+header rows (1–2). ``E2`` (the pre-insert
    value) froze only the banner and let the headers scroll away.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = CONTENT_PLANNER_SHEET
    ws.append(["← Return to Executive Briefing"])  # row 1 banner (return strip)
    ws.append(["Primary", "Secondary", "Tertiary", "Page link"])  # row 2 headers
    ws.freeze_panes = "E194"

    apply_bespoke_freeze_panes(wb)
    assert wb[CONTENT_PLANNER_SHEET].freeze_panes == "E3"
