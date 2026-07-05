"""Per-issue playbook metadata for client education (C6)."""

from __future__ import annotations

from dataclasses import dataclass

from hype_frog.rules.registry import (
    DEFAULT_EFFORT_BY_SEVERITY,
    ISSUE_CONTENT,
    IssueRule,
    owner_for_issue,
)

__all__ = [
    "PlaybookEntry",
    "PLAYBOOK_COLUMNS",
    "entry_for_rule",
    "build_playbook_entry_index",
    "build_issue_playbook_rows",
]


@dataclass(frozen=True)
class PlaybookEntry:
    what_it_is: str
    why_it_matters: str
    how_to_fix: str
    time_to_fix: str
    owner: str
    how_to_verify: str


PLAYBOOK_COLUMNS: tuple[str, ...] = (
    "Section",
    "Issue",
    "Severity",
    "What It Is",
    "Why It Matters",
    "How To Fix",
    "Time To Fix",
    "Owner",
    "How To Verify",
)

_EFFORT_HOURS = {"S": "1–4 hours", "M": "4–10 hours", "L": "1–2 days"}


def _entry_for_rule(rule: IssueRule) -> PlaybookEntry:
    content = ISSUE_CONTENT.get(rule.name, {})
    effort = DEFAULT_EFFORT_BY_SEVERITY.get(rule.severity, "S")
    default_verify = (
        f"Re-run the audit and confirm '{rule.name}' no longer appears for affected URLs "
        "on the Issue Register tab."
    )
    return PlaybookEntry(
        what_it_is=content.get(
            "what_it_is", "Template/technical implementation quality issue."
        ),
        why_it_matters=content.get("why_it_matters", _default_why(rule)),
        how_to_fix=content.get(
            "how_to_fix", "Apply fix based on issue type and re-run audit."
        ),
        time_to_fix=content.get("time_to_fix", _EFFORT_HOURS.get(effort, "4–10 hours")),
        owner=content.get("owner", owner_for_issue(rule.name, rule.severity)),
        how_to_verify=content.get("how_to_verify", default_verify),
    )


def entry_for_rule(rule: IssueRule) -> PlaybookEntry:
    """Public accessor for the per-rule playbook entry (What It Is / How To Fix / …)."""
    return _entry_for_rule(rule)


def build_playbook_entry_index(rules: list[IssueRule]) -> dict[str, PlaybookEntry]:
    """Build a rule-name-keyed index of playbook entries, for reuse across sheet builders."""
    return {rule.name: entry_for_rule(rule) for rule in rules}


def _default_why(rule: IssueRule) -> str:
    if rule.severity == "Critical":
        return "Blocks indexation, ranking, or conversion until resolved."
    if rule.severity == "Warning":
        return "Dilutes crawl budget, relevance signals, or user trust if left open."
    return "Improves polish, extractability, or competitive parity when addressed."


def build_issue_playbook_rows(rules: list[IssueRule]) -> list[dict[str, str]]:
    """Build registry-backed playbook rows for issues detected in the crawl."""
    rows: list[dict[str, str]] = []
    for rule in rules:
        entry = _entry_for_rule(rule)
        rows.append(
            {
                "Section": "Issue Playbook",
                "Issue": rule.name,
                "Severity": rule.severity,
                "What It Is": entry.what_it_is,
                "Why It Matters": entry.why_it_matters,
                "How To Fix": entry.how_to_fix,
                "Time To Fix": entry.time_to_fix,
                "Owner": entry.owner,
                "How To Verify": entry.how_to_verify,
            }
        )
    return rows
