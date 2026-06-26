"""Executive Dashboard — KPI cards and charts backed by visible source rows."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from openpyxl.chart import BarChart, DoughnutChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.chart.series import DataPoint
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from hype_frog.core.models import ExtraRowPayload, MainRowPayload, SummaryMetricsPayload
from hype_frog.reporter.chart_compat import configure_openpyxl_chart_for_excel
from hype_frog.reporter.dashboard_logic import (
    DashboardComputationResult,
    FixPlanRowPayload,
    compute_dashboard_metrics,
)
from hype_frog.reporter.engine_io import _safe_sheet_name, _sanitize_excel_value
from hype_frog.reporter.sheets.config import EXECUTIVE_DASHBOARD_SHEET, STD_NAVY

_KPI_FILL = PatternFill("solid", fgColor="DCE3EA")
_SECTION_FILL = PatternFill("solid", fgColor="E5E7EB")
_SOURCE_FILL = PatternFill("solid", fgColor="F3F4F6")
_INSIGHT_FILL = PatternFill("solid", fgColor="F5F7FA")

_KEY_INSIGHTS_ROW = 5

# Visual grid: rows 1–58 are charts/KPIs; row 59 hint; source tables from row 60.
_CHART_BAND_ROW_HEIGHT_PT = 15.0
_LEFT_CHART_COL = "A"
_RIGHT_CHART_COL = "G"
_CHART_BAND_ROWS = 12

_ROW_SEC_HEALTH = 6
_ROW_CH_HEALTH = 7

_ROW_SEC_ISSUES = 19
_ROW_CH_ISSUES = 20

_ROW_SEC_ACTIONS = 32
_ROW_CH_ACTIONS = 33

_ROW_SEC_TOP_ISSUES = 45
_ROW_CH_TOP_ISSUES = 46

_SOURCE_DATA_HINT_ROW = 59

# Chart size presets (cm): full-width and half-sheet (A–F / G–L).
_SIZE_HEALTH_FULL = (18.0, 7.8)
_SIZE_HALF_CHART = (9.2, 7.0)
_SIZE_DOUGHNUT = (9.0, 7.2)
_SIZE_TOP_ISSUES = (18.0, 6.8)

_LOW_VALUE_URL_PATH_TOKENS: tuple[str, ...] = (
    "cart",
    "checkout",
    "thank-you",
    "thankyou",
    "thanks",
    "order-received",
    "sponsorship",
    "sponsor",
    "donate",
    "login",
    "sign-in",
    "signin",
    "my-account",
    "account",
    "wp-json",
    "/feed",
    "attachment",
    "privacy-policy",
    "terms",
)

# Chart tables in visible columns A–C below the chart area (Excel ignores hidden cols by default).
CHART_SOURCE_FIRST_ROW = 60
CHART_LABEL_COL = 1
CHART_VALUE_COL = 2
CHART_VALUE2_COL = 3

# Doughnut slice colours — 6-digit RRGGBB only (Excel ``srgbClr`` rejects 8-digit ARGB).
_SEVERITY_SLICE_COLORS: tuple[str, ...] = ("C00000", "ED7D31", "BFBFBF")
_OWNER_SLICE_COLORS: tuple[str, ...] = (
    "4472C4",
    "70AD47",
    "7030A0",
    "A6A6A6",
    "FFC000",
)


@dataclass(frozen=True)
class ChartDataLayout:
    """1-based row anchors for chart source tables (columns A–C)."""

    health_start: int = CHART_SOURCE_FIRST_ROW + 1
    health_rows: int = 4
    severity_start: int = CHART_SOURCE_FIRST_ROW + 9
    severity_rows: int = 3
    owner_start: int = CHART_SOURCE_FIRST_ROW + 16
    owner_rows: int = 0
    priority_start: int = CHART_SOURCE_FIRST_ROW + 25
    priority_rows: int = 0
    content_start: int = CHART_SOURCE_FIRST_ROW + 37
    content_rows: int = 5
    projected_start: int = CHART_SOURCE_FIRST_ROW + 45
    projected_rows: int = 2
    top_issues_start: int = CHART_SOURCE_FIRST_ROW + 50
    top_issues_rows: int = 0


def _label_col() -> int:
    return CHART_LABEL_COL


def _value_col() -> int:
    return CHART_VALUE_COL


def _value_col_2() -> int:
    return CHART_VALUE2_COL


def _normalize_chart_rgb(color: str) -> str:
    cleaned = color.strip().lstrip("#").upper()
    if len(cleaned) == 8:
        cleaned = cleaned[2:]
    return cleaned[:6]


def _write_label_cell(ws: Worksheet, row: int, value: object) -> None:
    cell = ws.cell(row=row, column=_label_col(), value=_sanitize_excel_value(str(value)))
    cell.data_type = "s"


def _to_float(value: object, default: float = 0.0) -> float:
    if value is None or str(value).strip() == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _optional_float(value: object) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out:
        return None
    return out


def _short_url_label(url: object, *, max_len: int = 36) -> str:
    raw = str(url or "").strip()
    if not raw:
        return "(no url)"
    path = urlparse(raw).path or "/"
    if path == "/":
        label = raw.replace("https://", "").replace("http://", "").rstrip("/") or "/"
    else:
        label = path.strip("/")
        if len(label) > max_len:
            label = "…" + label[-(max_len - 1) :]
    return _sanitize_excel_value(label) or "(url)"


def _avg_psi_score(extra_rows: list[dict[str, Any]]) -> float | None:
    scores: list[float] = []
    for row in extra_rows:
        for key in ("Mobile PSI Score", "Desktop PSI Score"):
            val = _optional_float(row.get(key))
            if val is not None and val > 0:
                scores.append(val)
    if not scores:
        return None
    return round(sum(scores) / len(scores), 1)


def _content_readiness_percentages(
    extra_rows: list[dict[str, Any]],
) -> list[tuple[str, float]]:
    total = len(extra_rows)
    if total <= 0:
        return [
            ("Good H1", 0.0),
            ("Meta description", 0.0),
            ("Answer paragraphs", 0.0),
            ("Schema present", 0.0),
            ("Image alt ≥80%", 0.0),
            ("Question headings", 0.0),
        ]

    def pct(count: int) -> float:
        return round((count / total) * 100.0, 1)

    good_h1 = sum(
        1
        for row in extra_rows
        if not bool(row.get("Missing H1 Flag")) and int(row.get("H1 Count") or 0) > 0
    )
    good_meta = sum(1 for row in extra_rows if not bool(row.get("Meta Description Missing")))
    answer_blocks = sum(
        1 for row in extra_rows if int(row.get("Paragraphs 40-60 Words Count") or 0) > 0
    )
    schema = sum(1 for row in extra_rows if int(row.get("Schema Types Count") or 0) > 0)
    alt_ok = sum(
        1 for row in extra_rows if _to_float(row.get("Image Alt Coverage (%)")) >= 80.0
    )
    question_headings = sum(
        1 for row in extra_rows if int(row.get("Question Heading Count") or 0) > 0
    )
    return [
        ("Good H1", pct(good_h1)),
        ("Meta description", pct(good_meta)),
        ("Answer paragraphs", pct(answer_blocks)),
        ("Schema present", pct(schema)),
        ("Image alt ≥80%", pct(alt_ok)),
        ("Question headings", pct(question_headings)),
    ]


def _traffic_lift_total(hub_metrics_rows: list[dict[str, Any]] | None) -> int:
    if not hub_metrics_rows:
        return 0
    return int(
        round(
            sum(_to_float(row.get("Potential Traffic Lift"), 0.0) for row in hub_metrics_rows)
        )
    )


def _normalize_fixplan_severity(raw: object) -> str:
    sev = str(raw or "").strip().lower()
    if sev == "critical":
        return "Critical"
    if sev in {"warning", "high"}:
        return "Warning"
    if sev in {"observation", "medium", "low", "info"}:
        return "Observation"
    return "Observation"


def _severity_metrics(
    extra_rows: list[dict[str, Any]],
    fixplan_rows: list[dict[str, Any]],
) -> list[tuple[str, int, int]]:
    """Return (label, unique_urls, issue_instances) per severity tier."""
    unique_urls: Counter[str] = Counter()
    for row in extra_rows:
        badge = str(row.get("Severity Badge") or "").strip()
        if badge == "Critical":
            unique_urls["Critical"] += 1
        elif badge == "Warning":
            unique_urls["Warning"] += 1
        elif badge in {"Observation", "Info"}:
            unique_urls["Observation"] += 1

    issue_instances: Counter[str] = Counter()
    for row in fixplan_rows:
        tier = _normalize_fixplan_severity(row.get("Severity"))
        issue_instances[tier] += int(row.get("Affected Count") or 0)

    rows: list[tuple[str, int, int]] = []
    for label in ("Critical", "Warning", "Observation"):
        url_count = unique_urls.get(label, 0)
        instance_count = issue_instances.get(label, 0)
        if url_count > 0 or instance_count > 0:
            rows.append((label, url_count, instance_count))
    if not rows:
        return [("No open issues", 0, 0)]
    return rows


def _owner_metrics(
    extra_rows: list[dict[str, Any]],
    fixplan_rows: list[dict[str, Any]],
) -> list[tuple[str, int, int]]:
    """Return (owner, unique_urls, issue_instances) sorted by unique URL count."""
    urls_by_owner: dict[str, set[str]] = defaultdict(set)
    for row in extra_rows:
        badge = str(row.get("Severity Badge") or "").strip()
        if badge not in {"Critical", "Warning", "Observation", "Info"}:
            continue
        owner = str(row.get("Owner") or "Unassigned").strip() or "Unassigned"
        url = str(row.get("URL") or "").strip()
        if url:
            urls_by_owner[owner].add(url)

    instances_by_owner: Counter[str] = Counter()
    for row in fixplan_rows:
        owner = str(row.get("Owner") or "Unassigned").strip() or "Unassigned"
        instances_by_owner[owner] += int(row.get("Affected Count") or 0)

    owners = set(urls_by_owner) | set(instances_by_owner)
    if not owners:
        return [("Unassigned", 0, 0)]

    ranked = sorted(
        owners,
        key=lambda name: (
            -len(urls_by_owner.get(name, set())),
            -instances_by_owner.get(name, 0),
            name,
        ),
    )
    return [
        (
            owner,
            len(urls_by_owner.get(owner, set())),
            instances_by_owner.get(owner, 0),
        )
        for owner in ranked[:8]
    ]


def _to_do_share(summary_metrics: SummaryMetricsPayload) -> float:
    total = max(1, summary_metrics.urls_crawled)
    return (summary_metrics.critical_url_count + summary_metrics.warning_url_count) / total


def _project_component_score(current: float, summary_metrics: SummaryMetricsPayload) -> float:
    """Mirror export_flow projected-health uplift (0.9 × open-issue share)."""
    share = _to_do_share(summary_metrics)
    return min(
        100.0,
        round(current + max(0.0, 100.0 - current) * share * 0.9, 1),
    )


def _avg_technical_health(extra_rows: list[dict[str, Any]], fallback: float) -> float:
    values: list[float] = []
    for row in extra_rows:
        for key in ("Technical Health", "SEO Health Score"):
            val = _optional_float(row.get(key))
            if val is not None and val >= 0:
                values.append(val)
                break
    if not values:
        return round(fallback, 1)
    return round(sum(values) / len(values), 1)


def _is_low_value_priority_url(url: object) -> bool:
    path = urlparse(str(url or "")).path.lower()
    return any(token in path for token in _LOW_VALUE_URL_PATH_TOKENS)


def _meaningful_priority_rows(
    priority_rows: list[dict[str, Any]],
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Prefer high-intent URLs for the business-risk chart (exclude cart/checkout/etc.)."""
    ranked = sorted(
        priority_rows,
        key=lambda item: _to_float(item.get("Business Risk Score"), 0.0),
        reverse=True,
    )
    filtered = [row for row in ranked if not _is_low_value_priority_url(row.get("URL"))]
    if filtered:
        return filtered[:limit]
    return ranked[:limit]


