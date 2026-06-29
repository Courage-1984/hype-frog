"""Run quick_test RunConfig through app_orchestrator.main (snapshot path)."""

from __future__ import annotations

import asyncio
import sys

from hype_frog.app_orchestrator import main
from hype_frog.core.run_config import quick_test_run_config

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

asyncio.run(main(run=quick_test_run_config()))
