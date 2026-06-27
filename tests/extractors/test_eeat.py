"""E-E-A-T signal extraction tests (Top 8 Part 2 / D5)."""
from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from hype_frog.extractors.eeat import extract_eeat_signals


def test_extract_eeat_signals_from_sample_page(fixtures_dir: Path) -> None:
    html = (fixtures_dir / "sample_page.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)
    signals = extract_eeat_signals(
        soup=soup,
        page_url="https://example.com/news/conference-recap",
        page_text=text,
    )

    assert signals["Meta Author"] == "Jane Doe"
    assert signals["Has Byline Element"] is True
    assert signals["Schema Author Name"] == "Jane Doe"
    assert signals["OG Published Time"] == "2025-03-15T10:00:00Z"
    assert signals["Has Privacy Policy Link"] is True
    assert signals["Has Terms Link"] is True
    assert signals["Has Social Links"] is True
    assert signals["Has Email Address"] is True
    assert signals["Has Phone Number"] is True
    assert signals["Links to About Page"] is True
    assert signals["Has Authority External Links"] is True
    assert (signals["E-E-A-T Signal Score"] or 0) >= 6


def test_extract_eeat_signals_empty_page(empty_page_html: str) -> None:
    soup = BeautifulSoup(empty_page_html, "lxml")
    signals = extract_eeat_signals(
        soup=soup,
        page_url="https://example.com/empty",
        page_text=soup.get_text(" ", strip=True),
    )
    assert signals["E-E-A-T Signal Score"] == 0
    assert signals["Has Privacy Policy Link"] is False
