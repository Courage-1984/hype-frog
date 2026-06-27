# Hype Frog — Governance & Documentation Sync

## Cursor IDE Agent Instructions — LI-HF-DOCSYNC-P0 | 27 June 2026

---

## PURPOSE

The governance files (`.cursorrules`, `.cursor/rules/*.mdc`, `docs/*.md`, `README.md`, `pyproject.toml`, `pytest.ini`) are behind the current state of the codebase. Multiple phases of changes were implemented without updating documentation. This prompt instructs you to **investigate the actual code first**, then update every governance file to accurately reflect what the code does today.

**Do NOT assume** what was implemented. The investigation phase exists precisely because the code may differ from what was planned.

---

## CRITICAL RULES

1. **Investigate before writing.** Every documentation claim must be verified against actual code. Do not copy text from planning documents or prompts — describe what the code does now.
2. **Respect the 10-file governance cap** from `.cursorrules` Rule 9: exactly 3 docs (`docs/system_architecture.md`, `docs/data_contracts.md`, `docs/excel_reporting_standards.md`), exactly 4 mdc files (`.cursor/rules/architecture.mdc`, `auto_documentation.mdc`, `crawler_engine.mdc`, `excel_engine.mdc`), plus `README.md`, `.cursorrules`, and `.cursorignore`. Do NOT create new governance files. All findings go into the existing files.
3. **Keep the existing structure and headings** in each file where possible. Add new sections, update existing sections, and mark any removed features. Do not reorganise the document structure unless a section is completely obsolete.
4. **Use British English** per `.cursorrules` Rule 8.
5. **Run `uv run pytest` after updating docs** to confirm nothing is broken by any incidental changes.
6. **Do not touch any Python source code in this prompt.** This is a documentation-only task.

---

## PHASE 1 — INVESTIGATION (do ALL of this before writing any documentation)

Run every investigation command below. Paste the output into a temporary section in `AUDIT_FIX_LOG.md` under `## Governance Sync — Investigation Output`. This is your source of truth for Phase 2.

### 1.1 — Directory structure

```bash
# Full src tree (2 levels deep)
find src/hype_frog -maxdepth 2 -type f -name "*.py" | sort

# Are there new directories beyond the documented set?
ls -la src/hype_frog/
# Check for: validators/, analysis/, checkpoint/ — do they exist?
```

Document: which directories exist under `src/hype_frog/` that are NOT mentioned in current docs.

### 1.2 — Rules engine: IssueRule structure

```bash
# What is the return type of get_summary_rules?
grep -n "def get_summary_rules" src/hype_frog/rules/registry.py
# Show first 80 lines of the file to see the data structure
head -80 src/hype_frog/rules/registry.py

# Is IssueRule a dataclass or tuple?
grep -n "class IssueRule\|@dataclass\|NamedTuple" src/hype_frog/rules/registry.py

# What scope values exist?
grep -n "scope=" src/hype_frog/rules/registry.py | head -20

# Count total rules
grep -c "IssueRule(" src/hype_frog/rules/registry.py
```

Document: the exact data structure used for rules, the `scope` field values, and a count of rules by scope.

### 1.3 — PSI engine: CrUX detection

```bash
# Check for origin detection logic
grep -n "origin_fallback\|originLoadingExperience\|crux_data_level\|CrUX Level\|_detect_crux_level\|_field_experience_metrics" src/hype_frog/crawler/psi_engine.py | head -20

# Check PSI Data Status values
grep -n "PSI Data Status\|CWV Data Source\|Field vs Lab" src/hype_frog/crawler/psi_engine.py | head -20

# Check what categories are requested from PSI API
grep -n "category\|categories\|performance\|accessibility\|best.practices\|seo" src/hype_frog/crawler/psi_engine.py | head -15
```

Document: whether CrUX origin detection exists, what labels it uses, and what Lighthouse categories are requested.

### 1.4 — Data assembler: indexability and status code handling

```bash
# Check finalize_row_state for status code handling
grep -n "status_int\|status_raw\|Timeout\|Not Indexable\|Indexability" src/hype_frog/crawler/data_assembler.py | head -20

# Check if string status codes are handled
grep -n "Timeout\|timeout\|Connection Error\|DNS Error" src/hype_frog/crawler/data_assembler.py | head -10
```

Document: whether the Timeout/string status code bug is fixed and how indexability is determined.

### 1.5 — GSC coverage: null vs zero handling

