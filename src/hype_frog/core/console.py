from __future__ import annotations

import time
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from hype_frog.core.logger import console, get_logger

logger = get_logger(__name__)


def log_phase_banner(title: str) -> None:
    """Render a styled horizontal rule — a visible landmark between pipeline phases."""
    console.print(Rule(f" {title} ", style="bold cyan"))


@contextmanager
def log_stage_timer(stage_name: str) -> Generator[None, None, None]:
    """Time a stage, show a spinner while it runs, log elapsed on exit."""
    logger.info(">> %s started", stage_name)
    started = time.perf_counter()
    with console.status(f"[dim]{stage_name}…[/dim]", spinner="dots"):
        yield
    elapsed = time.perf_counter() - started
    logger.info(">> %s completed in %.1fs", stage_name, elapsed)


def log_startup_panel(
    *,
    target_input: str,
    url_count: int,
    workers: int,
    request_delay: float,
    mode: str,
    crawl_mode: str,
    output_filename: str,
) -> None:
    """Render a pre-crawl configuration summary panel."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold", justify="right")
    grid.add_column()
    grid.add_row("Target", target_input)
    grid.add_row("URLs", str(url_count))
    grid.add_row("Workers", f"{workers}  ·  Delay {request_delay}s")
    grid.add_row("Mode", mode)
    grid.add_row("Render", crawl_mode)
    grid.add_row("Output", output_filename)
    console.print(
        Panel(
            grid,
            title="[bold]hype-frog[/bold]  ·  Python SEO Auditor",
            border_style="cyan",
        )
    )


def log_completion_panel(
    *,
    output_filename: str,
    url_count: int,
    elapsed_seconds: float,
    pdf_filename: str | None = None,
) -> None:
    """Render a success panel after export finishes."""
    mins, secs = divmod(int(elapsed_seconds), 60)
    elapsed_str = f"{mins}m {secs}s" if mins else f"{secs}s"

    file_size = ""
    try:
        size_bytes = Path(output_filename).stat().st_size
        file_size = f"  ({size_bytes / 1_048_576:.1f} MB)"
    except OSError:
        pass

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold", justify="right")
    grid.add_column()
    grid.add_row("Crawled", f"{url_count} URLs in {elapsed_str}")
    grid.add_row("Workbook", f"{output_filename}{file_size}")
    if pdf_filename:
        grid.add_row("PDF", pdf_filename)
    console.print(
        Panel(grid, title="[bold green]Done[/bold green]", border_style="green")
    )
