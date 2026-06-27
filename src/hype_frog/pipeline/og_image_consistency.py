"""Site-wide Open Graph image consistency and legacy-asset detection."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse

_GENERIC_OG_BASENAMES: frozenset[str] = frozenset(
    {
        "og-image.png",
        "og-image.jpg",
        "og-image.jpeg",
        "og-image.webp",
        "og.jpg",
        "og.png",
        "og.webp",
        "opengraph.png",
        "opengraph.jpg",
        "social-share.png",
        "social-share.jpg",
        "share-image.png",
        "default-og.png",
        "default-og.jpg",
    }
)

_LEGACY_OG_RE = re.compile(
    r"(?:^|[_-])(?:faw|legacy|old|backup|archive|copy\d*|v\d+)(?:[_-]|\.|$)|"
    r"(?:^|[_-])amc[_-]faw|faw[_-]amc",
    re.IGNORECASE,
)

_DOMINANT_SHARE_THRESHOLD = 0.35


@dataclass(frozen=True)
class OgImageSiteProfile:
    """Most common OG image basename across the crawl set."""

    dominant_basename: str | None
    dominant_count: int
    total_with_og: int

    @property
    def dominant_share(self) -> float:
        if self.total_with_og <= 0:
            return 0.0
        return self.dominant_count / self.total_with_og


def og_image_basename(url: object) -> str:
    """Return lowercased filename from an OG image URL."""
    raw = str(url or "").strip()
    if not raw:
        return ""
    path = urlparse(raw).path or raw
    name = PurePosixPath(path).name.strip().lower()
    return name


def resolve_og_image_url(
    main_values: Mapping[str, Any] | None,
    extra_values: Mapping[str, Any] | None,
) -> str:
    """Prefer ``OG Image URL``, then extra ``OG Image``, then Main ``OG-Image``."""
    m = main_values or {}
    e = extra_values or {}
    for key in ("OG Image URL", "OG Image", "OG-Image"):
        if key == "OG Image URL":
            raw = e.get(key) or m.get(key)
        elif key == "OG-Image":
            raw = m.get(key)
        else:
            raw = e.get(key)
        text = str(raw or "").strip()
        if text:
            return text
    return ""


def build_og_image_site_profile(
    main_rows: list[Mapping[str, Any]],
    extra_rows: list[Mapping[str, Any]],
) -> OgImageSiteProfile:
    """Count OG image basenames across the full crawl for outlier detection."""
    extra_by_url = {
        str(row.get("URL") or "").strip(): row for row in extra_rows if row.get("URL")
    }
    counts: Counter[str] = Counter()
    for main in main_rows:
        url = str(main.get("URL") or "").strip()
        extra = extra_by_url.get(url, {})
        og_url = resolve_og_image_url(main, extra)
        base = og_image_basename(og_url)
        if base:
            counts[base] += 1
    if not counts:
        return OgImageSiteProfile(dominant_basename=None, dominant_count=0, total_with_og=0)
    dominant, dominant_count = counts.most_common(1)[0]
    return OgImageSiteProfile(
        dominant_basename=dominant,
        dominant_count=dominant_count,
        total_with_og=sum(counts.values()),
    )


def classify_og_image_consistency(
    og_url: object,
    profile: OgImageSiteProfile,
) -> str:
    """Human-readable OG image status for the Content Optimisation Hub."""
    url_text = str(og_url or "").strip()
    if not url_text:
        return "Missing OG image"

    basename = og_image_basename(url_text)
    if not basename:
        return "Missing OG image"

    dominant = profile.dominant_basename
    share = profile.dominant_share

    if dominant and basename == dominant:
        if basename in _GENERIC_OG_BASENAMES:
            return "Site default (generic filename — confirm branded creative)"
        return "Consistent with site default"

    if _LEGACY_OG_RE.search(basename):
        if dominant and share >= _DOMINANT_SHARE_THRESHOLD:
            return f"Legacy/outdated OG asset — site default is {dominant}"
        return "Possible legacy OG asset — review for rebrand"

    if basename in _GENERIC_OG_BASENAMES:
        if dominant and basename != dominant and share >= _DOMINANT_SHARE_THRESHOLD:
            return f"Generic OG file — site mostly uses {dominant}"
        return "Generic OG filename — verify branded asset"

    if dominant and share >= _DOMINANT_SHARE_THRESHOLD and basename != dominant:
        return f"Outlier — site mostly uses {dominant}"

    return "Present — mixed OG images across site"


__all__ = [
    "OgImageSiteProfile",
    "build_og_image_site_profile",
    "classify_og_image_consistency",
    "og_image_basename",
    "resolve_og_image_url",
]
