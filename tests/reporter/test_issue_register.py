"""Issue Register history columns (C1 improvements)."""

from __future__ import annotations

from hype_frog.analysis.delta_engine import IssueRecord
from hype_frog.reporter.sheets.merged_builders import build_issue_register_rows


def test_build_issue_register_rows_tracks_days_open() -> None:
    rows = build_issue_register_rows(
        summary_rows=[],
        issue_inventory_rows=[
            {
                "URL": "https://example.com/a",
                "Issue": "Missing Meta Description",
                "Severity": "Warning",
                "Reference Tab": "Content",
                "Stable Issue ID": "issue-1",
                "Owner": "",
                "Sprint": "",
                "Status": "Open",
            }
        ],
        issue_records={
            "issue-1": IssueRecord(
                stable_issue_id="issue-1",
                url="https://example.com/a",
                issue="Missing Meta Description",
                severity="Warning",
                first_seen="2026-01-01 00:00:00",
                last_seen="2026-06-01 00:00:00",
            )
        },
        run_date="2026-06-27 00:00:00",
    )
    assert rows[0]["Date First Detected"] == "2026-01-01 00:00:00"
    assert rows[0]["Days Open"] == 177
    assert rows[0]["Assigned To"] == ""
    assert rows[0]["Client Notes"] == ""
