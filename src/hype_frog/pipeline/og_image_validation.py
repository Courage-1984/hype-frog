"""Optional post-crawl OG image HTTP status and dimension checks."""

from __future__ import annotations

import asyncio
import struct
from typing import Any

import aiohttp

from hype_frog.config import CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS, TIMEOUT_SECONDS
from hype_frog.core import get_logger
from hype_frog.core.models import ExtraRowPayload
from hype_frog.core.status_codes import is_success_status
from hype_frog.extractors.og_social import og_image_dimensions_ok
from hype_frog.pipeline.og_image_consistency import resolve_og_image_url

_MAX_IMAGE_BYTES = 65_536
logger = get_logger(__name__)


def read_image_dimensions(data: bytes) -> tuple[int, int] | None:
    """Read width/height from PNG, JPEG, or WebP header bytes."""
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
        width, height = struct.unpack(">II", data[16:24])
        return int(width), int(height)

    if len(data) >= 2 and data[:2] == b"\xff\xd8":
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            if marker in {0xC0, 0xC1, 0xC2, 0xC3}:
                height, width = struct.unpack(">HH", data[index + 5 : index + 9])
                return int(width), int(height)
            if marker in {0xD8, 0xD9}:
                break
            if index + 4 > len(data):
                break
            segment_len = struct.unpack(">H", data[index + 2 : index + 4])[0]
            index += 2 + segment_len

    if len(data) >= 30 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        if data[12:16] == b"VP8X" and len(data) >= 30:
            width = 1 + struct.unpack("<I", data[24:27] + b"\x00")[0]
            height = 1 + struct.unpack("<I", data[27:30] + b"\x00")[0]
            return int(width), int(height)
        if data[12:16] == b"VP8 " and len(data) >= 30:
            width, height = struct.unpack("<HH", data[26:30])
            return int(width & 0x3FFF), int(height & 0x3FFF)

    return None


async def _fetch_og_image_probe(
    session: aiohttp.ClientSession,
    url: str,
    semaphore: asyncio.Semaphore,
) -> tuple[int | None, int | None, int | None]:
    timeout = aiohttp.ClientTimeout(
        total=min(TIMEOUT_SECONDS, 15),
        connect=min(CONNECT_TIMEOUT_SECONDS, 6),
        sock_read=min(READ_TIMEOUT_SECONDS, 12),
    )
    async with semaphore:
        try:
            async with session.get(url, timeout=timeout, allow_redirects=True) as resp:
                status = resp.status
                if not is_success_status(status):
                    return status, None, None
                chunk = await resp.content.read(_MAX_IMAGE_BYTES)
                dims = read_image_dimensions(chunk)
                if dims:
                    return status, dims[0], dims[1]
                return status, None, None
        except Exception:
            logger.debug("og_image_probe_failed", url=url, exc_info=True)
            return None, None, None


async def enrich_og_image_validation(
    session: aiohttp.ClientSession,
    extra_rows: list[ExtraRowPayload],
    *,
    workers: int,
) -> None:
    """Populate OG Image OK / width / height on rows that declare an OG image."""
    targets: list[tuple[int, str]] = []
    for index, row in enumerate(extra_rows):
        row_values = row.values
        main_stub = {"OG-Image": row_values.get("OG Image URL") or row_values.get("OG Image")}
        image_url = resolve_og_image_url(main_stub, row_values)
        if image_url:
            targets.append((index, str(image_url)))

    if not targets:
        return

    semaphore = asyncio.Semaphore(min(20, max(5, workers * 3)))
    results = await asyncio.gather(
        *[_fetch_og_image_probe(session, url, semaphore) for _, url in targets]
    )

    for (index, _url), (status, width, height) in zip(targets, results):
        row_values = extra_rows[index].values
        if status is None:
            row_values["OG Image OK"] = False
        else:
            row_values["OG Image OK"] = is_success_status(status)
        if width is not None and height is not None:
            row_values["OG Image Width"] = width
            row_values["OG Image Height"] = height
            row_values["OG Image Dimensions OK"] = og_image_dimensions_ok(width, height)


def og_image_validation_summary(extra_rows: list[ExtraRowPayload]) -> dict[str, Any]:
    checked = sum(1 for row in extra_rows if row.values.get("OG Image OK") is not None)
    broken = sum(1 for row in extra_rows if row.values.get("OG Image OK") is False)
    wrong_dims = sum(
        1
        for row in extra_rows
        if row.values.get("OG Image Width") is not None
        and row.values.get("OG Image Dimensions OK") is False
    )
    return {"checked": checked, "broken": broken, "wrong_dimensions": wrong_dims}
