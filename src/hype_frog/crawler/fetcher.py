from __future__ import annotations

import asyncio
import random
import re
import time
from collections import defaultdict
from typing import Any
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup

from hype_frog.config import (
    CONNECT_TIMEOUT_SECONDS,
    DELAY_BETWEEN_REQUESTS,
    PLAYWRIGHT_MAX_SESSIONS,
    MAX_RETRIES,
    READ_TIMEOUT_SECONDS,
    REQUEST_JITTER_SECONDS,
    RETRY_BACKOFF_FACTOR,
    RETRY_BASE_DELAY_SECONDS,
    RETRY_MAX_DELAY_SECONDS,
    RETRYABLE_STATUS_CODES,
    TIMEOUT_SECONDS,
)
from hype_frog.core import get_logger
from hype_frog.extractors import (
    extract_aeo_snippets,
    parse_html_signals,
    parse_jsonld_summary,
    resolve_indexability_directive,
)
from hype_frog.utils import image_extension, looks_generic_image_filename, normalize_url_key, readability_flesch, status_class, url_depth, word_count_band

logger = get_logger(__name__)
_PLAYWRIGHT_SEMAPHORE = asyncio.Semaphore(max(1, int(PLAYWRIGHT_MAX_SESSIONS)))


async def _fetch_rendered_html(
    target_url: str,
    render_wait_ms: int,
    selector_wait_ms: int,
) -> tuple[str | None, str, str, dict[str, str] | None]:
    async with _PLAYWRIGHT_SEMAPHORE:
        try:
            probe = await asyncio.create_subprocess_exec(
                "python",
                "-c",
                "print('ok')",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await probe.communicate()
        except NotImplementedError:
            logger.warning(
                "Accurate mode requested but this asyncio event loop cannot spawn subprocesses. "
                "Falling back to HTTP mode."
            )
            return None, "raw_http", "partial", None

        try:
            from playwright.async_api import Error as PlaywrightError
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            from playwright.async_api import async_playwright
        except Exception:
            logger.warning(
                "Accurate mode requested but Playwright is unavailable. "
                "Install with: pip install playwright && playwright install chromium"
            )
            return None, "raw_http", "partial", None

        browser = None
        try:
            async with async_playwright() as p:
                try:
                    browser = await p.chromium.launch(headless=True)
                except Exception:
                    logger.warning("Chromium browser binaries are missing. Run: playwright install chromium")
                    return None, "raw_http", "partial", None
                context = await browser.new_context()
                page = await context.new_page()
                try:
                    nav_response = await page.goto(target_url, wait_until="domcontentloaded", timeout=max(3000, render_wait_ms))
                    try:
                        await page.wait_for_load_state("networkidle", timeout=max(1000, render_wait_ms))
                    except PlaywrightTimeoutError:
                        # Keep current DOM snapshot if network-idle is noisy.
                        pass
                    extraction_state = "complete"
                    selectors = ["title", "meta[name='description']", "link[rel='canonical']", "script[type='application/ld+json']"]
                    for selector in selectors:
                        try:
                            await page.wait_for_selector(selector, timeout=max(1000, selector_wait_ms))
                        except PlaywrightTimeoutError:
                            extraction_state = "partial"
                    html = await page.content()
                    response_headers = dict(nav_response.headers) if nav_response else {}
                    await context.close()
                    return html, "rendered_browser", extraction_state, response_headers
                except PlaywrightTimeoutError:
                    html = await page.content()
                    response_headers = dict(nav_response.headers) if "nav_response" in locals() and nav_response else {}
                    await context.close()
                    return html, "rendered_browser", "partial", response_headers
                except PlaywrightError:
                    await context.close()
                    return None, "raw_http", "partial", None
        except Exception:
            return None, "raw_http", "partial", None
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass


def _init_rows(url: str, sitemap_meta: dict[str, dict[str, Any]] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_url = normalize_url_key(url)
    main_data = {"URL": normalized_url, "Extraction State": "skipped", "Extraction Source": "raw_http", "Status Code": None, "Load Time (s)": None, "Indexability": "Indexable", "Title": None, "Title Length": 0, "Meta Description": None, "Meta Desc Length": 0, "Word Count (Body)": 0, "OG-Image": None, "Has Valid JSON-LD": False}
    for i in range(1, 7):
        main_data[f"H{i} Content"] = None
        main_data[f"H{i} Length"] = 0
    extra = {"URL": normalized_url, "Extraction State": "skipped", "Extraction Source": "raw_http", "Status Code": None, "Final URL": None, "Protocol": None, "Redirect Chain Length": 0, "Redirect Target": None, "Redirect Hops": None, "HTTP->HTTPS Redirect": False, "Status Class": None, "TTFB (ms)": None, "Total Request Time (ms)": None, "Content-Type": None, "HTTP Version": None, "HTML Size (KB)": None, "Compression Enabled": False, "Cache-Control": None, "ETag": None, "X-Robots-Tag": None, "Meta Robots Raw": None, "Canonical URL": None, "Canonical Matches Final URL": None, "Canonical Type": None, "Canonical Absolute URL": None, "Canonical in Sitemap Match": None, "Hreflang Present": False, "Hreflang Count": 0, "Hreflang Self Reference": False, "Hreflang Reciprocal Check": None, "Hreflang Canonical Consistency": None, "x-default Present": False, "Pagination rel=next": False, "Pagination rel=prev": False, "H1 Count": 0, "Current H-Tag Structure": None, "Current Page Copy Snippet": None, "Missing H1 Flag": False, "Multiple H1 Flag": False, "Thin Content Flag": False, "Body Text-to-HTML Ratio": None, "Word Count": 0, "Word Count Band": None, "Sentence Count": 0, "Readability (Rough Flesch)": None, "Last-Modified": None, "Published Date": None, "Modified Date": None, "Last Updated": None, "Change Frequency": None, "Priority": None, "Internal Links Count": 0, "External Links Count": 0, "Unique Internal Links Count": 0, "Nofollow Internal Links Count": 0, "Nofollow External Links Count": 0, "Generic Anchor Text Count": 0, "Param URL Flag": "?" in normalized_url, "URL Depth": url_depth(normalized_url), "Image Count": 0, "Images": None, "Images Missing Alt": 0, "Image Alt Coverage (%)": None, "Image Extension Distribution": None, "Likely Large Image Count": 0, "Image Filename Quality Issues": 0, "Image On Canonical Domain (%)": None, "Mixed Content Detected": False, "Schema Types Found": None, "Schema Types Count": 0, "Schema Parse Errors": 0, "Open Graph Complete": False, "Twitter Card Type": None, "OG Title": None, "OG Description": None, "OG Image": None, "Meta Keywords": None, "Strict-Transport-Security": None, "Content-Security-Policy": None, "X-Content-Type-Options": None, "X-Frame-Options": None, "Referrer-Policy": None, "Permissions-Policy": None, "Robots.txt Accessible": None, "Sitemap in Robots.txt": None, "Robots.txt Crawl-Delay": None, "Robots.txt Disallow /": None, "AI Crawlers Allowed (GPTBot/ClaudeBot/PerplexityBot)": None, "llms.txt Present": None, "Title Missing": True, "Meta Description Missing": True, "Indexability Reason": None, "SERP Title Truncation Risk": False, "SERP Meta Truncation Risk": False, "SERP Title Pixel Approx": 0, "SERP Meta Pixel Approx": 0, "Inlinks Bucket": None, "Important But Underlinked": False, "Cannibalization Hint": None, "FAQ Section Count": 0, "Question Heading Count": 0, "HowTo Signal": False, "Definition Signal": False, "List/Table Answer Signal": False, "Paragraphs 40-60 Words Count": 0, "Answer Block Detected (First 60 Words)": False, "AEO Extractability Score": "Low", "Regional Authority Score": 0, "Regional Entity Hits": 0, "CWV LCP (s)": None, "CWV INP (ms)": None, "CWV CLS": None, "CWV Data Source": "Lab", "Field vs Lab": "Lab", "Speakable Schema Present": False, "QAPage/FAQ Schema Present": False, "AEO Readiness Score": 0, "AEO Badge": "Needs Work", "Action Needed": "No", "Owner": None, "Sprint": "", "Status": "Open", "Stable Issue IDs": None, "WordPress Post ID": None, "Internal Links List Full": [], "Internal Links List": [], "Link Details": [], "aeo_snippets": []}
    if sitemap_meta and url in sitemap_meta:
        extra["Change Frequency"] = sitemap_meta[url].get("changefreq")
        extra["Priority"] = sitemap_meta[url].get("priority")
        extra["Last Updated"] = sitemap_meta[url].get("lastmod")
    return main_data, extra


async def fetch_and_parse(
    url: str,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    full_suite: bool = True,
    robots_cache: dict[str, Any] | None = None,
    request_delay: float | None = None,
    sitemap_meta: dict[str, dict[str, Any]] | None = None,
    crawl_mode: str = "fast",
    render_wait_ms: int = 4000,
    selector_wait_ms: int = 3000,
) -> dict[str, dict[str, Any]]:
    async with semaphore:
        start_time = time.time()
        main_data, extra = _init_rows(url, sitemap_meta)
        timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS, sock_read=READ_TIMEOUT_SECONDS)
        completed = False
        for attempt in range(MAX_RETRIES + 1):
            request_start = time.time()
            try:
                async with session.get(url, timeout=timeout) as response:
                    main_data["Load Time (s)"] = round(time.time() - start_time, 3)
                    main_data["Status Code"] = response.status
                    extra["Status Code"] = response.status
                    extra["Final URL"] = normalize_url_key(str(response.url))
                    extra["Protocol"] = urlparse(str(response.url)).scheme
                    parsed_final = urlparse(str(response.url))
                    domain_key = f"{parsed_final.scheme}://{parsed_final.netloc}"
                    extra["Redirect Chain Length"] = len(response.history)
                    extra["Status Class"] = status_class(response.status)
                    extra["TTFB (ms)"] = round((time.time() - request_start) * 1000, 2)
                    extra["Content-Type"] = response.headers.get("Content-Type")
                    extra["HTTP Version"] = f"HTTP/{response.version.major}.{response.version.minor}"
                    extra["Cache-Control"] = response.headers.get("Cache-Control")
                    extra["ETag"] = response.headers.get("ETag")
                    extra["X-Robots-Tag"] = response.headers.get("X-Robots-Tag")
                    extra["Strict-Transport-Security"] = response.headers.get("Strict-Transport-Security")
                    extra["Content-Security-Policy"] = response.headers.get("Content-Security-Policy")
                    extra["X-Content-Type-Options"] = response.headers.get("X-Content-Type-Options")
                    extra["X-Frame-Options"] = response.headers.get("X-Frame-Options")
                    extra["Referrer-Policy"] = response.headers.get("Referrer-Policy")
                    extra["Permissions-Policy"] = response.headers.get("Permissions-Policy")
                    content_encoding = (response.headers.get("Content-Encoding") or "").lower()
                    extra["Compression Enabled"] = any(token in content_encoding for token in ("gzip", "br", "deflate"))
                    if response.history:
                        redirect_targets = [str(h.url) for h in response.history]
                        extra["Redirect Hops"] = " -> ".join(redirect_targets + [str(response.url)])
                        extra["Redirect Target"] = str(response.url)
                        if redirect_targets:
                            first_scheme = urlparse(redirect_targets[0]).scheme.lower()
                            final_scheme = urlparse(str(response.url)).scheme.lower()
                            extra["HTTP->HTTPS Redirect"] = first_scheme == "http" and final_scheme == "https"
                    if robots_cache is not None and domain_key:
                        if domain_key not in robots_cache:
                            llms_present = False
                            ai_allowed = None
                            try:
                                async with session.get(f"{domain_key}/llms.txt", timeout=timeout) as llms_resp:
                                    llms_present = llms_resp.status == 200
                            except Exception:
                                llms_present = False
                            try:
                                async with session.get(f"{domain_key}/robots.txt", timeout=timeout) as robots_resp:
                                    if robots_resp.status == 200:
                                        robots_text = (await robots_resp.text()).lower()
                                        ai_allowed = all(bot.lower() in robots_text for bot in ["gptbot", "claudebot", "perplexitybot"])
                            except Exception:
                                ai_allowed = None
                            robots_cache[domain_key] = {"llms_present": llms_present, "ai_allowed": ai_allowed}
                        extra["llms.txt Present"] = robots_cache.get(domain_key, {}).get("llms_present")
                        extra["AI Crawlers Allowed (GPTBot/ClaudeBot/PerplexityBot)"] = robots_cache.get(domain_key, {}).get("ai_allowed")
                    if response.status in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES:
                        wait_time = min(RETRY_MAX_DELAY_SECONDS, RETRY_BASE_DELAY_SECONDS * (RETRY_BACKOFF_FACTOR ** attempt)) + random.uniform(0, REQUEST_JITTER_SECONDS)
                        logger.warning(
                            "[%s] Retrying %s (attempt %s/%s) in %.1fs",
                            response.status,
                            url,
                            attempt + 2,
                            MAX_RETRIES + 1,
                            wait_time,
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    if response.status == 200 and "text/html" in (response.headers.get("Content-Type", "") or "").lower():
                        html = await response.text()
                        extraction_source = "raw_http"
                        extraction_state_hint = "complete"
                        rendered_headers: dict[str, str] = {}
                        if crawl_mode == "accurate":
                            rendered_html, rendered_source, rendered_state, rendered_headers_raw = await _fetch_rendered_html(
                                url,
                                render_wait_ms=render_wait_ms,
                                selector_wait_ms=selector_wait_ms,
                            )
                            if rendered_html:
                                html = rendered_html
                                extraction_source = rendered_source
                                extraction_state_hint = rendered_state
                                rendered_headers = {str(k).lower(): str(v) for k, v in (rendered_headers_raw or {}).items()}
                            else:
                                extraction_state_hint = "partial"
                        main_data["Extraction Source"] = extraction_source
                        extra["Extraction Source"] = extraction_source
                        if rendered_headers:
                            extra["Cache-Control"] = rendered_headers.get("cache-control", extra["Cache-Control"])
                            extra["ETag"] = rendered_headers.get("etag", extra["ETag"])
                            extra["X-Robots-Tag"] = rendered_headers.get("x-robots-tag", extra["X-Robots-Tag"])
                            extra["Strict-Transport-Security"] = rendered_headers.get("strict-transport-security", extra["Strict-Transport-Security"])
                            extra["Content-Security-Policy"] = rendered_headers.get("content-security-policy", extra["Content-Security-Policy"])
                            extra["X-Content-Type-Options"] = rendered_headers.get("x-content-type-options", extra["X-Content-Type-Options"])
                            extra["X-Frame-Options"] = rendered_headers.get("x-frame-options", extra["X-Frame-Options"])
                            extra["Referrer-Policy"] = rendered_headers.get("referrer-policy", extra["Referrer-Policy"])
                            extra["Permissions-Policy"] = rendered_headers.get("permissions-policy", extra["Permissions-Policy"])
                            rendered_encoding = (rendered_headers.get("content-encoding") or "").lower()
                            if rendered_encoding:
                                extra["Compression Enabled"] = any(token in rendered_encoding for token in ("gzip", "br", "deflate"))
                        extra["Total Request Time (ms)"] = round((time.time() - request_start) * 1000, 2)
                        extra["HTML Size (KB)"] = round(len(html.encode("utf-8")) / 1024, 2)
                        parsed = parse_html_signals(html)
                        soup = BeautifulSoup(html, "lxml")
                        body_classes = " ".join(soup.body.get("class", [])) if soup.body else ""
                        post_id_match = re.search(r"(?:postid|page-id)-(\d+)", body_classes)
                        if post_id_match:
                            extra["WordPress Post ID"] = int(post_id_match.group(1))
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
                        canonical_tag = soup.find("link", attrs={"rel": lambda value: value and "canonical" in str(value).lower()})
                        canonical_raw = (canonical_tag.get("href") or "").strip() if canonical_tag else ""
                        if canonical_raw:
                            canonical_abs = normalize_url_key(urljoin(str(response.url), canonical_raw))
                            extra["Canonical URL"] = canonical_abs
                            extra["Canonical Absolute URL"] = canonical_abs
                            final_norm = normalize_url_key(str(response.url))
                            extra["Canonical Matches Final URL"] = canonical_abs == final_norm
                            extra["Canonical Type"] = "self" if canonical_abs == final_norm else "cross-canonical"
                        else:
                            extra["Canonical Type"] = "missing"
                        meta_robots = soup.find("meta", attrs={"name": lambda v: v and v.lower() == "robots"})
                        meta_robots_raw = (meta_robots.get("content") or "").strip() if meta_robots else None
                        extra["Meta Robots Raw"] = meta_robots_raw
                        main_data["Indexability"] = resolve_indexability_directive(meta_robots_raw, extra.get("X-Robots-Tag"))
                        # Prefer strict OG image meta tags used by social platforms.
                        og_title_meta = soup.find("meta", attrs={"property": "og:title"})
                        og_desc_meta = soup.find("meta", attrs={"property": "og:description"})
                        og_image_meta = soup.find("meta", attrs={"property": "og:image"})
                        twitter_image_meta = soup.find("meta", attrs={"name": "twitter:image"})
                        twitter_card_meta = soup.find("meta", attrs={"name": "twitter:card"})
                        extra["OG Title"] = (og_title_meta.get("content") or "").strip() if og_title_meta else None
                        extra["OG Description"] = (og_desc_meta.get("content") or "").strip() if og_desc_meta else None
                        extra["Twitter Card Type"] = (twitter_card_meta.get("content") or "").strip() if twitter_card_meta else None
                        og_image_url = ""
                        if og_image_meta and (og_image_meta.get("content") or "").strip():
                            og_image_url = og_image_meta.get("content", "").strip()
                        elif twitter_image_meta and (twitter_image_meta.get("content") or "").strip():
                            og_image_url = twitter_image_meta.get("content", "").strip()
                        if og_image_url:
                            extra["OG Image"] = og_image_url
                            main_data["OG-Image"] = og_image_url
                        extra["Open Graph Complete"] = bool(extra["OG Title"] and extra["OG Description"] and extra["OG Image"])
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
                        # 2026 answer-first heuristic: first 60 words should directly answer.
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
                            "africa", "african", "pan-african", "sadc", "ecowas", "east africa", "west africa",
                            "southern africa", "north africa", "kenya", "south africa", "nigeria", "ghana", "zambia",
                            "botswana", "namibia", "uganda", "tanzania", "ethiopia", "rwanda", "angola", "mozambique",
                        ]
                        h_text = " ".join(h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"])).lower()
                        body_text_l = (soup.get_text(" ", strip=True) or "").lower()
                        schema_text_l = " ".join(s.get_text(" ", strip=True) for s in soup.find_all("script", attrs={"type": "application/ld+json"})).lower()
                        regional_hits = sum(1 for term in regional_terms if term in h_text or term in body_text_l or term in schema_text_l)
                        extra["Regional Entity Hits"] = regional_hits
                        extra["Regional Authority Score"] = min(100, regional_hits * 10 + (20 if regional_hits > 0 and any(term in h_text for term in regional_terms) else 0))
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
                        extra["Image Extension Distribution"] = ", ".join(f"{k}:{v}" for k, v in sorted(ext_counts.items())) if ext_counts else None
                        extra["Image Alt Coverage (%)"] = round(((max(0, len(images) - missing_alt) / len(images)) * 100), 2) if images else None

                        schema_summary = parse_jsonld_summary(html)
                        schema_types = schema_summary.get("schema_types") or []
                        extra["Schema Types Found"] = " | ".join(schema_types) if schema_types else None
                        extra["Schema Types Count"] = int(schema_summary.get("schema_types_count") or 0)
                        extra["Schema Parse Errors"] = int(schema_summary.get("schema_parse_errors") or 0)
                        main_data["Has Valid JSON-LD"] = extra["Schema Types Count"] > 0 and extra["Schema Parse Errors"] == 0
                        extra["QAPage/FAQ Schema Present"] = any(t.lower() in {"faqpage", "qapage"} for t in schema_types)
                        extra["Speakable Schema Present"] = any(t.lower() == "speakablespecification" for t in schema_types)

                        source_netloc = urlparse(str(response.url)).netloc.lower()
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
                            target_abs = normalize_url_key(urljoin(str(response.url), href_raw))
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
                                    "Source URL": normalize_url_key(str(response.url)),
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
                    main_data["Extraction State"] = extraction_state_hint if response.status == 200 and "text/html" in (response.headers.get("Content-Type", "") or "").lower() else "partial"
                    extra["Extraction State"] = main_data["Extraction State"]
                    completed = True
                    break
            except asyncio.TimeoutError:
                if attempt < MAX_RETRIES:
                    wait_time = min(RETRY_MAX_DELAY_SECONDS, RETRY_BASE_DELAY_SECONDS * (RETRY_BACKOFF_FACTOR ** attempt)) + random.uniform(0, REQUEST_JITTER_SECONDS)
                    logger.warning(
                        "[Timeout] Retrying %s (attempt %s/%s) in %.1fs",
                        url,
                        attempt + 2,
                        MAX_RETRIES + 1,
                        wait_time,
                    )
                    await asyncio.sleep(wait_time)
                    continue
                main_data["Status Code"] = "Timeout"
                extra["Status Code"] = "Timeout"
                main_data["Extraction State"] = "skipped"
                extra["Extraction State"] = "skipped"
                break
            except aiohttp.ClientError:
                if attempt < MAX_RETRIES:
                    wait_time = min(RETRY_MAX_DELAY_SECONDS, RETRY_BASE_DELAY_SECONDS * (RETRY_BACKOFF_FACTOR ** attempt)) + random.uniform(0, REQUEST_JITTER_SECONDS)
                    logger.warning(
                        "[Connection Error] Retrying %s (attempt %s/%s) in %.1fs",
                        url,
                        attempt + 2,
                        MAX_RETRIES + 1,
                        wait_time,
                    )
                    await asyncio.sleep(wait_time)
                    continue
                main_data["Status Code"] = "Connection Error"
                extra["Status Code"] = "Connection Error"
                main_data["Extraction State"] = "skipped"
                extra["Extraction State"] = "skipped"
                break
            except Exception as e:
                main_data["Status Code"] = f"Error: {str(e)}"
                extra["Status Code"] = f"Error: {str(e)}"
                main_data["Extraction State"] = "skipped"
                extra["Extraction State"] = "skipped"
                break
        if not completed and main_data["Load Time (s)"] is None:
            main_data["Load Time (s)"] = round(time.time() - start_time, 3)
        if extra["Status Class"] is None:
            extra["Status Class"] = status_class(extra["Status Code"])
        status_val = extra["Status Code"]
        status_int = status_val if isinstance(status_val, int) else None
        indexability_reasons = []
        if status_int is not None and status_int >= 400:
            indexability_reasons.append(f"HTTP {status_int}")
        if isinstance(status_val, str) and status_val in {"Timeout", "Connection Error"}:
            indexability_reasons.append(status_val)
        if not indexability_reasons:
            directive_state = resolve_indexability_directive(extra.get("Meta Robots Raw"), extra.get("X-Robots-Tag"))
            indexability_reasons.append("Noindex" if directive_state == "Noindex" else "Indexable")
        extra["Indexability Reason"] = " | ".join(indexability_reasons)
        logger.info("[%s] Crawled: %s", main_data["Status Code"], url)
        delay_seconds = request_delay if request_delay is not None else DELAY_BETWEEN_REQUESTS
        await asyncio.sleep(delay_seconds + random.uniform(0, REQUEST_JITTER_SECONDS))
        return {"main": main_data, "extra": extra}
