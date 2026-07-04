"""Tests for `crawler/client.py::create_session` — the real (non-monkeypatched) session builder.

`create_session` is live code, imported through `hype_frog.crawler.__init__`
and used directly in `crawl_runner.py`'s BFS loop — it is NOT dead code.
Every existing test that touches the crawl loop monkeypatches it away
entirely, so its real behavior (the User-Agent header, TCPConnector
limit/keepalive settings) was never exercised.
"""

from __future__ import annotations

import pytest

from hype_frog.config import (
    HTTP_CONNECTOR_KEEPALIVE_TIMEOUT,
    HTTP_CONNECTOR_LIMIT,
    HTTP_CONNECTOR_LIMIT_PER_HOST,
)
from hype_frog.crawler.client import create_session


@pytest.mark.asyncio
async def test_create_session_sets_expected_user_agent_header() -> None:
    session = create_session()
    try:
        assert "User-Agent" in session.headers
        assert "Technical-SEO-Auditor" in session.headers["User-Agent"]
        assert "Mozilla/5.0" in session.headers["User-Agent"]
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_create_session_configures_connector_limits_from_config() -> None:
    session = create_session()
    try:
        connector = session.connector
        assert connector.limit == HTTP_CONNECTOR_LIMIT
        assert connector.limit_per_host == HTTP_CONNECTOR_LIMIT_PER_HOST
        assert connector._keepalive_timeout == HTTP_CONNECTOR_KEEPALIVE_TIMEOUT
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_create_session_returns_a_usable_open_session() -> None:
    session = create_session()
    try:
        assert session.closed is False
    finally:
        await session.close()
    assert session.closed is True


@pytest.mark.asyncio
async def test_create_session_is_importable_via_crawler_package_facade() -> None:
    from hype_frog.crawler import create_session as facade_create_session

    assert facade_create_session is create_session
