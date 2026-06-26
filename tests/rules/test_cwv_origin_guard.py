"""CWV rules must not fire per-URL Critical when data is origin-level CrUX."""

from __future__ import annotations

from hype_frog.core.models import ExtraRowPayload
from hype_frog.reporter.summary_builder import build_issue_inventory_rows, safe_rule
from hype_frog.rules import get_summary_rules, score_url_health


def _rule(name: str):
    return next(r for r in get_summary_rules() if r.name == name)


def test_url_level_cwv_lcp_still_critical() -> None:
    row = {
        "URL": "https://example.com/page",
        "Extraction State": "partial",
        "Status Code": 200,
        "CWV LCP (s)": 5.0,
        "CWV Data Source": "PSI API (CrUX)",
    }
    rule = _rule("CWV LCP Above 4.0s")
    assert safe_rule(rule.fn, row) is True
    _score, badge, _icon, matched = score_url_health(row, get_summary_rules())
    assert badge == "Critical"
    assert "CWV LCP Above 4.0s" in matched["Critical"]


def test_origin_cwv_lcp_skips_url_critical_uses_site_rule() -> None:
    row = {
        "URL": "https://example.com/page",
        "Extraction State": "partial",
        "Status Code": 200,
        "CWV LCP (s)": 5.0,
        "CWV Data Source": "CrUX API (Origin-level)",
    }
    url_rule = _rule("CWV LCP Above 4.0s")
    site_rule = _rule("CWV LCP Above 4.0s (Origin CrUX — Run PSI Pass for Per-URL Data)")
    assert safe_rule(url_rule.fn, row) is False
    assert safe_rule(site_rule.fn, row) is True

    _score, badge, _icon, matched = score_url_health(row, get_summary_rules())
    assert "CWV LCP Above 4.0s" not in matched["Critical"]
    assert site_rule.name in matched["Observation"]


def test_origin_cwv_rules_collapse_in_issue_inventory() -> None:
    rules = get_summary_rules()
    site_rule = _rule("CWV LCP Above 4.0s (Origin CrUX — Run PSI Pass for Per-URL Data)")
    extra_rows = [
        ExtraRowPayload.model_validate(
            {
                "URL": "https://example.com/1",
                "Matched Issues": site_rule.name,
                "CWV LCP (s)": 5.0,
                "CWV Data Source": "CrUX API (Origin-level)",
            }
        ),
        ExtraRowPayload.model_validate(
            {
                "URL": "https://example.com/2",
                "Matched Issues": site_rule.name,
                "CWV LCP (s)": 5.0,
                "CWV Data Source": "CrUX API (Origin-level)",
            }
        ),
    ]
    rows = build_issue_inventory_rows(rules, extra_rows)
    lcp_rows = [
        r
        for r in rows
        if r.get("Issue") == site_rule.name
    ]
    assert len(lcp_rows) == 1
    assert lcp_rows[0]["URL"] == "(site-wide)"
    assert lcp_rows[0]["Affected URL Count"] == 2