```bash
grep -n "GSC Clicks\|GSC Impressions\|GSC CTR\|GSC Avg Position" src/hype_frog/pipeline/gsc_coverage.py | head -20
# Check what value is written when GSC is unavailable
grep -A5 "else:" src/hype_frog/pipeline/gsc_coverage.py | head -15
```

Document: whether GSC columns write `None` or `0.0` when unavailable.

### 1.6 — Crawl runner: URL parameter exclusion

```bash
# Check for WooCommerce/parameter exclusion
grep -n "EXCLUDED_QUERY_PARAMS\|add.to.cart\|_is_crawlable_html_candidate" src/hype_frog/orchestration/crawl_runner.py | head -15

# Check what params are excluded
grep -A15 "EXCLUDED_QUERY_PARAMS" src/hype_frog/orchestration/crawl_runner.py | head -20
```

Document: the exact exclusion list and where it's applied.

### 1.7 — Link inventory deduplication

```bash
grep -n "dedup\|seen_keys\|seen\|duplicate" src/hype_frog/reporter/sheets/merged_builders.py | head -10
```

Document: whether dedup exists and what key it uses.

### 1.8 — Click depth and orphan handling

```bash
grep -n "click_depth\|Click Depth\|orphan\|-1\|homepage" src/hype_frog/pipeline/graph_engine.py | head -20
```

Document: what value is assigned for unreachable pages and how homepage is detected.

### 1.9 — Reporter: duplicate column prevention

```bash
grep -n "header_exists\|_column_exists\|Technical View\|BACK TO DASHBOARD" src/hype_frog/reporter/sheets/links.py src/hype_frog/reporter/sheets/navigation.py | head -15
```

Document: whether the duplicate column guard exists.

### 1.10 — Sheets: what sheets exist in the workbook

```bash
# Check TOC descriptions or sheet sequence
grep -rn "toc_descriptions\|sheet_sequence\|get_sheet_sequence\|CMS Action URLs\|Quick Wins\|Broken Link Impact" src/hype_frog/reporter/ | head -20

# Check the export flow for sheet names
grep -rn "sheet_name\|\"Dashboard\"\|\"Executive Dashboard\"\|\"CMS Action\"" src/hype_frog/orchestration/export_flow.py | head -30
```

Document: the complete list of sheets in the current output.

### 1.11 — Checkpoint system

```bash
# Check if checkpoint module exists
ls -la src/hype_frog/checkpoint/ 2>/dev/null || echo "No checkpoint directory"
grep -rn "checkpoint\|CrawlCheckpointer\|CheckpointState" src/hype_frog/ --include="*.py" | head -15
```

Document: what checkpoint functionality exists.

### 1.12 — New extractors and validators

```bash
# Check for new modules
ls -la src/hype_frog/extractors/ 2>/dev/null
ls -la src/hype_frog/validators/ 2>/dev/null
ls -la src/hype_frog/analysis/ 2>/dev/null

# Check for schema validator
grep -rn "schema_validator\|validate_schema\|SchemaValidationResult" src/hype_frog/ --include="*.py" | head -10

# Check for EEAT extractor
grep -rn "eeat\|E.E.A.T\|extract_eeat" src/hype_frog/ --include="*.py" | head -10

# Check for content similarity
grep -rn "simhash\|content_similarity\|Near.Duplicate" src/hype_frog/ --include="*.py" | head -10
```

Document: which new modules exist and which don't.

### 1.13 — Pydantic models: new fields

```bash
# Check MainRowPayload and ExtraRowPayload for new fields
grep -n "class MainRowPayload\|class ExtraRowPayload\|class CrawlRowPayload" src/hype_frog/core/models.py
# Show the models
grep -A30 "class MainRowPayload" src/hype_frog/core/models.py | head -40
grep -A30 "class ExtraRowPayload" src/hype_frog/core/models.py | head -40
```

Document: what fields exist in the current models.

### 1.14 — pyproject.toml vs actual dependencies

```bash
# Check if new dependencies were added
cat pyproject.toml | head -40
# Check if simhash, python-dateutil, reportlab exist
grep -i "simhash\|dateutil\|dateparser\|reportlab\|pillow" pyproject.toml
```

Document: which dependencies from the expansion prompts were actually added.

### 1.15 — Tests: what exists

```bash
find tests/ -type f -name "*.py" | sort 2>/dev/null || echo "No tests directory"
```

Document: what test files exist.

### 1.16 — Main column list: actual current state

