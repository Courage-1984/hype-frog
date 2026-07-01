"""Tests for cross-platform path helpers."""

from __future__ import annotations

from pathlib import Path

from hype_frog.core.path_utils import as_resolved_path, ensure_parent_dir, path_exists


def test_path_exists_false_for_missing(tmp_path: Path) -> None:
    assert path_exists(tmp_path / "missing.txt") is False
    assert path_exists(None) is False
    assert path_exists("") is False


def test_path_exists_true_for_file(tmp_path: Path) -> None:
    target = tmp_path / "ok.txt"
    target.write_text("x", encoding="utf-8")
    assert path_exists(target) is True


def test_as_resolved_path_absolute(tmp_path: Path) -> None:
    resolved = as_resolved_path(tmp_path / "nested")
    assert resolved.is_absolute()


def test_ensure_parent_dir_creates_parents(tmp_path: Path) -> None:
    target = tmp_path / "out" / "nested" / "report.xlsx"
    ensure_parent_dir(target)
    assert (tmp_path / "out" / "nested").is_dir()
