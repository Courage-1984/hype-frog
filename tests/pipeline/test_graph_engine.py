"""Click Depth graph intelligence (Phase 7)."""

from __future__ import annotations

from hype_frog.core.models import ExtraRowPayload
from hype_frog.pipeline.graph_engine import (
    CLICK_DEPTH_UNREACHABLE,
    _find_homepage,
    compute_internal_link_intelligence,
)


def test_find_homepage_prefers_root_path() -> None:
    urls = [
        "https://example.com/about",
        "https://example.com",
        "https://example.com/blog/post",
    ]
    assert _find_homepage(urls) == "https://example.com"


def test_find_homepage_falls_back_to_shortest_path() -> None:
    urls = [
        "https://example.com/about",
        "https://example.com/contact",
    ]
    assert _find_homepage(urls) == "https://example.com/about"


def test_click_depth_never_null_and_homepage_is_zero() -> None:
    extra_rows = [
        ExtraRowPayload.model_validate(
            {
                "URL": "https://example.com",
                "Final URL": "https://example.com",
                "Internal Links List": ["https://example.com/about"],
            }
        ),
        ExtraRowPayload.model_validate(
            {
                "URL": "https://example.com/about",
                "Final URL": "https://example.com/about",
                "Internal Links List": [],
            }
        ),
    ]
    metrics = compute_internal_link_intelligence(extra_rows, "example.com")
    home_key = "https://example.com/"
    about_key = "https://example.com/about"
    assert metrics[home_key]["Click Depth"] == 0
    assert metrics[about_key]["Click Depth"] == 1
    assert all(row["Click Depth"] is not None for row in metrics.values())


def test_unreachable_node_gets_minus_one() -> None:
    extra_rows = [
        ExtraRowPayload.model_validate(
            {
                "URL": "https://example.com",
                "Final URL": "https://example.com",
                "Internal Links List": [],
            }
        ),
        ExtraRowPayload.model_validate(
            {
                "URL": "https://example.com/isolated",
                "Final URL": "https://example.com/isolated",
                "Internal Links List": [],
            }
        ),
    ]
    metrics = compute_internal_link_intelligence(extra_rows, "example.com")
    assert metrics["https://example.com/"]["Click Depth"] == 0
    assert metrics["https://example.com/isolated"]["Click Depth"] == CLICK_DEPTH_UNREACHABLE


def test_deep_url_rule_ignores_unreachable_click_depth() -> None:
    from hype_frog.rules import get_summary_rules
    from hype_frog.reporter.summary_builder import safe_rule

    rule = next(r for r in get_summary_rules() if r.name == "Deep URL (>3 clicks)")
    row = {"Click Depth": CLICK_DEPTH_UNREACHABLE}
    assert safe_rule(rule.fn, row) is False
    assert safe_rule(rule.fn, {"Click Depth": 4}) is True
