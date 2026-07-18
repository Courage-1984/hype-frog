# Workbook tabs — end-user reference

Canonical, per-tab inventory of every Excel tab produced by a full-suite hype-frog export: audience, content summary, and end-user descriptions.

**Related:** [`excel_reporting_standards.md`](excel_reporting_standards.md) (formatting/view-state rules for these tabs), [`system_architecture.md`](system_architecture.md) (pipeline overview), [`data_contracts.md`](data_contracts.md) (row payloads feeding these sheets).

**Canonical code sources**

| Concern | Location |
|---------|----------|
| Tab order & visibility | `src/hype_frog/reporter/sheets/workbook_layout.py` |
| Short TOC blurbs | `src/hype_frog/reporter/engine_guardrails.py` (`_TOC_FRIENDLY_DESCRIPTIONS`) |
| Sheet builders | `src/hype_frog/orchestration/export_workbook.py`, `export_registry.py`, `reporter/sheets/merged_builders.py` |
| Reporting standards | `docs/excel_reporting_standards.md` |

**How the workbook is organised**

- The workbook **opens on Executive Briefing**; **Table of Contents** stays left-most (index 0).
- Tab colours follow persona grouping: Management (dark blue-grey), Content (green), Technical (blue), Inventory (orange), Advanced (purple), Historical (grey).
- **Advanced** tabs are **hidden by default**. Open them via TOC / Executive Briefing links, or Excel → Unhide Sheet.
- Full suite exports **31 tabs**: 15 primary (visible) + 16 advanced/historical.

---

## Primary workflow (visible)

### Table of Contents

| | |
|---|---|
| **Audience** | Everyone |
| **Colour group** | Default (no persona colour) |
| **What it is** | Index of every tab with section labels, Open hyperlinks, and short blurbs. |
| **Content** | Section \| Open link \| Description. Split into *Primary workflow* vs *Technical & Historical (Advanced)*. |

**End-user description**

> Start here for navigation. Jump to any sheet via the Open links. Advanced technical and historical tabs are listed but hidden by default to keep the tab bar focused.

---

### Executive Briefing

| | |
|---|---|
| **Audience** | Management / stakeholders |
| **Colour group** | Management |
| **What it is** | Landing dashboard — KPIs, charts, triage, and deep-links. |
| **Builder** | `reporter/sheets/executive_dashboard.py` (`write_executive_briefing`) |
| **Content** | KPI cards (SEO health now/projected, AEO readiness, traffic lift, PSI); key insights; charts (health comparison, severity, priority URLs, content readiness, status, traffic/AEO); owner triage matrix; Advanced Sheets panel; chart source tables below. Freeze pins the title/KPI/insights band. |

**End-user description**

> Your executive overview of site health, risk, and next actions. Use the KPI cards and charts for the story; use the triage links to open FixPlan, Priority URLs, and advanced diagnostics.

---

### Priority URLs

| | |
|---|---|
| **Audience** | Technical SEO / project leads |
| **Colour group** | Technical |
| **What it is** | Pages ranked by business risk for immediate attention. |
| **Builder** | `orchestration/export_registry.py` (`build_priority_rows`) |
| **Key columns** | URL, Action Needed, Why Prioritized, Business Risk Score, Severity Badge, SEO Health Score, Critical/Warning Issues Count, GSC Impressions/CTR/Coverage, Revenue Intent, Owner, Status, Sprint |
| **UX notes** | Editable triage Status (`Open` / `In Progress` / `Resolved` / `Won't Fix`) and Sprint; Status/Sprint headers marked as editable inputs. |

**End-user description**

> High-value pages that need attention first, scored by issues, health, and commercial intent. Use Status and Sprint to triage ownership without leaving the sheet.

---

### FixPlan

