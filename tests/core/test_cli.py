"""Tests for interactive CLI configuration."""

from __future__ import annotations

import logging

import pytest

from hype_frog.core.cli import UserConfig, _resolve_crawl_engine, get_user_config
from hype_frog.core.logger import resolve_console_level_from_cli
from hype_frog.main import _parse_args


def test_resolve_crawl_engine_maps_choices() -> None:
    assert _resolve_crawl_engine("1") == "fast"
    assert _resolve_crawl_engine("2") == "accurate"
    assert _resolve_crawl_engine("") == "accurate"
    assert _resolve_crawl_engine("invalid") == "accurate"


def test_get_user_config_parses_prompts(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter(
        [
            "https://example.com/sitemap.xml",
            "10",
            "2",
            "about, pricing",
            "1",
            "5000",
            "2500",
            "yes",
            "y",
            "y",
            "50",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    config = get_user_config()

    assert isinstance(config, UserConfig)
    assert config.target_input == "https://example.com/sitemap.xml"
    assert config.max_urls == 10
    assert config.max_psi_urls == 2
    assert config.high_value_slugs == ["about", "pricing"]
    assert config.crawl_mode == "fast"
    assert config.render_wait_ms == 5000
    assert config.selector_wait_ms == 2500
    assert config.check_external_link_status is True
    assert config.check_og_images is True
    assert config.check_content_images is True
    assert config.quick_wins_max_results == 50


def test_get_user_config_ignores_invalid_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter(
        [
            "https://example.com/",
            "not-a-number",
            "bad",
            "",
            "2",
            "",
            "",
            "",
            "",
            "",
            "not-a-number-either",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    config = get_user_config()

    assert config.max_urls is None
    assert config.max_psi_urls is None
    assert config.high_value_slugs == []
    assert config.render_wait_ms == 4000
    assert config.selector_wait_ms == 3000
    assert config.check_content_images is False
    assert config.quick_wins_max_results is None


def test_parse_args_verbose_and_quiet_flags() -> None:
    verbose = _parse_args(["--verbose"])
    quiet = _parse_args(["--quiet"])
    assert verbose.verbose is True
    assert verbose.quiet is False
    assert quiet.verbose is False
    assert quiet.quiet is True


def test_verbose_quiet_map_to_console_levels() -> None:
    assert resolve_console_level_from_cli(verbose=True, quiet=False) == logging.DEBUG
    assert resolve_console_level_from_cli(verbose=False, quiet=True) == logging.WARNING
