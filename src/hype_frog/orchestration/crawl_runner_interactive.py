"""Interactive crawl prompts and runtime option resolution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from hype_frog.config import MAX_WORKERS, get_delay_between_requests
from hype_frog.core import get_logger
from hype_frog.core.env_vars import get_hf_previous_audit_path
from hype_frog.core.logger import console
from hype_frog.orchestration.run_setup import RunSetup

logger = get_logger(__name__)


@dataclass(frozen=True)
class CrawlRuntimeOptions:
    workers: int
    request_delay: float
    full_suite: bool
    previous_audit_path: str
    checkpoint_every: int
    hide_advanced_tabs: bool = True


def prompt_crawl_options_sync(setup: RunSetup) -> CrawlRuntimeOptions:
    """Synchronous interactive configuration — run via ``asyncio.to_thread``."""
    console.print("\n[bold]Crawl Safety Profile[/bold]")
    console.print("  [cyan]1[/cyan]  Gentle   — fewer workers, longer delay")
    console.print("  [cyan]2[/cyan]  Balanced — default")
    console.print("  [cyan]3[/cyan]  Faster   — more workers, shorter delay")
    profile_choice = input(
        "Select Crawl Safety Profile [1:Gentle | 2:Balanced | 3:Faster]: "
    ).strip()
    if profile_choice == "1":
        workers = 2
        request_delay = 4.0
    elif profile_choice == "3":
        workers = 4
        request_delay = 1.5
    elif profile_choice == "2" or profile_choice == "":
        workers = MAX_WORKERS
        request_delay = get_delay_between_requests()
    else:
        logger.warning("Invalid input; defaulting to Balanced.")
        workers = MAX_WORKERS
        request_delay = get_delay_between_requests()

    suite_choice = input(
        "Audit Depth: [1] Main Inventory Only | [2] Full AEO/SEO Suite: "
    ).strip()
    if suite_choice == "1":
        full_suite = False
    elif suite_choice == "2":
        full_suite = True
    elif suite_choice == "":
        full_suite = False
    else:
        logger.warning("Invalid input; defaulting to Full AEO/SEO Suite.")
        full_suite = True

    if setup.hide_advanced_tabs_preset is not None:
        # --show-all-tabs (or another explicit override) was passed even though
        # the rest of this run is interactive — honor it without prompting.
        hide_advanced_tabs = setup.hide_advanced_tabs_preset
    else:
        tabs_choice = input(
            "Workbook Tab Visibility: [1] Hide advanced/historical tabs (default) "
            "| [2] Show all tabs: "
        ).strip()
        if tabs_choice == "2":
            hide_advanced_tabs = False
        elif tabs_choice == "1" or tabs_choice == "":
            hide_advanced_tabs = True
        else:
            logger.warning("Invalid input; defaulting to hiding advanced/historical tabs.")
            hide_advanced_tabs = True

    previous_audit_path = input(
        "Previous Audit Path (.xlsx or _delta_summary.json) [leave blank to skip]: "
    ).strip()
    if not previous_audit_path:
        previous_audit_path = get_hf_previous_audit_path()
    checkpoint_raw = input(
        "Auto-Save Checkpoint Frequency (N URLs) [0 to disable]: "
    ).strip()
    try:
        checkpoint_every = int(checkpoint_raw or "0")
    except ValueError:
        checkpoint_every = 0

    return CrawlRuntimeOptions(
        workers=workers,
        request_delay=request_delay,
        full_suite=full_suite,
        previous_audit_path=previous_audit_path,
        checkpoint_every=checkpoint_every,
        hide_advanced_tabs=hide_advanced_tabs,
    )


async def resolve_crawl_runtime_options(setup: RunSetup) -> CrawlRuntimeOptions:
    """Resolve workers, delay, suite, checkpoint from preset or interactive prompts."""
    if setup.workers_preset is not None:
        previous_audit_path = (setup.previous_audit_path_preset or "").strip()
        if not previous_audit_path:
            previous_audit_path = get_hf_previous_audit_path()
        logger.info(
            "Crawl safety profile: preset (%s workers, %ss delay)",
            setup.workers_preset,
            setup.request_delay_preset,
        )
        logger.debug("Run mode: Full SEO suite (preset)")
        logger.debug("Checkpoint save: disabled (preset)")
        return CrawlRuntimeOptions(
            workers=setup.workers_preset,
            request_delay=(
                setup.request_delay_preset
                if setup.request_delay_preset is not None
                else get_delay_between_requests()
            ),
            full_suite=bool(setup.full_suite_preset),
            previous_audit_path=previous_audit_path,
            checkpoint_every=int(setup.checkpoint_every_preset or 0),
            hide_advanced_tabs=(
                setup.hide_advanced_tabs_preset
                if setup.hide_advanced_tabs_preset is not None
                else True
            ),
        )

    return await asyncio.to_thread(prompt_crawl_options_sync, setup)
