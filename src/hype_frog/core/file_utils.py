from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from hype_frog.config import REPORTS_LATEST_DIR
from hype_frog.core.text_utils import sanitize_filename_part


def build_output_filename(source_label: str, full_suite: bool = True) -> str:
    """Return path string under `reports/latest/` (directory created if needed)."""
    parsed = urlparse(source_label if "://" in source_label else f"https://{source_label}")
    source = sanitize_filename_part(parsed.netloc or source_label)
    REPORTS_LATEST_DIR.mkdir(parents=True, exist_ok=True)

    _ = full_suite  # retained for API parity with legacy callers
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base_name = f"SEO_AEO_Audit_{source}_{timestamp}"
    candidate = REPORTS_LATEST_DIR / f"{base_name}.xlsx"

    counter = 1
    while candidate.exists():
        candidate = REPORTS_LATEST_DIR / f"{base_name}_{counter}.xlsx"
        counter += 1

    return str(candidate.resolve())
