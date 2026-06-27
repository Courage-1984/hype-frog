"""Tests for Open Graph and Twitter Card extraction (A1)."""

from __future__ import annotations

from bs4 import BeautifulSoup

from hype_frog.extractors.og_social import (
    compute_og_completeness_score,
    extract_og_social_fields,
    og_image_dimensions_ok,
    og_url_mismatch,
)


def test_extract_og_social_fields_populates_core_columns() -> None:
    html = """
    <html><head>
      <meta property="og:title" content="Conference 2026" />
      <meta property="og:description" content="Join leaders across Africa." />
      <meta property="og:type" content="article" />
      <meta property="og:url" content="https://example.com/events/conference" />
      <meta property="og:image" content="https://cdn.example.com/share.jpg" />
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content="Twitter title" />
      <meta name="twitter:description" content="Twitter description" />
      <meta name="twitter:image" content="https://cdn.example.com/twitter.jpg" />
    </head><body></body></html>
    """
    soup = BeautifulSoup(html, "lxml")
    payload = extract_og_social_fields(
        soup,
        resolved_url="https://example.com/events/conference?utm=1",
        canonical_url="https://example.com/events/conference",
        og_image_url="https://cdn.example.com/share.jpg",
    )
    extra = payload["extra"]
    assert extra["OG Title"] == "Conference 2026"
    assert extra["OG Description"] == "Join leaders across Africa."
    assert extra["OG Type"] == "article"
    assert extra["OG URL"] == "https://example.com/events/conference"
    assert extra["OG Image URL"] == "https://cdn.example.com/share.jpg"
    assert extra["Twitter Card Type"] == "summary_large_image"
    assert extra["Twitter Title"] == "Twitter title"
    assert extra["OG Completeness Score"] == 5
    assert extra["Open Graph Complete"] is True
    assert extra["OG URL Mismatch"] is False
    assert payload["main"]["OG-Image"] == "https://cdn.example.com/share.jpg"


def test_og_url_mismatch_when_differs_from_page_and_canonical() -> None:
    assert og_url_mismatch(
        page_url="https://example.com/page",
        canonical_url="https://example.com/page",
        og_url="https://example.com/other",
    )


def test_og_completeness_score_counts_populated_fields() -> None:
    assert (
        compute_og_completeness_score(
            og_title="Title",
            og_description=None,
            og_type="website",
            og_url=None,
            og_image_url="https://example.com/a.jpg",
        )
        == 3
    )


def test_og_image_dimensions_ok_within_tolerance() -> None:
    assert og_image_dimensions_ok(1200, 630) is True
    assert og_image_dimensions_ok(800, 400) is False
    assert og_image_dimensions_ok(None, 630) is None
