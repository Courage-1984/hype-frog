from __future__ import annotations

import re
from typing import Any

from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.formatting.rule import (
    CellIsRule,
    ColorScaleRule,
    DataBarRule,
    FormulaRule,
)

from hype_frog.core import get_logger
from hype_frog.reporter.engine_formatting import apply_global_conditional_formatting
from hype_frog.reporter.sheets.config import (
    CONTENT_HUB_FREEZE_PANES,
    CONTENT_HUB_METRICS_SHEET,
    CONTENT_OPTIMISATION_HUB_SHEET,
    DATA_BAR_BLUE,
    DEBUG_EXCEL_ISOLATION_MODE,
    DISABLE_CONDITIONAL_FORMATTING,
    DISABLE_DATA_VALIDATION,
    DISABLE_EXTERNAL_LINKS_AND_IMAGES,
    HEATMAP_HIGH,
    HEATMAP_LOW,
    HEATMAP_MID,
    RAG_AMBER,
    RAG_AMBER_FONT,
    RAG_GREEN,
    RAG_GREEN_FONT,
    RAG_RED,
    RAG_RED_FONT,
    STD_NAVY,
)
from hype_frog.reporter.sheets.layout import CONTENT_HUB_ROW2_HEADER_COMMENTS
from hype_frog.reporter.sheets.links import (
    is_safe_hyperlink_target,
    sanitize_excel_url,
)
from hype_frog.reporter.sheets.style_helpers import header_index
from hype_frog.reporter.sheets.view_state import set_freeze_panes_safe

logger = get_logger(__name__)


def apply_wrapped_row_heights(worksheet: Worksheet) -> None:
    """Increase row heights for wrapped long-text columns.

    Args:
        worksheet: Worksheet to update.
    """
    if worksheet.max_row < 2:
        return

    headers = header_index(worksheet)
    wrapped_cols: list[int] = []
    for header_name in (
        "URL",
        "Final URL",
        "Canonical URL",
        "Affected URLs",
        "Internal Link Statuses",
        "How to Fix in AIOSEO",
    ):
        col_idx = headers.get(header_name)
        if col_idx:
            wrapped_cols.append(col_idx)
    if not wrapped_cols:
        return

    for row_idx in range(2, worksheet.max_row + 1):
        max_lines = 1
        for col_idx in wrapped_cols:
            value = worksheet.cell(row=row_idx, column=col_idx).value
            if value is None:
                continue
            text = str(value)
            explicit_lines = text.count("\n") + 1
            estimated_wrap_lines = max(1, int(len(text) / 50) + 1)
            max_lines = max(max_lines, explicit_lines, estimated_wrap_lines)
        if max_lines > 1:
            worksheet.row_dimensions[row_idx].height = min(120, 15 * max_lines)


_SHEET_WRAP_TARGETS: dict[str, tuple[int, tuple[str, ...]]] = {
    "Technical": (1, ("Redirect Hops", "X-Robots-Tag", "Content-Security-Policy")),
    "AEO": (1, ("Why It Matters", "Snippet Preview Mockup")),
    CONTENT_HUB_METRICS_SHEET: (1, ("Anchor Text Diversity", "Search Intent")),
}


def apply_sheet_text_wrap_columns(worksheet: Worksheet, sheet_name: str) -> None:
    """Wrap and cap row heights for high-volume narrative / policy columns."""
    if sheet_name == CONTENT_OPTIMISATION_HUB_SHEET:
        if worksheet.max_row <= 2:
            return
        headers: dict[str, int] = {}
        for c in range(1, worksheet.max_column + 1):
            v = worksheet.cell(row=2, column=c).value
            if v is not None and str(v).strip():
                headers[str(v).strip()] = c
        _hub_wrap = frozenset(
            {
                "Current Title",
                "Current Meta Desc",
                "H1",
                "H2",
                "H3",
                "H4",
                "H5",
                "H6",
                "URL Slug Normalization",
            }
        )
        for _name, col_idx in headers.items():
            if _name not in _hub_wrap and "proposed" not in str(_name).lower():
                continue
            for row_idx in range(4, worksheet.max_row + 1):
                cell = worksheet.cell(row=row_idx, column=col_idx)
                prev = cell.alignment
                cell.alignment = Alignment(
                    horizontal=prev.horizontal if prev else "left",
                    vertical="top",
                    wrap_text=True,
                )
        return
    spec = _SHEET_WRAP_TARGETS.get(sheet_name)
    if not spec:
        return
    header_row, col_names = spec
    if worksheet.max_row <= header_row:
        return
    headers: dict[str, int] = {}
    for c in range(1, worksheet.max_column + 1):
        v = worksheet.cell(row=header_row, column=c).value
        if v is not None and str(v).strip():
            headers[str(v).strip()] = c
    wrap_cols = [headers[n] for n in col_names if n in headers]
    if not wrap_cols:
        return
    for row_idx in range(header_row + 1, worksheet.max_row + 1):
        max_lines = 1
        for col_idx in wrap_cols:
            cell = worksheet.cell(row=row_idx, column=col_idx)
            cell.alignment = Alignment(
                wrap_text=True, vertical="top", horizontal="left"
            )
            val = cell.value
            if val is None:
                continue
            text = str(val)
            explicit_lines = text.count("\n") + 1
            estimated_wrap_lines = max(1, int(len(text) / 45) + 1)
            max_lines = max(max_lines, explicit_lines, estimated_wrap_lines)
        if max_lines > 1:
            worksheet.row_dimensions[row_idx].height = min(110, 13 * max_lines)