```bash
# Find column definitions
grep -rn "MAIN_COLUMN_GROUP\|main_cols\|COLUMN_GROUP" src/hype_frog/reporter/ --include="*.py" | head -10
# Show the column group definitions
grep -rn "MAIN_COLUMN_GROUP_DEFINITIONS" src/hype_frog/reporter/sheets/layout.py 2>/dev/null | head -5
# If found, show the full definition
grep -A200 "MAIN_COLUMN_GROUP_DEFINITIONS" src/hype_frog/reporter/sheets/layout.py 2>/dev/null | head -250
```

Document: what columns are actually defined for the Main sheet.

### 1.17 — Conditional formatting on Main sheet

```bash
grep -rn "conditional_format\|ColorScale\|DataBar\|CellIsRule\|apply_main_sheet\|conditional" src/hype_frog/reporter/ --include="*.py" | head -20
```

Document: whether conditional formatting exists on the Main sheet.

### 1.18 — FixPlan: current column structure

```bash
grep -rn "build_fixplan_rows\|FIXPLAN_COLUMNS\|Affected Link Instances\|Affected Count" src/hype_frog/reporter/ --include="*.py" | head -15
```

Document: what columns exist in FixPlan.

### 1.19 — IssueInventory: scope branching

```bash
grep -rn "build_issue_inventory_rows\|site.wide\|server config\|Affected URL Count" src/hype_frog/reporter/summary_builder.py | head -15
```

Document: whether the site-level scope branching exists in IssueInventory.

### 1.20 — Quick test and smoke gate

```bash
grep -rn "quick.test\|quick_test\|--quick-test" src/hype_frog/ --include="*.py" | head -10
```

Document: whether the `--quick-test` functionality described in README still matches the code.

---

## PHASE 2 — UPDATE EACH FILE

After completing ALL investigation commands and documenting findings, update each file below based ONLY on what the investigation revealed. Do not speculate about features that weren't found in the code.

---

### 2.1 — Update `docs/system_architecture.md`

**Read the investigation output for items 1.1–1.20 before writing.**

Update these sections based on what you found:

**Layers section:** Add any new directories (e.g. `validators/`, `analysis/`) found in 1.1. Remove any directories that no longer exist. Update the description of each layer to match current responsibilities.

**Staged async pipeline section:** Update the sequence to include any new enrichment steps found (schema validation, E-E-A-T, content similarity — but ONLY if they actually exist in the code per 1.12).

**BFS spider section:** If 1.6 confirmed WooCommerce parameter exclusion exists, document the exclusion mechanism and the parameter list.

**Pydantic data contracts section:** If 1.13 revealed new fields, update the field descriptions. Cross-reference `data_contracts.md`.

**Rules section:** If 1.2 confirmed `IssueRule` dataclass with `scope` field, document:
- The dataclass structure (severity, name, fn, scope)
- The scope values used: "url", "site", "server" (and any others found)
- How scope affects IssueInventory and FixPlan output
- The total rule count

**PSI / CWV section:** If the architecture doc doesn't have a PSI section, add one based on 1.3 findings. Document:
- What API calls are made (mobile + desktop PSI, which Lighthouse categories)
- How CrUX origin vs URL-level detection works (if it exists per 1.3)
- What labels are used for `PSI Data Status`, `Field vs Lab`, `CWV Data Source`
- How origin-level data is handled differently from URL-level data

**Fetch modes / extraction contract section:** If 1.4 revealed Timeout string handling, document it under the extraction contract. If status code normalisation exists, document it.

**Workbook integrity section:** If 1.10 found new sheets (e.g. `CMS Action URLs`), add them to the sheet list. Document any new sheets.

**Add a new "CMS Action URLs" subsection** if 1.10 confirmed the sheet exists, explaining what it contains and why.

---

### 2.2 — Update `docs/data_contracts.md`

**Read investigation items 1.2, 1.3, 1.4, 1.5, 1.8, 1.13, 1.14 before writing.**

Update these sections:

**Crawl result envelope:** Update the `main` and `extra` field descriptions if 1.13 revealed new fields in the Pydantic models.

**Additive key policy:** If new columns were added by the 8 phases, document them as established keys that must not be removed. Specifically check for:
- `CrUX Level`, `Origin CrUX LCP (s)`, `CWV Data Source` (from PSI changes)
- `Is Thin Content`, `Is Near Duplicate`, `Is Draft or Test Page` (from duplicate detection)
- `E-E-A-T Signal Score` and related fields
- `Schema Present`, `Schema Valid`, `Schema Error Count`
- `Content Age (days)`, `Freshness Status`
- `Reachable from Homepage`

