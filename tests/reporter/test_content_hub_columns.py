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
    assert content_hub_column_letter("URL Slug Normalization") == "H"
    assert content_hub_column_letter("URL") == "I"
    assert content_hub_column_letter("Current Title") == "K"
    assert content_hub_column_letter("Title Health") == "L"
    assert content_hub_column_letter("On-Page Optimization Score") == "B"
    assert content_hub_column_letter("OG Image Health") == "AC"
    assert content_hub_column_letter("Recommended Action") == "AF"
    assert content_hub_column_letter("Priority Reason") == "AG"
    assert content_hub_column_letter("Entity Density (%)") == "AH"
    assert content_hub_column_letter("Semantic AEO Score") == "AK"


def test_hub_score_link_formula_uses_data_row_and_main_header_row() -> None:
    from openpyxl import Workbook

    from hype_frog.reporter.engine_rows import content_hub_column_letter
    from hype_frog.reporter.sheets.config import CONTENT_OPTIMISATION_HUB_SHEET
    from hype_frog.reporter.sheets.tables_impl import _link_hub_scores_from_main

    wb = Workbook()
    ws = wb.active
    ws.title = CONTENT_OPTIMISATION_HUB_SHEET
    ws.append(["banner"])
    ws.append(["Action Required", "On-Page Optimization Score", "SEO Score", "URL"])
    ws.append(["Needs Copy", 0.0, 12.5, "https://example.com/"])
    _link_hub_scores_from_main(ws)
    seo_col = content_hub_column_letter("SEO Score")
    formula = str(ws[f"{seo_col}3"].value)
    url_col = content_hub_column_letter("URL")
    assert "MATCH(\"SEO Score\",'Main'!$2:$2,0)" in formula
    assert f"MATCH(TRIM({url_col}3" in formula
    assert "OFFSET('Main'!$A$1,2," in formula


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
