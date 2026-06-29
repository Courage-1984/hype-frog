# Data contracts

## Crawl result envelope

Each processed URL contributes:

- **`main`** — `dict[str, Any]` aligned with `MainRowPayload` contracts in `src/hype_frog/core/models.py` plus additive pipeline fields (scores, badges, extraction metadata, etc.).
- **`extra`** — `dict[str, Any]` for extended signals (`ExtraRow` patterns: links, hreflang, snippets, etc.).

Typed payload models in `src/hype_frog/core/models.py` document intent. **`MainRowPayload`** and **`ExtraRowPayload`** use a **whitelist** (`extra="ignore"`): only keys declared in `MAIN_ROW_DEFAULTS` / `EXTRA_ROW_DEFAULTS` (including `ENRICHMENT_PIPELINE_DEFAULTS` for post-crawl enrichment) survive `model_validate()`. New crawl or enrichment fields **must** be registered there before they can reach Main merge or inventory sheets.

## Additive key policy

Established keys consumed by reporters, scoring, or checkpoints **must not be renamed or removed** without an explicit migration and human approval. New analytics should add **new keys** or clearly versioned side structures.

### Enrichment pipeline defaults (`ENRICHMENT_PIPELINE_DEFAULTS`)

Post-crawl fields registered in `core/models.py` must survive `ExtraRowPayload.model_validate()` before Main merge. Confirmed groups (see `*_MAIN_MERGE_KEYS` in `pipeline/assemble.py`):

| Group | Representative keys |
|-------|---------------------|
| A2 third-party | `Third Party Script Count`, `Third Party Scripts`, `PSI Network Items`, `PSI Render Blocking URLs` |
| A4 images | `Broken Image Count`, `Content Images`, `Has Broken Images` |
| A6 hreflang | `Hreflang Declared Languages`, `Hreflang Reciprocal Status`, `Hreflang Code Valid` |
| B2 equity | `PageRank Percentile`, `Equity Tier`, `Inbound Internal Link Count` |
| B3 snippets | `Featured Snippet Type`, `Featured Snippet Readiness`, `GSC Position Opportunity` |
| B6 topical | `Top TF-IDF Terms`, `Keyword in Title`, `Keyword Density (%)` |
| Top 8 / schema / E-E-A-T | `Schema Present`, `Schema Valid`, `E-E-A-T Signal Score`, `Is Near Duplicate`, `Freshness Status` |
| PSI / CrUX | `CrUX Level`, `Origin CrUX LCP (s)`, `CWV Data Source`, Lighthouse `Lab *` / `Lighthouse *` keys |
| Graph | `Click Depth`, `Reachable from Homepage`, `Orphan Pages` |

## GSC Search Analytics semantics

When a crawled URL has **no** matching row in bulk Search Analytics, `pipeline/gsc_coverage.apply_gsc_coverage_fields` writes:

- `GSC Clicks`, `GSC Impressions`, `GSC CTR`, `GSC Avg Position` → **`None`** (not `0.0`).

This distinguishes “not in export” from a measured zero. `GSC Coverage Note` still records match/unmatch narrative via `resolve_gsc_coverage_note`.

## Issue rules contract

`rules/registry.py` — **`IssueRule`** dataclass:

| Field | Type | Notes |
|-------|------|-------|
| `severity` | str | `Critical`, `Warning`, `Observation` |
| `name` | str | Stable issue label for FixPlan / Issue Register |
| `fn` | callable | Predicate on extra-row dict |
| `scope` | str | `url` (default), `site`, or `server` |

`get_summary_rules()` returns 99 rules. Non-URL scopes produce **aggregate** IssueInventory rows with `Affected URL Count` (`reporter/summary_builder.py`).

## Extraction observability

`Extraction State` and `Extraction Source` are part of the contract between `crawler/fetcher.py` outcomes and downstream scoring. Values must stay aligned with the lowercase literals documented in [system_architecture.md](./system_architecture.md).

## Serialization and checkpoints

Checkpoint payloads store completed URL lists and serialized crawl results. Any change to on-disk checkpoint schema must remain backward compatible or be version-guarded.

**Checkpoint vs crawl replay snapshots** — do not conflate the two:

