"""Centralised tuning defaults for crawl, enrichment, scoring, and reporting.

This is the SINGLE SOURCE OF TRUTH for all numeric and string defaults.
- env_vars.py accessors may fall back to constants defined here — never use
  raw literals in env_vars.py.
- Domain modules that need a threshold must import the named constant from
  here; never define the same value inline in the module.
"""

from __future__ import annotations

from typing import Any

# --- Content / duplication ---
THIN_CONTENT_WORD_THRESHOLD: int = 200
NEAR_DUPLICATE_SIMHASH_DISTANCE: int = 8

# --- PSI API pacing ---
PSI_BASE_DELAY_SECONDS: float = 2.5
PSI_JITTER_FRACTION: float = 0.3
PSI_STRATEGY_GAP_SECONDS: float = 0.35

# --- Crawl / HTTP ---
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

# --- Checkpointing ---
CHECKPOINT_EVERY_N_PAGES: int = 50

# --- Crawl replay snapshots (post-enrichment report regeneration) ---
SNAPSHOT_RETENTION_PER_DOMAIN_DEFAULT: int = 10
CRAWL_SNAPSHOTS_DB_RELATIVE: str = ".cache/crawl_snapshots.sqlite"

# --- Core Web Vitals / lab thresholds (registry rules) ---
CWV_LCP_CRITICAL_THRESHOLD: float = 4.0
CWV_LCP_WARNING_THRESHOLD: float = 2.5
LAB_TBT_CRITICAL_MS: int = 300
LAB_TBT_WARNING_MS: int = 150
CWV_INP_WARNING_MS: int = 200

# --- Content freshness ---
CONTENT_AGE_STALE_DAYS: int = 730
CONTENT_AGE_AGEING_DAYS: int = 365
CONTENT_AGE_RECENT_DAYS: int = 90

# --- Quick Wins tab ---
QUICK_WINS_MAX_EFFORT_HOURS: float = 4.0
QUICK_WINS_MAX_RESULTS: int = 15

# --- E-E-A-T ---
EEAT_LOW_SCORE_THRESHOLD: int = 3

# --- Image / script / link thresholds ---
LARGE_IMAGE_SIZE_KB: int = 200
UNDER_LINKED_INBOUND_THRESHOLD: int = 3
GENERIC_ANCHOR_DOMINANCE_PCT: int = 50
HIGH_THIRD_PARTY_SCRIPT_COUNT: int = 10

# CMS / WooCommerce action query parameters — blocked from crawl queue (see crawl_runner).
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

USER_CONFIG_KEYS: frozenset[str] = frozenset(
    {
        "THIN_CONTENT_WORD_THRESHOLD",
        "NEAR_DUPLICATE_SIMHASH_DISTANCE",
        "PSI_BASE_DELAY_SECONDS",
        "PSI_JITTER_FRACTION",
        "PSI_STRATEGY_GAP_SECONDS",
        "MAX_WORKERS",
        "DELAY_BETWEEN_REQUESTS",
        "REQUEST_JITTER_SECONDS",
        "TIMEOUT_SECONDS",
        "CONNECT_TIMEOUT_SECONDS",
        "READ_TIMEOUT_SECONDS",
        "CHECKPOINT_EVERY_N_PAGES",
        "CWV_LCP_CRITICAL_THRESHOLD",
        "CWV_LCP_WARNING_THRESHOLD",
        "LAB_TBT_CRITICAL_MS",
        "LAB_TBT_WARNING_MS",
        "CWV_INP_WARNING_MS",
        "CONTENT_AGE_STALE_DAYS",
        "CONTENT_AGE_AGEING_DAYS",
        "CONTENT_AGE_RECENT_DAYS",
        "QUICK_WINS_MAX_EFFORT_HOURS",
        "QUICK_WINS_MAX_RESULTS",
        "EEAT_LOW_SCORE_THRESHOLD",
        "LARGE_IMAGE_SIZE_KB",
        "UNDER_LINKED_INBOUND_THRESHOLD",
        "GENERIC_ANCHOR_DOMINANCE_PCT",
        "HIGH_THIRD_PARTY_SCRIPT_COUNT",
    }
)

