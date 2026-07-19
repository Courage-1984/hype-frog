---
name: add-issue-rule
description: Add IssueRule with playbook, test, and optional model defaults. Invoke manually for new rules.
disable-model-invocation: true
---

# Add IssueRule

Follow @references/checklist.md.

## Scope
- `url` — per-URL Main + Issue Register
- `site` — site-level aggregates
- `server` — single server-wide rule

Verify:
```powershell
uv run pytest tests/rules/ -q --tb=short
```

Stable IDs — never rename without migration.