def _build_key_insights(
    summary_metrics: SummaryMetricsPayload,
    dashboard_metrics: DashboardComputationResult,
) -> list[str]:
    insights: list[str] = []
    if summary_metrics.critical_url_count > 0:
        insights.append(
            f"{summary_metrics.critical_url_count} URL(s) carry a Critical badge and need urgent attention."
        )
    if summary_metrics.warning_url_count > 0:
        insights.append(
            f"{summary_metrics.warning_url_count} URL(s) are in Warning state — schedule fixes before they escalate."
        )
    if dashboard_metrics.top_issue_rows:
        lead = dashboard_metrics.top_issue_rows[0]
        insights.append(
            f"Largest theme: \"{lead.issue_name}\" touches {lead.affected_urls} URL(s) (see Fix Plan)."
        )
    if dashboard_metrics.aeo_readiness < 70:
        insights.append(
            f"AEO readiness averages {dashboard_metrics.aeo_readiness:.0f}% — structure and schema gaps may limit AI visibility."
        )
    if dashboard_metrics.error_count > 0:
        insights.append(
            f"{dashboard_metrics.error_count} URL(s) returned 4xx/5xx during the crawl."
        )
    if not insights:
        insights.append(
            f"Site SEO health is {summary_metrics.health_score_pct:.0f}% with no Critical URLs in this crawl."
        )
    return insights[:4]


