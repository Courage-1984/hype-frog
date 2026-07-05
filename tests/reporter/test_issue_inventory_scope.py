"""IssueInventory aggregate rows for site/server scoped rules."""

from __future__ import annotations

from hype_frog.core.models import ExtraRowPayload
from hype_frog.reporter.summary_builder import build_issue_inventory_rows
from hype_frog.rules import IssueRule, get_summary_rules


def test_issue_inventory_collapses_server_and_site_rules() -> None:
    rules = get_summary_rules()
    extra_rows = [
        ExtraRowPayload.model_validate(
            {
                "URL": "https://example.com/a",
                "Matched Issues": "No ETag Header | AI Crawlers Not Explicitly Allowed | Missing Title",
                "ETag": None,
                "AI Crawlers Allowed (GPTBot/ClaudeBot/PerplexityBot)": False,
                "Title Missing": True,
            }
        ),
        ExtraRowPayload.model_validate(
            {
                "URL": "https://example.com/b",
                "Matched Issues": "No ETag Header | AI Crawlers Not Explicitly Allowed",
                "ETag": None,
                "AI Crawlers Allowed (GPTBot/ClaudeBot/PerplexityBot)": False,
            }
        ),
    ]
    rows = build_issue_inventory_rows(rules, extra_rows)

    etag_rows = [r for r in rows if r.get("Issue") == "No ETag Header"]
    ai_rows = [r for r in rows if r.get("Issue") == "AI Crawlers Not Explicitly Allowed"]
    title_rows = [r for r in rows if r.get("Issue") == "Missing Title"]

    assert len(etag_rows) == 1
    assert etag_rows[0]["URL"] == "(server config)"
    assert etag_rows[0]["Affected URL Count"] == 2

    assert len(ai_rows) == 1
    assert ai_rows[0]["URL"] == "(site-wide)"
    assert ai_rows[0]["Affected URL Count"] == 2

    assert len(title_rows) == 1
    assert title_rows[0]["URL"] == "https://example.com/a"
    assert title_rows[0].get("Affected URL Count") is None


def test_issue_inventory_excludes_synthetic_unmeasured_placeholder() -> None:
    """Regression (L6): "Unmeasured" is a synthetic placeholder for
    skipped-extraction URLs (pipeline/assemble.py), not a real rule match —
    it must not appear as its own Issue Inventory row."""
    rules = get_summary_rules()
    extra_rows = [
        ExtraRowPayload.model_validate(
            {
                "URL": "https://example.com/skipped",
                "Matched Issues": "Unmeasured",
            }
        ),
        ExtraRowPayload.model_validate(
            {
                "URL": "https://example.com/measured",
                "Matched Issues": "Missing Title",
                "Title Missing": True,
            }
        ),
    ]
    rows = build_issue_inventory_rows(rules, extra_rows)
    assert not any(r.get("Issue") == "Unmeasured" for r in rows)
    assert any(r.get("Issue") == "Missing Title" for r in rows)


def test_issue_inventory_custom_scope_rule() -> None:
    rule = IssueRule(
        "Observation",
        "Synthetic Site Rule",
        lambda r: r.get("Param URL Flag") is True,
        scope="site",
    )
    extra_rows = [
        ExtraRowPayload.model_validate(
            {
                "URL": "https://example.com/1",
                "Matched Issues": "Synthetic Site Rule",
                "Param URL Flag": True,
            }
        ),
        ExtraRowPayload.model_validate(
            {
                "URL": "https://example.com/2",
                "Matched Issues": "Synthetic Site Rule",
                "Param URL Flag": True,
            }
        ),
    ]
    rows = build_issue_inventory_rows([rule], extra_rows)
    assert len(rows) == 1
    assert rows[0]["URL"] == "(site-wide)"
    assert rows[0]["Affected URL Count"] == 2
