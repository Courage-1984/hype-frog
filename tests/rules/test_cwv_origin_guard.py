"""CWV and Lighthouse rules must respect CrUX Level and lab column semantics."""

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
        "CrUX Level": "URL",
        "CWV LCP (s)": 5.0,
    }
    rule = _rule("CWV LCP Above 4.0s (Field Data)")
    assert safe_rule(rule.fn, row) is True
    _score, badge, _icon, matched = score_url_health(row, get_summary_rules())
    assert badge == "Critical"
    assert "CWV LCP Above 4.0s (Field Data)" in matched["Critical"]


def test_origin_crux_skips_url_field_critical_uses_site_rule() -> None:
    row = {
        "URL": "https://example.com/page",
        "Extraction State": "partial",
        "Status Code": 200,
        "CrUX Level": "Origin",
        "CWV LCP (s)": None,
        "Origin CrUX LCP (s)": 11.852,
    }
    url_rule = _rule("CWV LCP Above 4.0s (Field Data)")
    site_rule = _rule(
        "Origin CrUX LCP Above 4.0s (per-URL data unavailable — re-run with PSI key for URL-level data)"
    )
    assert safe_rule(url_rule.fn, row) is False
    assert safe_rule(site_rule.fn, row) is True

    _score, badge, _icon, matched = score_url_health(row, get_summary_rules())
    assert "CWV LCP Above 4.0s (Field Data)" not in matched["Critical"]
    assert site_rule.name in matched["Observation"]


def test_origin_crux_rules_collapse_in_issue_inventory() -> None:
    rules = get_summary_rules()
    site_rule = _rule(
        "Origin CrUX LCP Above 4.0s (per-URL data unavailable — re-run with PSI key for URL-level data)"
    )
    extra_rows = [
        ExtraRowPayload.model_validate(
            {
                "URL": "https://example.com/1",
                "Matched Issues": site_rule.name,
                "CrUX Level": "Origin",
                "Origin CrUX LCP (s)": 11.852,
            }
        ),
        ExtraRowPayload.model_validate(
            {
                "URL": "https://example.com/2",
                "Matched Issues": site_rule.name,
                "CrUX Level": "Origin",
                "Origin CrUX LCP (s)": 11.852,
            }
        ),
    ]
    rows = build_issue_inventory_rows(rules, extra_rows)
    lcp_rows = [r for r in rows if r.get("Issue") == site_rule.name]
    assert len(lcp_rows) == 1
    assert lcp_rows[0]["URL"] == "(site-wide)"
    assert lcp_rows[0]["Affected URL Count"] == 2


def test_lab_lcp_above_4s_fires_on_mobile_lab_column() -> None:
    row = {
        "URL": "https://example.com/slow",
        "Extraction State": "partial",
        "Status Code": 200,
        "CrUX Level": "Origin",
        "Lab LCP (Mobile) (s)": 28.201,
    }
    rule = _rule("Lab LCP Above 4.0s (Mobile)")
    assert safe_rule(rule.fn, row) is True
    _score, badge, _icon, matched = score_url_health(row, get_summary_rules())
    assert "Lab LCP Above 4.0s (Mobile)" in matched["Critical"]


def test_low_lighthouse_performance_mobile_fires_under_50() -> None:
    row = {
        "URL": "https://example.com/slow",
        "Extraction State": "partial",
        "Status Code": 200,
        "Lighthouse Performance (Mobile)": 28,
    }
    rule = _rule("Low Lighthouse Performance Mobile (<50)")
    assert safe_rule(rule.fn, row) is True
