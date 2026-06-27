from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def empty_page_html(fixtures_dir: Path) -> str:
    return (fixtures_dir / "empty_page.html").read_text(encoding="utf-8")


@pytest.fixture
def hreflang_cluster_html(fixtures_dir: Path) -> str:
    return (fixtures_dir / "hreflang_cluster.html").read_text(encoding="utf-8")


@pytest.fixture
def malformed_schema_html(fixtures_dir: Path) -> str:
    return (fixtures_dir / "malformed_schema.html").read_text(encoding="utf-8")


@pytest.fixture
def aeo_content_html(fixtures_dir: Path) -> str:
    return (fixtures_dir / "aeo_content.html").read_text(encoding="utf-8")


@pytest.fixture
def sample_page_html(fixtures_dir: Path) -> str:
    return (fixtures_dir / "sample_page.html").read_text(encoding="utf-8")