def apply_generic_sheet_coloring(worksheet: Worksheet, sheet_name: str) -> None:
    """Apply base per-cell semantic coloring and global conditional formatting.

    Args:
        worksheet: Worksheet to style.
        sheet_name: Current sheet name.
    """
    if worksheet.max_row < 2:
        return

    bad_fill = PatternFill(start_color="F4CCCC", end_color="F4CCCC", fill_type="solid")
    warn_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    good_fill = PatternFill(start_color="D9EAD3", end_color="D9EAD3", fill_type="solid")
    traffic_warn_fill = PatternFill(
        start_color="F4B183", end_color="F4B183", fill_type="solid"
    )
    edge_fill = PatternFill(start_color="D9D2E9", end_color="D9D2E9", fill_type="solid")
    zebra_fill = PatternFill(
        start_color="F7F7F7", end_color="F7F7F7", fill_type="solid"
    )
    headers = [cell.value for cell in worksheet[1]]
    is_wide_sheet = worksheet.max_column >= 30

    def parse_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes", "y"}
        return bool(value)

    def is_bad_header(header_name: str) -> bool:
        h = (header_name or "").lower()
        return any(
            t in h
            for t in [
                "error",
                "broken",
                "missing",
                "noindex",
                "disallow",
                "thin",
                "mixed content",
                "cross-canonical",
                "issue",
                "non-200",
                "loop",
                "out of",
            ]
        )

    def is_edge_header(header_name: str) -> bool:
        h = (header_name or "").lower()
        return any(
            t in h for t in ["redirect chain", "param url", "edge", "unresolved"]
        )

    def is_good_header(header_name: str) -> bool:
        h = (header_name or "").lower()
        return any(
            t in h
            for t in [
                "accessible",
                "match",
                "enabled",
                "complete",
                "present",
                "indexable",
                "coverage (%)",
            ]
        )

    for row_idx in range(2, worksheet.max_row + 1):
        row_has_issue = False
        for col_idx, header in enumerate(headers, start=1):
            cell = worksheet.cell(row=row_idx, column=col_idx)
            val = cell.value
            h = str(header) if header is not None else ""
            is_url_like = (
                "url" in h.lower()
                or h.lower().endswith("urls")
                or h.lower() in {"final url", "canonical url"}
            )
            if is_wide_sheet and is_url_like:
                cell.alignment = Alignment(
                    wrap_text=False, shrink_to_fit=True, vertical="top"
                )
            elif "url" in h.lower() or "hops" in h.lower() or "images" == h.lower():
                cell.alignment = Alignment(wrap_text=True, vertical="top")
            else:
                cell.alignment = Alignment(vertical="top")

            if "%" in h:
                try:
                    pct = float(val)
                    if pct == 100.0:
                        cell.fill = good_fill
                    elif pct < 80:
                        cell.fill = bad_fill
                        row_has_issue = True
                    else:
                        cell.fill = warn_fill
                except Exception as exc:
                    logger.debug(
                        "Percent CF skipped at %s!%s (%s=%r): %s",
                        worksheet.title,
                        cell.coordinate,
                        h,
                        val,
                        exc,
                    )
            if h in {"Status Code", "Target Status (if crawled)"} and isinstance(
                val, int
            ):
                if val >= 400:
                    cell.fill = bad_fill
                    row_has_issue = True
                elif val >= 300:
                    cell.fill = warn_fill
                elif 200 <= val < 300:
                    cell.fill = good_fill
            if isinstance(val, bool) or (
                isinstance(val, str) and val.strip().lower() in {"true", "false"}
            ):
                flag = parse_bool(val)
                if is_bad_header(h):
                    cell.fill = bad_fill if flag else good_fill
                    row_has_issue = row_has_issue or flag
                elif is_good_header(h):
                    cell.fill = good_fill if flag else warn_fill
                    row_has_issue = row_has_issue or (not flag)
                elif is_edge_header(h) and flag:
                    cell.fill = edge_fill
            if h in {
                "Broken Internal Links Count",
                "Image Filename Quality Issues",
                "Generic Anchor Text Count",
            }:
                try:
                    if int(val or 0) > 0:
                        cell.fill = bad_fill
                        row_has_issue = True
                    else:
                        cell.fill = good_fill
                except Exception as exc:
                    logger.debug(
                        "Count CF skipped at %s!%s (%s=%r): %s",
                        worksheet.title,
                        cell.coordinate,
                        h,
                        val,
                        exc,
                    )
            if h in {"Word Count Band"} and isinstance(val, str):
                band = val.lower()
                if band == "thin":
                    cell.fill = bad_fill
                    row_has_issue = True
                elif band == "ok":
                    cell.fill = warn_fill
                elif band == "strong":
                    cell.fill = good_fill
            if h in {"Indexability Reason"} and isinstance(val, str):
                if "indexable" in val.lower() and "noindex" not in val.lower():
                    cell.fill = good_fill
                else:
                    cell.fill = bad_fill
                    row_has_issue = True
            if h in {"Severity", "Severity Badge"} and isinstance(val, str):
                sev = val.strip().lower()
                if sev == "critical":
                    cell.fill = bad_fill
                    row_has_issue = True
                elif sev == "warning":
                    cell.fill = traffic_warn_fill
                    row_has_issue = True
                elif sev in {"info", "observation"}:
                    cell.fill = edge_fill
                elif sev == "pass":
                    cell.fill = good_fill
            if h in {"SEO Score", "Technical Health", "Copy Score"}:
                try:
                    score = float(val)
                    if score < 70:
                        cell.fill = bad_fill
                        row_has_issue = True
                    elif score < 90:
                        cell.fill = traffic_warn_fill
                        row_has_issue = True
                    else:
                        cell.fill = good_fill
                except Exception as exc:
                    logger.debug(
                        "Score CF skipped at %s!%s (%s=%r): %s",
                        worksheet.title,
                        cell.coordinate,
                        h,
                        val,
                        exc,
                    )
            if h == "Status" and isinstance(val, str):
                st = val.strip().lower()
                if st in {"to do", "todo", "open"}:
                    cell.fill = bad_fill
                    row_has_issue = True
                elif st == "in progress":
                    cell.fill = traffic_warn_fill
                    row_has_issue = True
                elif st in {"fixed", "done", "closed"}:
                    cell.fill = good_fill
            if (
                h == "Direct Edit Link"
                and isinstance(val, str)
                and val.startswith(("http://", "https://"))
            ):
                if is_safe_hyperlink_target(
                    val,
                    disable_external_links_and_images=DISABLE_EXTERNAL_LINKS_AND_IMAGES,
                ):
                    cell.hyperlink = val
                    cell.style = "Hyperlink"
                    cell.fill = PatternFill(
                        start_color="1F4E78", end_color="1F4E78", fill_type="solid"
                    )
                    cell.font = Font(color="FFFFFF", bold=True, underline="single")
                    cell.alignment = Alignment(horizontal="center", vertical="center")

        if not row_has_issue:
            worksheet.cell(row=row_idx, column=1).fill = good_fill
        if sheet_name != "Dashboard" and row_idx % 2 == 0:
            for col_idx in range(1, worksheet.max_column + 1):
                cell = worksheet.cell(row=row_idx, column=col_idx)
                if cell.fill.fill_type is None:
                    cell.fill = zebra_fill

    if not DISABLE_CONDITIONAL_FORMATTING:
        # On Main, apply_main_sheet_heatmaps owns these columns; tell the global pass
        # to skip them so we never stack two conflicting rules on one range.
        skip_headers = _MAIN_HEATMAP_OWNED_HEADERS if sheet_name == "Main" else frozenset()
        apply_global_conditional_formatting(
            worksheet,
            merged_audit_tabs=sheet_name in _MERGED_TAB_NAMES,
            skip_headers=skip_headers,
        )


