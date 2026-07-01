"""Tests for startup environment validation."""

from __future__ import annotations

from hype_frog.core.env_config import validate_environment, validate_project_layout


def test_validate_project_layout_ok_in_repo(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("hype_frog.core.env_config.PROJECT_ROOT", tmp_path)
    monkeypatch.setattr("hype_frog.core.env_config.LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(
        "hype_frog.core.env_config.REPORTS_LATEST_DIR", tmp_path / "reports" / "latest"
    )
    monkeypatch.setattr(
        "hype_frog.core.env_config.REPORTS_ARCHIVE_DIR", tmp_path / "reports" / "archive"
    )
    monkeypatch.setattr("hype_frog.core.env_config.SECRETS_DIR", tmp_path / "secrets")

    result = validate_project_layout()
    assert result.ok
    assert (tmp_path / "logs").is_dir()


def test_validate_environment_warns_without_psi_key(monkeypatch) -> None:
    from hype_frog.core.env_config import EnvValidationResult

    monkeypatch.setattr("hype_frog.core.env_config.load_environment", lambda: None)
    monkeypatch.setattr(
        "hype_frog.core.env_config.validate_project_layout",
        lambda: EnvValidationResult(),
    )
    monkeypatch.setattr("hype_frog.core.env_config.get_psi_api_key", lambda: None)
    monkeypatch.setattr("hype_frog.core.env_config.get_hf_output_filename", lambda: None)

    result = validate_environment(context="crawl")
    assert result.ok
    assert any("PSI_API_KEY" in warning for warning in result.warnings)
