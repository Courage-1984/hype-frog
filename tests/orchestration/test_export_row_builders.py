"""Unit tests for AEO/AIOSEO recommendation row builders.

Covers the page-type detector, numeric coercion helpers, the AEO "Why It
Matters" narrative builder, and the AIOSEO issue-collection + severity
sort contract in :mod:`hype_frog.orchestration.export_row_builders`.
"""

from __future__ import annotations

from hype_frog.orchestration.export_row_builders import (
    _detect_wp_page_type,
    _to_float,
    _to_int,
    _wordpress_edit_context,
    build_aeo_rows,
    build_aioseo_rows,
)

# ---------------------------------------------------------------------------
# _detect_wp_page_type
# ---------------------------------------------------------------------------


def test_detect_wp_page_type_woocommerce_product() -> None:
    assert (
        _detect_wp_page_type("https://example.com/product/widget", 42)
        == "WooCommerce Product"
    )


def test_detect_wp_page_type_regular_post_or_page() -> None:
    assert _detect_wp_page_type("https://example.com/about", 7) == "Post/Page"


def test_detect_wp_page_type_taxonomy_by_url_token() -> None:
    assert (
        _detect_wp_page_type("https://example.com/category/shoes", 0)
        == "Taxonomy/Archive"
    )


def test_detect_wp_page_type_homepage() -> None:
    assert _detect_wp_page_type("https://example.com/", 0) == "Homepage"
    assert _detect_wp_page_type("https://example.com", 0) == "Homepage"


def test_detect_wp_page_type_no_post_id_no_taxonomy_token_falls_back_to_archive() -> None:
    """Any non-homepage page with no WordPress post ID and no recognised
    taxonomy token still classifies as Taxonomy/Archive (the catch-all for
    unmanaged/static content outside the WP admin edit flow)."""
    assert (
        _detect_wp_page_type("https://example.com/some-static-page", 0)
        == "Taxonomy/Archive"
    )


# ---------------------------------------------------------------------------
# _to_int / _to_float coercion
# ---------------------------------------------------------------------------


def test_to_int_coerces_numeric_string() -> None:
    assert _to_int("42") == 42


def test_to_int_none_returns_fallback() -> None:
    assert _to_int(None, fallback=5) == 5


def test_to_int_unparseable_returns_fallback() -> None:
    assert _to_int("not-a-number", fallback=-1) == -1


def test_to_float_coerces_numeric_string() -> None:
    assert _to_float("3.14") == 3.14


def test_to_float_none_returns_fallback() -> None:
    assert _to_float(None, fallback=1.5) == 1.5


def test_to_float_unparseable_returns_fallback() -> None:
    assert _to_float("nope", fallback=-2.0) == -2.0


# ---------------------------------------------------------------------------
# _wordpress_edit_context
# ---------------------------------------------------------------------------


def test_wordpress_edit_context_builds_direct_edit_link() -> None:
    post_id, link = _wordpress_edit_context(
        "https://example.com/post", {"WordPress Post ID": 99}
    )
    assert post_id == 99
    assert link == "https://example.com/wp-admin/post.php?post=99&action=edit"


def test_wordpress_edit_context_no_post_id_no_link() -> None:
    post_id, link = _wordpress_edit_context("https://example.com/post", {})
    assert post_id == 0
    assert link is None


def test_wordpress_edit_context_no_site_root_no_link() -> None:
    post_id, link = _wordpress_edit_context("relative/path", {"WordPress Post ID": 5})
    assert post_id == 5
    assert link is None


# ---------------------------------------------------------------------------
# build_aeo_rows
# ---------------------------------------------------------------------------


def test_build_aeo_rows_all_signals_missing_produces_full_why_notes() -> None:
    rows = build_aeo_rows(
        [
            {
                "Question Heading Count": 0,
                "FAQ Section Count": 0,
                "Paragraphs 40-60 Words Count": 0,
                "QAPage/FAQ Schema Present": False,
                "Speakable Schema Present": False,
                "HowTo Signal": False,
                "Definition Signal": False,
                "List/Table Answer Signal": False,
                "Title Missing": True,
                "Meta Description Missing": True,
                "AEO Readiness Score": 10,
            }
        ]
    )
    assert len(rows) == 1
    why = rows[0]["Why It Matters"]
    assert "answer blocks" in why
    assert "Question-style headings" in why
    assert "FAQ/QA schema" in why
    assert "Speakable" in why
    assert "Missing title/meta" in why


def test_build_aeo_rows_strong_page_gets_maintenance_note() -> None:
    rows = build_aeo_rows(
        [
            {
                "Question Heading Count": 3,
                "FAQ Section Count": 1,
                "Paragraphs 40-60 Words Count": 2,
                "QAPage/FAQ Schema Present": True,
                "Speakable Schema Present": True,
                "HowTo Signal": True,
                "Definition Signal": False,
                "List/Table Answer Signal": False,
                "Title Missing": False,
                "Meta Description Missing": False,
                "AEO Readiness Score": 85,
            }
        ]
    )
    assert rows[0]["Why It Matters"] == (
        "Strong answer-engine foundations are present; maintain concise, "
        "direct answer blocks."
    )