| | |
|---|---|
| **Audience** | Technical SEO / delivery teams |
| **Colour group** | Technical |
| **What it is** | Prioritised backlog of issue types with effort, owners, and playbook links. |
| **Builder** | `reporter/engine_rows.py` (`build_fixplan_rows`) |
| **Key columns** | Issue Type, Severity, Priority Score, Affected Count/URLs, Detail Reference Tab, Resolution Type, Recommended Fix, What It Is, Likely Root Cause, Owner, Agency Owner, Effort, Est. Hours, Est. Sprint Points, Status, Verified By, Date Resolved, Revenue Risk, Action Needed, Jump to Details / Playbook, Sprint |
| **UX notes** | Rows are **issue types** (not one URL each). Workflow Status dropdown. Live Hub Status can INDEX/MATCH from Content Optimisation Hub. |

**End-user description**

> The master remediation plan: each row is an issue type (not one URL), with how many pages are affected, who should fix it, estimated effort, and links into Playbook and detail sheets. Track Status as work progresses.

---

### Quick Wins

| | |
|---|---|
| **Audience** | Technical SEO / content ops |
| **Colour group** | Technical |
| **What it is** | Top high-impact, low-effort URL×issue pairs (capped by config). |
| **Builder** | `reporter/sheets/merged_builders.py` (`build_quick_wins_rows`) |
| **Key columns** | URL, Issue, Severity, Priority Score, Business Risk Score, GSC Clicks (30d), Effort (hrs), What It Is, Why It Matters, Recommended Fix, How To Verify, Owner, Sprint, Revenue Risk, Jump to FixPlan, Jump to Playbook |

**End-user description**

> Fastest wins: concrete page-level fixes that score well on impact versus effort. Start here when you need early delivery momentum before tackling systemic FixPlan items.

---

### Content Optimisation Hub

| | |
|---|---|
| **Audience** | Content / editorial |
| **Colour group** | Content |
| **What it is** | Editorial command centre for on-page copy and SERP elements. |
| **Builder** | `reporter/engine_rows.py` (hub rows) + Hub formulas/layout in `reporter/sheets/` |
| **Key columns** | Action Required (`Needs Copy` / `Needs Optimisation` / `Complete`), On-Page Optimisation Score, SEO Score, Technical Health, Copy Score, Recommended Action, Priority Reason, semantic/AEO signals, Status, Assigned Owner, URL Slug Normalization, URL, Proposed URL Slug, Current Title/Meta/H1–H6 + Health formulas, Elementor Builder Link, OG Image fields, Open in Main |
| **UX notes** | Action Required is a **static Python classification** at export (not a live formula). Freeze through Assigned Owner + slug (`I3`). Status is a separate workflow column. Pair with Content Hub Metrics for ROI/CWV. Header row physically moves from row 1 to row 2 partway through formatting — see *Content Hub header-row timing* in `excel_reporting_standards.md` if touching this sheet's builder code. |

**End-user description**

> Day-to-day content workspace: see what each page needs (copy vs optimisation), edit titles/meta/headings with live health checks, and track workflow Status and owner. Pair with Content Hub Metrics for traffic and CWV context.

---

### Content Planner

| | |
|---|---|
| **Audience** | Content / design / client sign-off |
| **Colour group** | Content |
| **What it is** | Site-structure workflow tracker for production and approvals. |
| **Builder** | `orchestration/content_planner.py` (`build_content_planner_rows`) |
| **Key columns** | Primary, Secondary, Tertiary, Page link, Copy Doc, Copywriter Sign off, Copy First Check, 2nd Revisions, Client copy sign off, Web design off, UXI sign off, Visual Design sign off, Client final sign off, Optimisations, Desktop, Tablet, Mobile, SEO, Performance |
| **UX notes** | Identity columns A–E get scoped zebra banding (F:S carry their own RAG sign-off fills instead). Freeze `E3` (banner + header rows, columns A–D). |

**End-user description**

> Production checklist for every page in the site tree. Use the sign-off columns to track copy, design, and client approval through to go-live.

---

### Content Hub Metrics

