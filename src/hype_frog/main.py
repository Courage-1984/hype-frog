"""CLI entry for the hype_frog package (post-migration)."""

from __future__ import annotations

import asyncio


def run() -> None:
    """Run the async audit pipeline (body lives in ``entry_main`` after migration)."""
    from hype_frog.entry_main import main as _async_main  # noqa: PLC0415

    asyncio.run(_async_main())


if __name__ == "__main__":
    run()
