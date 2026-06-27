"""Delta and ResolvedIssues baseline messaging on first-run exports."""

from __future__ import annotations

import pandas as pd

from hype_frog.orchestration.export_registry import (
    BASELINE_DELTA_NOTE,
    build_delta_and_trend_rows,
)


def test_baseline_report_shows_first_run_note() -> None:
    delta_rows, resolved_df = build_delta_and_trend_rows(
        issue_inventory_df=pd.DataFrame(
            {"Stable Issue ID": ["https://example.com/::missing-title"]}
        ),
        typed_extra_rows=[],
        summary_rules=[],
        prev_issue_ids=set(),
        prev_fixed_issue_ids=set(),
        prev_counts={},
        previous_issue_inventory_df=pd.DataFrame(),
        baseline_report=True,
    )
    status_rows = [
        row for row in delta_rows if row.get("Issue") == "Report Status"
    ]
    assert status_rows
    assert status_rows[0].get("Current Value") == BASELINE_DELTA_NOTE
    baseline_count_rows = [
        row
        for row in delta_rows
        if row.get("Issue") == "Current Issues (baseline inventory)"
    ]
    assert baseline_count_rows
    assert baseline_count_rows[0].get("Current Value") == 1
    assert resolved_df.iloc[0]["Issue"] == BASELINE_DELTA_NOTE


def test_compare_run_keeps_resolved_placeholder_when_none_fixed() -> None:
    delta_rows, resolved_df = build_delta_and_trend_rows(
        issue_inventory_df=pd.DataFrame({"Stable Issue ID": ["a::issue"]}),
        typed_extra_rows=[],
        summary_rules=[],
        prev_issue_ids={"a::issue"},
        prev_fixed_issue_ids=set(),
        prev_counts={},
        previous_issue_inventory_df=pd.DataFrame(
            {"Stable Issue ID": ["a::issue"], "Issue": ["Example"], "URL": ["https://a"]}
        ),
        baseline_report=False,
    )
    assert any(row.get("Issue") == "Resolved Issues" for row in delta_rows if row.get("Section") == "Summary")
    assert "No resolved issues identified" in str(resolved_df.iloc[0]["Issue"])
