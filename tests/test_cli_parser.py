"""Unit tests for :mod:`hype_frog.cli_parser`.

Covers command routing (structured subcommands vs. the legacy flag surface),
the structured ``crawl`` subcommand's argument shapes, ``auth``/``setup``/
``test`` subcommand requiredness, and the two normalisation functions that
turn parsed argv into the project's internal config objects
(``legacy_namespace_to_cli_overrides``, ``structured_crawl_run_config``).

Pure argparse logic — no I/O, no mocking needed.
"""

from __future__ import annotations

import pytest

from hype_frog.cli_parser import (
    ParsedCli,
    legacy_namespace_to_cli_overrides,
    parse_cli,
    structured_crawl_run_config,
)

# ---------------------------------------------------------------------------
# parse_cli: structured vs. legacy routing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", ["crawl", "validate", "auth", "setup", "test"])
def test_parse_cli_routes_known_commands_to_structured_parser(command: str) -> None:
    # Each structured command has required sub-args; supply the minimum to parse cleanly.
    trailing = {
        "auth": ["gsc"],
        "setup": ["semantic"],
        "test": ["quick"],
    }.get(command, [])
    result = parse_cli([command, *trailing])
    assert result.is_structured is True
    assert result.structured is not None
    assert result.legacy is None
    assert result.structured.command == command


def test_parse_cli_falls_back_to_legacy_for_unknown_first_token() -> None:
    result = parse_cli(["--quick-test"])
    assert result.is_structured is False
    assert result.legacy is not None
    assert result.legacy.quick_test is True


def test_parse_cli_empty_argv_uses_legacy_parser() -> None:
    result = parse_cli([])
    assert result.is_structured is False
    assert result.legacy is not None


def test_parsed_cli_is_structured_property() -> None:
    assert ParsedCli(structured=object()).is_structured is True
    assert ParsedCli(legacy=object()).is_structured is False
    assert ParsedCli().is_structured is False


# ---------------------------------------------------------------------------
# Structured "crawl" subcommand
# ---------------------------------------------------------------------------


def test_structured_crawl_defaults_are_none_or_false() -> None:
    args = parse_cli(["crawl"]).structured
    assert args.url is None
    assert args.mode is None
    assert args.max_urls is None
    assert args.max_psi_urls is None
    assert args.inventory_only is False
    assert args.streaming is False
    assert args.regen_report is False


def test_structured_crawl_mode_rejects_invalid_choice() -> None:
    with pytest.raises(SystemExit):
        parse_cli(["crawl", "--mode", "turbo"])


@pytest.mark.parametrize("mode", ["fast", "accurate"])
def test_structured_crawl_mode_accepts_valid_choices(mode: str) -> None:
    args = parse_cli(["crawl", "--mode", mode]).structured
    assert args.mode == mode


def test_structured_crawl_parses_url_and_max_urls() -> None:
    args = parse_cli(
        ["crawl", "--url", "https://example.com/", "--max-urls", "25"]
    ).structured
    assert args.url == "https://example.com/"
    assert args.max_urls == 25


def test_structured_crawl_short_url_flag() -> None:
    args = parse_cli(["crawl", "-u", "https://example.com/"]).structured
    assert args.url == "https://example.com/"


def test_structured_crawl_rejects_combined_verbose_and_quiet_flags_present() -> None:
    """Argparse itself allows both flags to be set (they're independent
    store_true actions) — the mutual-exclusivity check lives in
    ``legacy_namespace_to_cli_overrides``, exercised below."""
    args = parse_cli(["crawl", "--verbose", "--quiet"]).structured
    assert args.verbose is True
    assert args.quiet is True


# ---------------------------------------------------------------------------
# auth / setup / test: required sub-subcommands
# ---------------------------------------------------------------------------


def test_auth_requires_a_subcommand() -> None:
    with pytest.raises(SystemExit):
        parse_cli(["auth"])


def test_auth_gsc_subcommand_parses() -> None:
    args = parse_cli(["auth", "gsc"]).structured
    assert args.auth_command == "gsc"


def test_setup_requires_a_subcommand() -> None:
    with pytest.raises(SystemExit):
        parse_cli(["setup"])


@pytest.mark.parametrize("target", ["semantic", "playwright"])
def test_setup_subcommands_parse(target: str) -> None:
    args = parse_cli(["setup", target]).structured
    assert args.setup_command == target


def test_test_requires_a_subcommand() -> None:
    with pytest.raises(SystemExit):
        parse_cli(["test"])


def test_test_quick_gate_flags() -> None:
    args = parse_cli(["test", "quick", "--fast", "--skip-audit"]).structured
    assert args.test_command == "quick"
    assert args.fast is True
    assert args.skip_audit is True
    assert args.skip_preflight is False


def test_test_full_smoke_gate_parses() -> None:
    args = parse_cli(["test", "full-smoke"]).structured
    assert args.test_command == "full-smoke"


# ---------------------------------------------------------------------------
# legacy_namespace_to_cli_overrides
# ---------------------------------------------------------------------------


def test_legacy_overrides_gsc_inspection_full_takes_precedence() -> None:
    args = parse_cli(["--gsc-url-inspection", "--gsc-url-inspection-full"]).legacy
    overrides = legacy_namespace_to_cli_overrides(args)
    assert overrides.gsc_url_inspection == "full"


