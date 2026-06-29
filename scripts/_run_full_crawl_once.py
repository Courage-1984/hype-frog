"""One-off non-interactive full crawl for snapshot/regen validation (not shipped)."""

from __future__ import annotations

import asyncio
import sys

from hype_frog.app_orchestrator import main
from hype_frog.core.run_config import RunConfig

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

FULL_CRAWL = RunConfig(
    target_input="https://africanmarketingconfederation.org/page-sitemap.xml",
    max_urls=None,
    max_psi_urls=None,
    high_value_slugs=["about", "contact", "membership", "awards"],
    crawl_mode="accurate",
    render_wait_ms=2000,
    selector_wait_ms=1500,
    workers=4,
    request_delay=1.0,
    full_suite=True,
    previous_audit_path="",
    checkpoint_every=50,
    resume_checkpoint="no",
    check_external_link_status=True,
    check_og_images=False,
    check_content_images=False,
    bfs_max_depth=3,
    export_pdf=True,
)

asyncio.run(main(run=FULL_CRAWL))
