from __future__ import annotations

from extractors.page import extract_aeo_snippets, has_valid_hreflang_reciprocity, parse_html_signals
from extractors.robots import resolve_indexability_directive
from extractors.schema import parse_jsonld_summary


def test_conflicting_directives_more_restrictive_wins() -> None:
    result = resolve_indexability_directive(
        meta_robots_content="index,follow",
        x_robots_tag="noindex",
    )
    assert result == "Noindex"


def test_hreflang_cluster_flags_missing_reciprocal(hreflang_cluster_html: str) -> None:
    reciprocal_targets = {
        "https://example.com/en/page": ["https://example.com/origin/page"],
        "https://example.com/fr/page": ["https://example.com/origin/page"],
        # Missing backlink from /de/page on purpose.
        "https://example.com/de/page": ["https://example.com/other/page"],
    }
    valid = has_valid_hreflang_reciprocity(
        hreflang_cluster_html,
        "https://example.com/origin/page",
        reciprocal_targets,
    )
    assert valid is False


def test_malformed_schema_fails_gracefully(malformed_schema_html: str) -> None:
    parsed = parse_jsonld_summary(malformed_schema_html)
    assert parsed["schema_parse_errors"] >= 1
    assert "QAPage" in parsed["schema_types"]
    assert parsed["schema_types_count"] >= 1


def test_empty_missing_data_defaults(empty_page_html: str) -> None:
    parsed = parse_html_signals(empty_page_html)
    assert parsed["title"] is None
    assert parsed["meta_description"] is None
    assert parsed["h1_count"] == 0


def test_aeo_snippet_extraction(aeo_content_html: str) -> None:
    snippets = extract_aeo_snippets(aeo_content_html)
    assert len(snippets) == 1
    assert snippets[0]["heading"] == "What is answer engine optimization?"
    assert 40 <= snippets[0]["word_count"] <= 60
    assert "structuring content" in snippets[0]["snippet"].lower()
