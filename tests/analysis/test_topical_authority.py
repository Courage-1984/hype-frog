"""Unit tests for topical authority enrichment (B6)."""

from __future__ import annotations

from hype_frog.analysis.topical_authority import enrich_topical_authority_fields


def test_enrich_topical_authority_fields_adds_keyword_signals() -> None:
    rows = [
        {
            "URL": "https://example.com/marketing-conference",
            "Title": "Marketing Conference Africa",
            "Primary H1 Content": "Marketing Conference Africa",
            "Body Text Excerpt": (
                "The marketing conference africa brings together leaders. "
                "Marketing conference africa events focus on strategy."
            ),
        },
        {
            "URL": "https://example.com/about",
            "Title": "About Us",
            "Primary H1 Content": "About Us",
            "Body Text Excerpt": "We are a general about page with little overlap.",
        },
    ]
    enrich_topical_authority_fields(rows)
    first = rows[0]
    assert first["Keyword in Title"] is True
    assert first["Keyword in H1"] is True
    assert first["Keyword in First Paragraph"] is True
    assert str(first["Top TF-IDF Terms"])
    assert first["Keyword Density (%)"] != ""
