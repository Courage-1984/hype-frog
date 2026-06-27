# Hype Frog — Full Feature Backlog & Requirements
## Everything beyond the Top 8 — All Four Areas
## LI-HF-BACKLOG-P0 | 27 June 2026

---

## How to use this document

This is the complete feature backlog for Hype Frog, covering all identified gaps across data collection, analysis depth, output presentation, and codebase reliability. Items are ordered by area, with implementation notes and priority guidance. Use this as a planning document for Cursor IDE sessions after the Top 8 prompt is complete.

**Priority tiers:**
- 🔴 **P1** — significant gap in every crawl, affects client output quality
- 🟡 **P2** — valuable addition, affects some clients or specific use cases
- 🟢 **P3** — nice to have, polish and scale concerns

---

## AREA A — Data Collection Gaps

---

### A1 — Open Graph & Social Card Comprehensive Audit 🔴 P1

**Current state:** Only `OG-Image` (boolean) is captured. No og:title, og:description, og:type, og:url, og:locale, or Twitter Card data.

**Why it matters:** Every client has social media presence. Broken or missing OG data means links shared to LinkedIn, Facebook, and WhatsApp show no preview, no image, or wrong content. Clients ask about this constantly.

**Implementation approach:**
- In `data_assembler.py`, extend the meta tag extraction pass to pull all `og:*` and `twitter:*` properties.
- Add a separate validation pass for OG image dimensions. The image URL is in `og:image` — fetch the image HEAD request and check content dimensions via `Content-Length` or by downloading the image header bytes (first 24 bytes of PNG/JPEG to read dimensions).
- Note: image dimension checking requires an extra HTTP request per page. Make it optional (gated by a config flag `--check-og-images`) and run it only on pages where `og:image` is set.

**New columns for Main sheet:**
- `OG Title` (string)
- `OG Description` (string)
- `OG Type` (string: website, article, video.movie, etc.)
- `OG URL` (string — should match canonical)
- `OG Image URL` (string)
- `OG Image Width` (int — from image HEAD request, optional)
- `OG Image Height` (int — optional)
- `OG Image OK` (bool — image URL returns 200)
- `Twitter Card Type` (string: summary, summary_large_image, app, player)
- `Twitter Title` (string)
- `Twitter Description` (string)
- `Twitter Image` (string)
- `OG Completeness Score` (int 0-5: one point per populated field)

