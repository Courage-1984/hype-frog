"""Extraction source consistency helpers in the HTTP/render fetch path."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from hype_frog.crawler.fetcher import _fetch_render_with_retries
from hype_frog.crawler.network_engine import RenderedFetchDiagnostics


def _diag(*, html: str | None, source: str = "rendered_browser") -> RenderedFetchDiagnostics:
    return RenderedFetchDiagnostics(
        html=html,
        raw_html=None,
        extraction_source=source,
        extraction_state="complete" if html else "partial",
        response_headers={},
        field_lcp_ms=None,
        field_cls=None,
        raw_word_count=0,
        rendered_word_count=0,
        is_js_dependent=False,
    )


@pytest.mark.asyncio
async def test_fetch_render_with_retries_uses_primary_url_first() -> None:
    calls: list[str] = []

    async def fake_fetch(
        render_url: str,
        *,
        render_wait_ms: int,
        selector_wait_ms: int,
        playwright_session_manager: object | None,
    ) -> RenderedFetchDiagnostics:
        del render_wait_ms, selector_wait_ms, playwright_session_manager
        calls.append(render_url)
        if render_url.endswith("/final"):
            return _diag(html="<html>ok</html>")
        return _diag(html=None)

    with patch("hype_frog.crawler.fetcher._fetch_render_diagnostics", side_effect=fake_fetch):
        result = await _fetch_render_with_retries(
            primary_url="https://example.com/final",
            fallback_url="https://example.com/start",
            render_wait_ms=4000,
            selector_wait_ms=3000,
            playwright_session_manager=None,
        )

    assert result["html"] == "<html>ok</html>"
    assert calls[0] == "https://example.com/final"


@pytest.mark.asyncio
async def test_fetch_render_with_retries_falls_back_to_seed_url() -> None:
    calls: list[str] = []

    async def fake_fetch(
        render_url: str,
        *,
        render_wait_ms: int,
        selector_wait_ms: int,
        playwright_session_manager: object | None,
    ) -> RenderedFetchDiagnostics:
        del render_wait_ms, selector_wait_ms, playwright_session_manager
        calls.append(render_url)
        if render_url == "https://example.com/start":
            return _diag(html="<html>seed</html>")
        return _diag(html=None)

    with patch("hype_frog.crawler.fetcher._fetch_render_diagnostics", side_effect=fake_fetch):
        result = await _fetch_render_with_retries(
            primary_url="https://example.com/final",
            fallback_url="https://example.com/start",
            render_wait_ms=4000,
            selector_wait_ms=3000,
            playwright_session_manager=None,
        )

    assert result["html"] == "<html>seed</html>"
    assert "https://example.com/final" in calls
    assert "https://example.com/start" in calls


@pytest.mark.asyncio
async def test_fetch_and_parse_promotes_skipped_render_to_partial_when_http_html_exists() -> None:
    """Raw HTTP HTML must remain scorable when Playwright render is unavailable."""
    import asyncio

    import aiohttp

    from hype_frog.crawler.fetcher import fetch_and_parse
    from hype_frog.crawler.network_engine import _empty_diagnostics

    html = """
    <html><head><title>Partial page</title></head>
    <body><main><h1>Heading</h1><p>Enough body copy for extraction.</p></main></body></html>
    """

    async def fake_http(**kwargs: object) -> dict[str, object]:
        del kwargs
        return {
            "status_code": 200,
            "final_url": "https://example.com/page",
            "response_headers": {"Content-Type": "text/html"},
            "redirect_hops": [],
            "html": html,
            "ttfb_ms": 12.0,
            "total_request_ms": 40.0,
        }

    async def fake_render(**kwargs: object) -> RenderedFetchDiagnostics:
        del kwargs
        return _empty_diagnostics("skipped")

    semaphore = asyncio.Semaphore(1)
    async with aiohttp.ClientSession() as session:
        with (
            patch("hype_frog.crawler.fetcher.fetch_http", side_effect=fake_http),
            patch(
                "hype_frog.crawler.fetcher._fetch_render_with_retries",
                side_effect=fake_render,
            ),
        ):
            payload = await fetch_and_parse(
                "https://example.com/page",
                session,
                semaphore,
                crawl_mode="accurate",
            )

    assert payload.main.values["Extraction State"] == "partial"
    assert payload.extra.values["Extraction Source Fallback"] is True
    assert payload.main.values["Title"] == "Partial page"


@pytest.mark.asyncio
async def test_fetch_and_parse_non_200_status_skips_extraction_entirely() -> None:
    import asyncio

    import aiohttp

    from hype_frog.crawler.fetcher import fetch_and_parse

    async def fake_http(**kwargs: object) -> dict[str, object]:
        del kwargs
        return {
            "status_code": 404,
            "final_url": "https://example.com/missing",
            "response_headers": {},
            "redirect_hops": [],
            "redirect_hop_details": [],
            "html": None,
            "ttfb_ms": 8.0,
            "total_request_ms": 20.0,
            "error_kind": None,
        }

    semaphore = asyncio.Semaphore(1)
    async with aiohttp.ClientSession() as session:
        with patch("hype_frog.crawler.fetcher.fetch_http", side_effect=fake_http):
            payload = await fetch_and_parse("https://example.com/missing", session, semaphore)

    assert payload.main.values["Status Code"] == 404
    assert payload.main.values["Extraction State"] == "skipped"


@pytest.mark.asyncio
async def test_fetch_and_parse_unsupported_mime_skips_with_reason() -> None:
    """HTTP 200 with a non-HTML Content-Type and no HTML body must skip
    extraction with the ``unsupported_mime`` dead-letter reason, per the
    Extraction State contract, and must not attempt a render fallback."""
    import asyncio

    import aiohttp

    from hype_frog.crawler.fetcher import fetch_and_parse

    async def fake_http(**kwargs: object) -> dict[str, object]:
        del kwargs
        return {
            "status_code": 200,
            "final_url": "https://example.com/report.pdf",
            "response_headers": {"Content-Type": "application/pdf"},
            "redirect_hops": [],
            "redirect_hop_details": [],
            "html": None,
            "ttfb_ms": 10.0,
            "total_request_ms": 30.0,
            "error_kind": None,
        }

    render_called = False

    async def fake_render(**kwargs: object) -> RenderedFetchDiagnostics:
        nonlocal render_called
        render_called = True
        del kwargs
        return _empty_diagnostics("skipped")

    semaphore = asyncio.Semaphore(1)
    async with aiohttp.ClientSession() as session:
        with (
            patch("hype_frog.crawler.fetcher.fetch_http", side_effect=fake_http),
            patch(
                "hype_frog.crawler.fetcher._fetch_render_with_retries",
                side_effect=fake_render,
            ),
        ):
            payload = await fetch_and_parse(
                "https://example.com/report.pdf", session, semaphore, crawl_mode="fast"
            )

    assert payload.main.values["Extraction State"] == "skipped"
    assert payload.extra.values["skip_reason"] == "unsupported_mime"
    assert render_called is False


@pytest.mark.asyncio
async def test_fetch_and_parse_records_redirect_chain_fields() -> None:
    import asyncio

    import aiohttp

    from hype_frog.crawler.fetcher import fetch_and_parse

    async def fake_http(**kwargs: object) -> dict[str, object]:
        del kwargs
        return {
            "status_code": 200,
            "final_url": "https://example.com/new",
            "response_headers": {"Content-Type": "text/html"},
            "redirect_hops": ["https://example.com/old"],
            "redirect_hop_details": [{"url": "https://example.com/old", "status": 301}],
            "html": "<html><head><title>New</title></head><body>Moved.</body></html>",
            "ttfb_ms": 5.0,
            "total_request_ms": 15.0,
            "error_kind": None,
        }

    async def fake_render(**kwargs: object) -> RenderedFetchDiagnostics:
        del kwargs
        return _empty_diagnostics("skipped")

    semaphore = asyncio.Semaphore(1)
    async with aiohttp.ClientSession() as session:
        with (
            patch("hype_frog.crawler.fetcher.fetch_http", side_effect=fake_http),
            patch(
                "hype_frog.crawler.fetcher._fetch_render_with_retries",
                side_effect=fake_render,
            ),
        ):
            payload = await fetch_and_parse("https://example.com/old", session, semaphore)

    assert payload.extra.values["Redirect Chain Length"] == 1
    assert payload.extra.values["HTTP->HTTPS Redirect"] is False
