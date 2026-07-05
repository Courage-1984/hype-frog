"""Tests for structured CLI parsing."""

from __future__ import annotations

import sys

import pytest

from hype_frog.cli_parser import (
    legacy_namespace_to_cli_overrides,
    parse_cli,
    structured_crawl_run_config,
)
from hype_frog.main import _parse_args


def test_legacy_parse_args_verbose_and_quiet() -> None:
    verbose = _parse_args(["--verbose"])
    quiet = _parse_args(["--quiet"])
    assert verbose.verbose is True
    assert quiet.quiet is True


def test_structured_crawl_parses_url_and_mode() -> None:
    parsed = parse_cli(
        ["crawl", "--url", "https://example.com/sitemap.xml", "--mode", "fast", "--streaming"]
    )
    assert parsed.is_structured
    assert parsed.structured is not None
    assert parsed.structured.command == "crawl"
    assert parsed.structured.url == "https://example.com/sitemap.xml"
    assert parsed.structured.mode == "fast"
    assert parsed.structured.streaming is True


def test_structured_crawl_run_config_builds_preset() -> None:
    parsed = parse_cli(["crawl", "-u", "https://example.com/", "-m", "accurate", "--max-urls", "50"])
    assert parsed.structured is not None
    run_config = structured_crawl_run_config(parsed.structured)
    assert run_config is not None
    assert run_config.target_input == "https://example.com/"
    assert run_config.crawl_mode == "accurate"
    assert run_config.max_urls == 50
    assert run_config.full_suite is True


def test_structured_crawl_without_url_is_interactive() -> None:
    parsed = parse_cli(["crawl"])
    assert parsed.structured is not None
    assert structured_crawl_run_config(parsed.structured) is None


def test_parse_cli_uses_sys_argv_when_argv_none(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["hype-frog", "validate", "--url", "https://example.com/"])
    parsed = parse_cli()
    assert parsed.is_structured
    assert parsed.structured is not None
    assert parsed.structured.command == "validate"


def test_legacy_flags_still_parse_without_subcommand() -> None:
    parsed = parse_cli(["--quick-test-fast"])
    assert not parsed.is_structured
    assert parsed.legacy is not None
    assert parsed.legacy.quick_test_fast is True


def test_legacy_namespace_to_cli_overrides_rejects_verbose_and_quiet() -> None:
    args = _parse_args(["--verbose", "--quiet"])
    with pytest.raises(SystemExit):
        legacy_namespace_to_cli_overrides(args)


def test_show_all_tabs_flag_sets_cli_override() -> None:
    args = _parse_args(["--show-all-tabs"])
    overrides = legacy_namespace_to_cli_overrides(args)
    assert overrides.show_all_tabs is True


def test_show_all_tabs_flag_defaults_false() -> None:
    args = _parse_args([])
    overrides = legacy_namespace_to_cli_overrides(args)
    assert overrides.show_all_tabs is False


def test_structured_crawl_run_config_hides_tabs_by_default() -> None:
    parsed = parse_cli(["crawl", "-u", "https://example.com/"])
    assert parsed.structured is not None
    run_config = structured_crawl_run_config(parsed.structured)
    assert run_config is not None
    assert run_config.hide_advanced_tabs is True


def test_structured_crawl_run_config_show_all_tabs_flag() -> None:
    parsed = parse_cli(["crawl", "-u", "https://example.com/", "--show-all-tabs"])
    assert parsed.structured is not None
    run_config = structured_crawl_run_config(parsed.structured)
    assert run_config is not None
    assert run_config.hide_advanced_tabs is False
