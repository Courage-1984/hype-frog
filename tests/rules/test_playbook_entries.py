"""Playbook enrichment rows (C6)."""

from __future__ import annotations

from hype_frog.rules.playbook_entries import PLAYBOOK_COLUMNS, build_issue_playbook_rows
from hype_frog.rules.registry import IssueRule, get_summary_rules


def test_build_issue_playbook_rows_includes_fix_steps() -> None:
    rules = [
        IssueRule("Warning", "Missing Title", lambda r: True),
    ]
    rows = build_issue_playbook_rows(rules)
    assert rows[0]["Issue"] == "Missing Title"
    assert "title" in rows[0]["How To Fix"].lower()
    assert rows[0]["How To Verify"]


def test_all_summary_rules_generate_playbook_rows() -> None:
    rules = get_summary_rules()
    rows = build_issue_playbook_rows(rules)
    assert len(rows) == len(rules)
    rule_names = {rule.name for rule in rules}
    assert {row["Issue"] for row in rows} == rule_names
    for row in rows:
        for column in PLAYBOOK_COLUMNS:
            assert row[column]
            assert str(row[column]).strip()
