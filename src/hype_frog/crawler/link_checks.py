from __future__ import annotations

import asyncio

import aiohttp

from hype_frog.config import CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS, TIMEOUT_SECONDS
from hype_frog.core import get_logger

logger = get_logger(__name__)


async def check_url_status_light(
    session: aiohttp.ClientSession,
    url: str,
    *,
    timeout_seconds: float | None = None,
) -> int | None:
    total_cap = min(timeout_seconds or TIMEOUT_SECONDS, 12)
    connect_cap = min(CONNECT_TIMEOUT_SECONDS, 6, total_cap)
    read_cap = min(READ_TIMEOUT_SECONDS, 10, total_cap)
    timeout = aiohttp.ClientTimeout(
        total=total_cap,
        connect=connect_cap,
        sock_read=read_cap,
    )
    try:
        async with session.head(url, timeout=timeout, allow_redirects=True) as resp:
            return resp.status
    except Exception as exc:
        logger.debug("HEAD %r failed, falling back to GET: %s", url, exc)
        try:
            async with session.get(url, timeout=timeout, allow_redirects=True) as resp:
                return resp.status
        except Exception as exc2:
            logger.debug("GET %r also failed: %s", url, exc2)
            return None


async def check_url_status_light_limited(
    session: aiohttp.ClientSession,
    url: str,
    semaphore: asyncio.Semaphore,
    *,
    timeout_seconds: float | None = None,
) -> int | None:
    async with semaphore:
        return await check_url_status_light(session, url, timeout_seconds=timeout_seconds)