| Store | Path / module | Lifecycle | Payload |
|-------|----------------|-----------|---------|
| BFS resume checkpoint | `{workbook}_checkpoint.json`, `checkpoint/store.py` | Per in-progress run; deleted on completion | Raw `CrawlResult` pairs + BFS queue state |
| Post-crawl replay snapshot | `.cache/crawl_snapshots.sqlite`, `snapshots/store.py` | Retained across runs (per-domain cap) | Post-enrichment `main_rows` + `extra_rows` + export context |
| Delta sidecar | `{workbook}_delta_summary.json`, `analysis/delta_loader.py` | One JSON per export | Compact `RunSnapshot` (metrics + issues only) |

If a change to **`MainRowPayload`** or **`ExtraRow`** is **not** purely additive, the developer or agent must either **explicitly instruct the user to delete `.cache/*.sqlite`** before the next run, or **implement a `CACHE_VERSION` increment** (or equivalent invalidation) so SQLite-backed resume paths cannot load stale JSON that causes corruption or crashes during replay.

## SQLite cache versioning and invalidation

The runtime uses **SQLite** for durable caches and intermediate stores (for example crawl **audit cache** under `checkpoint/`, **crawl replay snapshots** under `snapshots/` (`.cache/crawl_snapshots.sqlite`), **PSI** and **GSC** metric caches under `crawler/`). Treat on-disk SQLite files as part of the **data contract surface**:

- **Schema or semantics change** — If table layout, column meaning, or JSON payload shape written into a cache row changes incompatibly, **bump a cache version** (dedicated metadata row/table, filename suffix, or documented constant) and **invalidate or migrate** existing rows. Do not silently read stale rows that deserialize into wrong-shaped dicts or scores.
- **TTL and eviction** — Where a cache is time-bounded (for example “fresh for N hours”), document and honour that TTL in code; avoid serving expired blobs as if current without explicit caller awareness.
- **Additive JSON in crawl cache** — Extra keys in cached `main_json` / `extra_json` can remain additive when consumers tolerate `extra="allow"`; **removals or renames** of cached keys require version bump or migration so resumed runs do not emit corrupted workbook rows.
- **Operational hygiene** — Prefer explicit **delete/rebuild** of a cache file when a breaking change ships rather than leaving incompatible databases on disk without detection.

> **Current state:** no `CACHE_VERSION` constant is implemented yet. Today the only invalidation path is **manual deletion** of `.cache/*.sqlite` (crawl audit cache via `checkpoint/cache.py`, crawl replay store via `snapshots/store.py`, plus PSI/GSC metric caches under `crawler/`). When a non-additive contract change ships, instruct the user to delete the cache, or introduce a version sentinel as described above.

## Crawl replay snapshots (`CrawlReplaySnapshot`)

Full post-enrichment row payloads for `--regen-report`. **Not** the same contract as `analysis/delta_models.RunSnapshot` (delta compare uses four summary metrics + issue inventory only).

| Constant / field | Value / type | Notes |
|------------------|--------------|-------|
| `CRAWL_SNAPSHOT_SCHEMA_VERSION` | `1` | Separate from `delta_models.SNAPSHOT_VERSION` |
| `snapshot_id` | `str` (UUID4) | Primary key in SQLite |
| `domain` | `str` | Normalised host from crawl target (e.g. `example.com`) |
| `run_timestamp` | `str` | UTC `YYYY-MM-DD HH:MM:SS` |
| `source_output_path` | `str \| null` | Original crawl workbook path |
| `main_rows` | `list[dict]` | Post-enrichment main row dicts (append-only key contract) |
| `extra_rows` | `list[dict]` | Post-enrichment extra row dicts |
| `crawl_context` | `dict` | Serialised `CrawlExecutionResult` fields required for export |
| `enrichment_context` | `dict` | Serialised `EnrichmentResult` fields (`status_by_url`, `graph_metrics`, etc.) |
| `setup_context` | `dict` | Export-relevant `RunSetup` subset (`high_value_slugs`, `competitor_domains`, …) |

SQLite table `crawl_snapshots` indexes `domain` + `created_at` for “latest for domain” queries. Retention: `HF_SNAPSHOT_RETENTION_PER_DOMAIN` (default **10**). Override DB path: `HF_SNAPSHOTS_DB_PATH`.

