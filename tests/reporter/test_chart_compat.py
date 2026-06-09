"""Tests for openpyxl chart compatibility helpers."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd

from hype_frog.core.models import ExtraRowPayload, MainRowPayload, SummaryMetricsPayload
from hype_frog.reporter.chart_compat import patch_xlsx_app_xml_for_excel_compatibility
from hype_frog.reporter.sheets.executive_dashboard import write_executive_dashboard


def test_patch_xlsx_app_xml_strips_openpyxl_compatible_stamp(tmp_path: Path) -> None:
    out = tmp_path / "patch_test.xlsx"
    url = "https://example.com/"
    extra = {
        "URL": url,
        "Status Code": 200,
        "Severity Badge": "Warning",
        "SEO Health Score": 62,
        "Critical Issues Count": 0,
        "Warning Issues Count": 1,
        "Observation Issues Count": 0,
        "Mobile PSI Score": 78,
        "Desktop PSI Score": 82,
        "AEO Readiness Score": 55,
        "Missing H1 Flag": False,
        "H1 Count": 1,
        "Meta Description Missing": False,
        "Paragraphs 40-60 Words Count": 1,
        "Schema Types Count": 1,
        "Image Alt Coverage (%)": 85,
    }
    writer = pd.ExcelWriter(out, engine="openpyxl")
    write_executive_dashboard(
        writer,
        summary_metrics=SummaryMetricsPayload(
            urls_crawled=1,
            seo_pass_rate_pct=0.0,
            health_score_pct=62.0,
            critical_url_count=0,
            warning_url_count=1,
            projected_health_score_pct=78.0,
            projected_pass_rate_pct=40.0,
        ),
        typed_main_rows=[MainRowPayload.model_validate({"URL": url, "SEO Health Score": 62.0})],
        typed_extra_rows=[ExtraRowPayload.model_validate(extra)],
        priority_rows=[{"URL": url, "Business Risk Score": 42}],
        fixplan_rows=[
            {
                "Issue Type": "Missing Meta",
                "Severity": "Warning",
                "Affected Count": 1,
                "Owner": "Copy Writer",
            }
        ],
        hub_metrics_rows=[{"URL": url, "Potential Traffic Lift": 10}],
    )
    writer.close()

    with zipfile.ZipFile(out) as zf:
        assert "Compatible / Openpyxl" in zf.read("docProps/app.xml").decode()

    patch_xlsx_app_xml_for_excel_compatibility(out)

    with zipfile.ZipFile(out) as zf:
        app_xml = zf.read("docProps/app.xml").decode()
        assert "Compatible / Openpyxl" not in app_xml
        assert "<Application>Microsoft Excel</Application>" in app_xml
        chart_xml = zf.read("xl/charts/chart1.xml").decode()
        assert 'plotVisOnly val="0"' in chart_xml
