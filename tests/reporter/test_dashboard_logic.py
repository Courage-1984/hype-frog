"""Typed dashboard metric aggregation."""

from __future__ import annotations

import pytest

from hype_frog.core.models import ExtraRowPayload, MainRowPayload, SummaryMetricsPayload
from hype_frog.reporter.dashboard_logic import (
    FixPlanRowPayload,
    compute_dashboard_metrics,
)


def _extra(**values: object) -> ExtraRowPayload:
    payload = ExtraRowPayload.model_validate({})
    payload.values.update(values)
    return payload


def _main(**values: object) -> MainRowPayload:
    payload = MainRowPayload.model_validate({})
    payload.values.update(values)
    return payload


def _summary() -> SummaryMetricsPayload:
    return SummaryMetricsPayload(
        urls_crawled=3,
        seo_pass_rate_pct=0.0,
        health_score_pct=0.0,
        critical_url_count=0,
        warning_url_count=0,
        projected_health_score_pct=0.0,
        projected_pass_rate_pct=0.0,
    )


def _result():
    technical_extra = [
        _extra(
            **{
                "Status Code": 200,
                "Severity Badge": "critical",
                "Schema Types Count": 2,
                "Broken Internal Links Count": 1,
                "TTFB (ms)": 100,
                "Critical Issues Count": 1,
                "Warning Issues Count": 0,
            }
        ),
        _extra(
            **{
                "Status Code": 301,
                "Severity Badge": "warning",
                "Schema Types Count": 0,
                "Broken Internal Links Count": 0,
                "TTFB (ms)": 200,
                "Critical Issues Count": 0,
                "Warning Issues Count": 2,
            }
        ),
        _extra(
            **{
                "Status Code": 404,
                "Severity Badge": "",
                "Schema Types Count": 1,
                "Broken Internal Links Count": 0,
                "TTFB (ms)": 300,
                "Critical Issues Count": 0,
                "Warning Issues Count": 0,
            }
        ),
    ]
    technical_main = [
        _main(**{"SEO Health Score": 80.0}),
        _main(**{"SEO Health Score": 60.0}),
        _main(**{"SEO Health Score": 40.0}),
    ]
    fixplan = [
        FixPlanRowPayload.model_validate(
            {
                "Issue Type": "Broken Links",
                "Affected Count": 5,
                "Severity": "Critical",
                "Owner": "Bob",
            }
        )
    ]
    aeo = [_extra(**{"AEO Readiness Score": 50.0}), _extra(**{"AEO Readiness Score": 70.0})]
    return compute_dashboard_metrics(
        summary_metrics=_summary(),
        technical_main_rows=technical_main,
        technical_extra_rows=technical_extra,
        fixplan_rows=fixplan,
        aeo_rows=aeo,
    )


def test_status_buckets_and_counts() -> None:
    result = _result()
    assert result.status_buckets["200 OK"] == 1
    assert result.status_buckets["3xx Redirects"] == 1
    assert result.status_buckets["4xx Errors"] == 1
    assert result.success_count == 1
    assert result.error_count == 1
    assert result.crawl_denominator == 3


def test_severity_schema_and_link_aggregates() -> None:
    result = _result()
    assert result.critical_urls == 1
    assert result.warning_urls == 1
    assert result.schema_urls == 2
    assert result.broken_link_instances_total == 1


def test_pass_and_average_metrics() -> None:
    result = _result()
    assert result.pass_urls == 1  # only the row with zero critical/warning issues
    assert result.pass_rate_pct == pytest.approx(33.33, abs=0.01)
    assert result.avg_ttfb_ms == pytest.approx(200.0)
    assert result.avg_health_score == pytest.approx(60.0)
    assert result.overall_health == pytest.approx(60.0)


def test_fixplan_and_aeo_rollups() -> None:
    result = _result()
    assert result.top_issue_name == "Broken Links"
    assert result.top_issue_affected == 5
    assert result.severity_counts.get("Critical") == 1
    assert result.aeo_readiness == pytest.approx(60.0)
    assert "Bob" in result.owner_rollup
    assert result.owner_rollup["Bob"].critical == 1


def test_aeo_average_excludes_unmeasured_rows() -> None:
    aeo_rows = [
        _extra(**{"AEO Readiness Score": 50.0, "AEO Badge": "Needs Work"}),
        _extra(**{"AEO Readiness Score": 70.0, "AEO Badge": "Good"}),
        _extra(**{"AEO Readiness Score": 71.0, "AEO Badge": "Unmeasured"}),
    ]
    result = compute_dashboard_metrics(
        summary_metrics=_summary(),
        technical_main_rows=[],
        technical_extra_rows=[],
        fixplan_rows=[],
        aeo_rows=aeo_rows,
    )
    assert result.aeo_readiness == pytest.approx(60.0)
    assert result.aeo_unmeasured_count == 1


def test_traditional_score_blends_success_and_health() -> None:
    result = _result()
    # (success/denominator*100)*0.4 + avg_health*0.6 = 33.33*0.4 + 60*0.6
    assert result.traditional_score == pytest.approx(49.33, abs=0.05)
