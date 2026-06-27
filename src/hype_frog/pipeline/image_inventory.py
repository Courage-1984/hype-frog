"""Content image validation, inventory, and per-page broken/oversized analysis (A4)."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any
from urllib.parse import urlparse

import aiohttp

from hype_frog.config import CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS, TIMEOUT_SECONDS
from hype_frog.config_defaults import get_large_image_size_kb
from hype_frog.core import get_logger
from hype_frog.core.models import ExtraRowPayload
from hype_frog.core.status_codes import is_success_status
from hype_frog.core.text_utils import image_extension
from hype_frog.pipeline.og_image_validation import read_image_dimensions

_MAX_IMAGE_BYTES = 65_536
logger = get_logger(__name__)

IMAGE_INVENTORY_COLUMNS: tuple[str, ...] = (
    "Image URL",
    "Status Code",
    "Size (KB)",
    "Width",
    "Height",
    "Is Broken",
    "Is Oversized",
    "Alt Text",
    "File Extension",
    "Found On Pages",
    "Found On Pages (first 5)",
)


def _normalise_images(raw: object) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in raw:
        if isinstance(item, dict):
            url = str(item.get("url") or "").strip()
            alt = str(item.get("alt") or "").strip()
        else:
            url = str(item or "").strip()
            alt = ""
        if url:
            out.append({"url": url, "alt": alt})
    return out


def _content_images_for_row(row: dict[str, Any]) -> list[dict[str, str]]:
    """Prefer structured ``Content Images``; fall back to pipe-delimited ``Images``."""
    images = _normalise_images(row.get("Content Images"))
    if images:
        return images
    raw = row.get("Images")
    if not raw:
        return []
    return [
        {"url": part.strip(), "alt": ""}
        for part in str(raw).split("|")
        if part.strip()
    ]


async def _probe_image(
    session: aiohttp.ClientSession,
    url: str,
    semaphore: asyncio.Semaphore,
) -> dict[str, Any]:
    timeout = aiohttp.ClientTimeout(
        total=min(TIMEOUT_SECONDS, 15),
        connect=min(CONNECT_TIMEOUT_SECONDS, 6),
        sock_read=min(READ_TIMEOUT_SECONDS, 12),
    )
    result: dict[str, Any] = {
        "status_code": None,
        "size_kb": None,
        "width": None,
        "height": None,
        "broken": True,
        "oversized": False,
    }
    async with semaphore:
        try:
            async with session.head(url, timeout=timeout, allow_redirects=True) as head_resp:
                status = head_resp.status
                result["status_code"] = status
                length = head_resp.headers.get("Content-Length")
                if length:
                    try:
                        result["size_kb"] = round(float(length) / 1024.0, 2)
                    except (TypeError, ValueError):
                        pass
                if not is_success_status(status):
                    return result
        except Exception as exc:
            logger.debug("Image probe HEAD failed %r: %s", url, exc)
            return result

        try:
            async with session.get(url, timeout=timeout, allow_redirects=True) as resp:
                result["status_code"] = resp.status
                if not is_success_status(resp.status):
                    return result
                chunk = await resp.content.read(_MAX_IMAGE_BYTES)
                result["size_kb"] = round(len(chunk) / 1024.0, 2)
                dims = read_image_dimensions(chunk)
                if dims:
                    result["width"], result["height"] = dims
                else:
                    result["broken"] = True
                    return result
        except Exception as exc:
            logger.debug("Image probe GET failed %r: %s", url, exc)
            return result

    large_kb = get_large_image_size_kb()
    result["broken"] = not is_success_status(result["status_code"])
    if result["size_kb"] is not None and result["size_kb"] > large_kb:
        result["oversized"] = True
    if is_success_status(result["status_code"]) and result["width"]:
        result["broken"] = False
    return result


async def enrich_content_image_inventory(
    session: aiohttp.ClientSession,
    extra_rows: list[ExtraRowPayload],
    *,
    workers: int,
) -> dict[str, dict[str, Any]]:
    """Probe unique content images; mutate per-page broken/oversized columns."""
    page_images: list[tuple[int, dict[str, str]]] = []
    for index, row in enumerate(extra_rows):
        for image in _content_images_for_row(row.values):
            page_images.append((index, image))

    unique_urls = sorted({image["url"] for _, image in page_images})
    if not unique_urls:
        for row in extra_rows:
            row.values.setdefault("Broken Image Count", 0)
            row.values.setdefault("Large Image Count", 0)
            row.values.setdefault("Has Broken Images", False)
        return {}

    semaphore = asyncio.Semaphore(min(20, max(5, workers * 3)))
    probes = await asyncio.gather(
        *[_probe_image(session, url, semaphore) for url in unique_urls]
    )
    probe_by_url = dict(zip(unique_urls, probes, strict=True))

    for row in extra_rows:
        values = row.values
        page_url = str(values.get("URL") or "")
        broken_urls: list[str] = []
        oversized_urls: list[str] = []
        for image in _content_images_for_row(values):
            probe = probe_by_url.get(image["url"], {})
            if probe.get("broken"):
                broken_urls.append(image["url"])
            if probe.get("oversized"):
                oversized_urls.append(image["url"])
        values["Broken Image Count"] = len(broken_urls)
        values["Large Image Count"] = len(oversized_urls)
        values["Has Broken Images"] = bool(broken_urls)
        values["Broken Image URLs"] = " | ".join(broken_urls[:3]) if broken_urls else None
        values["Oversized Image URLs"] = (
            " | ".join(oversized_urls[:3]) if oversized_urls else None
        )

    return probe_by_url


def build_image_inventory_rows(
    extra_rows: list[dict[str, Any]],
    probe_by_url: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    site_index: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"pages": set(), "alt": ""}
    )
    for row in extra_rows:
        page_url = str(row.get("URL") or "").strip()
        for image in _content_images_for_row(row):
            url = image["url"]
            entry = site_index[url]
            if page_url:
                entry["pages"].add(page_url)
            if image["alt"] and not entry["alt"]:
                entry["alt"] = image["alt"]

    rows: list[dict[str, Any]] = []
    for url, data in sorted(site_index.items()):
        probe = probe_by_url.get(url, {})
        pages = sorted(data.get("pages") or [])
        ext = image_extension(url)
        status = probe.get("status_code")
        rows.append(
            {
                "Image URL": url,
                "Status Code": status if status is not None else "",
                "Size (KB)": probe.get("size_kb"),
                "Width": probe.get("width"),
                "Height": probe.get("height"),
                "Is Broken": bool(probe.get("broken")),
                "Is Oversized": bool(probe.get("oversized")),
                "Alt Text": data.get("alt") or "",
                "File Extension": ext,
                "Found On Pages": len(pages),
                "Found On Pages (first 5)": " | ".join(pages[:5]),
            }
        )
    rows.sort(key=lambda item: (-int(item.get("Found On Pages") or 0), str(item["Image URL"])))
    return rows
