"""Systematic default/override coverage for every accessor in `core/env_vars.py`.

Before this file, of the 44 public getters here, only a handful were directly
asserted anywhere (mostly `get_hf_gsc_url_inspection`, `get_hf_max_memory_mb`,
plus a few set-but-not-asserted flags via `test_run_setup.py`). All PDF/HTML
branding, theme, snapshot-retention/db-path, and formatting-disable getters
had zero direct tests.
"""

from __future__ import annotations

import pytest

from hype_frog.core import env_vars


# ---------------------------------------------------------------------------
# Third-party API keys
# ---------------------------------------------------------------------------

def test_get_psi_api_key_default_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PSI_API_KEY", raising=False)
    assert env_vars.get_psi_api_key() is None


def test_get_psi_api_key_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PSI_API_KEY", "abc123")
    assert env_vars.get_psi_api_key() == "abc123"


def test_get_openai_api_key_default_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert env_vars.get_openai_api_key() is None


def test_get_openai_api_key_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert env_vars.get_openai_api_key() == "sk-test"


def test_get_openai_model_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    assert env_vars.get_openai_model() == "gpt-4o-mini"
    assert env_vars.get_openai_model(default="custom-default") == "custom-default"


def test_get_openai_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    assert env_vars.get_openai_model() == "gpt-4o"


def test_get_anthropic_api_key_default_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert env_vars.get_anthropic_api_key() is None


def test_get_anthropic_api_key_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-test")
    assert env_vars.get_anthropic_api_key() == "anthropic-test"


# ---------------------------------------------------------------------------
# HF_ runtime knobs
# ---------------------------------------------------------------------------

def test_get_hf_max_depth_default_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_MAX_DEPTH", raising=False)
    assert env_vars.get_hf_max_depth() is None


def test_get_hf_max_depth_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_MAX_DEPTH", "3")
    assert env_vars.get_hf_max_depth() == 3


def test_get_hf_max_depth_invalid_value_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_MAX_DEPTH", "not-an-int")
    assert env_vars.get_hf_max_depth() is None


def test_get_hf_max_memory_mb_default_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_MAX_MEMORY_MB", raising=False)
    assert env_vars.get_hf_max_memory_mb() is None


def test_get_hf_max_memory_mb_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_MAX_MEMORY_MB", "2048")
    assert env_vars.get_hf_max_memory_mb() == 2048


def test_get_hf_output_filename_default_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_OUTPUT_FILENAME", raising=False)
    assert env_vars.get_hf_output_filename() is None


def test_get_hf_output_filename_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_OUTPUT_FILENAME", "custom.xlsx")
    assert env_vars.get_hf_output_filename() == "custom.xlsx"


def test_set_env_default_if_blank_sets_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_MAX_DEPTH", raising=False)
    env_vars.set_env_default_if_blank("HF_MAX_DEPTH", "5")
    assert env_vars.get_hf_max_depth() == 5


def test_set_env_default_if_blank_sets_when_blank_string(monkeypatch: pytest.MonkeyPatch) -> None:
    """Blank-aware, unlike ``os.environ.setdefault`` — a present-but-empty value
    still gets the computed default."""
    monkeypatch.setenv("HF_OUTPUT_FILENAME", "")
    env_vars.set_env_default_if_blank("HF_OUTPUT_FILENAME", "computed.xlsx")
    assert env_vars.get_hf_output_filename() == "computed.xlsx"


def test_set_env_default_if_blank_does_not_override_existing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HF_OUTPUT_FILENAME", "user-chosen.xlsx")
    env_vars.set_env_default_if_blank("HF_OUTPUT_FILENAME", "computed.xlsx")
    assert env_vars.get_hf_output_filename() == "user-chosen.xlsx"


def test_get_hf_test_sitemap_url_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_TEST_SITEMAP_URL", raising=False)
    assert env_vars.get_hf_test_sitemap_url("https://default.example/sitemap.xml") == (
        "https://default.example/sitemap.xml"
    )


def test_get_hf_test_sitemap_url_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_TEST_SITEMAP_URL", "https://override.example/sitemap.xml")
    assert env_vars.get_hf_test_sitemap_url("https://default.example/sitemap.xml") == (
        "https://override.example/sitemap.xml"
    )