def apply_content_hub_conditional_rules(worksheet: Worksheet, writer: Any) -> None:
    """Apply Content Hub-specific validations, formulas, and conditional rules.

    Args:
        worksheet: Content Optimisation Hub worksheet.
        writer: Pandas ExcelWriter-like object.
    """
    if worksheet.max_row < 2:
        return

    worksheet.insert_rows(1)
    max_col = worksheet.max_column
    instruction = (
        "CONTENT HUB (DIAGNOSTIC): Edit Title, Meta, and H1-H6 in-place; health columns "
        "and On-Page score update live. | Use Elementor link for CMS edits. | "
        "Set Status to Completed when done. | "
        "NOTE: If images show '#BLOCKED!', enable external content in Excel security."
    )
    if max_col > 1:
        inner_end = get_column_letter(max_col - 1)
        worksheet.merge_cells(f"A1:{inner_end}1")
        worksheet["A1"] = instruction
        back_cell = worksheet.cell(row=1, column=max_col)
        back_cell.value = "BACK TO DASHBOARD"
        back_cell.hyperlink = "#'Dashboard'!A1"
        back_cell.style = "Hyperlink"
        back_cell.font = Font(color="0563C1", underline="single", bold=True)
        back_cell.alignment = Alignment(horizontal="center", vertical="center")
        worksheet["A1"].hyperlink = None
    else:
        worksheet["A1"] = instruction
        worksheet["A1"].hyperlink = None
    worksheet["A1"].fill = PatternFill(
        start_color="BFE9E4", end_color="BFE9E4", fill_type="solid"
    )
    worksheet["A1"].font = Font(color=STD_NAVY, bold=True)
    worksheet["A1"].alignment = Alignment(horizontal="left", vertical="center")
    worksheet.row_dimensions[1].height = 28
    set_freeze_panes_safe(worksheet, CONTENT_HUB_FREEZE_PANES)
    headers = {
        str(cell.value): idx
        for idx, cell in enumerate(worksheet[2], start=1)
        if cell.value
    }
    status_col = headers.get("Status")
    # Row 1 = banner (inserted above), row 2 = headers, row 3 = scope-note row
    # (merged across all columns by the exporter before this function runs).
    # Actual data starts at row 4.
    start_row = 4
    end_row = worksheet.max_row

    if status_col and not DISABLE_DATA_VALIDATION and end_row >= start_row:
        dv = DataValidation(
            type="list",
            formula1='"To Do,In Progress,Review,Completed"',
            allow_blank=True,
        )
        # Header guidance is served via cell comments to avoid freeze-pane clipping.
        dv.showInputMessage = False
        worksheet.add_data_validation(dv)
        dv.add(
            f"{get_column_letter(status_col)}{start_row}:{get_column_letter(status_col)}{end_row}"
        )
    if status_col and end_row >= start_row and not DISABLE_CONDITIONAL_FORMATTING:
        status_letter = get_column_letter(status_col)
        for label, bg_hex, font_color in (
            ("completed", "1F7A1F", "FFFFFF"),
            ("in progress", "FFC000", "000000"),
            ("review", "FFC000", "000000"),
            ("to do", "D9D9D9", "000000"),
            ("needs copy", "D9D9D9", "000000"),
        ):
            worksheet.conditional_formatting.add(
                f"{status_letter}{start_row}:{status_letter}{end_row}",
                FormulaRule(
                    formula=[f'LOWER({status_letter}{start_row})="{label}"'],
                    stopIfTrue=True,
                    fill=PatternFill(
                        start_color=bg_hex, end_color=bg_hex, fill_type="solid"
                    ),
                    font=Font(color=font_color, bold=True),
                ),
            )
    if end_row >= start_row and not DISABLE_CONDITIONAL_FORMATTING:
        for score_header in (
            "On-Page Optimization Score",
            "SEO Score",
            "Technical Health",
            "Copy Score",
        ):
            col_idx = headers.get(score_header)
            if not col_idx:
                continue
            letter = get_column_letter(col_idx)
            rng = f"{letter}{start_row}:{letter}{end_row}"
            worksheet.conditional_formatting.add(
                rng,
                ColorScaleRule(
                    start_type="num",
                    start_value=0,
                    start_color=HEATMAP_LOW,
                    mid_type="num",
                    mid_value=50,
                    mid_color=HEATMAP_MID,
                    end_type="num",
                    end_value=100,
                    end_color=HEATMAP_HIGH,
                ),
            )
    owner_col = headers.get("Assigned Owner")
    if owner_col and end_row >= start_row and not DISABLE_CONDITIONAL_FORMATTING:
        ol = get_column_letter(owner_col)
        o_rng = f"{ol}{start_row}:{ol}{end_row}"
        for needle, bg_hex, font_color in (
            ("copy writer", "92D050", "FFFFFF"),
            ("developer", "5B9BD5", "FFFFFF"),
            ("server", "ED7D31", "FFFFFF"),
        ):
            worksheet.conditional_formatting.add(
                o_rng,
                FormulaRule(
                    formula=[
                        f'ISNUMBER(SEARCH("{needle}",LOWER(SUBSTITUTE({ol}{start_row},"/",""))))'
                    ],
                    stopIfTrue=True,
                    fill=PatternFill(
                        start_color=bg_hex, end_color=bg_hex, fill_type="solid"
                    ),
                    font=Font(color=font_color, bold=True),
                ),
            )
    action_required_col = headers.get("Action Required")
    if (
        action_required_col
        and end_row >= start_row
        and not DISABLE_CONDITIONAL_FORMATTING
    ):
        ar_letter = get_column_letter(action_required_col)
        ar_range = f"{ar_letter}{start_row}:{ar_letter}{end_row}"
        worksheet.conditional_formatting.add(
            ar_range,
            CellIsRule(
                operator="equal",
                formula=['"Needs Copy"'],
                fill=PatternFill(
                    start_color=RAG_RED, end_color=RAG_RED, fill_type="solid"
                ),
                font=Font(color=RAG_RED_FONT, bold=True),
            ),
        )
        for optimisation_literal in ('"Needs Optimisation"',):
            worksheet.conditional_formatting.add(
                ar_range,
                CellIsRule(
                    operator="equal",
                    formula=[optimisation_literal],
                    fill=PatternFill(
                        start_color=RAG_AMBER, end_color=RAG_AMBER, fill_type="solid"
                    ),
                    font=Font(color=RAG_AMBER_FONT, bold=True),
                ),
            )
        for complete_literal in ('"Complete"', '"Ready to Publish"'):
            worksheet.conditional_formatting.add(
                ar_range,
                CellIsRule(
                    operator="equal",
                    formula=[complete_literal],
                    fill=PatternFill(
                        start_color=RAG_GREEN, end_color=RAG_GREEN, fill_type="solid"
                    ),
                    font=Font(color=RAG_GREEN_FONT, bold=True),
                ),
            )

    health_headers = (
        "Title Health",
        "Meta Health",
        "H1 Health",
        "H2 Health",
        "H3 Health",
        "H4 Health",
        "H5 Health",
        "H6 Health",
    )
    if not DISABLE_CONDITIONAL_FORMATTING and end_row >= start_row:
        green_h = PatternFill(
            start_color="C6EFCE", end_color="C6EFCE", fill_type="solid"
        )
        red_h = PatternFill(
            start_color="F4CCCC", end_color="F4CCCC", fill_type="solid"
        )
        orange_h = PatternFill(
            start_color="FCE4D6", end_color="FCE4D6", fill_type="solid"
        )
        for hname in health_headers:
            cix = headers.get(hname)
            if not cix:
                continue
            hl = get_column_letter(cix)
            h_rng = f"{hl}{start_row}:{hl}{end_row}"
            top = f"{hl}{start_row}"
            worksheet.conditional_formatting.add(
                h_rng,
                FormulaRule(
                    formula=[
                        f'OR(ISNUMBER(SEARCH("OK",{top})),ISNUMBER(SEARCH("Perfect",{top})))'
                    ],
                    stopIfTrue=True,
                    fill=green_h,
                    font=Font(color="006100", bold=False),
                ),
            )
            worksheet.conditional_formatting.add(
                h_rng,
                FormulaRule(
                    formula=[
                        f'OR(ISNUMBER(SEARCH("FIX",{top})),ISNUMBER(SEARCH("MISSING",{top})))'
                    ],
                    stopIfTrue=True,
                    fill=red_h,
                    font=Font(color="9C0006", bold=True),
                ),
            )
            worksheet.conditional_formatting.add(
                h_rng,
                FormulaRule(
                    formula=[
                        f'OR(ISNUMBER(SEARCH("SHORT",{top})),ISNUMBER(SEARCH("LONG",{top})),'
                        f'ISNUMBER(SEARCH("REVIEW",{top})),LEFT({top},3)="Tip")'
                    ],
                    stopIfTrue=True,
                    fill=orange_h,
                    font=Font(color="833C0C", bold=True),
                ),
            )

    og_health_col = headers.get("OG Image Health")
    if og_health_col and end_row >= start_row and not DISABLE_CONDITIONAL_FORMATTING:
        health_letter = get_column_letter(og_health_col)
        health_rng = f"{health_letter}{start_row}:{health_letter}{end_row}"
        worksheet.conditional_formatting.add(
            health_rng,
            FormulaRule(
                formula=[
                    f'OR(ISNUMBER(SEARCH("Outlier",{health_letter}{start_row})),'
                    f'ISNUMBER(SEARCH("Legacy",{health_letter}{start_row})),'
                    f'ISNUMBER(SEARCH("legacy",{health_letter}{start_row})),'
                    f'ISNUMBER(SEARCH("Generic",{health_letter}{start_row})),'
                    f'ISNUMBER(SEARCH("Missing",{health_letter}{start_row})))'
                ],
                stopIfTrue=True,
                fill=PatternFill("solid", fgColor="FCE4D6"),
                font=Font(color="833C0C", bold=True),
            ),
        )

    og_url_col = headers.get("Current OG-Image URL")
    og_preview_col = headers.get("OG Image Preview")
    if og_preview_col and og_url_col and end_row >= start_row:
        og_url_letter = get_column_letter(og_url_col)
        for r in range(start_row, end_row + 1):
            og_url_cell = worksheet.cell(row=r, column=og_url_col)
            og_url_formula = str(og_url_cell.value or "").strip()
            target_url = ""
            if og_url_formula.upper().startswith("=HYPERLINK("):
                m = re.match(r'^=HYPERLINK\("([^"]+)"\s*,', og_url_formula, re.IGNORECASE)
                if m:
                    target_url = sanitize_excel_url(m.group(1))
            else:
                target_url = sanitize_excel_url(og_url_cell.value)
            worksheet.cell(
                row=r,
                column=og_preview_col,
                value=(
                    str(target_url or "")
                    if (DEBUG_EXCEL_ISOLATION_MODE or DISABLE_EXTERNAL_LINKS_AND_IMAGES)
                    else (
                        ""
                        if not target_url
                        else f'=IF(LEN("{target_url}")>0,IFERROR(_xlfn.IMAGE("{target_url}"),"{target_url}"),"")'
                    )
                ),
            )

    url_col_idx = headers.get("URL")
    if url_col_idx and end_row >= start_row:
        link_font = Font(color="0563C1", underline="single")
        for rr in range(start_row, end_row + 1):
            ucell = worksheet.cell(row=rr, column=url_col_idx)
            uv = ucell.value
            if isinstance(uv, str) and uv.strip().upper().startswith("=HYPERLINK("):
                ucell.font = link_font
    open_in_main_col_idx = headers.get("Open in Main")
    if open_in_main_col_idx and end_row >= start_row:
        link_font = Font(color="0563C1", underline="single")
        for rr in range(start_row, end_row + 1):
            worksheet.cell(row=rr, column=open_in_main_col_idx).font = link_font
    og_image_url_col_idx = headers.get("Current OG-Image URL")
    if og_image_url_col_idx and end_row >= start_row:
        link_font = Font(color="0563C1", underline="single")
        for rr in range(start_row, end_row + 1):
            worksheet.cell(row=rr, column=og_image_url_col_idx).font = link_font

    for hdr_name, cidx in headers.items():
        tip = CONTENT_HUB_ROW2_HEADER_COMMENTS.get(hdr_name)
        if tip:
            hcell = worksheet.cell(row=2, column=cidx)
            hcell.comment = Comment(tip, "hype-frog")

    worksheet["A1"].hyperlink = None


