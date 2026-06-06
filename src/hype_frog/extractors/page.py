from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag
from urllib.parse import urljoin

_HEADING_TAG_NAMES: frozenset[str] = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
_CHROME_SELECTORS: tuple[str, ...] = (
    "nav",
    "header",
    "footer",
    "aside",
    "script",
    "style",
    "noscript",
    "template",
    "[role='navigation']",
    "[role='banner']",
    "[role='contentinfo']",
    "[role='complementary']",
)
_HIDDEN_CLASS_RE = re.compile(
    r"(?:^|\s)(?:sr-only|screen-reader|screenreader|visually-hidden|elementor-screen-only|"
    r"hide-text|hidden|wpcf7-screen-reader-response)(?:\s|$)",
    re.IGNORECASE,
)
_MAX_HEADING_CHARS = 500
_MAX_OUTLINE_LINES = 80
_MAX_TEXTS_PER_LEVEL = 24


@dataclass(frozen=True)
class HeadingOutline:
    """Content-scoped heading inventory in document order."""

    h1_count: int
    counts_by_level: dict[int, int] = field(default_factory=dict)
    headings_by_level: dict[int, tuple[str, ...]] = field(default_factory=dict)
    outline_lines: tuple[str, ...] = ()
    question_heading_count: int = 0

    @property
    def current_h_tag_structure(self) -> str:
        return "\n".join(self.outline_lines)


def _normalise_heading_text(raw: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(raw or "").replace("\u00a0", " ")).strip()
    if len(cleaned) > _MAX_HEADING_CHARS:
        return f"{cleaned[: _MAX_HEADING_CHARS - 3]}..."
    return cleaned


def _is_hidden_heading(tag: Tag) -> bool:
    if str(tag.get("aria-hidden") or "").strip().lower() == "true":
        return True
    style = str(tag.get("style") or "").replace(" ", "").lower()
    if "display:none" in style or "visibility:hidden" in style:
        return True
    class_tokens = " ".join(str(c) for c in (tag.get("class") or []))
    if _HIDDEN_CLASS_RE.search(class_tokens):
        return True
    return False


def _prepare_content_root(soup: BeautifulSoup) -> Tag | None:
    for selector in _CHROME_SELECTORS:
        for tag in soup.select(selector):
            tag.decompose()
    return (
        soup.find("main")
        or soup.find("article")
        or soup.find(attrs={"role": "main"})
        or soup.body
    )


def _heading_level_from_tag(tag: Tag) -> int | None:
    name = str(tag.name or "").lower()
    if name in _HEADING_TAG_NAMES:
        return int(name[1])
    if str(tag.get("role") or "").strip().lower() == "heading":
        try:
            level = int(str(tag.get("aria-level") or "2").strip())
        except ValueError:
            level = 2
        return min(6, max(1, level))
    return None


def _is_inside_head(tag: Tag) -> bool:
    for parent in tag.parents:
        if getattr(parent, "name", None) == "head":
            return True
    return False


def _iter_content_headings(root: Tag, *, allow_headings_in_head: bool = False) -> list[tuple[int, str]]:
    discovered: list[tuple[int, str]] = []
    seen_ids: set[int] = set()

    for element in root.descendants:
        if isinstance(element, NavigableString):
            continue
        if not isinstance(element, Tag):
            continue
        element_id = id(element)
        if element_id in seen_ids:
            continue
        level = _heading_level_from_tag(element)
        if level is None:
            continue
        if not allow_headings_in_head and _is_inside_head(element):
            continue
        if _is_hidden_heading(element):
            continue
        text = _normalise_heading_text(element.get_text(" ", strip=True))
        if not text:
            continue
        seen_ids.add(element_id)
        discovered.append((level, text))
    return discovered


def _outline_from_discovered(discovered: list[tuple[int, str]]) -> HeadingOutline:
    counts: dict[int, int] = {level: 0 for level in range(1, 7)}
    by_level: dict[int, list[str]] = {level: [] for level in range(1, 7)}
    outline_lines: list[str] = []
    question_count = 0

    for level, text in discovered:
        counts[level] += 1
        if len(by_level[level]) < _MAX_TEXTS_PER_LEVEL:
            by_level[level].append(text)
        if len(outline_lines) < _MAX_OUTLINE_LINES:
            outline_lines.append(f"H{level}: {text}")
        if text.endswith("?"):
            question_count += 1

    return HeadingOutline(
        h1_count=counts[1],
        counts_by_level=counts,
        headings_by_level={level: tuple(texts) for level, texts in by_level.items()},
        outline_lines=tuple(outline_lines),
        question_heading_count=question_count,
    )


