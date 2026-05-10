from __future__ import annotations

from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import coordinate_to_tuple
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet

from hype_frog.reporter.help_layer import apply_semantic_aeo_tooltips
from hype_frog.reporter.engine_formatting import (
    apply_executive_priority_formatting,
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
    apply_merged_tabs_conditional_formatting,
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
    STD_FROG_GREEN,
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

# Sprint 4 + Sprint 5 — structural / security / i18n diagnostic
# tooltips and the new "ghost data" surfaced from Sprint 2's rendered
# diagnostics pipeline. A single dict feeds both the Content Hub
# (header_row=2) and the Technical Diagnostics tab (header_row=1) —
# ``_apply_diagnostic_header_tooltips`` does header-name lookup so each
# call only attaches comments to columns that actually exist on the
# given sheet. Inlined here (not in ``reporter.help_layer``) because
# ``help_layer.py`` is outside the 4-file authorisation for both sprints.
_DIAGNOSTIC_HEADER_TOOLTIPS: dict[str, str] = {
    "Crawl Depth": (
        "Description: BFS hop distance from the seed URL during this audit "
        "(0 = seed). Higher values indicate pages buried deeper in the site "
        "structure, which can hurt discoverability and crawl budget."
    ),
    "Security: HSTS": (
        "Description: TRUE when a non-empty Strict-Transport-Security "
        "response header was returned, signalling enforced HTTPS to "
        "browsers (HSTS)."
    ),
    "Security: CSP": (
        "Description: TRUE when a non-empty Content-Security-Policy "
        "response header was returned, signalling browser-side defence "
        "against XSS / script-injection."
    ),
    "Anchor Text Diversity": (
        "Description: Summary of the internal-link anchor pool on this "
        "page, formatted as '<unique> unique / <total> total'. Low "
        "diversity often means heavy reuse of generic anchors "
        "(e.g. 'click here') across the internal link graph."
    ),
    "Hreflang Signals": (
        "Description: On-page hreflang cluster joined as "
        "'lang: url; lang: url'. Extraction is HTML-only — no extra "
        "network requests are issued for cluster validation."
    ),
    "JS Dependent": (
        "Description: Flags pages where JavaScript adds more than 100 "
        "words or > 50% additional content compared to the raw HTML. "
        "Strong indicator that bots without a JS renderer (some "
        "answer-engine crawlers, monitoring tools) will see a thin "
        "version of the page."
    ),
    "Raw Words": (
        "Description: Word count of the raw HTML body returned by the "
        "initial HTTP fetch, before JavaScript execution. Compare with "
        "Rendered Words to gauge JS dependency."
    ),
    "Rendered Words": (
        "Description: Word count of the body after Playwright "
        "rendering, ``networkidle`` wait, and hydration settle. The "
        "delta vs Raw Words drives the JS Dependent flag."
    ),
    "Field LCP (ms)": (
        "Description: Largest Contentful Paint in milliseconds, "
        "captured live in the browser via PerformanceObserver during "
        "the rendered fetch. Blank when the observer was blocked "
        "(CSP) or the page never reached a stable LCP."
    ),
    "Field CLS": (
        "Description: Cumulative Layout Shift captured live in the "
        "browser via PerformanceObserver during the rendered fetch. "
        "Blank when the observer was blocked or the page produced no "
        "shift events in the observation window."
    ),
    # Sprint 6 — executive ROI tooltips. Numbers reference the
    # constants in ``hype_frog.core.scoring`` so any future re-tuning
    # only needs to edit one place; the tooltip text is duplicated here
    # for the workbook reader.
    "Potential Traffic Lift": (
        "Description: Estimated monthly clicks recoverable by closing "
        "the AEO gap on this URL.\n"
        "Calculation: GSC Clicks * ((100 - Semantic AEO Score) / 100) "
        "* 0.25 (assumed 25% maximum AEO-driven lift).\n"
        "Returns 0 when GSC traffic or AEO score is missing."
    ),
    "AEO Visibility Gain": (
        "Description: Semantic readiness headroom on a 0-100 scale "
        "(100 - Semantic AEO Score). Higher = more upside if the AEO "
        "issues on this page are addressed."
    ),
    "Instant Priority": (
        "Description: 'CRITICAL' when GSC Clicks > 500 AND (Semantic "
        "AEO Score < 50 OR Field LCP > 2500ms). High-traffic pages "
        "with weak readiness or poor field web vitals are flagged for "
        "immediate executive attention; everything else is 'Standard'."
    ),
}


def _apply_diagnostic_header_tooltips(
    worksheet: Worksheet,
    *,
    header_row: int = 1,
) -> None:
    """Attach Sprint 4 + Sprint 5 diagnostic header tooltips by name lookup."""
    for col_idx in range(1, worksheet.max_column + 1):
        cell = worksheet.cell(row=header_row, column=col_idx)
        header = str(cell.value or "").strip()
        tooltip = _DIAGNOSTIC_HEADER_TOOLTIPS.get(header)
        if tooltip:
            cell.comment = Comment(tooltip, "hype-frog")


def _apply_link_inventory_client_polish(worksheet: Worksheet) -> None:
    """Frog-green header row and readable widths for the seven export columns."""
    header_fill = PatternFill(
        start_color=STD_FROG_GREEN,
        end_color=STD_FROG_GREEN,
        fill_type="solid",
    )
    header_font = Font(color=STD_WHITE, bold=True)
    for col_idx in range(1, 8):
        cell = worksheet.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(
            horizontal="center", vertical="center", wrap_text=True
        )
    worksheet.column_dimensions["A"].width = 50.0
    worksheet.column_dimensions["B"].width = 50.0
    worksheet.column_dimensions["C"].width = 30.0


_COPY_HUB_WIDE_HEADERS: frozenset[str] = frozenset(
    {
        "Current Title",
        "Current Meta Desc",
        "H1",
        "H2",
        "H3",
        "H4",
        "H5",
        "H6",
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
    fixed_width_by_header: dict[str, float] = {
        "Elementor Builder Link": 18.14,
        "Open in Main": 22.57,
        "Current OG-Image URL": 15.0,
        "Assigned Owner": 15.0,
        "On-Page Optimization Score": 12.0,
    }
    for name, col_idx in headers.items():
        if name in fixed_width_by_header:
            letter = get_column_letter(col_idx)
            worksheet.column_dimensions[letter].width = fixed_width_by_header[name]
            continue
        low = name.lower()
        if name in _COPY_HUB_WIDE_HEADERS or "proposed" in low:
            letter = get_column_letter(col_idx)
            cur = worksheet.column_dimensions[letter].width or 8.0
            floor = 56.0 if name == "Target Keywords" else 45.0
            worksheet.column_dimensions[letter].width = max(floor, float(cur))
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


def _link_main_technical_health_to_diagnostics(worksheet) -> None:
    """Keep Main Technical Health synced from Technical Diagnostics by URL lookup."""
    headers = header_index(worksheet)
    url_col = headers.get("URL")
    technical_health_col = headers.get("Technical Health")
    if not url_col or not technical_health_col:
        return
    url_letter = get_column_letter(url_col)
    technical_health_letter = get_column_letter(technical_health_col)
    for row_idx in range(2, worksheet.max_row + 1):
        worksheet[f"{technical_health_letter}{row_idx}"] = (
            f'=IFERROR(VLOOKUP({url_letter}{row_idx},'
            "'Technical Diagnostics'!$A:$E,5,FALSE),\"\")"
        )


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
        _link_main_technical_health_to_diagnostics(worksheet)
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
        # Sprint 6 — executive ROI heatmaps. Runs AFTER the Hub
        # conditional pipeline so the banner row insert in
        # ``apply_content_hub_conditional_rules`` has already pushed
        # headers to row 2 / data to row 3, which is what the new
        # helper expects.
        apply_executive_priority_formatting(worksheet, header_row=2)
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
        if sheet_name in (
            "Technical Diagnostics",
            "Content & AI Readiness",
            "Link Intelligence",
            "Link Inventory",
            "Issue Register",
            "Template & Duplication Risks",
        ):
            apply_merged_tabs_conditional_formatting(
                worksheet, sheet_name, header_row=header_row
            )
        if sheet_name == "Technical Diagnostics":
            # Sprint 5 — attach tooltips for the migrated diagnostic
            # columns (Crawl Depth / Security: HSTS / Security: CSP /
            # Hreflang Signals). The helper is name-keyed so it skips
            # any header it doesn't recognise.
            _apply_diagnostic_header_tooltips(worksheet, header_row=header_row)
        if sheet_name == "Link Inventory":
            _apply_link_inventory_client_polish(worksheet)
    if sheet_name == CONTENT_OPTIMISATION_HUB_SHEET:
        finalize_content_hub_after_normalized_headers(worksheet)
        _apply_content_hub_assigned_owner_validation(worksheet)
        _apply_content_hub_copywriter_column_layout(worksheet)
        apply_header_tooltips(worksheet, header_row=2)
        apply_semantic_aeo_tooltips(worksheet, header_row=2)
        _apply_diagnostic_header_tooltips(worksheet, header_row=2)
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
