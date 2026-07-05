"""config.py — resolve_project_relative_path() behaviour."""

from __future__ import annotations

from pathlib import Path

from hype_frog import config


def test_empty_string_returns_bare_path() -> None:
    assert config.resolve_project_relative_path("") == Path()


def test_none_like_whitespace_returns_bare_path() -> None:
    assert config.resolve_project_relative_path("   ") == Path()


def test_relative_path_resolves_against_project_root() -> None:
    result = config.resolve_project_relative_path("assets/client_logo.png")
    assert result == (config.PROJECT_ROOT / "assets/client_logo.png").resolve()


def test_absolute_path_is_returned_unchanged(tmp_path: Path) -> None:
    absolute = tmp_path / "logo.png"
    assert config.resolve_project_relative_path(str(absolute)) == absolute


def test_leading_dot_slash_resolves_against_project_root() -> None:
    result = config.resolve_project_relative_path("./assets/client_logo.png")
    assert result == (config.PROJECT_ROOT / "assets/client_logo.png").resolve()
