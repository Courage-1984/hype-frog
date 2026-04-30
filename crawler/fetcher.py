from __future__ import annotations

import asyncio
import random
import time
from collections import defaultdict
from typing import Any
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup

from config import (
    CONNECT_TIMEOUT_SECONDS,
    DELAY_BETWEEN_REQUESTS,
    MAX_RETRIES,
    READ_TIMEOUT_SECONDS,
    REQUEST_JITTER_SECONDS,
    RETRY_BACKOFF_FACTOR,
    RETRY_BASE_DELAY_SECONDS,
    RETRY_MAX_DELAY_SECONDS,
    RETRYABLE_STATUS_CODES,
    TIMEOUT_SECONDS,
)
from extractors import extract_aeo_snippets, parse_html_signals
from utils import image_extension, looks_generic_image_filename, readability_flesch, status_class, url_depth, word_count_band


def _init_rows(url: str, sitemap_meta: dict[str, dict[str, Any]] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    main_data = {"URL": url, "Status Code": None, "Load Time (s)": None, "Indexability": "Indexable", "Title": None, "Title Length": 0, "Meta Description": None, "Meta Desc Length": 0, "Word Count (Body)": 0, "OG-Image": None, "Has Valid JSON-LD": False}
    for i in range(1, 7):
        main_data[f"H{i} Content"] = None
        main_data[f"H{i} Length"] = 0
    extra = {"URL": url, "Status Code": None, "Final URL": None, "Protocol": None, "Redirect Chain Length": 0, "Redirect Target": None, "Redirect Hops": None, "HTTP->HTTPS Redirect": False, "Status Class": None, "TTFB (ms)": None, "Total Request Time (ms)": None, "Content-Type": None, "HTTP Version": None, "HTML Size (KB)": None, "Compression Enabled": False, "Cache-Control": None, "ETag": None, "X-Robots-Tag": None, "Meta Robots Raw": None, "Canonical URL": None, "Canonical Matches Final URL": None, "Canonical Type": None, "Canonical Absolute URL": None, "Canonical in Sitemap Match": None, "Hreflang Present": False, "Hreflang Count": 0, "Hreflang Self Reference": False, "Hreflang Reciprocal Check": None, "Hreflang Canonical Consistency": None, "x-default Present": False, "Pagination rel=next": False, "Pagination rel=prev": False, "H1 Count": 0, "Missing H1 Flag": False, "Multiple H1 Flag": False, "Thin Content Flag": False, "Body Text-to-HTML Ratio": None, "Word Count": 0, "Word Count Band": None, "Sentence Count": 0, "Readability (Rough Flesch)": None, "Last-Modified": None, "Published Date": None, "Modified Date": None, "Last Updated": None, "Change Frequency": None, "Priority": None, "Internal Links Count": 0, "External Links Count": 0, "Unique Internal Links Count": 0, "Nofollow Internal Links Count": 0, "Nofollow External Links Count": 0, "Generic Anchor Text Count": 0, "Param URL Flag": "?" in url, "URL Depth": url_depth(url), "Image Count": 0, "Images": None, "Images Missing Alt": 0, "Image Alt Coverage (%)": None, "Image Extension Distribution": None, "Likely Large Image Count": 0, "Image Filename Quality Issues": 0, "Image On Canonical Domain (%)": None, "Mixed Content Detected": False, "Schema Types Found": None, "Schema Types Count": 0, "Schema Parse Errors": 0, "Open Graph Complete": False, "Twitter Card Type": None, "OG Title": None, "OG Description": None, "OG Image": None, "Strict-Transport-Security": None, "Content-Security-Policy": None, "X-Content-Type-Options": None, "X-Frame-Options": None, "Referrer-Policy": None, "Permissions-Policy": None, "Robots.txt Accessible": None, "Sitemap in Robots.txt": None, "Robots.txt Crawl-Delay": None, "Robots.txt Disallow /": None, "Title Missing": True, "Meta Description Missing": True, "Indexability Reason": None, "SERP Title Truncation Risk": False, "SERP Meta Truncation Risk": False, "SERP Title Pixel Approx": 0, "SERP Meta Pixel Approx": 0, "Inlinks Bucket": None, "Important But Underlinked": False, "Cannibalization Hint": None, "FAQ Section Count": 0, "Question Heading Count": 0, "HowTo Signal": False, "Definition Signal": False, "List/Table Answer Signal": False, "Paragraphs 40-60 Words Count": 0, "Speakable Schema Present": False, "QAPage/FAQ Schema Present": False, "AEO Readiness Score": 0, "AEO Badge": "Needs Work", "Action Needed": "No", "Owner": None, "Sprint": "", "Status": "Open", "Stable Issue IDs": None, "Internal Links List Full": [], "Internal Links List": [], "Link Details": [], "aeo_snippets": []}
    if sitemap_meta and url in sitemap_meta:
        extra["Change Frequency"] = sitemap_meta[url].get("changefreq")
        extra["Priority"] = sitemap_meta[url].get("priority")
        extra["Last Updated"] = sitemap_meta[url].get("lastmod")
    return main_data, extra


async def fetch_and_parse(url: str, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore, full_suite: bool = True, robots_cache: dict[str, Any] | None = None, request_delay: float | None = None, sitemap_meta: dict[str, dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
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
                    extra["Final URL"] = str(response.url)
                    extra["Protocol"] = urlparse(str(response.url)).scheme
                    extra["Redirect Chain Length"] = len(response.history)
                    extra["Status Class"] = status_class(response.status)
                    extra["TTFB (ms)"] = round((time.time() - request_start) * 1000, 2)
                    extra["Content-Type"] = response.headers.get("Content-Type")
                    extra["HTTP Version"] = f"HTTP/{response.version.major}.{response.version.minor}"
                    if response.status in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES:
                        wait_time = min(RETRY_MAX_DELAY_SECONDS, RETRY_BASE_DELAY_SECONDS * (RETRY_BACKOFF_FACTOR ** attempt)) + random.uniform(0, REQUEST_JITTER_SECONDS)
                        print(f"[{response.status}] Retrying {url} (attempt {attempt + 2}/{MAX_RETRIES + 1}) in {wait_time:.1f}s")
                        await asyncio.sleep(wait_time)
                        continue
                    if response.status == 200 and "text/html" in response.headers.get("Content-Type", ""):
                        html = await response.text()
                        extra["Total Request Time (ms)"] = round((time.time() - request_start) * 1000, 2)
                        extra["HTML Size (KB)"] = round(len(html.encode("utf-8")) / 1024, 2)
                        parsed = parse_html_signals(html)
                        soup = BeautifulSoup(html, "lxml")
                        if parsed.get("title"):
                            title_text = str(parsed["title"])
                            main_data["Title"] = title_text
                            main_data["Title Length"] = len(title_text)
                            extra["Title Missing"] = False
                            extra["SERP Title Pixel Approx"] = int(len(title_text) * 7.2)
                        if parsed.get("meta_description"):
                            desc_text = str(parsed["meta_description"])
                            main_data["Meta Description"] = desc_text
                            main_data["Meta Desc Length"] = len(desc_text)
                            extra["Meta Description Missing"] = False
                            extra["SERP Meta Pixel Approx"] = int(len(desc_text) * 6.2)
                        extra["H1 Count"] = int(parsed.get("h1_count") or 0)
                        extra["Missing H1 Flag"] = extra["H1 Count"] == 0
                        extra["Multiple H1 Flag"] = extra["H1 Count"] > 1
                        if soup.body:
                            body_text = soup.body.get_text(separator=" ", strip=True)
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
                    completed = True
                    break
            except asyncio.TimeoutError:
                if attempt < MAX_RETRIES:
                    wait_time = min(RETRY_MAX_DELAY_SECONDS, RETRY_BASE_DELAY_SECONDS * (RETRY_BACKOFF_FACTOR ** attempt)) + random.uniform(0, REQUEST_JITTER_SECONDS)
                    print(f"[Timeout] Retrying {url} (attempt {attempt + 2}/{MAX_RETRIES + 1}) in {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    continue
                main_data["Status Code"] = "Timeout"
                extra["Status Code"] = "Timeout"
                break
            except aiohttp.ClientError:
                if attempt < MAX_RETRIES:
                    wait_time = min(RETRY_MAX_DELAY_SECONDS, RETRY_BASE_DELAY_SECONDS * (RETRY_BACKOFF_FACTOR ** attempt)) + random.uniform(0, REQUEST_JITTER_SECONDS)
                    print(f"[Connection Error] Retrying {url} (attempt {attempt + 2}/{MAX_RETRIES + 1}) in {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    continue
                main_data["Status Code"] = "Connection Error"
                extra["Status Code"] = "Connection Error"
                break
            except Exception as e:
                main_data["Status Code"] = f"Error: {str(e)}"
                extra["Status Code"] = f"Error: {str(e)}"
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
            indexability_reasons.append("Indexable")
        extra["Indexability Reason"] = " | ".join(indexability_reasons)
        print(f"[{main_data['Status Code']}] Crawled: {url}")
        delay_seconds = request_delay if request_delay is not None else DELAY_BETWEEN_REQUESTS
        await asyncio.sleep(delay_seconds + random.uniform(0, REQUEST_JITTER_SECONDS))
        return {"main": main_data, "extra": extra}
