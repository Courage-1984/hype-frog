"""Centralised typed accessors for all environment variables used by hype-frog.

This is the ONLY module permitted to read ``os.environ`` / ``os.getenv``
directly (alongside ``config_loader.py`` which handles YAML overrides).
All domain modules must import from here instead of calling os.getenv.
"""

from __future__ import annotations

import os


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y"}


def _env_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


# ---------------------------------------------------------------------------
# Third-party API keys
# ---------------------------------------------------------------------------


def get_psi_api_key() -> str | None:
    return os.getenv("PSI_API_KEY") or None


def get_openai_api_key() -> str | None:
    value = _env_str("OPENAI_API_KEY")
    return value or None


def get_openai_model(default: str = "gpt-4o-mini") -> str:
    return _env_str("OPENAI_MODEL") or default


def get_anthropic_api_key() -> str | None:
    value = _env_str("ANTHROPIC_API_KEY")
    return value or None


# ---------------------------------------------------------------------------
# HF_ runtime knobs
# ---------------------------------------------------------------------------


def get_hf_max_depth() -> int | None:
    raw = _env_str("HF_MAX_DEPTH")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def get_hf_max_memory_mb() -> int | None:
    raw = _env_str("HF_MAX_MEMORY_MB")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def get_hf_output_filename() -> str | None:
    return _env_str("HF_OUTPUT_FILENAME") or None


def get_hf_test_sitemap_url(default: str) -> str:
    """Override the sitemap URL used by --quick-test / --full-smoke-test."""
    return _env_str("HF_TEST_SITEMAP_URL") or default


def get_hf_full_smoke_url_count(default: int) -> int:
    raw = _env_str("HF_FULL_SMOKE_URL_COUNT")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def get_hf_competitors() -> str:
    return os.getenv("HF_COMPETITORS", "")


def get_hf_previous_audit_path() -> str:
    return _env_str("HF_PREVIOUS_AUDIT_PATH")


def get_hf_streaming() -> bool:
    return _env_flag("HF_STREAMING")


def get_hf_export_pdf() -> bool:
    return _env_flag("HF_EXPORT_PDF")


def get_hf_export_html() -> bool:
    return _env_flag("HF_EXPORT_HTML")


def get_hf_gsc_url_inspection() -> str | None:
    mode = _env_str("GSC_URL_INSPECTION").lower()
    if mode in {"full", "all"}:
        return "full"
    if mode in {"1", "true", "yes", "limited"}:
        return "limited"
    return None


def get_check_og_images() -> bool:
    return _env_flag("CHECK_OG_IMAGES")


def get_check_content_images() -> bool:
    return _env_flag("CHECK_CONTENT_IMAGES")


# ---------------------------------------------------------------------------
# Reporter / branding
# ---------------------------------------------------------------------------


def get_hf_report_brand_colour() -> str:
    return _env_str("HF_REPORT_BRAND_COLOUR")


def get_hf_pdf_brand_colour() -> str:
    return _env_str("HF_PDF_BRAND_COLOUR")


def get_hf_report_prepared_by() -> str:
    return _env_str("HF_REPORT_PREPARED_BY")


def get_hf_pdf_prepared_by() -> str:
    return _env_str("HF_PDF_PREPARED_BY")


def get_hf_report_client_name() -> str:
    return _env_str("HF_REPORT_CLIENT_NAME")


def get_hf_pdf_client_name() -> str:
    return _env_str("HF_PDF_CLIENT_NAME")


def get_hf_pdf_logo_path() -> str:
    return _env_str("HF_PDF_LOGO_PATH")


def get_hf_report_logo_path() -> str:
    return _env_str("HF_REPORT_LOGO_PATH")


def get_hf_report_accent_colour(default: str = "#2563eb") -> str:
    return _env_str("HF_REPORT_ACCENT_COLOUR") or default


def get_hf_report_accent_colour_override() -> str:
    """Return HF_REPORT_ACCENT_COLOUR only when explicitly set (no default)."""
    return _env_str("HF_REPORT_ACCENT_COLOUR")


def get_hf_report_theme() -> str:
    return _env_str("HF_REPORT_THEME").lower()


def get_hf_excel_theme() -> str:
    return _env_str("HF_EXCEL_THEME").lower()


# ---------------------------------------------------------------------------
# Reporter debug / isolation flags
# ---------------------------------------------------------------------------


def get_hf_debug_excel_isolation_mode() -> bool:
    return _env_flag("HF_DEBUG_EXCEL_ISOLATION_MODE")


def get_hf_disable_data_validation() -> bool:
    return _env_flag("HF_DISABLE_DATA_VALIDATION")


def get_hf_disable_tooltips() -> bool:
    return _env_flag("HF_DISABLE_TOOLTIPS")


def get_hf_disable_conditional_formatting() -> bool:
    return _env_flag("HF_DISABLE_CONDITIONAL_FORMATTING")


def get_hf_disable_external_links_and_images() -> bool:
    return _env_flag("HF_DISABLE_EXTERNAL_LINKS_AND_IMAGES")


def get_hf_disable_non_core_freeze_panes() -> bool:
    return _env_flag("HF_DISABLE_NON_CORE_FREEZE_PANES")


# ---------------------------------------------------------------------------
# Playwright / system paths
# ---------------------------------------------------------------------------


def get_playwright_browsers_path() -> str | None:
    return os.environ.get("PLAYWRIGHT_BROWSERS_PATH")


def get_local_app_data() -> str | None:
    return os.environ.get("LOCALAPPDATA")


def set_playwright_browsers_path(path: str) -> None:
    """Set PLAYWRIGHT_BROWSERS_PATH — the only permitted env write outside config_loader."""
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = path
