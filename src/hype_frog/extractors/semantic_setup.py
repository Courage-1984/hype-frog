"""spaCy / semantic engine installation probes (no crawl side effects)."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from enum import Enum

from hype_frog.core import get_logger

logger = get_logger(__name__)

DEFAULT_SPACY_MODEL = "en_core_web_sm"
SEMANTIC_SYNC_HINT = "uv sync --extra semantic"
SEMANTIC_INSTALL_HINT = (
    f"{SEMANTIC_SYNC_HINT}  (includes spaCy + {DEFAULT_SPACY_MODEL}); "
    f"or run: uv run hype-frog --install-semantic"
)


class SemanticEngineStatus(str, Enum):
    READY = "ready"
    MODEL_MISSING = "model_missing"
    SPACY_MISSING = "spacy_missing"


@dataclass(frozen=True)
class SemanticEngineProbe:
    status: SemanticEngineStatus
    message: str
    model_name: str = DEFAULT_SPACY_MODEL


def probe_semantic_engine(*, model_name: str = DEFAULT_SPACY_MODEL) -> SemanticEngineProbe:
    """Check spaCy import and model load without mutating analyzer poison flags."""
    try:
        import spacy
    except ImportError:
        return SemanticEngineProbe(
            status=SemanticEngineStatus.SPACY_MISSING,
            message=(
                "spaCy optional extra not installed; crawls use keyword fallback for "
                f"entity columns. Install full NER with: {SEMANTIC_INSTALL_HINT}"
            ),
            model_name=model_name,
        )
    try:
        spacy.load(
            model_name,
            disable=["parser", "lemmatizer", "attribute_ruler", "tagger"],
        )
    except OSError:
        return SemanticEngineProbe(
            status=SemanticEngineStatus.MODEL_MISSING,
            message=(
                f"spaCy is installed but model '{model_name}' is missing. "
                f"Run: uv run hype-frog --install-semantic"
            ),
            model_name=model_name,
        )
    except Exception as exc:
        return SemanticEngineProbe(
            status=SemanticEngineStatus.MODEL_MISSING,
            message=f"spaCy model '{model_name}' could not be loaded: {exc}",
            model_name=model_name,
        )
    return SemanticEngineProbe(
        status=SemanticEngineStatus.READY,
        message=f"spaCy NER ready ({model_name}).",
        model_name=model_name,
    )


def install_semantic_model(*, model_name: str = DEFAULT_SPACY_MODEL) -> tuple[bool, str]:
    """Download the spaCy language model (requires ``uv sync --extra semantic``)."""
    probe = probe_semantic_engine(model_name=model_name)
    if probe.status == SemanticEngineStatus.READY:
        return True, probe.message

    if probe.status == SemanticEngineStatus.SPACY_MISSING:
        return False, probe.message

    try:
        completed = subprocess.run(
            [sys.executable, "-m", "spacy", "download", model_name],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        return False, f"spaCy model download failed to start: {exc}"

    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "").strip()
        return False, (
            f"spaCy model download failed (exit {completed.returncode}). "
            f"{stderr or 'No output.'}"
        )

    verify = probe_semantic_engine(model_name=model_name)
    if verify.status == SemanticEngineStatus.READY:
        return True, f"Installed and verified {model_name}."
    return False, verify.message


__all__ = [
    "DEFAULT_SPACY_MODEL",
    "SEMANTIC_INSTALL_HINT",
    "SEMANTIC_SYNC_HINT",
    "SemanticEngineProbe",
    "SemanticEngineStatus",
    "install_semantic_model",
    "probe_semantic_engine",
]
