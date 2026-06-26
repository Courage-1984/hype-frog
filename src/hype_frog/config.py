"""Central configuration, paths, and environment loading."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

# --- Repository layout (config.py lives at src/hype_frog/config.py) ---
PACKAGE_ROOT: Path = Path(__file__).resolve().parent
PROJECT_ROOT: Path = PACKAGE_ROOT.parent.parent
SRC_ROOT: Path = PACKAGE_ROOT.parent
DATA_DIR: Path = PROJECT_ROOT / "data"
SECRETS_DIR: Path = PROJECT_ROOT / "secrets"
LOGS_DIR: Path = PROJECT_ROOT / "logs"
REPORTS_LATEST_DIR: Path = PROJECT_ROOT / "reports" / "latest"
REPORTS_ARCHIVE_DIR: Path = PROJECT_ROOT / "reports" / "archive"


def load_environment() -> None:
    """Load `.env` from project root (no-op if missing)."""
    load_dotenv(PROJECT_ROOT / ".env")


# --- Crawl / HTTP defaults (parity with legacy root config.py) ---
MAX_WORKERS: int = 3
DELAY_BETWEEN_REQUESTS: float = 2.5
REQUEST_JITTER_SECONDS: float = 0.6
TIMEOUT_SECONDS: int = 20
CONNECT_TIMEOUT_SECONDS: int = 8
READ_TIMEOUT_SECONDS: int = 20
HTTP_CONNECTOR_LIMIT: int = 100
HTTP_CONNECTOR_LIMIT_PER_HOST: int = 20
HTTP_CONNECTOR_KEEPALIVE_TIMEOUT: int = 30
PLAYWRIGHT_MAX_SESSIONS: int = 3
MAX_RETRIES: int = 3
RETRY_BASE_DELAY_SECONDS: float = 2.0
RETRY_BACKOFF_FACTOR: float = 2.0
RETRY_MAX_DELAY_SECONDS: float = 20.0
RETRYABLE_STATUS_CODES: set[int] = {408, 425, 429, 500, 502, 503, 504}
OUTPUT_FILENAME: str = "seo_audit_report.xlsx"

# CMS / WooCommerce action query parameters — blocked from crawl queue (see crawl_runner).
# Safe params such as page, lang, paged, orderby are intentionally omitted.
EXCLUDED_CMS_ACTION_QUERY_PARAMS: frozenset[str] = frozenset(
    {
        "add-to-cart",
        "removed_item",
        "undo_item",
        "wc-ajax",
        "add_to_wishlist",
        "share_token",
        "preview_id",
        "preview_nonce",
        "preview",
    }
)
DEFAULT_OWNER_BY_SEVERITY: dict[str, str] = {
    "Critical": "Dev",
    "Warning": "Copy Writer",
    "Observation": "Copy Writer",
}
DEFAULT_EFFORT_BY_SEVERITY: dict[str, str] = {
    "Critical": "M",
    "Warning": "S",
    "Observation": "S",
}
