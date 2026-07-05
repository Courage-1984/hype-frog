"""Semantic entity analysis and citation-readiness detection for AEO scoring.

Sprint 3 intelligence core. Two responsibilities:

1. **Entity density scoring** (#7) — extract named entities (ORG, PERSON,
   GPE, PRODUCT, EVENT) via spaCy and compute the density per 100 words,
   plus the top three entities by frequency for the strategic narrative.
2. **Citation-readiness audit** (#8) — detect 40-60 word "cite-able"
   snippets containing definition triggers (``is``, ``refers to``,
   ``means``, ``provides``) that LLM answer engines (Perplexity, Gemini,
   SearchGPT) tend to surface.

The module is built around a single :class:`SemanticAnalyzer` class with a
class-level model cache so a bulk crawl loads spaCy **once**, not once per
URL. Per-call work is bounded by ``max_chars`` to keep memory flat under
10k+ page audits.

**Graceful degradation contract:** when spaCy or its ``en_core_web_sm``
model are unavailable, the analyzer logs a single warning and the entity
half of the result reverts to ``None`` (not an exception). The citation
counter is regex-only and continues to work in that case.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, TypedDict

from hype_frog.core import get_logger
from hype_frog.core.api_clients import SEARCH_INTENT_LABELS, classify_search_intent_with_llm
from hype_frog.extractors.semantic_setup import SEMANTIC_INSTALL_HINT

logger = get_logger(__name__)

# --- Public configuration constants (instance-overridable at construction) ---

# spaCy entity labels surfaced into the workbook.
DEFAULT_ENTITY_LABELS: frozenset[str] = frozenset(
    {"ORG", "PERSON", "GPE", "PRODUCT", "EVENT"}
)

# Definition triggers used by answer engines as cite signals. Lower-case
# substring match against word-tokenised paragraph text (with leading/trailing
# space padding so "this provides" matches but "providescue" does not).
DEFAULT_DEFINITION_TRIGGERS: tuple[str, ...] = (
    " is ",
    " are ",
    " refers to ",
    " means ",
    " provides ",
)

# Brief: 40 <= words <= 60 (strict).
CITATION_MIN_WORDS: int = 40
CITATION_MAX_WORDS: int = 60

# Hard upper bound on text passed to spaCy per page; protects against
# RAM spikes during bulk crawls of unusually long pages (>~30k words).
DEFAULT_MAX_CHARS: int = 200_000

# AEO score weighting (0-100). Brief asks for a weighted average of entity
# density and citation presence — these constants make the trade-off auditable.
_AEO_DENSITY_WEIGHT: float = 60.0
_AEO_CITATION_WEIGHT: float = 40.0
_AEO_DENSITY_FULL_AT_PCT: float = 10.0
_AEO_CITATION_FULL_AT_COUNT: int = 5


class SemanticAnalysisResult(TypedDict):
    """Stable return shape for :meth:`SemanticAnalyzer.analyze`."""

    entity_density: float | None
    top_entities: list[str] | None
    citation_count: int | None
    aeo_score: float | None
    analysis_mode: str


_FALLBACK_STOPWORDS: frozenset[str] = frozenset(
    {
        "about",
        "after",
        "also",
        "been",
        "being",
        "both",
        "from",
        "have",
        "into",
        "more",
        "most",
        "only",
        "other",
        "over",
        "such",
        "than",
        "that",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "under",
        "until",
        "very",
        "what",
        "when",
        "where",
        "which",
        "while",
        "with",
        "would",
        "your",
    }
)

_PROPER_NOUN_PHRASE_RE = re.compile(
    r"\b(?:[A-Z][a-z]+(?:'[a-z]+)?)"
    r"(?:\s+(?:[A-Z][a-z]+|&|[A-Z]{2,})){0,3}\b"
)
_ACRONYM_RE = re.compile(r"\b[A-Z]{2,6}\b")
_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z'-]{3,}")


def _empty_result(citation_count: int = 0) -> SemanticAnalysisResult:
    """Safe-default payload returned for empty / non-analysable input."""
    return SemanticAnalysisResult(
        entity_density=0.0,
        top_entities=[],
        citation_count=citation_count,
        aeo_score=0.0,
        analysis_mode="No content",
    )


def extract_keyword_entities_fallback(
    text: str,
    *,
    max_terms: int = 40,
) -> list[str]:
    """Lightweight entity proxy when spaCy NER is unavailable."""
    cleaned = (text or "").strip()
    if not cleaned:
        return []

    entities: list[str] = []
    seen: set[str] = set()

    for match in _PROPER_NOUN_PHRASE_RE.finditer(cleaned):
        phrase = " ".join(match.group(0).split())
        key = phrase.casefold()
        if len(phrase) < 3 or key in seen or phrase.lower() in _FALLBACK_STOPWORDS:
            continue
        seen.add(key)
        entities.append(phrase)

    for match in _ACRONYM_RE.finditer(cleaned):
        token = match.group(0)
        key = token.casefold()
        if key in seen:
            continue
        seen.add(key)
        entities.append(token)

    freq = Counter(
        token
        for token in _TOKEN_RE.findall(cleaned.lower())
        if token not in _FALLBACK_STOPWORDS and not token.isdigit()
    )
    for word, _count in freq.most_common(max_terms):
        key = word.casefold()
        if key in seen:
            continue
        seen.add(key)
        entities.append(word.title())

    return entities[:max_terms]


def _keyword_fallback_result(
    cleaned: str,
    citation_count: int,
    entities: list[str],
) -> SemanticAnalysisResult:
    word_count = len(cleaned.split())
    density = (len(entities) / word_count) * 100.0 if word_count > 0 else 0.0
    top_entities = _top_entities_by_frequency(entities, n=3)
    aeo_score = _compute_aeo_score(density, citation_count)
    return SemanticAnalysisResult(
        entity_density=round(density, 2),
        top_entities=top_entities,
        citation_count=citation_count,
        aeo_score=aeo_score,
        analysis_mode="Keyword fallback",
    )


def _split_sentences(text: str) -> list[str]:
    """Cheap sentence splitter for citation windowing (regex, no NLP cost)."""
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part for part in (p.strip() for p in parts) if part]


def _matches_definition_trigger(
    text: str,
    triggers: tuple[str, ...] = DEFAULT_DEFINITION_TRIGGERS,
) -> bool:
    """Pad with spaces so substring match is word-bounded on both sides."""
    padded = f" {text.lower().strip()} "
    return any(trigger in padded for trigger in triggers)


def count_citation_candidates(
    *,
    body_text: str | None,
    paragraphs: list[str] | None = None,
    triggers: tuple[str, ...] = DEFAULT_DEFINITION_TRIGGERS,
    min_words: int = CITATION_MIN_WORDS,
    max_words: int = CITATION_MAX_WORDS,
) -> int:
    """Count 40-60 word paragraphs/clusters that contain a definition trigger.

    When ``paragraphs`` is provided (the normal call path from
    :func:`hype_frog.crawler.data_assembler.assemble_from_html` which has
    already extracted ``<p>`` text), each paragraph is evaluated directly.
    Otherwise sentences from ``body_text`` are clustered into 40-60 word
    windows and each window is evaluated. Both modes return ``0`` on empty
    input rather than raising.
    """
    blocks: list[str] = []

    if paragraphs:
        blocks = [p.strip() for p in paragraphs if p and p.strip()]
    elif body_text:
        sentences = _split_sentences(body_text)
        cluster: list[str] = []
        for sentence in sentences:
            cluster.extend(sentence.split())
            if min_words <= len(cluster) <= max_words:
                blocks.append(" ".join(cluster))
                cluster = []
            elif len(cluster) > max_words:
                # Keep tail to allow overlap detection across windows.
                cluster = cluster[-(max_words - 1):]

    if not blocks:
        return 0

    candidate_count = 0
    for block in blocks:
        word_count = len(block.split())
        if not (min_words <= word_count <= max_words):
            continue
        if _matches_definition_trigger(block, triggers):
            candidate_count += 1
    return candidate_count


def _top_entities_by_frequency(
    entities: list[str],
    *,
    n: int = 3,
) -> list[str]:
    """Top-``n`` entity surface forms by frequency, normalised on whitespace."""
    if not entities:
        return []
    normalised = [" ".join(ent.split()) for ent in entities if ent and ent.strip()]
    return [name for name, _ in Counter(normalised).most_common(n)]


def _compute_aeo_score(entity_density: float, citation_count: int) -> float:
    """Weighted 0-100 score: 60 % entity density (cap=10 %) + 40 % citations (cap=5)."""
    density_pct = max(0.0, float(entity_density or 0.0))
    citations = max(0, int(citation_count or 0))
    density_component = min(
        _AEO_DENSITY_WEIGHT,
        (density_pct / _AEO_DENSITY_FULL_AT_PCT) * _AEO_DENSITY_WEIGHT,
    )
    citation_component = min(
        _AEO_CITATION_WEIGHT,
        (citations / float(_AEO_CITATION_FULL_AT_COUNT)) * _AEO_CITATION_WEIGHT,
    )
    return round(density_component + citation_component, 2)


class SemanticAnalyzer:
    """spaCy-backed entity + citation analyser with a graceful no-NLP fallback.

    The class-level ``_model_cache`` makes the spaCy ``Language`` instance
    process-global so a 10k-page crawl pays the model load cost exactly once.
    Per-call work is bounded by ``max_chars`` and uses
    ``Language.disable_pipes`` to skip components we never read (parser,
    lemmatiser, attribute ruler, tagger), which roughly halves the per-page
    inference cost.

    Memory invariants:

    * spaCy import and ``spacy.load`` happen lazily inside :meth:`_load_model`
      and are skipped entirely when the analyser is never invoked.
    * A class-level "poison" flag (``_spacy_unavailable``) prevents repeat
      import attempts after the first failure, so missing-dependency warnings
      are emitted at most once per process.
    """

    _model_cache: Any = None
    _spacy_unavailable: bool = False
    _fallback_warned: bool = False

    def __init__(
        self,
        *,
        model_name: str = "en_core_web_sm",
        entity_labels: frozenset[str] = DEFAULT_ENTITY_LABELS,
        definition_triggers: tuple[str, ...] = DEFAULT_DEFINITION_TRIGGERS,
        max_chars: int = DEFAULT_MAX_CHARS,
        injected_model: Any | None = None,
    ) -> None:
        self._model_name = model_name
        self._entity_labels = entity_labels
        self._definition_triggers = definition_triggers
        self._max_chars = max(1_000, int(max_chars))
        self._injected_model = injected_model

    @classmethod
    def reset_model_cache(cls) -> None:
        """Drop the cached spaCy model (test hook; production should not use)."""
        cls._model_cache = None
        cls._spacy_unavailable = False
        cls._fallback_warned = False

    def _load_model(self) -> Any | None:
        """Lazy-load spaCy + ``en_core_web_sm``; return ``None`` on any failure."""
        if self._injected_model is not None:
            return self._injected_model
        cls = type(self)
        if cls._spacy_unavailable:
            return None
        if cls._model_cache is not None:
            return cls._model_cache
        try:
            import spacy
        except ImportError:
            logger.warning(
                "spaCy is not installed; entity columns will use keyword fallback. %s",
                SEMANTIC_INSTALL_HINT,
            )
            cls._spacy_unavailable = True
            return None
        try:
            # Disabling unused pipes halves the per-page inference cost
            # while keeping the NER pipeline fully active.
            model = spacy.load(
                self._model_name,
                disable=["parser", "lemmatizer", "attribute_ruler", "tagger"],
            )
        except OSError:
            logger.warning(
                "spaCy model %s is missing; entity columns will use keyword fallback. "
                "Run: uv run hype-frog --install-semantic",
                self._model_name,
            )
            cls._spacy_unavailable = True
            return None
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.warning("Unexpected spaCy load failure (%s); semantic engine disabled.", exc)
            cls._spacy_unavailable = True
            return None
        cls._model_cache = model
        return model

    def _extract_entities(self, text: str) -> list[str] | None:
        """Return entity surface forms restricted to ``self._entity_labels``."""
        nlp = self._load_model()
        if nlp is None:
            return None
        try:
            doc = nlp(text)
        except Exception as exc:
            logger.debug("spaCy nlp() failed: %s", exc)
            return None
        return [ent.text for ent in doc.ents if ent.label_ in self._entity_labels]

    def analyze(
        self,
        *,
        body_text: str | None,
        paragraphs: list[str] | None = None,
    ) -> SemanticAnalysisResult:
        """Run entity + citation analysis on already-extracted page text.

        ``body_text`` is the whitespace-collapsed visible copy from the
        primary content region (already produced by
        ``crawler/data_assembler.assemble_from_html`` — no re-cleaning).
        ``paragraphs`` is an optional list of raw paragraph texts used for
        more accurate citation windowing; when omitted the citation counter
        falls back to sentence-clustered windows of ``body_text``.
        """
        cleaned = (body_text or "").strip()
        citation_count = count_citation_candidates(
            body_text=cleaned,
            paragraphs=paragraphs,
            triggers=self._definition_triggers,
        )

        if not cleaned:
            return _empty_result(citation_count=citation_count)

        if len(cleaned) > self._max_chars:
            cleaned = cleaned[: self._max_chars]

        entities = self._extract_entities(cleaned)
        if entities is None:
            cls = type(self)
            if not cls._fallback_warned:
                logger.warning(
                    "Semantic engine using keyword fallback for entity density / "
                    "Top Entities / Semantic AEO Score. %s",
                    SEMANTIC_INSTALL_HINT,
                )
                cls._fallback_warned = True
            fallback_entities = extract_keyword_entities_fallback(cleaned)
            return _keyword_fallback_result(cleaned, citation_count, fallback_entities)

        word_count = len(cleaned.split())
        density = (len(entities) / word_count) * 100.0 if word_count > 0 else 0.0
        top_entities = _top_entities_by_frequency(entities, n=3)
        aeo_score = _compute_aeo_score(density, citation_count)

        return SemanticAnalysisResult(
            entity_density=round(density, 2),
            top_entities=top_entities,
            citation_count=citation_count,
            aeo_score=aeo_score,
            analysis_mode="spaCy NER",
        )


class IntentAnalyzer:
    """LLM-backed search-intent classifier with a no-key ``Unknown`` fallback."""

    def __init__(self, *, max_chars: int = 4_000) -> None:
        self._max_chars = max(200, int(max_chars))

    async def analyze_intent(self, rendered_text: str | None) -> str:
        """Classify page intent as one of the allowed workbook labels.

        The API client enforces the graceful fallback contract: no API key,
        empty text, network failures, or non-canonical model outputs all
        produce ``"Unknown"``.
        """
        text = " ".join(str(rendered_text or "").split())
        if not text:
            return "Unknown"
        intent = await classify_search_intent_with_llm(text[: self._max_chars])
        return intent if intent in SEARCH_INTENT_LABELS else "Unknown"


# Process-wide default analyser. Lazy-instantiated so importers that never
# call ``get_default_analyzer()`` (e.g. test modules that mock it) pay no
# construction cost.
_DEFAULT_ANALYZER: SemanticAnalyzer | None = None


def get_default_analyzer() -> SemanticAnalyzer:
    """Return a process-wide :class:`SemanticAnalyzer` (lazy-instantiated)."""
    global _DEFAULT_ANALYZER
    if _DEFAULT_ANALYZER is None:
        _DEFAULT_ANALYZER = SemanticAnalyzer()
    return _DEFAULT_ANALYZER


__all__ = [
    "CITATION_MAX_WORDS",
    "CITATION_MIN_WORDS",
    "DEFAULT_DEFINITION_TRIGGERS",
    "DEFAULT_ENTITY_LABELS",
    "DEFAULT_MAX_CHARS",
    "IntentAnalyzer",
    "SemanticAnalysisResult",
    "SemanticAnalyzer",
    "count_citation_candidates",
    "extract_keyword_entities_fallback",
    "get_default_analyzer",
]
