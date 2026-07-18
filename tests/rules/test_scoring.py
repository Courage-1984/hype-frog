"""Regression: per-URL scores must align with Summary issue rules on the same row dict."""

from __future__ import annotations

from hype_frog.rules import get_summary_rules, score_url_health
from hype_frog.rules.scoring import _severity_penalty, align_extraction_state_from_main
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


def test_severity_penalty_is_capped_and_diminishing() -> None:
    """First match carries most weight; extras add less; cap bounds the total."""
    assert _severity_penalty(0, first=20, step=10, cap=50) == 0
    assert _severity_penalty(1, first=20, step=10, cap=50) == 20
    assert _severity_penalty(2, first=20, step=10, cap=50) == 30
    assert _severity_penalty(4, first=20, step=10, cap=50) == 50
    assert _severity_penalty(10, first=20, step=10, cap=50) == 50
    assert _severity_penalty(3, first=8, step=5, cap=30) == 18
    assert _severity_penalty(10, first=8, step=5, cap=30) == 30
    assert _severity_penalty(2, first=3, step=3, cap=10) == 6


def test_score_url_health_discriminates_under_heavy_issue_load() -> None:
    """A page with many issues must score above 0 (0 is reserved for hard fails).

    Regression for the saturation bug where 3-4 Critical + 7-10 Warning matches
    floored every URL at 0 and erased all ranking signal.
    """
    rules = get_summary_rules()
    heavy_row: dict[str, object] = {
        "URL": "https://example.com/heavy",
        "Extraction State": "complete",
        "Status Code": 200,
        "Title Missing": True,
        "Broken Internal Links Count": 3,
        "Canonical Type": "cross-canonical",
        "Indexability Reason": "Noindex",
    }
    light_row: dict[str, object] = {
        "URL": "https://example.com/light",
        "Extraction State": "complete",
        "Status Code": 200,
        "Title Missing": True,
    }
    heavy_score, heavy_badge, _icon, heavy_matched = score_url_health(heavy_row, rules)
    light_score, _badge, _icon2, light_matched = score_url_health(light_row, rules)
    assert heavy_badge == "Critical"
    assert len(heavy_matched["Critical"]) > len(light_matched["Critical"])
    # Worst-case penalties are capped at 50 + 30 + 10 = 90, so a reachable,
    # scorable page can never floor at 0.
    assert heavy_score is not None and heavy_score >= 10
    assert light_score is not None and light_score > heavy_score


def test_score_url_health_keeps_zero_for_hard_fail_status() -> None:
    rules = get_summary_rules()
    row: dict[str, object] = {
        "URL": "https://example.com/missing",
        "Extraction State": "complete",
        "Status Code": 404,
    }
    score, badge, icon, matched = score_url_health(row, rules)
    assert score == 0
    assert badge == "Critical"
    assert icon == "FAIL 🔴"
    assert matched["Critical"] == ["Non-200 Status"]


def test_align_extraction_state_from_main_repairs_desync_before_scoring() -> None:
    rules = get_summary_rules()
    extra: dict[str, object] = {
        "URL": "https://example.com/page",
        "Extraction State": "skipped",
        "Status Code": 200,
        "Title Missing": True,
    }
    main: dict[str, object] = {
        "URL": "https://example.com/page",
        "Extraction State": "partial",
        "Extraction Source": "raw_http",
    }
    align_extraction_state_from_main(extra, main)
    assert extra["Extraction State"] == "partial"
    score, badge, _icon, matched = score_url_health(extra, rules)
    assert badge != "Unmeasured"
    assert score is not None
    assert "Missing Title" in matched["Critical"]
