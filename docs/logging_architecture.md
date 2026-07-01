# Logging & Observability Architecture

Canonical reference for hype-frog runtime logging, structured telemetry, and terminal UX.

**Related:** [`system_architecture.md`](system_architecture.md) (pipeline overview), [`data_contracts.md`](data_contracts.md) (row payloads), [`excel_reporting_standards.md`](excel_reporting_standards.md) (workbook `Crawl Log` sheet — separate concern).

---

## Design goals

1. **Structured file telemetry** — one JSON object per line (JSONL) for grep, jq, and log aggregators.
2. **Clean terminal UX** — Rich panels, progress bars, and INFO-level console output by default.
3. **Run correlation** — every record carries a stable `run_id` for the process lifetime.
4. **Library isolation** — only the named `hype_frog` logger tree is configured; pytest and third-party libraries are untouched.
5. **Independent workbook audit** — `CrawlLogCollector` remains an in-memory Excel export concern, not a logging backend.

---

## Stack

| Layer | Technology |
|-------|------------|
| API | **structlog** (`structlog.stdlib.BoundLogger`) |
| Stdlib bridge | `logging` named logger `hype_frog` |
| File output | `logging.FileHandler` + `structlog.processors.JSONRenderer` |
| Console output | `rich.logging.RichHandler` (`rich_tracebacks=True`) |
| Terminal chrome | `rich.Console` — panels, rules, progress (unchanged) |

---

## Bootstrap

`configure_logging()` is called from `orchestration/run_setup.py` at run start (and lazily from `get_logger()`). It is **idempotent** — subsequent calls return the existing `run_id` without reconfiguring handlers.

```python
from hype_frog.core.logger import configure_logging, get_logger, get_run_id

run_id = configure_logging()  # or configure_logging(console_level=..., file_level=...)
logger = get_logger(__name__)
logger.info("crawl_started", url_count=42, run_id=get_run_id())
```

---

## Log destination

| Property | Value |
|----------|-------|
| Directory | `hype_frog.config.LOGS_DIR` → `PROJECT_ROOT / "logs"` (absolute) |
| Filename | `crawler_{run_id}.log` — one file per process run |
| Rotation | **None within a run**; new run → new timestamped file (no shared append) |
| Encoding | UTF-8 |

`PROJECT_ROOT` resolves to the repository root in development and the executable directory in frozen builds (see `config.py`).

---

## Run ID (`run_id`)

Generated at first `configure_logging()` unless overridden.

| Source | Precedence |
|--------|------------|
| `HF_RUN_ID` env var | Highest — use for CI replay or cross-service correlation |
| Auto-generated | `{UTC_YYYYMMDD_HHMMSS}_{8-char-hex}` e.g. `20260629_143022_a1b2c3d4` |

Access at runtime: `get_run_id()`.

---

## Environment variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `HF_RUN_ID` | Correlation ID for this process | Auto-generated |
| `HF_LOG_LEVEL` | File handler minimum level | `DEBUG` |
| `HF_CONSOLE_LOG_LEVEL` | Console handler minimum level | `INFO` |

Accepted values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` (case-insensitive).

CLI flags override console level only:

| Flag | Console level |
|------|---------------|
| *(default)* | `INFO` (or `HF_CONSOLE_LOG_LEVEL`) |
| `--verbose` | `DEBUG` |
| `--quiet` | `WARNING` |

`--verbose` and `--quiet` are mutually exclusive; `main.py` rejects both.

---

## JSONL schema

Each file log line is a single JSON object. Core fields (always present when emitted via structlog):

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | ISO-8601 string | UTC event time |
| `level` | string | `debug`, `info`, `warning`, `error`, … |
| `logger` | string | Qualified name e.g. `hype_frog.orchestration.crawl_runner_bfs` |
| `event` | string | Human-readable message / event name |
| `run_id` | string | Process correlation ID |

Optional structured fields (event-specific):

| Field | Example usage |
|-------|---------------|
| `url` | Crawl / fetch context |
| `phase` | `fetch`, `enrichment`, `export` |
| `status_code` | HTTP outcome |
| `exception` | Present on `logger.exception()` — serialised traceback |

Example line:

```json
{"timestamp":"2026-06-29T14:30:22.123456Z","level":"info","logger":"hype_frog.orchestration.crawl_runner_bfs","event":"crawl_finished","run_id":"20260629_143022_a1b2c3d4","url_count":120,"duration_s":45.2}
```

---

## Logger naming

All application loggers live under the `hype_frog` namespace:

```
hype_frog                          ← handlers attached here; propagate=False
├── hype_frog.orchestration.*
├── hype_frog.crawler.*
├── hype_frog.pipeline.*
└── hype_frog.reporter.*
```

`get_logger(__name__)` automatically prefixes `hype_frog.` when the module path is passed.

The **root logger is never modified** — no `handlers.clear()`. The `hype_frog` logger uses `propagate=True` so test harnesses (pytest `caplog`) can observe records without attaching duplicate handlers.

---

## Console vs file split

| Channel | Default level | Format | Tracebacks |
|---------|---------------|--------|------------|
| Terminal (`RichHandler`) | `INFO` | Rich coloured text, `%H:%M:%S` timestamps | `rich_tracebacks=True` on `logger.exception()` |
| File (`FileHandler`) | `DEBUG` | JSONL | `format_exc_info` processor |

`logger.debug(...)` is **file-only** under default settings — keeping the terminal clean during large crawls.

---

## Exception handling convention

In `orchestration/` and `pipeline/`, caught exceptions in operational paths use:

```python
logger.exception(
    "gsc_url_inspection_batch_failed",
    phase="enrichment",
    url_count=len(urls),
)
```

Legacy `%s` interpolation in `except` blocks is discouraged for new code.

---

## Crawl Log sheet (not runtime logging)

`core/crawl_log.py` → `CrawlLogCollector` collects per-URL operational errors for the Excel **Crawl Log** tab. It does **not** write to `logs/` and is unchanged by this architecture.

---

## Testing

- `tests/core/test_logger.py` — JSONL shape, `run_id`, verbosity, named-logger isolation.
- `tests/core/test_cli.py` — `--verbose` / `--quiet` argparse contract.
- Tests may pass `log_dir=tmp_path` to `configure_logging()` to avoid writing to the repo `logs/` directory.
