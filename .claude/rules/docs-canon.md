---
paths:
  - docs/**
  - commands.md
---

# Documentation canon

Exactly **six** narrative files under `docs/` — do not add a seventh:

1. `system_architecture.md`
2. `data_contracts.md`
3. `excel_reporting_standards.md`
4. `workbook_tabs.md`
5. `logging_architecture.md`
6. `performance_benchmarks.md`

Also keep in sync when behaviour changes: `commands.md`, `.env.example`, root `README.md`.

## Before documenting
Run relevant tests (`uv run pytest tests/<layer>/`) and confirm they pass. Mark unverified guidance as **provisional**.

Skill: `.claude/skills/docs/doc-sync/`
