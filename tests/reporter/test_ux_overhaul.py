"""Excel Report UX Overhaul regression guards.

Covers the column-width contract, single-line URL policy, empty-state
messaging, the phantom ``Column_4`` fix, and the non-overlapping Executive
Briefing chart grid.
"""

from __future__ import annotations

import pytest
from openpyxl import Workbook

from hype_frog.reporter.sheets import executive_dashboard as ed
from hype_frog.reporter.sheets.config import RETURN_TO_BRIEFING_LABEL
from hype_frog.reporter.sheets.layout import (
    PROSE_HEADERS,
    URL_LIKE_HEADERS,
    _MAX_COL_WIDTH,
    _MIN_COL_WIDTH,
    _PROSE_COL_WIDTH,
    _URL_COL_WIDTH,
    apply_column_widths,
)
from hype_frog.reporter.sheets.navigation import add_return_to_briefing_strip
from hype_frog.reporter.sheets.sheet_rows import sheet_data_header_row
from hype_frog.reporter.sheets.tables import normalize_table_headers
from hype_frog.reporter.sheets.tables_impl import (
    _EMPTY_STATE_MESSAGE,
    _write_empty_state_message,
)


def _banner_sheet(title: str) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = title
    return wb


def test_apply_column_widths_assigns_widths_and_url_single_line() -> None:
    wb = _banner_sheet("Summary")
    ws = wb.active
    hr = sheet_data_header_row("Summary")
    assert hr == 2
    ws.cell(row=1, column=1, value=RETURN_TO_BRIEFING_LABEL)
    ws.cell(row=hr, column=1, value="URL")
    ws.cell(row=hr, column=2, value="Issue")
    ws.cell(row=hr, column=3, value="Why It Matters")
    ws.cell(
        row=hr + 1,
        column=1,
        value="https://example.org/a/very/long/path/that/would/wrap/badly",
    )
    ws.cell(row=hr + 1, column=2, value="Broken link")
    ws.cell(row=hr + 1, column=3, value="x" * 200)

    apply_column_widths(ws)

    # URL columns are a fixed single-line width, never content-driven.
    assert ws.column_dimensions["A"].width == pytest.approx(_URL_COL_WIDTH)
    # Long prose columns get the generous wrapped width, capped.
    assert ws.column_dimensions["C"].width == pytest.approx(_PROSE_COL_WIDTH)
    # Ordinary columns get a concrete, clamped width (the old routine left None).
    width_b = ws.column_dimensions["B"].width
    assert width_b is not None
    assert _MIN_COL_WIDTH <= width_b <= _MAX_COL_WIDTH


def test_apply_column_widths_reads_resolved_header_row_not_row_one() -> None:
    wb = _banner_sheet("Priority URLs")
    ws = wb.active
    ws.cell(row=1, column=1, value=RETURN_TO_BRIEFING_LABEL)
    ws.cell(row=2, column=1, value="URL")
    ws.cell(row=3, column=1, value="https://example.org/")
    apply_column_widths(ws)
    # If the pass had assumed row 1 it would never recognise the URL header.
    assert ws.column_dimensions["A"].width == pytest.approx(_URL_COL_WIDTH)


def test_url_and_prose_header_sets_are_disjoint() -> None:
    assert not (URL_LIKE_HEADERS & PROSE_HEADERS)


def test_empty_state_message_written_under_headers() -> None:
    wb = Workbook()
    ws = wb.active
    ws.cell(row=1, column=1, value=RETURN_TO_BRIEFING_LABEL)
    ws.cell(row=2, column=1, value="Issue Type")
    ws.cell(row=2, column=2, value="Severity")
    ws.cell(row=2, column=3, value="Affected Count")

    _write_empty_state_message(ws, header_row=2)

    assert ws.cell(row=3, column=1).value == _EMPTY_STATE_MESSAGE
    assert ws.cell(row=3, column=1).font.italic is True


def test_empty_state_message_skipped_when_data_present() -> None:
    wb = Workbook()
    ws = wb.active
    ws.cell(row=2, column=1, value="Issue Type")
    ws.cell(row=3, column=1, value="Broken internal link")

    _write_empty_state_message(ws, header_row=2)

    assert ws.cell(row=3, column=1).value == "Broken internal link"


def test_narrow_banner_sheet_has_no_phantom_column_4() -> None:
    wb = _banner_sheet("FixPlan")
    ws = wb.active
    ws.cell(row=1, column=1, value="Issue Type")
    ws.cell(row=1, column=2, value="Severity")
    ws.cell(row=1, column=3, value="Affected Count")

    add_return_to_briefing_strip(ws, "FixPlan")
    normalize_table_headers(ws, header_row=2)

    headers = [ws.cell(row=2, column=c).value for c in range(1, ws.max_column + 1)]
    assert "Column_4" not in headers
    assert ws.max_column == 3


def test_executive_briefing_chart_bands_do_not_overlap() -> None:
    bands = [
        ed._ROW_CH_HEALTH,
        ed._ROW_CH_ISSUES,
        ed._ROW_CH_ACTIONS,
        ed._ROW_CH_TOP_ISSUES,
    ]
    # Each chart is ~8.4 cm tall (~16-17 rows); require a clear gap between bands.
    for upper, lower in zip(bands, bands[1:]):
        assert lower - upper >= 17
    # The triage matrix sits below the final chart band, and the chart source
    # tables sit below the triage matrix.
    assert ed._BRIEFING_TRIAGE_START_ROW >= bands[-1] + 17
    assert ed.CHART_SOURCE_FIRST_ROW > ed._BRIEFING_TRIAGE_START_ROW
