"""HTML executive report disk I/O and logo embedding."""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import patch

import pytest

from hype_frog.reporter.html_report_data import ReportContext
from hype_frog.reporter.html_report_writer import _load_logo_base64, write_html_report


def test_write_html_report_creates_file_and_parent_dirs(tmp_path) -> None:
    ctx = ReportContext(domain="example.com", crawl_date="2026-06-27", total_urls=10)
    out_path = tmp_path / "nested" / "report.html"

    returned = write_html_report(ctx, out_path)

    assert returned == out_path
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert content.startswith("<!DOCTYPE html>")
    assert "example.com" in content


def test_load_logo_base64_unset_returns_empty(monkeypatch) -> None:
    monkeypatch.delenv("HF_REPORT_LOGO_PATH", raising=False)
    assert _load_logo_base64() == ""


def test_load_logo_base64_missing_path_returns_empty(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HF_REPORT_LOGO_PATH", str(tmp_path / "does_not_exist.png"))
    assert _load_logo_base64() == ""


def test_load_logo_base64_encodes_png(monkeypatch, tmp_path) -> None:
    logo = tmp_path / "logo.png"
    raw = b"\x89PNG\r\n\x1a\nfake-bytes"
    logo.write_bytes(raw)
    monkeypatch.setenv("HF_REPORT_LOGO_PATH", str(logo))

    data_uri = _load_logo_base64()

    assert data_uri.startswith("data:image/png;base64,")
    encoded = data_uri.split(",", 1)[1]
    assert base64.b64decode(encoded) == raw


def test_load_logo_base64_resolves_relative_to_project_root(monkeypatch, tmp_path) -> None:
    from hype_frog import config

    logo = tmp_path / "assets" / "client_logo.png"
    logo.parent.mkdir()
    raw = b"\x89PNG\r\n\x1a\nrelative-logo"
    logo.write_bytes(raw)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("HF_REPORT_LOGO_PATH", "./assets/client_logo.png")

    data_uri = _load_logo_base64()

    assert data_uri.startswith("data:image/png;base64,")
    assert base64.b64decode(data_uri.split(",", 1)[1]) == raw


def test_write_html_report_accepts_string_path(tmp_path: Path) -> None:
    ctx = ReportContext(domain="example.com", crawl_date="2026-06-27", total_urls=1)
    out = tmp_path / "report.html"
    result = write_html_report(ctx, str(out))
    assert isinstance(result, Path)
    assert out.exists()


def test_write_html_report_overwrites_existing_file(tmp_path: Path) -> None:
    ctx = ReportContext(domain="example.com", crawl_date="2026-06-27", total_urls=1)
    out = tmp_path / "report.html"
    out.write_text("stale content", encoding="utf-8")
    write_html_report(ctx, out)
    assert out.read_text(encoding="utf-8") != "stale content"


def test_write_html_report_renderer_exception_propagates(tmp_path: Path) -> None:
    ctx = ReportContext(domain="example.com", crawl_date="2026-06-27", total_urls=1)
    with patch(
        "hype_frog.reporter.html_report_writer.render_html_report",
        side_effect=ValueError("render exploded"),
    ):
        with pytest.raises(ValueError, match="render exploded"):
            write_html_report(ctx, tmp_path / "report.html")


def test_write_html_report_utf8_round_trip(tmp_path: Path) -> None:
    ctx = ReportContext(domain="example.com", crawl_date="2026-06-27", total_urls=1)
    out = tmp_path / "report.html"
    with patch(
        "hype_frog.reporter.html_report_writer.render_html_report",
        return_value="<html>café résumé naïve</html>",
    ):
        write_html_report(ctx, out)
    assert out.read_text(encoding="utf-8") == "<html>café résumé naïve</html>"


def test_load_logo_base64_missing_path_logs_warning(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("HF_REPORT_LOGO_PATH", str(tmp_path / "missing.png"))
    result = _load_logo_base64()
    assert result == ""
    assert "does not exist" in caplog.text


def test_load_logo_base64_encodes_svg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    logo = tmp_path / "logo.svg"
    logo.write_bytes(b"<svg xmlns='http://www.w3.org/2000/svg'></svg>")
    monkeypatch.setenv("HF_REPORT_LOGO_PATH", str(logo))
    result = _load_logo_base64()
    assert result.startswith("data:image/svg+xml;base64,")