On load, if `schema_version` exceeds the runtime supported version, replay aborts with a logged error. Replay reconstructs `MainRowPayload` / `ExtraRowPayload` via `model_validate`; reporters treat rows as read-only (same as live crawl).

## Runtime configuration (D6)

Tunable thresholds and crawl pacing live in `src/hype_frog/config_defaults.py`. Optional overrides:

- **`hype_frog.config.yaml`** at the project root (keys must match `USER_CONFIG_KEYS` in `config_defaults.py`).
- **CLI:** `--psi-delay SECONDS` overrides `PSI_BASE_DELAY_SECONDS` for the current run.

Registry rules, content similarity, freshness labels, and Quick Wins caps read effective values via getter functions after `load_environment()` runs.

## Social Cards (A1 — Main merge)

After enrichment, Main rows mirror these **extra** keys (see `A1_MAIN_MERGE_KEYS` in `pipeline/assemble.py`):

| Key | Type | Notes |
|-----|------|--------|
| `OG Title`, `OG Description`, `OG Type`, `OG URL` | string \| null | From `og:*` meta |
| `OG Image URL` | string \| null | Resolved share image; legacy `OG-Image` kept in sync |
| `OG Image Width`, `OG Image Height` | int \| null | Populated only when OG image validation runs |
| `OG Image OK` | bool \| null | `null` = not checked; `false` = non-200 or fetch error |
| `OG Image Dimensions OK` | bool \| null | Within 1200×630 ±20% when dimensions measured |
| `OG URL Mismatch` | bool | `og:url` differs from page URL and canonical |
| `Twitter Card Type`, `Twitter Title`, `Twitter Description`, `Twitter Image` | string \| null | From `twitter:*` meta |
| `OG Completeness Score` | int 0–5 | One point each for title, description, type, url, image |
| `Open Graph Complete` | bool | Title, description, and image all present |

Optional validation is gated by `--check-og-images`, interactive prompt, or `CHECK_OG_IMAGES=1` (see `pipeline/og_image_validation.py`).

## Redirect chain mapping (A3 — Main merge + Extra)

Per-hop redirect data is captured from aiohttp `response.history` in `crawler/redirect_chain.py` and stored on **Extra** rows; selected keys merge to **Main** via `A3_MAIN_MERGE_KEYS` in `pipeline/assemble.py`.

| Main / Extra key | Type | Notes |
|---|---|---|
| `Final URL` | str | Normalised destination after redirects |
| `Redirect Chain` | str | Display: `A → [301] → B → [302] → C` |
| `Redirect Chain Length` | int | Hop count |
| `Redirect Chain Hops` | JSON str | `[{"url","status"}, …]` |
| `Has 302 in Chain` | bool | Temporary redirect (302/303/307) present |
| `Has Mixed Redirect Types` | bool | Both permanent and temporary hops |
| `Redirect Loop Flag` | bool | Source URL equals final URL with hops |

Full-suite exports add **Redirect Map** (one row per URL with `Redirect Chain Length` > 0) and refresh the **Redirects** tab. Registry rules: `Redirect Chains`, `302 Redirect (Temporary)`, `Mixed 301/302 Chain`, `Redirect Loop`.

## Canonical chain tracing (B1 — Main merge + Extra)

Post-crawl graph walk in `analysis/canonical_chain.py` after link status resolution. Keys merge to **Main** via `B1_MAIN_MERGE_KEYS`.

| Key | Type | Notes |
|---|---|---|
| `Canonical Chain Depth` | int | 0 = self-canonical |
| `Canonical Chain Final` | str | Terminal URL in chain |
| `Canonical Chain` | str | Display `A → B → C` |
| `Canonical Loop Detected` | bool | Cycle in canonical graph |
| `Canonical Points to Redirect` | bool | Target returns 3xx / redirect chain |
| `Canonical Points to Non-200` | bool | Target broken (non-redirect failure) |

Registry: `Canonical Chain (>1 hop)`, `Canonical Loop`, `Canonical Points to Broken URL`, `Canonical Points to Redirect`.

## GSC URL Inspection (B4 — optional)

