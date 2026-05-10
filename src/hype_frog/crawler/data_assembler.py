from __future__ import annotations

import re
from collections import defaultdict
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from hype_frog.core import get_logger
from hype_frog.core.link_constants import GENERIC_ANCHOR_TERMS
from hype_frog.core.models import ExtraRowPayload, MainRowPayload
from hype_frog.core.text_utils import (
    count_syllables_approx,
    flesch_kincaid_grade_level,
    image_extension,
    looks_generic_image_filename,
    status_class,
    word_count_band,
)
from hype_frog.core.url_normalization import normalize_url
from hype_frog.extractors import (
    extract_aeo_snippets,
    parse_html_signals,
    parse_jsonld_summary,
    resolve_indexability_directive,
)
from hype_frog.extractors.semantic_engine import (
    SemanticAnalyzer,
    get_default_analyzer,
)

logger = get_logger(__name__)


def normalize_url_key(url: object, keep_query: bool = True) -> str:
    return normalize_url(url, keep_query=keep_query)


def readability_flesch(words: int, sentences: int, syllables: int) -> float | None:
    if words <= 0 or sentences <= 0:
        return None
    score = 206.835 - 1.015 * (words / sentences) - 84.6 * (syllables / words)
    bounded_score = max(0.0, min(100.0, score))
    return round(bounded_score, 2)


def url_depth(url: str) -> int:
    path = urlparse(url).path.strip("/")
    if not path:
        return 0
    return len([p for p in path.split("/") if p])


def _has_truthy_header(value: object) -> bool:
    """Treat any non-empty header (string or non-False scalar) as 'present'."""
    if value is None or value is False:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def _extract_hreflang_signals(
    soup: BeautifulSoup, resolved_url: str
) -> tuple[str | None, int, bool, bool]:
    """Return (joined_signals, count, self_referenced, x_default_present).

    Reads ``<link rel="alternate" hreflang="...">`` tags from the parsed
    document and joins them as ``"lang: url; lang: url"`` for the
    workbook. No additional network requests are issued — this is
    purely on-page extraction per the Sprint 4 brief.
    """
    pairs: list[str] = []
    count = 0
    self_referenced = False
    x_default = False
    resolved_norm = normalize_url_key(resolved_url)
    seen: set[tuple[str, str]] = set()
    try:
        candidates = soup.find_all(
            "link", attrs={"rel": True, "hreflang": True}
        )
    except Exception:
        return None, 0, False, False
    for tag in candidates:
        rel_tokens = tag.get("rel") or []
        if isinstance(rel_tokens, str):
            rel_tokens = [rel_tokens]
        if not any("alternate" in str(t).lower() for t in rel_tokens):
            continue
        lang = (tag.get("hreflang") or "").strip()
        href = (tag.get("href") or "").strip()
        if not lang or not href:
            continue
        try:
            absolute = normalize_url_key(urljoin(resolved_url, href))
        except Exception:
            absolute = href
        key = (lang.lower(), absolute)
        if key in seen:
            continue
        seen.add(key)
        count += 1
        pairs.append(f"{lang}: {absolute}")
        if lang.lower() == "x-default":
            x_default = True
        if absolute == resolved_norm:
            self_referenced = True
    if not pairs:
        return None, 0, False, False
    return "; ".join(pairs), count, self_referenced, x_default

def init_rows(
    url: str, sitemap_meta: dict[str, dict[str, object]] | None
) -> tuple[MainRowPayload, ExtraRowPayload]:
    normalized_url = normalize_url_key(url)
    main_payload = MainRowPayload.model_validate(
        {
            "URL": normalized_url,
        }
    )
    extra_payload = ExtraRowPayload.model_validate(
        {
            "URL": normalized_url,
            "Param URL Flag": "?" in normalized_url,
            "URL Depth": url_depth(normalized_url),
        }
    )
    main_data = main_payload.values
    extra = extra_payload.values
    if sitemap_meta and url in sitemap_meta:
        extra["Change Frequency"] = sitemap_meta[url].get("changefreq")
        extra["Priority"] = sitemap_meta[url].get("priority")
        extra["Last Updated"] = sitemap_meta[url].get("lastmod")
    return main_payload, extra_payload


