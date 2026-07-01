"""Theme palette constants — Phase 1 UI/UX refurbishment."""

from __future__ import annotations

from hype_frog.reporter.sheets.config import (
    AIOSEO_RECOMMENDATIONS_SHEET,
    GRID_BORDER,
    RAG_AMBER,
    RAG_AMBER_FONT,
    RAG_GREEN,
    RAG_GREEN_FONT,
    RAG_RED,
    RAG_RED_FONT,
    STD_NAVY,
    THEME_HEADER_BG,
    THEME_HEADER_TEXT,
    ZEBRA_FAINT,
)
from hype_frog.reporter.sheets.workbook_layout import (
    TAB_COLOR_TECHNICAL,
    _SHEET_TAB_COLORS,
)


def test_muted_rag_palette_defaults() -> None:
    assert RAG_RED == "FCE8E6"
    assert RAG_RED_FONT == "A51D24"
    assert RAG_AMBER == "FEF3D6"
    assert RAG_AMBER_FONT == "8F6B00"
    assert RAG_GREEN == "E6F4EA"
    assert RAG_GREEN_FONT == "137333"


def test_theme_header_aliases_std_navy() -> None:
    assert THEME_HEADER_BG == "222A35"
    assert THEME_HEADER_TEXT == "FFFFFF"
    assert STD_NAVY == THEME_HEADER_BG


def test_large_sheet_support_tokens() -> None:
    assert GRID_BORDER == "E0E0E0"
    assert ZEBRA_FAINT == "FAFAFA"


def test_aioseo_tab_mapped_to_technical_persona() -> None:
    assert _SHEET_TAB_COLORS[AIOSEO_RECOMMENDATIONS_SHEET] == TAB_COLOR_TECHNICAL