Gated by `--gsc-url-inspection` (max 50 qualifying URLs) or `--gsc-url-inspection-full`. Requires GSC OAuth token. Smart gate: indexable, HTTP 200, zero Search Analytics impressions (or unmatched in bulk export).

| Main key | Source |
|---|---|
| `GSC Index Status` | Inspection verdict (`INDEXED` / `NOT_INDEXED` / `NEUTRAL`) |
| `GSC Last Crawl Date` | ISO date from `lastCrawlTime` |
| `GSC Mobile Usability` | `MOBILE_FRIENDLY` / `NOT_MOBILE_FRIENDLY` |
| `GSC Rich Result Status` | `VALID` / `INVALID` / `NONE` |
| `GSC Coverage Reason` | `coverageState` string |
| `Days Since Last Crawl` | int, derived from last crawl date |

Legacy `GSC Inspection *` keys remain on Extra for Technical Diagnostics compatibility.

## robots.txt per-URL mapping (A5)

Parsed once per domain during crawl (`crawler/robots_mapping.py`); per-URL `can_fetch` via stdlib `RobotFileParser`. Keys merge to **Main** via `A5_MAIN_MERGE_KEYS`.

| Main key | Values |
|---|---|
| `Robots.txt: Googlebot` etc. | `Allow` / `Disallow` / `Not specified` |
| `Crawl-Delay Applies` | bool — Googlebot group has Crawl-delay |

Full-suite exports add **Robots.txt Analysis** (raw file, rules, blocked URLs, sitemap vs robots conflicts).

## Crawl log (D7)

**Crawl Log** sheet: errors/warnings only from fetch, render, extract, intent, PSI, and GSC phases. Columns: Timestamp, URL, Phase, Error Type, Error Detail, Recovery Action Taken. Empty runs show a baseline summary row.

## Delta tracking (C1)

Each full-suite export writes `{workbook_basename}_delta_summary.json` alongside the xlsx. Pass `--previous-run PATH` (xlsx or JSON) to populate `DeltaFromPreviousRun` and `ResolvedIssues` with new/resolved issue rows, KPI deltas, and up to three SEO Health trend points per URL.

The delta system is split across four modules:

| Module | Role |
|--------|------|
| `analysis/delta_engine.py` | Compares current run against prior export; tags URLs as new / changed / removed |
| `analysis/delta_loader.py` | Loads prior run snapshots from `_delta_summary.json` or legacy xlsx via `load_run_snapshot()`, `load_snapshot_json()`, `load_snapshot_xlsx()` |
| `analysis/delta_models.py` | Dataclasses and constants: `SNAPSHOT_VERSION = 1`, `DELTA_SUMMARY_SUFFIX`, `METRIC_FIELDS` (SEO Health, AEO Readiness, Mobile PSI, Technical Health), `DELTA_SHEET_COLUMNS` (14 columns: Section, URL, Issue, Severity, Previous/Current Value, Change, Direction, First/Last Seen, Days Open, Trend Runs, Notes), `RunSnapshot` dataclass, utility helpers (`direction_for_change`, `utc_now_iso`, `parse_run_timestamp`) |
| `analysis/delta_sheet_builder.py` | Builds `DeltaFromPreviousRun` sheet rows via `build_delta_sheet_rows()` (multi-section: Summary, New Issues, Resolved Issues, Health Trend) and `build_health_trend_section()` (three-run trend visualisation) |

URL matching in `delta_engine.py` uses **normalised URL identity** from `core/url_normalization.py` — never raw strings. Delta output is additive-key only for backward reporter compatibility.

## Third-party scripts (A2)

PSI `PSI Network Items` and render-blocking URLs feed `analysis/third_party_scripts.py`. Keys merge to Main via `A2_MAIN_MERGE_KEYS`. **Script Inventory** aggregates third-party domains site-wide.

## Featured snippets (B3)

`analysis/snippet_opportunities.py` runs after composite scoring in enrichment. **Snippet Opportunities** lists URLs with `Featured Snippet Readiness` > 5 and `GSC Position Opportunity` true.

## Competitor benchmarks (B5)

`--competitors domain1,domain2` or `HF_COMPETITORS` enables `analysis/competitor_benchmarks.py` and the optional **Competitor Benchmarks** sheet.
