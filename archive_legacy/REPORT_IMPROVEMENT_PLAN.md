# Executive Report Improvement Plan (HTML + PDF)

**Scope:** the client-facing executive deliverables produced at the end of a run —
the PDF executive summary and the self-contained HTML report.

**Source artefacts reviewed**
- `reports/full_smoke_test/..._executive_summary.pdf`
- `reports/full_smoke_test/..._122419.html`

**Code under review**
- `src/hype_frog/reporter/pdf_exporter.py`
- `src/hype_frog/reporter/html_report_data.py`
- `src/hype_frog/reporter/html_report_renderer.py`
- `src/hype_frog/reporter/html_report_writer.py`
- `src/hype_frog/orchestration/export_flow.py` (wiring; PDF lines ~952-968, HTML lines ~970-995)

> **Context:** these sample files come from `--full-smoke-test`, which uses synthetic
> fixtures (`/smoke-archive/page-N`). Some `0%`/`0` values are **mocked-data artefacts**,
> not product bugs. This plan separates genuine rendering/logic defects (reproducible on
> real runs) from smoke-data artefacts.

---

## 1. Root problem: two divergent aggregation paths

The PDF and HTML describe the **same audit with different numbers** because each aggregates
independently, from different row sources, with different key names and different semantics.

| Fact | PDF | HTML | Cause |
|---|---|---|---|
| Missing Title affected | 72 URLs | 83 pages | PDF reads `fixplan_rows` (`Issue Type`/`Affected Count`); HTML reads `summary_rows` (`Issue`/`Affected URL Count`) |
| No Schema Markup | 72 | 83 | same |
| Headline severity | 197 / 727 **instances** | 83 / 0 **pages** | PDF counts issue instances; HTML counts pages by severity badge |
| Effort unit | T-shirt (`M`/`S`) | Hours (`30h`/`32h`) | PDF reads `Effort`; HTML aggregates `Est. Hours` per sprint |
| PSI / GSC / content readiness / severity bar | absent | present | only HTML builds them |
| Quick wins | present | absent | only PDF builds them |

**Root cause:** `pdf_exporter._aggregate_kpis()` / `_top_issues()` is a parallel re-implementation
of `html_report_data.build_report_context()`. They will keep drifting. **Collapsing to one
`ReportContext` is the highest-leverage fix.**

---

## 2. Genuine defects (reproduce on real runs)

### D1 — Quick-win effort always renders `?` (variable clobbering) — **PDF**
In `export_flow.py`, `quick_wins_rows` is built correctly (~line 394 via `build_quick_wins_rows`,
which carries effort fields), then **overwritten** (~lines 504-509) with dashboard action-hub dicts
shaped `{"Block","URL","Issue"}`. The clobbered version is handed to the PDF (~line 961), so
`pdf_exporter` looks up `row.get('Effort (hrs)')`, misses, and prints the `'?'` fallback.
**Impact:** PDF "Quick wins" effort is meaningless; the real Quick Wins data is discarded for the PDF.

### D2 — PDF "Status" column is meaningless — **PDF**
`pdf_exporter.py` (~lines 182-205) emits a `●` glyph whose only signal is text colour, with **no
legend**. In extracted text it degrades to `l`. `rag` at ~line 191 is dead code (recomputed at ~203).
**Fix:** add a RAG legend + word label, or remove the column; delete the dead assignment.

### D3 — HTTP status table renders all zeros — **HTML**
`html_report_data.py` (~lines 142-162) counts `Status Code` only when not `None`, but on this path
`Status Code` is `None`, so the table shows `200 OK: 0` everywhere — directly contradicting the PDF's
"Non-200 Status (Critical, 11 URLs)". On real runs status may live elsewhere (e.g. `status_by_url`).
**Fix:** source status reliably; when unmeasured, show an explicit "Not measured" state, not silent `0`.

### D4 — Severity bar contradicts the issues table — **HTML**
The bar (page-level `Severity Badge`: Critical 83 / Warning 0 / Observation 0) sits above a Top-Issues
table full of Warning/Observation badges affecting 83 pages each. Looks broken to a reader.
**Fix:** relabel both axes ("Pages by worst severity" vs "Issues by rule severity") or reconcile into
one structure with a visible total.

### D5 — Priority Pages "Action" shows "Yes"; GSC not joined — **HTML**
`html_report_data.py` (~line 232) pulls `Why Prioritized`, but that field holds a Yes/No flag, so every
row reads "Yes" under a header labelled "Action". The human-readable reason is never surfaced. Every
priority page shows `0` impressions while GSC reports 1,459 — GSC metrics aren't joined onto priority rows.
**Fix:** surface the real reason text, join GSC impressions, relabel the column consistently with the code.