| | |
|---|---|
| **Audience** | Content leads / SEO analysts |
| **Colour group** | Content |
| **What it is** | Companion metrics for the same Hub URL set. |
| **Builder** | Hub metrics split in content-hub row builders (`CONTENT_HUB_METRICS_EXPORT_COLUMNS`) |
| **Key columns** | URL, Search Intent, Search Intent Source, Instant Priority, Potential Traffic Lift, AEO Visibility Gain, JS Dependent, Raw Words, Rendered Words, Field LCP (ms), Field CLS, Anchor Text Diversity |

**End-user description**

> Supporting evidence for Hub decisions: intent, estimated ROI, JS dependence, word counts, field Core Web Vitals, and anchor diversity — without cluttering the editorial Hub.

---

### Main

| | |
|---|---|
| **Audience** | Analysts / inventory users |
| **Colour group** | Inventory |
| **What it is** | Primary crawled-URL inventory (wide sheet; triage columns visible first). |
| **Builder** | Main rows via crawl/pipeline assemble; written in export flow |
| **Visible triage columns** | Health Icon, URL, Status Code, Indexability, Load Time (s), Title, Meta Description, Word Count (Body), SEO Health Score, Severity Badge, Action Needed (+ Owner / Status / Sprint) |
| **UX notes** | Performance & CWV columns live in a collapsed/hidden group; **Technical Diagnostics** is the source of truth for PSI/CWV detail. Heatmaps on key score columns. Locale-formatted percent/integer/decimal/date columns via `apply_south_african_formats` — see `excel_reporting_standards.md`. |

**End-user description**

> Complete URL inventory from the crawl. Use the left-hand triage columns for filtering; expand column groups or open Technical Diagnostics when you need deep performance and indexability detail.

---

### AIOSEO Recommendations

| | |
|---|---|
| **Audience** | WordPress / AIOSEO users |
| **Colour group** | Technical |
| **What it is** | Plugin-aligned fix list with edit links. |
| **Builder** | `orchestration/export_row_builders.py` / AIOSEO row builder |
| **Key columns** | URL, WordPress Post ID, Direct Edit Link, AIOSEO Panel, Severity, Issue, Current Value, Recommended Target, Why It Matters, How to Fix in AIOSEO, Reference Tab, Reference Field, Action Needed, Owner, Status, Priority Score, Est. Hours, Stable Issue ID |

**End-user description**

> Actionable recommendations mapped to All in One SEO panels, with direct edit links and current vs target values. Use when the site is managed in WordPress with AIOSEO.

---

### Link Inventory

| | |
|---|---|
| **Audience** | Technical SEO / link QA |
| **Colour group** | Inventory |
| **What it is** | Anchor-level outbound link catalogue (deduped). |
| **Builder** | `merged_builders.build_link_inventory_rows` (streamed via SQLite cache) |
| **Key columns** | Source URL, Target URL, Anchor Text, Rel Attribute, Link Type, Status Code, Generic Anchor |
| **UX notes** | Dedup key: `(Source URL, Target URL, Anchor Text)`. |

**End-user description**

> Every distinct outbound link instance from the crawl — where it came from, where it goes, how it is labelled, and whether the destination responded successfully.

---

### Broken Link Impact

| | |
|---|---|
| **Audience** | Technical SEO |
| **Colour group** | Inventory |
| **What it is** | Broken destinations ranked by reach and traffic impact. |
| **Builder** | `merged_builders.build_broken_link_impact_rows` |
| **Key columns** | Priority Score, Broken URL, Status Code, Inbound Link Count, Source Page Clicks Total, Source Pages (first 5), Anchor Texts Used, Recommended Action |

**End-user description**

> Broken links ordered by how many pages point to them and how much Search Console traffic those sources earn. Fix high-priority rows first to recover the most value.

---

### SitemapQA

