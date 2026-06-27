"""Central configuration, paths, and environment loading."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

from hype_frog.config_defaults import (
    CHECKPOINT_EVERY_N_PAGES,
    CONNECT_TIMEOUT_SECONDS,
    CONTENT_AGE_AGEING_DAYS,
    CONTENT_AGE_RECENT_DAYS,
    CONTENT_AGE_STALE_DAYS,
    CWV_INP_WARNING_MS,
    CWV_LCP_CRITICAL_THRESHOLD,
    CWV_LCP_WARNING_THRESHOLD,
    DEFAULT_EFFORT_BY_SEVERITY,
    DEFAULT_OWNER_BY_SEVERITY,
    DELAY_BETWEEN_REQUESTS,
    EEAT_LOW_SCORE_THRESHOLD,
    EXCLUDED_CMS_ACTION_QUERY_PARAMS,
    HTTP_CONNECTOR_KEEPALIVE_TIMEOUT,
    HTTP_CONNECTOR_LIMIT,
    HTTP_CONNECTOR_LIMIT_PER_HOST,
    LAB_TBT_CRITICAL_MS,
    LAB_TBT_WARNING_MS,
    MAX_RETRIES,
    MAX_WORKERS,
    NEAR_DUPLICATE_SIMHASH_DISTANCE,
    OUTPUT_FILENAME,
    PLAYWRIGHT_MAX_SESSIONS,
    PSI_BASE_DELAY_SECONDS,
    PSI_JITTER_FRACTION,
    PSI_STRATEGY_GAP_SECONDS,
    QUICK_WINS_MAX_EFFORT_HOURS,
    QUICK_WINS_MAX_RESULTS,
    READ_TIMEOUT_SECONDS,
    REQUEST_JITTER_SECONDS,
    RETRY_BACKOFF_FACTOR,
    RETRY_BASE_DELAY_SECONDS,
    RETRY_MAX_DELAY_SECONDS,
    RETRYABLE_STATUS_CODES,
    THIN_CONTENT_WORD_THRESHOLD,
    TIMEOUT_SECONDS,
    apply_runtime_override,
    get_content_age_ageing_days,
    get_content_age_recent_days,
    get_content_age_stale_days,
    get_cwv_inp_warning_ms,
    get_cwv_lcp_critical_threshold,
    get_cwv_lcp_warning_threshold,
    get_delay_between_requests,
    get_high_third_party_script_count,
    get_lab_tbt_critical_ms,
    get_near_duplicate_simhash_distance,
    get_psi_base_delay_seconds,
    get_psi_jitter_fraction,
    get_psi_strategy_gap_seconds,
    get_quick_wins_max_effort_hours,
    get_quick_wins_max_results,
    get_request_jitter_seconds,
    get_thin_content_word_threshold,
)
from hype_frog.config_loader import apply_user_config, load_user_config

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
    """Load ``.env`` and optional ``hype_frog.config.yaml`` from the project root."""
    load_dotenv(PROJECT_ROOT / ".env")
    apply_user_config(PROJECT_ROOT)
