"""Catppuccin Mocha theme palette and HTML integration."""

from __future__ import annotations

from hype_frog.reporter.html_report_data import ReportContext
from hype_frog.reporter.html_report_renderer import render_html_report
from hype_frog.reporter.mocha_theme import (
    JETBRAINS_MONO_CDN,
    MOCHA,
    SEMANTIC,
    excel_palette_overrides,
    html_font_links,
    html_theme_css,
    resolve_accent_colour,
    resolve_brand_colour,
)


def test_mocha_palette_has_official_base_colours() -> None:
    assert MOCHA.base == "#1e1e2e"
    assert MOCHA.green == "#a6e3a1"
    assert MOCHA.teal == "#94e2d5"
    assert SEMANTIC.frog_green == MOCHA.green


def test_resolve_brand_and_accent_defaults() -> None:
    assert resolve_brand_colour(None) == SEMANTIC.brand
    assert resolve_brand_colour("") == SEMANTIC.brand
    assert resolve_brand_colour("#1e293b") == SEMANTIC.brand
    assert resolve_brand_colour("#ff0000") == "#ff0000"

    assert resolve_accent_colour(None) == SEMANTIC.accent
    assert resolve_accent_colour("#2563eb") == SEMANTIC.accent
    assert resolve_accent_colour("#cba6f7") == "#cba6f7"


def test_excel_palette_overrides_use_openpyxl_hex() -> None:
    overrides = excel_palette_overrides()
    assert "#" not in overrides["STD_NAVY"]
    assert overrides["STD_FROG_GREEN"] == "A6E3A1"
    assert overrides["RAG_GREEN"] == SEMANTIC.rag_green


def test_html_font_links_include_jetbrains_mono_cdn() -> None:
    links = html_font_links()
    assert "fonts.googleapis.com" in links
    assert "JetBrains+Mono" in links
    assert JETBRAINS_MONO_CDN in links


def test_html_theme_css_uses_mocha_surfaces() -> None:
    css = html_theme_css(SEMANTIC.brand, SEMANTIC.accent)
    assert SEMANTIC.page_bg in css
    assert SEMANTIC.frog_green in css
    assert "JetBrains Mono" in css


def test_render_html_report_mocha_includes_font_and_dark_bg() -> None:
    ctx = ReportContext(
        domain="example.com",
        crawl_date="2026-06-28",
        total_urls=5,
        theme="mocha",
    )
    html = render_html_report(ctx)
    assert "fonts.googleapis.com" in html
    assert SEMANTIC.page_bg in html
    assert SEMANTIC.frog_green in html


def test_render_html_report_default_theme_is_self_contained() -> None:
    ctx = ReportContext(domain="example.com", crawl_date="2026-06-28", total_urls=1)
    html = render_html_report(ctx)
    assert "fonts.googleapis.com" not in html
    assert "#fff" in html or "background: #fff" in html
