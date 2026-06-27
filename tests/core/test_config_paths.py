"""Project-relative path resolution for branding assets."""

from __future__ import annotations

from pathlib import Path

import pytest

from hype_frog import config


def test_resolve_project_relative_path_resolves_against_project_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    logo = tmp_path / "assets" / "client_logo.png"
    logo.parent.mkdir()
    logo.write_bytes(b"png")

    resolved = config.resolve_project_relative_path("./assets/client_logo.png")

    assert resolved == logo.resolve()


def test_resolve_project_relative_path_keeps_absolute_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path / "ignored")
    absolute = tmp_path / "logo.png"
    absolute.write_bytes(b"png")

    resolved = config.resolve_project_relative_path(str(absolute))

    assert resolved == absolute
