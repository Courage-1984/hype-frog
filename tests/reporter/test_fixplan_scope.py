"""FixPlan resolution type for site/server scoped rules."""

from __future__ import annotations

from hype_frog.core.models import ExtraRowPayload
from hype_frog.reporter.engine_rows import build_fixplan_rows
from hype_frog.rules import IssueRule, get_summary_rules


def test_fixplan_server_and_site_resolution_types() -> None:
    rules = get_summary_rules()
    extra_rows = [
        ExtraRowPayload.model_validate(
            {
                "URL": "https://example.com/",
                "Matched Issues": "No ETag Header | AI Crawlers Not Explicitly Allowed",
            }
        )
    ]
    rows = build_fixplan_rows(
        rules,
        extra_rows,
        aeo_issue_names=set(),
        root_cause_resolver=lambda _name: ("cause", "fix"),
        default_effort_by_severity={"Observation": "S"},
        default_owner_by_severity={"Observation": "Dev"},
    )
    by_issue = {row["Issue Type"]: row for row in rows}
    assert by_issue["No ETag Header"]["Resolution Type"] == "Server Config"
    assert by_issue["AI Crawlers Not Explicitly Allowed"]["Resolution Type"] == "Site Config"


def test_fixplan_explicit_scope_overrides_global_template_token() -> None:
    rule = IssueRule(
        "Observation",
        "No ETag Header",
        lambda r: True,
        scope="server",
    )
    rows = build_fixplan_rows(
        [rule],
        [ExtraRowPayload.model_validate({"URL": "https://example.com/", "Matched Issues": "No ETag Header"})],
        aeo_issue_names=set(),
        root_cause_resolver=lambda _name: ("cause", "fix"),
        default_effort_by_severity={"Observation": "S"},
        default_owner_by_severity={"Observation": "Dev"},
    )
    assert rows[0]["Resolution Type"] == "Server Config"
