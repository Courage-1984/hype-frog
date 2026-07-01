from __future__ import annotations

from typing import Any

from openpyxl.worksheet.worksheet import Worksheet

from hype_frog.core import get_logger

logger = get_logger(__name__)


def header_index(worksheet: Worksheet, header_row: int = 1) -> dict[str, int]:
    return header_row_index(worksheet, header_row)


def header_row_index(worksheet: Worksheet, header_row: int = 1) -> dict[str, int]:
    """Map normalised header labels to 1-based column indices on ``header_row``."""
    out: dict[str, int] = {}
    for idx, cell in enumerate(worksheet[header_row], start=1):
        if cell.value is None:
            continue
        label = str(cell.value).strip()
        if label:
            out[label] = idx
    return out


def header_exists_in_worksheet(
    worksheet: Worksheet, header_name: str, *, header_row: int = 1
) -> bool:
    """Return True when ``header_name`` already exists on ``header_row``."""
    for cell in worksheet[header_row]:
        if cell.value == header_name:
            return True
    return False


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception as exc:
        logger.debug("Could not coerce %r to int: %s", value, exc)
        return default


_NUMERIC_HEADER_TOKENS: tuple[str, ...] = (
    "score",
    "count",
    "%",
    "hours",
    "points",
    "depth",
    "size",
    "length",
    "ctr",
    "clicks",
    "impressions",
    "position",
    "code",
    "rank",
    "ratio",
    "days",
    " ms",
    "(s)",
    "ttfb",
    "lcp",
    "cls",
    "inp",
    "fcp",
    "kb",
)


def header_suggests_numeric_alignment(header: object) -> bool:
    """Heuristic: right-align headers that typically sit above numeric cells."""
    text = str(header or "").lower()
    return any(token in text for token in _NUMERIC_HEADER_TOKENS)


__all__ = [
    "header_exists_in_worksheet",
    "header_index",
    "header_row_index",
    "header_suggests_numeric_alignment",
    "to_int",
]
