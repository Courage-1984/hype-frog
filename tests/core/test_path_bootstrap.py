"""Tests for `core/path_bootstrap.py` — src/ layout bootstrap for scripts/frozen builds.

Before this file, `bootstrap_src_path`, `repo_root`, `src_root`, and
`package_root` had zero test coverage.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from hype_frog.core import path_bootstrap


def test_package_root_points_at_hype_frog_package_dir() -> None:
    root = path_bootstrap.package_root()
    assert root.name == "hype_frog"
    assert (root / "core").is_dir()


def test_src_root_is_parent_of_package_root() -> None:
    assert path_bootstrap.src_root() == path_bootstrap.package_root().parent
    assert path_bootstrap.src_root().name == "src"


def test_repo_root_is_parent_of_src_root() -> None:
    assert path_bootstrap.repo_root() == path_bootstrap.src_root().parent
    assert (path_bootstrap.repo_root() / "pyproject.toml").is_file()


def test_bootstrap_src_path_is_noop_when_hype_frog_already_imported() -> None:
    assert "hype_frog" in sys.modules  # true for the whole test session
    path_before = list(sys.path)
    result = path_bootstrap.bootstrap_src_path()
    assert result == path_bootstrap.src_root()
    assert sys.path == path_before  # nothing was inserted


def test_bootstrap_src_path_inserts_src_when_hype_frog_not_imported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(sys.modules, "hype_frog", raising=False)
    src_str = str(path_bootstrap.src_root())
    monkeypatch.setattr(sys, "path", [p for p in sys.path if p != src_str])

    result = path_bootstrap.bootstrap_src_path()

    assert result == path_bootstrap.src_root()
    assert sys.path[0] == src_str
    assert getattr(sys, path_bootstrap._MARKED, False) is True


def test_bootstrap_src_path_does_not_duplicate_existing_src_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(sys.modules, "hype_frog", raising=False)
    src_str = str(path_bootstrap.src_root())
    if src_str not in sys.path:
        monkeypatch.setattr(sys, "path", [src_str, *sys.path])
    before_count = sys.path.count(src_str)

    path_bootstrap.bootstrap_src_path()

    assert sys.path.count(src_str) == before_count


def test_bootstrap_src_path_follows_anchor_to_find_alternate_src(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delitem(sys.modules, "hype_frog", raising=False)
    fake_src = tmp_path / "project" / "src"
    (fake_src / "hype_frog").mkdir(parents=True)
    anchor = tmp_path / "project" / "scripts" / "run.py"
    anchor.parent.mkdir(parents=True)
    anchor.write_text("", encoding="utf-8")

    real_src_str = str(path_bootstrap.src_root())
    monkeypatch.setattr(sys, "path", [p for p in sys.path if p != real_src_str])

    result = path_bootstrap.bootstrap_src_path(anchor=anchor)

    assert result == fake_src
    assert str(fake_src) in sys.path


def test_bootstrap_src_path_ignores_anchor_without_matching_src(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delitem(sys.modules, "hype_frog", raising=False)
    anchor = tmp_path / "unrelated" / "script.py"
    anchor.parent.mkdir(parents=True)
    anchor.write_text("", encoding="utf-8")
    real_src_str = str(path_bootstrap.src_root())
    monkeypatch.setattr(sys, "path", [p for p in sys.path if p != real_src_str])

    result = path_bootstrap.bootstrap_src_path(anchor=anchor)

    assert result == path_bootstrap.src_root()
    assert real_src_str in sys.path
