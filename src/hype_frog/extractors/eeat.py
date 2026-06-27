"""
Extract E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness) signals.
All signals extracted from already-fetched HTML — no additional network calls.
"""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from hype_frog.core import get_logger

logger = get_logger(__name__)


def extract_eeat_signals(
    soup: BeautifulSoup,
    page_url: str,
    page_text: str,
) -> dict[str, Any]:
    out: dict[str, Any] = {}

    author_meta = soup.find("meta", attrs={"name": "author"})
    out["Meta Author"] = author_meta.get("content", "").strip() if author_meta else None

    article_author = soup.find("meta", property="article:author")
    out["OG Article Author"] = article_author.get("content") if article_author else None

    rel_author = soup.find("a", rel=lambda rel: rel and "author" in rel)
    out["Has Rel Author Link"] = rel_author is not None
    out["Rel Author URL"] = rel_author.get("href") if rel_author else None

    byline_candidates = soup.select(
        ".byline, .author, [class*='author'], [class*='byline'], [rel='author']"
    )
    out["Has Byline Element"] = len(byline_candidates) > 0
    out["Byline Text"] = (
        byline_candidates[0].get_text(strip=True)[:120] if byline_candidates else None
    )

    pub_time = soup.find("meta", property="article:published_time")
    out["OG Published Time"] = pub_time.get("content") if pub_time else None

    mod_time = soup.find("meta", property="article:modified_time")
    out["OG Modified Time"] = mod_time.get("content") if mod_time else None

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            graphs = data.get("@graph", [data])
            graph_items = graphs if isinstance(graphs, list) else [graphs]
            for graph_node in graph_items:
                if not isinstance(graph_node, dict):
                    continue
                if not out.get("Schema Published Date"):
                    out["Schema Published Date"] = graph_node.get("datePublished")
                if not out.get("Schema Modified Date"):
                    out["Schema Modified Date"] = graph_node.get("dateModified")
                if not out.get("Schema Author Name"):
                    author = graph_node.get("author")
                    if isinstance(author, dict):
                        out["Schema Author Name"] = author.get("name")
                    elif isinstance(author, str):
                        out["Schema Author Name"] = author
        except Exception as exc:
            logger.debug("Malformed JSON-LD: %s", exc)

    time_el = soup.find("time", attrs={"datetime": True})
    out["Has Time Element"] = time_el is not None
    out["Time Element Datetime"] = time_el.get("datetime") if time_el else None

    about_links = soup.find_all("a", href=re.compile(r"/about", re.I))
    out["Links to About Page"] = len(about_links) > 0

    phone_pattern = re.compile(
        r"(?<!\d)"
        r"(\+\d{1,3}[\s\-]?)?"
        r"(\(?\d{2,4}\)?[\s\-]?)"
        r"\d{3,4}[\s\-]?\d{3,4}"
        r"(?!\d)"
    )
    out["Has Phone Number"] = bool(phone_pattern.search(page_text))

    email_pattern = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
    out["Has Email Address"] = bool(email_pattern.search(page_text))

    privacy_links = soup.find_all(
        "a", href=re.compile(r"privacy|gdpr|popia|data-policy", re.I)
    )
    out["Has Privacy Policy Link"] = len(privacy_links) > 0

    terms_links = soup.find_all(
        "a", href=re.compile(r"terms|conditions|legal|disclaimer", re.I)
    )
    out["Has Terms Link"] = len(terms_links) > 0

    social_patterns = re.compile(
        r"twitter\.com|x\.com|linkedin\.com|facebook\.com|instagram\.com|youtube\.com|tiktok\.com",
        re.I,
    )
    social_links = [anchor.get("href") for anchor in soup.find_all("a", href=social_patterns)]
    out["Social Profile Link Count"] = len(social_links)
    out["Has Social Links"] = len(social_links) > 0

    ext_links = [
        anchor.get("href")
        for anchor in soup.find_all("a", href=True)
        if str(anchor.get("href", "")).startswith("http")
        and urlparse(str(anchor.get("href", ""))).netloc != urlparse(page_url).netloc
    ]
    out["External Link Count"] = len(ext_links)

    authority_domains = re.compile(
        r"wikipedia\.org|\.gov\.|\.edu\.|who\.int|worldbank\.org|un\.org",
        re.I,
    )
    out["Has Authority External Links"] = any(
        authority_domains.search(link) for link in ext_links if link
    )

    score = 0
    if out.get("Meta Author") or out.get("OG Article Author") or out.get("Schema Author Name"):
        score += 2
    if out.get("Has Byline Element"):
        score += 1
    if out.get("OG Published Time") or out.get("Schema Published Date"):
        score += 1
    if out.get("OG Modified Time") or out.get("Schema Modified Date"):
        score += 1
    if out.get("Has Privacy Policy Link"):
        score += 1
    if out.get("Has Terms Link"):
        score += 1
    if out.get("Has Social Links"):
        score += 1
    if out.get("Has Phone Number") or out.get("Has Email Address"):
        score += 1
    if out.get("Links to About Page"):
        score += 1
    out["E-E-A-T Signal Score"] = score

    return out
