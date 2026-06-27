"""Async light URL status checks."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from hype_frog.crawler.link_checks import check_url_status_light, check_url_status_light_limited


def _mock_response(status: int) -> MagicMock:
    response = MagicMock()
    response.status = status
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    return response


@pytest.mark.asyncio
async def test_check_url_status_light_uses_head_response() -> None:
    session = MagicMock()
    session.head = MagicMock(return_value=_mock_response(200))
    session.get = MagicMock()

    status = await check_url_status_light(session, "https://example.com/")

    assert status == 200
    session.head.assert_called_once()
    session.get.assert_not_called()


@pytest.mark.asyncio
async def test_check_url_status_light_falls_back_to_get() -> None:
    session = MagicMock()
    session.head = MagicMock(side_effect=RuntimeError("HEAD blocked"))
    session.get = MagicMock(return_value=_mock_response(301))

    status = await check_url_status_light(session, "https://example.com/redirect")

    assert status == 301
    session.get.assert_called_once()


@pytest.mark.asyncio
async def test_check_url_status_light_returns_none_on_total_failure() -> None:
    session = MagicMock()
    session.head = MagicMock(side_effect=RuntimeError("HEAD blocked"))
    session.get = MagicMock(side_effect=RuntimeError("GET blocked"))

    status = await check_url_status_light(session, "https://example.com/down")

    assert status is None


@pytest.mark.asyncio
async def test_check_url_status_light_limited_respects_semaphore() -> None:
    session = MagicMock()
    session.head = MagicMock(return_value=_mock_response(200))
    semaphore = AsyncMock()
    semaphore.__aenter__ = AsyncMock(return_value=None)
    semaphore.__aexit__ = AsyncMock(return_value=None)

    status = await check_url_status_light_limited(session, "https://example.com/", semaphore)

    assert status == 200
    semaphore.__aenter__.assert_awaited_once()
