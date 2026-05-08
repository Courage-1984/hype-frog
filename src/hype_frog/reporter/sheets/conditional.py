from __future__ import annotations

from typing import Any

from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule, FormulaRule

from hype_frog.reporter.engine_formatting import apply_global_conditional_formatting
from hype_frog.reporter.sheets.config import (
    CONTENT_OPTIMISATION_HUB_SHEET,
    DEBUG_EXCEL_ISOLATION_MODE,
    DISABLE_CONDITIONAL_FORMATTING,
    DISABLE_DATA_VALIDATION,
    DISABLE_EXTERNAL_LINKS_AND_IMAGES,
    STD_NAVY,
    STD_WHITE,
)
from hype_frog.reporter.sheets.links import (
    is_safe_hyperlink_target,
    normalize_url_for_match,
    sanitize_excel_url,
)
from hype_frog.reporter.sheets.utils import header_index
from hype_frog.reporter.sheets.view_state import set_freeze_panes_safe


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
        for _name, col_idx in headers.items():
            if "proposed" not in str(_name).lower():
                continue
            for row_idx in range(3, worksheet.max_row + 1):
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
                except Exception:
                    pass
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
                except Exception:
                    pass
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
            if h in {"SEO Health Score", "SEO Score", "Technical Health", "Copy Score"}:
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
                except Exception:
                    pass
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
        apply_global_conditional_formatting(worksheet)


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
        "CONTENT HUB INSTRUCTIONS: 1. Draft in 'Proposed' columns. | "
        "2. Watch 'Count' for Green. | "
        "3. Click 'Elementor' link. | "
        "4. Mark 'Status' as 'Completed'. | "
        "NOTE: If images show '#BLOCKED!', click the 'Security Warning' bar at the top of Excel and select 'Enable Content'."
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
    set_freeze_panes_safe(worksheet, "F3")
    headers = {
        str(cell.value): idx
        for idx, cell in enumerate(worksheet[2], start=1)
        if cell.value
    }
    status_col = headers.get("Status")
    start_row = 3
    end_row = worksheet.max_row

    if status_col and not DISABLE_DATA_VALIDATION and end_row >= start_row:
        dv = DataValidation(
            type="list",
            formula1='"To Do,In Progress,Review,Completed"',
            allow_blank=True,
        )
        worksheet.add_data_validation(dv)
        dv.add(
            f"{get_column_letter(status_col)}{start_row}:{get_column_letter(status_col)}{end_row}"
        )
    if status_col and end_row >= start_row and not DISABLE_CONDITIONAL_FORMATTING:
        status_letter = get_column_letter(status_col)
        for label, color, font_color in (
            ("completed", "00B050", "000000"),
            ("in progress", "FFFF00", "000000"),
            ("review", "FFC000", "000000"),
            ("to do", "FF0000", "FFFFFF"),
        ):
            worksheet.conditional_formatting.add(
                f"{status_letter}{start_row}:{status_letter}{end_row}",
                FormulaRule(
                    formula=[f'LOWER({status_letter}{start_row})="{label}"'],
                    stopIfTrue=True,
                    fill=PatternFill("solid", fgColor=color),
                    font=Font(color=font_color),
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
                    start_color="FF0000", end_color="FF0000", fill_type="solid"
                ),
                font=Font(color="FFFFFF", bold=True),
            ),
        )
        worksheet.conditional_formatting.add(
            ar_range,
            CellIsRule(
                operator="equal",
                formula=['"Needs Optimisation"'],
                fill=PatternFill(
                    start_color="FFC000", end_color="FFC000", fill_type="solid"
                ),
                font=Font(color="000000", bold=True),
            ),
        )
        worksheet.conditional_formatting.add(
            ar_range,
            CellIsRule(
                operator="equal",
                formula=['"Needs Optimization"'],
                fill=PatternFill(
                    start_color="FFC000", end_color="FFC000", fill_type="solid"
                ),
                font=Font(color="000000", bold=True),
            ),
        )
        worksheet.conditional_formatting.add(
            ar_range,
            CellIsRule(
                operator="equal",
                formula=['"Complete"'],
                fill=PatternFill(
                    start_color="00FF00", end_color="00FF00", fill_type="solid"
                ),
                font=Font(color="000000", bold=True),
            ),
        )
        worksheet.conditional_formatting.add(
            ar_range,
            CellIsRule(
                operator="equal",
                formula=['"Ready to Publish"'],
                fill=PatternFill(
                    start_color="00FF00", end_color="00FF00", fill_type="solid"
                ),
                font=Font(color="000000", bold=True),
            ),
        )

    og_url_col = headers.get("Current OG-Image URL")
    og_preview_col = headers.get("OG Image Preview")
    if og_preview_col and og_url_col and end_row >= start_row:
        og_url_letter = get_column_letter(og_url_col)
        for r in range(start_row, end_row + 1):
            og_url_cell = worksheet.cell(row=r, column=og_url_col)
            og_url_cell.value = sanitize_excel_url(og_url_cell.value)
            worksheet.cell(
                row=r,
                column=og_preview_col,
                value=(
                    str(og_url_cell.value or "")
                    if (DEBUG_EXCEL_ISOLATION_MODE or DISABLE_EXTERNAL_LINKS_AND_IMAGES)
                    else f'=IF(LEN({og_url_letter}{r})>0, _xlfn.IMAGE({og_url_letter}{r}), "")'
                ),
            )
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


def apply_main_sheet_heatmaps(worksheet: Worksheet) -> None:
    """Apply main-sheet heatmaps for key SEO and content quality metrics.

    Args:
        worksheet: Main worksheet where heatmaps should be added.
    """
    if DISABLE_CONDITIONAL_FORMATTING:
        return
    if worksheet.max_row <= 1:
        return

    start_row = 2
    end_row = worksheet.max_row
    if end_row < start_row:
        return

    headers = header_index(worksheet)

    seo_health_col = headers.get("SEO Health Score")
    if seo_health_col:
        seo_col_letter = get_column_letter(seo_health_col)
        seo_range = f"{seo_col_letter}{start_row}:{seo_col_letter}{end_row}"
        worksheet.conditional_formatting.add(
            seo_range,
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

    word_count_col = headers.get("Word Count (Body)")
    if word_count_col:
        wc_col_letter = get_column_letter(word_count_col)
        wc_range = f"{wc_col_letter}{start_row}:{wc_col_letter}{end_row}"
        worksheet.conditional_formatting.add(
            wc_range,
            ColorScaleRule(
                start_type="num",
                start_value=0,
                start_color="F8696B",
                mid_type="num",
                mid_value=150,
                mid_color="FFEB84",
                end_type="num",
                end_value=300,
                end_color="63BE7B",
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


__all__ = [
    "apply_wrapped_row_heights",
    "apply_sheet_text_wrap_columns",
    "apply_generic_sheet_coloring",
    "apply_content_hub_conditional_rules",
    "finalize_content_hub_after_normalized_headers",
    "apply_psi_conditional_rules",
    "apply_main_sheet_heatmaps",
]
