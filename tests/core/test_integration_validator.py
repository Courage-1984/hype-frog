"""Offline integration-validator checks (no live network or browser launch)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from hype_frog.diagnostics import integration_validator as iv
from hype_frog.diagnostics.integration_validator import (
    CheckStatus,
    IntegrationCheck,
    check_environment_file,
    check_gsc_api,
    check_gsc_client_secrets,
    check_gsc_token_file,
    check_optional_llm_keys,
    check_playwright_chromium,
    check_psi_api_key_present,
    check_psi_api_live,
    check_semantic_engine,
    format_validation_report,
    run_integration_validation,
    run_validation_cli,
)
from hype_frog.extractors.semantic_setup import SemanticEngineProbe, SemanticEngineStatus


def test_check_environment_file_present_and_absent(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(iv, "PROJECT_ROOT", tmp_path)
    assert check_environment_file().status == CheckStatus.WARN

    (tmp_path / ".env").write_text("PSI_API_KEY=abc", encoding="utf-8")
    assert check_environment_file().status == CheckStatus.PASS


def test_check_gsc_client_secrets_missing(monkeypatch, tmp_path) -> None:
    missing = tmp_path / "client_secrets.json"
    monkeypatch.setattr(iv, "resolve_gsc_credentials_path", lambda: missing)
    result = check_gsc_client_secrets()
    assert result.status == CheckStatus.FAIL
    assert "not found" in result.message.lower()


def test_check_gsc_client_secrets_invalid_json(monkeypatch, tmp_path) -> None:
    path = tmp_path / "client_secrets.json"
    path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(iv, "resolve_gsc_credentials_path", lambda: path)
    assert check_gsc_client_secrets().status == CheckStatus.FAIL


def test_check_gsc_client_secrets_installed_block_passes(monkeypatch, tmp_path) -> None:
    path = tmp_path / "client_secrets.json"
    path.write_text(
        json.dumps({"installed": {"client_id": "abc123.apps", "project_id": "proj"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(iv, "resolve_gsc_credentials_path", lambda: path)
    result = check_gsc_client_secrets()
    assert result.status == CheckStatus.PASS
    # Client id is masked in the rendered details, never shown in full.
    assert result.details["client_id"] != "abc123.apps"


def test_check_gsc_client_secrets_web_block_warns(monkeypatch, tmp_path) -> None:
    path = tmp_path / "client_secrets.json"
    path.write_text(json.dumps({"web": {"client_id": "abc123.apps"}}), encoding="utf-8")
    monkeypatch.setattr(iv, "resolve_gsc_credentials_path", lambda: path)
    assert check_gsc_client_secrets().status == CheckStatus.WARN


def test_check_gsc_client_secrets_missing_client_id_fails(monkeypatch, tmp_path) -> None:
    path = tmp_path / "client_secrets.json"
    path.write_text(json.dumps({"installed": {"project_id": "proj"}}), encoding="utf-8")
    monkeypatch.setattr(iv, "resolve_gsc_credentials_path", lambda: path)
    assert check_gsc_client_secrets().status == CheckStatus.FAIL


def test_check_psi_api_key_present(monkeypatch) -> None:
    monkeypatch.setattr(iv, "get_psi_api_key", lambda: "")
    assert check_psi_api_key_present().status == CheckStatus.FAIL

    monkeypatch.setattr(iv, "get_psi_api_key", lambda: "a-real-looking-psi-key")
    assert check_psi_api_key_present().status == CheckStatus.PASS


def test_check_optional_llm_keys(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    statuses = {c.name: c.status for c in check_optional_llm_keys()}
    assert statuses["Optional OPENAI_API_KEY"] == CheckStatus.SKIP
    assert statuses["Optional ANTHROPIC_API_KEY"] == CheckStatus.SKIP
    # No key and no local base URL: heuristic-fallback warning surfaces.
    assert statuses["Search Intent classifier"] == CheckStatus.WARN

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-value")
    statuses = {c.name: c.status for c in check_optional_llm_keys()}
    assert statuses["Optional OPENAI_API_KEY"] == CheckStatus.PASS
    assert statuses["Optional ANTHROPIC_API_KEY"] == CheckStatus.SKIP
    assert "Search Intent classifier" not in statuses


def test_check_optional_llm_keys_local_base_url_passes_without_api_key(
    monkeypatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    statuses = {c.name: c.status for c in check_optional_llm_keys()}
    assert statuses["OPENAI_BASE_URL"] == CheckStatus.PASS
    assert "Search Intent classifier" not in statuses


def test_playwright_install_hint_frozen_exe(monkeypatch) -> None:
    monkeypatch.setattr(iv.sys, "frozen", True, raising=False)
    assert iv._playwright_install_hint() == "./hype-frog.exe --install-playwright"


def test_playwright_install_hint_dev(monkeypatch) -> None:
    monkeypatch.setattr(iv.sys, "frozen", False, raising=False)
    assert iv._playwright_install_hint() == "uv run playwright install chromium"


def test_check_gsc_token_file_missing(monkeypatch, tmp_path) -> None:
    missing = tmp_path / "token.json"
    monkeypatch.setattr(iv, "resolve_gsc_token_path", lambda: missing)
    result = check_gsc_token_file()
    assert result.status == CheckStatus.FAIL
    assert "not found" in result.message.lower()


def test_check_gsc_token_file_load_failure(monkeypatch, tmp_path) -> None:
    present = tmp_path / "token.json"
    present.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(iv, "resolve_gsc_token_path", lambda: present)
    monkeypatch.setattr(iv, "load_gsc_credentials_readonly", lambda: (None, "token expired"))
    result = check_gsc_token_file()
    assert result.status == CheckStatus.FAIL
    assert result.message == "token expired"


def test_check_gsc_token_file_success(monkeypatch, tmp_path) -> None:
    present = tmp_path / "token.json"
    present.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(iv, "resolve_gsc_token_path", lambda: present)
    fake_creds = MagicMock()
    fake_creds.expiry = None
    monkeypatch.setattr(iv, "load_gsc_credentials_readonly", lambda: (fake_creds, None))
    result = check_gsc_token_file()
    assert result.status == CheckStatus.PASS
    assert result.details["expiry"] == "<unknown>"


def test_check_gsc_api_success_no_target(monkeypatch) -> None:
    sites = ["https://a.test/"]
    monkeypatch.setattr(
        iv, "probe_gsc_api_access", lambda target_url=None: (True, "reachable", sites, None)
    )
    result = check_gsc_api(None)
    assert result.status == CheckStatus.PASS
    assert result.details["visible_properties"] == sites


def test_check_gsc_api_target_url_with_no_property_match_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        iv,
        "probe_gsc_api_access",
        lambda target_url=None: (True, "reachable", ["https://a.test/"], None),
    )
    result = check_gsc_api("https://unrelated.example.com/")
    assert result.status == CheckStatus.FAIL


def test_check_gsc_api_target_url_matched_property_passes(monkeypatch) -> None:
    monkeypatch.setattr(
        iv,
        "probe_gsc_api_access",
        lambda target_url=None: (True, "reachable", ["https://a.test/"], "https://a.test/"),
    )
    result = check_gsc_api("https://a.test/page")
    assert result.status == CheckStatus.PASS
    assert result.details["matched_property"] == "https://a.test/"


def test_check_gsc_api_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        iv, "probe_gsc_api_access", lambda target_url=None: (False, "API disabled", [], None)
    )
    result = check_gsc_api(None)
    assert result.status == CheckStatus.FAIL


def test_check_semantic_engine_ready(monkeypatch) -> None:
    monkeypatch.setattr(
        iv,
        "probe_semantic_engine",
        lambda: SemanticEngineProbe(status=SemanticEngineStatus.READY, message="ready to go"),
    )
    result = check_semantic_engine()
    assert result.status == CheckStatus.PASS
    assert result.details["mode"] == "spaCy NER"


def test_check_semantic_engine_not_ready_warns(monkeypatch) -> None:
    monkeypatch.setattr(
        iv,
        "probe_semantic_engine",
        lambda: SemanticEngineProbe(
            status=SemanticEngineStatus.SPACY_MISSING, message="spaCy not installed."
        ),
    )
    result = check_semantic_engine()
    assert result.status == CheckStatus.WARN
    assert "keyword fallback" in result.message.lower()
    assert result.details["mode"] == "Keyword fallback"


@pytest.mark.asyncio
async def test_check_psi_api_live_success(monkeypatch) -> None:
    monkeypatch.setattr(
        iv,
        "probe_psi_api_key",
        AsyncMock(return_value=(True, "reachable", {"http_status": 200, "lab_metrics": None})),
    )
    result = await check_psi_api_live("https://example.com")
    assert result.status == CheckStatus.PASS


@pytest.mark.asyncio
async def test_check_psi_api_live_rate_limited_warns(monkeypatch) -> None:
    monkeypatch.setattr(
        iv, "probe_psi_api_key", AsyncMock(return_value=(True, "quota hit", {"http_status": 429}))
    )
    result = await check_psi_api_live("https://example.com")
    assert result.status == CheckStatus.WARN


@pytest.mark.asyncio
async def test_check_psi_api_live_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        iv, "probe_psi_api_key", AsyncMock(return_value=(False, "unreachable", None))
    )
    result = await check_psi_api_live("https://example.com")
    assert result.status == CheckStatus.FAIL


@pytest.mark.asyncio
async def test_check_playwright_chromium_not_installed(monkeypatch) -> None:
    monkeypatch.setattr(
        "hype_frog.crawler.fetcher.configure_playwright_browsers_path", lambda: None
    )
    import builtins

    real_import = builtins.__import__

    def _blocked_import(name, *args, **kwargs):
        if name == "playwright.async_api" or name.startswith("playwright"):
            raise ImportError("playwright not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked_import)

    result = await check_playwright_chromium()

    assert result.status == CheckStatus.FAIL
    assert "not installed" in result.message.lower()


# ---------------------------------------------------------------------------
# run_integration_validation — SKIP-branch orchestration
# ---------------------------------------------------------------------------


def _patch_common_checks(monkeypatch, *, token_status: CheckStatus, psi_key_status: CheckStatus) -> None:
    monkeypatch.setattr(
        iv,
        "check_environment_file",
        lambda: IntegrationCheck(name="Environment file", status=CheckStatus.PASS, message="ok"),
    )
    monkeypatch.setattr(
        iv,
        "check_gsc_client_secrets",
        lambda: IntegrationCheck(name="GSC client_secrets.json", status=CheckStatus.PASS, message="ok"),
    )
    monkeypatch.setattr(
        iv,
        "check_gsc_token_file",
        lambda: IntegrationCheck(name="GSC token.json", status=token_status, message="."),
    )
    monkeypatch.setattr(
        iv,
        "check_psi_api_key_present",
        lambda: IntegrationCheck(name="PSI API key", status=psi_key_status, message="."),
    )
    monkeypatch.setattr(iv, "check_optional_llm_keys", lambda: [])
    monkeypatch.setattr(
        iv,
        "check_semantic_engine",
        lambda: IntegrationCheck(name="Semantic engine (spaCy NER)", status=CheckStatus.PASS, message="."),
    )
    monkeypatch.setattr(
        iv, "check_playwright_chromium", AsyncMock(
            return_value=IntegrationCheck(name="Playwright (Chromium)", status=CheckStatus.PASS, message=".")
        )
    )


@pytest.mark.asyncio
async def test_run_integration_validation_skips_gsc_api_when_token_not_ready(
    monkeypatch,
) -> None:
    monkeypatch.setattr(iv, "load_environment", lambda: None)
    _patch_common_checks(monkeypatch, token_status=CheckStatus.FAIL, psi_key_status=CheckStatus.PASS)
    monkeypatch.setattr(
        iv, "check_psi_api_live", AsyncMock(
            return_value=IntegrationCheck(name="PSI API live probe", status=CheckStatus.PASS, message=".")
        )
    )

    checks = await run_integration_validation()

    gsc_api_check = next(c for c in checks if c.name == "GSC Search Console API")
    assert gsc_api_check.status == CheckStatus.SKIP


@pytest.mark.asyncio
async def test_run_integration_validation_skips_psi_live_when_key_missing(
    monkeypatch,
) -> None:
    monkeypatch.setattr(iv, "load_environment", lambda: None)
    _patch_common_checks(monkeypatch, token_status=CheckStatus.PASS, psi_key_status=CheckStatus.FAIL)
    monkeypatch.setattr(
        iv, "check_gsc_api",
        lambda target_url: IntegrationCheck(name="GSC Search Console API", status=CheckStatus.PASS, message="."),
    )

    checks = await run_integration_validation()

    psi_live_check = next(c for c in checks if c.name == "PSI API live probe")
    assert psi_live_check.status == CheckStatus.SKIP


# ---------------------------------------------------------------------------
# run_validation_cli
# ---------------------------------------------------------------------------


def test_run_validation_cli_returns_zero_when_no_failures(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        iv,
        "run_integration_validation",
        AsyncMock(
            return_value=[
                IntegrationCheck(name="A", status=CheckStatus.PASS, message="ok"),
                IntegrationCheck(name="B", status=CheckStatus.WARN, message="warn"),
            ]
        ),
    )
    exit_code = run_validation_cli()
    assert exit_code == 0


def test_run_validation_cli_returns_one_when_any_check_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        iv,
        "run_integration_validation",
        AsyncMock(
            return_value=[
                IntegrationCheck(name="A", status=CheckStatus.PASS, message="ok"),
                IntegrationCheck(name="B", status=CheckStatus.FAIL, message="bad"),
            ]
        ),
    )
    exit_code = run_validation_cli()
    assert exit_code == 1


def test_format_validation_report_counts_and_icons() -> None:
    checks = [
        IntegrationCheck(name="A", status=CheckStatus.PASS, message="ok"),
        IntegrationCheck(name="B", status=CheckStatus.WARN, message="warn"),
        IntegrationCheck(name="C", status=CheckStatus.FAIL, message="bad"),
        IntegrationCheck(name="D", status=CheckStatus.SKIP, message="skip"),
    ]
    report = format_validation_report(checks)
    assert "[PASS] A" in report
    assert "[FAIL] C" in report
    assert "1 passed, 1 warnings, 1 failed, 1 skipped" in report