def test_get_hf_full_smoke_url_count_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_FULL_SMOKE_URL_COUNT", raising=False)
    assert env_vars.get_hf_full_smoke_url_count(80) == 80


def test_get_hf_full_smoke_url_count_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_FULL_SMOKE_URL_COUNT", "40")
    assert env_vars.get_hf_full_smoke_url_count(80) == 40


def test_get_hf_full_smoke_url_count_invalid_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HF_FULL_SMOKE_URL_COUNT", "nope")
    assert env_vars.get_hf_full_smoke_url_count(80) == 80


def test_get_hf_competitors_default_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_COMPETITORS", raising=False)
    assert env_vars.get_hf_competitors() == ""


def test_get_hf_competitors_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_COMPETITORS", "a.com,b.com")
    assert env_vars.get_hf_competitors() == "a.com,b.com"


def test_get_hf_previous_audit_path_default_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_PREVIOUS_AUDIT_PATH", raising=False)
    assert env_vars.get_hf_previous_audit_path() == ""


def test_get_hf_previous_audit_path_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_PREVIOUS_AUDIT_PATH", "prior.xlsx")
    assert env_vars.get_hf_previous_audit_path() == "prior.xlsx"


@pytest.mark.parametrize(
    ("getter_name", "env_name"),
    [
        ("get_hf_streaming", "HF_STREAMING"),
        ("get_hf_export_pdf", "HF_EXPORT_PDF"),
        ("get_hf_export_html", "HF_EXPORT_HTML"),
        ("get_check_og_images", "CHECK_OG_IMAGES"),
        ("get_check_content_images", "CHECK_CONTENT_IMAGES"),
        ("get_hf_regen_report", "HF_REGEN_REPORT"),
        ("get_hf_debug_excel_isolation_mode", "HF_DEBUG_EXCEL_ISOLATION_MODE"),
        ("get_hf_disable_data_validation", "HF_DISABLE_DATA_VALIDATION"),
        ("get_hf_disable_tooltips", "HF_DISABLE_TOOLTIPS"),
        ("get_hf_disable_conditional_formatting", "HF_DISABLE_CONDITIONAL_FORMATTING"),
        ("get_hf_disable_external_links_and_images", "HF_DISABLE_EXTERNAL_LINKS_AND_IMAGES"),
        ("get_hf_disable_non_core_freeze_panes", "HF_DISABLE_NON_CORE_FREEZE_PANES"),
    ],
)
def test_boolean_flag_defaults_false_when_unset(
    monkeypatch: pytest.MonkeyPatch, getter_name: str, env_name: str
) -> None:
    monkeypatch.delenv(env_name, raising=False)
    getter = getattr(env_vars, getter_name)
    assert getter() is False


@pytest.mark.parametrize(
    ("getter_name", "env_name", "truthy_value"),
    [
        ("get_hf_streaming", "HF_STREAMING", "1"),
        ("get_hf_export_pdf", "HF_EXPORT_PDF", "true"),
        ("get_hf_export_html", "HF_EXPORT_HTML", "yes"),
        ("get_check_og_images", "CHECK_OG_IMAGES", "y"),
        ("get_check_content_images", "CHECK_CONTENT_IMAGES", "1"),
        ("get_hf_regen_report", "HF_REGEN_REPORT", "true"),
        ("get_hf_debug_excel_isolation_mode", "HF_DEBUG_EXCEL_ISOLATION_MODE", "1"),
        ("get_hf_disable_data_validation", "HF_DISABLE_DATA_VALIDATION", "1"),
        ("get_hf_disable_tooltips", "HF_DISABLE_TOOLTIPS", "1"),
        ("get_hf_disable_conditional_formatting", "HF_DISABLE_CONDITIONAL_FORMATTING", "1"),
        ("get_hf_disable_external_links_and_images", "HF_DISABLE_EXTERNAL_LINKS_AND_IMAGES", "1"),
        ("get_hf_disable_non_core_freeze_panes", "HF_DISABLE_NON_CORE_FREEZE_PANES", "1"),
    ],
)
def test_boolean_flag_true_for_all_truthy_spellings(
    monkeypatch: pytest.MonkeyPatch, getter_name: str, env_name: str, truthy_value: str
) -> None:
    monkeypatch.setenv(env_name, truthy_value)
    getter = getattr(env_vars, getter_name)
    assert getter() is True


