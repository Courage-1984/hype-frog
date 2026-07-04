"""Quick Wins / FixPlan must carry linked descriptions and correct jump formulas."""

from __future__ import annotations

from hype_frog.config import DEFAULT_EFFORT_BY_SEVERITY, DEFAULT_OWNER_BY_SEVERITY
from hype_frog.core.models import ExtraRowPayload
from hype_frog.reporter.engine_rows import build_fixplan_rows
from hype_frog.reporter.sheets.merged_builders import build_quick_wins_rows
from hype_frog.rules import get_summary_rules, root_cause_and_fix
from hype_frog.rules.playbook_entries import build_playbook_entry_index


def _non_200_rule() -> list:
    rules = [rule for rule in get_summary_rules() if rule.name == "Non-200 Status"]
    assert rules, "Non-200 Status rule must exist in the registry"
    return rules


def test_fixplan_gets_what_it_is_and_playbook_link() -> None:
    rules = _non_200_rule()
    playbook_index = build_playbook_entry_index(rules)
    extra_rows = [
        ExtraRowPayload.model_validate(
            {"URL": "https://example.com/missing", "Status Code": 404}
        )
    ]
    fixplan_rows = build_fixplan_rows(
        rules,
        extra_rows,
        aeo_issue_names=set(),
        root_cause_resolver=root_cause_and_fix,
        default_effort_by_severity=DEFAULT_EFFORT_BY_SEVERITY,
        default_owner_by_severity=DEFAULT_OWNER_BY_SEVERITY,
        playbook_index=playbook_index,
    )
    row = next(r for r in fixplan_rows if r["Issue Type"] == "Non-200 Status")
    assert row["What It Is"] == playbook_index["Non-200 Status"].what_it_is
    assert "'Playbook'!B:B" in row["Jump to Playbook"]
    assert "#'Playbook'!A" in row["Jump to Playbook"]


def test_quick_wins_gets_what_it_is_and_both_jump_links_fixed() -> None:
    rules = _non_200_rule()
    playbook_index = build_playbook_entry_index(rules)
    fixplan_extra_rows = [
        ExtraRowPayload.model_validate(
            {"URL": "https://example.com/missing", "Status Code": 404}
        )
    ]
    fixplan_rows = build_fixplan_rows(
        rules,
        fixplan_extra_rows,
        aeo_issue_names=set(),
        root_cause_resolver=root_cause_and_fix,
        default_effort_by_severity=DEFAULT_EFFORT_BY_SEVERITY,
        default_owner_by_severity=DEFAULT_OWNER_BY_SEVERITY,
        playbook_index=playbook_index,
    )
    quick_wins_extra_rows = [
        {
            "URL": "https://example.com/missing",
            "Status Code": 404,
            "GSC Clicks": 5,
            "Business Risk Score": 10,
        }
    ]
    quick_wins_rows = build_quick_wins_rows(
        quick_wins_extra_rows, fixplan_rows, rules, playbook_index
    )
    assert quick_wins_rows
    row = quick_wins_rows[0]
    assert row["What It Is"] == playbook_index["Non-200 Status"].what_it_is
    # Regression: this formula previously matched 'FixPlan'!B:B, which holds
    # Severity post-reorder, not Issue Type — every link silently fell through
    # to the IFERROR fallback instead of the correct row.
    assert "'FixPlan'!A:A" in row["Jump to FixPlan"]
    assert "'FixPlan'!B:B" not in row["Jump to FixPlan"]
    assert "'Playbook'!B:B" in row["Jump to Playbook"]