def _reserve_chart_band(
    exec_ws: Worksheet,
    start_row: int,
    row_count: int,
    *,
    row_height_pt: float = _CHART_BAND_ROW_HEIGHT_PT,
) -> None:
    """Reserve vertical space so openpyxl charts (sized in cm) do not overlap."""
    for offset in range(row_count):
        exec_ws.row_dimensions[start_row + offset].height = row_height_pt


def _apply_executive_column_grid(exec_ws: Worksheet) -> None:
    """Even column widths so left (A–F) and right (G–L) halves use full sheet width."""
    for col_idx in range(1, 13):
        exec_ws.column_dimensions[get_column_letter(col_idx)].width = 12.0


def _write_source_data_hint(exec_ws: Worksheet) -> None:
    exec_ws.merge_cells(f"A{_SOURCE_DATA_HINT_ROW}:L{_SOURCE_DATA_HINT_ROW}")
    hint = exec_ws.cell(
        row=_SOURCE_DATA_HINT_ROW,
        column=1,
        value=f"▼ Chart source data begins row {CHART_SOURCE_FIRST_ROW} (columns A–C)",
    )
    hint.font = Font(italic=True, size=9, color="666666")
    hint.fill = _SOURCE_FILL
    hint.alignment = Alignment(horizontal="center", vertical="center")
    exec_ws.row_dimensions[_SOURCE_DATA_HINT_ROW].height = 18


