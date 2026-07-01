"""Phase 3 polish regression guards: formulas, formats, visibility, display headers."""

from __future__ import annotations

from openpyxl import Workbook

from hype_frog.pipeline.broken_links import link_inventory_broken_internal_total_formula
from hype_frog.reporter.sheets.layout import (
    DISPLAY_HEADER_ALIASES,
    apply_display_header_aliases,
    link_intelligence_column_letter,
    link_inventory_column_letter,
    sheet_data_column_range,
)
from hype_frog.reporter.sheets.links import _fixplan_hub_status_formula
from hype_frog.reporter.sheets.number_formats import apply_south_african_formats
from hype_frog.reporter.sheets.workbook_layout import (
    DASHBOARD_ADVANCED_SHEET_LINKS,
    SHEETS_EXCLUDED_FROM_TOC,
)


def test_fixplan_hub_status_uses_status_not_seo_score_column() -> None:
    formula = _fixplan_hub_status_formula("H", 4)
    assert "!F3:F10000" in formula
    assert "!I3:I10000" in formula
    assert "!C:C" not in formula


def test_link_inventory_formula_uses_header_resolved_columns() -> None:
    formula = link_inventory_broken_internal_total_formula()
    lt = link_inventory_column_letter("Link Type")
    sc = link_inventory_column_letter("Status Code")
    assert f"'Link Inventory'!${lt}$2:${lt}$100000" in formula
    assert f"'Link Inventory'!${sc}$2:${sc}$100000" in formula
    assert lt == "E" and sc == "F"


def test_link_intelligence_generic_anchor_column_is_dynamic() -> None:
    assert link_intelligence_column_letter("Generic Anchor Text Count") == "O"
    assert link_intelligence_column_letter("Record Type") == "B"


def test_sheet_data_column_range_is_header_driven() -> None:
    rng = sheet_data_column_range("Technical Diagnostics", "SEO Health Score")
    assert "MATCH(\"SEO Health Score\"" in rng
    assert "Technical Diagnostics" in rng
    assert "$2:$2" in rng


def test_sheet_data_column_range_main_uses_row2_header_and_row3_data() -> None:
    rng = sheet_data_column_range("Main", "SEO Score")
    assert "MATCH(\"SEO Score\",'Main'!$2:$2,0)" in rng
    assert "OFFSET('Main'!$A$1,2," in rng


def test_issue_inventory_excluded_from_toc_and_dashboard_links() -> None:
    assert "IssueInventory" in SHEETS_EXCLUDED_FROM_TOC
    assert all(name != "IssueInventory" for name, _ in DASHBOARD_ADVANCED_SHEET_LINKS)


def test_issue_inventory_skipped_in_toc_advanced_section() -> None:
    from hype_frog.reporter.sheets.toc import ADVANCED_WORKBOOK_TAB_ORDER

    assert "IssueInventory" in ADVANCED_WORKBOOK_TAB_ORDER
    assert "IssueInventory" in SHEETS_EXCLUDED_FROM_TOC


def test_display_header_alias_rewrites_optimisation_label() -> None:
    ws = Workbook().active
    ws["A1"] = "On-Page Optimization Score"
    ws["B1"] = "URL"
    apply_display_header_aliases(ws)
    assert ws["A1"].value == DISPLAY_HEADER_ALIASES["On-Page Optimization Score"]
    assert ws["B1"].value == "URL"


def test_number_formats_apply_to_psi_and_citation_count() -> None:
    ws = Workbook().active
    ws["A1"] = "Mobile PSI Score"
    ws["A2"] = 0.82
    ws["B1"] = "Citation Candidate Count"
    ws["B2"] = 3
    apply_south_african_formats(ws)
    assert ws["A2"].number_format == "[$-en-ZA]#,##0"
    assert ws["B2"].number_format == "[$-en-ZA]#,##0"
