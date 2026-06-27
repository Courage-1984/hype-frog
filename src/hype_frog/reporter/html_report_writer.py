"""
Write the HTML executive report to disk alongside the xlsx workbook.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path

from hype_frog.config import resolve_project_relative_path
from hype_frog.core import get_logger
from hype_frog.reporter.html_report_data import ReportContext
from hype_frog.reporter.html_report_renderer import render_html_report

logger = get_logger(__name__)


def write_html_report(
    ctx: ReportContext,
    output_path: str | Path,
) -> Path:
    """Render and write the HTML executive report to disk. Returns the output path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    html_content = render_html_report(ctx)
    path.write_text(html_content, encoding="utf-8")
    logger.info("HTML executive report written to %s (%d bytes)", path, len(html_content))
    return path


def _load_logo_base64() -> str:
    """Load logo from HF_REPORT_LOGO_PATH env var. Returns data URI or empty string."""
    logo_path = os.environ.get("HF_REPORT_LOGO_PATH", "").strip()
    if not logo_path:
        return ""
    try:
        path = resolve_project_relative_path(logo_path)
        if not path.exists():
            logger.warning("HF_REPORT_LOGO_PATH does not exist: %s", path)
            return ""
        data = path.read_bytes()
        ext = path.suffix.lower().lstrip(".")
        mime = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "svg": "image/svg+xml",
            "webp": "image/webp",
        }.get(ext, "image/png")
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception as exc:
        logger.warning("Could not load logo from %s: %s", path, exc)
        return ""
