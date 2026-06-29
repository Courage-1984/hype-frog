"""Content Optimisation Hub header row survives banner + scope-note layout."""

from __future__ import annotations

import openpyxl

from hype_frog.reporter.engine_rows import CONTENT_HUB_EXPORT_COLUMNS
from hype_frog.reporter.sheets.conditional import apply_content_hub_conditional_rules
from hype_frog.reporter.sheets.config import CONTENT_OPTIMISATION_HUB_SHEET


def test_content_hub_row2_retains_column_headers_after_banner_insert() -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = CONTENT_OPTIMISATION_HUB_SHEET
    columns = list(CONTENT_HUB_EXPORT_COLUMNS)
    ws.append(columns)
    scope_row: list[object | None] = [None] * len(columns)
    scope_row[0] = "Scope note: diagnostic pages only."
    ws.append(scope_row)
    data_row: list[object | None] = [None] * len(columns)
    data_row[columns.index("Action Required")] = "Needs Copy"
    data_row[columns.index("URL")] = "https://example.com/about/"
    ws.append(data_row)

    class _Writer:
        book = wb
        sheets = {CONTENT_OPTIMISATION_HUB_SHEET: ws}

    apply_content_hub_conditional_rules(ws, _Writer())

    header_values = [
        ws.cell(row=2, column=col_idx).value
        for col_idx in range(1, len(columns) + 1)
    ]
    assert header_values == columns
    assert ws.cell(row=3, column=1).value == "Scope note: diagnostic pages only."
    assert ws.max_row >= 4
    url_col = columns.index("URL") + 1
    assert ws.cell(row=4, column=url_col).value == "https://example.com/about/"
