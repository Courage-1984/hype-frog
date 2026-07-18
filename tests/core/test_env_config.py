"""Tests for startup environment validation."""

from __future__ import annotations

import pytest

from hype_frog.core.env_config import (
    EnvConfigError,
    EnvValidationResult,
    require_valid_environment,
    validate_environment,
    validate_project_layout,
)


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


def test_env_validation_result_ok_is_false_with_any_error() -> None:
    result = EnvValidationResult()
    assert result.ok is True
    result.errors.append("something broke")
    assert result.ok is False


def test_validate_project_layout_missing_project_root_is_a_hard_error(
    tmp_path, monkeypatch
) -> None:
    missing = tmp_path / "does-not-exist"
    monkeypatch.setattr("hype_frog.core.env_config.PROJECT_ROOT", missing)

    result = validate_project_layout()

    assert not result.ok
    assert any("Project root does not exist" in err for err in result.errors)


def test_validate_project_layout_warns_when_secrets_dir_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("hype_frog.core.env_config.PROJECT_ROOT", tmp_path)
    monkeypatch.setattr("hype_frog.core.env_config.LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(
        "hype_frog.core.env_config.REPORTS_LATEST_DIR", tmp_path / "reports" / "latest"
    )
    monkeypatch.setattr(
        "hype_frog.core.env_config.REPORTS_ARCHIVE_DIR", tmp_path / "reports" / "archive"
    )
    monkeypatch.setattr("hype_frog.core.env_config.SECRETS_DIR", tmp_path / "secrets-absent")

    result = validate_project_layout()

    assert result.ok  # a missing secrets dir is a warning, not a hard error
    assert any("Secrets directory not found" in warning for warning in result.warnings)


def test_validate_project_layout_unwritable_dir_is_an_error(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("hype_frog.core.env_config.PROJECT_ROOT", tmp_path)
    # LOGS_DIR points at a path that can never be created/written: a file
    # already occupies where a parent directory would need to go.
    blocker = tmp_path / "blocker"
    blocker.write_text("occupied", encoding="utf-8")
    monkeypatch.setattr("hype_frog.core.env_config.LOGS_DIR", blocker / "logs")
    monkeypatch.setattr(
        "hype_frog.core.env_config.REPORTS_LATEST_DIR", tmp_path / "reports" / "latest"
    )
    monkeypatch.setattr(
        "hype_frog.core.env_config.REPORTS_ARCHIVE_DIR", tmp_path / "reports" / "archive"
    )
    monkeypatch.setattr("hype_frog.core.env_config.SECRETS_DIR", tmp_path / "secrets")

    result = validate_project_layout()

    assert not result.ok
    assert any("Logs directory is not writable" in err for err in result.errors)


def test_validate_environment_startup_context_has_no_psi_warning(monkeypatch) -> None:
    monkeypatch.setattr("hype_frog.core.env_config.load_environment", lambda: None)
    monkeypatch.setattr(
        "hype_frog.core.env_config.validate_project_layout", lambda: EnvValidationResult()
    )
    monkeypatch.setattr("hype_frog.core.env_config.get_psi_api_key", lambda: None)
    monkeypatch.setattr("hype_frog.core.env_config.get_hf_output_filename", lambda: None)

    result = validate_environment(context="startup")

    assert not any("PSI_API_KEY" in warning for warning in result.warnings)


def test_validate_environment_accurate_crawl_warns_when_playwright_missing(monkeypatch) -> None:
    import builtins

    monkeypatch.setattr("hype_frog.core.env_config.load_environment", lambda: None)
    monkeypatch.setattr(
        "hype_frog.core.env_config.validate_project_layout", lambda: EnvValidationResult()
    )
    monkeypatch.setattr("hype_frog.core.env_config.get_psi_api_key", lambda: "key-present")
    monkeypatch.setattr("hype_frog.core.env_config.get_hf_output_filename", lambda: None)

    real_import = builtins.__import__

    def _blocked_import(name, *args, **kwargs):
        if name == "playwright":
            raise ImportError("no playwright installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked_import)

    result = validate_environment(context="accurate_crawl")

    assert result.ok
    assert any("Playwright is not installed" in warning for warning in result.warnings)


def test_validate_environment_creates_output_filename_parent_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("hype_frog.core.env_config.load_environment", lambda: None)
    monkeypatch.setattr(
        "hype_frog.core.env_config.validate_project_layout", lambda: EnvValidationResult()
    )
    monkeypatch.setattr("hype_frog.core.env_config.get_psi_api_key", lambda: "key")
    target = tmp_path / "custom_reports" / "audit.xlsx"
    monkeypatch.setattr(
        "hype_frog.core.env_config.get_hf_output_filename", lambda: str(target)
    )

    result = validate_environment(context="startup")

    assert result.ok
    assert target.parent.is_dir()


# ---------------------------------------------------------------------------
# require_valid_environment
# ---------------------------------------------------------------------------


def test_require_valid_environment_passes_silently_when_ok(monkeypatch) -> None:
    monkeypatch.setattr(
        "hype_frog.core.env_config.validate_environment",
        lambda **_kwargs: EnvValidationResult(),
    )
    require_valid_environment(context="startup")  # must not raise


def test_require_valid_environment_raises_env_config_error_with_joined_messages(
    monkeypatch,
) -> None:
    failing = EnvValidationResult(errors=["error one", "error two"])
    monkeypatch.setattr(
        "hype_frog.core.env_config.validate_environment", lambda **_kwargs: failing
    )

    with pytest.raises(EnvConfigError) as exc:
        require_valid_environment(context="startup")

    assert "error one" in str(exc.value)
    assert "error two" in str(exc.value)
