# Data contracts

## Crawl result envelope

Each processed URL contributes:

- **`main`** — `dict[str, Any]` aligned with `MainRow`-style fields in `models.py` plus dynamic columns added by the pipeline (scores, badges, extraction fields, etc.).
- **`extra`** — `dict[str, Any]` for extended signals (`ExtraRow` patterns: links, hreflang, snippets, etc.).

Typed aliases document intent; runtime rows may carry additional keys when `extra="allow"` models are used.

## Additive key policy

Established keys consumed by reporters, scoring, or checkpoints **must not be renamed or removed** without an explicit migration and human approval. New analytics should add **new keys** or clearly versioned side structures.

## Extraction observability

`Extraction State` and `Extraction Source` are part of the contract between `crawler/fetcher.py` outcomes and downstream scoring. Values must stay aligned with the lowercase literals documented in [crawler_engine.md](./crawler_engine.md).

## Serialization and checkpoints

Checkpoint payloads store completed URL lists and serialized crawl results. Any change to on-disk checkpoint schema must remain backward compatible or be version-guarded.