| | |
|---|---|
| **Audience** | Technical SEO |
| **Colour group** | Technical |
| **What it is** | Sitemap coverage and metadata quality checks. |
| **Builder** | `orchestration/export_registry.py` (`build_sitemapqa_rows`) |
| **Key columns** | Record Type (Sitemap File / URL), Sitemap URL, Final URL, Status Code, Found via Crawl/Sitemap, Discovery Source, In Sitemap but Non-200, Sitemap URL Redirects, Redirect Type, In Sitemap but Canonicalized Elsewhere, Missing lastmod/changefreq/priority, sitemap image fields, Lastmod vs HTTP Match, Canonical vs Sitemap Match, Crawled but Missing from Sitemap |

**End-user description**

> Quality assurance for your XML sitemaps: which URLs are in the sitemap versus the crawl, redirects and non-200 entries, missing sitemap tags, and pages crawled but absent from the sitemap.

---

### Template & Duplication Risks

| | |
|---|---|
| **Audience** | Technical SEO / developers |
| **Colour group** | Technical |
| **What it is** | Duplicate titles/meta plus folder-level template patterns. |
| **Builder** | `merged_builders.build_template_duplication_risks_rows` (from duplicates + pattern rows) |
| **Key columns** | URL, Risk Category, Subfolder / Template Group, Issue, Affected Ratio, Affected URL Count, Example URLs, Exact Action, Severity, Source Legacy Tab |

**End-user description**

> Systemic content risks: duplicate titles and descriptions, draft/copy pages, and template-wide defects (for example missing H1 across a folder). Prefer one template fix over dozens of one-off edits.

---

### Playbook

| | |
|---|---|
| **Audience** | All teams / client education |
| **Colour group** | Management |
| **What it is** | Standards reference plus per-issue how-to. |
| **Builder** | `orchestration/export_workbook_constants.py` + issue playbook rows from rules |
| **Content sections** | Meta Data Standards; On-Page Structure (H-Tags); AEO & Content; 2025 AEO Strategy; Issue Playbook (What / Fix / Verify); Glossary & Legend |
| **Columns** | Section, Item, Guideline, Why It Matters |

**End-user description**

> In-workbook education: editorial standards, answer-engine guidance, and a how-to playbook for each issue type — what it is, why it matters, how to fix it, and how to verify.

---

## Technical & historical (advanced — hidden by default)

### Issue Register

| | |
|---|---|
| **Audience** | Project managers / SEO leads |
| **Colour group** | Advanced |
| **What it is** | Canonical issue backlog (Summary roll-ups + per-URL rows). Legacy **IssueInventory** and standalone **Summary** tabs are no longer exported. |
| **Builder** | `merged_builders.build_issue_register_rows` |
| **Key columns** | URL, Section, Issue, Severity, Affected URL Count, Reference Area, Stable Issue ID, Owner, Sprint, Status, Affected URLs Sample, Source Legacy Tab, Source Row ID, Date First Detected, Days Open, Assigned To, Client Notes |

**End-user description**

> Single backlog of tracked issues with history (first seen, days open) and assignment fields. Use this as the living register; FixPlan remains the remediation plan by issue type.

---

### Technical Diagnostics

| | |
|---|---|
| **Audience** | Technical SEO / developers |
| **Colour group** | Advanced |
| **What it is** | Per-URL technical deep dive. |
| **Builder** | `merged_builders.build_technical_diagnostics_rows` |
| **Key columns** | URL, Diagnostic Category, Status Code, Severity Badge, SEO Health Score, Pass Flag, Critical/Warning Issues Count, Extraction State/Source, Indexability Reason, Canonical Type, Redirect Chain Length/Loop, security headers (HSTS, CSP, XCTO), Desktop/Mobile PSI, Mobile LCP/CLS/TTFB, Lighthouse & CrUX lab/field metrics, Final/Canonical URL, Meta Robots, X-Robots-Tag, GSC Index Status/Last Crawl/Coverage, Discovery Rank, Reachable from Homepage, Crawl Depth, Hreflang fields |

**End-user description**

