"""Hreflang audit helpers (A6)."""

from __future__ import annotations

from hype_frog.analysis.hreflang_audit import (
    enrich_hreflang_reciprocity,
    extract_hreflang_from_soup,
    is_valid_hreflang_code,
    parse_hreflang_signal_pairs,
)


def test_is_valid_hreflang_code_accepts_common_values() -> None:
    assert is_valid_hreflang_code("en")
    assert is_valid_hreflang_code("en-GB")
    assert is_valid_hreflang_code("x-default")
    assert not is_valid_hreflang_code("english")


def test_enrich_hreflang_reciprocity_detects_missing_return_link() -> None:
    rows = [
        {
            "URL": "https://example.com/en",
            "Final URL": "https://example.com/en",
            "Hreflang Present": True,
            "Hreflang Code Valid": True,
            "Hreflang Self Reference": True,
            "Hreflang Signals": "en: https://example.com/en; fr: https://example.com/fr",
        },
        {
            "URL": "https://example.com/fr",
            "Final URL": "https://example.com/fr",
            "Hreflang Present": True,
            "Hreflang Code Valid": True,
            "Hreflang Self Reference": True,
            "Hreflang Signals": "fr: https://example.com/fr",
        },
    ]
    enrich_hreflang_reciprocity(rows)
    assert rows[0]["Hreflang Reciprocal Status"] == "Missing Return Link"
    assert rows[0]["Hreflang Reciprocal Check"] is False


def test_parse_hreflang_signal_pairs() -> None:
    pairs = parse_hreflang_signal_pairs(
        "en: https://example.com/en; fr: https://example.com/fr"
    )
    assert pairs == [
        ("en", "https://example.com/en"),
        ("fr", "https://example.com/fr"),
    ]
