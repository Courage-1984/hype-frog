---
paths:
  - src/hype_frog/diagnostics/**
---

# Diagnostics CLI gates

Shipped package features (importable from `main.py`) — not test helpers.

| Module | CLI | Slash command |
|--------|-----|---------------|
| `quick_test.py` | `--quick-test` / `--quick-test-fast` | `/quick-test` |
| `full_smoke_test.py` | `--full-smoke-test` | `/smoke-test` |
| `integration_validator.py` | `--validate` | `/validate` |

Update commands + this rule together when gate semantics change.
