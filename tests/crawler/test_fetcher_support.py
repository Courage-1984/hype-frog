"""Tests for :mod:`hype_frog.crawler.fetcher` support functions:
Playwright browser-path configuration/install, and the per-domain
robots.txt/llms.txt cache populator (``_populate_robots_cache``).

Distinct from ``test_fetcher_extraction.py`` (HTML extraction-source
consistency) and ``test_extraction_contract.py`` (Extraction State contract).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from hype_frog.crawler.fetcher import (
    _populate_robots_cache,
    configure_playwright_browsers_path,
    install_playwright_chromium,
)

# ---------------------------------------------------------------------------
# configure_playwright_browsers_path
# ---------------------------------------------------------------------------


def test_configure_playwright_path_dev_mode_returns_none(monkeypatch) -> None:
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    monkeypatch.setattr("sys.frozen", False, raising=False)
    assert configure_playwright_browsers_path() is None


def test_configure_playwright_path_returns_existing_override(monkeypatch) -> None:
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", "C:/existing/path")
    assert configure_playwright_browsers_path() == "C:/existing/path"


def test_configure_playwright_path_frozen_sets_persistent_location(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    result = configure_playwright_browsers_path()

    assert result is not None
    assert "hype-frog" in result
    assert "ms-playwright" in result
    import os

    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == result


def test_configure_playwright_path_frozen_unwritable_target_returns_none(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    monkeypatch.setattr("sys.frozen", True, raising=False)
    # LOCALAPPDATA points at a path where a FILE already occupies the
    # "hype-frog" segment, so Path.mkdir(parents=True) cannot create the
    # "hype-frog/ms-playwright" directory tree underneath it.
    blocker = tmp_path / "hype-frog"
    blocker.write_text("occupied", encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert configure_playwright_browsers_path() is None


# ---------------------------------------------------------------------------
# install_playwright_chromium
# ---------------------------------------------------------------------------


def test_install_playwright_chromium_success(monkeypatch) -> None:
    monkeypatch.setattr(
        "hype_frog.crawler.fetcher.configure_playwright_browsers_path", lambda: None
    )
    monkeypatch.setattr(
        "playwright._impl._driver.compute_driver_executable",
        lambda: ("node", "cli.js"),
    )
    completed = MagicMock(returncode=0, stdout="", stderr="")
    monkeypatch.setattr("subprocess.run", MagicMock(return_value=completed))

    ok, message = install_playwright_chromium()

    assert ok is True
    assert "installed" in message.lower()


def test_install_playwright_chromium_nonzero_exit_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        "hype_frog.crawler.fetcher.configure_playwright_browsers_path", lambda: None
    )
    monkeypatch.setattr(
        "playwright._impl._driver.compute_driver_executable",
        lambda: ("node", "cli.js"),
    )
    completed = MagicMock(returncode=1, stdout="", stderr="download failed: 403")
    monkeypatch.setattr("subprocess.run", MagicMock(return_value=completed))

    ok, message = install_playwright_chromium()

    assert ok is False
    assert "download failed: 403" in message


def test_install_playwright_chromium_driver_lookup_raises(monkeypatch) -> None:
    monkeypatch.setattr(
        "hype_frog.crawler.fetcher.configure_playwright_browsers_path", lambda: None
    )

    def _raise():
        raise RuntimeError("playwright not installed")

    monkeypatch.setattr("playwright._impl._driver.compute_driver_executable", _raise)

    ok, message = install_playwright_chromium()

    assert ok is False
    assert "Could not install Playwright Chromium" in message


def test_install_playwright_chromium_single_string_driver_normalised(monkeypatch) -> None:
    """Older Playwright builds return a single launcher-script string rather
    than a (node, cli.js) tuple — must still build a valid command list."""
    monkeypatch.setattr(
        "hype_frog.crawler.fetcher.configure_playwright_browsers_path", lambda: None
    )
    monkeypatch.setattr(
        "playwright._impl._driver.compute_driver_executable",
        lambda: "/path/to/launcher.sh",
    )
    completed = MagicMock(returncode=0, stdout="", stderr="")
    mock_run = MagicMock(return_value=completed)
    monkeypatch.setattr("subprocess.run", mock_run)

    ok, _message = install_playwright_chromium()

    assert ok is True
    called_cmd = mock_run.call_args.args[0]
    assert called_cmd[0] == "/path/to/launcher.sh"
    assert called_cmd[1:] == ["install", "chromium"]


# ---------------------------------------------------------------------------
# _populate_robots_cache
# ---------------------------------------------------------------------------


def _cm_response(status: int, body: str = "") -> MagicMock:
    response = MagicMock()
    response.status = status
    response.text = AsyncMock(return_value=body)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=response)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest.mark.asyncio
async def test_populate_robots_cache_records_llms_and_robots_present() -> None:
    session = MagicMock()
    robots_body = "User-agent: *\nAllow: /\ngptbot\nclaudebot\nperplexitybot\nccbot"
    session.get = MagicMock(
        side_effect=lambda url, **_kwargs: _cm_response(200)
        if "llms.txt" in url
        else _cm_response(200, robots_body)
    )
    cache: dict = {}

    await _populate_robots_cache(
        session=session, timeout=MagicMock(), robots_cache=cache, domain_key="https://example.com"
    )

    entry = cache["https://example.com"]
    assert entry["llms_present"] is True


@pytest.mark.asyncio
async def test_populate_robots_cache_llms_absent_robots_missing() -> None:
    session = MagicMock()
    session.get = MagicMock(
        side_effect=lambda url, **_kwargs: _cm_response(404)
    )
    cache: dict = {}

    await _populate_robots_cache(
        session=session, timeout=MagicMock(), robots_cache=cache, domain_key="https://example.com"
    )

    entry = cache["https://example.com"]
    assert entry["llms_present"] is False


@pytest.mark.asyncio
async def test_populate_robots_cache_transport_failure_degrades_gracefully() -> None:
    """A connection failure on either probe must not raise — the domain still
    gets a cache entry with null-safe fields so the calling crawl isn't
    aborted by a single robots.txt/llms.txt hiccup."""
    session = MagicMock()
    session.get = MagicMock(side_effect=RuntimeError("connection refused"))
    cache: dict = {}

    await _populate_robots_cache(
        session=session, timeout=MagicMock(), robots_cache=cache, domain_key="https://example.com"
    )

    assert "https://example.com" in cache
    entry = cache["https://example.com"]
    assert entry["llms_present"] is False


@pytest.mark.asyncio
async def test_populate_robots_cache_computes_aeo_bot_coverage_ratio() -> None:
    session = MagicMock()
    # Only one of the three _AEO_ENGINE_BOTS ("gptbot", "perplexitybot", "ccbot") present.
    robots_body = "User-agent: *\ngptbot allowed"
    session.get = MagicMock(
        side_effect=lambda url, **_kwargs: _cm_response(404)
        if "llms.txt" in url
        else _cm_response(200, robots_body)
    )
    cache: dict = {}

    await _populate_robots_cache(
        session=session, timeout=MagicMock(), robots_cache=cache, domain_key="https://example.com"
    )

    entry = cache["https://example.com"]
    assert entry["aeo_engine_bot_coverage"] == pytest.approx(1 / 3)
