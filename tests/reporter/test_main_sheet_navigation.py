"""Main sheet navigation columns must not duplicate on repeated formatting."""

from __future__ import annotations

from openpyxl import Workbook

from hype_frog.reporter.sheets.links import apply_cross_sheet_links
from hype_frog.reporter.sheets.navigation import add_back_to_dashboard_link
from hype_frog.reporter.sheets.style_helpers import header_index
from hype_frog.reporter.sheets.tables import normalize_table_headers


class _WriterStub:
    def __init__(self, book: Workbook) -> None:
        self.book = book


def _main_headers(worksheet) -> list[str]:
    return [
        str(worksheet.cell(row=1, column=c).value or "")
        for c in range(1, worksheet.max_column + 1)
    ]


def _build_main_workbook() -> tuple[_WriterStub, Workbook]:
    wb = Workbook()
    ws = wb.active
    ws.title = "Main"
    ws.cell(row=1, column=1, value="URL")
    ws.cell(row=1, column=2, value="SEO Health Score")
    ws.cell(row=2, column=1, value="https://example.com/page-a")
    ws.cell(row=2, column=2, value=72.0)
    ws.cell(row=3, column=1, value="https://example.com/page-b")
    ws.cell(row=3, column=2, value=65.0)
    wb.create_sheet("Technical Diagnostics")
    wb.create_sheet("Dashboard")
    return _WriterStub(wb), wb


def test_main_navigation_columns_survive_double_format_pass() -> None:
    """Simulate export_flow calling adjust_sheet_format twice on Main."""
    writer, wb = _build_main_workbook()
    ws = wb["Main"]

    for _ in range(2):
        apply_cross_sheet_links(
            writer,
            ws,
            "Main",
            debug_excel_isolation_mode=False,
            header_index_fn=header_index,
        )
        add_back_to_dashboard_link(ws, "Main")
        normalize_table_headers(ws, header_row=1)

    headers = _main_headers(ws)
    assert headers.count("Technical View") == 1
    assert headers.count("BACK TO DASHBOARD") == 1
    assert not any(h.endswith("_1") for h in headers)

    tech_col = header_index(ws)["Technical View"]
    assert str(ws.cell(row=2, column=tech_col).value or "").startswith("=IFERROR(HYPERLINK")
    back_col = header_index(ws)["BACK TO DASHBOARD"]
    assert ws.cell(row=1, column=back_col).hyperlink is not None


def test_back_to_dashboard_skips_when_header_already_present() -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.cell(row=1, column=1, value="Section")
    ws.cell(row=1, column=2, value="BACK TO DASHBOARD")

    add_back_to_dashboard_link(ws, "Summary")

    assert ws.max_column == 2
    assert _main_headers(ws).count("BACK TO DASHBOARD") == 1
