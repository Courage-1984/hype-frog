from __future__ import annotations

from hype_frog.pipeline.action_required import determine_action_required


def test_determine_action_required_needs_copy_when_low_or_missing_copy() -> None:
    assert determine_action_required({"Copy Score": None, "SEO Score": 90.0}) == "Needs Copy"
    assert determine_action_required({"Copy Score": 79.9, "SEO Score": 90.0}) == "Needs Copy"
    assert determine_action_required({"SEO Score": 90.0}) == "Needs Copy"


def test_determine_action_required_needs_optimisation_when_seo_low() -> None:
    assert determine_action_required({"Copy Score": 80.0, "SEO Score": None}) == "Needs Optimisation"
    assert determine_action_required({"Copy Score": 90.0, "SEO Score": 49.9}) == "Needs Optimisation"


def test_determine_action_required_complete_when_both_thresholds_met() -> None:
    assert determine_action_required({"Copy Score": 80.0, "SEO Score": 50.0}) == "Complete"
    assert determine_action_required({"Copy Score": 100.0, "SEO Score": 100.0}) == "Complete"


def test_determine_action_required_coerces_numeric_strings() -> None:
    assert determine_action_required({"Copy Score": "90", "SEO Score": "60"}) == "Complete"