def _apply_chart_size(chart: BarChart | DoughnutChart, width_cm: float, height_cm: float) -> None:
    chart.width = width_cm
    chart.height = height_cm


def _write_section_header(
    exec_ws: Worksheet,
    row: int,
    title: str,
    *,
    merge_to_col: int = 12,
) -> None:
    merge = f"A{row}:{get_column_letter(merge_to_col)}{row}"
    exec_ws.merge_cells(merge)
    cell = exec_ws.cell(row=row, column=1, value=title)
    cell.fill = _SECTION_FILL
    cell.font = Font(bold=True, color=STD_NAVY, size=11)
    cell.alignment = Alignment(horizontal="left", vertical="center")
    exec_ws.row_dimensions[row].height = 22


def _write_key_insights(
    exec_ws: Worksheet,
    insights: list[str],
) -> None:
    exec_ws.merge_cells(f"A{_KEY_INSIGHTS_ROW}:L{_KEY_INSIGHTS_ROW}")
    body = exec_ws.cell(
        row=_KEY_INSIGHTS_ROW,
        column=1,
        value="Key insights: " + " | ".join(insights),
    )
    body.fill = _INSIGHT_FILL
    body.font = Font(size=9, color="1F2937")
    body.alignment = Alignment(wrap_text=True, vertical="center", horizontal="left")
    exec_ws.row_dimensions[_KEY_INSIGHTS_ROW].height = 32


def _top_issues_by_impact(
    fixplan_rows: list[dict[str, Any]],
    *,
    limit: int = 8,
) -> list[tuple[str, int]]:
    ranked = sorted(
        fixplan_rows,
        key=lambda row: int(row.get("Affected Count") or 0),
        reverse=True,
    )
    issues: list[tuple[str, int]] = []
    for row in ranked:
        count = int(row.get("Affected Count") or 0)
        if count <= 0:
            continue
        name = _sanitize_excel_value(str(row.get("Issue Type") or "Unknown")) or "Unknown"
        if len(name) > 42:
            name = name[:39] + "…"
        issues.append((name, count))
        if len(issues) >= limit:
            break
    return issues


def _build_projection_narrative(summary_metrics: SummaryMetricsPayload) -> str:
    total = max(1, summary_metrics.urls_crawled)
    open_urls = summary_metrics.critical_url_count + summary_metrics.warning_url_count
    open_pct = round((open_urls / total) * 100.0)
    gap = max(
        0.0,
        summary_metrics.projected_health_score_pct - summary_metrics.health_score_pct,
    )
    return (
        f"SEO health is {summary_metrics.health_score_pct:.0f}% across {total} crawled URLs. "
        f"{open_urls} URL(s) ({open_pct}%) carry Critical or Warning badges. "
        f"If those were cleared, blended SEO health could reach ~"
        f"{summary_metrics.projected_health_score_pct:.0f}% (+{gap:.0f} pts) — "
        f"an illustrative ceiling from the export model (90% of remaining headroom × open-issue share). "
        f"Technical, PSI, and AEO components use the same conservative formula in the chart below; "
        f"they are not guaranteed to move in lockstep. Source tables: row {CHART_SOURCE_FIRST_ROW}+."
    )