> Full technical profile per URL: HTTP and indexability, security headers, redirects, PageSpeed/Core Web Vitals, and Search Console signals. Prefer this over Main for PSI and CWV detail.

---

### Content & AI Readiness

| | |
|---|---|
| **Audience** | Content / AEO specialists |
| **Colour group** | Advanced |
| **What it is** | Content depth, schema, media, and answer-engine readiness. |
| **Builder** | `merged_builders.build_content_ai_readiness_rows` |
| **Key columns** | URL, Content Category, Word Count, Readability (Rough Flesch), Flesch-Kincaid Grade, Thin Content Flag, H1 Count / Missing H1, Meta Description Missing, AEO Readiness Score / Badge, Schema Types Count/Found/Parse Errors, Question Heading Count, Answer Blocks, FAQ Section Count, Image Count, Images Missing Alt, Image Alt Coverage (%), AEO Extractability Score, Title Missing, Media Mixed Content Detected |

**End-user description**

> How ready each page is for search and answer engines: content depth, structure, schema, media alt coverage, and AEO extractability scores.

---

### Link Intelligence

| | |
|---|---|
| **Audience** | Technical SEO |
| **Colour group** | Advanced |
| **What it is** | Per-URL link summary plus broken-link triage detail. |
| **Builder** | `merged_builders.build_link_intelligence_rows` |
| **Key columns** | URL, Record Type, Target URL, Anchor Text, Target Status (if crawled), Crawlable, Internal/Broken/Unresolved/External Links Count, Inlinks Count, Orphan Candidate, Click Depth, Internal PageRank, Generic Anchor Text Count, Nofollow Internal/External Counts, Internal Link Statuses, Actionable Fixes |

**End-user description**

> Link health at page level: inlinks and outlinks, orphans, click depth, equity, and broken or generic anchors — with enough detail to plan internal-linking fixes.

---

### CMS Action URLs

| | |
|---|---|
| **Audience** | Developers / CMS owners |
| **Colour group** | Advanced |
| **What it is** | WooCommerce/CMS action-parameter URLs withheld from the crawl. |
| **Builder** | `orchestration/export_registry.py` (`build_cms_action_url_rows`) |
| **Key columns** | URL, Excluded Query Parameters, Exclusion Reason, Discovered On URL, Review Note |

**End-user description**

> Cart, add-to-cart, and similar CMS action URLs discovered but not crawled as pages. Review handlers and canonicals in the CMS; they appear here for audit visibility only.

---

### Redirects

| | |
|---|---|
| **Audience** | Technical SEO / developers |
| **Colour group** | Advanced |
| **What it is** | Redirect chain map with SEO risk flags. |
| **Builder** | `merged_builders.build_redirects_sheet_rows` |
| **Key columns** | URL, Status Code, Final URL, Redirect Chain, Chain Length/Hops, Has 302 in Chain, Has Mixed Redirect Types, Redirect Target, HTTP→HTTPS Redirect, Redirect Loop Flag, Redirect SEO Risk, Hop 1–3 URL/Status |

**End-user description**

> Every redirect path found in the crawl, hop by hop, with loops, temporary redirects, and SEO risk notes so you can shorten or correct chains.

---

### Robots.txt Analysis

| | |
|---|---|
| **Audience** | Technical SEO |
| **Colour group** | Advanced |
| **What it is** | Parsed robots.txt rules and conflicts. |
| **Builder** | `crawler/robots_mapping.py` (`build_robots_analysis_rows`) |
| **Key columns** | Section, User Agent, URL, Status, Detail |
| **Agents covered** | Googlebot, Bingbot, GPTBot, ClaudeBot, PerplexityBot |

**End-user description**

> How robots.txt treats key crawlers and AI bots, which paths are blocked, and where rules conflict with sitemap or crawl expectations.

---

### Crawl Log