def finalize_content_hub_after_normalized_headers(worksheet: Worksheet) -> None:
    """Strip stray header hyperlinks after mock table (hub formulas live in row data)."""
    if worksheet.title != CONTENT_OPTIMISATION_HUB_SHEET or worksheet.max_row < 3:
        return
    for col_idx in range(1, worksheet.max_column + 1):
        hdr = worksheet.cell(row=2, column=col_idx)
        hdr.hyperlink = None
        try:
            if hdr.style and str(hdr.style) == "Hyperlink":
                hdr.style = "Normal"
        except (AttributeError, TypeError):
            pass
    # Reassert Content Hub freeze target after downstream header normalization passes.
    set_freeze_panes_safe(worksheet, CONTENT_HUB_FREEZE_PANES)


def apply_psi_conditional_rules(worksheet: Worksheet) -> None:
    """Apply PSI score/LCP-specific conditional formatting rules.

    Args:
        worksheet: PSI Performance worksheet.
    """
    if worksheet.max_row < 2:
        return

    start_row = 2
    end_row = worksheet.max_row
    if end_row < start_row:
        return

    headers = header_index(worksheet)
    mobile_lcp_col = headers.get("Mobile LCP")
    for header_name, tooltip in {
        "Mobile LCP": "Largest Contentful Paint. Target: < 2.5 seconds.",
        "Mobile CLS": "Cumulative Layout Shift. Target: < 0.1.",
    }.items():
        cidx = headers.get(header_name)
        if cidx:
            worksheet.cell(row=1, column=cidx).comment = Comment(
                tooltip, "SEO Audit Bot"
            )
    score_cols = [
        cidx
        for h, cidx in headers.items()
        if ("score" in str(h).lower())
        and ("desktop" in str(h).lower() or "mobile" in str(h).lower())
    ]
    for cidx in score_cols:
        col = get_column_letter(cidx)
        rng = f"{col}{start_row}:{col}{end_row}"
        if not DISABLE_CONDITIONAL_FORMATTING:
            worksheet.conditional_formatting.add(
                rng,
                FormulaRule(
                    formula=[f"{col}{start_row}>=90"],
                    stopIfTrue=True,
                    fill=PatternFill("solid", fgColor="C6EFCE"),
                    font=Font(color="006100"),
                ),
            )
            worksheet.conditional_formatting.add(
                rng,
                FormulaRule(
                    formula=[f"AND({col}{start_row}>=50,{col}{start_row}<90)"],
                    stopIfTrue=True,
                    fill=PatternFill("solid", fgColor="FFEB9C"),
                    font=Font(color="9C6500"),
                ),
            )
            worksheet.conditional_formatting.add(
                rng,
                FormulaRule(
                    formula=[f"{col}{start_row}<50"],
                    stopIfTrue=True,
                    fill=PatternFill("solid", fgColor="FFC7CE"),
                    font=Font(color="9C0006"),
                ),
            )
    if mobile_lcp_col and not DISABLE_CONDITIONAL_FORMATTING:
        col = get_column_letter(mobile_lcp_col)
        rng = f"{col}{start_row}:{col}{end_row}"
        worksheet.conditional_formatting.add(
            rng,
            FormulaRule(
                formula=[f"{col}{start_row}<=2.5"],
                stopIfTrue=True,
                fill=PatternFill("solid", fgColor="C6EFCE"),
            ),
        )
        worksheet.conditional_formatting.add(
            rng,
            FormulaRule(
                formula=[f"{col}{start_row}>4.0"],
                stopIfTrue=True,
                fill=PatternFill("solid", fgColor="FFC7CE"),
            ),
        )


