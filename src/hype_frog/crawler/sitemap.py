from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

import aiohttp

from hype_frog.core import get_logger

logger = get_logger(__name__)


MAX_SITEMAP_RECURSION_DEPTH = 3


async def _fetch_sitemap_xml(url: str, session: aiohttp.ClientSession) -> str:
    timeout = aiohttp.ClientTimeout(total=10)
    async with session.get(url, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
        return await response.text()


def _strip_default_namespace(xml_data: str) -> ET.Element:
    sanitized = re.sub(r'\sxmlns="[^"]+"', "", xml_data, count=1)
    return ET.fromstring(sanitized)


def _detect_sitemap_kind(root: ET.Element, xml_data: str) -> str:
    tag = str(root.tag or "").lower()
    if tag.endswith("sitemapindex"):
        return "sitemapindex"
    lowered = xml_data.lower()
    if "image:image" in lowered or root.find(".//image") is not None:
        return "image"
    if "video:video" in lowered or root.find(".//video") is not None:
        return "video"
    return "urlset"


async def parse_sitemap(
    url: str, session: aiohttp.ClientSession
) -> tuple[list[str], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Return discovered URLs, per-URL metadata, and per-sitemap-file metadata."""
    logger.info("Fetching sitemap from: %s", url)
    visited_sitemaps: set[str] = set()
    discovered_urls: list[str] = []
    seen_page_urls: set[str] = set()
    sitemap_meta: dict[str, dict[str, Any]] = {}
    sitemap_files_meta: dict[str, dict[str, Any]] = {}

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
            logger.warning("Skipping sitemap %s (%s)", sitemap_key, exc)
            return

        kind = _detect_sitemap_kind(root, xml_data)
        file_url_count = 0

        if root.tag.endswith("sitemapindex") or kind == "sitemapindex":
            sitemap_files_meta[sitemap_key] = {
                "kind": "sitemapindex",
                "url_count": len(root.findall("./sitemap")),
                "size_bytes": len(xml_data.encode("utf-8")),
                "is_index": True,
            }
            for sm_node in root.findall("./sitemap"):
                child_loc = sm_node.findtext("loc")
                if child_loc and child_loc.strip():
                    await _walk(child_loc.strip(), depth + 1)
            return

        for url_node in root.findall("./url"):
            loc_node = url_node.find("loc")
            if loc_node is None or not loc_node.text:
                continue
            page_url = loc_node.text.strip()
            if not page_url:
                continue
            file_url_count += 1
            if page_url not in seen_page_urls:
                seen_page_urls.add(page_url)
                discovered_urls.append(page_url)
            if page_url not in sitemap_meta:
                sitemap_meta[page_url] = {
                    "changefreq": (
                        url_node.findtext("changefreq").strip()
                        if url_node.findtext("changefreq")
                        else None
                    ),
                    "priority": (
                        url_node.findtext("priority").strip()
                        if url_node.findtext("priority")
                        else None
                    ),
                    "lastmod": (
                        url_node.findtext("lastmod").strip()
                        if url_node.findtext("lastmod")
                        else None
                    ),
                    "source_sitemap": sitemap_key,
                    "sitemap_kind": kind,
                }

        sitemap_files_meta[sitemap_key] = {
            "kind": kind,
            "url_count": file_url_count,
            "size_bytes": len(xml_data.encode("utf-8")),
            "is_index": False,
        }

    try:
        await _walk(url, depth=0)
        urls = list(discovered_urls)
        logger.info(
            "Found %s URLs across %s sitemap file(s).",
            len(urls),
            len(visited_sitemaps),
        )
        return urls, sitemap_meta, sitemap_files_meta
    except Exception as e:
        logger.warning("Error parsing sitemap: %s", e)
        return [], {}, {}
