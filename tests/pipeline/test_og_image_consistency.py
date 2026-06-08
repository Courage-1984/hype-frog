"""OG image site profile and Content Hub health labels."""

from __future__ import annotations

from hype_frog.pipeline.og_image_consistency import (
    build_og_image_site_profile,
    classify_og_image_consistency,
    og_image_basename,
)


def test_og_image_basename_from_url() -> None:
    assert og_image_basename("https://cdn.example.com/uploads/og-image.png?v=2") == "og-image.png"


def test_legacy_faw_asset_flagged_against_site_default() -> None:
    main_rows = [
        {"URL": "https://example.com/a", "OG-Image": "https://example.com/og-image.png"},
        {"URL": "https://example.com/b", "OG-Image": "https://example.com/og-image.png"},
        {"URL": "https://example.com/c", "OG-Image": "https://example.com/og-image.png"},
    ]
    extra_rows = [
        {
            "URL": "https://example.com/speakers-copy",
            "OG Image": "https://example.com/media/amc_faw.png",
        }
    ]
    profile = build_og_image_site_profile(main_rows, extra_rows)
    assert profile.dominant_basename == "og-image.png"
    note = classify_og_image_consistency(
        "https://example.com/media/amc_faw.png",
        profile,
    )
    assert "Legacy" in note or "Outlier" in note
    assert "og-image.png" in note


def test_consistent_default_image() -> None:
    profile = build_og_image_site_profile(
        [{"URL": "https://example.com/", "OG-Image": "https://example.com/og-image.png"}],
        [],
    )
    assert (
        classify_og_image_consistency("https://example.com/og-image.png", profile)
        == "Site default (generic filename — confirm branded creative)"
    )
