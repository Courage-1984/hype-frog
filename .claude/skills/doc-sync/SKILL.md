---
name: doc-sync
description: Map hype-frog code changes to canonical documentation files.
disable-model-invocation: true
---

# Documentation sync map

When behaviour or contracts change, update the matching canonical file:

| Area | File |
|------|------|
| Pipeline, BFS, AEO, intent, ROI, PSI | `docs/system_architecture.md` |
| Row shapes, Pydantic, checkpoints, GSC nulls | `docs/data_contracts.md` |
| Excel integrity, TOC, Hub, view state | `docs/excel_reporting_standards.md` |
| Logging, run_id, JSONL | `docs/logging_architecture.md` |
| Concurrency, memory, benchmarks | `docs/performance_benchmarks.md` |
| CLI flags and examples | `commands.md` |
| Env vars | `.env.example` + `core/env_vars.py` |
| Quickstart | `README.md` |

## Before documenting
Run relevant tests (`uv run pytest tests/<layer>/`) and confirm they pass. Mark unverified guidance as **provisional**.

Do not add new files under `docs/` beyond the governed five.
