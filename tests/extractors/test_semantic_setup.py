"""Tests for spaCy semantic engine probes."""

from __future__ import annotations

import builtins
from unittest.mock import MagicMock

import pytest

from hype_frog.extractors import semantic_setup as ss
from hype_frog.extractors.semantic_setup import (
    SemanticEngineProbe,
    SemanticEngineStatus,
    install_semantic_model,
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


def test_probe_semantic_engine_reports_model_missing_on_other_load_errors(
    monkeypatch, real_import
) -> None:
    """A non-``OSError`` failure during ``spacy.load`` (corrupt model files,
    version mismatch, etc.) must still degrade to ``MODEL_MISSING``, not
    propagate an unhandled exception."""
    mock_spacy = MagicMock()
    mock_spacy.load.side_effect = ValueError("incompatible model version")

    def fake_import(name: str, globals=None, locals=None, fromlist=(), level=0):
        if name == "spacy":
            return mock_spacy
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    probe = probe_semantic_engine(model_name="en_core_web_sm")
    assert probe.status == SemanticEngineStatus.MODEL_MISSING
    assert "incompatible model version" in probe.message


# ---------------------------------------------------------------------------
# install_semantic_model
# ---------------------------------------------------------------------------


def test_install_semantic_model_already_ready_skips_download(monkeypatch) -> None:
    monkeypatch.setattr(
        ss,
        "probe_semantic_engine",
        lambda *, model_name=ss.DEFAULT_SPACY_MODEL: SemanticEngineProbe(
            status=SemanticEngineStatus.READY, message="already ready"
        ),
    )
    monkeypatch.setattr(
        ss.subprocess, "run", MagicMock(side_effect=AssertionError("should not download"))
    )

    ok, message = install_semantic_model()

    assert ok is True
    assert message == "already ready"


def test_install_semantic_model_spacy_missing_fails_without_attempting_download(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        ss,
        "probe_semantic_engine",
        lambda *, model_name=ss.DEFAULT_SPACY_MODEL: SemanticEngineProbe(
            status=SemanticEngineStatus.SPACY_MISSING, message="spaCy not installed"
        ),
    )
    monkeypatch.setattr(
        ss.subprocess, "run", MagicMock(side_effect=AssertionError("should not download"))
    )

    ok, message = install_semantic_model()

    assert ok is False
    assert message == "spaCy not installed"


def test_install_semantic_model_downloads_and_verifies_success(monkeypatch) -> None:
    probes = iter(
        [
            SemanticEngineProbe(status=SemanticEngineStatus.MODEL_MISSING, message="missing"),
            SemanticEngineProbe(status=SemanticEngineStatus.READY, message="ready now"),
        ]
    )
    monkeypatch.setattr(
        ss, "probe_semantic_engine", lambda *, model_name=ss.DEFAULT_SPACY_MODEL: next(probes)
    )
    completed = MagicMock(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(ss.subprocess, "run", MagicMock(return_value=completed))

    ok, message = install_semantic_model()

    assert ok is True
    assert "Installed and verified" in message


def test_install_semantic_model_download_nonzero_exit_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        ss,
        "probe_semantic_engine",
        lambda *, model_name=ss.DEFAULT_SPACY_MODEL: SemanticEngineProbe(
            status=SemanticEngineStatus.MODEL_MISSING, message="missing"
        ),
    )
    completed = MagicMock(returncode=1, stdout="", stderr="network unreachable")
    monkeypatch.setattr(ss.subprocess, "run", MagicMock(return_value=completed))

    ok, message = install_semantic_model()

    assert ok is False
    assert "network unreachable" in message
    assert "exit 1" in message


def test_install_semantic_model_download_subprocess_raises(monkeypatch) -> None:
    monkeypatch.setattr(
        ss,
        "probe_semantic_engine",
        lambda *, model_name=ss.DEFAULT_SPACY_MODEL: SemanticEngineProbe(
            status=SemanticEngineStatus.MODEL_MISSING, message="missing"
        ),
    )
    monkeypatch.setattr(
        ss.subprocess, "run", MagicMock(side_effect=OSError("spacy CLI not found"))
    )

    ok, message = install_semantic_model()

    assert ok is False
    assert "failed to start" in message.lower()


def test_install_semantic_model_download_succeeds_but_reverify_fails(monkeypatch) -> None:
    """The download subprocess exits 0, but the post-install re-probe still
    doesn't find a ready model (e.g. downloaded to the wrong environment) —
    must report failure using the re-probe's message, not silently succeed."""
    probes = iter(
        [
            SemanticEngineProbe(status=SemanticEngineStatus.MODEL_MISSING, message="missing"),
            SemanticEngineProbe(
                status=SemanticEngineStatus.MODEL_MISSING, message="still missing after install"
            ),
        ]
    )
    monkeypatch.setattr(
        ss, "probe_semantic_engine", lambda *, model_name=ss.DEFAULT_SPACY_MODEL: next(probes)
    )
    completed = MagicMock(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(ss.subprocess, "run", MagicMock(return_value=completed))

    ok, message = install_semantic_model()

    assert ok is False
    assert message == "still missing after install"
