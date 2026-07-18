# snapshots/ — scoped context

Inherits root [`CLAUDE.md`](../../../CLAUDE.md).

**Source of truth:** [`.cursor/rules/snapshots.mdc`](../../../.cursor/rules/snapshots.mdc).

Read it before editing this layer: backs `--regen-report` replay (`models.py`, `store.py`, `replay.py`). Replay must reconstruct the exact prior row shape; bump `CRAWL_SNAPSHOT_SCHEMA_VERSION` on any schema change. Distinct from the delta engine's unrelated `RunSnapshot` in `analysis/delta_models.py` — don't conflate the two.
