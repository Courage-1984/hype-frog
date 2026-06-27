from __future__ import annotations

from typing import Any

from openpyxl.worksheet.worksheet import Worksheet


def header_index(worksheet: Worksheet) -> dict[str, int]:
    return {
        str(cell.value): idx
        for idx, cell in enumerate(worksheet[1], start=1)
        if cell.value
    }


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


__all__ = ["header_index", "to_int"]
