"""Non-interactive --regen-report harness for PowerShell test scripts."""

from __future__ import annotations

import asyncio
import sys

from hype_frog.app_orchestrator import main
from hype_frog.core.cli import UserConfig
from hype_frog.core.run_config import CliRunOverrides

TARGET = "https://africanmarketingconfederation.org/page-sitemap.xml"


def _user_config() -> UserConfig:
    return UserConfig(
        target_input=TARGET,
        max_urls=None,
        max_psi_urls=None,
        high_value_slugs=["about", "contact", "membership", "awards"],
        crawl_mode="accurate",
        render_wait_ms=2000,
        selector_wait_ms=1500,
        check_external_link_status=True,
        check_og_images=False,
        check_content_images=False,
    )


if __name__ == "__main__":
    import hype_frog.orchestration.run_setup as run_setup

    run_setup.get_user_config = _user_config  # type: ignore[method-assign]

    snapshot_id = sys.argv[1] if len(sys.argv) > 1 else None
    overrides = CliRunOverrides(
        regen_report=True,
        snapshot_id=snapshot_id,
    )
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main(cli_overrides=overrides))