_MERGED_TAB_NAMES: frozenset[str] = frozenset(
    {
        "Technical Diagnostics",
        "Content & AI Readiness",
        "Link Intelligence",
        "Link Inventory",
        "Broken Link Impact",
        "Quick Wins",
        "Issue Register",
        "Template & Duplication Risks",
    }
)

# Columns whose conditional formatting is owned by ``apply_main_sheet_heatmaps`` on the
# Main sheet. The global pass skips these to avoid stacking two rules on one range.
_MAIN_HEATMAP_OWNED_HEADERS: frozenset[str] = frozenset(
    {
        "Status Code",
        "SEO Health Score",
        "AEO Readiness Score",
        "Word Count",
        "Word Count (Body)",
        "Severity Badge",
    }
)

_HIGHER_BETTER_HEADERS: tuple[str, ...] = (
    "SEO Health Score",
    "Desktop PSI Score",
    "Readability (Rough Flesch)",
)

_LOWER_BETTER_HEADERS: tuple[str, ...] = (
    "Mobile LCP (s)",
    "Mobile TTFB (s)",
    "Mobile CLS",
)

_DATA_BAR_HEADERS: tuple[str, ...] = (
    "Word Count",
    "Image Count",
    "Inlinks Count",
    "Internal PageRank",
    "Internal Links Count",
    "Redirect Chain Length",
    "Priority Score",
    "Inbound Link Count",
)


def _merged_headers(worksheet: Worksheet, header_row: int) -> dict[str, int]:
    return {
        str(cell.value).strip(): idx
        for idx, cell in enumerate(worksheet[header_row], start=1)
        if cell.value is not None and str(cell.value).strip()
    }


def _column_range(headers: dict[str, int], header_name: str, start_row: int, end_row: int) -> str | None:
    col_idx = headers.get(header_name)
    if not col_idx or end_row < start_row:
        return None
    letter = get_column_letter(col_idx)
    return f"{letter}{start_row}:{letter}{end_row}"


def _add_color_scale_higher_better(
    worksheet: Worksheet, rng: str
) -> None:
    """Fixed 0–100 scale so SEO/PSI/readability gradients are smooth, not data-relative bands."""
    worksheet.conditional_formatting.add(
        rng,
        ColorScaleRule(
            start_type="num",
            start_value=0,
            start_color="F8696B",
            mid_type="num",
            mid_value=50,
            mid_color="FFEB84",
            end_type="num",
            end_value=100,
            end_color="63BE7B",
        ),
    )


def _add_color_scale_lower_better(worksheet: Worksheet, rng: str) -> None:
    worksheet.conditional_formatting.add(
        rng,
        ColorScaleRule(
            start_type="min",
            start_color="63BE7B",
            mid_type="percentile",
            mid_value=50,
            mid_color="FFEB84",
            end_type="max",
            end_color="F8696B",
        ),
    )


def _add_data_bar_blue(worksheet: Worksheet, rng: str) -> None:
    worksheet.conditional_formatting.add(
        rng,
        DataBarRule(
            start_type="min",
            end_type="max",
            color="638EC6",
            showValue=True,
        ),
    )


def _add_text_semantic_highlights(
    worksheet: Worksheet,
    headers: dict[str, int],
    header_names: tuple[str, ...],
    start_row: int,
    end_row: int,
) -> None:
    """Red/pink for Critical / Non-Pass / Error; yellow/orange for Warning / Needs Work."""
    critical_fill = PatternFill(start_color="F4CCCC", end_color="F4CCCC", fill_type="solid")
    warn_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    for name in header_names:
        col_idx = headers.get(name)
        if not col_idx:
            continue
        col = get_column_letter(col_idx)
        rng = f"{col}{start_row}:{col}{end_row}"
        top = f"{col}{start_row}"
        worksheet.conditional_formatting.add(
            rng,
            FormulaRule(
                formula=[
                    f'OR(NOT(ISERROR(SEARCH("Critical",{top}))),NOT(ISERROR(SEARCH("Non-Pass",{top}))),NOT(ISERROR(SEARCH("Error",{top}))))'
                ],
                stopIfTrue=True,
                fill=critical_fill,
            ),
        )
        worksheet.conditional_formatting.add(
            rng,
            FormulaRule(
                formula=[
                    f'OR(NOT(ISERROR(SEARCH("Warning",{top}))),NOT(ISERROR(SEARCH("Needs Work",{top}))))'
                ],
                stopIfTrue=True,
                fill=warn_fill,
            ),
        )


