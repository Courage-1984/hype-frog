"""Tests for run-to-run delta engine (C1)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from hype_frog.analysis.delta_engine import (
    BASELINE_DELTA_NOTE,
    IssueRecord,
    RunSnapshot,
    TrendPoint,
    build_delta_sheet_rows,
    build_resolved_issues_dataframe,
    delta_summary_path_for_workbook,
    load_run_snapshot,
    save_run_snapshot_json,
    snapshot_from_current_run,
)


def test_delta_summary_path_for_workbook() -> None:
    assert delta_summary_path_for_workbook(
        "reports/latest/audit.xlsx"
    ).endswith("_delta_summary.json")


def test_snapshot_round_trip_json(tmp_path: Path) -> None:
    snapshot = RunSnapshot(
        run_date="2026-06-01 10:00:00",
        source_path="reports/audit.xlsx",
        issues={
            "https://example.com/::missing-title": IssueRecord(
                stable_issue_id="https://example.com/::missing-title",
                url="https://example.com/",
                issue="Missing Title",
                severity="Critical",
                first_seen="2026-06-01 10:00:00",
            )
        },
        metrics_by_url={
            "https://example.com/": {"SEO Health Score": 55.0},
        },
        health_trend={
            "https://example.com/": [
                TrendPoint(run_date="2026-06-01 10:00:00", score=55.0),
            ]
        },
        issue_counts_by_name={"Missing Title": 1},
    )
    path = tmp_path / "audit_delta_summary.json"
    save_run_snapshot_json(str(path), snapshot)
    loaded = load_run_snapshot(str(path))
    assert loaded is not None
    assert loaded.issue_ids == snapshot.issue_ids
    assert loaded.metrics_by_url["https://example.com/"]["SEO Health Score"] == 55.0


def test_build_delta_sheet_rows_compare_run() -> None:
    previous = RunSnapshot(
        run_date="2026-05-01 09:00:00",
        source_path="prev.xlsx",
        issues={
            "resolved::issue": IssueRecord(
                stable_issue_id="resolved::issue",
                url="https://example.com/old",
                issue="Missing Meta Description",
                severity="Warning",
                first_seen="2026-04-01 09:00:00",
            ),
            "unchanged::issue": IssueRecord(
                stable_issue_id="unchanged::issue",
                url="https://example.com/",
                issue="Missing Title",
                severity="Critical",
            ),
        },
        metrics_by_url={
            "https://example.com/": {
                "SEO Health Score": 60.0,
                "AEO Readiness Score": 70.0,
                "Mobile PSI Score": 40.0,
                "Technical Health": 55.0,
            }
        },
    )
    current = RunSnapshot(
        run_date="2026-06-01 10:00:00",
        source_path="current.xlsx",
        issues={
            "new::issue": IssueRecord(
                stable_issue_id="new::issue",
                url="https://example.com/new",
                issue="Missing H1",
                severity="Warning",
                first_seen="2026-06-01 10:00:00",
            ),
            "unchanged::issue": IssueRecord(
                stable_issue_id="unchanged::issue",
                url="https://example.com/",
                issue="Missing Title",
                severity="Critical",
            ),
        },
        metrics_by_url={
            "https://example.com/": {
                "SEO Health Score": 72.0,
                "AEO Readiness Score": 70.0,
                "Mobile PSI Score": 40.0,
                "Technical Health": 55.0,
            }
        },
        health_trend={
            "https://example.com/": [
                TrendPoint(run_date="2026-05-01 09:00:00", score=60.0),
                TrendPoint(run_date="2026-06-01 10:00:00", score=72.0),
            ]
        },
    )

    rows = build_delta_sheet_rows(
        current=current,
        previous=previous,
        baseline_report=False,
        typed_extra_rows=[],
        summary_rules=[],
    )
    summary_issues = [row.get("Issue") for row in rows if row.get("Section") == "Summary"]
    assert "New Issues" in summary_issues
    assert "Resolved Issues" in summary_issues
    new_rows = [row for row in rows if row.get("Section") == "New Issues" and row.get("URL")]
    assert any(row["Issue"] == "Missing H1" for row in new_rows)
    metric_rows = [
        row for row in rows if row.get("Section") == "Metric Changes" and row.get("Change")
    ]
    assert any(row["Issue"] == "SEO Health Score" and row["Change"] == 12.0 for row in metric_rows)


def test_snapshot_from_current_run_merges_health_trend() -> None:
    previous = RunSnapshot(
        run_date="2026-05-01 09:00:00",
        source_path="prev.xlsx",
        health_trend={
            "https://example.com/": [
                TrendPoint(run_date="2026-05-01 09:00:00", score=60.0),
            ]
        },
    )
    inventory = pd.DataFrame(
        {
            "Stable Issue ID": ["a::issue"],
            "URL": ["https://example.com/"],
            "Issue": ["Missing Title"],
            "Severity": ["Critical"],
            "Status": ["Open"],
        }
    )
    snapshot = snapshot_from_current_run(
        issue_inventory_df=inventory,
        main_rows=[{"URL": "https://example.com/", "SEO Health Score": 72.0}],
        extra_rows=[{"URL": "https://example.com/", "AEO Readiness Score": 80}],
        source_path="current.xlsx",
        run_date="2026-06-01 10:00:00",
        previous_snapshot=previous,
    )
    trend = snapshot.health_trend["https://example.com/"]
    assert len(trend) == 2
    assert trend[-1].score == 72.0


def test_baseline_resolved_placeholder() -> None:
    current = RunSnapshot(run_date="2026-06-01", source_path="current.xlsx")
    resolved = build_resolved_issues_dataframe(
        current=current,
        previous=None,
        baseline_report=True,
    )
    assert resolved.iloc[0]["Issue"] == BASELINE_DELTA_NOTE


def test_load_legacy_xlsx_snapshot_handles_nan_counts() -> None:
    path = Path("reports.old/SEO_AEO_Audit_africanmarketingconfederation.org_20260626_160647.xlsx")
    if not path.exists():
        pytest.skip("AMC reference workbook not available locally")
    snapshot = load_run_snapshot(str(path))
    assert snapshot is not None
    assert len(snapshot.issue_ids) > 0
    assert all(isinstance(v, int) for v in snapshot.issue_counts_by_name.values())


def test_safe_int_handles_pandas_nan_summary_counts() -> None:
    from hype_frog.analysis.delta_engine import _safe_int

    assert _safe_int(float("nan")) == 0
    assert _safe_int(pd.NA) == 0
