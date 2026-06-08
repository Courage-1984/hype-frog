"""Installed package CLI entry (delegates to migrated main body)."""

from __future__ import annotations

import argparse
import asyncio

from hype_frog.core.integration_validator import run_validation_cli
from hype_frog.core.quick_test import QuickTestOptions, run_quick_test_gate
from hype_frog.app_orchestrator import main as _async_main
from hype_frog.crawler.gsc_engine import ensure_gsc_oauth_token
from hype_frog.extractors.semantic_setup import install_semantic_model


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="hype-frog technical SEO auditor")
    parser.add_argument(
        "--quick-test",
        action="store_true",
        help=(
            "Comprehensive smoke gate: preflight checks, focused pytest, "
            "10-URL sitemap crawl (Playwright + full suite), workbook audit"
        ),
    )
    parser.add_argument(
        "--quick-test-fast",
        action="store_true",
        help="Same crawl/export as --quick-test but skip preflight and pytest",
    )
    parser.add_argument(
        "--quick-test-skip-preflight",
        action="store_true",
        help="With --quick-test: skip GSC/PSI preflight checks",
    )
    parser.add_argument(
        "--quick-test-skip-pytest",
        action="store_true",
        help="With --quick-test: skip focused pytest regression subset",
    )
    parser.add_argument(
        "--quick-test-skip-audit",
        action="store_true",
        help="With --quick-test: skip post-export workbook audit",
    )
    parser.add_argument(
        "--install-semantic",
        action="store_true",
        help=(
            "Install/verify the spaCy en_core_web_sm model "
            "(requires: uv sync --extra semantic)"
        ),
    )
    parser.add_argument(
        "--gsc-auth",
        action="store_true",
        help=(
            "Trigger Google Search Console OAuth flow only and create/refresh "
            "secrets/token.json from secrets/client_secrets.json"
        ),
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help=(
            "Validate GSC OAuth files, PSI API key, and optional LLM keys "
            "without running a crawl"
        ),
    )
    parser.add_argument(
        "--validate-url",
        default=None,
        metavar="URL",
        help=(
            "When used with --validate, check that this crawl target matches a "
            "visible Search Console property (e.g. https://example.com/)"
        ),
    )
    parser.add_argument(
        "--psi-probe-url",
        default="https://example.com",
        metavar="URL",
        help="URL used for the live PageSpeed Insights probe during --validate",
    )
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    if args.validate:
        raise SystemExit(
            run_validation_cli(
                target_url=args.validate_url,
                psi_probe_url=args.psi_probe_url,
            )
        )
    if args.install_semantic:
        ok, message = install_semantic_model()
        print(message)
        raise SystemExit(0 if ok else 1)
    if args.gsc_auth:
        ok, token_path = ensure_gsc_oauth_token()
        if ok:
            print(f"GSC OAuth token ready: {token_path}")
        else:
            print(
                "GSC OAuth token bootstrap failed. Ensure "
                "secrets/client_secrets.json exists and re-run --gsc-auth."
            )
        return
    if args.quick_test or args.quick_test_fast:
        options = QuickTestOptions(
            skip_preflight=args.quick_test_fast or args.quick_test_skip_preflight,
            skip_pytest=args.quick_test_fast or args.quick_test_skip_pytest,
            skip_workbook_audit=args.quick_test_skip_audit,
        )
        raise SystemExit(asyncio.run(run_quick_test_gate(options)))
    asyncio.run(_async_main(None))


if __name__ == "__main__":
    run()