def test_boolean_flag_false_for_garbage_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_STREAMING", "maybe")
    assert env_vars.get_hf_streaming() is False


def test_get_hf_gsc_url_inspection_default_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GSC_URL_INSPECTION", raising=False)
    assert env_vars.get_hf_gsc_url_inspection() is None


@pytest.mark.parametrize("raw", ["full", "ALL", "all"])
def test_get_hf_gsc_url_inspection_full_mode(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv("GSC_URL_INSPECTION", raw)
    assert env_vars.get_hf_gsc_url_inspection() == "full"


@pytest.mark.parametrize("raw", ["1", "true", "yes", "limited"])
def test_get_hf_gsc_url_inspection_limited_mode(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv("GSC_URL_INSPECTION", raw)
    assert env_vars.get_hf_gsc_url_inspection() == "limited"


def test_get_hf_gsc_url_inspection_unrecognised_value_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GSC_URL_INSPECTION", "bogus")
    assert env_vars.get_hf_gsc_url_inspection() is None


def test_get_hf_snapshot_id_default_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_SNAPSHOT_ID", raising=False)
    assert env_vars.get_hf_snapshot_id() is None


def test_get_hf_snapshot_id_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_SNAPSHOT_ID", "snap-123")
    assert env_vars.get_hf_snapshot_id() == "snap-123"


def test_get_hf_snapshot_retention_per_domain_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HF_SNAPSHOT_RETENTION_PER_DOMAIN", raising=False)
    assert env_vars.get_hf_snapshot_retention_per_domain() == 10


def test_get_hf_snapshot_retention_per_domain_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HF_SNAPSHOT_RETENTION_PER_DOMAIN", "25")
    assert env_vars.get_hf_snapshot_retention_per_domain() == 25


def test_get_hf_snapshot_retention_per_domain_negative_clamped_to_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HF_SNAPSHOT_RETENTION_PER_DOMAIN", "-5")
    assert env_vars.get_hf_snapshot_retention_per_domain() == 0


def test_get_hf_snapshot_retention_per_domain_invalid_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HF_SNAPSHOT_RETENTION_PER_DOMAIN", "abc")
    assert env_vars.get_hf_snapshot_retention_per_domain() == 10


def test_get_hf_snapshots_db_path_default_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_SNAPSHOTS_DB_PATH", raising=False)
    assert env_vars.get_hf_snapshots_db_path() is None


def test_get_hf_snapshots_db_path_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_SNAPSHOTS_DB_PATH", "/tmp/snaps.sqlite")
    assert env_vars.get_hf_snapshots_db_path() == "/tmp/snaps.sqlite"


# ---------------------------------------------------------------------------
# Reporter / branding
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("getter_name", "env_name"),
    [
        ("get_hf_report_brand_colour", "HF_REPORT_BRAND_COLOUR"),
        ("get_hf_pdf_brand_colour", "HF_PDF_BRAND_COLOUR"),
        ("get_hf_report_prepared_by", "HF_REPORT_PREPARED_BY"),
        ("get_hf_pdf_prepared_by", "HF_PDF_PREPARED_BY"),
        ("get_hf_report_client_name", "HF_REPORT_CLIENT_NAME"),
        ("get_hf_pdf_client_name", "HF_PDF_CLIENT_NAME"),
        ("get_hf_pdf_logo_path", "HF_PDF_LOGO_PATH"),
        ("get_hf_report_logo_path", "HF_REPORT_LOGO_PATH"),
        ("get_hf_report_accent_colour_override", "HF_REPORT_ACCENT_COLOUR"),
    ],
)
def test_branding_getter_default_empty_string(
    monkeypatch: pytest.MonkeyPatch, getter_name: str, env_name: str
) -> None:
    monkeypatch.delenv(env_name, raising=False)
    getter = getattr(env_vars, getter_name)
    assert getter() == ""


@pytest.mark.parametrize(
    ("getter_name", "env_name", "value"),
    [
        ("get_hf_report_brand_colour", "HF_REPORT_BRAND_COLOUR", "#123456"),
        ("get_hf_pdf_brand_colour", "HF_PDF_BRAND_COLOUR", "#654321"),
        ("get_hf_report_prepared_by", "HF_REPORT_PREPARED_BY", "Jane Doe"),
        ("get_hf_pdf_prepared_by", "HF_PDF_PREPARED_BY", "John Doe"),
        ("get_hf_report_client_name", "HF_REPORT_CLIENT_NAME", "Acme Co"),
        ("get_hf_pdf_client_name", "HF_PDF_CLIENT_NAME", "Acme Inc"),
        ("get_hf_pdf_logo_path", "HF_PDF_LOGO_PATH", "logo.png"),
        ("get_hf_report_logo_path", "HF_REPORT_LOGO_PATH", "logo2.png"),
        ("get_hf_report_accent_colour_override", "HF_REPORT_ACCENT_COLOUR", "#abcdef"),
    ],
)
def test_branding_getter_override(
    monkeypatch: pytest.MonkeyPatch, getter_name: str, env_name: str, value: str
) -> None:
    monkeypatch.setenv(env_name, value)
    getter = getattr(env_vars, getter_name)
    assert getter() == value


def test_get_hf_report_accent_colour_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_REPORT_ACCENT_COLOUR", raising=False)
    assert env_vars.get_hf_report_accent_colour() == "#2563eb"
    assert env_vars.get_hf_report_accent_colour(default="#000000") == "#000000"


def test_get_hf_report_accent_colour_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_REPORT_ACCENT_COLOUR", "#ff00ff")
    assert env_vars.get_hf_report_accent_colour() == "#ff00ff"


def test_get_hf_report_theme_default_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_REPORT_THEME", raising=False)
    assert env_vars.get_hf_report_theme() == ""


def test_get_hf_report_theme_lowercased(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_REPORT_THEME", "MOCHA")
    assert env_vars.get_hf_report_theme() == "mocha"


def test_get_hf_excel_theme_default_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_EXCEL_THEME", raising=False)
    assert env_vars.get_hf_excel_theme() == ""


def test_get_hf_excel_theme_lowercased(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_EXCEL_THEME", "MOCHA")
    assert env_vars.get_hf_excel_theme() == "mocha"


# ---------------------------------------------------------------------------
# Logging / observability
# ---------------------------------------------------------------------------

def test_get_hf_log_level_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_LOG_LEVEL", raising=False)
    assert env_vars.get_hf_log_level() == "DEBUG"
    assert env_vars.get_hf_log_level(default="INFO") == "INFO"


def test_get_hf_log_level_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_LOG_LEVEL", "WARNING")
    assert env_vars.get_hf_log_level() == "WARNING"


def test_get_hf_console_log_level_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_CONSOLE_LOG_LEVEL", raising=False)
    assert env_vars.get_hf_console_log_level() == "INFO"
    assert env_vars.get_hf_console_log_level(default="ERROR") == "ERROR"


def test_get_hf_console_log_level_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_CONSOLE_LOG_LEVEL", "DEBUG")
    assert env_vars.get_hf_console_log_level() == "DEBUG"


def test_get_hf_run_id_default_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_RUN_ID", raising=False)
    assert env_vars.get_hf_run_id() == ""


def test_get_hf_run_id_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_RUN_ID", "run-42")
    assert env_vars.get_hf_run_id() == "run-42"


# ---------------------------------------------------------------------------
# Playwright / system paths
# ---------------------------------------------------------------------------

def test_get_playwright_browsers_path_default_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    assert env_vars.get_playwright_browsers_path() is None


def test_get_playwright_browsers_path_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", "C:/browsers")
    assert env_vars.get_playwright_browsers_path() == "C:/browsers"


def test_get_local_app_data_default_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    assert env_vars.get_local_app_data() is None


def test_get_local_app_data_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", "C:/Users/test/AppData/Local")
    assert env_vars.get_local_app_data() == "C:/Users/test/AppData/Local"


def test_set_playwright_browsers_path_writes_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    env_vars.set_playwright_browsers_path("D:/pw-browsers")
    assert env_vars.get_playwright_browsers_path() == "D:/pw-browsers"
