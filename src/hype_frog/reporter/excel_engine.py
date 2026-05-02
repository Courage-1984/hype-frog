"""
Post-export workbook guardrails (openpyxl).

Applies frozen policy for Action Required cells, TOC descriptions, and freeze panes.
Intended to run after pandas/openpyxl writes and after tab hyperlink pass.
"""

from __future__ import annotations

from typing import Iterable

from openpyxl.styles import Font, PatternFill
from openpyxl.workbook.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

_BANNED_TOC_FALLBACK = "Detailed URL diagnostic data"
_RED = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
_BOLD = Font(bold=True)


def _header_map(ws: Worksheet, row: int = 1) -> dict[str, int]:
    out: dict[str, int] = {}
    for cell in ws[row]:
        val = cell.value
        if val is None:
            continue
        key = str(val).strip()
        if key:
            out[key] = cell.column
    return out


def _describe_sheet_from_headers(ws: Worksheet, *, max_labels: int = 10, max_chars: int = 220) -> str:
    labels: list[str] = []
    for cell in ws[1]:
        v = cell.value
        if v is None:
            continue
        s = str(v).strip()
        if s:
            labels.append(s)
        if len(labels) >= max_labels:
            break
    if not labels:
        return "Row-level metrics for this tab (no header row detected)."
    body = ", ".join(labels)
    text = f"Primary columns: {body}"
    if len(text) > max_chars:
        return text[: max_chars - 1].rstrip() + "…"
    return text


def apply_action_required_guardrails(ws: Worksheet, *, header_row: int = 1) -> None:
    """
    For the **Action Required** column: any non-empty cell (data rows) becomes the
    literal ``Needs Copy`` with bold font and solid red fill (``FF0000``).
    """
    headers = _header_map(ws, header_row)
    col = headers.get("Action Required")
    if not col:
        return
    for r in range(header_row + 1, ws.max_row + 1):
        cell = ws.cell(row=r, column=col)
        raw = cell.value
        if raw is None:
            continue
        if isinstance(raw, str) and not raw.strip():
            continue
        cell.value = "Needs Copy"
        cell.font = _BOLD
        cell.fill = _RED


def refresh_toc_descriptions_dynamic(wb: Workbook) -> None:
    """
    Replace generic TOC description text with labels derived from each target
    sheet's first-row headers (never uses the banned fallback string).
    """
    if "Table of Contents" not in wb.sheetnames:
        return
    toc = wb["Table of Contents"]
    row = 3
    while row <= toc.max_row:
        name_cell = toc.cell(row=row, column=1)
        desc_cell = toc.cell(row=row, column=3)
        sheet_name = name_cell.value
        if not sheet_name:
            row += 1
            continue
        name = str(sheet_name).strip()
        if name not in wb.sheetnames:
            row += 1
            continue
        target = wb[name]
        desc_cell.value = _describe_sheet_from_headers(target)
        cur = str(desc_cell.value or "")
        if _BANNED_TOC_FALLBACK.lower() in cur.lower():
            desc_cell.value = _describe_sheet_from_headers(target)
        row += 1


def apply_freeze_c2_data_sheets(wb: Workbook, *, skip_names: Iterable[str] | None = None) -> None:
    """Freeze top row and first two columns (pane at ``C2``) on all sheets except skips."""
    skip = frozenset(skip_names or ("Table of Contents",))
    for name in wb.sheetnames:
        if name in skip:
            continue
        ws = wb[name]
        ws.freeze_panes = "C2"


def apply_workbook_export_guardrails(wb: Workbook) -> None:
    """Run Action Required rules on every sheet, refresh TOC text, then freeze data sheets."""
    for name in wb.sheetnames:
        if name == "Table of Contents":
            continue
        apply_action_required_guardrails(wb[name])
    refresh_toc_descriptions_dynamic(wb)
    apply_freeze_c2_data_sheets(wb)


__all__ = [
    "apply_action_required_guardrails",
    "apply_freeze_c2_data_sheets",
    "apply_workbook_export_guardrails",
    "refresh_toc_descriptions_dynamic",
]
