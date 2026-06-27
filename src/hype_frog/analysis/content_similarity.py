"""
Separate thin content detection from genuine duplicate content detection.
"""
from __future__ import annotations

import re
from typing import Any

from hype_frog.core.models import ExtraRowPayload
from hype_frog.config import (
    get_near_duplicate_simhash_distance,
    get_thin_content_word_threshold,
)

try:
    from simhash import Simhash

    SIMHASH_AVAILABLE = True
except ImportError:
    SIMHASH_AVAILABLE = False


def _normalise_text(text: str) -> str:
    """Strip noise before hashing — lowercase, collapse whitespace."""
    lowered = text.lower()
    lowered = re.sub(r"[^\w\s]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _shingle(text: str, k: int = 3) -> list[str]:
    """Split text into k-word shingles for simhash."""
    words = text.split()
    return [" ".join(words[i : i + k]) for i in range(len(words) - k + 1)]


def compute_content_fingerprint(text: str) -> int | None:
    """Return simhash fingerprint (64-bit int) for content similarity comparison."""
    if not SIMHASH_AVAILABLE:
        return None
    normalised = _normalise_text(text)
    if len(normalised.split()) < 10:
        return None
    return Simhash(_shingle(normalised)).value


def simhash_distance(h1: int, h2: int) -> int:
    """Hamming distance between two simhash values (0=identical, 64=completely different)."""
    return bin(h1 ^ h2).count("1")


def classify_page_duplication(
    url: str,
    title: str | None,
    word_count: int,
    content_hash: int | None,
    all_hashes: dict[str, int],
    *,
    thin_threshold: int = 200,
    similarity_threshold: int = 8,
) -> dict[str, Any]:
    """Return separate thin / near-duplicate / draft URL classification flags."""
    out: dict[str, Any] = {
        "Is Thin Content": False,
        "Thin Content Word Count": word_count,
        "Is Near Duplicate": False,
        "Near Duplicate Of": None,
        "Content Similarity Score": None,
        "Is Draft or Test Page": False,
        "Draft Signal": None,
    }

    if word_count < thin_threshold:
        out["Is Thin Content"] = True

    draft_patterns = re.compile(
        r"(-copy\b|-copy-\d+|-test\b|-draft\b|-temp\b|-old\b|-backup\b|-bak\b|-v\d+\b|/staging/|/dev/)",
        re.IGNORECASE,
    )
    match = draft_patterns.search(url)
    if match:
        out["Is Draft or Test Page"] = True
        out["Draft Signal"] = match.group(0)

    if content_hash is not None and SIMHASH_AVAILABLE:
        closest_url: str | None = None
        closest_dist = 64

        for other_url, other_hash in all_hashes.items():
            if other_url == url or other_hash is None:
                continue
            dist = simhash_distance(content_hash, other_hash)
            if dist < closest_dist:
                closest_dist = dist
                closest_url = other_url

        if closest_dist <= similarity_threshold and closest_url:
            out["Is Near Duplicate"] = True
            out["Near Duplicate Of"] = closest_url
            out["Content Similarity Score"] = round((1 - closest_dist / 64) * 100, 1)

    return out


def enrich_content_similarity(
    crawl_rows: list[ExtraRowPayload],
    *,
    titles_by_url: dict[str, str | None] | None = None,
) -> None:
    """Post-crawl pass: compute content fingerprints and find near-duplicates."""
    titles_by_url = titles_by_url or {}
    hashes: dict[str, int | None] = {}
    for row in crawl_rows:
        text = row.values.get("Body Text Excerpt") or ""
        word_count = int(
            row.values.get("Word Count (Body)") or row.values.get("Word Count") or 0
        )
        url = str(row.values.get("URL") or "")
        fingerprint = compute_content_fingerprint(text) if isinstance(text, str) else None
        hashes[url] = fingerprint
        row.values["Content Fingerprint"] = fingerprint

    valid_hashes = {url: fp for url, fp in hashes.items() if fp is not None}
    for row in crawl_rows:
        url = str(row.values.get("URL") or "")
        word_count = int(
            row.values.get("Word Count (Body)") or row.values.get("Word Count") or 0
        )
        title = titles_by_url.get(url) or row.values.get("Title")
        content_hash = hashes.get(url)
        classification = classify_page_duplication(
            url=url,
            title=str(title) if title else None,
            word_count=word_count,
            content_hash=content_hash,
            all_hashes=valid_hashes,
            thin_threshold=get_thin_content_word_threshold(),
            similarity_threshold=get_near_duplicate_simhash_distance(),
        )
        row.values.update(classification)
        row.values.pop("Body Text Excerpt", None)
