"""Coverage for output-filename construction under ``reports/latest/``."""

from __future__ import annotations

import re
from pathlib import Path

from hype_frog.core import file_utils


def test_build_output_filename_uses_sanitised_domain(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(file_utils, "REPORTS_LATEST_DIR", tmp_path)

    result = file_utils.build_output_filename("https://Example.com/some/path")
    path = Path(result)

    assert path.parent == tmp_path.resolve()
    assert path.suffix == ".xlsx"
    assert re.match(r"SEO_AEO_Audit_example\.com_\d{8}_\d{6}\.xlsx", path.name)
    assert tmp_path.exists()


def test_build_output_filename_accepts_bare_domain(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(file_utils, "REPORTS_LATEST_DIR", tmp_path)

    result = file_utils.build_output_filename("example.org", full_suite=False)

    assert "SEO_AEO_Audit_example.org_" in Path(result).name


def test_build_output_filename_avoids_overwriting_existing_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(file_utils, "REPORTS_LATEST_DIR", tmp_path)

    first = file_utils.build_output_filename("collide.test")
    # Materialise the first candidate so the next call must pick a new name.
    Path(first).write_text("x", encoding="utf-8")

    # Force an identical timestamp/base so only the collision counter can differ.
    fixed_base = Path(first).stem
    monkeypatch.setattr(
        file_utils,
        "datetime",
        _FixedDatetime(fixed_base.rsplit("_", 2)[-2] + "_" + fixed_base.rsplit("_", 1)[-1]),
    )
    second = file_utils.build_output_filename("collide.test")

    assert first != second
    assert Path(second).name.startswith(Path(first).stem)


class _FixedDatetime:
    """Minimal stand-in returning a deterministic UTC timestamp string."""

    def __init__(self, stamp: str) -> None:
        self._stamp = stamp

    def now(self, *_args, **_kwargs) -> "_FixedDatetime":
        return self

    def strftime(self, _fmt: str) -> str:
        return self._stamp
