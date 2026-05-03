from __future__ import annotations

from typing import Any

from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from hype_frog.reporter.sheets.config import (
    DEBUG_EXCEL_ISOLATION_MODE,
    DISABLE_EXTERNAL_LINKS_AND_IMAGES,
    STD_BLUE,
)
from hype_frog.reporter.sheets.links import (
    add_url_navigation_links as add_url_navigation_links_impl,
    apply_cross_sheet_links as apply_cross_sheet_links_impl,
)
from hype_frog.reporter.sheets.utils import header_index


def add_back_to_dashboard_link(worksheet: Worksheet, sheet_name: str) -> None:
    """Append a dashboard return hyperlink in the first row.

    Args:
        worksheet: Worksheet receiving the helper hyperlink.
        sheet_name: Current worksheet name used for exclusions.
    """
    if DEBUG_EXCEL_ISOLATION_MODE:
        return
    if sheet_name == "Dashboard":
        return
    target_col = worksheet.max_column + 1
    target_ref = f"{get_column_letter(target_col)}1"
    worksheet[target_ref] = "BACK TO DASHBOARD"
    worksheet[target_ref].hyperlink = "#'Dashboard'!A1"
    worksheet[target_ref].style = "Hyperlink"
    worksheet[target_ref].font = Font(color=STD_BLUE, underline="single", bold=True)
    worksheet[target_ref].alignment = Alignment(horizontal="left")


def add_url_navigation_links(
    writer: Any, worksheet: Worksheet, sheet_name: str
) -> None:
    """Delegate URL/link column generation to link helpers.

    Args:
        writer: Pandas ExcelWriter-like object.
        worksheet: Active worksheet.
        sheet_name: Current worksheet name.
    """
    add_url_navigation_links_impl(
        writer,
        worksheet,
        sheet_name,
        debug_excel_isolation_mode=DEBUG_EXCEL_ISOLATION_MODE,
        disable_external_links_and_images=DISABLE_EXTERNAL_LINKS_AND_IMAGES,
        header_index_fn=header_index,
    )


def apply_cross_sheet_links(
    writer: Any, worksheet: Worksheet, sheet_name: str
) -> None:
    """Delegate cross-sheet link generation with project defaults.

    Args:
        writer: Pandas ExcelWriter-like object.
        worksheet: Active worksheet.
        sheet_name: Current worksheet name.
    """
    apply_cross_sheet_links_impl(
        writer,
        worksheet,
        sheet_name,
        debug_excel_isolation_mode=DEBUG_EXCEL_ISOLATION_MODE,
        header_index_fn=header_index,
    )


__all__ = [
    "add_back_to_dashboard_link",
    "add_url_navigation_links",
    "apply_cross_sheet_links",
]
