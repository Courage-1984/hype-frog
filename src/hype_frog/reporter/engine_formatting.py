from __future__ import annotations

from openpyxl.formatting.rule import CellIsRule, ColorScaleRule, DataBarRule, FormulaRule
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from hype_frog.reporter.sheets.config import CONTENT_OPTIMISATION_HUB_SHEET


def apply_fixplan_workflow_formatting(worksheet: Worksheet) -> None:
    headers = [cell.value for cell in worksheet[1]]
    header_to_col = {str(h): i + 1 for i, h in enumerate(headers) if h is not None}
    priority_col = header_to_col.get("Priority Score")
    points_col = header_to_col.get("Est. Sprint Points")
    aging_col = header_to_col.get("Aging/Priority")
    critical_fill = PatternFill(start_color="F4CCCC", end_color="F4CCCC", fill_type="solid")
    warning_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    good_fill = PatternFill(start_color="D9EAD3", end_color="D9EAD3", fill_type="solid")
    edge_fill = PatternFill(start_color="D9D2E9", end_color="D9D2E9", fill_type="solid")
    for row_idx in range(2, worksheet.max_row + 1):
        if priority_col:
            cell = worksheet.cell(row=row_idx, column=priority_col)
            try:
                score = int(cell.value or 0)
                if score >= 100:
                    cell.fill = critical_fill
                elif score >= 65:
                    cell.fill = warning_fill
                else:
                    cell.fill = edge_fill
            except Exception:
                pass
        if points_col:
            cell = worksheet.cell(row=row_idx, column=points_col)
            try:
                points = int(cell.value or 0)
                if points >= 8:
                    cell.fill = critical_fill
                elif points >= 5:
                    cell.fill = warning_fill
                else:
                    cell.fill = good_fill
            except Exception:
                pass
        if aging_col:
            cell = worksheet.cell(row=row_idx, column=aging_col)
            value = str(cell.value or "").lower()
            if "immediate" in value:
                cell.fill = critical_fill
            elif "next sprint" in value:
                cell.fill = warning_fill
            elif "backlog" in value:
                cell.fill = edge_fill


def _legacy_sheet_header_index(worksheet: Worksheet) -> dict[str, int]:
    return {
        str(cell.value): idx
        for idx, cell in enumerate(worksheet[1], start=1)
        if cell.value
    }


def ensure_auto_filter(worksheet: Worksheet) -> None:
    if worksheet.title not in {"Main", "Dashboard", "Link Inventory"} and (
        worksheet.max_row < 10 or worksheet.max_column < 5
    ):
        worksheet.auto_filter.ref = None
        return

    header_row = 2 if worksheet.title == CONTENT_OPTIMISATION_HUB_SHEET else 1
    if worksheet.max_row >= header_row + 1 and worksheet.max_column >= 1:
        worksheet.auto_filter.ref = (
            f"A{header_row}:{get_column_letter(worksheet.max_column)}{worksheet.max_row}"
        )
    else:
        worksheet.auto_filter.ref = None


def _clear_orphaned_selection(worksheet: Worksheet) -> None:
    try:
        worksheet.views.sheetView[0].selection = []
    except Exception:
        pass


def ensure_freeze_header(worksheet: Worksheet) -> None:
    if worksheet.title == CONTENT_OPTIMISATION_HUB_SHEET:
        return
    if worksheet.title not in {"Main", "Dashboard", "Link Inventory"} and (
        worksheet.max_row < 10 or worksheet.max_column < 5
    ):
        worksheet.freeze_panes = None
        _clear_orphaned_selection(worksheet)
        return
    if worksheet.max_row > 1 and worksheet.max_column >= 1:
        worksheet.freeze_panes = "A2"
    else:
        worksheet.freeze_panes = None
        _clear_orphaned_selection(worksheet)


