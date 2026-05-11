"""Content Optimisation Hub column order vs formula letter contracts."""

from hype_frog.reporter.engine_rows import (
    CONTENT_HUB_EXPORT_COLUMNS,
    _CONTENT_HUB_FIELDS_PRE_REORDER,
    content_hub_column_letter,
)
from hype_frog.reporter.sheets.layout import content_optimisation_hub_ordered_headers


def test_content_hub_ordered_headers_matches_reorder_semantics() -> None:
    ordered = content_optimisation_hub_ordered_headers(_CONTENT_HUB_FIELDS_PRE_REORDER)
    assert ordered == CONTENT_HUB_EXPORT_COLUMNS


def test_content_hub_operational_prefix_and_formula_letters() -> None:
    assert CONTENT_HUB_EXPORT_COLUMNS[:6] == (
        "Action Required",
        "On-Page Optimization Score",
        "SEO Score",
        "Technical Health",
        "Copy Score",
        "Status",
    )
    assert content_hub_column_letter("URL") == "H"
    assert content_hub_column_letter("Current Title") == "K"
    assert content_hub_column_letter("Title Health") == "L"
    assert content_hub_column_letter("On-Page Optimization Score") == "B"
    assert content_hub_column_letter("Entity Density (%)") == "AE"
    assert content_hub_column_letter("Semantic AEO Score") == "AH"


def test_hub_display_text_strips_zero_width_space() -> None:
    from hype_frog.reporter.engine_rows import _hub_display_text

    raw = "Hello\u200b World"
    assert _hub_display_text(raw) == "Hello World"


def test_slug_normalization_label_root_vs_nested() -> None:
    from hype_frog.reporter.engine_rows import _slug_normalization_link_label

    assert _slug_normalization_link_label("https://ex.com/", "") == "/"
    assert _slug_normalization_link_label(
        "https://ex.com/foo-bar", ""
    ) == "Foo Bar"
    assert _slug_normalization_link_label("https://ex.com/", "My Keyword") == "My Keyword"