BUT only document keys that actually exist in the code per investigation. Do not list planned features.

**GSC data section:** Add a section documenting that GSC columns use `None` (not `0.0`) when GSC data is unavailable (if confirmed by 1.5). Explain the semantic difference.

**Issue rules contract:** Add a section documenting the `IssueRule` dataclass and `scope` field (if confirmed by 1.2). This is a new contract that `summary_builder.py` and `engine_rows.py` depend on.

**SQLite cache versioning:** Check if the cache version was incremented for any of the 8 phases. Document current version if found.

---

### 2.3 — Update `docs/excel_reporting_standards.md`

**Read investigation items 1.7, 1.9, 1.10, 1.17, 1.18, 1.19 before writing.**

Update these sections:

**Reporter module ownership:** If new sheet builders were added (e.g. for `CMS Action URLs`, `Quick Wins`, `Broken Link Impact`), document them and their file locations.

**Link Inventory deduplication:** If 1.7 confirmed dedup exists, add a section documenting the dedup key and behaviour.

**Duplicate column prevention:** If 1.9 confirmed the guard exists, add a section documenting the `_header_exists_in_worksheet` (or equivalent) pattern.

**IssueInventory scope branching:** If 1.19 confirmed site-level scope branching, document the behaviour: site/server-scoped issues generate one aggregate row with `Affected URL Count` instead of per-URL rows.

**FixPlan columns:** If 1.18 confirmed `Affected Link Instances` as a new column, document it.

**Conditional formatting on Main:** If 1.17 confirmed conditional formatting exists on the Main sheet, document the rules (which columns, which format types).

**New sheets:** If 1.10 found sheets not documented, add entries for each with a description of their purpose, column structure, and tab colour group.

**TOC requirements:** If new sheets exist, note that they need TOC entries.

---

### 2.4 — Update `.cursorrules`

**Read all investigation items before writing.**

Update these rules:

**Rule 1 (Architecture ownership):** If new directories exist (e.g. `validators/`, `analysis/`), add them to the ownership list with their responsibility description.

**Rule 2 (Typed chain-of-trust):** If `IssueRule` dataclass is in `rules/registry.py` (not `core/models.py`), update the reference. If the chain-of-trust model has been extended by new contracts, document them.

