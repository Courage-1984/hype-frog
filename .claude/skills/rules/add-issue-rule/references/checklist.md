# New IssueRule checklist

1. **`rules/registry.py`** — `IssueRule` with stable lowercase snake_case ID, severity, `scope` (`url` | `site` | `server`), predicate
2. **`rules/playbook_entries.py`** — playbook metadata (Issue Type column A contract for HYPERLINK/MATCH)
3. **`tests/rules/`** — predicate + scope placement (Issue Register vs per-URL)
4. **`core/models.py`** — if new fields: additive keys in `MAIN_ROW_DEFAULTS` / `EXTRA_ROW_DEFAULTS`
5. **`docs/data_contracts.md`** — if contract/scoring semantics change
6. **Scoring** — only if composite scores change: `rules/scoring.py` + tests
7. **Severity CF** — do not invent new severity labels without `reporter/sheets/conditional.py`
