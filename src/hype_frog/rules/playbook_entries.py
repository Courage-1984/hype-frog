"""Per-issue playbook metadata for client education (C6)."""

from __future__ import annotations

from dataclasses import dataclass

from hype_frog.rules.registry import (
    DEFAULT_EFFORT_BY_SEVERITY,
    IssueRule,
    owner_for_issue,
    root_cause_and_fix,
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
    root_cause, recommended_fix = root_cause_and_fix(rule.name)
    effort = DEFAULT_EFFORT_BY_SEVERITY.get(rule.severity, "S")
    owner = owner_for_issue(rule.name, rule.severity)
    verify = (
        f"Re-run the audit and confirm '{rule.name}' no longer appears for affected URLs "
        "on the Issue Register tab."
    )
    extras = _PLAYBOOK_OVERRIDES.get(rule.name)
    if extras:
        return PlaybookEntry(
            what_it_is=extras.get("what_it_is", root_cause),
            why_it_matters=extras.get("why_it_matters", _default_why(rule)),
            how_to_fix=extras.get("how_to_fix", recommended_fix),
            time_to_fix=extras.get("time_to_fix", _EFFORT_HOURS.get(effort, "4–10 hours")),
            owner=extras.get("owner", owner),
            how_to_verify=extras.get("how_to_verify", verify),
        )
    return PlaybookEntry(
        what_it_is=root_cause,
        why_it_matters=_default_why(rule),
        how_to_fix=recommended_fix,
        time_to_fix=_EFFORT_HOURS.get(effort, "4–10 hours"),
        owner=owner,
        how_to_verify=verify,
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


_PLAYBOOK_OVERRIDES: dict[str, dict[str, str]] = {
    "Missing Title": {
        "what_it_is": "The HTML <title> element is absent or empty.",
        "why_it_matters": "Titles are the primary SERP headline and strongest on-page relevance signal.",
        "how_to_fix": (
            "1. Add one unique <title> per URL (50–60 characters).\n"
            "2. Lead with the primary topic, then brand.\n"
            "3. Publish and request recrawl in Search Console."
        ),
        "how_to_verify": "View source or the Content Hub — Title Health should read OK.",
    },
    "Missing Meta Description": {
        "what_it_is": "The meta description tag is missing.",
        "why_it_matters": "Descriptions influence click-through from search results even when not a direct ranking factor.",
        "how_to_fix": (
            "1. Write a unique 120–155 character summary.\n"
            "2. Match search intent and include a soft call to action.\n"
            "3. Avoid duplicating the title verbatim."
        ),
    },
    "Hreflang Without Reciprocity": {
        "what_it_is": "Hreflang alternates do not reference back to this URL.",
        "why_it_matters": "Google may ignore one-way hreflang clusters, causing wrong-country rankings or duplicate content.",
        "how_to_fix": (
            "1. List every language variant on each page in the cluster.\n"
            "2. Ensure each alternate URL returns the same set of hreflang tags.\n"
            "3. Include x-default where appropriate."
        ),
        "owner": "Dev",
    },
    "Invalid Hreflang Language Code": {
        "what_it_is": "One or more hreflang values use non-standard language or region codes.",
        "why_it_matters": "Invalid codes are ignored by search engines and break international targeting.",
        "how_to_fix": (
            "1. Use ISO 639-1 language codes (e.g. en, fr).\n"
            "2. Add ISO 3166-1 region only when needed (e.g. en-GB).\n"
            "3. Keep x-default for the fallback URL."
        ),
        "owner": "Dev",
    },
    "Low AEO Readiness Score": {
        "what_it_is": "The page scores below the AEO extraction-confidence threshold.",
        "why_it_matters": "Answer engines and AI overviews favour concise, structured, factual copy.",
        "how_to_fix": (
            "1. Add question-style H2 headings.\n"
            "2. Place a 40–60 word factual answer directly beneath each question.\n"
            "3. Add FAQPage or HowTo schema that mirrors visible content."
        ),
        "owner": "Copy Writer",
    },
    "Not Indexed by Google": {
        "what_it_is": "Google Search Console reports the URL is not indexed.",
        "why_it_matters": "Non-indexed pages cannot earn organic traffic.",
        "how_to_fix": (
            "1. Review the GSC coverage reason on the Main tab.\n"
            "2. Remove accidental noindex or robots blocks.\n"
            "3. Strengthen internal links and submit the URL for inspection."
        ),
        "owner": "Dev",
    },
}


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