_RUNTIME_OVERRIDES: dict[str, Any] = {}


def apply_runtime_override(key: str, value: object) -> None:
    """Apply a CLI or YAML override for a known defaults key."""
    if key not in USER_CONFIG_KEYS:
        raise ValueError(f"Unknown config key: {key}")
    _RUNTIME_OVERRIDES[key] = value


def _resolve_int(key: str, default: int) -> int:
    raw = _RUNTIME_OVERRIDES.get(key, default)
    return int(raw)


def _resolve_float(key: str, default: float) -> float:
    raw = _RUNTIME_OVERRIDES.get(key, default)
    return float(raw)


def get_psi_base_delay_seconds() -> float:
    return _resolve_float("PSI_BASE_DELAY_SECONDS", PSI_BASE_DELAY_SECONDS)


def get_psi_jitter_fraction() -> float:
    return _resolve_float("PSI_JITTER_FRACTION", PSI_JITTER_FRACTION)


def get_psi_strategy_gap_seconds() -> float:
    return _resolve_float("PSI_STRATEGY_GAP_SECONDS", PSI_STRATEGY_GAP_SECONDS)


def get_delay_between_requests() -> float:
    return _resolve_float("DELAY_BETWEEN_REQUESTS", DELAY_BETWEEN_REQUESTS)


def get_request_jitter_seconds() -> float:
    return _resolve_float("REQUEST_JITTER_SECONDS", REQUEST_JITTER_SECONDS)


def get_thin_content_word_threshold() -> int:
    return _resolve_int("THIN_CONTENT_WORD_THRESHOLD", THIN_CONTENT_WORD_THRESHOLD)


def get_near_duplicate_simhash_distance() -> int:
    return _resolve_int("NEAR_DUPLICATE_SIMHASH_DISTANCE", NEAR_DUPLICATE_SIMHASH_DISTANCE)


def get_content_age_stale_days() -> int:
    return _resolve_int("CONTENT_AGE_STALE_DAYS", CONTENT_AGE_STALE_DAYS)


def get_content_age_ageing_days() -> int:
    return _resolve_int("CONTENT_AGE_AGEING_DAYS", CONTENT_AGE_AGEING_DAYS)


def get_content_age_recent_days() -> int:
    return _resolve_int("CONTENT_AGE_RECENT_DAYS", CONTENT_AGE_RECENT_DAYS)


def get_quick_wins_max_effort_hours() -> float:
    return _resolve_float("QUICK_WINS_MAX_EFFORT_HOURS", QUICK_WINS_MAX_EFFORT_HOURS)


def get_quick_wins_max_results() -> int:
    return _resolve_int("QUICK_WINS_MAX_RESULTS", QUICK_WINS_MAX_RESULTS)


def get_cwv_lcp_critical_threshold() -> float:
    return _resolve_float("CWV_LCP_CRITICAL_THRESHOLD", CWV_LCP_CRITICAL_THRESHOLD)


def get_cwv_lcp_warning_threshold() -> float:
    return _resolve_float("CWV_LCP_WARNING_THRESHOLD", CWV_LCP_WARNING_THRESHOLD)


def get_lab_tbt_critical_ms() -> int:
    return _resolve_int("LAB_TBT_CRITICAL_MS", LAB_TBT_CRITICAL_MS)


def get_cwv_inp_warning_ms() -> int:
    return _resolve_int("CWV_INP_WARNING_MS", CWV_INP_WARNING_MS)


def get_large_image_size_kb() -> int:
    return _resolve_int("LARGE_IMAGE_SIZE_KB", LARGE_IMAGE_SIZE_KB)


def get_high_third_party_script_count() -> int:
    return _resolve_int("HIGH_THIRD_PARTY_SCRIPT_COUNT", HIGH_THIRD_PARTY_SCRIPT_COUNT)
