from __future__ import annotations

import re
from collections import defaultdict
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from hype_frog.extractors import (
    extract_aeo_snippets,
    parse_html_signals,
    parse_jsonld_summary,
    resolve_indexability_directive,
)
from hype_frog.utils import (
    image_extension,
    looks_generic_image_filename,
    normalize_url_key,
    readability_flesch,
    status_class,
    url_depth,
    word_count_band,
)


def init_rows(
    url: str, sitemap_meta: dict[str, dict[str, Any]] | None
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_url = normalize_url_key(url)
    main_data = {
        "URL": normalized_url,
        "Extraction State": "skipped",
        "Extraction Source": "raw_http",
        "Status Code": None,
        "Load Time (s)": None,
        "Indexability": "Indexable",
        "Title": None,
        "Title Length": 0,
        "Meta Description": None,
        "Meta Desc Length": 0,
        "Word Count (Body)": 0,
        "OG-Image": None,
        "Has Valid JSON-LD": False,
    }
    for i in range(1, 7):
        main_data[f"H{i} Content"] = None
        main_data[f"H{i} Length"] = 0
    extra = {
        "URL": normalized_url,
        "Extraction State": "skipped",
        "Extraction Source": "raw_http",
        "Status Code": None,
        "Final URL": None,
        "Protocol": None,
        "Redirect Chain Length": 0,
        "Redirect Target": None,
        "Redirect Hops": None,
        "HTTP->HTTPS Redirect": False,
        "Status Class": None,
        "TTFB (ms)": None,
        "Total Request Time (ms)": None,
        "Content-Type": None,
        "HTTP Version": None,
        "HTML Size (KB)": None,
        "Compression Enabled": False,
        "Cache-Control": None,
        "ETag": None,
        "X-Robots-Tag": None,
        "Meta Robots Raw": None,
        "Canonical URL": None,
        "Canonical Matches Final URL": None,
        "Canonical Type": None,
        "Canonical Absolute URL": None,
        "Canonical in Sitemap Match": None,
        "Hreflang Present": False,
        "Hreflang Count": 0,
        "Hreflang Self Reference": False,
        "Hreflang Reciprocal Check": None,
        "Hreflang Canonical Consistency": None,
        "x-default Present": False,
        "Pagination rel=next": False,
        "Pagination rel=prev": False,
        "H1 Count": 0,
        "Current H-Tag Structure": None,
        "Current Page Copy Snippet": None,
        "Missing H1 Flag": False,
        "Multiple H1 Flag": False,
        "Thin Content Flag": False,
        "Body Text-to-HTML Ratio": None,
        "Word Count": 0,
        "Word Count Band": None,
        "Sentence Count": 0,
        "Readability (Rough Flesch)": None,
        "Last-Modified": None,
        "Published Date": None,
        "Modified Date": None,
        "Last Updated": None,
        "Change Frequency": None,
        "Priority": None,
        "Internal Links Count": 0,
        "External Links Count": 0,
        "Unique Internal Links Count": 0,
        "Nofollow Internal Links Count": 0,
        "Nofollow External Links Count": 0,
        "Generic Anchor Text Count": 0,
        "Param URL Flag": "?" in normalized_url,
        "URL Depth": url_depth(normalized_url),
        "Image Count": 0,
        "Images": None,
        "Images Missing Alt": 0,
        "Image Alt Coverage (%)": None,
        "Image Extension Distribution": None,
        "Likely Large Image Count": 0,
        "Image Filename Quality Issues": 0,
        "Image On Canonical Domain (%)": None,
        "Mixed Content Detected": False,
        "Schema Types Found": None,
        "Schema Types Count": 0,
        "Schema Parse Errors": 0,
        "Open Graph Complete": False,
        "Twitter Card Type": None,
        "OG Title": None,
        "OG Description": None,
        "OG Image": None,
        "Meta Keywords": None,
        "Strict-Transport-Security": None,
        "Content-Security-Policy": None,
        "X-Content-Type-Options": None,
        "X-Frame-Options": None,
        "Referrer-Policy": None,
        "Permissions-Policy": None,
        "Robots.txt Accessible": None,
        "Sitemap in Robots.txt": None,
        "Robots.txt Crawl-Delay": None,
        "Robots.txt Disallow /": None,
        "AI Crawlers Allowed (GPTBot/ClaudeBot/PerplexityBot)": None,
        "llms.txt Present": None,
        "Title Missing": True,
        "Meta Description Missing": True,
        "Indexability Reason": None,
        "SERP Title Truncation Risk": False,
        "SERP Meta Truncation Risk": False,
        "SERP Title Pixel Approx": 0,
        "SERP Meta Pixel Approx": 0,
        "Inlinks Bucket": None,
        "Important But Underlinked": False,
        "Cannibalization Hint": None,
        "FAQ Section Count": 0,
        "Question Heading Count": 0,
        "HowTo Signal": False,
        "Definition Signal": False,
        "List/Table Answer Signal": False,
        "Paragraphs 40-60 Words Count": 0,
        "Answer Block Detected (First 60 Words)": False,
        "AEO Extractability Score": "Low",
        "Regional Authority Score": 0,
        "Regional Entity Hits": 0,
        "CWV LCP (s)": None,
        "CWV INP (ms)": None,
        "CWV CLS": None,
        "CWV Data Source": "Lab",
        "Field vs Lab": "Lab",
        "Speakable Schema Present": False,
        "QAPage/FAQ Schema Present": False,
        "AEO Readiness Score": 0,
        "AEO Badge": "Needs Work",
        "Action Needed": "No",
        "Owner": None,
        "Sprint": "",
        "Status": "Open",
        "Stable Issue IDs": None,
        "WordPress Post ID": None,
        "Internal Links List Full": [],
        "Internal Links List": [],
        "Link Details": [],
        "aeo_snippets": [],
    }
    if sitemap_meta and url in sitemap_meta:
        extra["Change Frequency"] = sitemap_meta[url].get("changefreq")
        extra["Priority"] = sitemap_meta[url].get("priority")
        extra["Last Updated"] = sitemap_meta[url].get("lastmod")
    return main_data, extra


def assemble_from_html(
    *,
    main_data: dict[str, Any],
    extra: dict[str, Any],
    html: str,
    resolved_url: str,
) -> None:
    extra["HTML Size (KB)"] = round(len(html.encode("utf-8")) / 1024, 2)
    parsed = parse_html_signals(html)
    soup = BeautifulSoup(html, "lxml")
    body_classes = " ".join(soup.body.get("class", [])) if soup.body else ""
    post_id_match = re.search(r"(?:postid|page-id)-(\d+)", body_classes)
    if post_id_match:
        extra["WordPress Post ID"] = int(post_id_match.group(1))

    if parsed.get("title"):
        title_text = str(parsed["title"])
        main_data["Title"] = title_text
        main_data["Title Length"] = len(title_text)
        extra["Title Missing"] = False
        extra["SERP Title Pixel Approx"] = int(len(title_text) * 7.2)
    meta_keywords = soup.find("meta", attrs={"name": "keywords"})
    if meta_keywords and (meta_keywords.get("content") or "").strip():
        extra["Meta Keywords"] = meta_keywords.get("content", "").strip()
        main_data["Meta Keywords"] = meta_keywords.get("content", "").strip()
    if parsed.get("meta_description"):
        desc_text = str(parsed["meta_description"])
        main_data["Meta Description"] = desc_text
        main_data["Meta Desc Length"] = len(desc_text)
        extra["Meta Description Missing"] = False
        extra["SERP Meta Pixel Approx"] = int(len(desc_text) * 6.2)

    canonical_tag = soup.find(
        "link", attrs={"rel": lambda value: value and "canonical" in str(value).lower()}
    )
    canonical_raw = (canonical_tag.get("href") or "").strip() if canonical_tag else ""
    if canonical_raw:
        canonical_abs = normalize_url_key(urljoin(resolved_url, canonical_raw))
        extra["Canonical URL"] = canonical_abs
        extra["Canonical Absolute URL"] = canonical_abs
        final_norm = normalize_url_key(resolved_url)
        extra["Canonical Matches Final URL"] = canonical_abs == final_norm
        extra["Canonical Type"] = (
            "self" if canonical_abs == final_norm else "cross-canonical"
        )
    else:
        extra["Canonical Type"] = "missing"

    meta_robots = soup.find("meta", attrs={"name": lambda v: v and v.lower() == "robots"})
    meta_robots_raw = (meta_robots.get("content") or "").strip() if meta_robots else None
    extra["Meta Robots Raw"] = meta_robots_raw
    main_data["Indexability"] = resolve_indexability_directive(
        meta_robots_raw, extra.get("X-Robots-Tag")
    )

    og_title_meta = soup.find("meta", attrs={"property": "og:title"})
    og_desc_meta = soup.find("meta", attrs={"property": "og:description"})
    og_image_meta = soup.find("meta", attrs={"property": "og:image"})
    twitter_image_meta = soup.find("meta", attrs={"name": "twitter:image"})
    twitter_card_meta = soup.find("meta", attrs={"name": "twitter:card"})
    extra["OG Title"] = (
        (og_title_meta.get("content") or "").strip() if og_title_meta else None
    )
    extra["OG Description"] = (
        (og_desc_meta.get("content") or "").strip() if og_desc_meta else None
    )
    extra["Twitter Card Type"] = (
        (twitter_card_meta.get("content") or "").strip() if twitter_card_meta else None
    )
    og_image_url = ""
    if og_image_meta and (og_image_meta.get("content") or "").strip():
        og_image_url = og_image_meta.get("content", "").strip()
    elif twitter_image_meta and (twitter_image_meta.get("content") or "").strip():
        og_image_url = twitter_image_meta.get("content", "").strip()
    if og_image_url:
        extra["OG Image"] = og_image_url
        main_data["OG-Image"] = og_image_url
    extra["Open Graph Complete"] = bool(
        extra["OG Title"] and extra["OG Description"] and extra["OG Image"]
    )

    extra["H1 Count"] = int(parsed.get("h1_count") or 0)
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
    extra["Current H-Tag Structure"] = "\n".join(h_tag_lines).strip()
    extra["Missing H1 Flag"] = extra["H1 Count"] == 0
    extra["Multiple H1 Flag"] = extra["H1 Count"] > 1

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
        extra["Current Page Copy Snippet"] = (
            (body_text[:250] + "...") if len(body_text) > 250 else body_text
        )
        words = body_text.split()
        word_count = len(words)
        main_data["Word Count (Body)"] = word_count
        extra["Word Count"] = word_count
        extra["Thin Content Flag"] = word_count < 300
        extra["Word Count Band"] = word_count_band(word_count)
        sentence_count = max(1, len([s for s in body_text.split(".") if s.strip()]))
        extra["Sentence Count"] = sentence_count
        extra["Readability (Rough Flesch)"] = readability_flesch(word_count, sentence_count)

    aeo_snippets = extract_aeo_snippets(html)
    extra["aeo_snippets"] = aeo_snippets
    extra["Question Heading Count"] = len({s["heading"] for s in aeo_snippets})
    extra["Paragraphs 40-60 Words Count"] = len(aeo_snippets)
    first_60_words = " ".join((soup.get_text(" ", strip=True) or "").split()[:60]).lower()
    extra["Answer Block Detected (First 60 Words)"] = any(
        token in first_60_words for token in [" is ", " are ", " means ", " refers to ", " can "]
    ) and len(first_60_words.split()) >= 30
    has_list = bool(soup.find(["ul", "ol"]))
    has_table = bool(soup.find("table"))
    has_question_headings = extra["Question Heading Count"] > 0
    if has_question_headings and (has_list or has_table):
        extra["AEO Extractability Score"] = "High"
    elif has_question_headings or has_list or has_table:
        extra["AEO Extractability Score"] = "Medium"
    else:
        extra["AEO Extractability Score"] = "Low"

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
    extra["Regional Entity Hits"] = regional_hits
    extra["Regional Authority Score"] = min(
        100,
        regional_hits * 10
        + (
            20
            if regional_hits > 0 and any(term in h_text for term in regional_terms)
            else 0
        ),
    )

    images = soup.find_all("img")
    extra["Image Count"] = len(images)
    image_urls: list[str] = []
    missing_alt = 0
    for img in images:
        src = (img.get("src") or "").strip()
        if src:
            image_urls.append(src)
        if not (img.get("alt") or "").strip():
            missing_alt += 1
    unique_images = sorted(set(image_urls))
    extra["Images"] = " | ".join(unique_images) if unique_images else None
    extra["Images Missing Alt"] = missing_alt
    ext_counts = defaultdict(int)
    generic_image_names = 0
    for img_url in unique_images:
        ext_counts[image_extension(img_url)] += 1
        if looks_generic_image_filename(img_url):
            generic_image_names += 1
    extra["Image Filename Quality Issues"] = generic_image_names
    extra["Image Extension Distribution"] = (
        ", ".join(f"{k}:{v}" for k, v in sorted(ext_counts.items()))
        if ext_counts
        else None
    )
    extra["Image Alt Coverage (%)"] = (
        round(((max(0, len(images) - missing_alt) / len(images)) * 100), 2)
        if images
        else None
    )

    schema_summary = parse_jsonld_summary(html)
    schema_types = schema_summary.get("schema_types") or []
    extra["Schema Types Found"] = " | ".join(schema_types) if schema_types else None
    extra["Schema Types Count"] = int(schema_summary.get("schema_types_count") or 0)
    extra["Schema Parse Errors"] = int(schema_summary.get("schema_parse_errors") or 0)
    main_data["Has Valid JSON-LD"] = (
        extra["Schema Types Count"] > 0 and extra["Schema Parse Errors"] == 0
    )
    extra["QAPage/FAQ Schema Present"] = any(
        t.lower() in {"faqpage", "qapage"} for t in schema_types
    )
    extra["Speakable Schema Present"] = any(
        t.lower() == "speakablespecification" for t in schema_types
    )

    source_netloc = urlparse(resolved_url).netloc.lower()
    internal_links: list[str] = []
    external_links_count = 0
    nofollow_internal = 0
    nofollow_external = 0
    generic_anchor_text_count = 0
    link_details: list[dict[str, Any]] = []
    generic_anchor_tokens = {"click here", "read more", "learn more", "more", "here"}
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
        if anchor_text.lower() in generic_anchor_tokens:
            generic_anchor_text_count += 1
        target_netloc = urlparse(target_abs).netloc.lower()
        link_type = "Internal" if target_netloc == source_netloc else "External"
        if link_type == "Internal":
            internal_links.append(target_abs)
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
                "Rel": " ".join(sorted(rel_tokens)) if rel_tokens else None,
                "Link Type": link_type,
                "Nofollow": nofollow,
            }
        )
    unique_internal = sorted(set(internal_links))
    extra["Internal Links List Full"] = unique_internal
    extra["Internal Links List"] = unique_internal[:200]
    extra["Internal Links Count"] = len(internal_links)
    extra["Unique Internal Links Count"] = len(unique_internal)
    extra["External Links Count"] = external_links_count
    extra["Nofollow Internal Links Count"] = nofollow_internal
    extra["Nofollow External Links Count"] = nofollow_external
    extra["Generic Anchor Text Count"] = generic_anchor_text_count
    extra["Link Details"] = link_details


def finalize_row_state(main_data: dict[str, Any], extra: dict[str, Any]) -> None:
    if extra["Status Class"] is None:
        extra["Status Class"] = status_class(extra["Status Code"])
    status_val = extra["Status Code"]
    status_int = status_val if isinstance(status_val, int) else None
    indexability_reasons: list[str] = []
    if status_int is not None and status_int >= 400:
        indexability_reasons.append(f"HTTP {status_int}")
    if isinstance(status_val, str) and status_val in {"Timeout", "Connection Error"}:
        indexability_reasons.append(status_val)
    if not indexability_reasons:
        directive_state = resolve_indexability_directive(
            extra.get("Meta Robots Raw"), extra.get("X-Robots-Tag")
        )
        indexability_reasons.append(
            "Noindex" if directive_state == "Noindex" else "Indexable"
        )
    extra["Indexability Reason"] = " | ".join(indexability_reasons)
    if main_data.get("Extraction State") not in {"complete", "partial"}:
        main_data["Extraction State"] = "skipped"
    extra["Extraction State"] = main_data["Extraction State"]
