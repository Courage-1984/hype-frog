"""Playbook enrichment rows (C6)."""

from __future__ import annotations

from hype_frog.rules.playbook_entries import build_issue_playbook_rows
from hype_frog.rules.registry import IssueRule


def test_build_issue_playbook_rows_includes_fix_steps() -> None:
    rules = [
        IssueRule("Warning", "Missing Title", lambda r: True),
    ]
    rows = build_issue_playbook_rows(rules)
    assert rows[0]["Issue"] == "Missing Title"
    assert "title" in rows[0]["How To Fix"].lower()
    assert rows[0]["How To Verify"]
