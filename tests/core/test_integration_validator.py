"""Offline integration-validator checks (no live network or browser launch)."""

from __future__ import annotations

import json

from hype_frog.diagnostics import integration_validator as iv
from hype_frog.diagnostics.integration_validator import (
    CheckStatus,
    IntegrationCheck,
    check_environment_file,
    check_gsc_client_secrets,
    check_optional_llm_keys,
    check_psi_api_key_present,
    format_validation_report,
)


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
    checks = check_optional_llm_keys()
    assert {c.status for c in checks} == {CheckStatus.SKIP}

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-value")
    statuses = {c.name: c.status for c in check_optional_llm_keys()}
    assert statuses["Optional OPENAI_API_KEY"] == CheckStatus.PASS
    assert statuses["Optional ANTHROPIC_API_KEY"] == CheckStatus.SKIP


def test_playwright_install_hint_frozen_exe(monkeypatch) -> None:
    monkeypatch.setattr(iv.sys, "frozen", True, raising=False)
    assert iv._playwright_install_hint() == "./hype-frog.exe --install-playwright"


def test_playwright_install_hint_dev(monkeypatch) -> None:
    monkeypatch.setattr(iv.sys, "frozen", False, raising=False)
    assert iv._playwright_install_hint() == "uv run playwright install chromium"


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
