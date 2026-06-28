from __future__ import annotations

from collections.abc import Callable

from openpyxl.comments import Comment
from openpyxl.worksheet.worksheet import Worksheet

from hype_frog.reporter.sheets.validation import (
    SCHEMA_METADATA_HEADER_TOOLTIP_BODIES,
    apply_comment_dimensions,
)


def add_schema_header_tooltips(
    worksheet: Worksheet,
    *,
    disable_data_validation: bool,
    header_index_fn: Callable[[Worksheet], dict[str, int]],
) -> None:
    if disable_data_validation:
        return
    author = "hype-frog"
    headers = header_index_fn(worksheet)
    for header, message in SCHEMA_METADATA_HEADER_TOOLTIP_BODIES.items():
        col_idx = headers.get(header)
        if not col_idx:
            continue
        cell = worksheet.cell(row=1, column=col_idx)
        text = f"{header}\n\n{message}"
        comment = Comment(text, author)
        apply_comment_dimensions(comment)
        cell.comment = comment


__all__ = ["add_schema_header_tooltips"]