def populate_chart_data_sheet(
    ws: Worksheet,
    *,
    summary_metrics: SummaryMetricsPayload,
    dashboard_metrics: DashboardComputationResult,
    extra_rows: list[dict[str, Any]],
    priority_rows: list[dict[str, Any]],
    fixplan_rows: list[dict[str, Any]],
    hub_metrics_rows: list[dict[str, Any]] | None,
) -> ChartDataLayout:
    """Write chart source tables in visible columns A–C (no merged cells in data)."""
    layout = ChartDataLayout()
    psi = _avg_psi_score(extra_rows)
    aeo = round(dashboard_metrics.aeo_readiness, 1)
    current_health = round(summary_metrics.health_score_pct, 1)
    projected_health = round(summary_metrics.projected_health_score_pct, 1)
    technical_health = _avg_technical_health(extra_rows, dashboard_metrics.overall_health)
    label_col = _label_col()
    value_col = _value_col()
    value_col_2 = _value_col_2()
    projected_technical = _project_component_score(technical_health, summary_metrics)
    projected_psi = _project_component_score(psi or 0.0, summary_metrics) if psi else 0.0
    projected_aeo = _project_component_score(aeo, summary_metrics)

    ws.merge_cells(
        start_row=CHART_SOURCE_FIRST_ROW,
        start_column=CHART_LABEL_COL,
        end_row=CHART_SOURCE_FIRST_ROW,
        end_column=CHART_VALUE2_COL,
    )
    banner = ws.cell(row=CHART_SOURCE_FIRST_ROW, column=CHART_LABEL_COL)
    banner.value = "Chart source data (scroll down — used by charts above)"
    banner.font = Font(bold=True, size=9, color="666666")
    banner.fill = _SOURCE_FILL

    _write_label_cell(ws, layout.health_start, "Health comparison")
    hr = layout.health_start + 1
    _write_label_cell(ws, hr, "Metric")
    ws.cell(row=hr, column=value_col, value="Current")
    ws.cell(row=hr, column=value_col_2, value="Illustrative projected")
    health_rows = [
        ("SEO Health", current_health, projected_health),
        ("Technical Health", technical_health, projected_technical),
        ("Performance (PSI)", psi or 0.0, projected_psi),
        ("AEO Readiness", aeo, projected_aeo),
    ]
    data_row = hr + 1
    for metric, current, projected in health_rows:
        _write_label_cell(ws, data_row, metric)
        ws.cell(row=data_row, column=value_col, value=current)
        ws.cell(row=data_row, column=value_col_2, value=projected)
        data_row += 1
    layout = ChartDataLayout(
        health_start=layout.health_start,
        health_rows=len(health_rows),
        severity_start=layout.severity_start,
    )

    _write_label_cell(ws, layout.severity_start, "Severity — unique URLs vs issue instances")
    sr = layout.severity_start + 1
    _write_label_cell(ws, sr, "Severity")
    ws.cell(row=sr, column=value_col, value="Unique URLs")
    ws.cell(row=sr, column=value_col_2, value="Issue instances")
    severity = _severity_metrics(extra_rows, fixplan_rows)
    layout = ChartDataLayout(
        health_start=layout.health_start,
        health_rows=layout.health_rows,
        severity_start=layout.severity_start,
        severity_rows=len(severity),
    )
    for idx, (label, unique_urls, issue_instances) in enumerate(severity, start=sr + 1):
        _write_label_cell(ws, idx, label)
        ws.cell(row=idx, column=value_col, value=unique_urls)
        ws.cell(row=idx, column=value_col_2, value=issue_instances)

    _write_label_cell(ws, layout.owner_start, "Owner workload — unique URLs vs issue instances")
    orow = layout.owner_start + 1
    _write_label_cell(ws, orow, "Owner")
    ws.cell(row=orow, column=value_col, value="Unique URLs")
    ws.cell(row=orow, column=value_col_2, value="Issue instances")
    owners = _owner_metrics(extra_rows, fixplan_rows)
    layout = ChartDataLayout(
        health_start=layout.health_start,
        health_rows=layout.health_rows,
        severity_start=layout.severity_start,
        severity_rows=layout.severity_rows,
        owner_start=layout.owner_start,
        owner_rows=len(owners),
    )
    for idx, (owner, unique_urls, issue_instances) in enumerate(owners, start=orow + 1):
        _write_label_cell(ws, idx, owner)
        ws.cell(row=idx, column=value_col, value=unique_urls)
        ws.cell(row=idx, column=value_col_2, value=issue_instances)

    _write_label_cell(
        ws,
        layout.priority_start,
        "Top business risk URLs (chart excludes cart/checkout/thank-you pages)",
    )
    pr = layout.priority_start + 1
    _write_label_cell(ws, pr, "Page")
    ws.cell(row=pr, column=value_col, value="Business Risk Score")
    top_priority = _meaningful_priority_rows(priority_rows, limit=8)
    layout = ChartDataLayout(
        health_start=layout.health_start,
        health_rows=layout.health_rows,
        severity_start=layout.severity_start,
        severity_rows=layout.severity_rows,
        owner_start=layout.owner_start,
        owner_rows=layout.owner_rows,
        priority_start=layout.priority_start,
        priority_rows=len(top_priority),
    )
    for idx, row_dict in enumerate(top_priority, start=pr + 1):
        _write_label_cell(ws, idx, _short_url_label(row_dict.get("URL")))
        ws.cell(row=idx, column=value_col, value=_to_float(row_dict.get("Business Risk Score"), 0.0))

    _write_label_cell(ws, layout.content_start, "Content readiness")
    cr = layout.content_start + 1
    _write_label_cell(ws, cr, "Metric")
    ws.cell(row=cr, column=value_col, value="Percent")
    content = _content_readiness_percentages(extra_rows)
    for idx, (label, pct) in enumerate(content, start=cr + 1):
        _write_label_cell(ws, idx, label)
        ws.cell(row=idx, column=value_col, value=pct)

    _write_label_cell(ws, layout.projected_start, "SEO health — export projection model")
    pj = layout.projected_start + 1
    _write_label_cell(ws, pj, "Metric")
    ws.cell(row=pj, column=value_col, value="Percent")
    _write_label_cell(ws, pj + 1, "Current SEO Health")
    ws.cell(row=pj + 1, column=value_col, value=current_health)
    _write_label_cell(ws, pj + 2, "Illustrative projected SEO Health")
    ws.cell(row=pj + 2, column=value_col, value=projected_health)
    note_row = pj + 3
    _write_label_cell(
        ws,
        note_row,
        "Model: current + (100-current) × open-issue share × 0.9 (matches export_flow)",
    )

    top_issues_start = CHART_SOURCE_FIRST_ROW + 50
    _write_label_cell(ws, top_issues_start, "Top issues by URL impact")
    tir = top_issues_start + 1
    _write_label_cell(ws, tir, "Issue")
    ws.cell(row=tir, column=value_col, value="Affected URLs")
    top_issues = _top_issues_by_impact(fixplan_rows, limit=8)
    for idx, (issue_name, affected) in enumerate(top_issues, start=tir + 1):
        _write_label_cell(ws, idx, issue_name)
        ws.cell(row=idx, column=value_col, value=affected)

    return ChartDataLayout(
        health_start=layout.health_start,
        health_rows=layout.health_rows,
        severity_start=layout.severity_start,
        severity_rows=layout.severity_rows,
        owner_start=layout.owner_start,
        owner_rows=layout.owner_rows,
        priority_start=layout.priority_start,
        priority_rows=layout.priority_rows,
        content_start=layout.content_start,
        content_rows=len(content),
        projected_start=layout.projected_start,
        projected_rows=2,
        top_issues_start=top_issues_start,
        top_issues_rows=len(top_issues),
    )


