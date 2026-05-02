"""Installed package CLI entry (delegates to migrated main body)."""
from __future__ import annotations

import asyncio

from hype_frog.entry_main import main as _async_main


def run() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    run()
