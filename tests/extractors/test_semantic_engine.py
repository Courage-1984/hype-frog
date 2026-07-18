"""Unit tests for the Sprint-3 semantic engine.

Covers ``hype_frog.extractors.semantic_engine``:

* ``count_citation_candidates`` — 40-60 word window detection with
  definition triggers (paragraph-mode + sentence-cluster mode).
* ``_compute_aeo_score`` — weighted 60 % entity density + 40 % citations.
* ``SemanticAnalyzer`` poison flag — when ``import spacy`` fails the
  analyser must (a) log a single warning, (b) flip the class-level
  ``_spacy_unavailable`` flag, (c) keep returning regex-only citation
  counts, and (d) skip subsequent import attempts.
* ``SemanticAnalyzer.analyze`` happy path with an injected fake spaCy
  model so the entity branch is exercised without requiring the real
  ``en_core_web_sm`` download.

Rule #2 (No Network): no spaCy model download, no LLM call, no HTTP.
Rule #3 (Extraction State): not in scope — this module reads
already-extracted text, never raw payloads.
"""

from __future__ import annotations

import builtins
import logging
from typing import Any

import pytest

from hype_frog.extractors.semantic_engine import (
    extract_keyword_entities_fallback,
    CITATION_MAX_WORDS,
    CITATION_MIN_WORDS,
    DEFAULT_DEFINITION_TRIGGERS,
    SemanticAnalyzer,
    _compute_aeo_score,
    count_citation_candidates,
)


def _log_event_text(record: logging.LogRecord) -> str:
    if isinstance(record.msg, dict):
        return str(record.msg.get("event", ""))
    return record.getMessage()


# ---------------------------------------------------------------------------
# count_citation_candidates — paragraph mode
# ---------------------------------------------------------------------------


