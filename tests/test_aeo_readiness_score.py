"""Unit tests for weighted AEO readiness scoring."""

from __future__ import annotations

from hype_frog.core.text_utils import count_syllables_approx, flesch_kincaid_grade_level
from hype_frog.pipeline.assemble import compute_aeo_readiness_score


def test_flesch_kincaid_grade_level_reasonable_band() -> None:
    text = "The quick brown fox jumps over the lazy dog. " * 8
    words = len(text.split())
    sentences = 8
    syllables = count_syllables_approx(text)
    grade = flesch_kincaid_grade_level(
        word_count=words, sentence_count=sentences, syllable_count=syllables
    )
    assert grade is not None
    assert 0.0 < float(grade) < 20.0


def test_weighted_aeo_readiness_maxes_at_one_hundred() -> None:
    row: dict[str, object] = {
        "Extraction State": "complete",
        "Paragraphs 40-60 Words Count": 2,
        "QAPage/FAQ Schema Present": True,
        "HowTo Signal": False,
        "Speakable Schema Present": False,
        "Flesch-Kincaid Grade (Est.)": 8.5,
        "List/Table Answer Signal": True,
        "AEO Robots AI Bot Coverage": 1.0,
    }
    score, badge = compute_aeo_readiness_score(row)
    assert score == 100.0
    assert badge == "Strong"


def test_unmeasured_extraction_returns_neutral_above_warning_threshold() -> None:
    row: dict[str, object] = {"Extraction State": "skipped"}
    score, badge = compute_aeo_readiness_score(row)
    assert badge == "Unmeasured"
    assert score >= 70.0
