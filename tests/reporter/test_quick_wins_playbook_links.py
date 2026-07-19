"""Quick Wins / FixPlan must carry linked descriptions and correct jump formulas."""

from __future__ import annotations

from hype_frog.config import DEFAULT_EFFORT_BY_SEVERITY, DEFAULT_OWNER_BY_SEVERITY
from hype_frog.core.models import ExtraRowPayload
from hype_frog.reporter.engine_rows import build_fixplan_rows
from hype_frog.reporter.sheets.merged_builders import (
    QUICK_WINS_COLUMNS,
    build_quick_wins_rows,
)
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
    assert row["Why It Matters"] == playbook_index["Non-200 Status"].why_it_matters
    assert row["How To Verify"] == playbook_index["Non-200 Status"].how_to_verify
    # Regression: this formula previously matched 'FixPlan'!B:B, which holds
    # Severity post-reorder, not Issue Type — every link silently fell through
    # to the IFERROR fallback instead of the correct row.
    assert "'FixPlan'!A:A" in row["Jump to FixPlan"]
    assert "'FixPlan'!B:B" not in row["Jump to FixPlan"]
    assert "'Playbook'!B:B" in row["Jump to Playbook"]
    assert list(row.keys()) == list(QUICK_WINS_COLUMNS)


def test_quick_wins_columns_follow_narrative_stage_order() -> None:
    """Regression: columns must read identity -> why-it's-a-quick-win -> owner
    (frozen pane boundary) -> what-to-do -> navigation, top to bottom. "Sprint"
    was removed entirely (it duplicated FixPlan's Aging/Priority bucket)."""
    assert QUICK_WINS_COLUMNS == (
        "URL",
        "Issue",
        "Severity",
        "Priority Score",
        "Effort (hrs)",
        "GSC Clicks (30d)",
        "Owner",
        "What It Is",
        "Why It Matters",
        "Recommended Fix",
        "How To Verify",
        "Business Risk Score",
        "Revenue Risk",
        "Jump to FixPlan",
        "Jump to Playbook",
    )
    assert "Sprint" not in QUICK_WINS_COLUMNS


def test_quick_wins_business_risk_score_comes_from_risk_score_by_url_map() -> None:
    """Regression (M1): "Business Risk Score" is never set on raw extra_rows dicts
    themselves — it's only ever computed separately for Priority URLs. A literal
    "Business Risk Score" key on the extra_rows dict (as some legacy/test data has)
    must NOT be used; only the risk_score_by_url lookup should populate the column,
    and it must also unlock the clicks==0-but-high-risk inclusion path."""
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
    # Zero clicks, no "Business Risk Score" key on the row itself — should be
    # excluded unless the risk_score_by_url map supplies a positive risk score.
    quick_wins_extra_rows = [
        {"URL": "https://example.com/missing", "Status Code": 404, "GSC Clicks": 0}
    ]

    excluded = build_quick_wins_rows(
        quick_wins_extra_rows, fixplan_rows, rules, playbook_index
    )
    assert excluded == []

    included = build_quick_wins_rows(
        quick_wins_extra_rows,
        fixplan_rows,
        rules,
        playbook_index,
        risk_score_by_url={"https://example.com/missing": 85},
    )
    assert included
    assert included[0]["Business Risk Score"] == 85.0
