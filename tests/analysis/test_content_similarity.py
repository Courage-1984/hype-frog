"""Simhash-based duplicate detection."""
from __future__ import annotations

from unittest.mock import patch

from hype_frog.analysis import content_similarity as cs
from hype_frog.analysis.content_similarity import (
    classify_page_duplication,
    compute_content_fingerprint,
    enrich_content_similarity,
    simhash_distance,
)
from hype_frog.core.models import ExtraRowPayload


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


def test_simhash_distance_identical_hashes_is_zero() -> None:
    assert simhash_distance(0b1010, 0b1010) == 0


def test_simhash_distance_maximally_different_is_sixty_four() -> None:
    assert simhash_distance(0, 0xFFFFFFFFFFFFFFFF) == 64


def test_enrich_content_similarity_populates_flags_and_strips_excerpt() -> None:
    body = " ".join(["marketing conference africa"] * 20)
    row = ExtraRowPayload.model_validate(
        {
            "URL": "https://example.com/a",
            "Body Text Excerpt": body,
            "Word Count (Body)": 250,
        }
    )
    enrich_content_similarity([row])
    assert "Body Text Excerpt" not in row.values
    assert "Content Fingerprint" in row.values
    assert row.values["Is Thin Content"] is False


@patch.object(cs, "SIMHASH_AVAILABLE", False)
def test_compute_content_fingerprint_unavailable_when_simhash_missing() -> None:
    text = " ".join(["marketing conference africa"] * 20)
    assert compute_content_fingerprint(text) is None


@patch.object(cs, "SIMHASH_AVAILABLE", False)
def test_classify_page_duplication_skips_near_duplicate_without_simhash() -> None:
    classification = classify_page_duplication(
        url="https://example.com/a",
        title="A",
        word_count=500,
        content_hash=12345,
        all_hashes={"https://example.com/a": 12345, "https://example.com/b": 12345},
    )
    assert classification["Is Near Duplicate"] is False
    assert classification["Content Similarity Score"] is None
