---
paths:
  - src/hype_frog/rules/**
---

# Rules engine

## Ownership
- `registry.py` — `IssueRule` instances (stable IDs, severity, scope, predicate)
- `playbook_entries.py` — playbook copy paired to Issue Type (HYPERLINK/MATCH contract)
- `scoring.py` — pure composite scores 0–100 or `None`; no network, no row mutation

## Scope
- `url` — per-URL + Issue Register
- `site` — site aggregates (Affected URL Count)
- `server` — single server-wide rule

## Adding a rule
1. Stable lowercase snake_case ID — **never rename** without migration
2. Playbook entry required
3. Test in `tests/rules/`
4. New row fields → additive defaults in `core/models.py`
5. Severity CF lives in `reporter/sheets/conditional.py` — do not invent new severity labels casually

Skill: `.claude/skills/rules/add-issue-rule/`
