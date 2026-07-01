"""Startup environment and filesystem validation (read-only over ``env_vars``)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from hype_frog.config import (
    LOGS_DIR,
    PROJECT_ROOT,
    REPORTS_ARCHIVE_DIR,
    REPORTS_LATEST_DIR,
    SECRETS_DIR,
    load_environment,
)
from hype_frog.core import get_logger
from hype_frog.core.env_vars import get_hf_output_filename, get_psi_api_key

logger = get_logger(__name__)

ValidationContext = Literal["startup", "crawl", "accurate_crawl"]


class EnvConfigError(RuntimeError):
    """Raised when required configuration or layout checks fail."""


@dataclass
class EnvValidationResult:
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _ensure_writable_dir(path: Path, label: str, *, result: EnvValidationResult) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_probe"
        probe.write_text("", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        result.errors.append(f"{label} is not writable: {path} ({exc})")


def validate_project_layout() -> EnvValidationResult:
    """Confirm project directories exist and are writable."""
    result = EnvValidationResult()
    if not PROJECT_ROOT.is_dir():
        result.errors.append(
            f"Project root does not exist: {PROJECT_ROOT}. "
            "Run from the repository clone or place the executable beside your .env file."
        )
        return result

    for path, label in (
        (LOGS_DIR, "Logs directory"),
        (REPORTS_LATEST_DIR, "Reports directory"),
        (REPORTS_ARCHIVE_DIR, "Reports archive directory"),
    ):
        _ensure_writable_dir(path, label, result=result)

    if not SECRETS_DIR.is_dir():
        result.warnings.append(
            f"Secrets directory not found ({SECRETS_DIR}). "
            "GSC OAuth will fail until secrets/client_secrets.json is present."
        )
    return result


def validate_environment(*, context: ValidationContext = "startup") -> EnvValidationResult:
    """Validate layout and optional keys for the given runtime context.

    Stability-first: missing optional API keys produce warnings, not hard failures.
    """
    load_environment()
    result = validate_project_layout()

    output_path = get_hf_output_filename()
    if output_path:
        target = Path(output_path)
        parent = target.parent if target.is_absolute() else (PROJECT_ROOT / target).parent
        if str(parent) not in {".", ""}:
            try:
                parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                result.errors.append(
                    f"HF_OUTPUT_FILENAME parent directory is not writable: {parent} ({exc})"
                )

    if context in {"crawl", "accurate_crawl"} and not get_psi_api_key():
        result.warnings.append(
            "PSI_API_KEY is not set — PageSpeed Insights columns will be blank for this run."
        )

    if context == "accurate_crawl":
        try:
            import playwright  # noqa: F401
        except ImportError:
            result.warnings.append(
                "Playwright is not installed. Install with: uv sync --extra render "
                "&& uv run hype-frog setup playwright"
            )

    for warning in result.warnings:
        logger.warning(warning)
    return result


def require_valid_environment(*, context: ValidationContext = "startup") -> None:
    """Raise ``EnvConfigError`` when layout validation fails."""
    result = validate_environment(context=context)
    if not result.ok:
        message = "\n".join(result.errors)
        raise EnvConfigError(message)


__all__ = [
    "EnvConfigError",
    "EnvValidationResult",
    "ValidationContext",
    "require_valid_environment",
    "validate_environment",
    "validate_project_layout",
]