def _attach_chart(exec_ws: Worksheet, chart: BarChart | DoughnutChart, anchor: str) -> None:
    configure_openpyxl_chart_for_excel(chart)
    exec_ws.add_chart(chart, anchor)


def _apply_doughnut_colors(
    chart: DoughnutChart,
    colors: tuple[str, ...],
    *,
    point_count: int,
) -> None:
    if point_count <= 0 or not chart.series:
        return
    series = chart.series[0]
    for point_idx in range(point_count):
        color = _normalize_chart_rgb(colors[point_idx % len(colors)])
        pt = DataPoint(idx=point_idx)
        pt.graphicalProperties.solidFill = color
        series.data_points.append(pt)


def _add_health_comparison_chart(
    exec_ws: Worksheet,
    layout: ChartDataLayout,
    anchor: str,
) -> None:
    header_row = layout.health_start + 1
    first_data = header_row + 1
    last_data = first_data + layout.health_rows - 1
    chart = BarChart()
    chart.type = "col"
    chart.grouping = "clustered"
    chart.title = "Health components — current vs illustrative projected"
    chart.y_axis.title = "Score"
    chart.x_axis.title = "Metric"
    chart.legend.position = "b"
    _apply_chart_size(chart, *_SIZE_HEALTH_FULL)
    data = Reference(
        exec_ws,
        min_col=_value_col(),
        min_row=header_row,
        max_col=_value_col_2(),
        max_row=last_data,
    )
    cats = Reference(
        exec_ws,
        min_col=_label_col(),
        min_row=first_data,
        max_row=last_data,
    )
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    _attach_chart(exec_ws, chart, anchor)


def _add_doughnut_chart(
    exec_ws: Worksheet,
    *,
    title: str,
    header_row: int,
    data_rows: int,
    anchor: str,
    colors: tuple[str, ...],
    value_col: int | None = None,
) -> None:
    if data_rows <= 0:
        return
    first_data = header_row + 1
    last_data = header_row + data_rows
    series_col = value_col if value_col is not None else _value_col()
    total = sum(
        _to_float(exec_ws.cell(row=r, column=series_col).value, 0.0)
        for r in range(first_data, last_data + 1)
    )
    if total <= 0:
        return
    chart = DoughnutChart()
    chart.title = title
    chart.legend.position = "r"
    _apply_chart_size(chart, *_SIZE_DOUGHNUT)
    data = Reference(exec_ws, min_col=series_col, min_row=header_row, max_row=last_data)
    cats = Reference(exec_ws, min_col=_label_col(), min_row=first_data, max_row=last_data)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    chart.dataLabels = DataLabelList()
    chart.dataLabels.showPercent = True
    chart.dataLabels.showCatName = True
    _apply_doughnut_colors(chart, colors, point_count=data_rows)
    _attach_chart(exec_ws, chart, anchor)


def _add_severity_comparison_chart(
    exec_ws: Worksheet,
    layout: ChartDataLayout,
    anchor: str,
) -> None:
    if layout.severity_rows <= 0:
        return
    header_row = layout.severity_start + 1
    first_data = header_row + 1
    last_data = header_row + layout.severity_rows
    chart = BarChart()
    chart.type = "col"
    chart.grouping = "clustered"
    chart.title = "Issue severity — unique URLs vs instances"
    chart.y_axis.title = "Count"
    chart.x_axis.title = "Severity"
    chart.legend.position = "b"
    _apply_chart_size(chart, *_SIZE_HALF_CHART)
    data = Reference(
        exec_ws,
        min_col=_value_col(),
        min_row=header_row,
        max_col=_value_col_2(),
        max_row=last_data,
    )
    cats = Reference(
        exec_ws,
        min_col=_label_col(),
        min_row=first_data,
        max_row=last_data,
    )
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    _attach_chart(exec_ws, chart, anchor)