def apply_merged_tabs_conditional_formatting(
    worksheet: Worksheet,
    sheet_name: str,
    *,
    header_row: int = 1,
) -> None:
    """Conditional formatting for Wave 3 merged workbook tabs (color scales, data bars, text highlights)."""
    if DISABLE_CONDITIONAL_FORMATTING:
        return
    if sheet_name not in _MERGED_TAB_NAMES:
        return
    if worksheet.max_row <= header_row:
        return

    headers = _merged_headers(worksheet, header_row)
    start_row = header_row + 1
    end_row = worksheet.max_row

    for hdr in _HIGHER_BETTER_HEADERS:
        rng = _column_range(headers, hdr, start_row, end_row)
        if rng:
            _add_color_scale_higher_better(worksheet, rng)

    for hdr in _LOWER_BETTER_HEADERS:
        rng = _column_range(headers, hdr, start_row, end_row)
        if rng:
            _add_color_scale_lower_better(worksheet, rng)

    for hdr in _DATA_BAR_HEADERS:
        rng = _column_range(headers, hdr, start_row, end_row)
        if rng:
            _add_data_bar_blue(worksheet, rng)

    if sheet_name == "Technical Diagnostics":
        _add_text_semantic_highlights(
            worksheet,
            headers,
            ("Severity Badge", "Pass Flag", "Indexability Reason"),
            start_row,
            end_row,
        )
    elif sheet_name == "Content & AI Readiness":
        _add_text_semantic_highlights(
            worksheet,
            headers,
            ("AEO Badge", "Thin Content Flag", "Title Missing"),
            start_row,
            end_row,
        )
    elif sheet_name == "Link Intelligence":
        _add_text_semantic_highlights(
            worksheet,
            headers,
            ("Record Type", "Crawlable"),
            start_row,
            end_row,
        )
    elif sheet_name == "Link Inventory":
        _add_text_semantic_highlights(
            worksheet,
            headers,
            ("Link Type", "Generic Anchor"),
            start_row,
            end_row,
        )
    elif sheet_name == "Issue Register":
        days_col = headers.get("Days Open")
        if days_col:
            days_letter = get_column_letter(days_col)
            days_range = f"{days_letter}{start_row}:{days_letter}{end_row}"
            worksheet.conditional_formatting.add(
                days_range,
                CellIsRule(
                    operator="greaterThan",
                    formula=["60"],
                    fill=PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"),
                    font=Font(bold=True, color="9C0006"),
                ),
            )
            worksheet.conditional_formatting.add(
                days_range,
                CellIsRule(
                    operator="between",
                    formula=["31", "60"],
                    fill=PatternFill(start_color="FFEB84", end_color="FFEB84", fill_type="solid"),
                ),
            )
        status_col = headers.get("Status")
        if status_col and worksheet.max_row >= 2:
            last_col = get_column_letter(worksheet.max_column)
            worksheet.auto_filter.ref = f"A1:{last_col}{worksheet.max_row}"
        _add_text_semantic_highlights(
            worksheet,
            headers,
            ("Severity", "Issue", "Status", "Section"),
            start_row,
            end_row,
        )
    elif sheet_name == "Template & Duplication Risks":
        _add_text_semantic_highlights(
            worksheet,
            headers,
            ("Issue", "Severity", "Exact Action", "Risk Category"),
            start_row,
            end_row,
        )
    elif sheet_name == "Quick Wins":
        effort_col = headers.get("Effort (hrs)")
        if effort_col:
            effort_letter = get_column_letter(effort_col)
            effort_range = f"{effort_letter}{start_row}:{effort_letter}{end_row}"
            worksheet.conditional_formatting.add(
                effort_range,
                CellIsRule(
                    operator="lessThanOrEqual",
                    formula=["2"],
                    fill=PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid"),
                ),
            )
            worksheet.conditional_formatting.add(
                effort_range,
                CellIsRule(
                    operator="between",
                    formula=["2.01", "4"],
                    fill=PatternFill(start_color="FFEB84", end_color="FFEB84", fill_type="solid"),
                ),
            )
        _add_text_semantic_highlights(
            worksheet,
            headers,
            ("Severity",),
            start_row,
            end_row,
        )
    elif sheet_name == "Broken Link Impact":
        status_col = headers.get("Status Code")
        if status_col:
            status_letter = get_column_letter(status_col)
            status_range = f"{status_letter}{start_row}:{status_letter}{end_row}"
            worksheet.conditional_formatting.add(
                status_range,
                CellIsRule(
                    operator="greaterThanOrEqual",
                    formula=["400"],
                    fill=PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"),
                    font=Font(bold=True, color="9C0006"),
                ),
            )


def apply_main_sheet_heatmaps(worksheet: Worksheet) -> None:
    """Apply traffic-light and data-bar formatting to Main sheet key columns."""
    if DISABLE_CONDITIONAL_FORMATTING:
        return
    if worksheet.max_row <= 1:
        return

    start_row = 2
    end_row = worksheet.max_row
    if end_row < start_row:
        return

    headers = header_index(worksheet)

    def col_range(col_name: str) -> str | None:
        col_idx = headers.get(col_name)
        if not col_idx:
            return None
        letter = get_column_letter(col_idx)
        return f"{letter}{start_row}:{letter}{end_row}"

    red_green_scale = ColorScaleRule(
        start_type="num",
        start_value=0,
        start_color="FFC7CE",
        mid_type="num",
        mid_value=50,
        mid_color="FFCC99",
        end_type="num",
        end_value=100,
        end_color="C6EFCE",
    )

    for col_name in (
        "SEO Health Score",
        "Mobile PSI Score",
        "Desktop PSI Score",
        "Lighthouse Performance (Mobile)",
        "Lighthouse Accessibility (Mobile)",
        "Lighthouse Best Practices (Mobile)",
        "Lighthouse SEO Score (Mobile)",
        "AEO Readiness Score",
    ):
        rng = col_range(col_name)
        if rng:
            worksheet.conditional_formatting.add(rng, red_green_scale)

    lcp_rng = col_range("Lab LCP (Mobile) (s)")
    if lcp_rng:
        worksheet.conditional_formatting.add(
            lcp_rng,
            ColorScaleRule(
                start_type="num",
                start_value=0,
                start_color="C6EFCE",
                mid_type="num",
                mid_value=2.5,
                mid_color="FFCC99",
                end_type="num",
                end_value=10.0,
                end_color="FFC7CE",
            ),
        )

    status_rng = col_range("Status Code")
    if status_rng:
        worksheet.conditional_formatting.add(
            status_rng,
            CellIsRule(
                operator="greaterThanOrEqual",
                formula=["400"],
                fill=PatternFill(start_color="FFC1C1", end_color="FFC1C1", fill_type="solid"),
                font=Font(bold=True, color="991B1B"),
            ),
        )
        worksheet.conditional_formatting.add(
            status_rng,
            CellIsRule(
                operator="equal",
                formula=['"Timeout"'],
                fill=PatternFill(start_color="FFCC99", end_color="FFCC99", fill_type="solid"),
                font=Font(bold=True, color="924012"),
            ),
        )

    word_rng = col_range("Word Count (Body)")
    if word_rng:
        worksheet.conditional_formatting.add(
            word_rng,
            DataBarRule(
                start_type="num",
                start_value=0,
                end_type="num",
                end_value=2000,
                color=DATA_BAR_BLUE,
            ),
        )

    eeat_rng = col_range("E-E-A-T Signal Score")
    if eeat_rng:
        worksheet.conditional_formatting.add(
            eeat_rng,
            ColorScaleRule(
                start_type="num",
                start_value=0,
                start_color="FFC7CE",
                mid_type="num",
                mid_value=5,
                mid_color="FFCC99",
                end_type="num",
                end_value=10,
                end_color="C6EFCE",
            ),
        )

    schema_err_rng = col_range("Schema Error Count")
    if schema_err_rng:
        worksheet.conditional_formatting.add(
            schema_err_rng,
            CellIsRule(
                operator="greaterThan",
                formula=["0"],
                fill=PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"),
            ),
        )
        worksheet.conditional_formatting.add(
            schema_err_rng,
            CellIsRule(
                operator="equal",
                formula=["0"],
                fill=PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid"),
            ),
        )

    depth_rng = col_range("Click Depth")
    if depth_rng:
        worksheet.conditional_formatting.add(
            depth_rng,
            CellIsRule(
                operator="equal",
                formula=["-1"],
                fill=PatternFill(start_color="FFCC99", end_color="FFCC99", fill_type="solid"),
                font=Font(italic=True),
            ),
        )

    page_size_rng = col_range("Page Size (KB)")
    if page_size_rng:
        worksheet.conditional_formatting.add(
            page_size_rng,
            CellIsRule(
                operator="greaterThan",
                formula=["1024"],
                fill=PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"),
            ),
        )

    badge_rng = col_range("Severity Badge")
    if badge_rng:
        for val, colour in (
            ("Critical", "FFC1C1"),
            ("Warning", "FFCC99"),
            ("Observation", "DBEAFE"),
            ("Unmeasured", "E5E7EB"),
        ):
            worksheet.conditional_formatting.add(
                badge_rng,
                CellIsRule(
                    operator="equal",
                    formula=[f'"{val}"'],
                    fill=PatternFill(start_color=colour, end_color=colour, fill_type="solid"),
                ),
            )

    for col_name in ("Is Thin Content", "Is Near Duplicate", "Is Draft or Test Page"):
        flag_rng = col_range(col_name)
        if flag_rng:
            worksheet.conditional_formatting.add(
                flag_rng,
                CellIsRule(
                    operator="equal",
                    formula=["TRUE"],
                    fill=PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"),
                ),
            )

    age_rng = col_range("Content Age (days)")
    if age_rng:
        worksheet.conditional_formatting.add(
            age_rng,
            CellIsRule(
                operator="greaterThan",
                formula=["730"],
                fill=PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"),
            ),
        )
        worksheet.conditional_formatting.add(
            age_rng,
            CellIsRule(
                operator="greaterThan",
                formula=["365"],
                fill=PatternFill(start_color="FFCC99", end_color="FFCC99", fill_type="solid"),
            ),
        )

    meta_desc_length_col = headers.get("Meta Desc Length")
    if meta_desc_length_col:
        mdl_col_letter = get_column_letter(meta_desc_length_col)
        mdl_range = f"{mdl_col_letter}{start_row}:{mdl_col_letter}{end_row}"
        worksheet.conditional_formatting.add(
            mdl_range,
            CellIsRule(
                operator="greaterThan",
                formula=["160"],
                fill=PatternFill(
                    start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"
                ),
                font=Font(color="9C0006"),
            ),
        )


