"""Executive Dashboard charts and visible source rows."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pytest
from openpyxl import load_workbook

from hype_frog.core.models import ExtraRowPayload, MainRowPayload, SummaryMetricsPayload
from hype_frog.reporter.chart_compat import patch_xlsx_app_xml_for_excel_compatibility
from hype_frog.reporter.sheets.config import EXECUTIVE_DASHBOARD_SHEET
from hype_frog.reporter.excel_engine import (
    adjust_sheet_format,
    apply_tab_hyperlinks,
    apply_workbook_export_guardrails,
)
from hype_frog.reporter.sheets.executive_dashboard import (
    CHART_SOURCE_FIRST_ROW,
    _is_low_value_priority_url,
    _meaningful_priority_rows,
    _owner_metrics,
    _project_component_score,
    _severity_metrics,
    write_executive_dashboard,
)


def _chart_title_text(chart: object) -> str:
    title = getattr(chart, "title", None)
    tx = getattr(title, "tx", None)
    rich = getattr(tx, "rich", None)
    if rich is None:
        return ""
    parts: list[str] = []
    for paragraph in rich.p:
        for run in paragraph.r:
            text = getattr(run, "t", None)
            if text:
                parts.append(str(text))
    return "".join(parts)


@pytest.fixture
def sample_export_context() -> dict[str, object]:
    url = "https://example.com/pricing"
    extra = {
        "URL": url,
        "Status Code": 200,
        "Severity Badge": "Warning",
        "SEO Health Score": 62.0,
        "Critical Issues Count": 0,
        "Warning Issues Count": 2,
        "Observation Issues Count": 1,
        "Mobile PSI Score": 78,
        "Desktop PSI Score": 82,
        "AEO Readiness Score": 55,
        "Missing H1 Flag": False,
        "H1 Count": 1,
        "Meta Description Missing": False,
        "Paragraphs 40-60 Words Count": 2,
        "Schema Types Count": 1,
        "Image Alt Coverage (%)": 85,
    }
    return {
        "summary_metrics": SummaryMetricsPayload(
            urls_crawled=1,
            seo_pass_rate_pct=0.0,
            health_score_pct=62.0,
            critical_url_count=0,
            warning_url_count=1,
            projected_health_score_pct=78.0,
            projected_pass_rate_pct=40.0,
        ),
        "typed_main_rows": [MainRowPayload.model_validate({"URL": url, "SEO Health Score": 62.0})],
        "typed_extra_rows": [ExtraRowPayload.model_validate(extra)],
        "priority_rows": [
            {
                "URL": url,
                "Business Risk Score": 42,
                "Severity Badge": "Warning",
            }
        ],
        "fixplan_rows": [
            {
                "Issue Type": "Missing Meta Description",
                "Severity": "Warning",
                "Affected Count": 1,
                "Owner": "Copy Writer",
            }
        ],
        "hub_metrics_rows": [{"URL": url, "Potential Traffic Lift": 120}],
    }


def test_severity_metrics_separates_unique_urls_from_issue_instances() -> None:
    extra_rows = [
        {
            "URL": "https://example.com/a",
            "Severity Badge": "Critical",
            "Owner": "Dev",
        },
        {
            "URL": "https://example.com/b",
            "Severity Badge": "Warning",
            "Owner": "Copy Writer",
        },
    ]
    fixplan_rows = [
        {"Severity": "Critical", "Affected Count": 3, "Owner": "Dev"},
        {"Severity": "Warning", "Affected Count": 2, "Owner": "Copy Writer"},
        {"Severity": "Warning", "Affected Count": 1, "Owner": "Copy Writer"},
    ]
    severity = _severity_metrics(extra_rows, fixplan_rows)
    by_label = {label: (urls, instances) for label, urls, instances in severity}
    assert by_label["Critical"] == (1, 3)
    assert by_label["Warning"] == (1, 3)

    owners = _owner_metrics(extra_rows, fixplan_rows)
    owner_map = {name: (urls, instances) for name, urls, instances in owners}
    assert owner_map["Dev"] == (1, 3)
    assert owner_map["Copy Writer"] == (1, 3)


def test_meaningful_priority_rows_skip_low_value_paths() -> None:
    rows = [
        {"URL": "https://example.com/cart", "Business Risk Score": 99},
        {"URL": "https://example.com/pricing", "Business Risk Score": 42},
        {"URL": "https://example.com/thank-you", "Business Risk Score": 80},
    ]
    assert _is_low_value_priority_url("https://example.com/checkout")
    filtered = _meaningful_priority_rows(rows, limit=2)
    assert [row["URL"] for row in filtered] == ["https://example.com/pricing"]


def test_project_component_score_matches_export_flow_uplift() -> None:
    summary = SummaryMetricsPayload(
        urls_crawled=10,
        seo_pass_rate_pct=40.0,
        health_score_pct=50.0,
        critical_url_count=2,
        warning_url_count=3,
        projected_health_score_pct=72.5,
        projected_pass_rate_pct=60.0,
    )
    projected = _project_component_score(50.0, summary)
    assert projected == 72.5


def test_executive_dashboard_writes_charts_with_visible_source_rows(
    tmp_path: Path,
    sample_export_context: dict[str, object],
) -> None:
    out = tmp_path / "exec_dash.xlsx"
    writer = __import__("pandas").ExcelWriter(out, engine="openpyxl")
    write_executive_dashboard(
        writer,
        summary_metrics=sample_export_context["summary_metrics"],  # type: ignore[arg-type]
        typed_main_rows=sample_export_context["typed_main_rows"],  # type: ignore[arg-type]
        typed_extra_rows=sample_export_context["typed_extra_rows"],  # type: ignore[arg-type]
        priority_rows=sample_export_context["priority_rows"],  # type: ignore[arg-type]
        fixplan_rows=sample_export_context["fixplan_rows"],  # type: ignore[arg-type]
        hub_metrics_rows=sample_export_context["hub_metrics_rows"],  # type: ignore[arg-type]
    )
    writer.close()
    patch_xlsx_app_xml_for_excel_compatibility(out)

    wb = load_workbook(out)
    exec_ws = wb[EXECUTIVE_DASHBOARD_SHEET]
    assert len(exec_ws._charts) >= 4
    titles = {_chart_title_text(chart) for chart in exec_ws._charts}
    assert "Health components — current vs illustrative projected" in titles
    assert any("Issue severity" in title for title in titles)
    assert any("Content & AEO readiness" in title for title in titles)
    assert any("Top issues by URL impact" in title for title in titles)
    assert "High-intent pages by business risk" in titles
    assert "Key insights:" in str(exec_ws.cell(row=5, column=1).value or "")
    assert exec_ws.cell(row=CHART_SOURCE_FIRST_ROW + 2, column=2).value is not None
    wb.close()


def test_executive_dashboard_chart_xml_uses_valid_rgb_and_visible_data(
    tmp_path: Path,
    sample_export_context: dict[str, object],
) -> None:
    out = tmp_path / "exec_dash_rgb.xlsx"
    writer = __import__("pandas").ExcelWriter(out, engine="openpyxl")
    write_executive_dashboard(
        writer,
        summary_metrics=sample_export_context["summary_metrics"],  # type: ignore[arg-type]
        typed_main_rows=sample_export_context["typed_main_rows"],  # type: ignore[arg-type]
        typed_extra_rows=sample_export_context["typed_extra_rows"],  # type: ignore[arg-type]
        priority_rows=sample_export_context["priority_rows"],  # type: ignore[arg-type]
        fixplan_rows=sample_export_context["fixplan_rows"],  # type: ignore[arg-type]
        hub_metrics_rows=sample_export_context["hub_metrics_rows"],  # type: ignore[arg-type]
    )
    writer.close()
    patch_xlsx_app_xml_for_excel_compatibility(out)

    with zipfile.ZipFile(out) as zf:
        app_xml = zf.read("docProps/app.xml").decode()
        assert "Compatible / Openpyxl" not in app_xml
        for name in zf.namelist():
            if not name.startswith("xl/charts/chart"):
                continue
            xml = zf.read(name).decode()
            for rgb in re.findall(r'srgbClr val="([^"]+)"', xml):
                assert len(rgb) == 6, f"invalid srgbClr {rgb!r} in {name}"
            assert 'plotVisOnly val="0"' in xml or "plotVisOnly" not in xml


def test_adjust_sheet_format_tolerates_executive_dashboard_merges(
    tmp_path: Path,
    sample_export_context: dict[str, object],
) -> None:
    out = tmp_path / "exec_dash_format.xlsx"
    writer = __import__("pandas").ExcelWriter(out, engine="openpyxl")
    write_executive_dashboard(
        writer,
        summary_metrics=sample_export_context["summary_metrics"],  # type: ignore[arg-type]
        typed_main_rows=sample_export_context["typed_main_rows"],  # type: ignore[arg-type]
        typed_extra_rows=sample_export_context["typed_extra_rows"],  # type: ignore[arg-type]
        priority_rows=sample_export_context["priority_rows"],  # type: ignore[arg-type]
        fixplan_rows=sample_export_context["fixplan_rows"],  # type: ignore[arg-type]
        hub_metrics_rows=sample_export_context["hub_metrics_rows"],  # type: ignore[arg-type]
    )
    adjust_sheet_format(writer, EXECUTIVE_DASHBOARD_SHEET)
    writer.close()
    wb = load_workbook(out)
    assert wb[EXECUTIVE_DASHBOARD_SHEET].freeze_panes == "A8"
    wb.close()


def test_executive_dashboard_survives_export_finalization(
    tmp_path: Path,
    sample_export_context: dict[str, object],
) -> None:
    out = tmp_path / "exec_dash_finalize.xlsx"
    writer = __import__("pandas").ExcelWriter(out, engine="openpyxl")
    write_executive_dashboard(
        writer,
        summary_metrics=sample_export_context["summary_metrics"],  # type: ignore[arg-type]
        typed_main_rows=sample_export_context["typed_main_rows"],  # type: ignore[arg-type]
        typed_extra_rows=sample_export_context["typed_extra_rows"],  # type: ignore[arg-type]
        priority_rows=sample_export_context["priority_rows"],  # type: ignore[arg-type]
        fixplan_rows=sample_export_context["fixplan_rows"],  # type: ignore[arg-type]
        hub_metrics_rows=sample_export_context["hub_metrics_rows"],  # type: ignore[arg-type]
    )
    apply_tab_hyperlinks(writer)
    adjust_sheet_format(writer, EXECUTIVE_DASHBOARD_SHEET)
    apply_workbook_export_guardrails(writer.book)
    writer.close()
    patch_xlsx_app_xml_for_excel_compatibility(out)
    wb = load_workbook(out)
    assert wb[EXECUTIVE_DASHBOARD_SHEET].freeze_panes == "A8"
    assert len(wb[EXECUTIVE_DASHBOARD_SHEET]._charts) >= 4
    wb.close()