def _add_priority_bar_chart(
    exec_ws: Worksheet,
    layout: ChartDataLayout,
    anchor: str,
) -> None:
    if layout.priority_rows <= 0:
        return
    header_row = layout.priority_start + 1
    first_data = header_row + 1
    last_data = header_row + layout.priority_rows
    chart = BarChart()
    chart.type = "bar"
    chart.title = "High-intent pages by business risk"
    chart.x_axis.title = "Business risk score"
    chart.y_axis.title = "Page"
    chart.legend = None
    _apply_chart_size(chart, *_SIZE_HALF_CHART)
    data = Reference(exec_ws, min_col=_value_col(), min_row=header_row, max_row=last_data)
    cats = Reference(exec_ws, min_col=_label_col(), min_row=first_data, max_row=last_data)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    _attach_chart(exec_ws, chart, anchor)


def _add_content_readiness_bar_chart(
    exec_ws: Worksheet,
    layout: ChartDataLayout,
    anchor: str,
) -> None:
    if layout.content_rows <= 0:
        return
    header_row = layout.content_start + 1
    first_data = header_row + 1
    last_data = header_row + layout.content_rows
    chart = BarChart()
    chart.type = "bar"
    chart.title = "Content & AEO readiness (% URLs)"
    chart.x_axis.title = "Percent of URLs"
    chart.y_axis.title = "Signal"
    chart.legend = None
    _apply_chart_size(chart, *_SIZE_HALF_CHART)
    data = Reference(exec_ws, min_col=_value_col(), min_row=header_row, max_row=last_data)
    cats = Reference(exec_ws, min_col=_label_col(), min_row=first_data, max_row=last_data)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    _attach_chart(exec_ws, chart, anchor)


def _add_top_issues_chart(
    exec_ws: Worksheet,
    layout: ChartDataLayout,
    anchor: str,
) -> None:
    if layout.top_issues_rows <= 0:
        return
    header_row = layout.top_issues_start + 1
    first_data = header_row + 1
    last_data = header_row + layout.top_issues_rows
    chart = BarChart()
    chart.type = "bar"
    chart.title = "Top issues by URL impact (Fix Plan)"
    chart.x_axis.title = "Affected URLs"
    chart.y_axis.title = "Issue"
    chart.legend = None
    _apply_chart_size(chart, *_SIZE_TOP_ISSUES)
    data = Reference(exec_ws, min_col=_value_col(), min_row=header_row, max_row=last_data)
    cats = Reference(exec_ws, min_col=_label_col(), min_row=first_data, max_row=last_data)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    _attach_chart(exec_ws, chart, anchor)


def _write_kpi_cards(
    exec_ws: Worksheet,
    *,
    summary_metrics: SummaryMetricsPayload,
    dashboard_metrics: DashboardComputationResult,
    traffic_lift: int,
    psi: float | None,
) -> None:
    exec_ws.merge_cells("A1:L1")
    title = exec_ws["A1"]
    title.value = "Executive Dashboard — Visual Summary"
    title.font = Font(bold=True, size=16, color=STD_NAVY)
    title.alignment = Alignment(horizontal="left", vertical="center")

    exec_ws.merge_cells("A2:L2")
    subtitle = exec_ws["A2"]
    subtitle.value = _build_projection_narrative(summary_metrics)
    subtitle.alignment = Alignment(wrap_text=True, vertical="top")
    subtitle.font = Font(size=9, color="374151")
    exec_ws.row_dimensions[2].height = 40

    cards: list[tuple[str, str]] = [
        ("SEO Health (now)", f"{summary_metrics.health_score_pct:.0f}%"),
        (
            "SEO Health (illustrative projected)",
            f"{summary_metrics.projected_health_score_pct:.0f}%",
        ),
        ("AEO Readiness", f"{dashboard_metrics.aeo_readiness:.0f}%"),
        ("Critical URLs", str(summary_metrics.critical_url_count)),
        ("Traffic Lift (est.)", str(traffic_lift)),
        (
            "Performance (PSI)",
            f"{psi:.0f}" if psi is not None else "N/A",
        ),
    ]
    positions = [(1, 3), (3, 3), (5, 3), (7, 3), (9, 3), (11, 3)]
    exec_ws.row_dimensions[3].height = 20
    exec_ws.row_dimensions[4].height = 30
    for (col, row), (label, value) in zip(positions, cards, strict=False):
        end_col = col + 1
        label_merge = f"{get_column_letter(col)}{row}:{get_column_letter(end_col)}{row}"
        value_merge = f"{get_column_letter(col)}{row + 1}:{get_column_letter(end_col)}{row + 1}"
        exec_ws.merge_cells(label_merge)
        exec_ws.merge_cells(value_merge)
        label_cell = exec_ws.cell(row=row, column=col, value=label)
        label_cell.font = Font(bold=True, size=10, color=STD_NAVY)
        label_cell.fill = _KPI_FILL
        label_cell.alignment = Alignment(horizontal="center")
        value_cell = exec_ws.cell(row=row + 1, column=col, value=value)
        value_cell.font = Font(bold=True, size=18)
        value_cell.fill = _KPI_FILL
        value_cell.alignment = Alignment(horizontal="center")