def extract_heading_outline(html: str) -> HeadingOutline:
    """Extract H1–H6 headings from main content, excluding chrome and hidden nodes."""
    soup = BeautifulSoup(html or "", "lxml")
    prepared = _prepare_content_root(BeautifulSoup(html or "", "lxml"))
    discovered = _iter_content_headings(prepared) if prepared is not None else []

    # Damaged markup can leave headings in ``<head>``; recover after chrome strip only.
    if not discovered:
        rescue = BeautifulSoup(html or "", "lxml")
        for selector in _CHROME_SELECTORS:
            for tag in rescue.select(selector):
                tag.decompose()
        discovered = _iter_content_headings(rescue, allow_headings_in_head=True)

    if not discovered:
        empty_counts = {level: 0 for level in range(1, 7)}
        return HeadingOutline(
            h1_count=0,
            counts_by_level=empty_counts,
            headings_by_level={level: () for level in range(1, 7)},
            outline_lines=(),
            question_heading_count=0,
        )

    return _outline_from_discovered(discovered)


def parse_html_signals(html: str) -> dict[str, Any]:
    """
    Pure HTML parser module boundary.
    This is intentionally narrow in Phase 1 and will be expanded as the
    crawler->extractor handoff is progressively deepened.
    """
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    meta = soup.find("meta", attrs={"name": "description"})
    meta_desc = meta.get("content", "").strip() if meta else None
    outline = extract_heading_outline(html)
    return {
        "title": title,
        "meta_description": meta_desc,
        "h1_count": outline.h1_count,
    }


def extract_hreflang_cluster(html: str, page_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links: list[str] = []
    for tag in soup.find_all("link", attrs={"rel": "alternate", "hreflang": True}):
        href = (tag.get("href") or "").strip()
        if href:
            links.append(urljoin(page_url, href).rstrip("/"))
    return links


def has_valid_hreflang_reciprocity(
    html: str,
    page_url: str,
    reciprocal_targets: dict[str, list[str]],
) -> bool:
    source = page_url.rstrip("/")
    cluster = extract_hreflang_cluster(html, page_url)
    if not cluster:
        return True
    for target in cluster:
        backlinks = [u.rstrip("/") for u in reciprocal_targets.get(target, [])]
        if source not in backlinks:
            return False
    return True


def _paragraph_before_next_heading(heading: Tag) -> str | None:
    """Return the first substantive paragraph after ``heading`` and before the next heading."""
    for candidate in heading.find_all_next():
        if candidate is heading:
            continue
        if isinstance(candidate, Tag) and _heading_level_from_tag(candidate) is not None:
            break
        if isinstance(candidate, Tag) and candidate.name == "p":
            paragraph = _normalise_heading_text(candidate.get_text(" ", strip=True))
            if paragraph:
                return paragraph
        if isinstance(candidate, Tag) and candidate.name in {"div", "section", "article"}:
            nested = candidate.find("p")
            if nested is not None:
                paragraph = _normalise_heading_text(nested.get_text(" ", strip=True))
                if paragraph:
                    return paragraph
    return None


def extract_aeo_snippets(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html or "", "lxml")
    root = _prepare_content_root(soup)
    if root is None:
        return []

    snippets: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for element in root.descendants:
        if not isinstance(element, Tag):
            continue
        level = _heading_level_from_tag(element)
        if level is None or level > 4:
            continue
        if _is_hidden_heading(element):
            continue
        heading_text = _normalise_heading_text(element.get_text(" ", strip=True))
        if not heading_text.endswith("?"):
            continue
        paragraph = _paragraph_before_next_heading(element)
        if not paragraph:
            continue
        word_count = len(paragraph.split())
        if not 40 <= word_count <= 60:
            continue
        dedupe_key = (heading_text.casefold(), paragraph.casefold())
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        snippets.append(
            {
                "heading": heading_text,
                "snippet": paragraph,
                "word_count": word_count,
            }
        )
    return snippets
