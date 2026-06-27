"""Tests for simhash-based duplicate detection."""
from __future__ import annotations

from hype_frog.analysis.content_similarity import (
    classify_page_duplication,
    compute_content_fingerprint,
)


def test_identical_text_produces_near_duplicate() -> None:
    text = " ".join(["marketing conference africa"] * 20)
    fp1 = compute_content_fingerprint(text)
    fp2 = compute_content_fingerprint(text + " extra")
    assert fp1 is not None
    assert fp2 is not None
    classification = classify_page_duplication(
        url="https://example.com/a",
        title="A",
        word_count=120,
        content_hash=fp1,
        all_hashes={"https://example.com/a": fp1, "https://example.com/b": fp2},
    )
    assert classification["Is Near Duplicate"] is True


def test_draft_url_pattern_detected() -> None:
    classification = classify_page_duplication(
        url="https://example.com/awards-2026-test",
        title=None,
        word_count=500,
        content_hash=None,
        all_hashes={},
    )
    assert classification["Is Draft or Test Page"] is True
    assert classification["Draft Signal"] == "-test"
