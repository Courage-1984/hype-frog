"""Phase helpers for ``assemble_from_html`` — keeps crawler row assembly testable."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from hype_frog.analysis.hreflang_audit import extract_hreflang_from_soup
from hype_frog.core import get_logger
from hype_frog.core.link_constants import GENERIC_ANCHOR_TERMS
from hype_frog.core.text_utils import (
    count_syllables_approx,
    flesch_kincaid_grade_level,
    image_extension,
    looks_generic_image_filename,
    word_count_band,
)
from hype_frog.core.url_normalization import normalize_url_key
from hype_frog.extractors import (
    extract_aeo_snippets,
    extract_heading_outline,
    extract_json_ld_blocks,
    parse_html_signals_from_soup,
    parse_jsonld_summary,
    resolve_indexability_directive,
)
from hype_frog.extractors.eeat import extract_eeat_signals
from hype_frog.extractors.freshness import extract_freshness_signals
from hype_frog.extractors.og_social import extract_og_social_fields
from hype_frog.extractors.page import HeadingOutline
from hype_frog.extractors.semantic_engine import SemanticAnalyzer
from hype_frog.validators.schema_validator import flatten_to_row, validate_schemas_from_html

logger = get_logger(__name__)

_AFRICAN_REGIONAL_TERMS: frozenset[str] = frozenset({
    "africa", "african", "pan-african", "sadc", "ecowas",
    "east africa", "west africa", "southern africa", "north africa",
    "kenya", "south africa", "nigeria", "ghana", "zambia",
    "botswana", "namibia", "uganda", "tanzania", "ethiopia",
    "rwanda", "angola", "mozambique",
})


def _has_truthy_header(value: object) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def _readability_flesch(words: int, sentences: int, syllables: int) -> float | None:
    if words <= 0 or sentences <= 0:
        return None
    score = 206.835 - 1.015 * (words / sentences) - 84.6 * (syllables / words)
    return round(max(0.0, min(100.0, score)), 2)


@dataclass
class HtmlAssemblyContext:
    """Mutable assembly state shared across HTML extraction phases."""

    main_values: dict[str, Any]
    extra_values: dict[str, Any]
    html: str
    resolved_url: str
    analyzer: SemanticAnalyzer
    response_headers: dict[str, str] | None = None
    soup: BeautifulSoup | None = None
    soup_full_text: str = ""
    soup_full_text_lower: str = ""
    heading_outline: HeadingOutline | None = None
    has_list: bool = False
    has_table: bool = False


def apply_crawl_depth_and_security(ctx: HtmlAssemblyContext, *, depth: int) -> None:
    try:
        ctx.extra_values["Crawl Depth"] = max(0, int(depth or 0))
    except (TypeError, ValueError):
        ctx.extra_values["Crawl Depth"] = 0

    ctx.extra_values["Security: HSTS"] = _has_truthy_header(
        ctx.extra_values.get("Strict-Transport-Security")
    )
    ctx.extra_values["Security: CSP"] = _has_truthy_header(
        ctx.extra_values.get("Content-Security-Policy")
    )
    ctx.extra_values["HTML Size (KB)"] = round(len(ctx.html.encode("utf-8")) / 1024, 2)


def parse_html_tree(ctx: HtmlAssemblyContext) -> None:
    ctx.soup = BeautifulSoup(ctx.html, "lxml")
    ctx.soup_full_text = ctx.soup.get_text(" ", strip=True) or ""
    ctx.soup_full_text_lower = ctx.soup_full_text.lower()


def apply_title_and_meta(ctx: HtmlAssemblyContext) -> None:
    assert ctx.soup is not None
    parsed = parse_html_signals_from_soup(ctx.soup)
    body_classes = " ".join(ctx.soup.body.get("class", [])) if ctx.soup.body else ""
    post_id_match = re.search(r"(?:postid|page-id)-(\d+)", body_classes)
    if post_id_match:
        ctx.extra_values["WordPress Post ID"] = int(post_id_match.group(1))

    if parsed.get("title"):
        title_text = str(parsed["title"])
        ctx.main_values["Title"] = title_text
        ctx.main_values["Title Length"] = len(title_text)
        ctx.extra_values["Title Missing"] = False
        ctx.extra_values["SERP Title Pixel Approx"] = int(len(title_text) * 7.2)

    meta_keywords = ctx.soup.find("meta", attrs={"name": "keywords"})
    if meta_keywords and (meta_keywords.get("content") or "").strip():
        keywords = meta_keywords.get("content", "").strip()
        ctx.extra_values["Meta Keywords"] = keywords
        ctx.main_values["Meta Keywords"] = keywords

    if parsed.get("meta_description"):
        desc_text = str(parsed["meta_description"])
        ctx.main_values["Meta Description"] = desc_text
        ctx.main_values["Meta Desc Length"] = len(desc_text)
        ctx.extra_values["Meta Description Missing"] = False
        ctx.extra_values["SERP Meta Pixel Approx"] = int(len(desc_text) * 6.2)


def apply_canonical_and_indexability(ctx: HtmlAssemblyContext) -> None:
    assert ctx.soup is not None
    canonical_tag = ctx.soup.find(
        "link", attrs={"rel": lambda value: value and "canonical" in str(value).lower()}
    )
    canonical_raw = (canonical_tag.get("href") or "").strip() if canonical_tag else ""
    if canonical_raw:
        canonical_abs = normalize_url_key(urljoin(ctx.resolved_url, canonical_raw))
        ctx.extra_values["Canonical URL"] = canonical_abs
        ctx.extra_values["Canonical Absolute URL"] = canonical_abs
        final_norm = normalize_url_key(ctx.resolved_url)
        ctx.extra_values["Canonical Matches Final URL"] = canonical_abs == final_norm
        ctx.extra_values["Canonical Type"] = (
            "self" if canonical_abs == final_norm else "cross-canonical"
        )
    else:
        ctx.extra_values["Canonical Type"] = "missing"

    meta_robots = ctx.soup.find("meta", attrs={"name": lambda v: v and v.lower() == "robots"})
    meta_robots_raw = (
        (meta_robots.get("content") or "").strip() if meta_robots else None
    )
    ctx.extra_values["Meta Robots Raw"] = meta_robots_raw
    ctx.main_values["Indexability"] = resolve_indexability_directive(
        meta_robots_raw, ctx.extra_values.get("X-Robots-Tag")
    )


def apply_hreflang(ctx: HtmlAssemblyContext) -> None:
    assert ctx.soup is not None
    hreflang = extract_hreflang_from_soup(ctx.soup, ctx.resolved_url)
    ctx.extra_values["Hreflang Signals"] = hreflang.signals
    ctx.extra_values["Hreflang Present"] = hreflang.count > 0
    ctx.extra_values["Hreflang Count"] = hreflang.count
    ctx.extra_values["Hreflang Self Reference"] = hreflang.self_referenced
    ctx.extra_values["x-default Present"] = hreflang.x_default_present
    ctx.extra_values["Hreflang Declared Languages"] = hreflang.declared_languages
    ctx.extra_values["Hreflang Alternate URLs"] = hreflang.alternate_urls
    ctx.extra_values["Hreflang Code Valid"] = hreflang.codes_valid
    ctx.extra_values["Hreflang Invalid Codes"] = hreflang.invalid_codes
    ctx.extra_values["Hreflang Reciprocal Status"] = (
        "Not Declared" if hreflang.count == 0 else "Pending Cluster Check"
    )


def apply_og_social(ctx: HtmlAssemblyContext) -> None:
    assert ctx.soup is not None
    from hype_frog.crawler.data_assembler import resolve_best_og_image_url

    og_image_url = resolve_best_og_image_url(ctx.soup, ctx.resolved_url)
    og_social = extract_og_social_fields(
        ctx.soup,
        resolved_url=ctx.resolved_url,
        canonical_url=ctx.extra_values.get("Canonical URL"),
        og_image_url=og_image_url,
    )
    ctx.extra_values.update(og_social["extra"])
    ctx.main_values.update(og_social["main"])


def apply_heading_outline(ctx: HtmlAssemblyContext) -> None:
    ctx.heading_outline = extract_heading_outline(ctx.html)
    assert ctx.heading_outline is not None
    h1_texts = list(ctx.heading_outline.headings_by_level.get(1, ()))
    ctx.extra_values["H1 Count"] = ctx.heading_outline.h1_count
    ctx.extra_values["Current H-Tag Structure"] = ctx.heading_outline.current_h_tag_structure
    ctx.extra_values["Primary H1 Content"] = h1_texts[0] if h1_texts else None
    ctx.extra_values["Missing H1 Flag"] = ctx.heading_outline.h1_count == 0
    ctx.extra_values["Multiple H1 Flag"] = ctx.heading_outline.h1_count > 1
    for level in range(1, 7):
        texts = list(ctx.heading_outline.headings_by_level.get(level, ()))
        if not texts:
            continue
        ctx.main_values[f"H{level} Content"] = " | ".join(texts[:8])
        ctx.main_values[f"H{level} Length"] = len(texts[0])


def apply_body_readability_and_semantic(ctx: HtmlAssemblyContext) -> None:
    assert ctx.soup is not None
    if not ctx.soup.body:
        return

    primary = (
        ctx.soup.find("main")
        or ctx.soup.find("article")
        or ctx.soup.find("div", attrs={"role": "main"})
    )
    if primary is None:
        content_soup = BeautifulSoup(ctx.html, "lxml")
        for tag in content_soup.select("nav, header, footer, aside, script"):
            tag.decompose()
        primary = content_soup.body

    body_text = primary.get_text(separator=" ", strip=True) if primary else ""
    ctx.extra_values["Current Page Copy Snippet"] = (
        (body_text[:250] + "...") if len(body_text) > 250 else body_text
    )
    ctx.extra_values["Body Text Excerpt"] = body_text[:2000]
    words = body_text.split()
    word_count = len(words)
    ctx.main_values["Word Count (Body)"] = word_count
    ctx.extra_values["Word Count"] = word_count
    ctx.extra_values["Thin Content Flag"] = word_count < 300
    ctx.extra_values["Word Count Band"] = word_count_band(word_count)
    sentence_parts = re.split(r"[.!?]+(?:\s+|$)", body_text)
    sentence_count = max(1, len([s for s in sentence_parts if s.strip()]))
    ctx.extra_values["Sentence Count"] = sentence_count
    syllables = count_syllables_approx(body_text)
    ctx.extra_values["Readability (Rough Flesch)"] = _readability_flesch(
        word_count, sentence_count, syllables
    )
    ctx.extra_values["Flesch-Kincaid Grade (Est.)"] = flesch_kincaid_grade_level(
        word_count=word_count,
        sentence_count=sentence_count,
        syllable_count=syllables,
    )

    paragraph_texts: list[str] = []
    if primary is not None:
        for paragraph_tag in primary.find_all("p"):
            paragraph_text = paragraph_tag.get_text(" ", strip=True)
            if paragraph_text:
                paragraph_texts.append(paragraph_text)
    try:
        semantic = ctx.analyzer.analyze(
            body_text=body_text,
            paragraphs=paragraph_texts or None,
        )
    except Exception as exc:
        logger.debug("Semantic analyser raised for %s: %s", ctx.resolved_url, exc)
        semantic = {
            "entity_density": None,
            "top_entities": None,
            "citation_count": 0,
            "aeo_score": None,
            "analysis_mode": "Error",
        }
    ctx.extra_values["Entity Density (%)"] = semantic.get("entity_density")
    top_entities = semantic.get("top_entities")
    ctx.extra_values["Top Entities"] = (
        " | ".join(top_entities) if top_entities else None
    )
    ctx.extra_values["Citation Candidate Count"] = int(semantic.get("citation_count") or 0)
    ctx.extra_values["Semantic AEO Score"] = semantic.get("aeo_score")
    ctx.extra_values["Semantic Analysis Mode"] = semantic.get("analysis_mode")


def apply_aeo_signals(ctx: HtmlAssemblyContext) -> None:
    assert ctx.soup is not None
    assert ctx.heading_outline is not None
    aeo_snippets = extract_aeo_snippets(ctx.html)
    ctx.extra_values["aeo_snippets"] = aeo_snippets
    question_from_snippets = len({s["heading"] for s in aeo_snippets})
    ctx.extra_values["Question Heading Count"] = max(
        ctx.heading_outline.question_heading_count,
        question_from_snippets,
    )
    ctx.extra_values["Paragraphs 40-60 Words Count"] = len(aeo_snippets)
    first_60_words = " ".join(ctx.soup_full_text.split()[:60]).lower()
    ctx.extra_values["Answer Block Detected (First 60 Words)"] = any(
        token in first_60_words
        for token in [" is ", " are ", " means ", " refers to ", " can "]
    ) and len(first_60_words.split()) >= 30
    ctx.has_list = bool(ctx.soup.find(["ul", "ol"]))
    ctx.has_table = bool(ctx.soup.find("table"))
    has_question_headings = ctx.extra_values["Question Heading Count"] > 0
    if has_question_headings and (ctx.has_list or ctx.has_table):
        ctx.extra_values["AEO Extractability Score"] = "High"
    elif has_question_headings or ctx.has_list or ctx.has_table:
        ctx.extra_values["AEO Extractability Score"] = "Medium"
    else:
        ctx.extra_values["AEO Extractability Score"] = "Low"


def apply_regional_authority(ctx: HtmlAssemblyContext) -> None:
    assert ctx.soup is not None
    assert ctx.heading_outline is not None
    h_text = " ".join(
        text
        for level in range(1, 7)
        for text in ctx.heading_outline.headings_by_level.get(level, ())
    ).lower()
    schema_text_l = " ".join(
        s.get_text(" ", strip=True)
        for s in ctx.soup.find_all(
            "script", attrs={"type": "application/ld+json"}
        )
    ).lower()
    regional_hits = sum(
        1
        for term in _AFRICAN_REGIONAL_TERMS
        if term in h_text
        or term in ctx.soup_full_text_lower
        or term in schema_text_l
    )
    ctx.extra_values["Regional Entity Hits"] = regional_hits
    ctx.extra_values["Regional Authority Score"] = min(
        100,
        regional_hits * 10
        + (
            20
            if regional_hits > 0 and any(term in h_text for term in _AFRICAN_REGIONAL_TERMS)
            else 0
        ),
    )


def apply_image_inventory(ctx: HtmlAssemblyContext) -> None:
    assert ctx.soup is not None
    images = ctx.soup.find_all("img")
    ctx.extra_values["Image Count"] = len(images)
    image_urls: list[str] = []
    content_images: list[dict[str, str]] = []
    missing_alt = 0
    for img in images:
        src = (img.get("src") or "").strip()
        if src:
            image_urls.append(src)
            content_images.append(
                {
                    "url": urljoin(ctx.resolved_url, src),
                    "alt": str(img.get("alt") or "").strip(),
                }
            )
        if not (img.get("alt") or "").strip():
            missing_alt += 1
    ctx.extra_values["Content Images"] = content_images
    ctx.extra_values["Has HTML Table"] = bool(ctx.soup.find("table"))
    unique_images = sorted(set(image_urls))
    ctx.extra_values["Images"] = " | ".join(unique_images) if unique_images else None
    ctx.extra_values["Images Missing Alt"] = missing_alt
    ext_counts: defaultdict[str, int] = defaultdict(int)
    generic_image_names = 0
    for img_url in unique_images:
        ext_counts[image_extension(img_url)] += 1
        if looks_generic_image_filename(img_url):
            generic_image_names += 1
    ctx.extra_values["Image Filename Quality Issues"] = generic_image_names
    ctx.extra_values["Image Extension Distribution"] = (
        ", ".join(f"{k}:{v}" for k, v in sorted(ext_counts.items()))
        if ext_counts
        else None
    )
    ctx.extra_values["Image Alt Coverage (%)"] = (
        round(((max(0, len(images) - missing_alt) / len(images)) * 100), 2)
        if images
        else None
    )


def apply_schema_signals(ctx: HtmlAssemblyContext) -> None:
    schema_summary = parse_jsonld_summary(ctx.html)
    schema_types = schema_summary.get("schema_types") or []
    json_ld_blocks = extract_json_ld_blocks(ctx.html)
    schema_result = validate_schemas_from_html(ctx.resolved_url, json_ld_blocks)
    schema_flat = flatten_to_row(schema_result)
    ctx.extra_values.update(schema_flat)
    parse_error_count = max(
        int(schema_summary.get("schema_parse_errors") or 0),
        len(schema_result.parse_errors),
    )
    ctx.extra_values["Schema Parse Errors"] = parse_error_count
    if schema_result.types_found:
        ctx.extra_values["Schema Types Found"] = ", ".join(schema_result.types_found)
    elif schema_types:
        ctx.extra_values["Schema Types Found"] = " | ".join(schema_types)
    ctx.extra_values["Schema Types Count"] = len(schema_result.types_found) or int(
        schema_summary.get("schema_types_count") or 0
    )
    ctx.main_values["Has Valid JSON-LD"] = (
        schema_result.has_any_schema and schema_result.is_fully_valid
    )
    all_schema_types = schema_result.types_found or schema_types
    ctx.extra_values["QAPage/FAQ Schema Present"] = any(
        t.lower() in {"faqpage", "qapage"} for t in all_schema_types
    )
    ctx.extra_values["Speakable Schema Present"] = any(
        "speakable" in t.lower() for t in all_schema_types
    )
    ctx.extra_values["HowTo Signal"] = any(t.lower() == "howto" for t in all_schema_types)
    ctx.extra_values["List/Table Answer Signal"] = bool(ctx.has_list or ctx.has_table)
    ctx.extra_values["Definition Signal"] = bool(
        ctx.extra_values.get("Answer Block Detected (First 60 Words)")
    )


def apply_link_inventory(ctx: HtmlAssemblyContext) -> None:
    assert ctx.soup is not None
    source_netloc = urlparse(ctx.resolved_url).netloc.lower()
    internal_links: list[str] = []
    internal_anchor_texts: list[str] = []
    external_links_count = 0
    nofollow_internal = 0
    nofollow_external = 0
    generic_anchor_text_count = 0
    link_details: list[dict[str, object]] = []
    for anchor in ctx.soup.find_all("a", href=True):
        href_raw = (anchor.get("href") or "").strip()
        if not href_raw or href_raw.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        target_abs = normalize_url_key(urljoin(ctx.resolved_url, href_raw))
        if not target_abs:
            continue
        rel_tokens = {str(token).lower() for token in (anchor.get("rel") or [])}
        nofollow = "nofollow" in rel_tokens
        anchor_text = anchor.get_text(" ", strip=True)
        anchor_norm = anchor_text.strip().lower()
        is_generic_anchor = anchor_norm in GENERIC_ANCHOR_TERMS
        if is_generic_anchor:
            generic_anchor_text_count += 1
        target_netloc = urlparse(target_abs).netloc.lower()
        link_type = "Internal" if target_netloc == source_netloc else "External"
        if link_type == "Internal":
            internal_links.append(target_abs)
            if anchor_text:
                internal_anchor_texts.append(anchor_text)
            if nofollow:
                nofollow_internal += 1
        else:
            external_links_count += 1
            if nofollow:
                nofollow_external += 1
        link_details.append(
            {
                "Source URL": normalize_url_key(ctx.resolved_url),
                "Target URL": target_abs,
                "Anchor Text": anchor_text or None,
                "Rel Attribute": (" ".join(sorted(rel_tokens)) if rel_tokens else None),
                "Link Type": link_type,
                "Nofollow": nofollow,
                "Generic Anchor": bool(is_generic_anchor),
                "Status Code": None,
            }
        )
    unique_internal = sorted(set(internal_links))
    ctx.extra_values["Internal Links List Full"] = unique_internal
    ctx.extra_values["Internal Links List"] = unique_internal[:200]
    ctx.extra_values["Internal Links Count"] = len(internal_links)
    ctx.extra_values["Unique Internal Links Count"] = len(unique_internal)
    ctx.extra_values["External Links Count"] = external_links_count
    ctx.extra_values["Nofollow Internal Links Count"] = nofollow_internal
    ctx.extra_values["Nofollow External Links Count"] = nofollow_external
    ctx.extra_values["Generic Anchor Text Count"] = generic_anchor_text_count
    ctx.extra_values["Link Details"] = link_details
    anchor_total = len(internal_anchor_texts)
    if anchor_total:
        seen_anchor_keys: set[str] = set()
        unique_anchor_texts: list[str] = []
        for text in internal_anchor_texts:
            key = " ".join(text.split()).casefold()
            if key in seen_anchor_keys:
                continue
            seen_anchor_keys.add(key)
            unique_anchor_texts.append(text)
        ctx.extra_values["Anchor Text Diversity"] = (
            f"{len(unique_anchor_texts)} unique / {anchor_total} total"
        )
    else:
        ctx.extra_values["Anchor Text Diversity"] = "0 unique / 0 total"


def apply_eeat_and_freshness(ctx: HtmlAssemblyContext) -> None:
    assert ctx.soup is not None
    ctx.extra_values.update(
        extract_eeat_signals(
            soup=ctx.soup,
            page_url=ctx.resolved_url,
            page_text=ctx.soup_full_text,
        )
    )
    extract_freshness_signals(ctx.response_headers or {}, ctx.soup, ctx.extra_values)
