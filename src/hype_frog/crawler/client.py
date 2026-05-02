from __future__ import annotations

import aiohttp
from hype_frog.config import (
    HTTP_CONNECTOR_KEEPALIVE_TIMEOUT,
    HTTP_CONNECTOR_LIMIT,
    HTTP_CONNECTOR_LIMIT_PER_HOST,
)


def create_session() -> aiohttp.ClientSession:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Technical-SEO-Auditor/1.0"
    }
    connector = aiohttp.TCPConnector(
        limit=HTTP_CONNECTOR_LIMIT,
        limit_per_host=HTTP_CONNECTOR_LIMIT_PER_HOST,
        keepalive_timeout=HTTP_CONNECTOR_KEEPALIVE_TIMEOUT,
    )
    return aiohttp.ClientSession(headers=headers, connector=connector)
