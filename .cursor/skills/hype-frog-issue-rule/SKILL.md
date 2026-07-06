---
name: hype-frog-issue-rule
description: IssueRule scope and playbook pairing checklist for hype-frog rules engine.
---

# IssueRule checklist

1. `rules/registry.py` — stable ID, `scope` (`url` | `site` | `server`)
2. `rules/playbook_entries.py` — paired entry; `Issue Type` stays column A
3. `tests/rules/` — scope and predicate coverage
4. Additive row keys only in `core/models.py` if needed

Verify: `uv run pytest tests/rules/ -q --tb=short`

Pure functions only — no I/O in `rules/`.
