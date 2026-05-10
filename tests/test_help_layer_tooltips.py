"""Contract tests for Excel help-layer tooltips (header drift + formula coverage)."""

from __future__ import annotations

from openpyxl.comments import Comment

from hype_frog.reporter.sheets.dashboard_config import (
    DASHBOARD_KPI_ROW_COMMENTS,
    DASHBOARD_TOOLTIPS,
)
from hype_frog.reporter.sheets.merged_builders import (
    CONTENT_AI_READINESS_COLUMNS,
    LINK_INTELLIGENCE_COLUMNS,
    TECHNICAL_DIAGNOSTICS_COLUMNS,
)
from hype_frog.reporter.sheets.validation import (
    HELP_CALCULATION_PREFIX,
    HELP_DESCRIPTION_PREFIX,
    SCHEMA_METADATA_HEADER_TOOLTIP_BODIES,
    apply_comment_dimensions,
    curated_help_keys_by_sheet,
    format_help_layer,
    resolve_curated_help_body,
    tooltip_for_header,
)


def _assert_help_layer_shape(text: str) -> None:
    assert HELP_DESCRIPTION_PREFIX in text
    assert HELP_CALCULATION_PREFIX in text
    assert "\n" in text


def test_format_help_layer_shape() -> None:
    body = format_help_layer(description="d", calculation="c")
    _assert_help_layer_shape(body)


def test_schema_and_curated_tooltips_include_calculation_section() -> None:
    for _header, body in SCHEMA_METADATA_HEADER_TOOLTIP_BODIES.items():
        _assert_help_layer_shape(body)
    for sheet, keys in curated_help_keys_by_sheet().items():
        for key in keys:
            body = resolve_curated_help_body(sheet, key)
            assert body is not None
            _assert_help_layer_shape(body)


def test_curated_headers_remain_subset_of_export_column_contracts() -> None:
    """If a curated key drifts from merged tab headers, tooltips silently stop applying."""
    contracts = {
        "Technical Diagnostics": TECHNICAL_DIAGNOSTICS_COLUMNS,
        "Content & AI Readiness": CONTENT_AI_READINESS_COLUMNS,
        "Link Intelligence": LINK_INTELLIGENCE_COLUMNS,
    }
    for sheet, keys in curated_help_keys_by_sheet().items():
        allowed = contracts[sheet]
        for key in keys:
            assert key in allowed, f"{sheet}: help key {key!r} missing from column contract"


def test_flesch_kincaid_header_alias_survives_suffix_changes() -> None:
    """Prefix match keeps FK help when marketing tweaks the parenthetical."""
    body = resolve_curated_help_body(
        "Content & AI Readiness",
        "Flesch-Kincaid Grade (Est.) — revised label",
    )
    assert body is not None
    assert "Flesch" in body and HELP_CALCULATION_PREFIX in body


def test_heuristic_tooltip_for_seo_health_header() -> None:
    body = tooltip_for_header("SEO Health Score")
    _assert_help_layer_shape(body)
    assert "score_url_health" in body


def test_dashboard_kpi_blocks_include_calculation() -> None:
    for ref, body in DASHBOARD_KPI_ROW_COMMENTS.items():
        assert ref.startswith("A")
        _assert_help_layer_shape(body)
    for ref, body in DASHBOARD_TOOLTIPS.items():
        assert len(ref) >= 2
        _assert_help_layer_shape(body)


def test_apply_comment_dimensions_increases_default_box() -> None:
    c = Comment("x", "a")
    apply_comment_dimensions(c)
    assert c.width >= 400.0
    assert c.height >= 200.0
