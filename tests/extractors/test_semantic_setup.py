"""Tests for spaCy semantic engine probes."""

from __future__ import annotations

import builtins
from unittest.mock import MagicMock

import pytest

from hype_frog.extractors.semantic_setup import (
    SemanticEngineStatus,
    probe_semantic_engine,
)


@pytest.fixture
def real_import():
    return builtins.__import__


def test_probe_semantic_engine_reports_spacy_missing(monkeypatch, real_import) -> None:
    def fake_import(name: str, globals=None, locals=None, fromlist=(), level=0):
        if name == "spacy":
            raise ImportError("no spacy")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    probe = probe_semantic_engine()
    assert probe.status == SemanticEngineStatus.SPACY_MISSING
    assert "spaCy" in probe.message


def test_probe_semantic_engine_reports_model_missing(monkeypatch, real_import) -> None:
    mock_spacy = MagicMock()
    mock_spacy.load.side_effect = OSError("model not found")

    def fake_import(name: str, globals=None, locals=None, fromlist=(), level=0):
        if name == "spacy":
            return mock_spacy
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    probe = probe_semantic_engine(model_name="en_core_web_sm")
    assert probe.status == SemanticEngineStatus.MODEL_MISSING
    assert "missing" in probe.message.lower()


def test_probe_semantic_engine_reports_ready_when_model_loads(monkeypatch, real_import) -> None:
    mock_spacy = MagicMock()
    mock_spacy.load.return_value = MagicMock()

    def fake_import(name: str, globals=None, locals=None, fromlist=(), level=0):
        if name == "spacy":
            return mock_spacy
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    probe = probe_semantic_engine(model_name="en_core_web_sm")
    assert probe.status == SemanticEngineStatus.READY
    assert "ready" in probe.message.lower()
