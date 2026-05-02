from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

import aiohttp


MAX_SITEMAP_RECURSION_DEPTH = 3


async def _fetch_sitemap_xml(url: str, session: aiohttp.ClientSession) -> str:
    async with session.get(url) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
        return await response.text()


def _strip_default_namespace(xml_data: str) -> ET.Element:
    sanitized = re.sub(r'\sxmlns="[^"]+"', "", xml_data, count=1)
    return ET.fromstring(sanitized)


async def parse_sitemap(url: str, session: aiohttp.ClientSession) -> tuple[list[str], dict[str, dict[str, Any]]]:
    print(f"Fetching sitemap from: {url}")
    visited_sitemaps: set[str] = set()
    discovered_urls: set[str] = set()
    sitemap_meta: dict[str, dict[str, Any]] = {}

    async def _walk(sitemap_url: str, depth: int) -> None:
        if depth > MAX_SITEMAP_RECURSION_DEPTH:
            return
        sitemap_key = str(sitemap_url or "").strip()
        if not sitemap_key or sitemap_key in visited_sitemaps:
            return
        visited_sitemaps.add(sitemap_key)

        try:
            xml_data = await _fetch_sitemap_xml(sitemap_key, session)
            root = _strip_default_namespace(xml_data)
        except Exception as exc:
            print(f"Skipping sitemap {sitemap_key} ({exc})")
            return

        # Nested sitemap index: recurse into child sitemaps.
        if root.tag == "sitemapindex":
            for sm_node in root.findall("./sitemap"):
                child_loc = sm_node.findtext("loc")
                if child_loc and child_loc.strip():
                    await _walk(child_loc.strip(), depth + 1)
            return

        # Standard URL set.
        for url_node in root.findall("./url"):
            loc_node = url_node.find("loc")
            if loc_node is None or not loc_node.text:
                continue
            page_url = loc_node.text.strip()
            if not page_url:
                continue
            discovered_urls.add(page_url)
            if page_url not in sitemap_meta:
                sitemap_meta[page_url] = {
                    "changefreq": url_node.findtext("changefreq").strip() if url_node.findtext("changefreq") else None,
                    "priority": url_node.findtext("priority").strip() if url_node.findtext("priority") else None,
                    "lastmod": url_node.findtext("lastmod").strip() if url_node.findtext("lastmod") else None,
                    "source_sitemap": sitemap_key,
                }

    try:
        await _walk(url, depth=0)
        urls = sorted(discovered_urls)
        print(
            f"Found {len(urls)} URLs across {len(visited_sitemaps)} sitemap file(s)."
        )
        return urls, sitemap_meta
    except Exception as e:
        print(f"Error parsing sitemap: {e}")
        return [], {}
