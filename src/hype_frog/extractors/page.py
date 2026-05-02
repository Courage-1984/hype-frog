from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup


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
    return {
        "title": title,
        "meta_description": meta_desc,
        "h1_count": len(soup.find_all("h1")),
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


def extract_aeo_snippets(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    snippets: list[dict[str, Any]] = []
    for heading in soup.find_all(["h2", "h3"]):
        heading_text = heading.get_text(" ", strip=True)
        if not heading_text.endswith("?"):
            continue
        sibling = heading.find_next_sibling()
        while sibling is not None and sibling.name not in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            if sibling.name == "p":
                paragraph = sibling.get_text(" ", strip=True)
                word_count = len(paragraph.split())
                if 40 <= word_count <= 60:
                    snippets.append(
                        {
                            "heading": heading_text,
                            "snippet": paragraph,
                            "word_count": word_count,
                        }
                    )
                    break
            sibling = sibling.find_next_sibling()
    return snippets
