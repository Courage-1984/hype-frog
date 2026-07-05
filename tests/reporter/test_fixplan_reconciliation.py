"""FixPlan Affected Count must align with Summary issue URL counts."""

from __future__ import annotations

from collections import defaultdict

from hype_frog.core.models import ExtraRowPayload
from hype_frog.reporter.engine_rows import build_fixplan_rows
from hype_frog.reporter.summary_builder import build_summary_rows, safe_rule
from hype_frog.rules import get_summary_rules, score_url_health


def _fixplan_kwargs() -> dict[str, object]:
    return {
        "aeo_issue_names": set(),
        "root_cause_resolver": lambda _name: ("cause", "fix"),
        "default_effort_by_severity": {"Critical": "M", "Warning": "S"},
        "default_owner_by_severity": {"Critical": "Dev", "Warning": "Dev"},
    }


def test_404_matched_issues_uses_non_200_status_rule_name() -> None:
    rules = get_summary_rules()
    row: dict[str, object] = {
        "URL": "https://example.com/missing",
        "Extraction State": "partial",
        "Status Code": 404,
    }
    _score, badge, _icon, matched = score_url_health(row, rules)
    assert badge == "Critical"
    assert matched["Critical"] == ["Non-200 Status"]
    assert "HTTP 404 Not Found" not in matched["Critical"]


def test_fixplan_non_200_status_counts_404_urls() -> None:
    rules = get_summary_rules()
    extra_rows = [
        ExtraRowPayload.model_validate(
            {
                "URL": "https://example.com/missing",
                "Matched Issues": "Non-200 Status",
                "Status Code": 404,
            }
        )
    ]
    fixplan = build_fixplan_rows(rules, extra_rows, **_fixplan_kwargs())
    non200 = next(row for row in fixplan if row["Issue Type"] == "Non-200 Status")
    assert non200["Affected Count"] == 1


def test_fixplan_broken_internal_links_counts_source_urls() -> None:
    rules = get_summary_rules()
    extra_rows = [
        ExtraRowPayload.model_validate(
            {
                "URL": "https://example.com/a",
                "Extraction State": "partial",
                "Status Code": 200,
                "Matched Issues": "Broken Internal Links",
                "Broken Internal Links Count": 3,
            }
        ),
        ExtraRowPayload.model_validate(
            {
                "URL": "https://example.com/b",
                "Extraction State": "partial",
                "Status Code": 200,
                "Matched Issues": "Broken Internal Links",
                "Broken Internal Links Count": 2,
            }
        ),
    ]
    fixplan = build_fixplan_rows(rules, extra_rows, **_fixplan_kwargs())
    broken = next(row for row in fixplan if row["Issue Type"] == "Broken Internal Links")
    assert broken["Affected Count"] == 2
    assert broken["Affected Link Instances"] == 5


def test_fixplan_and_summary_counts_align_for_sample_rules() -> None:
    rules = get_summary_rules()
    extra_rows = [
        ExtraRowPayload.model_validate(
            {
                "URL": "https://example.com/a",
                "Extraction State": "partial",
                "Status Code": 200,
                "Title Missing": True,
                "Meta Description Missing": False,
                "Broken Internal Links Count": 2,
            }
        ),
        ExtraRowPayload.model_validate(
            {
                "URL": "https://example.com/b",
                "Extraction State": "partial",
                "Status Code": 200,
                "Title Missing": False,
                "Meta Description Missing": False,
                "Broken Internal Links Count": 1,
            }
        ),
    ]
    for row in extra_rows:
        _score, _badge, _icon, matched = score_url_health(row.values, rules)
        row.values["Matched Issues"] = " | ".join(
            matched["Critical"] + matched["Warning"] + matched["Observation"]
        )

    summary_rows = build_summary_rows(
        rules,
        extra_rows,
        defaultdict(lambda: defaultdict(int)),
        lambda value, default: default if value is None else float(value),
    )
    fixplan_rows = build_fixplan_rows(rules, extra_rows, **_fixplan_kwargs())
    summary_counts = {
        str(row["Issue"]): int(row["Affected URL Count"] or 0)
        for row in summary_rows
        if row.get("Section") == "Issue Counts" and row.get("Issue")
    }
    fixplan_counts = {
        str(row["Issue Type"]): int(row["Affected Count"] or 0) for row in fixplan_rows
    }
    for issue_name, summary_count in summary_counts.items():
        if issue_name in fixplan_counts:
            assert fixplan_counts[issue_name] == summary_count, issue_name

    missing_title_rule = next(r for r in rules if r.name == "Missing Title")
    assert safe_rule(missing_title_rule.fn, extra_rows[0].values) is True


def test_fixplan_and_summary_exclude_extraction_skipped_urls_from_content_rules() -> None:
    """Regression (M2): a URL where extraction was skipped (Title=None only because
    the page was never parsed, not because a real title is genuinely missing)
    must not inflate url-scope, content-derived rule counts like Missing Title."""
    rules = get_summary_rules()
    extra_rows = [
        ExtraRowPayload.model_validate(
            {
                "URL": "https://example.com/real-missing-title",
                "Extraction State": "partial",
                "Status Code": 200,
                "Title Missing": True,
            }
        ),
        ExtraRowPayload.model_validate(
            {
                "URL": "https://example.com/skipped",
                "Extraction State": "skipped",
                "Status Code": 200,
                "Title Missing": True,
            }
        ),
    ]
    summary_rows = build_summary_rows(
        rules,
        extra_rows,
        defaultdict(lambda: defaultdict(int)),
        lambda value, default: default if value is None else float(value),
    )
    fixplan_rows = build_fixplan_rows(rules, extra_rows, **_fixplan_kwargs())
    missing_title_summary = next(
        row
        for row in summary_rows
        if row.get("Section") == "Issue Counts" and row.get("Issue") == "Missing Title"
    )
    missing_title_fixplan = next(
        row for row in fixplan_rows if row["Issue Type"] == "Missing Title"
    )
    # Only the genuinely-extracted URL counts — the skipped one is excluded.
    assert missing_title_summary["Affected URL Count"] == 1
    assert missing_title_fixplan["Affected Count"] == 1