### D6 — Date provenance differs — **PDF vs HTML**
PDF stamps `datetime.now()` (`pdf_exporter.py` ~line 160) as "Audit date"; HTML uses the crawl
`run_timestamp`. Regenerating the PDF later silently changes the audit date.
**Fix:** pass the crawl `run_timestamp` into the PDF.

### D7 — Branding defaults diverge — **PDF vs HTML**
PDF default brand `#1a365d` (export_flow ~964) vs HTML `#1e293b` (~990); PDF prepared-by defaults to
"Your agency team", HTML to blank. Same client, two looks.
**Fix:** share default brand colour and prepared-by between both deliverables.

---

## 3. Smoke-data artefacts (cosmetic here; harden so QA is meaningful)

- SEO Health `0.0%`, AEO `15%`, and every Content Readiness factor `0.0%` — the full-smoke fixtures
  don't populate `SEO Health Score`, `H1 Count`, `Meta Description Missing`, `Schema Types Count`, etc.
  on the rows the report reads, so the executive report looks alarming/empty.
- `/smoke-archive/page-N` slugs and `0 impressions` everywhere make the sample unusable for visual QA.

**Implication:** the smoke test cannot currently catch report regressions by eye. Richer fixtures fix this.

---

## 4. UX / polish gaps (both documents)

- Colour-only RAG encoding with no text label — accessibility / greyscale-print risk.
- No totals reconciliation (e.g. critical + warning + observation = total).
- PDF omits PSI, GSC, projected health, remediation roadmap (HTML has them); HTML omits quick wins.
  Neither deliverable is a superset of the other.
- British English is mandated (`.cursorrules` §8) — verify copy ("Optimization" vs "Optimisation").
- Missing data silently becomes `0` — no explicit "data not available" affordance.

---

## 5. Phased remediation plan

> **Status:** Phase 1 ✅ done · Phase 2 ✅ done · Phase 3 ✅ done · Phase 4 ✅ done. All phases complete.

### Phase 1 — Stop the bleeding (correctness; ~½ day; low risk) — ✅ DONE
- [x] **P1.1 (D1)** Renamed the dashboard action-hub list in `export_flow.py` to `dashboard_quick_win_rows`
      so the real `quick_wins_rows` survives to the PDF.
- [x] **P1.2 (D1)** Verified PDF quick-win keys (`Issue`, `Effort (hrs)`) match `build_quick_wins_rows`;
      effort now renders (e.g. "effort 4.0 hrs").
- [x] **P1.3 (D2)** Replaced the PDF status glyph with a coloured **word** + legend; removed dead `_rag_colour`.
- [x] **P1.4 (D3)** HTML status table now shows "HTTP status codes were not captured…" when unmeasured.
- [x] **P1.5 (D5)** Verified current code already surfaces the reason + joins GSC impressions ("Why Prioritised");
      the original artefact was stale. Residual `0 impressions` on smoke pages is fixture-driven (Phase 4).

### Phase 2 — One source of truth (structural; ~1 day) — ✅ DONE
- [x] **P2.1 (root)** Refactored `pdf_exporter.py` to consume the shared `ReportContext`; deleted
      `_aggregate_kpis` / `_top_issues`. PDF and HTML now show identical top-issue counts (83, not 72).
- [x] **P2.2** Standardised effort to **hours** (PDF sprint plan now mirrors HTML) and severity headline to
      **page counts** (`critical_url_count` / `warning_url_count`) in both renderers.
- [x] **P2.3 (D6, D7)** Unified branding (`#1e293b`) + prepared-by defaults (resolve `HF_REPORT_*` then
      `HF_PDF_*`); PDF audit date now comes from the crawl `run_timestamp`.

**Phase 2 verification:** 149 reporter/orchestration tests pass; lint clean; regenerated smoke artefacts
confirm PDF and HTML agree on KPIs, top issues (83 pages), and the sprint plan (Total 28 / 130h).
Canonical doc synced: `docs/excel_reporting_standards.md` → "Single source of truth for executive deliverables".

### Phase 3 — Clarity & parity (~1 day) — ✅ DONE
- [x] **P3.1 (D4)** HTML severity section relabelled "Pages by Worst Severity" with a visible total
      ("— N pages total") and a caption clarifying worst-severity-per-page vs per-issue counts; a matching
      caption added under "Top Issues by Impact".
