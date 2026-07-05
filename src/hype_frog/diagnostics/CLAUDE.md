# diagnostics/ — scoped Claude Code context

Inherits root `CLAUDE.md`. Additional invariants for this layer only. Cursor-side equivalent: `.cursor/rules/diagnostics.mdc`.

## Module ownership

| Module | CLI gate | Claude command |
|--------|----------|-----------------|
| `quick_test.py` | `--quick-test` | `.claude/commands/quick-test.md` |
| `full_smoke_test.py` (+ `full_smoke_fixtures.py`) | `--full-smoke-test` | `.claude/commands/smoke-test.md` |
| `integration_validator.py` | `--validate` | `.claude/commands/validate.md` |

`full_smoke_fixtures.py` provides deterministic, index-seeded synthetic fixtures for `full_smoke_test.py`: the homepage is left pristine and deeper pages get seeded issues, so the mocked crawl still exercises real rule-triggering logic.

## Shipped CLI features, not test helpers

These modules are shipped package features importable from `main.py`, not developer-only test utilities. Treat changes to their public functions/flags with the same care as any other CLI surface — the three `.claude/commands/*.md` files and `.cursor/rules/diagnostics.mdc` describe the same gates and must be updated together if flag names or gate semantics change.