def apply_dashboard_metric_conditional_rules(worksheet: Worksheet) -> None:
    """Apply at-a-glance color scales to primary dashboard metric values."""
    if DISABLE_CONDITIONAL_FORMATTING:
        return
    if worksheet.title != "Dashboard":
        return
    if worksheet.max_row < 8:
        return

    completion_scale = dict(
        start_type="num",
        start_value=0,
        start_color=HEATMAP_LOW,
        mid_type="num",
        mid_value=0.5,
        mid_color=HEATMAP_MID,
        end_type="num",
        end_value=1,
        end_color=HEATMAP_HIGH,
    )
    worksheet.conditional_formatting.add("B5:B7", ColorScaleRule(**completion_scale))
    worksheet.conditional_formatting.add(
        "B8:B8",
        CellIsRule(
            operator="lessThan",
            formula=["-10"],
            fill=PatternFill(start_color="F4CCCC", end_color="F4CCCC", fill_type="solid"),
        ),
    )
    worksheet.conditional_formatting.add(
        "B8:B8",
        CellIsRule(
            operator="lessThan",
            formula=["0"],
            font=Font(color=RAG_RED_FONT, bold=True),
        ),
    )
    worksheet.conditional_formatting.add("B17:B17", ColorScaleRule(**completion_scale))
    worksheet.conditional_formatting.add("B22:B22", ColorScaleRule(**completion_scale))
    worksheet.conditional_formatting.add(
        "B20:B20",
        CellIsRule(
            operator="greaterThan",
            formula=["0"],
            stopIfTrue=True,
            fill=PatternFill(start_color=RAG_RED, end_color=RAG_RED, fill_type="solid"),
            font=Font(color=RAG_RED_FONT, bold=True),
        ),
    )


_CONTENT_PLANNER_COL_WIDTHS: dict[str, float] = {
    "Primary": 24.0,
    "Secondary": 24.0,
    "Tertiary": 24.0,
    "Page link": 52.0,
    "Copy Doc": 30.0,
    "Copywriter Sign off": 20.0,
    "Copy First Check": 18.0,
    "2nd Revisions": 16.0,
    "Client copy sign off": 20.0,
    "Web design off": 18.0,
    "UXI sign off": 16.0,
    "Visual Design sign off": 20.0,
    "Client final sign off": 20.0,
    "Optimisations": 16.0,
    "Desktop": 14.0,
    "Tablet": 14.0,
    "Mobile": 14.0,
    "SEO": 14.0,
    "Performance": 16.0,
}

# Teal accent used for the hierarchy (Primary/Secondary/Tertiary) header cells.
_PLANNER_TEAL: str = "BFE9E4"
_PLANNER_TEAL_FONT: str = "1A4A47"
# Soft amber for the Copy Doc workflow column header.
_PLANNER_COPYDOC_HDR: str = "FFF3CD"
_PLANNER_COPYDOC_HDR_FONT: str = "7A5C00"
# Soft indigo band for sign-off / QA column headers.
_PLANNER_SIGNOFF_HDR: str = "E8EAF6"
_PLANNER_SIGNOFF_HDR_FONT: str = "1A237E"
_CONTENT_PLANNER_SIGNOFF_STATUS: str = "Not signed off"
_CONTENT_PLANNER_SIGNOFF_FIRST_COL: int = 6
_CONTENT_PLANNER_SIGNOFF_LAST_COL: int = 19


def _apply_content_planner_header_accents(
    worksheet: Worksheet, headers: dict[str, int]
) -> None:
    """Reapply section header colours after mock table styling."""
    for hier_name in ("Primary", "Secondary", "Tertiary"):
        col_idx = headers.get(hier_name)
        if not col_idx:
            continue
        hdr = worksheet.cell(row=1, column=col_idx)
        hdr.fill = PatternFill(
            start_color=_PLANNER_TEAL, end_color=_PLANNER_TEAL, fill_type="solid"
        )
        hdr.font = Font(color=_PLANNER_TEAL_FONT, bold=True)

    copy_doc_col = headers.get("Copy Doc")
    if copy_doc_col:
        hdr = worksheet.cell(row=1, column=copy_doc_col)
        hdr.fill = PatternFill(
            start_color=_PLANNER_COPYDOC_HDR,
            end_color=_PLANNER_COPYDOC_HDR,
            fill_type="solid",
        )
        hdr.font = Font(color=_PLANNER_COPYDOC_HDR_FONT, bold=True)

    for col_idx in range(_CONTENT_PLANNER_SIGNOFF_FIRST_COL, _CONTENT_PLANNER_SIGNOFF_LAST_COL + 1):
        hdr = worksheet.cell(row=1, column=col_idx)
        hdr.fill = PatternFill(
            start_color=_PLANNER_SIGNOFF_HDR,
            end_color=_PLANNER_SIGNOFF_HDR,
            fill_type="solid",
        )
        hdr.font = Font(color=_PLANNER_SIGNOFF_HDR_FONT, bold=True)