def _paragraph_with(words: int, *, trigger: str = " is ") -> str:
    """Build a paragraph of ``words`` whitespace-separated tokens."""
    base = ["seo"] * words
    # Splice in the trigger string near the middle (it is a multi-token phrase).
    mid = max(1, words // 2)
    base[mid] = trigger.strip()
    text = " ".join(base)
    # Ensure the trigger is surrounded by spaces (the matcher pads with spaces).
    return text.replace(trigger.strip(), trigger.strip())


def test_count_citation_returns_zero_on_empty_input() -> None:
    assert count_citation_candidates(body_text=None, paragraphs=None) == 0
    assert count_citation_candidates(body_text="", paragraphs=[]) == 0
    assert count_citation_candidates(body_text="   ", paragraphs=None) == 0


def test_count_citation_paragraph_with_definition_trigger_in_window() -> None:
    paragraph = (
        "Answer engine optimization is the discipline of structuring content "
        "for citation by AI systems like Perplexity, Gemini, and SearchGPT, "
        "and it includes schema markup, definitions, and concise summarising "
        "sentences shaped for cite-able knowledge surfacing in modern answer "
        "interfaces of next-generation generative search platforms today."
    )
    word_count = len(paragraph.split())
    assert CITATION_MIN_WORDS <= word_count <= CITATION_MAX_WORDS, (
        f"setup error: word_count={word_count}"
    )
    assert count_citation_candidates(body_text=None, paragraphs=[paragraph]) == 1


def test_count_citation_paragraph_too_short_is_excluded() -> None:
    paragraph = "Answer engine optimization is the discipline."
    assert len(paragraph.split()) < CITATION_MIN_WORDS
    assert count_citation_candidates(body_text=None, paragraphs=[paragraph]) == 0


def test_count_citation_paragraph_too_long_is_excluded() -> None:
    paragraph = (
        "Answer engine optimization is " + ("filler word " * 80) + "end."
    )
    assert len(paragraph.split()) > CITATION_MAX_WORDS
    assert count_citation_candidates(body_text=None, paragraphs=[paragraph]) == 0


def test_count_citation_paragraph_in_band_without_trigger_is_excluded() -> None:
    paragraph = (
        "Brands appearing within AI summaries shaped schema markup, headings, "
        "and concise factual statements while LLM-driven search experiences "
        "surfaced them across question-led research journeys, with buyers "
        "actively investigating modern enterprise software while comparing "
        "vendors, pricing tiers, onboarding timelines, integration catalogues, "
        "support commitments, and negotiated contract terms during procurement."
    )
    word_count = len(paragraph.split())
    assert CITATION_MIN_WORDS <= word_count <= CITATION_MAX_WORDS, (
        f"setup error: word_count={word_count}"
    )
    # Contains no definition trigger and is not a question-led Q&A block.
    assert count_citation_candidates(body_text=None, paragraphs=[paragraph]) == 0


def test_count_citation_each_canonical_trigger_is_recognised() -> None:
    base_filler = " ".join(["seo"] * 50)  # 50 words, in-band
    for trigger in DEFAULT_DEFINITION_TRIGGERS:
        paragraph = f"answer{trigger}{base_filler}"
        # Our paragraph is 51 words now — still in-band.
        word_count = len(paragraph.split())
        assert CITATION_MIN_WORDS <= word_count <= CITATION_MAX_WORDS, (
            f"setup error for trigger {trigger!r}: word_count={word_count}"
        )
        assert (
            count_citation_candidates(body_text=None, paragraphs=[paragraph]) == 1
        ), f"Trigger {trigger!r} was not recognised."


def test_count_citation_aggregates_multiple_paragraphs() -> None:
    yes = (
        "Answer engine optimization is " + " ".join(["filler"] * 48)
    )  # 50 words with " is "
    no_too_short = "It is short."
    yes_again = "AEO refers to " + " ".join(["filler"] * 48)
    yes_helps = "AEO helps brands " + " ".join(["filler"] * 47)  # " helps " trigger
    paragraphs = [yes, no_too_short, yes_again, yes_helps]
    assert count_citation_candidates(body_text=None, paragraphs=paragraphs) == 3


def test_count_citation_question_led_qa_block_counts() -> None:
    answer = " ".join(["insight"] * 40)
    qa_block = f"Why does answer engine optimisation matter? {answer}."
    word_count = len(qa_block.split())
    assert CITATION_MIN_WORDS <= word_count <= CITATION_MAX_WORDS
    assert count_citation_candidates(body_text=None, paragraphs=[qa_block]) == 1

    # A question with a too-thin answer is not citeable.
    thin_padding = " ".join(["window-padding"] * 30)
    thin = (
        f"{thin_padding}. Why does answer engine optimisation matter? It just does."
    )
    assert CITATION_MIN_WORDS <= len(thin.split()) <= CITATION_MAX_WORDS
    assert count_citation_candidates(body_text=None, paragraphs=[thin]) == 0


# ---------------------------------------------------------------------------
# count_citation_candidates — body_text fallback (sentence clustering)
# ---------------------------------------------------------------------------


def test_count_citation_body_text_clusters_sentences_into_windows() -> None:
    sentence = "Answer engine optimization is a structured discipline. "
    body = sentence * 6  # ~ 7 words × 6 = 42 words → in-band
    out = count_citation_candidates(body_text=body, paragraphs=None)
    assert out >= 1


def test_count_citation_body_text_empty_returns_zero() -> None:
    assert count_citation_candidates(body_text="", paragraphs=None) == 0


# ---------------------------------------------------------------------------
# _compute_aeo_score — weighted math
# ---------------------------------------------------------------------------


def test_compute_aeo_score_zero_inputs() -> None:
    assert _compute_aeo_score(0.0, 0) == 0.0


def test_compute_aeo_score_full_density_full_citations() -> None:
    # Density 10 % = full 60 weight. Citations 5 = full 40 weight.
    assert _compute_aeo_score(10.0, 5) == 100.0


def test_compute_aeo_score_caps_at_one_hundred_when_inputs_overshoot() -> None:
    # Density 25 % and citations 20 both clip at their respective ceilings.
    assert _compute_aeo_score(25.0, 20) == 100.0


def test_compute_aeo_score_density_only_half_full() -> None:
    # 5 % density → 30/60 weight; 0 citations → 0/40.
    assert _compute_aeo_score(5.0, 0) == 30.0


def test_compute_aeo_score_citations_only_half_full() -> None:
    # 0 density; 2.5 → int floor 2 → 16/40 weight.
    assert _compute_aeo_score(0.0, 2) == 16.0


def test_compute_aeo_score_negative_inputs_clamped_to_zero() -> None:
    assert _compute_aeo_score(-5.0, -3) == 0.0


def test_keyword_fallback_extracts_proper_nouns_and_acronyms_only() -> None:
    text = (
        "The African Marketing Confederation provides resources for SEO teams. "
        "Marketing teams use analytics across Africa."
    )
    entities = extract_keyword_entities_fallback(text)
    assert any("African Marketing Confederation" in ent for ent in entities)
    assert "SEO" in entities
    # Regression: common lowercase words must NOT be promoted to entities —
    # the old frequency top-up inflated Entity Density past 100% on short pages.
    assert "Analytics" not in entities
    assert "Resources" not in entities


def test_entity_density_is_clamped_to_sanity_ceiling() -> None:
    from hype_frog.extractors.semantic_engine import (
        _ENTITY_DENSITY_MAX_PCT,
        _entity_density_pct,
    )

    # 30 entities over 33 words would be ~91% — extractor noise, not signal.
    assert _entity_density_pct([f"Entity{i}" for i in range(30)], 33) == (
        _ENTITY_DENSITY_MAX_PCT
    )
    assert _entity_density_pct(["Acme"], 100) == 1.0
    assert _entity_density_pct([], 0) == 0.0


# ---------------------------------------------------------------------------
# SemanticAnalyzer — happy path with an injected fake spaCy model
# ---------------------------------------------------------------------------


class _FakeSpan:
    def __init__(self, text: str, label: str) -> None:
        self.text = text
        self.label_ = label


class _FakeDoc:
    def __init__(self, ents: list[_FakeSpan]) -> None:
        self.ents = ents


class _FakeNlp:
    """Minimal callable that mimics the slice of the spaCy API the analyser uses."""

    def __init__(self, *, ents: list[_FakeSpan]) -> None:
        self._ents = ents
        self.calls: int = 0

    def __call__(self, _text: str) -> _FakeDoc:
        self.calls += 1
        return _FakeDoc(self._ents)


def test_semantic_analyzer_happy_path_with_injected_model() -> None:
    SemanticAnalyzer.reset_model_cache()
    fake_nlp = _FakeNlp(
        ents=[
            _FakeSpan("OpenAI", "ORG"),
            _FakeSpan("OpenAI", "ORG"),
            _FakeSpan("Anthropic", "ORG"),
            _FakeSpan("Sam Altman", "PERSON"),
            _FakeSpan("San Francisco", "GPE"),
        ]
    )
    analyzer = SemanticAnalyzer(injected_model=fake_nlp)
    body = (
        "OpenAI is a research lab. " * 10
        + "Anthropic refers to a safety-focused lab. " * 5
    )
    result = analyzer.analyze(body_text=body)

    assert result["entity_density"] is not None
    assert result["entity_density"] > 0.0
    assert result["top_entities"] == ["OpenAI", "Anthropic", "Sam Altman"]
    assert (result["citation_count"] or 0) >= 1
    assert result["aeo_score"] is not None
    assert 0.0 <= result["aeo_score"] <= 100.0
    assert result["analysis_mode"] == "spaCy NER"
    assert fake_nlp.calls == 1


def test_semantic_analyzer_empty_body_returns_safe_defaults() -> None:
    SemanticAnalyzer.reset_model_cache()
    analyzer = SemanticAnalyzer(injected_model=_FakeNlp(ents=[]))
    result = analyzer.analyze(body_text="   ")
    assert result["entity_density"] == 0.0
    assert result["top_entities"] == []
    assert result["citation_count"] == 0
    assert result["aeo_score"] == 0.0
    assert result["analysis_mode"] == "No content"


# ---------------------------------------------------------------------------
# SemanticAnalyzer — spaCy poison flag
# ---------------------------------------------------------------------------


def _install_spacy_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``import spacy`` raise ``ImportError`` from inside ``_load_model``."""
    real_import = builtins.__import__

    def fake_import(name: str, globals_=None, locals_=None, fromlist=(), level=0) -> Any:
        if name == "spacy" or name.startswith("spacy."):
            raise ImportError("simulated: spacy is not installed")
        return real_import(name, globals_, locals_, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)


def test_semantic_analyzer_poison_flag_set_after_first_import_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    SemanticAnalyzer.reset_model_cache()
    _install_spacy_import_error(monkeypatch)

    analyzer = SemanticAnalyzer()
    body = (
        "Answer engine optimization is the discipline of structuring content "
        "for citation by AI systems and surfacing concise summaries to LLMs. "
    ) * 4

    with caplog.at_level(logging.WARNING, logger="hype_frog.extractors.semantic_engine"):
        result = analyzer.analyze(body_text=body)

    assert result["analysis_mode"] == "Keyword fallback"
    assert result["entity_density"] is not None
    assert result["top_entities"] is not None
    assert result["aeo_score"] is not None
    # Citation half (regex-only) keeps working even without spaCy.
    assert (result["citation_count"] or 0) >= 1

    assert SemanticAnalyzer._spacy_unavailable is True

    matching = [
        rec
        for rec in caplog.records
        if "spaCy is not installed" in _log_event_text(rec)
    ]
    assert len(matching) == 1, (
        f"Expected exactly one ImportError-fallback warning; got {len(matching)}."
    )


def test_semantic_analyzer_poison_flag_skips_repeat_import_attempts(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    SemanticAnalyzer.reset_model_cache()
    _install_spacy_import_error(monkeypatch)

    analyzer = SemanticAnalyzer()
    body = "Some body text. " * 30

    with caplog.at_level(logging.WARNING, logger="hype_frog.extractors.semantic_engine"):
        analyzer.analyze(body_text=body)
        analyzer.analyze(body_text=body)
        analyzer.analyze(body_text=body)

    matching = [
        rec
        for rec in caplog.records
        if "spaCy is not installed" in _log_event_text(rec)
    ]
    # Warning must fire exactly once across three analyse() calls.
    assert len(matching) == 1
    assert SemanticAnalyzer._spacy_unavailable is True


def test_semantic_analyzer_respects_pre_set_poison_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pre-poisoned analyser must short-circuit ``_load_model`` cleanly."""
    SemanticAnalyzer.reset_model_cache()
    monkeypatch.setattr(SemanticAnalyzer, "_spacy_unavailable", True)

    analyzer = SemanticAnalyzer()
    paragraph = (
        "Answer engine optimization is " + " ".join(["filler"] * 48)
    )
    result = analyzer.analyze(body_text=paragraph, paragraphs=[paragraph])

    assert result["analysis_mode"] == "Keyword fallback"
    assert result["entity_density"] is not None
    assert result["top_entities"] is not None
    assert result["aeo_score"] is not None
    assert result["citation_count"] == 1


# ---------------------------------------------------------------------------
# Cleanup — leave the class-level cache in a neutral state for downstream tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_semantic_analyzer_cache() -> Any:
    """Reset the process-global spaCy cache around each test in this module."""
    SemanticAnalyzer.reset_model_cache()
    yield
    SemanticAnalyzer.reset_model_cache()
