"""Installed package CLI entry (delegates to migrated main body)."""

from __future__ import annotations

import argparse
import asyncio

from hype_frog.core.run_config import RunConfig, quick_test_run_config
from hype_frog.app_orchestrator import main as _async_main
from hype_frog.crawler.gsc_engine import ensure_gsc_oauth_token


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="hype-frog technical SEO auditor")
    parser.add_argument(
        "--quick-test",
        action="store_true",
        help=(
            "Run a fixed 10-URL smoke crawl (sitemap + Playwright + full suite) "
            "with no interactive prompts"
        ),
    )
    parser.add_argument(
        "--gsc-auth",
        action="store_true",
        help=(
            "Trigger Google Search Console OAuth flow only and create/refresh "
            "src/hype_frog/token.json from src/hype_frog/client_secrets.json"
        ),
    )
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    if args.gsc_auth:
        ok, token_path = ensure_gsc_oauth_token()
        if ok:
            print(f"GSC OAuth token ready: {token_path}")
        else:
            print(
                "GSC OAuth token bootstrap failed. Ensure "
                "src/hype_frog/client_secrets.json exists and re-run --gsc-auth."
            )
        return
    preset: RunConfig | None = quick_test_run_config() if args.quick_test else None
    asyncio.run(_async_main(preset))


if __name__ == "__main__":
    run()
