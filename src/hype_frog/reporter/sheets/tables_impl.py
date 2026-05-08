from __future__ import annotations

from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import coordinate_to_tuple
from openpyxl.worksheet.datavalidation import DataValidation

from hype_frog.reporter.engine_formatting import (
    apply_fixplan_workflow_formatting,
    ensure_auto_filter,
    ensure_freeze_header,
)
from hype_frog.reporter.engine_guardrails import apply_header_tooltips
from hype_frog.reporter.sheets.toc import apply_workbook_toc_and_links
from hype_frog.reporter.sheets.conditional import (
    apply_content_hub_conditional_rules,
    apply_generic_sheet_coloring,
    apply_main_sheet_heatmaps,
    apply_psi_conditional_rules,
    apply_sheet_text_wrap_columns,
    apply_wrapped_row_heights,
    finalize_content_hub_after_normalized_headers,
)
from hype_frog.reporter.sheets.config import (
    CONTENT_OPTIMISATION_HUB_SHEET,
    DATA_HEAVY_TABS,
    DEBUG_EXCEL_ISOLATION_MODE,
    DISABLE_DATA_VALIDATION,
    DISABLE_EXTERNAL_LINKS_AND_IMAGES,
    DISABLE_NON_CORE_FREEZE_PANES,
    STD_BLUE,
    STD_NAVY,
    STD_WHITE,
)
from hype_frog.reporter.sheets.dashboard import style_dashboard
from hype_frog.reporter.sheets.layout import (
    MAIN_COLUMN_GROUP_DEFINITIONS,
    apply_column_grouping,
    apply_column_widths,
    apply_intelligent_sorting,
    hide_noisy_columns,
    reorder_columns,
)
from hype_frog.reporter.sheets.links import apply_editor_url_column_hyperlinks
from hype_frog.reporter.sheets.navigation import (
    add_back_to_dashboard_link,
    add_url_navigation_links,
    apply_cross_sheet_links,
)
from hype_frog.reporter.sheets.number_formats import apply_south_african_formats
from hype_frog.reporter.sheets.tables import (
    apply_mock_table_styling,
    compute_exact_table_ref,
    normalize_table_headers,
)
from hype_frog.reporter.sheets.technical import collapse_technical_deep_dive_columns
from hype_frog.reporter.sheets.validation import (
    add_all_header_tooltips,
    add_header_tooltips,
    apply_status_dropdown,
    apply_status_dropdown_to_inventory,
)
from hype_frog.reporter.sheets.view_state import (
    apply_optimal_view_state,
    audit_freeze_merge_conflicts,
    audit_non_overlapping_merges,
    sanitize_sheet_view_selection,
    set_freeze_panes_safe,
)
from hype_frog.reporter.sheets.style_helpers import header_index

_COPY_HUB_WIDE_HEADERS: frozenset[str] = frozenset(
    {
        "Current Title",
        "Proposed Title (50-60 Chars)",
        "Title Count",
        "Current Meta Desc",
        "Proposed Meta Desc (120-160 Chars)",
        "Desc Count",
        "Current H-Tag Structure",
        "Proposed H-Tag Fixes",
        "Current Page Copy Snippet",
        "AEO Answer Block Draft",
        "FAQ/QA Draft",
        "Current OG-Image URL",
        "Social Share Note",
        "Target Keywords",
    }
)


def _hub_headers_row2(worksheet) -> dict[str, int]:
    return {
        str(c.value).strip(): i for i, c in enumerate(worksheet[2], start=1) if c.value
    }


def _apply_content_hub_assigned_owner_validation(worksheet) -> None:
    if DISABLE_DATA_VALIDATION:
        return
    headers = _hub_headers_row2(worksheet)
    col = headers.get("Assigned Owner")
    if not col or worksheet.max_row < 3:
        return
    letter = get_column_letter(col)
    dv = DataValidation(
        type="list",
        formula1='"Copy Writer,Developer,Server/Host"',
        allow_blank=False,
        showErrorMessage=True,
        errorTitle="Invalid owner",
        error="Choose Copy Writer, Developer, or Server/Host.",
    )
    dv.errorStyle = "stop"
    worksheet.add_data_validation(dv)
    dv.add(f"{letter}3:{letter}{worksheet.max_row}")


def _apply_content_hub_copywriter_column_layout(worksheet) -> None:
    headers = _hub_headers_row2(worksheet)
    for name, col_idx in headers.items():
        low = name.lower()
        if name in _COPY_HUB_WIDE_HEADERS or "proposed" in low:
            letter = get_column_letter(col_idx)
            cur = worksheet.column_dimensions[letter].width or 8.0
            worksheet.column_dimensions[letter].width = max(45.0, float(cur))
    header_lower_by_col: dict[int, str] = {
        col_idx: str(name).lower() for name, col_idx in headers.items()
    }
    for r in range(3, worksheet.max_row + 1):
        for c in range(1, worksheet.max_column + 1):
            cell = worksheet.cell(row=r, column=c)
            prev = cell.alignment
            h = prev.horizontal if prev else "left"
            hdr_low = header_lower_by_col.get(c, "")
            wrap = "proposed" in hdr_low
            cell.alignment = Alignment(horizontal=h, vertical="top", wrap_text=wrap)


