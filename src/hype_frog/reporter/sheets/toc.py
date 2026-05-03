from __future__ import annotations

from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.views import Selection

from hype_frog.reporter.excel_engine import friendly_toc_description


def apply_workbook_toc_and_links(
    writer,
    *,
    debug_excel_isolation_mode: bool,
    disable_non_core_freeze_panes: bool,
    std_navy: str,
    std_white: str,
    std_blue: str,
) -> None:
    def _sheet_link_target(name: str) -> str:
        return str(name).replace("'", "''")

    def _clear_orphaned_selection(ws) -> None:
        try:
            ws.views.sheetView[0].selection = []
        except Exception:
            pass

    def _set_freeze_panes_safe(ws, value: str | None) -> None:
        view = ws.views.sheetView[0]
        if not view.selection:
            view.selection = [Selection(activeCell="A1", sqref="A1")]
        ws.freeze_panes = value

    if debug_excel_isolation_mode:
        return
    wb = writer.book
    wb.calculation.calcMode = "auto"
    if "Table of Contents" not in wb.sheetnames:
        toc_ws = wb.create_sheet("Table of Contents")
        toc_ws["A1"] = "Table of Contents"
        toc_ws["A1"].font = Font(color=std_navy, bold=True, size=14)
        toc_ws["A2"] = "Section"
        toc_ws["B2"] = "Open"
        toc_ws["C2"] = "Description"
        toc_ws["A2"].fill = PatternFill("solid", fgColor=std_navy)
        toc_ws["B2"].fill = PatternFill("solid", fgColor=std_navy)
        toc_ws["C2"].fill = PatternFill("solid", fgColor=std_navy)
        toc_ws["A2"].font = Font(color=std_white, bold=True)
        toc_ws["B2"].font = Font(color=std_white, bold=True)
        toc_ws["C2"].font = Font(color=std_white, bold=True)
        row_ptr = 3
        for sheet_name in wb.sheetnames:
            if sheet_name == "Table of Contents":
                continue
            toc_ws[f"A{row_ptr}"] = sheet_name
            toc_ws[f"B{row_ptr}"] = f'=HYPERLINK("#\'{_sheet_link_target(sheet_name)}\'!A1","Open")'
            toc_ws[f"C{row_ptr}"] = friendly_toc_description(sheet_name)
            toc_ws[f"B{row_ptr}"].font = Font(
                color=std_blue, underline="single", bold=True
            )
            row_ptr += 1
        toc_ws.column_dimensions["A"].width = 35
        toc_ws.column_dimensions["B"].width = 18
        toc_ws.column_dimensions["C"].width = 70
        toc_ws.freeze_panes = "A3"
    link_map = {
        "Summary": "Reference Tab",
        "FixPlan": "Reference Tab",
        "Dashboard": "Target Tab",
        "AIOSEO": "Reference Tab",
        "IssueInventory": "Reference Tab",
    }
    for sheet_name, col_header in link_map.items():
        if sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]
        headers = [c.value for c in ws[1]]
        if col_header not in headers:
            continue
        col_idx = headers.index(col_header) + 1
        for row_idx in range(2, ws.max_row + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            target = str(cell.value or "").strip()
            if target and target in wb.sheetnames:
                cell.hyperlink = f"#{target}!A1"
                cell.style = "Hyperlink"
    preferred_first_tabs = [
        "Table of Contents",
        "Dashboard",
        "Content Optimization Hub",
        "Quick Reference Guide",
        "FixPlan",
        "Main",
        "Technical",
        "Content",
        "AEO",
        "Schema & Metadata",
        "Links",
        "Indexability",
        "Redirects",
        "Priority URLs",
        "AIOSEO",
        "Security",
        "Summary",
        "LinksDetail",
        "Media",
        "Duplicates",
        "Pattern and Template Issues",
        "PSI Performance",
        "IssueInventory",
        "CrawlGraph",
        "SitemapQA",
        "DeltaFromPreviousRun",
        "RunMetadata",
    ]
    legend_name = "Glossary & Legend"
    if legend_name in wb.sheetnames and legend_name not in preferred_first_tabs:
        preferred_first_tabs.append(legend_name)
    for idx, tab_name in enumerate(preferred_first_tabs):
        if tab_name in wb.sheetnames:
            wb.move_sheet(wb[tab_name], offset=-wb.index(wb[tab_name]) + idx)
    if legend_name in wb.sheetnames:
        wb.move_sheet(
            wb[legend_name], offset=len(wb.sheetnames) - 1 - wb.index(wb[legend_name])
        )
    low_signal_tabs = {"RunMetadata", "DeltaFromPreviousRun"}
    for tab_name in low_signal_tabs:
        if tab_name in wb.sheetnames:
            wb[tab_name].sheet_state = "hidden"
    for tab_name in wb.sheetnames:
        ws = wb[tab_name]
        if disable_non_core_freeze_panes and tab_name not in {"Main", "Dashboard"}:
            _set_freeze_panes_safe(ws, None)
            _clear_orphaned_selection(ws)
            continue
        if tab_name not in {"Main", "Dashboard"} and (
            ws.max_row < 10 or ws.max_column < 5
        ):
            _set_freeze_panes_safe(ws, None)
            ws.auto_filter.ref = None
            _clear_orphaned_selection(ws)
            continue
        wide_sheets = {
            "Main",
            "Technical",
            "Content Optimization Hub",
            "FixPlan",
            "Content",
            "Links",
            "Schema & Metadata",
            "Indexability",
            "Priority URLs",
            "AEO",
            "Redirects",
            "AIOSEO",
            "Security",
            "Summary",
            "LinksDetail",
            "Media",
            "Pattern and Template Issues",
            "Duplicates",
            "PSI Performance",
            "IssueInventory",
            "RunMetadata",
            "DeltaFromPreviousRun",
            "ResolvedIssues",
            "CrawlGraph",
            "SitemapQA",
        }
        standard_data_sheets = {
            "Content",
            "Links",
            "Schema & Metadata",
            "Indexability",
            "Priority URLs",
        }
        if tab_name == "Content Optimization Hub":
            target_freeze = "C3" if ws.max_row >= 3 and ws.max_column >= 3 else None
            _set_freeze_panes_safe(ws, target_freeze)
        elif tab_name in standard_data_sheets:
            target_freeze = "B2" if ws.max_row >= 2 and ws.max_column >= 2 else None
            _set_freeze_panes_safe(ws, target_freeze)
        elif tab_name in wide_sheets:
            target_freeze = "C2" if ws.max_row >= 2 and ws.max_column >= 3 else None
            _set_freeze_panes_safe(ws, target_freeze)