def apply_global_conditional_formatting(
    worksheet: Worksheet, *, merged_audit_tabs: bool = False
) -> None:
    if worksheet.max_row <= 1:
        return
    headers = _legacy_sheet_header_index(worksheet)
    last_row = worksheet.max_row
    status_col = headers.get("Status Code") or headers.get("Target Status (if crawled)")
    if status_col:
        col = get_column_letter(status_col)
        rng = f"{col}2:{col}{last_row}"
        worksheet.conditional_formatting.add(
            rng,
            CellIsRule(
                operator="equal",
                formula=["200"],
                fill=PatternFill("solid", fgColor="C6EFCE"),
            ),
        )
        worksheet.conditional_formatting.add(
            rng,
            CellIsRule(
                operator="between",
                formula=["300", "399"],
                fill=PatternFill("solid", fgColor="FFEB9C"),
            ),
        )
        worksheet.conditional_formatting.add(
            rng,
            CellIsRule(
                operator="greaterThanOrEqual",
                formula=["400"],
                fill=PatternFill("solid", fgColor="FFC7CE"),
            ),
        )

    for load_header in ("Load Time (s)", "Load Time", "TTFB (ms)"):
        load_col = headers.get(load_header)
        if load_col:
            col = get_column_letter(load_col)
            rng = f"{col}2:{col}{last_row}"
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
            worksheet.conditional_formatting.add(
                rng,
                DataBarRule(
                    start_type="min",
                    end_type="max",
                    color="638EC6",
                    showValue=True,
                ),
            )
            break

    for wc_header in ("Word Count", "Word Count (Body)"):
        wc_col = headers.get(wc_header)
        if wc_col:
            col = get_column_letter(wc_col)
            rng = f"{col}2:{col}{last_row}"
            worksheet.conditional_formatting.add(
                rng,
                DataBarRule(
                    start_type="min",
                    end_type="max",
                    color="638EC6",
                    showValue=True,
                ),
            )
            break

    priority_col = headers.get("Priority Score")
    if priority_col:
        col = get_column_letter(priority_col)
        rng = f"{col}2:{col}{last_row}"
        worksheet.conditional_formatting.add(
            rng,
            CellIsRule(
                operator="greaterThanOrEqual",
                formula=["85"],
                font=Font(color="9C0006", bold=True),
                fill=PatternFill("solid", fgColor="FFC7CE"),
            ),
        )
        worksheet.conditional_formatting.add(
            rng,
            CellIsRule(
                operator="between",
                formula=["65", "84"],
                font=Font(color="9C5700", bold=True),
                fill=PatternFill("solid", fgColor="FFEB9C"),
            ),
        )

    seo_score_col = headers.get("SEO Health Score")
    if seo_score_col and not merged_audit_tabs:
        col = get_column_letter(seo_score_col)
        worksheet.conditional_formatting.add(
            f"{col}2:{col}{last_row}",
            ColorScaleRule(
                start_type="min",
                start_color="F8696B",
                mid_type="percentile",
                mid_value=50,
                mid_color="FFEB84",
                end_type="max",
                end_color="63BE7B",
            ),
        )

    aeo_score_col = headers.get("AEO Readiness Score")
    if aeo_score_col:
        col = get_column_letter(aeo_score_col)
        worksheet.conditional_formatting.add(
            f"{col}2:{col}{last_row}",
            ColorScaleRule(
                start_type="min",
                start_color="F8696B",
                mid_type="percentile",
                mid_value=50,
                mid_color="FFEB84",
                end_type="max",
                end_color="63BE7B",
            ),
        )

    for score_header in ("Desktop Score", "Mobile Score"):
        score_col = headers.get(score_header)
        if score_col:
            col = get_column_letter(score_col)
            rng = f"{col}2:{col}{last_row}"
            worksheet.conditional_formatting.add(
                rng,
                CellIsRule(
                    operator="between",
                    formula=["90", "100"],
                    fill=PatternFill("solid", fgColor="C6EFCE"),
                ),
            )
            worksheet.conditional_formatting.add(
                rng,
                CellIsRule(
                    operator="between",
                    formula=["50", "89"],
                    fill=PatternFill("solid", fgColor="FFEB9C"),
                ),
            )
            worksheet.conditional_formatting.add(
                rng,
                CellIsRule(
                    operator="between",
                    formula=["0", "49"],
                    fill=PatternFill("solid", fgColor="FFC7CE"),
                ),
            )

    lcp_col = headers.get("Mobile LCP")
    if lcp_col:
        col = get_column_letter(lcp_col)
        rng = f"{col}2:{col}{last_row}"
        worksheet.conditional_formatting.add(
            rng,
            CellIsRule(
                operator="lessThan",
                formula=["2.5"],
                fill=PatternFill("solid", fgColor="C6EFCE"),
            ),
        )
        worksheet.conditional_formatting.add(
            rng,
            CellIsRule(
                operator="greaterThan",
                formula=["4.0"],
                fill=PatternFill("solid", fgColor="FFC7CE"),
            ),
        )

    answer_para_col = headers.get("Paragraphs 40-60 Words Count")
    if answer_para_col:
        col = get_column_letter(answer_para_col)
        rng = f"{col}2:{col}{last_row}"
        worksheet.conditional_formatting.add(
            rng,
            CellIsRule(
                operator="equal",
                formula=["0"],
                fill=PatternFill("solid", fgColor="FFC7CE"),
            ),
        )
        worksheet.conditional_formatting.add(
            rng,
            CellIsRule(
                operator="between",
                formula=["1", "2"],
                fill=PatternFill("solid", fgColor="FFEB9C"),
            ),
        )
        worksheet.conditional_formatting.add(
            rng,
            CellIsRule(
                operator="greaterThanOrEqual",
                formula=["3"],
                fill=PatternFill("solid", fgColor="C6EFCE"),
            ),
        )

    action_col = headers.get("Action Needed")
    if action_col:
        col = get_column_letter(action_col)
        rng = f"{col}2:{col}{last_row}"
        worksheet.conditional_formatting.add(
            rng,
            FormulaRule(
                formula=[f'LOWER({col}2)="yes"'],
                stopIfTrue=True,
                fill=PatternFill("solid", fgColor="FFC7CE"),
            ),
        )
        worksheet.conditional_formatting.add(
            rng,
            FormulaRule(
                formula=[f'LOWER({col}2)="no"'],
                stopIfTrue=True,
                fill=PatternFill("solid", fgColor="C6EFCE"),
            ),
        )

    severity_badge_col = headers.get("Severity Badge")
    if severity_badge_col:
        col = get_column_letter(severity_badge_col)
        rng = f"{col}2:{col}{last_row}"
        worksheet.conditional_formatting.add(
            rng,
            FormulaRule(
                formula=[f'LOWER({col}2)="critical"'],
                stopIfTrue=True,
                fill=PatternFill("solid", fgColor="FFC7CE"),
            ),
        )
        worksheet.conditional_formatting.add(
            rng,
            FormulaRule(
                formula=[f'LOWER({col}2)="warning"'],
                stopIfTrue=True,
                fill=PatternFill("solid", fgColor="FFCC99"),
            ),
        )
        worksheet.conditional_formatting.add(
            rng,
            FormulaRule(
                formula=[f'OR(LOWER({col}2)="pass",LOWER({col}2)="observation")'],
                stopIfTrue=True,
                fill=PatternFill("solid", fgColor="C6EFCE"),
            ),
        )

    status_text_col = headers.get("Status")
    if status_text_col:
        col = get_column_letter(status_text_col)
        rng = f"{col}2:{col}{last_row}"
        worksheet.conditional_formatting.add(
            rng,
            FormulaRule(
                formula=[f'LOWER({col}2)="done"'],
                stopIfTrue=True,
                fill=PatternFill("solid", fgColor="D9EAD3"),
            ),
        )
        worksheet.conditional_formatting.add(
            rng,
            FormulaRule(
                formula=[
                    f'OR(LOWER({col}2)="to do",LOWER({col}2)="in progress",LOWER({col}2)="in review")'
                ],
                stopIfTrue=True,
                fill=PatternFill("solid", fgColor="FFF2CC"),
            ),
        )