def apply_content_planner_signoff_rules(worksheet: Worksheet) -> None:
    """Column widths, row heights, hyperlinks, and RAG sign-off formatting.

    Column layout: A=Primary, B=Secondary, C=Tertiary, D=Page link, E=Copy Doc,
    F-S = 14 sign-off/QA columns (Copywriter Sign off … Performance).
    Freeze panes at ``E2`` lock columns A–D while scrolling the workflow grid.
    """
    if worksheet.max_row <= 1:
        return

    headers = header_index(worksheet)
    last_row = worksheet.max_row
    signoff_col_indices = list(
        range(_CONTENT_PLANNER_SIGNOFF_FIRST_COL, _CONTENT_PLANNER_SIGNOFF_LAST_COL + 1)
    )

    # ── Column widths ────────────────────────────────────────────────────────
    for col_name, width in _CONTENT_PLANNER_COL_WIDTHS.items():
        col_idx = headers.get(col_name)
        if col_idx:
            worksheet.column_dimensions[get_column_letter(col_idx)].width = width

    # ── Header row: height + center alignment ────────────────────────────────
    worksheet.row_dimensions[1].height = 42
    for col_idx in range(1, worksheet.max_column + 1):
        cell = worksheet.cell(row=1, column=col_idx)
        cell.alignment = Alignment(
            horizontal="center", vertical="center", wrap_text=True
        )
    _apply_content_planner_header_accents(worksheet, headers)

    # ── Hierarchy columns: bold populated labels ─────────────────────────────
    for hier_name in ("Primary", "Secondary", "Tertiary"):
        col_idx = headers.get(hier_name)
        if not col_idx:
            continue
        for row_idx in range(2, last_row + 1):
            cell = worksheet.cell(row=row_idx, column=col_idx)
            cell.alignment = Alignment(horizontal="left", vertical="center")
            if cell.value:
                cell.font = Font(bold=True)

    # ── Page link column: hyperlinks + shrink-to-fit ────────────────────────
    page_link_col = headers.get("Page link")
    if page_link_col:
        link_font = Font(color="0563C1", underline="single")
        for row_idx in range(2, last_row + 1):
            cell = worksheet.cell(row=row_idx, column=page_link_col)
            url_val = str(cell.value or "").strip()
            if url_val.startswith(("http://", "https://")):
                cell.hyperlink = url_val
                cell.font = link_font
            cell.alignment = Alignment(
                wrap_text=False, shrink_to_fit=True, vertical="center"
            )

    # ── Copy Doc column: left-aligned placeholder hint ─────────────────────
    copy_doc_col = headers.get("Copy Doc")
    if copy_doc_col:
        placeholder_font = Font(color="808080", italic=True)
        for row_idx in range(2, last_row + 1):
            cell = worksheet.cell(row=row_idx, column=copy_doc_col)
            if cell.value is None or str(cell.value).strip() == "":
                cell.value = "Paste doc link"
                cell.font = placeholder_font
            cell.alignment = Alignment(horizontal="left", vertical="center")

    # ── Sign-off data cells: default status + centre alignment ───────────────
    for row_idx in range(2, last_row + 1):
        worksheet.row_dimensions[row_idx].height = 22
        for col_idx in signoff_col_indices:
            cell = worksheet.cell(row=row_idx, column=col_idx)
            if cell.value is None or str(cell.value).strip() == "":
                cell.value = _CONTENT_PLANNER_SIGNOFF_STATUS
            cell.alignment = Alignment(horizontal="center", vertical="center")

    # ── DataValidation for sign-off columns F–S ───────────────────────────────
    if not DISABLE_DATA_VALIDATION:
        dv = DataValidation(
            type="list",
            formula1='"Signed off,In progress,Not signed off"',
            allow_blank=False,
        )
        dv.showErrorMessage = True
        dv.errorTitle = "Invalid status"
        dv.error = "Select: Signed off, In progress, or Not signed off."
        worksheet.add_data_validation(dv)
        for col_idx in signoff_col_indices:
            letter = get_column_letter(col_idx)
            dv.add(f"{letter}2:{letter}{last_row}")

    # ── Conditional formatting: RAG for F2:S{last_row} ───────────────────────
    if not DISABLE_CONDITIONAL_FORMATTING:
        cf_range = (
            f"{get_column_letter(_CONTENT_PLANNER_SIGNOFF_FIRST_COL)}2:"
            f"{get_column_letter(_CONTENT_PLANNER_SIGNOFF_LAST_COL)}{last_row}"
        )
        signed_off_fill = PatternFill(
            start_color=RAG_GREEN, end_color=RAG_GREEN, fill_type="solid"
        )
        in_progress_fill = PatternFill(
            start_color=RAG_AMBER, end_color=RAG_AMBER, fill_type="solid"
        )
        not_signed_off_fill = PatternFill(
            start_color=RAG_RED, end_color=RAG_RED, fill_type="solid"
        )
        first_signoff_letter = get_column_letter(_CONTENT_PLANNER_SIGNOFF_FIRST_COL)
        worksheet.conditional_formatting.add(
            cf_range,
            FormulaRule(
                formula=[f'LOWER({first_signoff_letter}2)="signed off"'],
                fill=signed_off_fill,
                font=Font(color=RAG_GREEN_FONT),
                stopIfTrue=True,
            ),
        )
        worksheet.conditional_formatting.add(
            cf_range,
            FormulaRule(
                formula=[f'LOWER({first_signoff_letter}2)="in progress"'],
                fill=in_progress_fill,
                font=Font(color=RAG_AMBER_FONT),
                stopIfTrue=True,
            ),
        )
        worksheet.conditional_formatting.add(
            cf_range,
            FormulaRule(
                formula=[f'LOWER({first_signoff_letter}2)="not signed off"'],
                fill=not_signed_off_fill,
                font=Font(color=RAG_RED_FONT),
                stopIfTrue=True,
            ),
        )

    # ── Autofilter + freeze (columns A–D pinned) ────────────────────────────
    worksheet.auto_filter.ref = (
        f"A1:{get_column_letter(worksheet.max_column)}{last_row}"
    )
    set_freeze_panes_safe(worksheet, "E2")


__all__ = [
    "apply_wrapped_row_heights",
    "apply_sheet_text_wrap_columns",
    "apply_generic_sheet_coloring",
    "apply_content_hub_conditional_rules",
    "finalize_content_hub_after_normalized_headers",
    "apply_psi_conditional_rules",
    "apply_merged_tabs_conditional_formatting",
    "apply_main_sheet_heatmaps",
    "apply_dashboard_metric_conditional_rules",
    "apply_content_planner_signoff_rules",
]
