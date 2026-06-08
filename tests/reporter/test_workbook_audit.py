"""Workbook audit module smoke tests."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from hype_frog.reporter.workbook_audit import audit_workbook, count_main_rows


def test_audit_flags_missing_toc(tmp_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Main"
    ws.append(["URL", "Extraction State"])
    ws.append(["https://example.com/", "complete"])
    path = tmp_path / "bad.xlsx"
    wb.save(path)
    errors = audit_workbook(path, require_full_suite_sheets=False)
    assert any("TOC not at index 0" in err for err in errors)


def test_count_main_rows_excludes_header(tmp_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Main"
    ws.append(["URL", "Extraction State"])
    ws.append(["https://example.com/a", "complete"])
    ws.append(["https://example.com/b", "partial"])
    path = tmp_path / "main.xlsx"
    wb.save(path)
    assert count_main_rows(path) == 2
