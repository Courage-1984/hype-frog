"""Unit tests for Content Hub inline recommendations (C3)."""

from __future__ import annotations

from hype_frog.analysis.content_hub_recommendations import (
    build_hub_priority_reason,
    build_hub_recommended_action,
)


def test_build_hub_recommended_action_for_missing_meta() -> None:
    action = build_hub_recommended_action(
        {"Title": "Annual Summit"},
        {"Meta Description Missing": True, "Primary H1 Content": "Annual Summit"},
    )
    assert "meta description" in action.lower()
    assert "Annual Summit" in action


def test_build_hub_priority_reason_mentions_impressions() -> None:
    reason = build_hub_priority_reason(
        {"GSC Impressions": 1200},
        {"GSC Impressions": 1200, "Paragraphs 40-60 Words Count": 0},
    )
    assert "impressions" in reason.lower()
    assert "answer paragraphs" in reason.lower()
