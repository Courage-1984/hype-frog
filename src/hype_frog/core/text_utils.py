from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse


def normalize_text_hash(value: str | None) -> str:
    """Collapse whitespace and lowercase for stable deduplication keys."""
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def status_class(status_code: object) -> str:
    """Return HTTP status family string (e.g. 200 → '2xx', 404 → '4xx')."""
    if isinstance(status_code, int):
        return f"{status_code // 100}xx"
    return str(status_code)


def word_count_band(count: int) -> str:
    """Bucket a word count into 'Thin' / 'OK' / 'Strong' content tiers."""
    if count < 300:
        return "Thin"
    if count < 800:
        return "OK"
    return "Strong"


def image_extension(src_url: str) -> str:
    """Extract the normalised image format from a URL path (e.g. 'webp', 'jpg', 'other')."""
    path = urlparse(src_url).path.lower()
    for ext in [".webp", ".avif", ".jpg", ".jpeg", ".png", ".gif", ".svg"]:
        if path.endswith(ext):
            return ext.replace(".", "")
    return "other"


def looks_generic_image_filename(src_url: str) -> bool:
    name = Path(urlparse(src_url).path).name.lower()
    if not name:
        return False
    return bool(re.match(r"^(img|image|dsc|photo|pic)[-_]?\d+\.[a-z0-9]+$", name))


def to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def sanitize_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", str(value or "").strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("._-")
    return cleaned or "audit"


def estimate_syllables_for_word(word: str) -> int:
    """Heuristic syllable count for readability formulas (English-oriented).

    Args:
        word: Single token (letters and apostrophes only are counted).

    Returns:
        Estimated syllable count, at least ``1`` for non-empty alphabetic tokens.
    """
    w = re.sub(r"[^a-z']+", "", word.lower())
    if not w:
        return 0
    if w.endswith("e") and len(w) > 2:
        w = w[:-1]
    groups = len(re.findall(r"[aeiouy]+", w))
    return max(1, groups)


def count_syllables_approx(text: str) -> int:
    """Approximate total syllables in running text for Flesch–Kincaid grade.

    Args:
        text: Plain text (e.g. main body extract).

    Returns:
        Sum of per-word syllable estimates.
    """
    return sum(estimate_syllables_for_word(tok) for tok in str(text or "").split())


def flesch_kincaid_grade_level(
    *, word_count: int, sentence_count: int, syllable_count: int
) -> float | None:
    """Flesch–Kincaid grade level (higher = harder to read).

    Args:
        word_count: Words in the analysed passage.
        sentence_count: Sentence count (must be >= 1 for a defined score).
        syllable_count: Estimated syllable count for the same passage.

    Returns:
        Grade level rounded to two decimals, or ``None`` when undefined.
    """
    if word_count <= 0 or sentence_count <= 0:
        return None
    return round(
        0.39 * (word_count / sentence_count)
        + 11.8 * (syllable_count / word_count)
        - 15.59,
        2,
    )
