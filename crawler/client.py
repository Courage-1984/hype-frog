from __future__ import annotations

import aiohttp


def create_session() -> aiohttp.ClientSession:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Technical-SEO-Auditor/1.0"
    }
    return aiohttp.ClientSession(headers=headers)