def assemble_from_html(
    *,
    main_data: MainRowPayload,
    extra: ExtraRowPayload,
    html: str,
    resolved_url: str,
    semantic_analyzer: SemanticAnalyzer | None = None,
    depth: int = 0,
) -> None:
    """Populate row payloads from rendered HTML.

    ``depth`` carries the BFS hop count from the seed URL (``0`` for the
    seed). The production crawler entrypoint currently passes the
    default; threading the live BFS distance through ``fetcher.py`` is a
    follow-up tracked outside this sprint's 4-file budget.
    """
    main_values = main_data.values
    extra_values = extra.values
    analyzer = semantic_analyzer or get_default_analyzer()

    try:
        extra_values["Crawl Depth"] = max(0, int(depth or 0))
    except (TypeError, ValueError):
        extra_values["Crawl Depth"] = 0

    extra_values["Security: HSTS"] = _has_truthy_header(
        extra_values.get("Strict-Transport-Security")
    )
    extra_values["Security: CSP"] = _has_truthy_header(
        extra_values.get("Content-Security-Policy")
    )

    extra_values["HTML Size (KB)"] = round(len(html.encode("utf-8")) / 1024, 2)
    parsed = parse_html_signals(html)
    soup = BeautifulSoup(html, "lxml")
    body_classes = " ".join(soup.body.get("class", [])) if soup.body else ""
    post_id_match = re.search(r"(?:postid|page-id)-(\d+)", body_classes)
    if post_id_match:
        extra_values["WordPress Post ID"] = int(post_id_match.group(1))

    if parsed.get("title"):
        title_text = str(parsed["title"])
        main_values["Title"] = title_text
        main_values["Title Length"] = len(title_text)
        extra_values["Title Missing"] = False
        extra_values["SERP Title Pixel Approx"] = int(len(title_text) * 7.2)
    meta_keywords = soup.find("meta", attrs={"name": "keywords"})
    if meta_keywords and (meta_keywords.get("content") or "").strip():
        extra_values["Meta Keywords"] = meta_keywords.get("content", "").strip()
        main_values["Meta Keywords"] = meta_keywords.get("content", "").strip()
    if parsed.get("meta_description"):
        desc_text = str(parsed["meta_description"])
        main_values["Meta Description"] = desc_text
        main_values["Meta Desc Length"] = len(desc_text)
        extra_values["Meta Description Missing"] = False
        extra_values["SERP Meta Pixel Approx"] = int(len(desc_text) * 6.2)

    canonical_tag = soup.find(
        "link", attrs={"rel": lambda value: value and "canonical" in str(value).lower()}
    )
    canonical_raw = (canonical_tag.get("href") or "").strip() if canonical_tag else ""
    if canonical_raw:
        canonical_abs = normalize_url_key(urljoin(resolved_url, canonical_raw))
        extra_values["Canonical URL"] = canonical_abs
        extra_values["Canonical Absolute URL"] = canonical_abs
        final_norm = normalize_url_key(resolved_url)
        extra_values["Canonical Matches Final URL"] = canonical_abs == final_norm
        extra_values["Canonical Type"] = (
            "self" if canonical_abs == final_norm else "cross-canonical"
        )
    else:
        extra_values["Canonical Type"] = "missing"

    meta_robots = soup.find("meta", attrs={"name": lambda v: v and v.lower() == "robots"})
    meta_robots_raw = (meta_robots.get("content") or "").strip() if meta_robots else None
    extra_values["Meta Robots Raw"] = meta_robots_raw
    main_values["Indexability"] = resolve_indexability_directive(
        meta_robots_raw, extra_values.get("X-Robots-Tag")
    )

    # Sprint 4 — on-page hreflang cluster. Populates the long-empty
    # ``Hreflang Present`` / ``Hreflang Count`` columns alongside the
    # new ``Hreflang Signals`` workbook field. No extra network fetch.
    hreflang_signals, hreflang_count, hreflang_self, x_default_present = (
        _extract_hreflang_signals(soup, resolved_url)
    )
    extra_values["Hreflang Signals"] = hreflang_signals
    extra_values["Hreflang Present"] = hreflang_count > 0
    extra_values["Hreflang Count"] = hreflang_count
    extra_values["Hreflang Self Reference"] = hreflang_self
    extra_values["x-default Present"] = x_default_present

    og_title_meta = soup.find("meta", attrs={"property": "og:title"})
    og_desc_meta = soup.find("meta", attrs={"property": "og:description"})
    og_image_meta = soup.find("meta", attrs={"property": "og:image"})
    twitter_image_meta = soup.find("meta", attrs={"name": "twitter:image"})
    twitter_card_meta = soup.find("meta", attrs={"name": "twitter:card"})
    extra_values["OG Title"] = (
        (og_title_meta.get("content") or "").strip() if og_title_meta else None
    )
    extra_values["OG Description"] = (
        (og_desc_meta.get("content") or "").strip() if og_desc_meta else None
    )
    extra_values["Twitter Card Type"] = (
        (twitter_card_meta.get("content") or "").strip() if twitter_card_meta else None
    )
    og_image_url = ""
    if og_image_meta and (og_image_meta.get("content") or "").strip():
        og_image_url = og_image_meta.get("content", "").strip()
    elif twitter_image_meta and (twitter_image_meta.get("content") or "").strip():
        og_image_url = twitter_image_meta.get("content", "").strip()
    if og_image_url:
        extra_values["OG Image"] = og_image_url
        main_values["OG-Image"] = og_image_url
    extra_values["Open Graph Complete"] = bool(
        extra_values["OG Title"] and extra_values["OG Description"] and extra_values["OG Image"]
    )

    extra_values["H1 Count"] = int(parsed.get("h1_count") or 0)
    h_tag_lines: list[str] = []
    h1_tag = soup.find("h1")
    if h1_tag:
        h_tag_lines.append(f"H1: {h1_tag.get_text(' ', strip=True)}")
    for tag in soup.find_all(["h2", "h3"]):
        text = tag.get_text(" ", strip=True)
        if not text:
            continue
        h_tag_lines.append(f"{tag.name.upper()}: {text}")
        if len(h_tag_lines) >= 6:
            break
    extra_values["Current H-Tag Structure"] = "\n".join(h_tag_lines).strip()
    extra_values["Missing H1 Flag"] = extra_values["H1 Count"] == 0
    extra_values["Multiple H1 Flag"] = extra_values["H1 Count"] > 1

    has_list = False
    has_table = False
    if soup.body:
        content_soup = BeautifulSoup(html, "lxml")
        for tag in content_soup.select("nav, header, footer, aside, script"):
            tag.decompose()
        primary = (
            content_soup.find("main")
            or content_soup.find("article")
            or content_soup.find("div", attrs={"role": "main"})
            or content_soup.body
        )
        body_text = primary.get_text(separator=" ", strip=True) if primary else ""
        extra_values["Current Page Copy Snippet"] = (
            (body_text[:250] + "...") if len(body_text) > 250 else body_text
        )
        words = body_text.split()
        word_count = len(words)
        main_values["Word Count (Body)"] = word_count
        extra_values["Word Count"] = word_count
        extra_values["Thin Content Flag"] = word_count < 300
        extra_values["Word Count Band"] = word_count_band(word_count)
        sentence_parts = re.split(r"[.!?]+(?:\s+|$)", body_text)
        sentence_count = max(1, len([s for s in sentence_parts if s.strip()]))
        extra_values["Sentence Count"] = sentence_count
        syllables = count_syllables_approx(body_text)
        extra_values["Readability (Rough Flesch)"] = readability_flesch(
            word_count, sentence_count, syllables
        )
        fk_grade = flesch_kincaid_grade_level(
            word_count=word_count,
            sentence_count=sentence_count,
            syllable_count=syllables,
        )
        extra_values["Flesch-Kincaid Grade (Est.)"] = fk_grade

        # Sprint 3 semantic + citation analysis. Reuses the cleaned text
        # already produced above; ``primary`` provides paragraph-level text
        # for accurate 40-60 word citation windowing without re-parsing
        # the HTML. Falls back gracefully when spaCy is unavailable —
        # the citation count keeps working in that case.
        paragraph_texts: list[str] = []
        if primary is not None:
            for paragraph_tag in primary.find_all("p"):
                paragraph_text = paragraph_tag.get_text(" ", strip=True)
                if paragraph_text:
                    paragraph_texts.append(paragraph_text)
        try:
            semantic = analyzer.analyze(
                body_text=body_text,
                paragraphs=paragraph_texts or None,
            )
        except Exception as exc:  # never let semantic failure abort the row
            logger.debug("Semantic analyser raised for %s: %s", resolved_url, exc)
            semantic = {
                "entity_density": None,
                "top_entities": None,
                "citation_count": 0,
                "aeo_score": None,
            }
        extra_values["Entity Density (%)"] = semantic.get("entity_density")
        top_entities = semantic.get("top_entities")
        extra_values["Top Entities"] = (
            " | ".join(top_entities) if top_entities else None
        )
        extra_values["Citation Candidate Count"] = int(
            semantic.get("citation_count") or 0
        )
        extra_values["Semantic AEO Score"] = semantic.get("aeo_score")

    aeo_snippets = extract_aeo_snippets(html)
    extra_values["aeo_snippets"] = aeo_snippets
    extra_values["Question Heading Count"] = len({s["heading"] for s in aeo_snippets})
    extra_values["Paragraphs 40-60 Words Count"] = len(aeo_snippets)
    first_60_words = " ".join((soup.get_text(" ", strip=True) or "").split()[:60]).lower()
    extra_values["Answer Block Detected (First 60 Words)"] = any(
        token in first_60_words for token in [" is ", " are ", " means ", " refers to ", " can "]
    ) and len(first_60_words.split()) >= 30
    has_list = bool(soup.find(["ul", "ol"]))
    has_table = bool(soup.find("table"))
    has_question_headings = extra_values["Question Heading Count"] > 0
    if has_question_headings and (has_list or has_table):
        extra_values["AEO Extractability Score"] = "High"
    elif has_question_headings or has_list or has_table:
        extra_values["AEO Extractability Score"] = "Medium"
    else:
        extra_values["AEO Extractability Score"] = "Low"

    regional_terms = [
        "africa",
        "african",
        "pan-african",
        "sadc",
        "ecowas",
        "east africa",
        "west africa",
        "southern africa",
        "north africa",
        "kenya",
        "south africa",
        "nigeria",
        "ghana",
        "zambia",
        "botswana",
        "namibia",
        "uganda",
        "tanzania",
        "ethiopia",
        "rwanda",
        "angola",
        "mozambique",
    ]
    h_text = " ".join(
        h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"])
    ).lower()
    body_text_l = (soup.get_text(" ", strip=True) or "").lower()
    schema_text_l = " ".join(
        s.get_text(" ", strip=True)
        for s in soup.find_all("script", attrs={"type": "application/ld+json"})
    ).lower()
    regional_hits = sum(
        1
        for term in regional_terms
        if term in h_text or term in body_text_l or term in schema_text_l
    )
    extra_values["Regional Entity Hits"] = regional_hits
    extra_values["Regional Authority Score"] = min(
        100,
        regional_hits * 10
        + (
            20
            if regional_hits > 0 and any(term in h_text for term in regional_terms)
            else 0
        ),
    )

    images = soup.find_all("img")
    extra_values["Image Count"] = len(images)
    image_urls: list[str] = []
    missing_alt = 0
    for img in images:
        src = (img.get("src") or "").strip()
        if src:
            image_urls.append(src)
        if not (img.get("alt") or "").strip():
            missing_alt += 1
    unique_images = sorted(set(image_urls))
    extra_values["Images"] = " | ".join(unique_images) if unique_images else None
    extra_values["Images Missing Alt"] = missing_alt
    ext_counts = defaultdict(int)
    generic_image_names = 0
    for img_url in unique_images:
        ext_counts[image_extension(img_url)] += 1
        if looks_generic_image_filename(img_url):
            generic_image_names += 1
    extra_values["Image Filename Quality Issues"] = generic_image_names
    extra_values["Image Extension Distribution"] = (
        ", ".join(f"{k}:{v}" for k, v in sorted(ext_counts.items()))
        if ext_counts
        else None
    )
    extra_values["Image Alt Coverage (%)"] = (
        round(((max(0, len(images) - missing_alt) / len(images)) * 100), 2)
        if images
        else None
    )

    schema_summary = parse_jsonld_summary(html)
    schema_types = schema_summary.get("schema_types") or []
    extra_values["Schema Types Found"] = " | ".join(schema_types) if schema_types else None
    extra_values["Schema Types Count"] = int(schema_summary.get("schema_types_count") or 0)
    extra_values["Schema Parse Errors"] = int(schema_summary.get("schema_parse_errors") or 0)
    main_values["Has Valid JSON-LD"] = (
        extra_values["Schema Types Count"] > 0 and extra_values["Schema Parse Errors"] == 0
    )
    extra_values["QAPage/FAQ Schema Present"] = any(
        t.lower() in {"faqpage", "qapage"} for t in schema_types
    )
    extra_values["Speakable Schema Present"] = any(
        "speakable" in t.lower() for t in schema_types
    )
    extra_values["HowTo Signal"] = any(t.lower() == "howto" for t in schema_types)
    extra_values["List/Table Answer Signal"] = bool(has_list or has_table)
    extra_values["Definition Signal"] = bool(
        extra_values.get("Answer Block Detected (First 60 Words)")
    )

    source_netloc = urlparse(resolved_url).netloc.lower()
    internal_links: list[str] = []
    internal_anchor_texts: list[str] = []
    external_links_count = 0
    nofollow_internal = 0
    nofollow_external = 0
    generic_anchor_text_count = 0
    link_details: list[dict[str, object]] = []
    for anchor in soup.find_all("a", href=True):
        href_raw = (anchor.get("href") or "").strip()
        if not href_raw or href_raw.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        target_abs = normalize_url_key(urljoin(resolved_url, href_raw))
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
                "Source URL": normalize_url_key(resolved_url),
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
    extra_values["Internal Links List Full"] = unique_internal
    extra_values["Internal Links List"] = unique_internal[:200]
    extra_values["Internal Links Count"] = len(internal_links)
    extra_values["Unique Internal Links Count"] = len(unique_internal)
    extra_values["External Links Count"] = external_links_count
    extra_values["Nofollow Internal Links Count"] = nofollow_internal
    extra_values["Nofollow External Links Count"] = nofollow_external
    extra_values["Generic Anchor Text Count"] = generic_anchor_text_count
    extra_values["Link Details"] = link_details
    # Sprint 4 — anchor-text diversity summary derived from the
    # internal anchor pool just collected above. Casefold dedup so
    # "Learn more" and "learn  more" collapse into a single bucket.
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
        extra_values["Anchor Text Diversity"] = (
            f"{len(unique_anchor_texts)} unique / {anchor_total} total"
        )
    else:
        extra_values["Anchor Text Diversity"] = "0 unique / 0 total"

def finalize_row_state(
    main_data: MainRowPayload,
    extra: ExtraRowPayload,
) -> None:
    main_values = main_data.values
    extra_values = extra.values

    if extra_values["Status Class"] is None:
        extra_values["Status Class"] = status_class(extra_values["Status Code"])
    status_val = extra_values["Status Code"]
    status_int = status_val if isinstance(status_val, int) else None
    indexability_reasons: list[str] = []
    if status_int is not None and status_int >= 400:
        indexability_reasons.append(f"HTTP {status_int}")
    if isinstance(status_val, str) and status_val in {"Timeout", "Connection Error"}:
        indexability_reasons.append(status_val)
    if not indexability_reasons:
        directive_state = resolve_indexability_directive(
            extra_values.get("Meta Robots Raw"), extra_values.get("X-Robots-Tag")
        )
        indexability_reasons.append(
            "Noindex" if directive_state == "Noindex" else "Indexable"
        )
    extra_values["Indexability Reason"] = " | ".join(indexability_reasons)
    if main_values.get("Extraction State") not in {"complete", "partial"}:
        main_values["Extraction State"] = "skipped"
    extra_values["Extraction State"] = main_values["Extraction State"]
