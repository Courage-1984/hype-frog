"""Installed package CLI entry (delegates to migrated main body)."""

from __future__ import annotations

import argparse
import asyncio

from hype_frog.core.run_config import RunConfig, quick_test_run_config
from hype_frog.app_orchestrator import main as _async_main


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
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    preset: RunConfig | None = quick_test_run_config() if args.quick_test else None
    asyncio.run(_async_main(preset))


if __name__ == "__main__":
    run()
