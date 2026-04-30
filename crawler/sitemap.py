from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

import aiohttp


async def parse_sitemap(url: str, session: aiohttp.ClientSession) -> tuple[list[str], dict[str, dict[str, Any]]]:
    print(f"Fetching sitemap from: {url}")
    try:
        async with session.get(url) as response:
            if response.status != 200:
                print("Failed to retrieve sitemap.")
                return [], {}
            xml_data = await response.text()
            xml_data = re.sub(r'\sxmlns="[^"]+"', "", xml_data, count=1)
            root = ET.fromstring(xml_data)
            urls: list[str] = []
            sitemap_meta: dict[str, dict[str, Any]] = {}
            for url_node in root.findall(".//url"):
                loc_node = url_node.find("loc")
                if loc_node is None or not loc_node.text:
                    continue
                page_url = loc_node.text.strip()
                urls.append(page_url)
                sitemap_meta[page_url] = {
                    "changefreq": url_node.findtext("changefreq").strip() if url_node.findtext("changefreq") else None,
                    "priority": url_node.findtext("priority").strip() if url_node.findtext("priority") else None,
                    "lastmod": url_node.findtext("lastmod").strip() if url_node.findtext("lastmod") else None,
                }
            if not urls:
                urls = [loc.text.strip() for loc in root.findall(".//loc") if loc.text]
            print(f"Found {len(urls)} URLs in sitemap.")
            return urls, sitemap_meta
    except Exception as e:
        print(f"Error parsing sitemap: {e}")
        return [], {}
