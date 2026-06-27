"""Test HTML report data collection from mock crawl data."""
import pytest
from hype_frog.reporter.html_report_data import build_report_context


def _mock_main_rows(n: int = 10) -> list[dict]:
    rows = []
    for i in range(n):
        rows.append({
            "URL": f"https://example.com/page-{i}",
            "Status Code": 200 if i < 8 else 404,
            "SEO Health Score": 10 + i * 5,
            "Severity Badge": "Critical" if i < 3 else "Warning" if i < 6 else "Observation",
            "Mobile PSI Score": 40 + i * 3,
            "Desktop PSI Score": 50 + i * 3,
            "GSC Clicks": i * 2 if i < 5 else None,
            "GSC Impressions": i * 20 if i < 5 else None,
            "GSC Avg Position": 5.0 + i if i < 5 else None,
            "GSC Coverage Note": "Matched" if i < 5 else None,
        })
    return rows


def _mock_extra_rows(n: int = 10) -> list[dict]:
    rows = []
    for i in range(n):
        rows.append({
            "URL": f"https://example.com/page-{i}",
            "Status Code": 200 if i < 8 else 404,
            "AEO Readiness Score": 20 + i * 5,
            "SEO Health Score": 10 + i * 5,
            "Severity Badge": "Critical" if i < 3 else "Warning" if i < 6 else "Observation",
            "H1 Count": 1 if i < 7 else 0,
            "Meta Description Missing": i >= 8,
            "Paragraphs 40-60 Words Count": 1 if i < 3 else 0,
            "Schema Types Count": 1 if i < 2 else 0,
            "Image Alt Coverage (%)": 80 + i if i < 5 else 20,
            "Question Heading Count": 2 if i < 4 else 0,
        })
    return rows


def _mock_fixplan_rows() -> list[dict]:
    return [
        {
            "Issue Type": "Broken Links",
            "Severity": "Critical",
            "Owner": "Dev",
            "Est. Hours": 10,
            "Aging/Priority": "Immediate (Current Sprint)",
            "Affected Count": 5,
        },
        {
            "Issue Type": "Missing Meta",
            "Severity": "Warning",
            "Owner": "Copy Writer",
            "Est. Hours": 4,
            "Aging/Priority": "Next Sprint",
            "Affected Count": 8,
        },
        {
            "Issue Type": "Low Alt Coverage",
            "Severity": "Warning",
            "Owner": "Copy Writer",
            "Est. Hours": 8,
            "Aging/Priority": "Backlog",
            "Affected Count": 3,
        },
    ]


def _mock_summary_rows() -> list[dict]:
    return [
        {"Section": "Issues", "Issue": "Broken Links", "Severity": "Critical", "Affected URL Count": 5},
        {"Section": "Issues", "Issue": "Missing Meta", "Severity": "Warning", "Affected URL Count": 8},
    ]


def test_build_report_context_basic():
    ctx = build_report_context(
        main_rows=_mock_main_rows(),
        extra_rows=_mock_extra_rows(),
        fixplan_rows=_mock_fixplan_rows(),
        priority_rows=_mock_main_rows(),
        summary_rows=_mock_summary_rows(),
        run_timestamp="2026-06-27 01:33:36",
    )
    assert ctx.domain == "example.com"
    assert ctx.total_urls == 10
    assert ctx.seo_health_mean > 0
    assert ctx.critical_url_count == 3
    assert ctx.warning_url_count == 3
    assert ctx.observation_url_count == 4
    assert ctx.status_200_count == 8
    assert ctx.status_4xx_count == 2
    assert len(ctx.sprint_plan) == 3
    assert ctx.total_fix_hours == 22.0
    assert ctx.gsc_available is True
    assert ctx.gsc_clicks_total > 0
    assert len(ctx.content_readiness) == 6
    assert ctx.executive_narrative != ""


def test_build_report_context_no_gsc():
    rows = _mock_main_rows()
    for r in rows:
        r["GSC Clicks"] = None
        r["GSC Impressions"] = None
        r["GSC Avg Position"] = None
        r["GSC Coverage Note"] = None
    ctx = build_report_context(
        main_rows=rows,
        extra_rows=_mock_extra_rows(),
        fixplan_rows=[],
        priority_rows=[],
        summary_rows=[],
        run_timestamp="2026-06-27 01:33:36",
    )
    assert ctx.gsc_available is False
    assert ctx.gsc_clicks_total == 0
    assert ctx.sprint_plan == []
    assert ctx.total_fix_hours == 0.0


def test_narrative_content():
    ctx = build_report_context(
        main_rows=_mock_main_rows(),
        extra_rows=_mock_extra_rows(),
        fixplan_rows=_mock_fixplan_rows(),
        priority_rows=[],
        summary_rows=_mock_summary_rows(),
        run_timestamp="2026-06-27 01:33:36",
    )
    assert "example.com" in ctx.executive_narrative
    assert "10 URLs" in ctx.executive_narrative


def test_sprint_plan_ordering():
    ctx = build_report_context(
        main_rows=[],
        extra_rows=[],
        fixplan_rows=_mock_fixplan_rows(),
        priority_rows=[],
        summary_rows=[],
    )
    sprint_labels = [sp["sprint"] for sp in ctx.sprint_plan]
    assert sprint_labels == [
        "Immediate (Current Sprint)",
        "Next Sprint",
        "Backlog",
    ]


def test_quick_wins_projection():
    quick_win_rows = [
        {"Issue": "Missing Meta Description", "Effort (hrs)": 4.0, "Owner": "Copy Writer"},
        {"Issue": "No ETag Header", "Effort (hrs)": 4.0, "Owner": "Dev"},
        {"Issue": "", "Effort (hrs)": 1.0, "Owner": "Dev"},  # blank name skipped
    ]
    ctx = build_report_context(
        main_rows=_mock_main_rows(),
        extra_rows=_mock_extra_rows(),
        fixplan_rows=_mock_fixplan_rows(),
        priority_rows=[],
        summary_rows=_mock_summary_rows(),
        quick_win_rows=quick_win_rows,
        run_timestamp="2026-06-27 01:33:36",
    )
    assert len(ctx.quick_wins) == 2
    assert ctx.quick_wins[0] == {
        "name": "Missing Meta Description",
        "effort_hours": 4.0,
        "owner": "Copy Writer",
    }


def test_content_readiness_correct_fields():
    extra = _mock_extra_rows()
    ctx = build_report_context(
        main_rows=_mock_main_rows(),
        extra_rows=extra,
        fixplan_rows=[],
        priority_rows=[],
        summary_rows=[],
    )
    factors = [item["factor"] for item in ctx.content_readiness]
    assert "Good H1 Tag" in factors
    assert "Meta Description Present" in factors
    assert "Answer Paragraphs (40–60 word)" in factors
    assert "Schema Markup" in factors
    # All items have status set
    for item in ctx.content_readiness:
        assert item["status"] in ("good", "warning", "critical")
