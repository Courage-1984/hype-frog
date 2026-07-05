"""Content Optimisation Hub "Action Required" — real 3-branch classifier (L4)."""

from __future__ import annotations

from hype_frog.core.models import ExtraRowPayload, MainRowPayload
from hype_frog.reporter.engine_rows import build_content_optimisation_hub_rows


def _hub_row(*, copy_score: float | None, seo_score: float | None) -> dict:
    main = MainRowPayload.model_validate({"URL": "https://example.com/p", "SEO Health Score": 50.0})
    extra = ExtraRowPayload.model_validate(
        {
            "URL": "https://example.com/p",
            "SEO Health Score": 50.0,
            **({"Copy Score": copy_score} if copy_score is not None else {}),
            **({"SEO Score": seo_score} if seo_score is not None else {}),
        }
    )
    hub_rows, _metrics = build_content_optimisation_hub_rows([main], [extra], [])
    return hub_rows[0]


def test_action_required_needs_copy_when_copy_score_low() -> None:
    row = _hub_row(copy_score=60.0, seo_score=90.0)
    assert row["Action Required"] == "Needs Copy"


def test_action_required_needs_optimisation_when_copy_ok_but_seo_low() -> None:
    """Regression (L4): the previous 2-branch Excel formula could never
    produce "Needs Optimisation" — copy is fine, but SEO score is below the
    threshold, so this must not collapse to "Complete" or "Needs Copy"."""
    row = _hub_row(copy_score=85.0, seo_score=30.0)
    assert row["Action Required"] == "Needs Optimisation"


def test_action_required_complete_when_both_scores_high() -> None:
    row = _hub_row(copy_score=90.0, seo_score=75.0)
    assert row["Action Required"] == "Complete"


def test_action_required_needs_copy_when_copy_score_missing() -> None:
    row = _hub_row(copy_score=None, seo_score=90.0)
    assert row["Action Required"] == "Needs Copy"
