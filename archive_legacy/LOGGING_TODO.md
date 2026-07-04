# Logging & Observability Overhaul — Progress Tracker

## Phase 0: Documentation & Planning

- [x] Create `docs/logging_architecture.md` (JSONL schema, env contracts, bootstrap)
- [x] Create `LOGGING_TODO.md` (this file)

## Phase 1: Foundation (Structured Logging)

- [x] Add `structlog` dependency
- [x] Refactor `core/logger.py` — structlog + JSONL file handler
- [x] Implement `run_id` generator + `get_run_id()` + `HF_RUN_ID` support
- [x] Absolute log path via `config.LOGS_DIR`
- [x] Timestamped per-run filenames (`crawler_{run_id}.log`)
- [x] Named logger `hype_frog` (no root logger mutation)

## Phase 2: CLI & Environment Controls

- [x] `HF_LOG_LEVEL` / `HF_CONSOLE_LOG_LEVEL` in `core/env_vars.py`
- [x] `--verbose` / `--quiet` flags in `main.py`
- [x] Wire verbosity through `CliRunOverrides` → `run_setup` → `configure_logging`
- [x] Console INFO / file DEBUG default split
- [x] Update `.env.example`

## Phase 3: Deep Observability & Error Handling

- [x] `logger.exception` sweep in `orchestration/` except blocks
- [x] `logger.exception` sweep in `pipeline/` except blocks
- [x] Structured key-value fields on high-signal orchestration events
- [x] Rich tracebacks triggered via `logger.exception`

## Phase 4: Validation & Cleanup

- [x] Add `tests/core/test_logger.py`
- [x] Extend `tests/core/test_cli.py` for verbosity flags
- [x] Remove `handlers.clear()` on root logger (replaced by named logger)
- [x] Full suite green: `uv run pytest tests/`

---

## Out of scope (unchanged)

- `CrawlLogCollector` / Excel Crawl Log sheet
- Rich phase banners, progress bars, startup/completion panels
- Workbook CSV/Excel generation
