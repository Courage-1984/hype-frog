from __future__ import annotations

from typing import Any

from hype_frog.rules.registry import IssueRule

# Rows with HTML-derived signals use these states (see crawler fetcher). "partial" still
# carries the same rule inputs as Summary tab issue counts; only skip scoring when we never
# got a usable crawl payload.
_SCORABLE_EXTRACTION_STATES = frozenset({"complete", "partial"})


def score_url_health(
    row: dict[str, Any], summary_rules: list[IssueRule]
) -> tuple[Any, str, str, dict[str, list[str]]]:
    raw_status = row.get("Status Code")
    status_code: int | None = None
    try:
        if raw_status is not None and str(raw_status).strip() != "":
            status_code = int(float(raw_status))
    except (TypeError, ValueError):
        status_code = None
    if status_code == 404:
        return (
            0,
            "Critical",
            "FAIL 🔴",
            {"Critical": ["Non-200 Status"], "Warning": [], "Observation": []},
        )

    extraction_state = str(row.get("Extraction State") or "").strip().lower()
    if extraction_state not in _SCORABLE_EXTRACTION_STATES:
        return None, "Unmeasured", "UNMEASURED", {"Critical": [], "Warning": [], "Observation": []}

    matched = {"Critical": [], "Warning": [], "Observation": []}
    for rule in summary_rules:
        try:
            if rule.fn(row):
                matched[rule.severity].append(rule.name)
        except Exception:
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
