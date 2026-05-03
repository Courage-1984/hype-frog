from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet

from hype_frog.reporter.sheets.config import (
    CONTENT_OPTIMISATION_HUB_SHEET,
    STD_BLUE,
    STD_NAVY,
)
from hype_frog.reporter.sheets.utils import header_index, to_int
from hype_frog.reporter.sheets.view_state import set_freeze_panes_safe


def style_dashboard(worksheet: Worksheet, writer: Any) -> None:
    """Render the executive dashboard sheet with KPI and ownership blocks.

    Ported from legacy ``_style_dashboard`` in ``tables_impl.legacy.old.py``
    (aggregation order, D/E status tables, owner summary, tooltips, row heights).

    Args:
        worksheet: Dashboard worksheet instance.
        writer: Pandas ExcelWriter-like object exposing workbook via ``book``.
    """
    worksheet.sheet_view.showGridLines = False
    set_freeze_panes_safe(worksheet, "A2")
    worksheet._charts = []
    light_header_fill = PatternFill("solid", fgColor="E5E7EB")
    headers = header_index(worksheet)
    health_from_feed: float | None = None
    projected_health_from_feed: float | None = None
    projected_pass_from_feed: float | None = None
    seo_pass_rate_from_run: float | None = None
    for row_idx in range(1, 80):
        for col_idx in range(4, max(worksheet.max_column + 1, 26)):
            worksheet.cell(row=row_idx, column=col_idx, value=None)
    metric_col = headers.get("Metric")
    value_col = headers.get("Value")
    total_urls = 0
    pass_rate_pct = 0.0
    if metric_col and value_col:
        metric_to_value: dict[str, Any] = {}
        for row_idx in range(2, worksheet.max_row + 1):
            metric_name = str(
                worksheet.cell(row=row_idx, column=metric_col).value or ""
            ).strip()
            if metric_name:
                metric_to_value[metric_name] = worksheet.cell(
                    row=row_idx, column=value_col
                ).value
        if worksheet.max_row > 0:
            worksheet.delete_rows(1, worksheet.max_row)
        for col_letter, width in {
            "A": 35,
            "B": 15,
            "C": 5,
            "D": 30,
            "E": 15,
            "F": 5,
            "G": 15,
            "H": 15,
            "I": 15,
            "J": 15,
            "K": 15,
        }.items():
            worksheet.column_dimensions[col_letter].width = width
        total_urls = to_int(
            metric_to_value.get("URLs Crawled") or metric_to_value.get("Total URLs"),
            0,
        )
        pass_raw = metric_to_value.get("SEO Pass Rate %") or metric_to_value.get(
            "Pass Rate (%)"
        )
        try:
            pass_rate_pct = float(pass_raw or 0.0)
        except Exception:
            pass_rate_pct = 0.0
        seo_pass_rate_from_run = pass_rate_pct
        critical_urls = to_int(metric_to_value.get("Critical URL Count"), 0)
        warning_urls = to_int(metric_to_value.get("Warning URL Count"), 0)
        try:
            if "Health Score %" in metric_to_value:
                health_from_feed = float(metric_to_value.get("Health Score %") or 0.0)
        except Exception:
            health_from_feed = None
        try:
            if "Projected Health Score %" in metric_to_value:
                projected_health_from_feed = float(
                    metric_to_value.get("Projected Health Score %") or 0.0
                )
        except Exception:
            projected_health_from_feed = None
        try:
            if "Projected Pass Rate %" in metric_to_value:
                projected_pass_from_feed = float(
                    metric_to_value.get("Projected Pass Rate %") or 0.0
                )
        except Exception:
            projected_pass_from_feed = None

        title = worksheet["A1"]
        title.value = "Executive SEO & AEO Performance Report"
        worksheet["A2"] = "Executive SEO & AEO Dashboard"
        worksheet["A2"].font = Font(color=STD_NAVY, bold=True, size=12)
        title.font = Font(color=STD_NAVY, bold=True, size=16)
        title.alignment = Alignment(horizontal="left", vertical="center")
        worksheet.row_dimensions[1].height = 45

        header_fill = PatternFill("solid", fgColor="ADD8E6")
        header_font = Font(color="000000", bold=True, size=12)
        value_fill = PatternFill("solid", fgColor="DCE3EA")

        worksheet["A4"] = "EXECUTIVE METRICS"
        worksheet["B4"] = "Value"
        for ref in ("A4", "B4"):
            worksheet[ref].fill = header_fill
            worksheet[ref].font = header_font
            worksheet[ref].alignment = Alignment(
                horizontal="center", vertical="center", wrap_text=True
            )

        worksheet["A5"] = '=HYPERLINK("#\'Main\'!A1","Total URLs")'
        worksheet["B5"] = total_urls
        worksheet["A6"] = '=HYPERLINK("#\'Summary\'!A1","Overall Health Score")'
        worksheet["B6"] = "=IFERROR(0,0)"
        worksheet["B6"].number_format = "0.00%"
        worksheet["A7"] = '=HYPERLINK("#\'Summary\'!A1","SEO Pass Rate %")'
        worksheet["B7"] = "=IFERROR(0,0)"
        worksheet["B7"].number_format = "0.00%"
        worksheet["A8"] = '=HYPERLINK("#\'Technical\'!A1","Pass URLs")'
        worksheet["B8"] = 0
        worksheet["A9"] = '=HYPERLINK("#\'Priority URLs\'!A1","Critical URLs")'
        worksheet["B9"] = critical_urls
        worksheet["A10"] = '=HYPERLINK("#\'Technical\'!A1","Warning URLs")'
        worksheet["B10"] = warning_urls
        worksheet["A11"] = '=HYPERLINK("#\'Technical\'!A1","Error Rate % (4xx/5xx)")'
        worksheet["B11"] = "=IFERROR(0,0)"
        worksheet["B11"].number_format = "0.00%"
        worksheet["A12"] = (
            '=HYPERLINK("#\'Technical\'!A1","Crawl Success Rate % (2xx)")'
        )
        worksheet["B12"] = "=IFERROR(0,0)"
        worksheet["B12"].number_format = "0.00%"
        worksheet["A13"] = '=HYPERLINK("#\'Technical\'!A1","Critical URL Rate %")'
        worksheet["B13"] = "=IFERROR(0,0)"
        worksheet["B13"].number_format = "0.00%"
        worksheet["A14"] = '=HYPERLINK("#\'Technical\'!A1","Warning URL Rate %")'
        worksheet["B14"] = "=IFERROR(0,0)"
        worksheet["B14"].number_format = "0.00%"
        worksheet["A15"] = "Projected Health Score % (if all To Do done)"
        worksheet["B15"] = "=IFERROR(0,0)"
        worksheet["B15"].number_format = "0.00%"
        worksheet["A16"] = "Projected Pass Rate % (if all To Do done)"
        worksheet["B16"] = "=IFERROR(0,0)"
        worksheet["B16"].number_format = "0.00%"
        worksheet["A17"] = (
            f'=HYPERLINK("#\'{CONTENT_OPTIMISATION_HUB_SHEET}\'!A1",'
            f'"Content Hub Readiness (%)")'
        )
        worksheet["B17"] = (
            f"=IFERROR(COUNTIF('{CONTENT_OPTIMISATION_HUB_SHEET}'!A:A,\"Complete\")/"
            f"COUNTA('{CONTENT_OPTIMISATION_HUB_SHEET}'!D:D),0)"
        )
        worksheet["B17"].number_format = "0.00%"
        worksheet["A18"] = '=HYPERLINK("#\'Schema & Metadata\'!A1","URLs with Schema")'
        worksheet["B18"] = 0
        worksheet["A19"] = '=HYPERLINK("#\'Links\'!A1","Broken Internal Links")'
        worksheet["B19"] = 0
        for ref in (
            "A5",
            "B5",
            "A6",
            "B6",
            "A7",
            "B7",
            "A8",
            "B8",
            "A9",
            "B9",
            "A10",
            "B10",
            "A11",
            "B11",
            "A12",
            "B12",
            "A13",
            "B13",
            "A14",
            "B14",
            "A15",
            "B15",
            "A16",
            "B16",
            "A17",
            "B17",
            "A18",
            "B18",
            "A19",
            "B19",
        ):
            worksheet[ref].fill = value_fill
            worksheet[ref].font = Font(
                color="1F2937", bold=True, size=12 if ref.startswith("A") else 14
            )
            worksheet[ref].alignment = Alignment(horizontal="center", vertical="center")
        for ref in (
            "A5",
            "A6",
            "A7",
            "A8",
            "A9",
            "A10",
            "A11",
            "A12",
            "A13",
            "A14",
            "A17",
            "A18",
            "A19",
        ):
            worksheet[ref].font = Font(
                color=STD_BLUE, underline="single", bold=True, size=12
            )
        for row in range(5, 20):
            worksheet[f"A{row}"].alignment = Alignment(
                horizontal="left", vertical="center"
            )
            worksheet.row_dimensions[row].height = 24

    status_buckets = {
        "200 OK": 0,
        "3xx Redirects": 0,
        "4xx Errors": 0,
        "5xx Errors": 0,
        "Other": 0,
    }
    pass_urls = 0
    critical_urls = 0
    warning_urls = 0
    avg_ttfb_ms = 0.0
    schema_urls = 0
    broken_links_total = 0
    if "Technical" in writer.book.sheetnames:
        tech_ws = writer.book["Technical"]
        tech_headers = header_index(tech_ws)
        sc_col = tech_headers.get("Status Code")
        sev_col = tech_headers.get("Severity Badge")
        ttfb_col = tech_headers.get("TTFB (ms)")
        schema_count_col = tech_headers.get("Schema Types Count")
        broken_links_col = tech_headers.get("Broken Internal Links Count")
        ttfb_values: list[float] = []
        if sc_col:
            for r in range(2, tech_ws.max_row + 1):
                code = to_int(tech_ws.cell(row=r, column=sc_col).value, 0)
                if 200 <= code < 300:
                    status_buckets["200 OK"] += 1
                elif 300 <= code < 400:
                    status_buckets["3xx Redirects"] += 1
                elif 400 <= code < 500:
                    status_buckets["4xx Errors"] += 1
                elif 500 <= code < 600:
                    status_buckets["5xx Errors"] += 1
                elif code:
                    status_buckets["Other"] += 1
                if sev_col:
                    sev_val = (
                        str(tech_ws.cell(row=r, column=sev_col).value or "")
                        .strip()
                        .lower()
                    )
                    if sev_val == "critical":
                        critical_urls += 1
                    elif sev_val == "warning":
                        warning_urls += 1
                if ttfb_col:
                    raw_ttfb = tech_ws.cell(row=r, column=ttfb_col).value
                    try:
                        if raw_ttfb is not None and str(raw_ttfb).strip() != "":
                            ttfb_values.append(float(raw_ttfb))
                    except Exception:
                        pass
                if schema_count_col:
                    schema_urls += (
                        1
                        if to_int(tech_ws.cell(row=r, column=schema_count_col).value, 0)
                        > 0
                        else 0
                    )
                if broken_links_col:
                    broken_links_total += to_int(
                        tech_ws.cell(row=r, column=broken_links_col).value, 0
                    )
        if ttfb_values:
            avg_ttfb_ms = round(sum(ttfb_values) / len(ttfb_values), 2)
        crit_col = tech_headers.get("Critical Issues Count")
        warn_col = tech_headers.get("Warning Issues Count")
        if crit_col and warn_col:
            for r in range(2, tech_ws.max_row + 1):
                crit_count = to_int(tech_ws.cell(row=r, column=crit_col).value, 0)
                warn_count = to_int(tech_ws.cell(row=r, column=warn_col).value, 0)
                if crit_count == 0 and warn_count == 0:
                    pass_urls += 1
        else:
            sev_badge_col = tech_headers.get("Severity Badge")
            if sev_badge_col:
                for r in range(2, tech_ws.max_row + 1):
                    sev = (
                        str(tech_ws.cell(row=r, column=sev_badge_col).value or "")
                        .strip()
                        .lower()
                    )
                    if sev in {"pass", "info"}:
                        pass_urls += 1

    severity_counts: Counter[str] = Counter()
    if "FixPlan" in writer.book.sheetnames:
        fix_ws = writer.book["FixPlan"]
        fix_headers = header_index(fix_ws)
        sev_col = fix_headers.get("Severity")
        if sev_col:
            for r in range(2, fix_ws.max_row + 1):
                sev = str(fix_ws.cell(r, sev_col).value or "").strip().lower()
                if sev == "critical":
                    severity_counts["Critical"] += 1
                elif sev in {"high", "warning"}:
                    severity_counts["High"] += 1
                elif sev == "medium":
                    severity_counts["Medium"] += 1
                else:
                    severity_counts["Low"] += 1

    status_total = sum(status_buckets.values())
    error_count = status_buckets["4xx Errors"] + status_buckets["5xx Errors"]
    success_count = status_buckets["200 OK"]
    crawl_denominator = max(1, status_total or total_urls)
    pass_rate_pct = round((pass_urls / crawl_denominator) * 100, 2)
    critical_rate_pct = round((critical_urls / crawl_denominator) * 100, 2)
    warning_rate_pct = round((warning_urls / crawl_denominator) * 100, 2)
    worksheet["B8"] = pass_urls
    worksheet["B9"] = critical_urls
    worksheet["B10"] = warning_urls
    worksheet["B18"] = schema_urls
    worksheet["B19"] = broken_links_total
    worksheet["B11"] = f"=IFERROR({error_count}/{crawl_denominator},0)"
    worksheet["B11"].number_format = "0.00%"
    worksheet["B12"] = f"=IFERROR({success_count}/{crawl_denominator},0)"
    worksheet["B12"].number_format = "0.00%"
    worksheet["B13"] = f"=IFERROR({critical_urls}/{crawl_denominator},0)"
    worksheet["B13"].number_format = "0.00%"
    worksheet["B14"] = f"=IFERROR({warning_urls}/{crawl_denominator},0)"
    worksheet["B14"].number_format = "0.00%"
    if seo_pass_rate_from_run is not None:
        worksheet["B7"] = seo_pass_rate_from_run / 100.0
    else:
        worksheet["B7"] = f"=IFERROR({pass_urls}/{crawl_denominator},0)"
    worksheet["B7"].number_format = "0.00%"
    for row in range(5, 15):
        worksheet[f"A{row}"].alignment = Alignment(horizontal="left", vertical="center")
        worksheet.row_dimensions[row].height = 24

    avg_health_score: float | None = None
    if "Technical" in writer.book.sheetnames:
        technical_ws = writer.book["Technical"]
        technical_headers = header_index(technical_ws)
        score_col = technical_headers.get("SEO Health Score")
        if score_col:
            score_values: list[float] = []
            for r in range(2, technical_ws.max_row + 1):
                raw = technical_ws.cell(row=r, column=score_col).value
                try:
                    if raw is not None and str(raw).strip() != "":
                        score_values.append(float(raw))
                except Exception:
                    pass
            if score_values:
                avg_health_score = sum(score_values) / len(score_values)
    if health_from_feed is not None:
        worksheet["B6"] = f"=IFERROR({round(health_from_feed, 4)}/100,0)"
    elif avg_health_score is not None:
        worksheet["B6"] = f"=IFERROR({round(avg_health_score, 2)}/100,0)"
    else:
        worksheet["B6"] = f"=IFERROR({pass_rate_pct}/100,0)"
    worksheet["B6"].number_format = "0.00%"

    table_header_fill = PatternFill("solid", fgColor="ADD8E6")
    table_header_font = Font(color="000000", bold=True, size=11)
    for ref, val in {
        "D4": "Status",
        "E4": "Count",
        "D12": "Severity",
        "E12": "Count",
    }.items():
        cell = worksheet[ref]
        cell.value = val
        cell.fill = table_header_fill
        cell.font = table_header_font
        cell.alignment = Alignment(
            horizontal="center", vertical="center", wrap_text=True
        )

    status_rows = [
        ("200 OK", status_buckets["200 OK"], "C6EFCE"),
        ("3xx Redirects", status_buckets["3xx Redirects"], "FFCC99"),
        ("4xx Errors", status_buckets["4xx Errors"], "FFC1C1"),
        ("5xx Errors", status_buckets["5xx Errors"], "FFC1C1"),
        ("Other", status_buckets["Other"], "FFCC99"),
    ]
    for idx, (label, count, color) in enumerate(status_rows, start=5):
        worksheet[f"D{idx}"] = label
        worksheet[f"E{idx}"] = count
        worksheet[f"D{idx}"].fill = PatternFill("solid", fgColor=color)
        worksheet[f"E{idx}"].fill = PatternFill("solid", fgColor=color)

    sev_rows = [
        ("Critical", severity_counts.get("Critical", 0), "FFC1C1"),
        ("Warning", severity_counts.get("High", 0), "FFCC99"),
        ("Medium", severity_counts.get("Medium", 0), "FFCC99"),
        ("Low", severity_counts.get("Low", 0), "C6EFCE"),
    ]
    for idx, (label, count, color) in enumerate(sev_rows, start=13):
        worksheet[f"D{idx}"] = label
        worksheet[f"E{idx}"] = count
        worksheet[f"D{idx}"].fill = PatternFill("solid", fgColor=color)
        worksheet[f"E{idx}"].fill = PatternFill("solid", fgColor=color)

    for row in range(5, 16):
        for col in ("D", "E"):
            worksheet[f"{col}{row}"].alignment = Alignment(
                horizontal="center", vertical="center"
            )

    worksheet["M4"] = "PRIORITY SNAPSHOT"
    worksheet["N4"] = "Value"
    for ref in ("M4", "N4"):
        worksheet[ref].fill = table_header_fill
        worksheet[ref].font = table_header_font
        worksheet[ref].alignment = Alignment(horizontal="center", vertical="center")
    top_issue_name = "N/A"
    top_issue_affected = 0
    owner_rollup: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "issue_rows": 0,
            "affected_urls": 0,
            "critical": 0,
            "warning": 0,
            "info": 0,
        }
    )
    if "FixPlan" in writer.book.sheetnames:
        fix_ws = writer.book["FixPlan"]
        fix_headers = header_index(fix_ws)
        issue_col = fix_headers.get("Issue Type")
        affected_col = fix_headers.get("Affected Count")
        owner_col = fix_headers.get("Owner")
        sev_col = fix_headers.get("Severity")
        if issue_col and affected_col:
            for r in range(2, fix_ws.max_row + 1):
                affected = to_int(fix_ws.cell(row=r, column=affected_col).value, 0)
                if affected > top_issue_affected:
                    top_issue_affected = affected
                    top_issue_name = str(
                        fix_ws.cell(row=r, column=issue_col).value or "N/A"
                    )
                owner_name = (
                    str(
                        fix_ws.cell(row=r, column=owner_col).value or "Unassigned"
                    ).strip()
                    if owner_col
                    else "Unassigned"
                )
                sev_val = (
                    str(fix_ws.cell(row=r, column=sev_col).value or "").strip().lower()
                    if sev_col
                    else ""
                )
                owner_rollup[owner_name]["issue_rows"] += 1
                owner_rollup[owner_name]["affected_urls"] += affected
                if sev_val == "critical":
                    owner_rollup[owner_name]["critical"] += 1
                elif sev_val in {"warning", "high", "medium"}:
                    owner_rollup[owner_name]["warning"] += 1
                else:
                    owner_rollup[owner_name]["info"] += 1
    worksheet["M5"] = "Top Blocking Issue"
    worksheet["N5"] = top_issue_name
    worksheet["M6"] = "Top Issue Affected URLs"
    worksheet["N6"] = top_issue_affected
    worksheet["M7"] = "4xx/5xx URLs"
    worksheet["N7"] = status_buckets["4xx Errors"] + status_buckets["5xx Errors"]
    worksheet["M8"] = "Avg TTFB (ms)"
    worksheet["N8"] = avg_ttfb_ms
    for row in range(5, 9):
        worksheet[f"M{row}"].fill = PatternFill("solid", fgColor="F5F7FA")
        worksheet[f"N{row}"].fill = PatternFill("solid", fgColor="F5F7FA")

    worksheet["G22"] = "OWNER ISSUE SUMMARY"
    worksheet["G23"] = "Owner"
    worksheet["H23"] = "Issue Rows"
    worksheet["I23"] = "Affected URLs"
    worksheet["J23"] = "Critical"
    worksheet["K23"] = "Warning"
    for ref in ("G22",):
        worksheet[ref].fill = light_header_fill
        worksheet[ref].font = table_header_font
        worksheet[ref].alignment = Alignment(
            horizontal="center", vertical="center", wrap_text=True
        )
    owner_header_fill = PatternFill("solid", fgColor="ADD8E6")
    for ref in ("G23", "H23", "I23", "J23", "K23"):
        worksheet[ref].fill = owner_header_fill
        worksheet[ref].font = Font(color="000000", bold=True, size=11)
        worksheet[ref].alignment = Alignment(
            horizontal="center", vertical="center", wrap_text=True
        )
    worksheet.merge_cells("G22:K22")

    owner_rows_sorted = sorted(
        owner_rollup.items(),
        key=lambda x: (
            -x[1]["affected_urls"],
            -x[1]["critical"],
            -x[1]["warning"],
            x[0],
        ),
    )
    owner_start_row = 24
    for idx, (owner_name, metrics) in enumerate(
        owner_rows_sorted[:8], start=owner_start_row
    ):
        worksheet[f"G{idx}"] = f'=HYPERLINK("#\'FixPlan\'!A1","{owner_name}")'
        worksheet[f"H{idx}"] = metrics["issue_rows"]
        worksheet[f"I{idx}"] = metrics["affected_urls"]
        worksheet[f"J{idx}"] = metrics["critical"]
        worksheet[f"K{idx}"] = metrics["warning"]
        for col in ("G", "H", "I", "J", "K"):
            worksheet[f"{col}{idx}"].fill = PatternFill("solid", fgColor="F5F7FA")
            worksheet[f"{col}{idx}"].alignment = Alignment(
                horizontal="center", vertical="center"
            )
    if not owner_rows_sorted:
        worksheet["G24"] = "No owner data"
        worksheet["G24"].fill = PatternFill("solid", fgColor="F5F7FA")
        worksheet["G24"].alignment = Alignment(horizontal="center", vertical="center")

    for col, width in {"G": 15, "H": 15, "I": 15, "J": 15, "K": 15}.items():
        worksheet.column_dimensions[col].width = width

    overall_health = float(
        health_from_feed
        if health_from_feed is not None
        else (avg_health_score if avg_health_score is not None else pass_rate_pct)
    )
    health_fill = (
        "C6EFCE"
        if overall_health >= 80
        else "FFEB9C" if overall_health >= 60 else "FFC7CE"
    )
    worksheet["B6"].fill = PatternFill("solid", fgColor=health_fill)
    b7_pass_display = (
        seo_pass_rate_from_run if seo_pass_rate_from_run is not None else pass_rate_pct
    )
    worksheet["B7"].fill = PatternFill(
        "solid",
        fgColor=(
            "C6EFCE"
            if b7_pass_display >= 70
            else "FFEB9C" if b7_pass_display >= 40 else "FFC7CE"
        ),
    )
    worksheet["B11"].fill = PatternFill(
        "solid", fgColor="FFC7CE" if error_count > 0 else "C6EFCE"
    )
    worksheet["B12"].fill = PatternFill(
        "solid",
        fgColor=(
            "C6EFCE" if success_count >= max(1, crawl_denominator * 0.9) else "FFEB9C"
        ),
    )
    worksheet["B13"].fill = PatternFill(
        "solid",
        fgColor=(
            "FFC7CE"
            if critical_rate_pct >= 10
            else "FFEB9C" if critical_rate_pct > 0 else "C6EFCE"
        ),
    )
    worksheet["B14"].fill = PatternFill(
        "solid",
        fgColor=(
            "FFC7CE"
            if warning_rate_pct >= 50
            else "FFEB9C" if warning_rate_pct > 20 else "C6EFCE"
        ),
    )
    projected_pass_rate_pct = min(
        100.0,
        pass_rate_pct
        + ((critical_urls * 1.0 + warning_urls * 0.75) / max(1, crawl_denominator))
        * 100.0,
    )
    projected_health_pct = min(
        100.0,
        (overall_health if overall_health <= 100 else 100.0)
        + ((100.0 - overall_health) * 0.6),
    )
    if projected_health_from_feed is not None:
        ph_use = min(100.0, max(0.0, projected_health_from_feed))
        worksheet["B15"] = ph_use / 100.0
    else:
        worksheet["B15"] = projected_health_pct / 100.0
    worksheet["B15"].number_format = "0.00%"
    if projected_pass_from_feed is not None:
        pp_use = min(100.0, max(0.0, projected_pass_from_feed))
        worksheet["B16"] = pp_use / 100.0
    else:
        worksheet["B16"] = projected_pass_rate_pct / 100.0
    worksheet["B16"].number_format = "0.00%"
    worksheet["B15"].fill = PatternFill(
        "solid",
        fgColor=(
            "C6EFCE"
            if projected_health_pct >= 80
            else "FFEB9C" if projected_health_pct >= 60 else "FFC7CE"
        ),
    )
    worksheet["B16"].fill = PatternFill(
        "solid",
        fgColor=(
            "C6EFCE"
            if projected_pass_rate_pct >= 70
            else "FFEB9C" if projected_pass_rate_pct >= 40 else "FFC7CE"
        ),
    )
    worksheet["B17"].fill = PatternFill("solid", fgColor="C6EFCE")

    worksheet["G14"] = "TOP ISSUES TO FIX FIRST"
    worksheet["H14"] = "Affected URLs"
    for ref in ("G14", "H14"):
        worksheet[ref].fill = table_header_fill
        worksheet[ref].font = table_header_font
        worksheet[ref].alignment = Alignment(horizontal="center", vertical="center")
    if "FixPlan" in writer.book.sheetnames:
        fix_ws = writer.book["FixPlan"]
        fix_headers = header_index(fix_ws)
        issue_col = fix_headers.get("Issue Type")
        affected_col = fix_headers.get("Affected Count")
        priority_col = fix_headers.get("Priority Score")
        top_rows: list[tuple[str, int, int, int]] = []
        if issue_col and affected_col:
            for r in range(2, fix_ws.max_row + 1):
                issue_name = str(
                    fix_ws.cell(row=r, column=issue_col).value or ""
                ).strip()
                affected = to_int(fix_ws.cell(row=r, column=affected_col).value, 0)
                priority = (
                    to_int(fix_ws.cell(row=r, column=priority_col).value, 0)
                    if priority_col
                    else 0
                )
                if issue_name:
                    top_rows.append((issue_name, affected, priority, r))
        top_rows.sort(key=lambda x: (-x[1], -x[2], x[0]))
        for idx, (issue_name, affected, _priority, source_row) in enumerate(
            top_rows[:5], start=15
        ):
            worksheet[f"G{idx}"] = (
                f'=HYPERLINK("#FixPlan!A{source_row}","{issue_name}")'
            )
            worksheet[f"H{idx}"] = affected
            worksheet[f"G{idx}"].fill = PatternFill("solid", fgColor="F5F7FA")
            worksheet[f"H{idx}"].fill = PatternFill("solid", fgColor="F5F7FA")
            worksheet[f"G{idx}"].font = Font(
                color=STD_BLUE, underline="single", bold=True
            )

    quick_nav_fill = PatternFill("solid", fgColor=STD_NAVY)
    worksheet["I12"] = "Quick Navigation"
    worksheet["J12"] = "Open"
    for ref in ("I12", "J12"):
        worksheet[ref].fill = quick_nav_fill
        worksheet[ref].font = Font(color="000000", bold=True, size=11)
        worksheet[ref].alignment = Alignment(horizontal="center", vertical="center")
    quick_links = [
        ("Fix Plan", "#FixPlan!A1"),
        ("Main URL Data", "#Main!A1"),
        ("Technical Diagnostics", "#Technical!A1"),
        ("Indexability", "#Indexability!A1"),
        ("AEO Opportunities", "#AEO!A1"),
    ]
    quick_links.append(("AIOSEO Action Queue", "#AIOSEO!A1"))
    for idx, (label, target) in enumerate(quick_links, start=13):
        worksheet[f"I{idx}"] = label
        worksheet[f"J{idx}"] = f'=HYPERLINK("{target}","Open")'
        worksheet[f"J{idx}"].font = Font(color=STD_BLUE, underline="single", bold=True)
        worksheet[f"I{idx}"].fill = PatternFill("solid", fgColor="F5F7FA")
        worksheet[f"J{idx}"].fill = PatternFill("solid", fgColor="F5F7FA")
        worksheet[f"K{idx}"].fill = PatternFill("solid", fgColor="F5F7FA")

    worksheet["I4"] = "BUSINESS IMPACT SUMMARY"
    worksheet["I5"] = (
        f"{status_buckets['4xx Errors'] + status_buckets['5xx Errors']} error URLs detected "
        f"({status_buckets['4xx Errors']} 4xx / {status_buckets['5xx Errors']} 5xx). "
        f"Critical issue volume is {critical_urls} URLs and warning volume is {warning_urls}. "
        f"Top blocker: {top_issue_name} affecting {top_issue_affected} URLs."
    )
    worksheet.merge_cells("I4:K4")
    worksheet.merge_cells("I5:K10")
    worksheet["I4"].fill = table_header_fill
    worksheet["I4"].font = table_header_font
    worksheet["I4"].alignment = Alignment(horizontal="center", vertical="center")
    worksheet["I5"].fill = PatternFill("solid", fgColor="F5F7FA")
    worksheet["I5"].alignment = Alignment(
        horizontal="left", vertical="top", wrap_text=True
    )

    worksheet["G4"] = "Traditional SEO vs. 2026 AEO Readiness"
    worksheet["G5"] = "Dimension"
    worksheet["H5"] = "Score"
    for ref in ("G4", "G5", "H5"):
        worksheet[ref].fill = table_header_fill
        worksheet[ref].font = table_header_font
        worksheet[ref].alignment = Alignment(horizontal="center", vertical="center")
    worksheet.merge_cells("G4:H4")

    traditional_score = max(
        0.0, min(100.0, (success_count / max(1, crawl_denominator)) * 100.0)
    )
    if avg_health_score is not None:
        traditional_score = round(
            (traditional_score * 0.4) + (avg_health_score * 0.6), 2
        )
    aeo_score_values: list[float] = []
    if "AEO" in writer.book.sheetnames:
        aeo_ws = writer.book["AEO"]
        aeo_headers = header_index(aeo_ws)
        aeo_col = aeo_headers.get("AEO Readiness Score")
        if aeo_col:
            for r in range(2, aeo_ws.max_row + 1):
                try:
                    raw = aeo_ws.cell(row=r, column=aeo_col).value
                    if raw is not None and str(raw).strip() != "":
                        aeo_score_values.append(float(raw))
                except Exception:
                    pass
    aeo_readiness = (
        round(sum(aeo_score_values) / len(aeo_score_values), 2)
        if aeo_score_values
        else 0.0
    )
    worksheet["G6"] = "Traditional SEO"
    worksheet["H6"] = traditional_score / 100.0
    worksheet["H6"].number_format = "0.00%"
    worksheet["G7"] = "2026 AEO Readiness"
    worksheet["H7"] = aeo_readiness / 100.0
    worksheet["H7"].number_format = "0.00%"
    for ref in ("G6", "H6", "G7", "H7"):
        worksheet[ref].fill = PatternFill("solid", fgColor="F5F7FA")
        worksheet[ref].alignment = Alignment(horizontal="center", vertical="center")
    worksheet["G9"] = "Strategic Narrative"
    worksheet["G10"] = (
        "High SEO / Low AEO suggests the site is visible to humans but invisible to AI answer engines."
        if traditional_score >= 70 and aeo_readiness < 60
        else "SEO and AEO signals are moving together; continue balancing crawl health with answer-first content."
    )
    worksheet.merge_cells("G10:H12")
    worksheet["G9"].fill = table_header_fill
    worksheet["G9"].font = table_header_font
    worksheet["G9"].alignment = Alignment(horizontal="center", vertical="center")
    worksheet["G10"].fill = PatternFill("solid", fgColor="F5F7FA")
    worksheet["G10"].alignment = Alignment(
        horizontal="left", vertical="top", wrap_text=True
    )

    dashboard_tooltips = {
        "C5": "Total URLs crawled in this run. Calculated as the number of audited URL rows.",
        "C6": "Overall Health Score. Calculated as average SEO Health Score across Technical URLs; fallback to SEO Pass Rate if score data is unavailable.",
        "C7": "SEO Pass Rate %. Calculated as Pass URLs divided by Total URLs.",
        "C8": "Pass URL count. URL is pass when it has no Critical and no Warning issues.",
        "C9": "Critical URL count from Technical severity badge.",
        "C10": "Warning URL count from Technical severity badge.",
        "C11": "HTTP Error Rate %. Calculated as (4xx URLs + 5xx URLs) / Total URLs.",
        "C12": "Crawl Success Rate %. Calculated as 2xx URLs / Total URLs.",
        "C13": "Critical URL Rate %. Calculated as Critical URLs / Total URLs.",
        "C14": "Warning URL Rate %. Calculated as Warning URLs / Total URLs.",
        "C15": "Projected Health Score if all current To Do items are completed in this cycle.",
        "C16": "Projected Pass Rate if all current To Do items are completed in this cycle.",
        "C17": "Content Hub Readiness %. Count of literal ``Complete`` in Action Required divided by URLs tracked in column E.",
        "O5": "Most widespread issue from FixPlan by affected URL count.",
        "O6": "Number of URLs impacted by the top blocking issue.",
        "O7": "Total URLs returning client/server errors (4xx + 5xx).",
        "O8": "Average Time to First Byte across Technical URLs (ms).",
        "H15": "Affected URL count for the highest-priority issue (linked to FixPlan).",
        "H16": "Affected URL count for the next issue in the priority list.",
        "H17": "Affected URL count for the next issue in the priority list.",
        "H18": "Affected URL count for the next issue in the priority list.",
        "H19": "Affected URL count for the next issue in the priority list.",
        "G23": "Owner responsible for remediation. Click to open FixPlan.",
        "H23": "Number of issue rows assigned to this owner.",
        "I23": "Total affected URLs across this owner's assigned issues.",
        "J23": "Count of critical issue types assigned to this owner.",
        "K23": "Count of warning issue types assigned to this owner.",
    }
    for ref, message in dashboard_tooltips.items():
        dv = DataValidation(
            type="custom", formula1="TRUE", showInputMessage=True, allow_blank=True
        )
        dv.promptTitle = f"KPI {ref}"
        dv.prompt = message
        worksheet.add_data_validation(dv)
        dv.add(ref)
    for row_idx in range(4, 60):
        if row_idx in (15, 16):
            continue
        worksheet.row_dimensions[row_idx].height = 20
    for row_idx in range(5, 11):
        worksheet.row_dimensions[row_idx].height = max(
            float(worksheet.row_dimensions[row_idx].height or 20), 26.0
        )
    for row_idx in (9, 10, 11, 12):
        worksheet.row_dimensions[row_idx].height = max(
            float(worksheet.row_dimensions[row_idx].height or 20), 24.0
        )
    for row_idx in range(13, 18):
        worksheet.row_dimensions[row_idx].height = max(
            float(worksheet.row_dimensions[row_idx].height or 20), 22.0
        )
    for row_idx in range(14, 20):
        worksheet.row_dimensions[row_idx].height = max(
            float(worksheet.row_dimensions[row_idx].height or 20), 22.0
        )
    worksheet.row_dimensions[15].height = 35
    worksheet.row_dimensions[16].height = 35
    for row_idx in range(1, 70):
        for col_idx in range(1, 12):
            cell = worksheet.cell(row=row_idx, column=col_idx)
            if cell.value and cell.font and cell.font.bold:
                cell.alignment = Alignment(
                    horizontal=(
                        cell.alignment.horizontal if cell.alignment else "center"
                    ),
                    vertical=cell.alignment.vertical if cell.alignment else "center",
                    wrap_text=True,
                )


__all__ = ["style_dashboard"]
