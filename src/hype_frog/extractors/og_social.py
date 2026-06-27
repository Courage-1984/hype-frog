"""Open Graph and Twitter Card meta extraction."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from hype_frog.core.url_normalization import normalize_url

_OG_IMAGE_DIM_WIDTH_LO = 960
_OG_IMAGE_DIM_WIDTH_HI = 1440
_OG_IMAGE_DIM_HEIGHT_LO = 504
_OG_IMAGE_DIM_HEIGHT_HI = 756


def _meta_tag_content(tag: object) -> str:
    if tag is None or not hasattr(tag, "get"):
        return ""
    raw = tag.get("content")
    return str(raw).strip() if raw is not None else ""


def _find_meta_property(soup: BeautifulSoup, prop: str) -> str | None:
    target = prop.lower()
    tag = soup.find(
        "meta",
        attrs={"property": lambda value: value and str(value).lower() == target},
    )
    text = _meta_tag_content(tag)
    return text or None


def _find_meta_name(soup: BeautifulSoup, name: str) -> str | None:
    target = name.lower()
    tag = soup.find(
        "meta",
        attrs={"name": lambda value: value and str(value).lower() == target},
    )
    text = _meta_tag_content(tag)
    return text or None


def _normalize_og_url(raw: str | None, base_url: str) -> str | None:
    text = (raw or "").strip()
    if not text:
        return None
    if text.lower().startswith("//"):
        text = "https:" + text
    elif not re.match(r"^https?://", text, re.I):
        text = urljoin(base_url, text)
    try:
        return normalize_url(text, keep_query=True)
    except Exception:
        return text or None


def compute_og_completeness_score(
    *,
    og_title: str | None,
    og_description: str | None,
    og_type: str | None,
    og_url: str | None,
    og_image_url: str | None,
) -> int:
    """One point each for title, description, type, url, and image (0–5)."""
    score = 0
    if og_title:
        score += 1
    if og_description:
        score += 1
    if og_type:
        score += 1
    if og_url:
        score += 1
    if og_image_url:
        score += 1
    return score


def og_url_mismatch(
    *,
    page_url: str,
    canonical_url: str | None,
    og_url: str | None,
) -> bool:
    """True when og:url is set but differs from the page URL and canonical."""
    if not og_url:
        return False
    try:
        norm_og = normalize_url(og_url, keep_query=True)
        norm_page = normalize_url(page_url, keep_query=True)
    except Exception:
        return False
    if norm_og == norm_page:
        return False
    if canonical_url:
        try:
            if norm_og == normalize_url(canonical_url, keep_query=True):
                return False
        except Exception:
            pass
    return True


def og_image_dimensions_ok(width: int | None, height: int | None) -> bool | None:
    """True when within 1200×630 ±20%; None when dimensions unknown."""
    if width is None or height is None:
        return None
    return (
        _OG_IMAGE_DIM_WIDTH_LO <= width <= _OG_IMAGE_DIM_WIDTH_HI
        and _OG_IMAGE_DIM_HEIGHT_LO <= height <= _OG_IMAGE_DIM_HEIGHT_HI
    )


def extract_og_social_fields(
    soup: BeautifulSoup,
    *,
    resolved_url: str,
    canonical_url: str | None = None,
    og_image_url: str | None = None,
) -> dict[str, Any]:
    """Return extra/main row fragments for OG and Twitter Card columns."""
    og_title = _find_meta_property(soup, "og:title")
    og_description = _find_meta_property(soup, "og:description")
    og_type = _find_meta_property(soup, "og:type")
    og_url_raw = _find_meta_property(soup, "og:url")
    og_url = _normalize_og_url(og_url_raw, resolved_url)

    twitter_card = _find_meta_name(soup, "twitter:card")
    twitter_title = _find_meta_name(soup, "twitter:title")
    twitter_description = _find_meta_name(soup, "twitter:description")
    twitter_image_raw = _find_meta_name(soup, "twitter:image")
    twitter_image = _normalize_og_url(twitter_image_raw, resolved_url)

    if not og_image_url:
        og_image_url = None
    completeness = compute_og_completeness_score(
        og_title=og_title,
        og_description=og_description,
        og_type=og_type,
        og_url=og_url,
        og_image_url=og_image_url,
    )
    open_graph_complete = bool(og_title and og_description and og_image_url)
    url_mismatch = og_url_mismatch(
        page_url=resolved_url,
        canonical_url=canonical_url,
        og_url=og_url,
    )

    extra: dict[str, Any] = {
        "OG Title": og_title,
        "OG Description": og_description,
        "OG Type": og_type,
        "OG URL": og_url,
        "OG Image": og_image_url,
        "OG Image URL": og_image_url,
        "Twitter Card Type": twitter_card,
        "Twitter Title": twitter_title,
        "Twitter Description": twitter_description,
        "Twitter Image": twitter_image,
        "OG Completeness Score": completeness,
        "Open Graph Complete": open_graph_complete,
        "OG URL Mismatch": url_mismatch,
    }
    main: dict[str, Any] = {}
    if og_image_url:
        main["OG-Image"] = og_image_url
    return {"extra": extra, "main": main}