| | |
|---|---|
| **Audience** | Operators / engineers |
| **Colour group** | Historical |
| **What it is** | Run-time errors and recovery notes. |
| **Builder** | `core/crawl_log.py` (`crawl_log_sheet_rows`) |
| **Key columns** | Timestamp, URL, Phase, Error Type, Error Detail, Recovery Action Taken |

**End-user description**

> Operational diary of fetch, render, PSI, and GSC problems during this audit — useful when results look incomplete or a URL failed unexpectedly.

---

### Link Equity Map

| | |
|---|---|
| **Audience** | Technical SEO |
| **Colour group** | Advanced |
| **What it is** | Internal equity / PageRank distribution. |
| **Builder** | `analysis/link_equity.py` (`build_link_equity_rows`) |
| **Key columns** | URL, Inbound Link Count, Unique Source Pages, Anchor Texts (top 5), PageRank Score, PageRank Percentile, Click Depth, Equity Tier, Recommended Action |

**End-user description**

> Where internal link equity concentrates: which pages are under-linked, how deep they sit from the homepage, and what to strengthen.

---

### Anchor Text Audit

| | |
|---|---|
| **Audience** | Technical SEO / content |
| **Colour group** | Advanced |
| **What it is** | Anchor-text quality by destination. |
| **Builder** | `analysis/link_equity.py` (`build_anchor_text_audit_rows`) |
| **Key columns** | Destination URL, Inbound Link Count, Generic Anchor Count, Generic Anchor %, Top Anchor Texts, Generic Anchor Dominance, Recommended Action |

**End-user description**

> Whether inbound anchors are descriptive or generic (“click here”). High generic share weakens relevance signals — rewrite anchors on the source pages.

---

### Snippet Opportunities

| | |
|---|---|
| **Audience** | Content / SEO |
| **Colour group** | Advanced |
| **What it is** | Featured-snippet / PAA-style opportunities. |
| **Builder** | `analysis/snippet_opportunities.py` |
| **Key columns** | URL, Current GSC Position, GSC Clicks, GSC Impressions, Snippet Type Detected, Featured Snippet Readiness, Recommended Restructuring, Effort |

**End-user description**

> Pages with the best chance of featured snippets or AI-style answers, plus suggested restructuring and effort level.

---

### Competitor Benchmarks

| | |
|---|---|
| **Audience** | Strategy / SEO leads |
| **Colour group** | Advanced |
| **What it is** | Sampled client-vs-competitor metric comparison. |
| **Builder** | `analysis/competitor_benchmarks.py` |
| **Key columns** | Metric, Client Site, plus competitor columns when configured |
| **UX notes** | **Optional** — only present when `--competitors` is configured for the run. |

**End-user description**

> Side-by-side snapshot of key on-page metrics versus configured competitor domains (sampled pages). Absent when no competitors were supplied for the run.

---

### Script Inventory

| | |
|---|---|
| **Audience** | Performance / developers |
| **Colour group** | Advanced |
| **What it is** | Known third-party trackers/tags (~19 common domains via PSI network requests) — **not** every script on the site. |
| **Builder** | `analysis/third_party_scripts.py` |
| **Key columns** | Domain, Service Name, Category, Pages Found On, Average Size (KB), Total Transferred (KB), Is Render Blocking |

**End-user description**

> Detected third-party tags and trackers (analytics, ads, chat, consent, etc.), where they load, transfer size, and whether they are render-blocking. Not a complete script catalogue.

---

### Image Inventory

| | |
|---|---|
| **Audience** | Content / performance |
| **Colour group** | Advanced |
| **What it is** | Image asset catalogue across the crawl. |
| **Builder** | `pipeline/image_inventory.py` |
| **Key columns** | Image URL, Image Category, Status Code, Size (KB), Width, Height, Is Broken, Is Oversized, Alt Text, Alt Source, File Extension, Found On Pages, Found On Pages (first 5) |

**End-user description**

> Every significant image found: broken or oversized files, alt-text coverage, dimensions, and which pages use them.

---

### DeltaFromPreviousRun

