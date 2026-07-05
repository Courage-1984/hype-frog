"""Detect probable WordPress draft/copy pages and near-duplicate content clusters."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from hype_frog.core.models import ExtraRowPayload, MainRowPayload
from hype_frog.core.text_utils import normalize_text_hash
from hype_frog.pipeline.assemble import normalize_url_key

# WordPress duplicate-page plugins and manual drafts commonly use these slug tails.
_WP_DRAFT_SLUG_SUFFIXES: tuple[re.Pattern[str], ...] = (
    re.compile(r"-copy(?:-\d+)?$", re.IGNORECASE),
    re.compile(r"-draft(?:-\d+)?$", re.IGNORECASE),
    re.compile(r"-old(?:-\d+)?$", re.IGNORECASE),
    re.compile(r"-backup(?:-\d+)?$", re.IGNORECASE),
    re.compile(r"-test(?:-\d+)?$", re.IGNORECASE),
    re.compile(r"-revision(?:-\d+)?$", re.IGNORECASE),
    re.compile(r"-clone(?:-\d+)?$", re.IGNORECASE),
    re.compile(r"-duplicate(?:-\d+)?$", re.IGNORECASE),
)

_STRONG_SIMILARITY_PCT = 70.0
_WARN_SIMILARITY_PCT = 55.0
_MIN_TOKEN_LEN = 4


@dataclass(frozen=True)
class _PageSignals:
    url: str
    parent_key: str
    slug: str
    is_draft_slug: bool
    base_slug: str
    heading_fp: str
    tokens: frozenset[str]
    inlinks: int


def _slug_tail(url: str) -> str:
    path = urlparse(url).path.strip("/")
    if not path:
        return ""
    return path.split("/")[-1]


def _parent_path_key(url: str) -> str:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    host = (parsed.netloc or "").lower()
    if len(parts) <= 1:
        return host or "(root)"
    return f"{host}/{'/'.join(parts[:-1])}"


def is_wordpress_draft_slug(slug: str) -> bool:
    """True when the URL slug looks like a WordPress copy/draft variant."""
    return any(pattern.search(slug) for pattern in _WP_DRAFT_SLUG_SUFFIXES)


def strip_wordpress_draft_suffix(slug: str) -> tuple[bool, str]:
    """Return ``(had_draft_suffix, base_slug_without_suffix)``."""
    for pattern in _WP_DRAFT_SLUG_SUFFIXES:
        if pattern.search(slug):
            return True, pattern.sub("", slug)
    return False, slug


def heading_structure_fingerprint(main_values: Mapping[str, Any]) -> str:
    """Stable fingerprint from ordered H1–H3 heading text (pipe-delimited in rows)."""
    parts: list[str] = []
    for level in (1, 2, 3):
        raw = str(main_values.get(f"H{level} Content") or "").strip()
        if not raw:
            continue
        for piece in raw.split("|"):
            norm = normalize_text_hash(piece.strip())
            if norm:
                parts.append(norm)
    return "||".join(parts)


def content_similarity_tokens(
    main_values: Mapping[str, Any],
    extra_values: Mapping[str, Any],
) -> frozenset[str]:
    """Token bag for Jaccard similarity (headings + body snippet)."""
    chunks = [
        str(main_values.get("H2 Content") or ""),
        str(main_values.get("H3 Content") or ""),
        str(extra_values.get("Current H-Tag Structure") or ""),
        str(extra_values.get("Current Page Copy Snippet") or ""),
        str(extra_values.get("Primary H1 Content") or main_values.get("H1 Content") or ""),
    ]
    text = normalize_text_hash(" ".join(chunks))
    return frozenset(
        token
        for token in text.split()
        if len(token) >= _MIN_TOKEN_LEN and not token.isdigit()
    )


def jaccard_similarity(left: frozenset[str], right: frozenset[str]) -> float:
    if not left or not right:
        return 0.0
    union = len(left | right)
    if union == 0:
        return 0.0
    return len(left & right) / union


def _duplicate_rank(page: _PageSignals) -> tuple[int, int, int]:
    """Higher rank = more likely to be the duplicate (not the canonical target)."""
    return (1 if page.is_draft_slug else 0, -page.inlinks, len(page.url))


def _should_point_to_duplicate(page: _PageSignals, other: _PageSignals) -> bool:
    return _duplicate_rank(page) > _duplicate_rank(other)


def _append_hint(existing: object, addition: str) -> str:
    current = str(existing or "").strip()
    if not current:
        return addition
    if addition in current:
        return current
    return f"{current} | {addition}"


def _build_page_signals(
    main_rows: list[MainRowPayload],
    extra_rows: list[ExtraRowPayload],
    inlinks_map: Mapping[str, set[str]],
) -> list[_PageSignals]:
    extra_by_url = {
        str(row.values.get("URL") or "").strip(): row.values for row in extra_rows if row.values.get("URL")
    }
    pages: list[_PageSignals] = []
    for main_row in main_rows:
        main_values = main_row.values
        url = str(main_values.get("URL") or "").strip()
        if not url:
            continue
        extra_values = extra_by_url.get(url, {})
        final_norm = normalize_url_key(extra_values.get("Final URL") or url)
        slug = _slug_tail(str(extra_values.get("Final URL") or url))
        is_draft, base_slug = strip_wordpress_draft_suffix(slug)
        pages.append(
            _PageSignals(
                url=url,
                parent_key=_parent_path_key(str(extra_values.get("Final URL") or url)),
                slug=slug,
                is_draft_slug=is_draft or is_wordpress_draft_slug(slug),
                base_slug=base_slug,
                heading_fp=heading_structure_fingerprint(main_values),
                tokens=content_similarity_tokens(main_values, extra_values),
                inlinks=len(inlinks_map.get(final_norm, set())),
            )
        )
    return pages


def enrich_content_duplicate_signals(
    main_rows: list[MainRowPayload],
    extra_rows: list[ExtraRowPayload],
    *,
    inlinks_map: Mapping[str, set[str]] | None = None,
) -> list[ExtraRowPayload]:
    """Flag draft/copy URLs and near-duplicate content clusters on extra rows."""
    links = inlinks_map or {}
    pages = _build_page_signals(main_rows, extra_rows, links)
    if not pages:
        return extra_rows

    by_url = {page.url: page for page in pages}
    slug_index: dict[str, dict[str, str]] = defaultdict(dict)
    heading_groups: dict[str, list[_PageSignals]] = defaultdict(list)
    parent_groups: dict[str, list[_PageSignals]] = defaultdict(list)

    for page in pages:
        slug_index[page.parent_key][page.slug.casefold()] = page.url
        if page.heading_fp:
            heading_groups[page.heading_fp].append(page)
        parent_groups[page.parent_key].append(page)

    updates: dict[str, dict[str, Any]] = {}

    for page in pages:
        slug_sibling: str | None = None
        if page.is_draft_slug and page.base_slug:
            slug_sibling = slug_index[page.parent_key].get(page.base_slug.casefold())
            if slug_sibling == page.url:
                slug_sibling = None

        candidates: dict[str, _PageSignals] = {}
        for other in heading_groups.get(page.heading_fp, []):
            if other.url != page.url:
                candidates[other.url] = other
        for other in parent_groups.get(page.parent_key, []):
            if other.url != page.url:
                candidates[other.url] = other

        best_match_url: str | None = None
        best_similarity = 0.0
        for other in candidates.values():
            score = jaccard_similarity(page.tokens, other.tokens)
            if page.heading_fp and page.heading_fp == other.heading_fp:
                score = max(score, 0.72)
            if score > best_similarity:
                best_similarity = score
                best_match_url = other.url

        duplicate_of: str | None = None
        similarity_pct = round(best_similarity * 100.0, 1) if best_similarity > 0 else None

        if slug_sibling:
            duplicate_of = slug_sibling
            sibling = by_url[slug_sibling]
            similarity_pct = max(
                similarity_pct or 0.0,
                round(jaccard_similarity(page.tokens, sibling.tokens) * 100.0, 1),
            )
        elif best_match_url and best_similarity * 100.0 >= _WARN_SIMILARITY_PCT:
            other = by_url[best_match_url]
            if _should_point_to_duplicate(page, other):
                duplicate_of = best_match_url

        heading_cluster_size = len(heading_groups.get(page.heading_fp, [])) if page.heading_fp else 0
        draft_flag = page.is_draft_slug
        in_heading_cluster = False
        if page.heading_fp and heading_cluster_size > 1:
            for other in heading_groups[page.heading_fp]:
                if other.url == page.url:
                    continue
                if jaccard_similarity(page.tokens, other.tokens) * 100.0 >= _WARN_SIMILARITY_PCT:
                    in_heading_cluster = True
                    break
        probable_duplicate = bool(duplicate_of) or draft_flag or in_heading_cluster

        hints: list[str] = []
        if draft_flag:
            hints.append("WordPress draft/copy slug pattern")
        if duplicate_of:
            hints.append(f"Probable duplicate of {duplicate_of}")
        elif draft_flag:
            hints.append("WordPress copy slug — confirm canonical page in CMS")
        if similarity_pct is not None and similarity_pct >= _STRONG_SIMILARITY_PCT:
            hints.append(f"High content similarity ({similarity_pct:.0f}%)")
        elif heading_cluster_size > 1 and page.heading_fp:
            hints.append("Repeated H2/H3 heading structure cluster")

        row_patch: dict[str, Any] = {
            "Draft Page Flag": draft_flag,
            "Probable Duplicate Flag": probable_duplicate,
            "Duplicate Of URL": duplicate_of,
            # Populated even when duplicate_of stays None (e.g. in_heading_cluster
            # is True but _should_point_to_duplicate didn't win the rank
            # comparison) — lets the sheet builder show a real candidate URL
            # instead of a blank target with a "point elsewhere" instruction.
            "Best Match URL": best_match_url,
            "Content Similarity %": similarity_pct,
            "Heading Structure Cluster Size": heading_cluster_size,
        }
        if hints:
            extra_values = next(
                (r.values for r in extra_rows if str(r.values.get("URL") or "").strip() == page.url),
                {},
            )
            row_patch["Cannibalization Hint"] = _append_hint(
                extra_values.get("Cannibalization Hint"),
                " | ".join(hints),
            )
        updates[page.url] = row_patch

    out: list[ExtraRowPayload] = []
    for row in extra_rows:
        url = str(row.values.get("URL") or "").strip()
        patch = updates.get(url)
        if patch:
            out.append(ExtraRowPayload.model_validate({**row.values, **patch}))
        else:
            out.append(row)
    return out


__all__ = [
    "content_similarity_tokens",
    "enrich_content_duplicate_signals",
    "heading_structure_fingerprint",
    "is_wordpress_draft_slug",
    "jaccard_similarity",
    "strip_wordpress_draft_suffix",
]