**New registry rules:**
- `Missing OG Title` — Warning — scope: url
- `Missing OG Description` — Warning — scope: url
- `Missing OG Image` — Warning — scope: url
- `OG Image Broken (non-200)` — Critical — scope: url
- `OG URL Mismatch` — Warning (og:url doesn't match page URL or canonical) — scope: url
- `OG Type Not Set` — Observation — scope: url
- `Missing Twitter Card` — Observation — scope: url
- `OG Image Wrong Dimensions` — Observation (not 1200×630 ± 20%) — scope: url

**Files affected:**
- `src/hype_frog/crawler/data_assembler.py` — add OG/Twitter extraction
- `src/hype_frog/rules/registry.py` — new rules
- Column group definitions — new "Social Cards" group in Main

---

### A2 — Third-Party Script Inventory 🟡 P2

**Current state:** `Page Size (KB)`, `JS Execution (ms)`, `Network Request Count` will be added by the PSI prompt (LI-HF-PSI-P0). The individual scripts are not inventoried.

**Why it matters:** Slow sites almost always have third-party script bloat. A client needs to know whether their performance problem is Google Analytics, Meta Pixel, Hotjar, a chat widget, or their own code. The Lighthouse `network-requests` audit already returns this data in the API response.

**Implementation approach:**
- The `network-requests` audit in Lighthouse returns `details.items` — each item has `url`, `transferSize`, `resourceType`, and `startTime`.
- Parse these items and identify known third-party domains via a lookup table.
- Aggregate by domain: total size, total count, type.

**Known third-party domain lookup table (start with):**
```python
KNOWN_THIRD_PARTIES = {
    "googletagmanager.com": "Google Tag Manager",
    "google-analytics.com": "Google Analytics",
    "googleads.g.doubleclick.net": "Google Ads",
    "connect.facebook.net": "Meta Pixel",
    "static.hotjar.com": "Hotjar",
    "cdn.segment.com": "Segment",
    "js.intercomcdn.com": "Intercom",
    "cdn.hubspot.net": "HubSpot",
    "static.klaviyo.com": "Klaviyo",
    "cdn.cookielaw.org": "OneTrust / CookieLaw",
    "consent.cookiebot.com": "Cookiebot",
    "assets.calendly.com": "Calendly",
    "embed.tawk.to": "Tawk.to Chat",
    "widget.freshworks.com": "Freshdesk",
    "cdn.onesignal.com": "OneSignal",
    "cdn.amplitude.com": "Amplitude",
    "bat.bing.com": "Microsoft Ads",
    "snap.licdn.com": "LinkedIn Insight",
    "px.ads.linkedin.com": "LinkedIn Ads",
}
```

**New columns for Main sheet:**
- `Third Party Script Count` (int)
- `Third Party Scripts` (string — comma-separated names, e.g. "GTM, Meta Pixel, Hotjar")
- `Third Party Total Size (KB)` (float)
- `Has Google Analytics` (bool)
- `Has Tag Manager` (bool)
- `Has Meta Pixel` (bool)
- `Has Chat Widget` (bool)
- `Has Consent Manager` (bool)
- `Third Party JS Blocking` (bool — any third-party script is render-blocking per Lighthouse)

**New sheet: "Script Inventory"**
- One row per unique third-party domain detected across the site
- Columns: Domain, Service Name, Pages Found On, Average Size (KB), Total Transferred (KB), Is Render Blocking, Category

**New registry rules:**
- `High Third-Party Script Count (>10)` — Warning — scope: url
- `Third-Party Scripts Blocking Render` — Warning — scope: url
- `No Consent Manager Detected` — Observation — scope: site (if cookies are being set)

**Files affected:**
- `src/hype_frog/crawler/psi_engine.py` — extract network-requests audit details
- New `src/hype_frog/analysis/third_party_scripts.py`
- Export flow — new "Script Inventory" sheet

---

### A3 — Full Redirect Chain Mapping 🔴 P1

**Current state:** `Redirect Chain Length` exists in Technical Diagnostics but does not show the full A→B→C path or distinguish 301 vs 302.

**Why it matters:** For a client with URL migration history, the difference between a 301 and 302 redirect is significant (302 does not pass PageRank). A chain of A→B→302→C means A's equity is lost at the 302 hop. Clients with multiple domain migrations accumulate 3-4 hop chains which slow down crawling and dilute PageRank.

**Implementation approach:**
- During crawl, when a URL returns 3xx, follow it and record each hop: `(from_url, to_url, status_code, hop_number)`.
- The crawler likely already follows redirects — intercept at the response level to record each hop before following.
- Store the full chain as a JSON string or pipe-delimited list.

**New columns for Main sheet:**
- `Redirect Chain` (string — `A → [301] → B → [302] → C`)
- `Redirect Chain Length` (int — already exists, verify it's correct)
- `Has 302 in Chain` (bool — temporary redirect in chain = possible SEO issue)
- `Has Mixed Redirect Types` (bool — mix of 301 and 302 in same chain)
- `Final URL` (string — already exists, verify populated)
- `Redirect Chain Hops` (JSON list of `{url, status}` dicts for machine processing)

**New sheet: "Redirect Map"**
- One row per redirect chain (one row per source URL with a redirect)
- Columns: Source URL, Hop 1 URL, Hop 1 Status, Hop 2 URL, Hop 2 Status, Hop 3 URL, Hop 3 Status, Final URL, Chain Length, Has 302, SEO Risk

**New registry rules:**
- `Redirect Chain (>1 hop)` — Warning — scope: url
- `302 Redirect (Temporary)` — Warning (should be 301 in most cases) — scope: url
- `Mixed 301/302 Chain` — Warning — scope: url
- `Redirect Loop` — Critical — scope: url (already detected? confirm)

---

### A4 — Broken Image Detection 🟡 P2

**Current state:** Image alt coverage is audited but the images themselves are not checked for HTTP status.

**Why it matters:** WordPress sites frequently have orphaned media — images referenced in content that were deleted from the media library. These return 404 and show as broken image icons to users, and signal low quality to crawlers.

**Implementation approach:**
- During HTML extraction, collect all `<img src>` URLs from the page.
- After crawl, run a HEAD request batch against unique image URLs (deduplicated across all pages).
- This is a separate post-crawl enrichment pass to avoid blocking the main crawl.
- Gate behind a config flag `--check-images` as it adds many HTTP requests.

**New columns for Main sheet:**
- `Image Count` (int — total images on page)
- `Broken Image Count` (int — images returning non-200)
- `Broken Image URLs` (string — pipe-delimited, first 3)
- `Has Broken Images` (bool)

**New sheet: "Image Inventory"**
- One row per unique image URL found across the site
- Columns: Image URL, Status Code, Found On Pages (count), Found On Pages (list, first 5), Is Broken, Alt Text (from first occurrence), File Extension

**New registry rules:**
- `Broken Images` — Warning — fn: `r.get("Broken Image Count", 0) > 0` — scope: url
- `High Broken Image Count (>3)` — Critical — scope: url

---

### A5 — robots.txt Rule Mapping Against Crawled URLs 🟡 P2

**Current state:** `AI Crawlers Not Explicitly Allowed` is a site-level observation but no per-URL robots.txt disallow analysis is performed.

**Why it matters:** Clients frequently have overly broad `Disallow: /` rules affecting pages they want indexed, or they use robots.txt to block staging directories that are accidentally live. Per-URL robots.txt status is essential for diagnosing missing pages in Google Search Console.

**Implementation approach:**
- Parse `robots.txt` using `urllib.robotparser.RobotFileParser` (built-in Python).
- For each crawled URL and each significant user-agent (Googlebot, Bingbot, GPTBot, ClaudeBot), check `can_fetch(user_agent, url)`.
- Store results per URL.

**New columns for Main sheet:**
- `Robots.txt: Googlebot` (string: "Allow" / "Disallow" / "Not specified")
- `Robots.txt: Bingbot` (string)
- `Robots.txt: GPTBot` (string)
- `Robots.txt: ClaudeBot` (string)
- `Robots.txt: PerplexityBot` (string)
- `Crawl-Delay Applies` (bool — page's user-agent group has a Crawl-delay directive)

**New sheet: "Robots.txt Analysis"**
- Section 1: Full parsed robots.txt content
- Section 2: User-agent groups and their rules
- Section 3: Crawled URLs that are blocked per-agent
- Section 4: Crawled URLs in sitemap that are blocked (sitemap vs robots conflict)

**New registry rules:**
- `Blocked by Googlebot` — Critical — scope: url
- `Blocked by Bingbot` — Warning — scope: url
- `In Sitemap but Blocked by Googlebot` — Critical — scope: url (the worst combination)
- `AI Crawlers: GPTBot Blocked` — Observation — scope: site
- `AI Crawlers: ClaudeBot Blocked` — Observation — scope: site

---

### A6 — Hreflang & Internationalisation Signals 🟢 P3

**Current state:** `Hreflang Signals` column exists in Technical Diagnostics but appears empty for all AMC pages.

**Why it matters:** For clients operating across multiple countries/languages (AMC operates across Africa — multiple countries and languages), missing or incorrect hreflang causes duplicate content issues and wrong-country ranking.

**Implementation approach:**
- Extract `<link rel="alternate" hreflang="xx">` tags from HTML.
- Check that every declared alternate URL is reachable (reciprocal links).
- Validate lang/region codes against ISO 639-1 / ISO 3166-1.

**New columns:** hreflang declared languages, hreflang URLs, reciprocal validation status.

---

## AREA B — Analysis Depth Gaps

---

### B1 — Canonical Chain Tracing 🔴 P1

**Current state:** `Canonical URL` and `Canonical Type` are captured but the crawler doesn't detect multi-hop canonical chains.

**Why it matters:** Page A has canonical pointing to page B, which has canonical pointing to page C, which redirects to page D. This four-hop chain means Google may not consolidate signals to the intended canonical. These chains are common after site migrations.

**Implementation approach:**
- After crawl, build a canonical graph (each URL → its canonical target).
- Run chain resolution: follow the canonical chain to its end, detecting loops.
- Maximum meaningful chain depth: 5 hops (beyond that it's a loop or misconfiguration).

**New columns for Main sheet:**
- `Canonical Chain Depth` (int — 0 = self-canonical, 1 = one hop, etc.)
- `Canonical Chain Final` (string — the ultimate canonical destination)
- `Canonical Chain` (string — full chain A → B → C)
- `Canonical Loop Detected` (bool)
- `Canonical Points to Redirect` (bool — canonical target returns 3xx)
- `Canonical Points to Non-200` (bool — canonical target is broken)

**New registry rules:**
- `Canonical Chain (>1 hop)` — Warning — scope: url
- `Canonical Loop` — Critical — scope: url
- `Canonical Points to Broken URL` — Critical — scope: url
- `Canonical Points to Redirect` — Warning — scope: url

---

### B2 — Internal Link Equity Distribution 🟡 P2

**Current state:** `Internal PageRank` is calculated. `Click Depth` and `Orphan Pages` are implemented. But there's no analysis of which pages are under-linked vs over-linked, or anchor text diversity per destination.

**Why it matters:** Pages that should rank (conference registration, sponsorship) may have very few internal links pointing to them. The homepage may receive 300% of all internal link equity while product pages get nothing.

**Implementation approach:**
- From the link inventory, for each destination URL: count inbound internal links, list source pages, aggregate anchor texts, calculate PageRank percentile.
- Build distribution analysis: top 10 most-linked pages, bottom 10 most under-linked high-value pages.

**New sheet: "Link Equity Map"**
Columns: URL, Inbound Link Count, Unique Source Pages, Anchor Texts (top 5), PageRank Score, PageRank Percentile, Click Depth, Equity Tier (High/Medium/Low/Orphan), Recommended Action.

**New sheet: "Anchor Text Audit"**
For each destination URL, break down inbound anchor texts:
- Exact match anchor (URL = keyword)
- Partial match anchor
- Branded anchor
- Generic anchor ("click here", "read more", "here")
- Naked URL anchor
Flag destination pages where >50% of inbound links use generic anchors.

**New registry rules:**
- `Under-Linked Priority Page` — Warning — fn: high business risk score + low inbound link count (<3) — scope: url
- `Generic Anchor Dominance` — Observation — fn: >50% of inbound anchors are generic — scope: url (already partially detected via `Generic Anchor Text Present`)

---

### B3 — Featured Snippet & PAA Opportunity Analysis 🟡 P2

**Current state:** Question headings are detected and counted. AEO readiness score is calculated. But there's no identification of which specific pages are best positioned for Featured Snippet or People Also Ask extraction.

**Why it matters:** For content-heavy clients, knowing "this page could win position 0 if you restructure it as a definition + list" is high-value strategic advice that converts an audit into a content brief.

**Implementation approach:**
- Identify pages where GSC average position is 4-20 (close enough to rank but not yet position 0-3).
- Score Featured Snippet potential per page type:
  - Definition content (page starts with "X is a/an..."): high potential
  - Step-by-step lists (numbered lists with action verbs): high potential
  - Comparison tables: high potential
  - FAQ with question headings: high potential
- These signals are extractable from already-captured heading structure and word patterns.

**New columns for Main sheet:**
- `Featured Snippet Type` (string: Definition / List / Table / None / FAQ)
- `Featured Snippet Readiness` (int 0-10)
- `GSC Position Opportunity` (bool — position 4-20 with snippetable content structure)

**New sheet: "Snippet Opportunities"**
- Only pages with position 4-20 in GSC AND `Featured Snippet Readiness` > 5
- Columns: URL, Current GSC Position, Clicks, Impressions, Snippet Type Detected, Recommended Restructuring, Effort

---

### B4 — GSC Coverage & Index Status Integration 🔴 P1

**Current state:** GSC Search Analytics (clicks, impressions, position) is integrated. But the GSC Index Coverage API (which pages are indexed, which have errors) is not used.

**Why it matters:** `GSC Coverage Category` is populated ("URL is unknown to Google" for AMC pages) but this appears to come from the Search Analytics endpoint, not the Index Coverage API. The Index Coverage API gives specific reasons for exclusion: "Crawled — currently not indexed", "Discovered — currently not indexed", "Page with redirect", "Excluded by noindex tag", "Blocked by robots.txt", etc.

**Implementation approach:**
- Use the `searchconsole.searchanalytics.urlInspection` method (GSC URL Inspection API) — this is different from Search Analytics.
- For each crawled URL, call `urlInspection.index.inspect` to get: indexing status, last crawl date, mobile usability, rich result status.
- This is expensive (one API call per URL) — gate behind a `--gsc-url-inspection` flag and limit to Priority URLs (top 50 by business risk score) unless full inspection is enabled.

**New columns for Main sheet:**
- `GSC Index Status` (string: INDEXED / NOT_INDEXED / etc. — already exists, enhance)
- `GSC Last Crawl Date` (date — when Google last crawled this URL)
- `GSC Mobile Usability` (string: MOBILE_FRIENDLY / NOT_MOBILE_FRIENDLY)
- `GSC Rich Result Status` (string: VALID / INVALID / NONE)
- `GSC Coverage Reason` (string — specific exclusion reason from GSC)
- `Days Since Last Crawl` (int — calculated from last crawl date)

**New registry rules:**
- `Not Indexed by Google` — Critical — fn: `r.get("GSC Index Status") == "NOT_INDEXED"` — scope: url
- `Not Crawled in >30 Days` — Warning — fn: days since last crawl > 30 — scope: url
- `GSC Mobile Usability Issue` — Warning — scope: url
- `GSC Rich Result Error` — Warning — fn: rich result status is INVALID — scope: url

---

### B5 — Competitor Benchmarking Context 🟢 P3

**Current state:** All analysis is self-referential — no external context.

**Why it matters:** "AEO readiness of 26%" lands differently as a finding when the context is "your top 3 competitors average 68%". Benchmarks make findings defensible and urgent.

**Implementation approach:**
- Allow the user to pass 3-5 competitor domains via config/CLI (`--competitors example.com,competitor.com`).
- For each competitor domain:
  - Fetch their homepage and a sample of 10 pages (from their sitemap if available)
  - Extract: schema types, AEO signals, meta completeness, PSI score, H1 pattern
  - Do NOT run a full crawl — just a quick 10-page sample
- Add a "Competitor Benchmarks" section to the Executive Dashboard source data
- This is a separate optional `--benchmarks` mode, not part of the standard crawl

**Output:** New "Competitor Benchmarks" sheet showing the client vs competitors on 10-15 key metrics as a comparison table.

---

### B6 — Keyword Density & Topical Authority Signals 🟢 P3

**Current state:** Entity density is calculated (via spaCy NER). Question heading count is captured. But there's no keyword relevance analysis connecting page content to the inferred search intent.

**Why it matters:** A page targeting "marketing conference Africa" should demonstrate topical authority through entity co-occurrence, semantic depth, and keyword presence. The AEO Readiness score captures some of this but doesn't explain it.

**Implementation approach:**
- From the body text, extract top-5 TF-IDF terms per page (using the full crawl corpus as the IDF base — so common words across all pages are down-weighted).
- Flag pages where the target keyword (inferred from title/H1) has low TF-IDF score vs other pages.
- This is a post-crawl corpus analysis pass.

**New columns:** `Top TF-IDF Terms`, `Keyword in Title`, `Keyword in H1`, `Keyword in First Paragraph`, `Keyword Density (%)`.

---

## AREA C — Output Presentation Gaps

---

### C1 — Comprehensive Delta Tracking 🔴 P1

**Current state:** `DeltaFromPreviousRun` tab shows only a baseline message on first run. No specific URL-level changes are tracked.

**Why it matters:** The value of a monthly audit service is showing progress. "You fixed 47 issues since last month and 12 new ones appeared" is the conversation that retains a client.

**Implementation approach:**
- Store the previous run's IssueInventory and Main row data in the checkpoint/output directory.
- On subsequent runs, diff against the previous:
  - New issues: appeared in current but not in previous (keyed by `Stable Issue ID`)
  - Resolved issues: in previous but not in current
  - Changed metrics: `SEO Health Score` change per URL, `AEO Readiness` change, PSI score change

**Expand `DeltaFromPreviousRun` tab:**
- Section 1: Summary (total issues: prev vs current, net change)
- Section 2: New Issues (appeared since last run) — columns: URL, Issue, Severity, First Seen
- Section 3: Resolved Issues (fixed since last run) — columns: URL, Issue, Severity, Last Seen, Days Open
- Section 4: Metric Changes — columns: URL, Metric, Previous Value, Current Value, Change, Direction (↑↓)
- Section 5: SEO Health trend (URL → [run1 score, run2 score, run3 score]) — builds over time

**New file:** `src/hype_frog/analysis/delta_engine.py`

**CLI change:** `--previous-run PATH` — path to previous output xlsx or JSON summary file. On successful run, auto-save a compact summary JSON alongside the xlsx for future delta use.

---

### C2 — PDF Executive Summary Export 🟡 P2

**Current state:** Output is xlsx only. No client-facing summary document.

**Why it matters:** A client's marketing director or exco does not open spreadsheets. A one-to-two page PDF summary is the deliverable that gets presented in board meetings.

**Implementation approach:**
- Use `reportlab` (Python PDF library) or `weasyprint` (HTML→PDF) to generate a PDF from a template.
- Content: cover page (client domain, audit date, your logo watermark slot), key metrics page (6 KPIs in RAG format), top 5 issues, top 5 quick wins, sprint plan table, AEO readiness indicator.
- This is NOT a full report — it's an executive summary only (2 pages max).
- Template-driven so it can be white-labelled: pass client name, primary colour, and logo path as parameters.

**CLI addition:** `--export-pdf` flag that generates `[output_name]_executive_summary.pdf` alongside the xlsx.

**Files:** New `src/hype_frog/reporter/pdf_exporter.py` with template-driven layout.

**Note on white-label:** The PDF template should have placeholders for: company/client name, audit date, "Prepared by" field, and a logo image path. No Hype Frog branding should appear in the PDF output.

---

### C3 — Content Hub Inline Recommendations 🟡 P2

**Current state:** The Content Optimisation Hub shows issues per page but the `Recommended Fix` column is brief. The AIOSEO Recommendations tab has 1,266 rows but no prioritisation column.

**Why it matters:** A content writer looking at their pages in the Content Hub needs actionable, specific guidance in plain language, not a terse technical label.

**Implementation approach:**
- For each page in the Content Hub, generate a plain-language recommendation string that incorporates the page's specific data:
  - Not: "Missing meta description"
  - But: "Add a meta description (currently missing). Aim for 120-155 characters summarising the page topic: [H1 content shortened to 120 chars] — focusing on [detected entity from NER]."
- This requires the LLM-based recommendation engine. Move it to a post-crawl pass (see Codebase section below).
- Add a `Priority Reason` column explaining WHY this page is in the top priorities (e.g. "High GSC impressions (890) + missing answer paragraphs = AEO opportunity").

---

### C4 — Issue Register Improvements 🟡 P2

**Current state:** The `Issue Register` tab exists but its structure is not clear from the audit data (it's separate from `IssueInventory`).

**What to add:**
- `Date First Detected` column (from first run)
- `Days Open` column (calculated from date first detected)
- `Assigned To` (blank text field for team member names)
- `Client Notes` (blank text field)
- Filter view showing only unresolved issues
- Colour coding: issues open >30 days go orange, >60 days go red

---

### C5 — Sitemap QA Enhancement 🟢 P3

**Current state:** SitemapQA tab exists. Current checks: `<lastmod>`, `<changefreq>`, `<priority>` presence, non-200 URLs in sitemap.

**Additional checks to add:**
- Pages crawled but NOT in sitemap (potentially should be added)
- Sitemap index vs individual sitemap detection
- Image sitemap and video sitemap detection
- Sitemap file size (Google limit: 10MB / 50,000 URLs per sitemap)
- Last-modified date consistency (lastmod in sitemap vs actual HTTP Last-Modified header)
- Sitemap vs canonical consistency (sitemap URL should match the canonical of the target page)

---

### C6 — Playbook Tab Enrichment 🟢 P3

**Current state:** A `Playbook` tab exists. Content from the audit is brief.

**What to add:**
- Per-issue playbook entries with: What it is, Why it matters, How to fix (step by step), Time to fix, Who fixes it, How to verify the fix
- For each registry rule, define a playbook entry in the rule definition itself (as a metadata field) so it auto-populates
- This turns the tool from a diagnostic into a training document for clients or junior team members

---

## AREA D — Codebase Reliability Gaps

---

### D1 — Memory Management for Large Sites 🔴 P1

**Current state:** The pipeline holds all crawl results in memory before writing the xlsx. For a 265-page site this is fine. For sites with 1,000+ pages this becomes a problem.

**Why it matters:** If you run this on a 5,000-page enterprise site, you will hit a MemoryError before the xlsx is written.

**Implementation approach:**

**Phase 1 — Streaming row write:**
- After each URL is crawled and enriched, write its Main row immediately to an in-progress xlsx using `openpyxl` streaming writer (`write_only=True`).
- Downside: streaming writers cannot go back and add conditional formatting or adjust column widths after the fact. Separate the "data write" phase from the "formatting phase": write data in streaming mode, then open the file again with openpyxl for formatting.

**Phase 2 — Chunked enrichment:**
- PSI API calls, GSC enrichment, and similarity analysis can be chunked: process 50 pages at a time, write results, discard from memory.
- The graph engine (Click Depth, Internal PageRank, link inventory) requires all pages in memory simultaneously. This is the hardest component to chunk. For sites >2,000 pages, consider incremental PageRank via the NetworkX streaming approach or replace with a simpler inbound-link-count proxy.

**Phase 3 — Size estimation and warning:**
- Before starting a large crawl, estimate memory requirements: `estimated_MB = url_count × 0.5MB` (rough per-URL estimate including link inventory).
- If estimated > 2GB, warn the user and suggest `--mode fast` or chunked processing.

**Config additions:**
- `--max-memory-mb N` — abort if RSS exceeds N MB
- `--streaming` — enable streaming write mode (disables some formatting features)

---

### D2 — LLM Search Intent as Separate Post-Crawl Pass 🟡 P2

**Current state:** From the code map, `_apply_search_intent` is called per-URL during the crawl loop. It calls an LLM (`IntentAnalyzer`) for each of 265 pages at crawl time.

**Why it matters:**
- Calling an LLM 265 times during the crawl adds significant time and cost.
- If the crawl fails at page 230, all LLM calls are lost.
- LLM calls during crawl cannot be checkpointed easily.
- The intent analysis is a nice-to-have enrichment, not a crawl blocker.

**Implementation approach:**
- Move `_apply_search_intent` entirely out of the crawl loop.
- Run it as a post-crawl enrichment step after all pages are crawled and checkpointed.
- Add its own checkpoint: save intent results to a JSON file keyed by URL. If it fails midway, resume from last saved URL.
- Gate behind `--search-intent` flag (default: off for fast mode, on for accurate mode).

**Files affected:**
- `src/hype_frog/orchestration/crawl_runner.py` — remove from crawl loop
- `src/hype_frog/orchestration/enrichment_flow.py` — add as enrichment step
- New checkpoint pattern in `core/checkpoint.py` (extend existing)

---

### D3 — PSI Request Delay Jitter 🟡 P2

**Current state:** Fixed 2.5s delay between all PSI requests.

**Why it matters:** Perfectly predictable request timing is a fingerprint that some API gateway rate-limiters detect and throttle. Jitter is standard practice in any production API client.

**Implementation:**
```python
import random

async def _jittered_delay(base_seconds: float = 2.5, jitter_fraction: float = 0.3) -> None:
    """Wait base_seconds ± jitter_fraction × base_seconds."""
    jitter = random.uniform(-jitter_fraction, jitter_fraction) * base_seconds
    await asyncio.sleep(base_seconds + jitter)
```

Replace all `await asyncio.sleep(2.5)` calls in `psi_engine.py` with `await _jittered_delay()`.

**Config addition:** `--psi-delay N` — base delay between PSI calls in seconds (default: 2.5).

---

### D4 — Status Code Type Normalisation 🔴 P1

**Current state:** `Status Code` column has mixed types — integer `200`, `404` and string `"Timeout"`. This causes `TypeError` in comparisons as confirmed by the audit (Phase 1A residue for Timeout pages).

**Why it matters:** Every rule that compares status code to an integer will silently fail or error for non-integer values. This will affect every new client site that has timeouts.

**Implementation approach:**
- Define a `NormalisedStatusCode` type:
  ```python
  from typing import Union
  StatusCode = Union[int, str]
  # Canonical string representations for non-HTTP statuses:
  STATUS_TIMEOUT = "Timeout"
  STATUS_DNS_ERROR = "DNS Error"
  STATUS_CONNECTION_ERROR = "Connection Error"
  STATUS_SSL_ERROR = "SSL Error"
  ```
- In `data_assembler.py`, when storing the status code, always normalise: HTTP statuses become `int`, error states become canonical strings.
- In `registry.py` and `scoring.py`, update all status code comparisons to handle both:
  ```python
  def is_error_status(status) -> bool:
      if isinstance(status, int):
          return status >= 400
      return status in (STATUS_TIMEOUT, STATUS_DNS_ERROR, STATUS_CONNECTION_ERROR, STATUS_SSL_ERROR)
  ```
- The `Indexability` fix (Phase 1A from previous prompt) should already handle Timeout once this normalisation is in place.

---

### D5 — Test Suite Foundation 🟡 P2

**Current state:** No automated tests are evident from the codebase (the grep commands in previous prompts searched with `grep -v test`, implying test files exist or the pattern was precautionary).

**Why it matters:** Every Cursor session risks breaking something that worked before. Without tests, regressions are found in client output rather than in CI.

**Minimum viable test suite:**

Create `tests/` directory if it doesn't exist. Add:

```
tests/
  unit/
    test_schema_validator.py      # Part 1 from Top 8 prompt
    test_content_similarity.py   # Part 3
    test_checkpoint.py           # Part 4
    test_eeat_extractor.py       # Part 2
    test_registry_rules.py       # Verify all rules fire correctly on sample data
    test_status_normalisation.py # D4
  integration/
    test_psi_engine.py           # Mock PSI API responses, verify extraction
    test_full_crawl_sample.py    # Crawl 5 pages of a known stable test site
  fixtures/
    sample_page.html             # A minimal HTML page with known content
    sample_schema.json           # Valid and invalid JSON-LD examples
    sample_psi_response.json     # Real PSI API response structure
```

**Priority order for writing tests:**
1. `test_schema_validator.py` — critical, the validator logic is complex
2. `test_registry_rules.py` — verify each rule fires on the right data
3. `test_status_normalisation.py` — prevent regressions on the Timeout bug
4. `test_checkpoint.py` — save/load round-trip test

**Framework:** Use `pytest`. Add to `pyproject.toml` or `requirements-dev.txt`.

---

### D6 — Configuration Centralisation 🟢 P3

**Current state:** Configuration values (delays, timeouts, thresholds, excluded query params, etc.) appear to be scattered across module-level constants.

**Why it matters:** When you need to tune a threshold (e.g. change the thin content word count from 200 to 300 for a client), you shouldn't need to edit source code.

**Implementation approach:**
- Create `src/hype_frog/config/defaults.py`:
  ```python
  THIN_CONTENT_WORD_THRESHOLD = 200
  NEAR_DUPLICATE_SIMHASH_DISTANCE = 8
  PSI_BASE_DELAY_SECONDS = 2.5
  PSI_JITTER_FRACTION = 0.3
  CHECKPOINT_EVERY_N_PAGES = 50
  EXCLUDED_QUERY_PARAMS = frozenset({"add-to-cart", "removed_item", ...})
  CWV_LCP_CRITICAL_THRESHOLD = 4.0
  CWV_LCP_WARNING_THRESHOLD = 2.5
  LAB_TBT_CRITICAL_MS = 300
  LAB_TBT_WARNING_MS = 150
  EEAT_LOW_SCORE_THRESHOLD = 3
  CONTENT_AGE_STALE_DAYS = 730
  CONTENT_AGE_AGEING_DAYS = 365
  QUICK_WINS_MAX_EFFORT_HOURS = 4
  QUICK_WINS_MAX_RESULTS = 15
  ```
- All registry rules and crawl settings read from `defaults.py`.
- Allow override via a `hype_frog.config.yaml` in the project root.

---

### D7 — Error Reporting & Crawl Log 🟡 P2

**Current state:** Errors during crawl (timeouts, PSI failures, rendering errors) are logged to the terminal but not persisted in the output.

**Why it matters:** When a client asks "why does my page not appear in the output?", you need a crawl log to show what happened. Currently you'd need to re-run with verbose logging to find out.

**Implementation approach:**
- Add a `Crawl Log` sheet to the workbook.
- For each URL that resulted in an error or warning during crawl, record: URL, Error Type, Error Message, Timestamp, Phase (fetch/render/PSI/GSC).
- For PSI API failures per URL: record which call failed and the error.
- Keep only errors, not successful crawl events (would be too many rows).

**New sheet: "Crawl Log"**
Columns: Timestamp, URL, Phase, Error Type, Error Detail, Recovery Action Taken.

---

### D8 — Dependency Version Pinning & Environment Documentation 🟢 P3

**Current state:** Unknown — not visible from the output sheet.

**Why it matters:** If `beautifulsoup4`, `openpyxl`, or `aiohttp` releases a breaking change, the crawler breaks silently on the next pip install. This is a production reliability concern.

**Implementation:**
- Pin all dependencies to specific versions in `requirements.txt` or `pyproject.toml`.
- Add a `README.md` section documenting: Python version requirement, OS compatibility, how to set up a virtualenv, how to configure API keys, how to run the first crawl.
- Add a `CHANGELOG.md` starting from the first prompt (LI-HF-AUDIT-P0) to track changes.

---

## IMPLEMENTATION PRIORITY ORDER

When scheduling Cursor sessions beyond the Top 8, this is the recommended order:

| Priority | Item | Rationale |
|---|---|---|
| 1 | D4 — Status code normalisation | Affects rule correctness on every crawl |
| 2 | D5 — Test suite (unit tests) | Prevents regression as codebase grows |
| 3 | A1 — OG & Social Card audit | Client question in almost every engagement |
| 4 | C1 — Delta tracking | Essential for ongoing monthly retainer model |
| 5 | A3 — Redirect chain mapping | Common on migrated client sites |
| 6 | B1 — Canonical chain tracing | Directly related to redirect chains |
| 7 | B4 — GSC Coverage API | Makes indexability data authoritative |
| 8 | D1 — Memory management | Required before using on enterprise sites |
| 14 | A5 — robots.txt per-URL mapping | Diagnostic completeness |
| 18 | D7 — Crawl log | Diagnostic capability |
| 15 | D3 — PSI jitter | Production robustness |
| 21 | D8 — Dependency pinning | Production reliability |
| 17 | D6 — Config centralisation | Developer experience |
| 10 | B2 — Internal link equity | Strategic SEO value |
| 19 | B3 — Snippet opportunities | Strategic content value |
| 12 | A4 — Broken, wrong, and large image detection, validation, propery extraction and inventory with analysis | WordPress client cleanup |
| 9 | A2 — Third-party script inventory | Performance narrative for clients |
| 16 | C1 — Issue Register improvements | Ongoing client relationship management |
| 23 | B6 — Topical authority | Advanced SEO |
| 24 | C5 — Sitemap QA enhancement | Polish |
| 26 | C3 — Content Hub recommendations | Nice to have |
| 11 | C2 — PDF export | Client-facing deliverable format |
| 22 | A6 — Hreflang | International clients only |
| 25 | C6 — Playbook enrichment | Client education |
| 20 | B5 — Competitor benchmarking | Pitch and retention value |


| 13 | D2 — LLM as post-crawl pass | Cost and reliability improvement |


---

## DEPENDENCY ADDITIONS SUMMARY

Add these libraries as required by the features above:

| Library | Version | Required by | Install |
|---|---|---|---|
| `python-simhash` | latest stable | Part 3 / B2 duplicate detection | `pip install simhash` |
| `python-dateutil` | `>=2.8` | Part 8 / content freshness | `pip install python-dateutil` |
| `reportlab` | `>=4.0` | C2 PDF export | `pip install reportlab` |
| `Pillow` | `>=10.0` | A1 OG image dimensions | `pip install Pillow` |
| `pytest` | `>=7.0` | D5 test suite | `pip install pytest` (dev dep) |
| `pytest-asyncio` | latest | D5 async tests | `pip install pytest-asyncio` (dev dep) |

Existing dependencies that should already be present: `beautifulsoup4`, `aiohttp`, `openpyxl`, `pandas`, `networkx`, `spacy`.