def adjust_sheet_format(writer, sheet_name):
    worksheet = writer.sheets[sheet_name]
    reorder_columns(worksheet, sheet_name)
    if sheet_name == "Main":
        apply_column_grouping(worksheet, MAIN_COLUMN_GROUP_DEFINITIONS)
    if sheet_name in {"FixPlan", "Main", "Technical", "AIOSEO"}:
        apply_intelligent_sorting(worksheet, sheet_name)
    apply_generic_sheet_coloring(worksheet, sheet_name)
    apply_column_widths(worksheet)
    if sheet_name == "Main":
        apply_main_sheet_heatmaps(worksheet)
    apply_wrapped_row_heights(worksheet)
    if sheet_name == "FixPlan":
        apply_fixplan_workflow_formatting(worksheet)
    hide_noisy_columns(worksheet, sheet_name)
    apply_south_african_formats(worksheet)
    collapse_technical_deep_dive_columns(
        worksheet, sheet_name, header_index_fn=header_index
    )
    add_url_navigation_links(writer, worksheet, sheet_name)
    apply_cross_sheet_links(writer, worksheet, sheet_name)
    if sheet_name == "AIOSEO":
        status_col = header_index(worksheet).get("Status")
        if status_col:
            apply_status_dropdown(worksheet, status_col)
    if sheet_name in {"FixPlan", "IssueInventory"}:
        apply_status_dropdown_to_inventory(worksheet)
    add_back_to_dashboard_link(worksheet, sheet_name)
    if sheet_name == CONTENT_OPTIMISATION_HUB_SHEET:
        apply_content_hub_conditional_rules(worksheet, writer)
    apply_sheet_text_wrap_columns(worksheet, sheet_name)
    if sheet_name in {CONTENT_OPTIMISATION_HUB_SHEET, "AIOSEO"}:
        apply_editor_url_column_hyperlinks(
            worksheet,
            sheet_name,
            disable_external_links_and_images=DISABLE_EXTERNAL_LINKS_AND_IMAGES,
        )
    if sheet_name == "PSI Performance":
        apply_psi_conditional_rules(worksheet)
    if sheet_name != CONTENT_OPTIMISATION_HUB_SHEET:
        add_all_header_tooltips(worksheet)
    if sheet_name in DATA_HEAVY_TABS and sheet_name != CONTENT_OPTIMISATION_HUB_SHEET:
        add_header_tooltips(worksheet)
    if sheet_name in {"Technical", "Main", "AEO"}:
        apply_header_tooltips(worksheet, header_row=1)
    if sheet_name == "Dashboard" and not DEBUG_EXCEL_ISOLATION_MODE:
        style_dashboard(worksheet, writer)
    if sheet_name != "Dashboard":
        header_row = 2 if sheet_name == CONTENT_OPTIMISATION_HUB_SHEET else 1
        normalize_table_headers(worksheet, header_row=header_row)
        header_values = [
            worksheet.cell(row=header_row, column=c).value
            for c in range(1, worksheet.max_column + 1)
        ]
        valid_table_headers = all(
            isinstance(v, str) and v.strip() for v in header_values
        )
        if (
            worksheet.max_row > header_row
            and worksheet.max_column > 0
            and valid_table_headers
        ):
            ref_string = compute_exact_table_ref(worksheet, header_row)
            if ref_string:
                start_ref, end_ref = ref_string.split(":")
                min_row, min_col = coordinate_to_tuple(start_ref)
                max_row, max_col = coordinate_to_tuple(end_ref)
                apply_mock_table_styling(
                    worksheet,
                    min_col=min_col,
                    max_col=max_col,
                    min_row=min_row,
                    max_row=max_row,
                )
    if sheet_name == CONTENT_OPTIMISATION_HUB_SHEET:
        finalize_content_hub_after_normalized_headers(worksheet)
        _apply_content_hub_assigned_owner_validation(worksheet)
        _apply_content_hub_copywriter_column_layout(worksheet)
        apply_header_tooltips(worksheet, header_row=2)
    ensure_auto_filter(worksheet)
    if sheet_name != "Dashboard":
        ensure_freeze_header(worksheet)
    apply_optimal_view_state(worksheet, sheet_name)
    sanitize_sheet_view_selection(worksheet)
    audit_non_overlapping_merges(worksheet)
    audit_freeze_merge_conflicts(worksheet)


def apply_tab_hyperlinks(writer):
    apply_workbook_toc_and_links(
        writer,
        debug_excel_isolation_mode=DEBUG_EXCEL_ISOLATION_MODE,
        disable_non_core_freeze_panes=DISABLE_NON_CORE_FREEZE_PANES,
        std_navy=STD_NAVY,
        std_white=STD_WHITE,
        std_blue=STD_BLUE,
    )


__all__ = ["adjust_sheet_format", "apply_tab_hyperlinks", "set_freeze_panes_safe"]
