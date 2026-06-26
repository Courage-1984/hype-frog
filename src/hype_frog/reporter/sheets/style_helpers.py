from __future__ import annotations

from typing import Any

from openpyxl.worksheet.worksheet import Worksheet


def header_index(worksheet: Worksheet) -> dict[str, int]:
    return {
        str(cell.value): idx
        for idx, cell in enumerate(worksheet[1], start=1)
        if cell.value
    }


def header_exists_in_worksheet(worksheet: Worksheet, header_name: str) -> bool:
    """Return True when ``header_name`` already exists in row 1."""
    for cell in worksheet[1]:
        if cell.value == header_name:
            return True
    return False


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


__all__ = ["header_exists_in_worksheet", "header_index", "to_int"]
