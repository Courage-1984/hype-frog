"""Guard against issue rules silently falling back to generic playbook copy."""

from __future__ import annotations

from hype_frog.rules.registry import ISSUE_CONTENT, get_summary_rules

_GENERIC_WHAT_IT_IS = "Template/technical implementation quality issue."
_GENERIC_HOW_TO_FIX = "Apply fix based on issue type and re-run audit."
_REQUIRED_FIELDS = ("what_it_is", "why_it_matters", "how_to_fix", "how_to_verify")


def test_every_summary_rule_has_a_content_entry() -> None:
    rule_names = {rule.name for rule in get_summary_rules()}
    missing = sorted(rule_names - ISSUE_CONTENT.keys())
    assert not missing, f"Rules missing an ISSUE_CONTENT entry: {missing}"


def test_no_content_entry_uses_generic_placeholder_text() -> None:
    generic = [
        name
        for name, entry in ISSUE_CONTENT.items()
        if entry.get("what_it_is") == _GENERIC_WHAT_IT_IS
        or entry.get("how_to_fix") == _GENERIC_HOW_TO_FIX
    ]
    assert not generic, f"Rules still using generic fallback copy: {generic}"


def test_every_content_entry_has_required_fields() -> None:
    incomplete = {
        name: [field for field in _REQUIRED_FIELDS if not str(entry.get(field, "")).strip()]
        for name, entry in ISSUE_CONTENT.items()
    }
    incomplete = {name: fields for name, fields in incomplete.items() if fields}
    assert not incomplete, f"Rules with missing/empty content fields: {incomplete}"
