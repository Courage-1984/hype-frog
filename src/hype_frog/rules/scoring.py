from __future__ import annotations

from collections.abc import Callable
from typing import Any

# Rows with HTML-derived signals use these states (see crawler fetcher). "partial" still
# carries the same rule inputs as Summary tab issue counts; only skip scoring when we never
# got a usable crawl payload.
_SCORABLE_EXTRACTION_STATES = frozenset({"complete", "partial"})


def score_url_health(
    row: dict[str, Any], summary_rules: list[tuple[str, str, Callable[[dict[str, Any]], bool]]]
) -> tuple[Any, str, str, dict[str, list[str]]]:
    extraction_state = str(row.get("Extraction State") or "").strip().lower()
    if extraction_state not in _SCORABLE_EXTRACTION_STATES:
        return None, "Unmeasured", "UNMEASURED", {"Critical": [], "Warning": [], "Observation": []}

    matched = {"Critical": [], "Warning": [], "Observation": []}
    for severity, issue_name, rule_fn in summary_rules:
        try:
            if rule_fn(row):
                matched[severity].append(issue_name)
        except Exception:
            continue
    score = max(0, 100 - (25 * len(matched["Critical"])) - (10 * len(matched["Warning"])) - (3 * len(matched["Observation"])))
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
