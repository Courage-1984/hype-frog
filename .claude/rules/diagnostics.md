---
paths:
  - src/hype_frog/diagnostics/**
---

# Diagnostics CLI gates

Source of truth: `.cursor/rules/diagnostics.mdc`.

| Module | CLI | Claude command |
|--------|-----|----------------|
| `quick_test.py` | `--quick-test` | `.claude/commands/quick-test.md` |
| `full_smoke_test.py` | `--full-smoke-test` | `.claude/commands/smoke-test.md` |
| `integration_validator.py` | `--validate` | `.claude/commands/validate.md` |

Shipped package features — not test helpers. Update commands + rule together when gate semantics change.
