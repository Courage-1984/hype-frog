from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any

from hype_frog.core import get_logger
from hype_frog.core.status_codes import (
    is_error_status,
    status_as_int_or_none,
)
from hype_frog.rules.registry import IssueRule

logger = get_logger(__name__)

# Rows with HTML-derived signals use these states (see crawler fetcher). "partial" still
# carries the same rule inputs as Summary tab issue counts; only skip scoring when we never
# got a usable crawl payload.
_SCORABLE_EXTRACTION_STATES = frozenset({"complete", "partial"})


def scorable_extraction_state(state: object) -> bool:
    """Return True when HTML-derived rule inputs are present on the row."""
    return str(state or "").strip().lower() in _SCORABLE_EXTRACTION_STATES


def align_extraction_state_from_main(
    extra: MutableMapping[str, Any],
    main: Mapping[str, Any],
) -> None:
    """Copy scorable main ``Extraction State`` onto extra when extra was left at skipped."""
    if scorable_extraction_state(extra.get("Extraction State")):
        return
    main_state = main.get("Extraction State")
    if not scorable_extraction_state(main_state):
        return
    extra["Extraction State"] = main_state
    main_source = main.get("Extraction Source")
    if main_source and not extra.get("Extraction Source"):
        extra["Extraction Source"] = main_source


def score_url_health(
    row: dict[str, Any], summary_rules: list[IssueRule]
) -> tuple[Any, str, str, dict[str, list[str]]]:
    raw_status = row.get("Status Code")
    status_code = status_as_int_or_none(raw_status)
    if is_error_status(raw_status) and not isinstance(raw_status, int):
        return (
            0,
            "Critical",
            "FAIL 🔴",
            {"Critical": ["Non-200 Status"], "Warning": [], "Observation": []},
        )
    if status_code == 404:
        return (
            0,
            "Critical",
            "FAIL 🔴",
            {"Critical": ["Non-200 Status"], "Warning": [], "Observation": []},
        )

    if not scorable_extraction_state(row.get("Extraction State")):
        return None, "Unmeasured", "UNMEASURED", {"Critical": [], "Warning": [], "Observation": []}

    matched = {"Critical": [], "Warning": [], "Observation": []}
    for rule in summary_rules:
        try:
            if rule.fn(row):
                matched[rule.severity].append(rule.name)
        except Exception as exc:
            logger.warning("Rule %r raised: %s", rule, exc)
            continue
    observation_penalty = min(10, 3 * len(matched["Observation"]))
    score = max(
        0,
        100
        - (25 * len(matched["Critical"]))
        - (10 * len(matched["Warning"]))
        - observation_penalty,
    )
    if matched["Critical"]:
        badge = "Critical"
        icon = "FAIL 🔴"
    elif matched["Warning"]:
        badge = "Warning"
        icon = "WARN 🟡"
    elif matched["Observation"]:
        badge = "Observation"
        icon = "OBS 🔵"
    else:
        badge = "Pass"
        icon = "PASS 🟢"
    return score, badge, icon, matched