# ---------------------------------------------------------------------------
# Sprint 6 — executive priority heatmap.
#
# Lives alongside ``apply_global_conditional_formatting`` because both
# share the openpyxl idiom (``worksheet.conditional_formatting.add(rng,
# Rule(...))``). Kept as a separate function rather than folded into
# the global helper because the Content Optimisation Hub uses
# ``header_row=2`` (banner row 1, headers row 2, data row 3) while
# every other audit sheet uses ``header_row=1`` — a single helper
# would have to branch on sheet identity, which we deliberately avoid
# here.
# ---------------------------------------------------------------------------


_CRITICAL_PRIORITY_FILL = PatternFill(
    start_color="C00000", end_color="C00000", fill_type="solid"
)
_CRITICAL_PRIORITY_FONT = Font(color="FFFFFF", bold=True)


def _header_index_at_row(worksheet: Worksheet, header_row: int) -> dict[str, int]:
    """Return ``{header_text: 1-indexed_column}`` for ``header_row``."""
    return {
        str(cell.value).strip(): cell.column
        for cell in worksheet[header_row]
        if cell.value is not None and str(cell.value).strip()
    }


def apply_executive_priority_formatting(
    worksheet: Worksheet,
    *,
    header_row: int = 2,
) -> None:
    """Apply Sprint 6 ROI heatmaps to the Content Optimisation Hub.

    Adds two openpyxl conditional rules driven by the executive ROI
    columns appended in ``engine_rows.CONTENT_HUB_EXPORT_COLUMNS``:

    1. **ColorScaleRule** (red → yellow → green) on ``Semantic AEO
       Score`` so low-readiness pages glow red and high-readiness
       pages glow green at a glance.
    2. **FormulaRule** on the entire data row that triggers a bold
       white-on-red fill when ``Instant Priority`` equals ``CRITICAL``.

    Both rules degrade gracefully: if either header is missing (e.g.
    a legacy export) the corresponding rule is simply skipped, no
    exception is raised.
    """
    if worksheet.max_row <= header_row:
        return
    headers = _header_index_at_row(worksheet, header_row)
    last_row = worksheet.max_row
    first_data_row = header_row + 1

    aeo_col = headers.get("Semantic AEO Score")
    if aeo_col:
        aeo_letter = get_column_letter(aeo_col)
        worksheet.conditional_formatting.add(
            f"{aeo_letter}{first_data_row}:{aeo_letter}{last_row}",
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

    priority_col = headers.get("Instant Priority")
    if priority_col:
        priority_letter = get_column_letter(priority_col)
        last_col_letter = get_column_letter(worksheet.max_column)
        row_range = (
            f"A{first_data_row}:{last_col_letter}{last_row}"
        )
        # Whole-row formula must use a column-absolute / row-relative
        # reference so each row evaluates against ITS OWN priority cell.
        worksheet.conditional_formatting.add(
            row_range,
            FormulaRule(
                formula=[f'UPPER(${priority_letter}{first_data_row})="CRITICAL"'],
                stopIfTrue=False,
                fill=_CRITICAL_PRIORITY_FILL,
                font=_CRITICAL_PRIORITY_FONT,
            ),
        )
        # Belt-and-braces: also add a CellIsRule directly on the
        # priority column itself so the flag stays legible even if a
        # downstream stylesheet removes the row-wide rule.
        worksheet.conditional_formatting.add(
            f"{priority_letter}{first_data_row}:{priority_letter}{last_row}",
            CellIsRule(
                operator="equal",
                formula=['"CRITICAL"'],
                stopIfTrue=False,
                fill=_CRITICAL_PRIORITY_FILL,
                font=_CRITICAL_PRIORITY_FONT,
            ),
        )
