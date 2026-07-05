"""Corpus TF-IDF and keyword placement signals for topical authority (B6)."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "have",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "were",
        "will",
        "with",
        "you",
        "your",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*", re.IGNORECASE)


def _tokenize(text: str) -> list[str]:
    return [
        token.lower()
        for token in _TOKEN_RE.findall(text)
        if len(token) >= 3 and token.lower() not in _STOPWORDS
    ]


def _infer_target_keyword(row: dict[str, Any], title: str = "") -> str:
    title = title or str(row.get("Title") or "").strip()
    h1 = str(row.get("Primary H1 Content") or row.get("H1 Content") or "").strip()
    for candidate in (title, h1):
        tokens = _tokenize(candidate)
        if tokens:
            return " ".join(tokens[:4])
    slug = str(row.get("URL") or "")
    slug_tokens = _tokenize(slug.replace("/", " ").replace("-", " "))
    if slug_tokens:
        return " ".join(slug_tokens[-3:])
    return ""


def _first_paragraph(body: str) -> str:
    chunks = [part.strip() for part in re.split(r"\n{2,}", body) if part.strip()]
    return chunks[0] if chunks else body[:500]


def _keyword_in_text(keyword: str, text: str) -> bool:
    if not keyword or not text:
        return False
    haystack = text.casefold()
    return keyword.casefold() in haystack


def _keyword_density_pct(keyword: str, body: str) -> float | None:
    if not keyword or not body:
        return None
    words = _tokenize(body)
    if not words:
        return None
    keyword_tokens = keyword.casefold().split()
    if not keyword_tokens:
        return None
    joined = " ".join(words)
    hits = joined.count(" ".join(keyword_tokens))
    if hits <= 0:
        return 0.0
    return round((hits / max(len(words), 1)) * 100.0, 2)


def _build_idf(corpus_tokens: list[list[str]]) -> dict[str, float]:
    doc_count = max(len(corpus_tokens), 1)
    df: Counter[str] = Counter()
    for tokens in corpus_tokens:
        df.update(set(tokens))
    return {term: math.log((doc_count + 1) / (freq + 1)) + 1.0 for term, freq in df.items()}


def _top_tfidf_terms(tokens: list[str], idf: dict[str, float], limit: int = 5) -> list[str]:
    if not tokens:
        return []
    tf = Counter(tokens)
    total = float(sum(tf.values()) or 1)
    scored = [
        (term, (count / total) * idf.get(term, 1.0))
        for term, count in tf.items()
    ]
    scored.sort(key=lambda item: item[1], reverse=True)
    return [term for term, _score in scored[:limit]]


def enrich_topical_authority_fields(
    rows: list[Any], *, titles_by_url: dict[str, Any] | None = None
) -> None:
    """Add TF-IDF and keyword placement columns to extra row payloads in place.

    ``titles_by_url`` is required when ``rows`` are Extra-row payloads/dicts,
    since "Title" is only ever populated on Main rows — without it, "Keyword
    in Title" and the title-derived half of ``Target Keyword`` silently see
    an empty title on every row.
    """
    corpus: list[list[str]] = []
    bodies: list[str] = []
    for row in rows:
        values = row if isinstance(row, dict) else row.values
        body = str(
            values.get("Body Text Excerpt")
            or values.get("Current Page Copy Snippet")
            or ""
        )
        bodies.append(body)
        corpus.append(_tokenize(body))

    idf = _build_idf(corpus)

    for row, body, tokens in zip(rows, bodies, corpus, strict=True):
        values = row if isinstance(row, dict) else row.values
        url_key = str(values.get("URL") or "").strip()
        title = str(
            values.get("Title") or (titles_by_url or {}).get(url_key) or ""
        ).strip()
        keyword = _infer_target_keyword(values, title=title)
        top_terms = _top_tfidf_terms(tokens, idf)
        values["Top TF-IDF Terms"] = ", ".join(top_terms)
        values["Target Keyword"] = keyword
        values["Keyword in Title"] = _keyword_in_text(keyword, title)
        values["Keyword in H1"] = _keyword_in_text(
            keyword,
            str(values.get("Primary H1 Content") or values.get("H1 Content") or ""),
        )
        values["Keyword in First Paragraph"] = _keyword_in_text(
            keyword, _first_paragraph(body)
        )
        density = _keyword_density_pct(keyword, body)
        values["Keyword Density (%)"] = density if density is not None else ""
