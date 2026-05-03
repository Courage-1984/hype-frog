from __future__ import annotations

from openpyxl.utils.cell import coordinate_to_tuple

from hype_frog.reporter.excel_engine import (
    apply_fixplan_workflow_formatting,
    apply_header_tooltips,
    ensure_auto_filter,
    ensure_freeze_header,
)
from hype_frog.reporter.sheets import apply_workbook_toc_and_links
from hype_frog.reporter.sheets.conditional import (
    apply_content_hub_conditional_rules,
    apply_generic_sheet_coloring,
    apply_main_sheet_heatmaps,
    apply_psi_conditional_rules,
    apply_sheet_text_wrap_columns,
    apply_wrapped_row_heights,
)
from hype_frog.reporter.sheets.config import (
    DATA_HEAVY_TABS,
    DEBUG_EXCEL_ISOLATION_MODE,
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
from hype_frog.reporter.sheets.utils import header_index


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
    if sheet_name == "Content Optimization Hub":
        apply_content_hub_conditional_rules(worksheet, writer)
    apply_sheet_text_wrap_columns(worksheet, sheet_name)
    if sheet_name in {"Content Optimization Hub", "AIOSEO"}:
        apply_editor_url_column_hyperlinks(
            worksheet,
            sheet_name,
            disable_external_links_and_images=DISABLE_EXTERNAL_LINKS_AND_IMAGES,
        )
    if sheet_name == "PSI Performance":
        apply_psi_conditional_rules(worksheet)
    add_all_header_tooltips(worksheet)
    if sheet_name in DATA_HEAVY_TABS:
        add_header_tooltips(worksheet)
    if sheet_name in {"Technical", "Main", "AEO"}:
        apply_header_tooltips(worksheet, header_row=1)
    if sheet_name == "Dashboard" and not DEBUG_EXCEL_ISOLATION_MODE:
        style_dashboard(worksheet, writer)
    if sheet_name != "Dashboard":
        header_row = 2 if sheet_name == "Content Optimization Hub" else 1
        normalize_table_headers(worksheet, header_row=header_row)
        header_values = [
            worksheet.cell(row=header_row, column=c).value
            for c in range(1, worksheet.max_column + 1)
        ]
        valid_table_headers = all(isinstance(v, str) and v.strip() for v in header_values)
        if worksheet.max_row > header_row and worksheet.max_column > 0 and valid_table_headers:
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