def test_legacy_overrides_gsc_inspection_limited_when_only_limited_set() -> None:
    args = parse_cli(["--gsc-url-inspection"]).legacy
    overrides = legacy_namespace_to_cli_overrides(args)
    assert overrides.gsc_url_inspection == "limited"


def test_legacy_overrides_gsc_inspection_none_when_neither_set() -> None:
    args = parse_cli([]).legacy
    overrides = legacy_namespace_to_cli_overrides(args)
    assert overrides.gsc_url_inspection is None


def test_legacy_overrides_rejects_verbose_and_quiet_together() -> None:
    args = parse_cli(["--verbose", "--quiet"]).legacy
    with pytest.raises(SystemExit, match="Cannot combine --verbose and --quiet"):
        legacy_namespace_to_cli_overrides(args)


def test_legacy_overrides_field_mapping() -> None:
    args = parse_cli(
        [
            "--competitors",
            "a.com,b.com",
            "--benchmarks",
            "--export-pdf",
            "--check-og-images",
            "--check-images",
            "--previous-run",
            "prior.xlsx",
            "--max-memory-mb",
            "2048",
            "--streaming",
            "--regen-report",
            "--snapshot-id",
            "abc-123",
            "--re-enrich",
            "--show-all-tabs",
        ]
    ).legacy
    overrides = legacy_namespace_to_cli_overrides(args)
    assert overrides.competitors == "a.com,b.com"
    assert overrides.benchmarks is True
    assert overrides.export_pdf is True
    assert overrides.check_og_images is True
    assert overrides.check_content_images is True
    assert overrides.previous_run == "prior.xlsx"
    assert overrides.max_memory_mb == 2048
    assert overrides.streaming is True
    assert overrides.regen_report is True
    assert overrides.snapshot_id == "abc-123"
    assert overrides.re_enrich is True
    assert overrides.show_all_tabs is True


def test_legacy_overrides_defaults_are_falsy() -> None:
    args = parse_cli([]).legacy
    overrides = legacy_namespace_to_cli_overrides(args)
    assert overrides.competitors is None
    assert overrides.benchmarks is False
    assert overrides.max_memory_mb is None
    assert overrides.regen_report is False


# ---------------------------------------------------------------------------
# structured_crawl_run_config
# ---------------------------------------------------------------------------


def test_structured_crawl_run_config_none_when_url_missing() -> None:
    args = parse_cli(["crawl"]).structured
    assert structured_crawl_run_config(args) is None


def test_structured_crawl_run_config_defaults_to_accurate_mode_timings() -> None:
    args = parse_cli(["crawl", "--url", "https://example.com/"]).structured
    config = structured_crawl_run_config(args)
    assert config is not None
    assert config.crawl_mode == "accurate"
    assert config.render_wait_ms == 4000
    assert config.selector_wait_ms == 3000


def test_structured_crawl_run_config_fast_mode_uses_shorter_timings() -> None:
    args = parse_cli(["crawl", "--url", "https://example.com/", "--mode", "fast"]).structured
    config = structured_crawl_run_config(args)
    assert config is not None
    assert config.crawl_mode == "fast"
    assert config.render_wait_ms == 1000
    assert config.selector_wait_ms == 500


def test_structured_crawl_run_config_inventory_only_disables_full_suite() -> None:
    args = parse_cli(
        ["crawl", "--url", "https://example.com/", "--inventory-only"]
    ).structured
    config = structured_crawl_run_config(args)
    assert config is not None
    assert config.full_suite is False


def test_structured_crawl_run_config_full_suite_is_default() -> None:
    args = parse_cli(["crawl", "--url", "https://example.com/"]).structured
    config = structured_crawl_run_config(args)
    assert config is not None
    assert config.full_suite is True


def test_structured_crawl_run_config_gsc_inspection_full_precedence() -> None:
    args = parse_cli(
        [
            "crawl",
            "--url",
            "https://example.com/",
            "--gsc-url-inspection",
            "--gsc-url-inspection-full",
        ]
    ).structured
    config = structured_crawl_run_config(args)
    assert config is not None
    assert config.gsc_url_inspection == "full"


def test_structured_crawl_run_config_gsc_inspection_none_by_default() -> None:
    args = parse_cli(["crawl", "--url", "https://example.com/"]).structured
    config = structured_crawl_run_config(args)
    assert config is not None
    assert config.gsc_url_inspection is None


def test_structured_crawl_run_config_show_all_tabs_disables_hide() -> None:
    args = parse_cli(
        ["crawl", "--url", "https://example.com/", "--show-all-tabs"]
    ).structured
    config = structured_crawl_run_config(args)
    assert config is not None
    assert config.hide_advanced_tabs is False


def test_structured_crawl_run_config_hides_advanced_tabs_by_default() -> None:
    args = parse_cli(["crawl", "--url", "https://example.com/"]).structured
    config = structured_crawl_run_config(args)
    assert config is not None
    assert config.hide_advanced_tabs is True


def test_structured_crawl_run_config_passes_through_previous_run_path() -> None:
    args = parse_cli(
        ["crawl", "--url", "https://example.com/", "--previous-run", "prior.xlsx"]
    ).structured
    config = structured_crawl_run_config(args)
    assert config is not None
    assert config.previous_audit_path == "prior.xlsx"


def test_structured_crawl_run_config_previous_run_defaults_to_empty_string() -> None:
    args = parse_cli(["crawl", "--url", "https://example.com/"]).structured
    config = structured_crawl_run_config(args)
    assert config is not None
    assert config.previous_audit_path == ""
