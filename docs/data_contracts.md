# Data contracts

## Crawl result envelope

Each processed URL contributes:

- **`main`** — `dict[str, Any]` aligned with `MainRowPayload` contracts in `src/hype_frog/core/models.py` plus additive pipeline fields (scores, badges, extraction metadata, etc.).
- **`extra`** — `dict[str, Any]` for extended signals (`ExtraRow` patterns: links, hreflang, snippets, etc.).

Typed payload models in `src/hype_frog/core/models.py` document intent; runtime rows may carry additional additive keys where models permit `extra="allow"`.

## Additive key policy

Established keys consumed by reporters, scoring, or checkpoints **must not be renamed or removed** without an explicit migration and human approval. New analytics should add **new keys** or clearly versioned side structures.

## Extraction observability

`Extraction State` and `Extraction Source` are part of the contract between `crawler/fetcher.py` outcomes and downstream scoring. Values must stay aligned with the lowercase literals documented in [system_architecture.md](./system_architecture.md).

## Serialization and checkpoints

Checkpoint payloads store completed URL lists and serialized crawl results. Any change to on-disk checkpoint schema must remain backward compatible or be version-guarded.

If a change to **`MainRowPayload`** or **`ExtraRow`** is **not** purely additive, the developer or agent must either **explicitly instruct the user to delete `.cache/*.sqlite`** before the next run, or **implement a `CACHE_VERSION` increment** (or equivalent invalidation) so SQLite-backed resume paths cannot load stale JSON that causes corruption or crashes during replay.

## SQLite cache versioning and invalidation

The runtime uses **SQLite** for durable caches and intermediate stores (for example crawl **audit cache** under `checkpoint/`, **PSI** and **GSC** metric caches under `crawler/`). Treat on-disk SQLite files as part of the **data contract surface**:

- **Schema or semantics change** — If table layout, column meaning, or JSON payload shape written into a cache row changes incompatibly, **bump a cache version** (dedicated metadata row/table, filename suffix, or documented constant) and **invalidate or migrate** existing rows. Do not silently read stale rows that deserialize into wrong-shaped dicts or scores.
- **TTL and eviction** — Where a cache is time-bounded (for example “fresh for N hours”), document and honour that TTL in code; avoid serving expired blobs as if current without explicit caller awareness.
- **Additive JSON in crawl cache** — Extra keys in cached `main_json` / `extra_json` can remain additive when consumers tolerate `extra="allow"`; **removals or renames** of cached keys require version bump or migration so resumed runs do not emit corrupted workbook rows.
- **Operational hygiene** — Prefer explicit **delete/rebuild** of a cache file when a breaking change ships rather than leaving incompatible databases on disk without detection.
