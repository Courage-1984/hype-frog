"""Header/data row resolution for standard workbook sheets (no I/O)."""

from __future__ import annotations

from hype_frog.reporter.sheets.config import (
    CONTENT_HUB_DATA_START_ROW,
    CONTENT_OPTIMISATION_HUB_SHEET,
    EXECUTIVE_BRIEFING_SHEET,
)

_RETURN_STRIP_EXEMPT_SHEETS: frozenset[str] = frozenset(
    {
        "Dashboard",
        EXECUTIVE_BRIEFING_SHEET,
        "Table of Contents",
        CONTENT_OPTIMISATION_HUB_SHEET,
    }
)


def sheet_uses_return_strip(sheet_name: str) -> bool:
    """Whether export inserts a row-1 return strip before the data header row."""
    return sheet_name not in _RETURN_STRIP_EXEMPT_SHEETS


def sheet_data_header_row(sheet_name: str) -> int:
    """1-based row index of column headers on standard data sheets."""
    if sheet_name == CONTENT_OPTIMISATION_HUB_SHEET:
        return 2
    if sheet_uses_return_strip(sheet_name):
        return 2
    return 1


def sheet_data_start_row(sheet_name: str) -> int:
    """First row of URL/data records (below headers)."""
    if sheet_name == CONTENT_OPTIMISATION_HUB_SHEET:
        return CONTENT_HUB_DATA_START_ROW
    return sheet_data_header_row(sheet_name) + 1


__all__ = [
    "sheet_data_header_row",
    "sheet_data_start_row",
    "sheet_uses_return_strip",
]
