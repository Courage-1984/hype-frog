"""Unit tests for snippet opportunity scoring (B3)."""

from __future__ import annotations

from hype_frog.analysis.snippet_opportunities import (
    compute_snippet_readiness,
    detect_featured_snippet_type,
    gsc_position_opportunity,
)


def test_detect_featured_snippet_type_faq() -> None:
    row = {
        "Question Heading Count": 2,
        "QAPage/FAQ Schema Present": True,
        "List/Table Answer Signal": False,
    }
    assert detect_featured_snippet_type(row) == "FAQ"


def test_gsc_position_opportunity_requires_mid_rank_and_readiness() -> None:
    row = {
        "GSC Avg Position": 8.5,
        "Featured Snippet Readiness": 7,
    }
    assert gsc_position_opportunity(row, readiness=7) is True
    assert gsc_position_opportunity({"GSC Avg Position": 2.0}, readiness=8) is False


def test_compute_snippet_readiness_caps_at_ten() -> None:
    score = compute_snippet_readiness(
        {
            "Question Heading Count": 3,
            "Paragraphs 40-60 Words Count": 2,
            "QAPage/FAQ Schema Present": True,
            "List/Table Answer Signal": True,
        },
        "FAQ",
    )
    assert 0 < score <= 10