**Rule 9 (Consolidated layout):** Verify the 10-file cap is still correct. If `AUDIT_FIX_LOG.md` exists at root, decide whether it should be in the cap or explicitly excluded (it's an operational log, not a governance file — exclude it from the cap with a note).

**Rule 10 (Advanced Tooling):** Verify that MCP references (`sequential-thinking`, `firecrawl-mcp`, `brave-search`, `filesystem`, `chrome-devtools`) are still relevant to the project's actual tooling. If any are no longer used, remove them. If new tooling was adopted, add it.

---

### 2.5 — Update `.cursor/rules/architecture.mdc`

**Read investigation items 1.1, 1.2, 1.3, 1.4, 1.6 before writing.**

Update:

**Module boundaries:** Add any new directories found in 1.1 (validators, analysis, etc.) with their responsibility.

**Data flow:** Update step 4 (enrichment) to include any new enrichment passes confirmed by investigation.

**AI/LLM operational governance:** Verify this section is still accurate. If new LLM integrations were added (e.g. for search intent or content analysis), ensure the timeout/fallback rules cover them.

---

### 2.6 — Update `.cursor/rules/crawler_engine.mdc`

**Read investigation items 1.3, 1.4, 1.6 before writing.**

Update:

**Extraction contract:** If "Timeout" string status is now handled (per 1.4), add it to the extraction state documentation. Document how non-integer status codes interact with the `complete`/`partial`/`skipped` contract.

**Skipped with reason:** If new `skip_reason` tokens were added by any phase, document them.

**Dual-mode behaviour:** If PSI categories were expanded (e.g. accessibility, best-practices, seo added to the API call per 1.3), document this.

**Add a new "URL parameter exclusion" section** if 1.6 confirmed the mechanism exists. Document the exclusion list and where to extend it.

---

### 2.7 — Update `.cursor/rules/excel_engine.mdc`

**Read investigation items 1.7, 1.9, 1.10, 1.17, 1.18, 1.19 before writing.**

Update:

**New sheets section:** If new sheets exist (per 1.10), update the "New sheets" section to include them.

**Add "Link Inventory deduplication" note** if 1.7 confirmed it.

**Add "Main sheet conditional formatting" section** if 1.17 confirmed it. Document the rule types and columns affected.

**Add "Duplicate column prevention" note** if 1.9 confirmed the guard.

---

### 2.8 — Update `README.md`

**Read investigation items 1.1, 1.11, 1.12, 1.14, 1.15, 1.20 before writing.**

Update:

**Project structure table:** If new directories exist (per 1.1), add rows. If directories were removed, remove rows.

**Tech stack table:** If new dependencies were added to `pyproject.toml` (per 1.14), add them. Examples: `simhash`, `python-dateutil`.

**What it does section:** If new capabilities were added (schema validation, E-E-A-T, content freshness, etc.), add bullet points.

**Running section:** If new CLI flags exist (per investigation of `main.py`), document them.

**Quick test section:** If `--quick-test` behaviour changed (e.g. new sheets to verify), update the description.

**Configuration section:** If new environment variables were added (for new features), document them.

---

### 2.9 — Update `pyproject.toml`

**Read investigation item 1.14 before writing.**

If new dependencies were added to `pyproject.toml` that are not listed in the current version, this should already be correct. But verify:
- Are all actually-imported packages listed as dependencies?
- Run: `grep -rn "^import\|^from" src/hype_frog/ --include="*.py" | grep -v __pycache__ | awk '{print $2}' | sort -u | head -40` to find all imported packages.
- Cross-reference against `pyproject.toml` dependencies.

If any import is not covered by a dependency (e.g. `simhash` imported but not in pyproject.toml), add it.

**Version:** Consider bumping from `0.2.0` to `0.3.0` given the volume of changes across 8 phases. Note in `AUDIT_FIX_LOG.md` if you bump it.

---

### 2.10 — Update `.cursorignore`

**Read investigation item 1.1 before writing.**

Check if any new directories should be added to `.cursorignore`:
- `reports/` — crawl output files (if they exist at project root)
- `test_outputs/` — test crawl outputs
- `secrets/` — OAuth tokens and API keys
- `.cache/` — already excluded, verify still present

Do NOT add source directories or governance files to `.cursorignore`.

---

### 2.11 — Update `auto_documentation.mdc`

**Read all investigation items before writing.**

This file defines the doc-sync discipline. Check:
- Does the "Continuous documentation sync" table correctly map areas to canonical locations?
- Should new areas be added to the table? For example:
  - PSI/CWV/CrUX behaviour → `docs/system_architecture.md`
  - Issue rule scope system → `docs/data_contracts.md`
  - New sheets and conditional formatting → `docs/excel_reporting_standards.md`

If the table is incomplete, add rows for the new areas.

---

## PHASE 3 — VERIFICATION

After all documentation updates are written:

1. **Read each updated file in full** and verify:
   - No section references a feature that was NOT found during investigation
   - No section omits a feature that WAS found during investigation
   - Cross-references between files are consistent (e.g. if `system_architecture.md` references `IssueRule`, `data_contracts.md` must also document it)

2. **Run tests:**
   ```bash
   uv run pytest
   ```
   Confirm they pass (documentation changes should not break tests, but verify).

3. **Update `AUDIT_FIX_LOG.md`:**
   ```markdown
   ## Governance Sync — LI-HF-DOCSYNC-P0

   ### Investigation completed: [date]
   ### Files updated:
   - [ ] docs/system_architecture.md
   - [ ] docs/data_contracts.md
   - [ ] docs/excel_reporting_standards.md
   - [ ] .cursorrules
   - [ ] .cursor/rules/architecture.mdc
   - [ ] .cursor/rules/auto_documentation.mdc
   - [ ] .cursor/rules/crawler_engine.mdc
   - [ ] .cursor/rules/excel_engine.mdc
   - [ ] README.md
   - [ ] pyproject.toml
   - [ ] .cursorignore

   ### Key findings from investigation:
   - [summarise what was actually in the code vs what docs said]

   ### New directories found: [list]
   ### New columns confirmed: [list]
   ### New sheets confirmed: [list]
   ### Features NOT found (planned but not implemented): [list]
   ```

---

## THINGS YOU MUST NOT DO

- Do not create new governance files (stay within the 10-file cap + `.cursorignore`).
- Do not modify any Python source code — this prompt is documentation-only.
- Do not document features that were NOT found during investigation, even if they were mentioned in planning documents.
- Do not remove existing content from governance files unless investigation confirms the feature no longer exists in the code.
- Do not reorganise the document structure of `system_architecture.md` or other docs — add new sections at the end or within existing sections.
- Do not remove the `uv.lock` file or modify it directly — it is auto-generated by `uv sync`.