def test_build_aeo_rows_builds_snippet_preview_from_first_snippet() -> None:
    rows = build_aeo_rows(
        [
            {
                "AEO Readiness Score": 90,
                "Question Heading Count": 1,
                "FAQ Section Count": 1,
                "Paragraphs 40-60 Words Count": 1,
                "QAPage/FAQ Schema Present": True,
                "Speakable Schema Present": True,
                "HowTo Signal": True,
                "aeo_snippets": [{"heading": "What is SEO?", "snippet": "Search engine optimisation."}],
            }
        ]
    )
    assert rows[0]["Snippet Preview Mockup"] == "What is SEO?\nSearch engine optimisation."


def test_build_aeo_rows_no_snippet_data_gives_none_preview() -> None:
    rows = build_aeo_rows([{"AEO Readiness Score": 90}])
    assert rows[0]["Snippet Preview Mockup"] is None


def test_build_aeo_rows_does_not_mutate_original_row_dict() -> None:
    original = {"AEO Readiness Score": 90}
    build_aeo_rows([original])
    assert "Why It Matters" not in original


# ---------------------------------------------------------------------------
# build_aioseo_rows
# ---------------------------------------------------------------------------


def _bad_extra_row(url: str = "https://example.com/broken") -> dict[str, object]:
    return {
        "URL": url,
        "Status Code": 404,
        "Indexability Reason": "noindex tag present",
        "Canonical Type": "cross-canonical",
        "Missing H1 Flag": True,
        "Multiple H1 Flag": False,
        "Thin Content Flag": True,
        "Word Count": 50,
        "Readability (Rough Flesch)": 20.0,
        "Internal Links Count": 0,
        "Broken Internal Links Count": 3,
        "Image Alt Coverage (%)": 10.0,
        "Schema Types Count": 0,
        "AEO Readiness Score": 20,
        "QAPage/FAQ Schema Present": False,
        "Question Heading Count": 0,
        "Paragraphs 40-60 Words Count": 0,
        "WordPress Post ID": 0,
    }


def _clean_main_row() -> dict[str, object]:
    return {"Title": "", "Meta Description": ""}


def test_build_aioseo_rows_bad_page_generates_many_issues_sorted_by_severity() -> None:
    extra_rows = [_bad_extra_row()]
    main_by_url = {"https://example.com/broken": _clean_main_row()}
    rows = build_aioseo_rows(extra_rows, main_by_url, {})

    assert len(rows) > 5
    severities = [row["Severity"] for row in rows]
    severity_rank = {"Critical": 0, "Warning": 1, "Observation": 2}
    ranks = [severity_rank[s] for s in severities]
    assert ranks == sorted(ranks)
    assert any(row["Issue"] == "Page returns non-200 response" for row in rows)
    assert any(row["Issue"] == "Noindex directive on page" for row in rows)
    assert any(row["Issue"] == "Canonical configuration issue" for row in rows)


def test_build_aioseo_rows_skips_rows_with_blank_url() -> None:
    rows = build_aioseo_rows([{"URL": ""}], {}, {})
    assert rows == []


def test_build_aioseo_rows_healthy_page_produces_minimal_issues() -> None:
    """A page with no problems should still surface only the always-on
    Observation-level checks (schema-type/FAQ/question-heading nudges),
    never Critical/Warning issues."""
    extra_rows = [
        {
            "URL": "https://example.com/great",
            "Status Code": 200,
            "Indexability Reason": "indexable",
            "Canonical Type": "self",
            "Missing H1 Flag": False,
            "Multiple H1 Flag": False,
            "Thin Content Flag": False,
            "Word Count": 900,
            "Readability (Rough Flesch)": 65.0,
            "Internal Links Count": 5,
            "Broken Internal Links Count": 0,
            "Image Alt Coverage (%)": 100.0,
            "Schema Types Count": 2,
            "AEO Readiness Score": 90,
            "QAPage/FAQ Schema Present": True,
            "Question Heading Count": 2,
            "Paragraphs 40-60 Words Count": 2,
            "WordPress Post ID": 0,
        }
    ]
    main_by_url = {
        "https://example.com/great": {
            "Title": "A" * 50,
            "Meta Description": "B" * 140,
        }
    }
    rows = build_aioseo_rows(extra_rows, main_by_url, {})
    assert all(row["Severity"] != "Critical" for row in rows)
    assert all(row["Severity"] != "Warning" for row in rows)


def test_build_aioseo_rows_taxonomy_page_gets_navigation_suffix() -> None:
    extra_rows = [
        {
            "URL": "https://example.com/category/shoes",
            "Status Code": 404,
            "WordPress Post ID": 0,
        }
    ]
    rows = build_aioseo_rows(
        extra_rows, {"https://example.com/category/shoes": {}}, {}
    )
    status_issue = next(r for r in rows if r["Issue"] == "Page returns non-200 response")
    assert "Taxonomies" in status_issue["How to Fix in AIOSEO"]
    assert status_issue["Page Type"] == "Taxonomy/Archive"