| | |
|---|---|
| **Audience** | Stakeholders / project leads |
| **Colour group** | Historical |
| **What it is** | Change report versus a prior audit. Resolved issues are folded into this sheet (no standalone ResolvedIssues tab). |
| **Builder** | `analysis/delta_sheet_builder.py` / `build_delta_workbook_output` |
| **Content sections** | Summary counts; New Issues; Resolved Issues; Metric changes; SEO health trend |
| **Key columns** | Section, Stable Issue ID, URL, Issue, Severity, Previous Value, Current Value, Change, Direction, First Seen, Last Seen, Days Open, Trend Run 1–3, Notes |
| **UX notes** | First run with no previous export shows a baseline note. |

**End-user description**

> What improved, what regressed, and what is new since the previous audit. On a first run with no prior export, this sheet records the baseline only.

---

### Audit Run Details

| | |
|---|---|
| **Audience** | Operators / auditors |
| **Colour group** | Historical |
| **What it is** | Run configuration and environment metadata. |
| **Builder** | Written in `export_workbook.write_full_suite_workbook` as Key/Value rows |
| **Typical keys** | Target Site, Run Timestamp, Total URLs, Duration (s), Crawl Mode, Extraction Source counts (Rendered / Raw HTTP / Fallback), GSC Data Freshness / Coverage Note, Mode, Semantic Engine probe, Semantic Analysis Modes, Workers, Delay Seconds, Retries, Timeout Seconds, Checkpoint Every, Previous Audit Path, External Link Unique Denominator / 200 OK, External Sniff / OG Image Validation flags |

**End-user description**

> Technical provenance for this workbook: how the crawl was configured, how long it took, and which enrichment sources (GSC, render, external sniff) were active. Use when reproducing or comparing runs.

---

## Quick reference — tab order

### Visible (`VISIBLE_WORKBOOK_TAB_ORDER`)

1. Table of Contents
2. Executive Briefing
3. Priority URLs
4. FixPlan
5. Quick Wins
6. Content Optimisation Hub
7. Content Planner
8. Content Hub Metrics
9. Main
10. AIOSEO Recommendations
11. Link Inventory
12. Broken Link Impact
13. SitemapQA
14. Template & Duplication Risks
15. Playbook

### Advanced / hidden (`ADVANCED_WORKBOOK_TAB_ORDER`)

1. Issue Register
2. Technical Diagnostics
3. Content & AI Readiness
4. Link Intelligence
5. CMS Action URLs
6. Redirects
7. Robots.txt Analysis
8. Crawl Log
9. Link Equity Map
10. Anchor Text Audit
11. Snippet Opportunities
12. Competitor Benchmarks
13. Script Inventory
14. Image Inventory
15. DeltaFromPreviousRun
16. Audit Run Details

---

## Retired / no longer exported

These appear in legacy TOC blurbs or older docs but are **not** current full-suite tabs:

- **Dashboard** / **Executive Dashboard** — replaced by **Executive Briefing**
- **Summary** — folded into **Issue Register**
- **IssueInventory** — replaced by **Issue Register**
- **ResolvedIssues** — folded into **DeltaFromPreviousRun**
- Standalone legacy tabs such as Technical, AEO, Content, Links, LinksDetail, Media, Schema & Metadata, Security, PSI Performance, Indexability, Duplicates, Pattern and Template Issues, Quick Reference Guide, Glossary & Legend, CrawlGraph — content lives in merged sheets (Technical Diagnostics, Content & AI Readiness, Link Intelligence, Template & Duplication Risks, Playbook, etc.)

---

## Planned: TOC/banner copy integration

The **End-user description** block under each tab above is written for direct reuse in:

1. TOC column C via `_TOC_FRIENDLY_DESCRIPTIONS` in `engine_guardrails.py`, and/or
2. A banner / note row on each sheet itself.

Not yet wired in — this doc is the source text for that future integration. British English spelling is preferred for user-facing copy (e.g. Optimisation, prioritised).
