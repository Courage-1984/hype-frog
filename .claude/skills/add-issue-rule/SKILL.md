---
name: add-issue-rule
description: Add a new IssueRule with playbook entry, test, and doc sync checklist for hype-frog.
disable-model-invocation: true
---

# Add IssueRule workflow

## Steps
1. **`rules/registry.py`** — Add `IssueRule` with stable ID and correct `scope` (`url` | `site` | `server`).
2. **`rules/playbook_entries.py`** — Pair playbook metadata (Issue Type column A contract for HYPERLINK/MATCH formulas).
3. **`tests/rules/`** — Test predicate and scope placement (Issue Register vs per-URL).
4. **`core/models.py`** — If new row fields: additive keys in `MAIN_ROW_DEFAULTS` / `EXTRA_ROW_DEFAULTS`.
5. **`docs/data_contracts.md`** — Update if contract semantics change.

## Verify
```powershell
uv run pytest tests/rules/ -q --tb=short
```

## Scope reminder
- `url` — per-URL Main tab + Issue Register
- `site` — site-level aggregates
- `server` — single server-wide rule
