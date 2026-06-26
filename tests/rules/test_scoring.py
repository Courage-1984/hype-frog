"""Regression: per-URL scores must align with Summary issue rules on the same row dict."""

from __future__ import annotations

from hype_frog.rules import get_summary_rules, score_url_health
from hype_frog.reporter.summary_builder import safe_rule


def test_score_url_health_scores_partial_extraction_like_summary_rules() -> None:
    """Accurate mode without a full render sets Extraction State to partial but still parses HTML."""
    rules = get_summary_rules()
    row: dict[str, object] = {
        "URL": "https://example.com/page",
        "Extraction State": "partial",
        "Extraction Source": "raw_http",
        "Status Code": 200,
        "Title Missing": True,
        "Meta Description Missing": True,
    }
    score, badge, _icon, matched = score_url_health(row, rules)
    assert badge != "Unmeasured"
    assert score is not None
    assert "Missing Title" in matched["Critical"]
    missing_title_rule = next(r for r in rules if r.name == "Missing Title")
    assert safe_rule(missing_title_rule.fn, row) is True


def test_score_url_health_skipped_stays_unmeasured() -> None:
    rules = get_summary_rules()
    row: dict[str, object] = {
        "URL": "https://example.com/gone",
        "Extraction State": "skipped",
        "Status Code": None,
    }
    score, badge, _icon, matched = score_url_health(row, rules)
    assert badge == "Unmeasured"
    assert score is None
    assert matched == {"Critical": [], "Warning": [], "Observation": []}
