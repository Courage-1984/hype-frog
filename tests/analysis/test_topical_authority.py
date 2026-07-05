"""Unit tests for topical authority enrichment (B6)."""

from __future__ import annotations

from hype_frog.analysis.topical_authority import (
    _build_idf,
    _tokenize,
    _top_tfidf_terms,
    enrich_topical_authority_fields,
)


def test_tokenize_strips_stopwords_and_short_tokens() -> None:
    tokens = _tokenize("The quick brown fox and seo marketing")
    assert "the" not in tokens
    assert "and" not in tokens
    assert "marketing" in tokens


def test_build_idf_weights_rarer_terms_higher() -> None:
    corpus = [
        _tokenize("marketing conference summit"),
        _tokenize("about page"),
        _tokenize("about team"),
    ]
    idf = _build_idf(corpus)
    assert idf["marketing"] > idf["about"]


def test_top_tfidf_terms_returns_highest_scoring_terms() -> None:
    tokens = _tokenize("marketing conference marketing summit marketing")
    idf = {"marketing": 2.0, "conference": 1.5, "summit": 1.2}
    terms = _top_tfidf_terms(tokens, idf, limit=2)
    assert terms[0] == "marketing"
    assert len(terms) == 2


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


def test_enrich_topical_authority_fields_resolves_title_via_titles_by_url() -> None:
    """Regression: Extra rows never carry "Title" directly (only Main rows do) —
    Keyword in Title/Target Keyword must resolve it via the titles_by_url map."""
    url = "https://example.com/marketing-conference"
    rows = [
        {
            "URL": url,
            "Primary H1 Content": "Marketing Conference Africa",
            "Body Text Excerpt": (
                "The marketing conference africa brings together leaders. "
                "Marketing conference africa events focus on strategy."
            ),
        }
    ]
    enrich_topical_authority_fields(rows, titles_by_url={url: "Marketing Conference Africa"})
    assert rows[0]["Keyword in Title"] is True
    assert rows[0]["Target Keyword"]


def test_enrich_topical_authority_fields_without_titles_by_url_stays_false() -> None:
    """Without a title source, Keyword in Title correctly stays False (not a bug)."""
    rows = [
        {
            "URL": "https://example.com/marketing-conference",
            "Primary H1 Content": "Marketing Conference Africa",
            "Body Text Excerpt": "The marketing conference africa brings together leaders.",
        }
    ]
    enrich_topical_authority_fields(rows)
    assert rows[0]["Keyword in Title"] is False
