"""Installed package CLI entry (delegates to migrated main body)."""

from __future__ import annotations

import argparse
import asyncio

from hype_frog.config import apply_runtime_override
from hype_frog.core.env_config import EnvConfigError, require_valid_environment, validate_environment
from hype_frog.core.logger import console
from hype_frog.core.run_config import RunConfig
from hype_frog.cli_parser import (
    ParsedCli,
    legacy_namespace_to_cli_overrides,
    parse_cli,
    structured_crawl_run_config,
)
from hype_frog.diagnostics.integration_validator import run_validation_cli
from hype_frog.diagnostics.quick_test import QuickTestOptions, run_quick_test_gate
from hype_frog.diagnostics.full_smoke_test import FullSmokeOptions, run_full_smoke_gate
from hype_frog.app_orchestrator import main as _async_main
from hype_frog.crawler.gsc_engine import ensure_gsc_oauth_token
from hype_frog.extractors.semantic_setup import install_semantic_model


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Legacy flag parser (retained for tests and backward compatibility)."""
    parsed = parse_cli(argv)
    if parsed.legacy is None:
        raise SystemExit("Use parse_cli() for structured subcommands.")
    return parsed.legacy


def _run_legacy(args: argparse.Namespace) -> None:
    if args.validate:
        raise SystemExit(
            run_validation_cli(
                target_url=args.validate_url,
                psi_probe_url=args.psi_probe_url,
            )
        )
    if args.install_semantic:
        ok, message = install_semantic_model()
        console.print(f"[green]{message}[/green]" if ok else f"[red]{message}[/red]")
        raise SystemExit(0 if ok else 1)
    if args.install_playwright:
        from hype_frog.crawler.fetcher import install_playwright_chromium

        ok, message = install_playwright_chromium()
        console.print(f"[green]{message}[/green]" if ok else f"[red]{message}[/red]")
        raise SystemExit(0 if ok else 1)
    if args.gsc_auth:
        ok, token_path = ensure_gsc_oauth_token()
        if ok:
            console.print(f"[green]GSC OAuth token ready: {token_path}[/green]")
        else:
            console.print(
                "[red]GSC OAuth token bootstrap failed. Ensure "
                "secrets/client_secrets.json exists and re-run "
                "'hype-frog auth gsc' or --gsc-auth.[/red]"
            )
        return
    if args.full_smoke_test or args.full_smoke_test_fast:
        smoke_options = FullSmokeOptions(
            skip_preflight=args.full_smoke_test_fast or args.full_smoke_test_skip_preflight,
            skip_pytest=args.full_smoke_test_fast or args.full_smoke_test_skip_pytest,
            skip_workbook_audit=args.full_smoke_test_skip_audit,
        )
        raise SystemExit(asyncio.run(run_full_smoke_gate(smoke_options)))
    if args.quick_test or args.quick_test_fast:
        options = QuickTestOptions(
            skip_preflight=args.quick_test_fast or args.quick_test_skip_preflight,
            skip_pytest=args.quick_test_fast or args.quick_test_skip_pytest,
            skip_workbook_audit=args.quick_test_skip_audit,
        )
        raise SystemExit(asyncio.run(run_quick_test_gate(options)))
    if args.regen_report and (
        args.quick_test
        or args.quick_test_fast
        or args.full_smoke_test
        or args.full_smoke_test_fast
        or args.validate
    ):
        raise SystemExit(
            "--regen-report cannot be combined with --quick-test, "
            "--full-smoke-test, or --validate."
        )
    cli_overrides = legacy_namespace_to_cli_overrides(args)
    asyncio.run(_async_main(None, cli_overrides=cli_overrides))


def _run_structured(args: argparse.Namespace) -> None:
    command = args.command
    if command == "validate":
        raise SystemExit(
            run_validation_cli(
                target_url=args.url,
                psi_probe_url=args.psi_probe_url,
            )
        )
    if command == "auth":
        if args.auth_command != "gsc":
            raise SystemExit(f"Unknown auth command: {args.auth_command}")
        ok, token_path = ensure_gsc_oauth_token()
        if ok:
            console.print(f"[green]GSC OAuth token ready: {token_path}[/green]")
        else:
            console.print(
                "[red]GSC OAuth token bootstrap failed. Ensure "
                "secrets/client_secrets.json exists.[/red]"
            )
            raise SystemExit(1)
        return
    if command == "setup":
        if args.setup_command == "semantic":
            ok, message = install_semantic_model()
            console.print(f"[green]{message}[/green]" if ok else f"[red]{message}[/red]")
            raise SystemExit(0 if ok else 1)
        if args.setup_command == "playwright":
            from hype_frog.crawler.fetcher import install_playwright_chromium

            ok, message = install_playwright_chromium()
            console.print(f"[green]{message}[/green]" if ok else f"[red]{message}[/red]")
            raise SystemExit(0 if ok else 1)
        raise SystemExit(f"Unknown setup command: {args.setup_command}")
    if command == "test":
        fast = args.fast or args.skip_preflight or args.skip_pytest
        if args.test_command == "quick":
            options = QuickTestOptions(
                skip_preflight=fast or args.skip_preflight,
                skip_pytest=fast or args.skip_pytest,
                skip_workbook_audit=args.skip_audit,
            )
            raise SystemExit(asyncio.run(run_quick_test_gate(options)))
        if args.test_command == "full-smoke":
            smoke_options = FullSmokeOptions(
                skip_preflight=fast or args.skip_preflight,
                skip_pytest=fast or args.skip_pytest,
                skip_workbook_audit=args.skip_audit,
            )
            raise SystemExit(asyncio.run(run_full_smoke_gate(smoke_options)))
        raise SystemExit(f"Unknown test command: {args.test_command}")
    if command == "crawl":
        if args.verbose and args.quiet:
            raise SystemExit("Cannot combine --verbose and --quiet.")
        run_config: RunConfig | None = structured_crawl_run_config(args)
        context = "startup"
        if run_config is not None:
            context = "accurate_crawl" if run_config.crawl_mode == "accurate" else "crawl"
        validate_environment(context=context)
        cli_overrides = legacy_namespace_to_cli_overrides(args)
        asyncio.run(_async_main(run_config, cli_overrides=cli_overrides))
        return
    raise SystemExit(f"Unknown command: {command}")


def run(argv: list[str] | None = None) -> None:
    parsed: ParsedCli = parse_cli(argv)
    try:
        require_valid_environment(context="startup")
    except EnvConfigError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1) from exc

    from hype_frog.crawler.fetcher import configure_playwright_browsers_path

    configure_playwright_browsers_path()

    if parsed.is_structured:
        assert parsed.structured is not None
        args = parsed.structured
        if args.command == "crawl" and args.psi_delay is not None and args.psi_delay >= 0:
            apply_runtime_override("PSI_BASE_DELAY_SECONDS", args.psi_delay)
        _run_structured(args)
        return

    assert parsed.legacy is not None
    args = parsed.legacy
    if args.psi_delay is not None and args.psi_delay >= 0:
        apply_runtime_override("PSI_BASE_DELAY_SECONDS", args.psi_delay)
    _run_legacy(args)


if __name__ == "__main__":
    run()