- [x] **P3.2** Parity achieved: PDF now includes Mobile PSI, Projected SEO health, and a Search Console
      section; HTML now includes a Quick Wins section. Both deliverables present the same shared facts.
- [x] **P3.3** RAG now carries text everywhere (PDF status words + legend incl. PSI band; HTML severity
      counts/total; numeric values in every table cell). British English verified — no American spellings
      in user-facing copy (only CSS `color` and the upstream `Why Prioritized` data key, rendered as
      "Why Prioritised").

**Phase 3 verification:** reporter tests pass (incl. new severity/quick-wins assertions); lint clean;
regenerated smoke artefacts confirm PDF and HTML show the same KPIs, GSC, PSI, projected health, top
issues (83 pages), quick wins, and sprint plan.

### Phase 4 — Representative smoke output + regression guards (~½ day) — ✅ DONE
- [x] **P4.1** Enriched `full_smoke_fixtures.py` with deterministic, index-seeded content/SEO/AEO signals
      (title/meta/H1/schema/E-E-A-T/OG/headers/answer paragraphs/FK grade, plus regional authority).
      The homepage is left pristine; issues are seeded on deeper pages so the pipeline computes a real
      spread. Regenerated smoke now reports **SEO health ≈ 61%, AEO ≈ 92%, 17 critical / 63 warning / 3
      observation pages, projected ≈ 95%**, and a populated HTTP status table (200:65, 3xx:7, 4xx:6,
      timeout:5 = 83) — replacing the all-missing 0%/all-critical baseline.
- [x] **P4.2** Added `tests/reporter/test_executive_report_parity.py`:
      - PDF and HTML build from the **same** `ReportContext` → top-issue counts cannot diverge.
      - Quick-win effort is always numeric (a row omitting `Effort (hrs)` still yields a `float`, never `?`).
      - Severity bar total reconciles (`critical + warning + observation == "N pages total"`).
      - PDF audit date derives from the crawl timestamp (D6 guard).
- [x] **P4.3** `uv run pytest` (full suite) and `ruff` pass before marking done; removed a pre-existing
      unused import surfaced by lint in the touched fixtures file.

**Phase 4 verification:** full `uv run pytest` green; `ruff check` clean; regenerated smoke artefacts
confirm PDF and HTML agree (SEO 61 vs 61.3, 17 critical, PSI 88, projected 95/94.9, GSC 53 clicks /
1,459 impressions) and the status table + severity tally both reconcile to 83 URLs.

---

## 6. Docs to sync on implementation (governance §8 / auto_documentation)
- `docs/excel_reporting_standards.md` — HTML/PDF report sections.
- `docs/data_contracts.md` — the shared `ReportContext` contract.
- `.env.example` — only if branding/default env vars change.

---

## 7. Sequencing recommendation
1. **Phase 1** first — tight, mostly single-file correctness pass, easy to verify.
2. **Phase 2** next as a separate reviewable diff — the `ReportContext` consolidation that makes
   Phase 1's fixes verifiable in one place.
3. Phases 3-4 follow.

> **Governance note (`.cursorrules` §4):** Phases 1-2 touch ≥3 files
> (`export_flow.py`, `pdf_exporter.py`, `html_report_data.py`, plus tests) and require explicit
> approval; keep each phase a small, reviewable diff. **Git Sovereignty (§11):** no git commands —
> the user owns all repository state.

---

## 8. Defect → fix traceability

| ID | Symptom | File(s) | Phase |
|---|---|---|---|
| Root | PDF vs HTML numbers disagree | `pdf_exporter.py`, `html_report_data.py` | P2.1 |
| D1 | Quick-win effort `?` | `export_flow.py`, `pdf_exporter.py` | P1.1, P1.2 |
| D2 | Meaningless PDF status dots | `pdf_exporter.py` | P1.3 |
| D3 | HTML status table all zeros | `html_report_data.py` | P1.4 |
| D4 | Severity bar vs issues contradiction | `html_report_data.py`, `html_report_renderer.py` | P3.1 |
| D5 | Priority "Action = Yes"; no GSC join | `html_report_data.py` | P1.5 |
| D6 | PDF date drift | `pdf_exporter.py`, `export_flow.py` | P2.3 |
| D7 | Branding defaults diverge | `export_flow.py` | P2.3 |
| D8 | Smoke output unrepresentative (0% health, all-critical, zeroed status) | `full_smoke_fixtures.py` | P4.1 |
| D9 | No regression guard against PDF/HTML divergence | `tests/reporter/test_executive_report_parity.py` | P4.2 |