def write_executive_dashboard(
    writer: Any,
    *,
    summary_metrics: SummaryMetricsPayload,
    typed_main_rows: list[MainRowPayload],
    typed_extra_rows: list[ExtraRowPayload],
    priority_rows: list[dict[str, Any]],
    fixplan_rows: list[dict[str, Any]],
    hub_metrics_rows: list[dict[str, Any]] | None = None,
) -> None:
    """Create visual Executive Dashboard worksheet with same-sheet chart sources."""
    book = writer.book
    if EXECUTIVE_DASHBOARD_SHEET in book.sheetnames:
        del book[EXECUTIVE_DASHBOARD_SHEET]

    exec_ws = book.create_sheet(title=_safe_sheet_name(EXECUTIVE_DASHBOARD_SHEET))
    writer.sheets[EXECUTIVE_DASHBOARD_SHEET] = exec_ws

    extra_rows = [dict(row.values) for row in typed_extra_rows]
    fixplan_payloads = [
        FixPlanRowPayload.model_validate({**row, "source_row": idx})
        for idx, row in enumerate(fixplan_rows, start=2)
    ]
    dashboard_metrics = compute_dashboard_metrics(
        summary_metrics=summary_metrics,
        technical_main_rows=typed_main_rows,
        technical_extra_rows=typed_extra_rows,
        fixplan_rows=fixplan_payloads,
        aeo_rows=typed_extra_rows,
    )
    layout = populate_chart_data_sheet(
        exec_ws,
        summary_metrics=summary_metrics,
        dashboard_metrics=dashboard_metrics,
        extra_rows=extra_rows,
        priority_rows=priority_rows,
        fixplan_rows=fixplan_rows,
        hub_metrics_rows=hub_metrics_rows,
    )

    psi = _avg_psi_score(extra_rows)
    traffic_lift = _traffic_lift_total(hub_metrics_rows)
    _write_kpi_cards(
        exec_ws,
        summary_metrics=summary_metrics,
        dashboard_metrics=dashboard_metrics,
        traffic_lift=traffic_lift,
        psi=psi,
    )
    _apply_executive_column_grid(exec_ws)
    _write_key_insights(
        exec_ws,
        _build_key_insights(summary_metrics, dashboard_metrics),
    )

    _write_section_header(exec_ws, _ROW_SEC_HEALTH, "Health & illustrative projection")
    _reserve_chart_band(exec_ws, _ROW_CH_HEALTH, _CHART_BAND_ROWS)
    _add_health_comparison_chart(
        exec_ws,
        layout,
        f"{_LEFT_CHART_COL}{_ROW_CH_HEALTH}",
    )

    _write_section_header(
        exec_ws,
        _ROW_SEC_ISSUES,
        "Issue distribution — unique URLs vs issue instances (see source row 60+)",
    )
    severity_header = layout.severity_start + 1
    owner_header = layout.owner_start + 1
    _reserve_chart_band(exec_ws, _ROW_CH_ISSUES, _CHART_BAND_ROWS)
    _add_severity_comparison_chart(
        exec_ws,
        layout,
        f"{_LEFT_CHART_COL}{_ROW_CH_ISSUES}",
    )
    _add_doughnut_chart(
        exec_ws,
        title="Owner workload — unique URLs",
        header_row=owner_header,
        data_rows=layout.owner_rows,
        anchor=f"{_RIGHT_CHART_COL}{_ROW_CH_ISSUES}",
        colors=_OWNER_SLICE_COLORS,
        value_col=_value_col(),
    )

    _write_section_header(
        exec_ws,
        _ROW_SEC_ACTIONS,
        "Priority pages & content readiness",
    )
    _reserve_chart_band(exec_ws, _ROW_CH_ACTIONS, _CHART_BAND_ROWS)
    _add_priority_bar_chart(
        exec_ws,
        layout,
        f"{_LEFT_CHART_COL}{_ROW_CH_ACTIONS}",
    )
    _add_content_readiness_bar_chart(
        exec_ws,
        layout,
        f"{_RIGHT_CHART_COL}{_ROW_CH_ACTIONS}",
    )

    _write_section_header(
        exec_ws,
        _ROW_SEC_TOP_ISSUES,
        "Top issues to fix first (by affected URLs)",
    )
    _reserve_chart_band(exec_ws, _ROW_CH_TOP_ISSUES, _CHART_BAND_ROWS)
    _add_top_issues_chart(
        exec_ws,
        layout,
        f"{_LEFT_CHART_COL}{_ROW_CH_TOP_ISSUES}",
    )

    _write_source_data_hint(exec_ws)
    exec_ws.sheet_view.showGridLines = False


__all__ = [
    "CHART_LABEL_COL",
    "CHART_SOURCE_FIRST_ROW",
    "CHART_VALUE2_COL",
    "CHART_VALUE_COL",
    "ChartDataLayout",
    "populate_chart_data_sheet",
    "write_executive_dashboard",
]
