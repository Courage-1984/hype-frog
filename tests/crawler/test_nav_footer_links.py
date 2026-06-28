"""Tests for nav/footer link extraction in apply_link_inventory."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from hype_frog.crawler.data_assembler_phases import HtmlAssemblyContext, apply_link_inventory
from hype_frog.extractors.semantic_engine import get_default_analyzer


def _make_ctx(html: str, url: str = "https://example.com/") -> HtmlAssemblyContext:
    soup = BeautifulSoup(html, "lxml")
    return HtmlAssemblyContext(
        main_values={},
        extra_values={},
        html=html,
        resolved_url=url,
        analyzer=get_default_analyzer(),
        soup=soup,
    )


# ---------------------------------------------------------------------------
# Nav footer link detection
# ---------------------------------------------------------------------------

def test_nav_links_extracted_to_nav_footer_key() -> None:
    html = """
    <html><body>
      <nav><a href="/about/">About</a><a href="/services/">Services</a></nav>
      <main><a href="/blog/">Blog</a></main>
    </body></html>
    """
    ctx = _make_ctx(html)
    apply_link_inventory(ctx)
    nf = ctx.extra_values["Nav Footer Link Details"]
    targets = {d["Target URL"] for d in nf}
    # normalize_url_key strips trailing slashes on non-root paths
    assert any("/about" in t for t in targets)
    assert any("/services" in t for t in targets)
    assert not any("/blog" in t for t in targets)


def test_footer_links_extracted_and_tagged_as_footer() -> None:
    html = """
    <html><body>
      <footer><a href="/privacy/">Privacy</a><a href="/terms/">Terms</a></footer>
    </body></html>
    """
    ctx = _make_ctx(html)
    apply_link_inventory(ctx)
    nf = ctx.extra_values["Nav Footer Link Details"]
    locations = {d["Link Location"] for d in nf}
    assert "footer" in locations
    assert "nav" not in locations


def test_nav_links_tagged_as_nav() -> None:
    html = """
    <html><body>
      <nav><a href="/contact/">Contact</a></nav>
    </body></html>
    """
    ctx = _make_ctx(html)
    apply_link_inventory(ctx)
    nf = ctx.extra_values["Nav Footer Link Details"]
    assert all(d["Link Location"] == "nav" for d in nf)


def test_role_navigation_treated_as_nav() -> None:
    html = """
    <html><body>
      <div role="navigation"><a href="/faq/">FAQ</a></div>
    </body></html>
    """
    ctx = _make_ctx(html)
    apply_link_inventory(ctx)
    nf = ctx.extra_values["Nav Footer Link Details"]
    targets = {d["Target URL"] for d in nf}
    assert any("/faq" in t for t in targets)


def test_role_contentinfo_treated_as_footer() -> None:
    html = """
    <html><body>
      <div role="contentinfo"><a href="/sitemap/">Sitemap</a></div>
    </body></html>
    """
    ctx = _make_ctx(html)
    apply_link_inventory(ctx)
    nf = ctx.extra_values["Nav Footer Link Details"]
    assert len(nf) == 1
    assert nf[0]["Link Location"] == "footer"


def test_nav_footer_skips_hash_and_mailto_links() -> None:
    html = """
    <html><body>
      <nav>
        <a href="#skip">Skip</a>
        <a href="mailto:info@example.com">Email</a>
        <a href="tel:+27000000">Call</a>
        <a href="/valid/">Valid</a>
      </nav>
    </body></html>
    """
    ctx = _make_ctx(html)
    apply_link_inventory(ctx)
    nf = ctx.extra_values["Nav Footer Link Details"]
    assert len(nf) == 1
    assert any("/valid" in d["Target URL"] for d in nf)


def test_nav_footer_empty_when_no_nav_or_footer() -> None:
    html = """
    <html><body>
      <main><a href="/about/">About</a></main>
    </body></html>
    """
    ctx = _make_ctx(html)
    apply_link_inventory(ctx)
    nf = ctx.extra_values["Nav Footer Link Details"]
    assert nf == []


def test_nav_footer_link_dict_has_required_keys() -> None:
    html = """
    <html><body>
      <nav><a href="/services/">Services</a></nav>
    </body></html>
    """
    ctx = _make_ctx(html)
    apply_link_inventory(ctx)
    nf = ctx.extra_values["Nav Footer Link Details"]
    assert len(nf) == 1
    link = nf[0]
    assert "Source URL" in link
    assert "Target URL" in link
    assert "Anchor Text" in link
    assert "Link Location" in link


def test_nav_footer_anchor_text_captured() -> None:
    html = """
    <html><body>
      <nav><a href="/about/">About Us</a></nav>
    </body></html>
    """
    ctx = _make_ctx(html)
    apply_link_inventory(ctx)
    nf = ctx.extra_values["Nav Footer Link Details"]
    assert nf[0]["Anchor Text"] == "About Us"


def test_nav_footer_source_url_is_resolved_url() -> None:
    html = """<html><body><nav><a href="/page/">Page</a></nav></body></html>"""
    ctx = _make_ctx(html, url="https://example.com/")
    apply_link_inventory(ctx)
    nf = ctx.extra_values["Nav Footer Link Details"]
    assert nf[0]["Source URL"] == "https://example.com/"


# ---------------------------------------------------------------------------
# Coexistence: nav/footer list is independent of the full link details list
# ---------------------------------------------------------------------------

def test_main_link_details_still_includes_all_links() -> None:
    html = """
    <html><body>
      <nav><a href="/nav-page/">Nav Page</a></nav>
      <main><a href="/content-page/">Content Page</a></main>
    </body></html>
    """
    ctx = _make_ctx(html)
    apply_link_inventory(ctx)
    all_targets = {d["Target URL"] for d in ctx.extra_values["Link Details"]}
    assert any("/nav-page" in t for t in all_targets)
    assert any("/content-page" in t for t in all_targets)


def test_nav_footer_does_not_duplicate_into_main_link_details() -> None:
    """Nav/footer extraction must not interfere with the main link loop counts."""
    html = """
    <html><body>
      <nav><a href="/nav/">Nav</a></nav>
      <footer><a href="/foot/">Footer</a></footer>
      <main><a href="/body/">Body</a></main>
    </body></html>
    """
    ctx = _make_ctx(html)
    apply_link_inventory(ctx)
    assert ctx.extra_values["Internal Links Count"] == 3
    assert len(ctx.extra_values["Link Details"]) == 3


# ---------------------------------------------------------------------------
# Both nav and footer present together
# ---------------------------------------------------------------------------

def test_nav_and_footer_both_collected() -> None:
    html = """
    <html><body>
      <nav><a href="/home/">Home</a></nav>
      <footer><a href="/legal/">Legal</a></footer>
    </body></html>
    """
    ctx = _make_ctx(html)
    apply_link_inventory(ctx)
    nf = ctx.extra_values["Nav Footer Link Details"]
    targets = {d["Target URL"] for d in nf}
    assert any("/home" in t for t in targets)
    assert any("/legal" in t for t in targets)
    locations = {d["Link Location"] for d in nf}
    assert "nav" in locations
    assert "footer" in locations
