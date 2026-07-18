"""Pure-function coverage for :mod:`hype_frog.core.text_utils` helpers."""

from __future__ import annotations

from hype_frog.core.text_utils import (
    count_syllables_approx,
    estimate_syllables_for_word,
    flesch_kincaid_grade_level,
    image_extension,
    looks_generic_image_filename,
    normalize_text_hash,
    sanitize_filename_part,
    status_class,
    to_bool,
    word_count_band,
)


def test_normalize_text_hash_collapses_whitespace_and_lowers() -> None:
    assert normalize_text_hash("  Hello   World  ") == "hello world"
    assert normalize_text_hash(None) == ""
    assert normalize_text_hash("") == ""


def test_status_class_buckets_integers_and_passes_through_strings() -> None:
    assert status_class(200) == "2xx"
    assert status_class(404) == "4xx"
    assert status_class(503) == "5xx"
    assert status_class("timeout") == "timeout"


def test_word_count_band_thresholds() -> None:
    assert word_count_band(299) == "Thin"
    assert word_count_band(300) == "OK"
    assert word_count_band(799) == "OK"
    assert word_count_band(800) == "Strong"


def test_image_extension_recognises_known_types() -> None:
    assert image_extension("https://s.test/a.JPG") == "jpg"
    assert image_extension("https://s.test/dir/b.webp") == "webp"
    assert image_extension("https://s.test/c.png?cache=1") == "png"
    assert image_extension("https://s.test/no-extension") == "other"


def test_image_extension_recognises_ico() -> None:
    """Regression: ``.ico`` was missing from the recognised list, so
    ``pipeline/image_inventory.py::_image_category``'s ``ext in {"ico", "svg"}``
    check could never match a favicon — this function is the only source of
    ``ext``, so a real, verifiable dead-code bug, not just a design choice."""
    assert image_extension("https://s.test/favicon.ico") == "ico"


def test_looks_generic_image_filename() -> None:
    assert looks_generic_image_filename("https://s.test/img_123.jpg") is True
    assert looks_generic_image_filename("https://s.test/photo1.png") is True
    assert looks_generic_image_filename("https://s.test/hero-banner.jpg") is False
    assert looks_generic_image_filename("https://s.test/") is False


def test_to_bool_handles_strings_numbers_and_bools() -> None:
    assert to_bool(True) is True
    assert to_bool("yes") is True
    assert to_bool("TRUE") is True
    assert to_bool("0") is False
    assert to_bool("") is False
    assert to_bool(1) is True
    assert to_bool(0) is False


def test_sanitize_filename_part_strips_unsafe_chars() -> None:
    assert sanitize_filename_part("Example.com/Path") == "example.com_path"
    assert sanitize_filename_part("  spaced name  ") == "spaced_name"
    assert sanitize_filename_part("") == "audit"
    assert sanitize_filename_part("///") == "audit"


def test_estimate_syllables_for_word() -> None:
    assert estimate_syllables_for_word("") == 0
    assert estimate_syllables_for_word("cat") == 1
    assert estimate_syllables_for_word("hello") == 2
    # Trailing silent "e" is dropped before counting vowel groups.
    assert estimate_syllables_for_word("make") == 1


def test_count_syllables_approx_sums_words() -> None:
    assert count_syllables_approx("hello world") == 3
    assert count_syllables_approx("") == 0


def test_flesch_kincaid_grade_level() -> None:
    assert flesch_kincaid_grade_level(word_count=0, sentence_count=5, syllable_count=10) is None
    assert flesch_kincaid_grade_level(word_count=100, sentence_count=0, syllable_count=10) is None
    assert (
        flesch_kincaid_grade_level(word_count=100, sentence_count=10, syllable_count=150)
        == 6.01
    )
