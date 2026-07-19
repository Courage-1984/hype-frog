---
name: doc-sync
description: Map hype-frog code changes to the six canonical docs plus commands.md. Use when behaviour or contracts change.
---

# Documentation sync

When behaviour or contracts change, update the matching file:

| Area | File |
|------|------|
| Pipeline, BFS, AEO, intent, ROI, PSI | `docs/system_architecture.md` |
| Row shapes, Pydantic, checkpoints, GSC nulls | `docs/data_contracts.md` |
| Excel integrity, TOC, Hub, view state | `docs/excel_reporting_standards.md` |
| Per-tab audience/content | `docs/workbook_tabs.md` |
| Logging, run_id, JSONL | `docs/logging_architecture.md` |
| Concurrency, memory, benchmarks | `docs/performance_benchmarks.md` |
| CLI flags and examples | `commands.md` |
| Env vars | `.env.example` + `core/env_vars.py` |
| Quickstart | `README.md` |

Exactly **six** files under `docs/` — do not add another.

## Before documenting
Run relevant tests and confirm they pass. Mark unverified guidance as **provisional**.

If Cursor `.mdc` rules also describe the same invariant, update `.claude/rules/` and note Cursor sync for the human (Cursor stack is separate SoT for Cursor).
