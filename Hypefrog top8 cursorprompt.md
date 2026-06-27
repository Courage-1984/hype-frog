# Hype Frog — Top 8 High-Impact Additions
## Cursor IDE Agent Instructions — LI-HF-EXPAND-P0 | 27 June 2026

---

## CRITICAL RULES

1. Do NOT remove any existing column, sheet, or rule.
2. All new sheets must be added to the Table of Contents sheet and navigation system.
3. All new columns must be added to the relevant COLUMN_GROUP_DEFINITIONS.
4. Each part must leave the codebase fully runnable. Test after every part.
5. New external dependencies (e.g. `python-simhash`, `dateparser`) must be added to `requirements.txt` or `pyproject.toml` — confirm which before installing.
6. **Test crawl after every part:** `https://africanmarketingconfederation.org/page-sitemap.xml` with AMC PSI key and GSC OAuth.

---

## STEP 0 — Context extraction (before touching any code)

```bash
# 1. Find where JSON-LD / schema is currently extracted
grep -rn "json.ld\|jsonld\|JSON-LD\|schema\|Schema" src/ --include="*.py" | grep -v test | grep -v ".pyc"

# 2. Find where 'Probable Draft or Duplicate Page' rule is defined
grep -rn "Probable Draft\|duplicate\|Duplicate\|thin content\|Thin Content" src/ --include="*.py"

# 3. Find BFS queue and crawl loop (for checkpoint)
grep -rn "bfs_queue\|queued_urls\|CrawlRowPayload\|checkpoint" src/ --include="*.py"

# 4. Find where HTTP response headers are stored
grep -rn "Last-Modified\|ETag\|headers\|response_headers" src/ --include="*.py" | grep -v test

# 5. Find where OG tags are extracted
grep -rn "og:image\|og_image\|OG.Image\|open.graph\|opengraph" src/ --include="*.py"

# 6. Find the Link Inventory builder (for broken link impact)
grep -rn "build_link_inventory\|Link Inventory" src/ --include="*.py"

# 7. Find where conditional formatting is applied (or not applied) to Main sheet
grep -rn "ConditionalFormatting\|conditional_format\|ColorScale\|DataBar\|adjust_sheet_format" src/ --include="*.py"

# 8. Find where new sheets are registered (Table of Contents, export sequence)
grep -rn "Table of Contents\|sheet_sequence\|get_sheet_sequence\|registry_config" src/ --include="*.py"
```

Document all findings in `AUDIT_FIX_LOG.md` under `## Top 8 Expansion — Context Map`.

---

## PART 1 — Schema Validation

### Current state (confirmed from audit data)
- `Has Valid JSON-LD` = `False` for ALL 265 pages on AMC — no schema at all.
- `Schema Types Found` is empty for all pages.
- `Schema Parse Errors` exists in Content & AI Readiness but is empty.
- The crawler detects schema presence but does not validate required properties.

### Context note
Before implementing validation, first check whether the issue on AMC is:
(a) No schema in the HTML at all → validation returns "No schema present"
(b) Schema present but malformed → parse errors
(c) Schema present, parses, but missing required properties → validation errors

The validator must handle all three cases.

### 1A — New validator module

Create `src/hype_frog/validators/schema_validator.py`:

```python
"""
Schema.org JSON-LD validation against required property definitions.
Validates structure, required fields, and data types without network calls.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any

# Required properties per schema type (schema.org minimum requirements for Google)
REQUIRED_PROPERTIES: dict[str, list[str]] = {
    "FAQPage": ["mainEntity"],
    "Question": ["name", "acceptedAnswer"],
    "Answer": ["text"],
    "Event": ["name", "startDate", "location"],
    "VirtualEvent": ["name", "startDate"],
    "Organization": ["name", "url"],
    "LocalBusiness": ["name", "address", "telephone"],
    "Person": ["name"],
    "Article": ["headline", "author", "datePublished"],
    "NewsArticle": ["headline", "author", "datePublished"],
    "BlogPosting": ["headline", "author", "datePublished"],
    "WebPage": ["name"],
    "Product": ["name", "offers"],
    "Offer": ["price", "priceCurrency"],
    "BreadcrumbList": ["itemListElement"],
    "ListItem": ["position", "name"],
    "SiteNavigationElement": ["name"],
    "WebSite": ["name", "url"],
    "ItemList": ["itemListElement"],
    "VideoObject": ["name", "description", "thumbnailUrl", "uploadDate"],
    "ImageObject": ["url"],
    "Course": ["name", "description", "provider"],
    "JobPosting": ["title", "description", "datePosted", "hiringOrganization"],
    "Recipe": ["name", "recipeIngredient", "recipeInstructions"],
    "Review": ["itemReviewed", "reviewRating", "author"],
    "AggregateRating": ["ratingValue", "reviewCount"],
    "HowTo": ["name", "step"],
    "HowToStep": ["text"],
    "SpeakableSpecification": [],
}

# Google-specific recommended properties (Warning level, not Error)
RECOMMENDED_PROPERTIES: dict[str, list[str]] = {
    "Article": ["image", "publisher", "dateModified"],
    "Event": ["description", "image", "offers", "organizer", "eventStatus"],
    "FAQPage": [],
    "Organization": ["logo", "sameAs", "contactPoint"],
    "Product": ["description", "image", "brand", "sku"],
    "LocalBusiness": ["openingHours", "geo", "image"],
    "Person": ["sameAs", "jobTitle", "affiliation"],
    "VideoObject": ["duration", "contentUrl", "embedUrl"],
    "WebSite": ["potentialAction"],
    "BreadcrumbList": [],
}


@dataclass
class SchemaIssue:
    schema_type: str
    issue_type: str        # "missing_required" | "missing_recommended" | "invalid_type" | "parse_error"
    property_name: str | None
    message: str
    severity: str          # "Error" | "Warning"


@dataclass
class SchemaValidationResult:
    url: str
    raw_schemas: list[dict[str, Any]] = field(default_factory=list)
    types_found: list[str] = field(default_factory=list)
    types_valid: list[str] = field(default_factory=list)
    types_with_errors: list[str] = field(default_factory=list)
    issues: list[SchemaIssue] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)
    has_any_schema: bool = False
    is_fully_valid: bool = False

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "Error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "Warning")

    @property
    def summary(self) -> str:
        if not self.has_any_schema:
            return "No schema"
        if self.is_fully_valid:
            return f"Valid ({', '.join(self.types_valid)})"
        return f"{self.error_count} errors, {self.warning_count} warnings ({', '.join(self.types_found)})"


def validate_schema_object(
    obj: dict[str, Any],
    schema_type: str,
    parent_path: str = "",
) -> list[SchemaIssue]:
    """Recursively validate a single schema object."""
    issues: list[SchemaIssue] = []
    required = REQUIRED_PROPERTIES.get(schema_type, [])
    recommended = RECOMMENDED_PROPERTIES.get(schema_type, [])

    for prop in required:
        if prop not in obj:
            issues.append(SchemaIssue(
                schema_type=schema_type,
                issue_type="missing_required",
                property_name=prop,
                message=f"{schema_type}: missing required property '{prop}'",
                severity="Error",
            ))

    for prop in recommended:
        if prop not in obj:
            issues.append(SchemaIssue(
                schema_type=schema_type,
                issue_type="missing_recommended",
                property_name=prop,
                message=f"{schema_type}: missing recommended property '{prop}'",
                severity="Warning",
            ))

    # Recurse into nested objects
    for key, val in obj.items():
        if isinstance(val, dict) and "@type" in val:
            nested_type = val["@type"]
            if isinstance(nested_type, str):
                nested_issues = validate_schema_object(val, nested_type, parent_path=f"{schema_type}.{key}")
                issues.extend(nested_issues)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict) and "@type" in item:
                    nested_type = item["@type"]
                    if isinstance(nested_type, str):
                        nested_issues = validate_schema_object(item, nested_type, parent_path=f"{schema_type}.{key}[]")
                        issues.extend(nested_issues)

    return issues


def _extract_type(obj: dict) -> str | None:
    t = obj.get("@type")
    if isinstance(t, list):
        return t[0] if t else None
    return t if isinstance(t, str) else None


def validate_schemas_from_html(url: str, json_ld_blocks: list[str]) -> SchemaValidationResult:
    """
    Validate all JSON-LD schema blocks found on a page.

    Args:
        url: The page URL (for error reporting)
        json_ld_blocks: List of raw JSON string content from <script type="application/ld+json"> tags
    """
    result = SchemaValidationResult(url=url)

    if not json_ld_blocks:
        return result

    result.has_any_schema = True
    all_valid = True

    for raw in json_ld_blocks:
        # Parse
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            result.parse_errors.append(str(e))
            result.issues.append(SchemaIssue(
                schema_type="Unknown",
                issue_type="parse_error",
                property_name=None,
                message=f"JSON-LD parse error: {e}",
                severity="Error",
            ))
            all_valid = False
            continue

        result.raw_schemas.append(parsed)

        # Handle @graph
        objects_to_validate: list[dict] = []
        if "@graph" in parsed:
            graph = parsed["@graph"]
            if isinstance(graph, list):
                objects_to_validate.extend([o for o in graph if isinstance(o, dict)])
        elif "@type" in parsed:
            objects_to_validate.append(parsed)

        for obj in objects_to_validate:
            schema_type = _extract_type(obj)
            if not schema_type:
                continue

            result.types_found.append(schema_type)
            issues = validate_schema_object(obj, schema_type)
            result.issues.extend(issues)

            errors = [i for i in issues if i.severity == "Error"]
            if errors:
                result.types_with_errors.append(schema_type)
                all_valid = False
            else:
                result.types_valid.append(schema_type)

    result.is_fully_valid = all_valid and result.has_any_schema
    return result


def flatten_to_row(result: SchemaValidationResult) -> dict[str, Any]:
    """Convert validation result to flat dict for Main sheet columns."""
    return {
        "Schema Present": result.has_any_schema,
        "Schema Valid": result.is_fully_valid,
        "Schema Types Found": ", ".join(result.types_found) if result.types_found else None,
        "Schema Types Valid": ", ".join(result.types_valid) if result.types_valid else None,
        "Schema Types With Errors": ", ".join(result.types_with_errors) if result.types_with_errors else None,
        "Schema Error Count": result.error_count,
        "Schema Warning Count": result.warning_count,
        "Schema Parse Errors": "; ".join(result.parse_errors) if result.parse_errors else None,
        "Schema Validation Summary": result.summary,
        "Schema Issues Detail": " | ".join(i.message for i in result.issues[:5]) if result.issues else None,
    }
```

### 1B — Integrate into data assembler

Find where `Has Valid JSON-LD` is currently set in `data_assembler.py`. Read the full surrounding function to understand how JSON-LD blocks are extracted.

After extracting the raw JSON-LD string content from the page HTML, call the validator:

```python
from hype_frog.validators.schema_validator import validate_schemas_from_html, flatten_to_row

# Get list of raw JSON-LD strings from the page
# (the exact variable name depends on what the extractor currently produces)
json_ld_blocks: list[str] = [...]  # read from existing extractor

schema_result = validate_schemas_from_html(url=page_url, json_ld_blocks=json_ld_blocks)
schema_flat = flatten_to_row(schema_result)
extra_values.update(schema_flat)

# Keep backward compat
extra_values["Has Valid JSON-LD"] = schema_result.has_any_schema and schema_result.is_fully_valid
```

### 1C — New columns to add

Add to Main sheet column group "Schema & Structured Data":
- `Schema Present` (bool)
- `Schema Valid` (bool)
- `Schema Types Found` (string — already exists in Content & AI Readiness, add to Main)
- `Schema Types Valid` (string)
- `Schema Types With Errors` (string)
- `Schema Error Count` (int)
- `Schema Warning Count` (int)
- `Schema Parse Errors` (string)
- `Schema Validation Summary` (string)
- `Schema Issues Detail` (string — first 5 issues concatenated)

### 1D — New registry rules

```python
IssueRule(severity="Critical", name="No Schema Markup",
    fn=lambda r: not r.get("Schema Present", False), scope="url"),
IssueRule(severity="Critical", name="Schema Parse Error",
    fn=lambda r: bool(r.get("Schema Parse Errors")), scope="url"),
IssueRule(severity="Warning", name="Schema Validation Errors",
    fn=lambda r: (r.get("Schema Error Count") or 0) > 0, scope="url"),
IssueRule(severity="Observation", name="Schema Validation Warnings",
    fn=lambda r: (r.get("Schema Warning Count") or 0) > 0
        and (r.get("Schema Error Count") or 0) == 0, scope="url"),
IssueRule(severity="Warning", name="Missing Event Schema",
    fn=lambda r: (
        any(x in (r.get("URL") or "") for x in ["conference", "event", "summit", "awards", "webinar"])
        and not r.get("Schema Present", False)
    ), scope="url"),
IssueRule(severity="Warning", name="Missing Article Schema",
    fn=lambda r: (
        any(x in (r.get("URL") or "") for x in ["news", "blog", "article", "post", "publication"])
        and not r.get("Schema Present", False)
    ), scope="url"),
```

### 1E — Test criteria

- `Schema Present` = False for all AMC pages (confirmed — zero schema on site)
- `No Schema Markup` rule fires on all 265 pages
- `Schema Validation Summary` = "No schema" for all AMC pages
- If testing on a site with schema: validate that a FAQPage without `mainEntity` gets `Schema Error Count` = 1

---

## PART 2 — E-E-A-T Signal Capture

### Context note
E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness) signals are extracted from HTML metadata, schema, and page structure. No network calls needed beyond what the crawler already fetches.

### 2A — New extractor

Create `src/hype_frog/extractors/eeat.py`:

```python
"""
Extract E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness) signals.
All signals extracted from already-fetched HTML — no additional network calls.
"""
from __future__ import annotations
from typing import Any
from urllib.parse import urlparse
from bs4 import BeautifulSoup


def extract_eeat_signals(
    soup: BeautifulSoup,
    page_url: str,
    page_text: str,
) -> dict[str, Any]:
    out: dict[str, Any] = {}

    # ── AUTHORSHIP ──────────────────────────────────────────────────────────
    # Author from schema (already extracted — check existing schema data)
    # Author from meta tags
    author_meta = soup.find("meta", attrs={"name": "author"})
    out["Meta Author"] = author_meta.get("content", "").strip() if author_meta else None

    # Article author from OG / structured patterns
    article_author = soup.find("meta", property="article:author")
    out["OG Article Author"] = article_author.get("content") if article_author else None

    # rel=author link
    rel_author = soup.find("a", rel=lambda r: r and "author" in r)
    out["Has Rel Author Link"] = rel_author is not None
    out["Rel Author URL"] = rel_author.get("href") if rel_author else None

    # byline class patterns (common in WordPress / news themes)
    byline_candidates = soup.select(".byline, .author, [class*='author'], [class*='byline'], [rel='author']")
    out["Has Byline Element"] = len(byline_candidates) > 0
    if byline_candidates:
        out["Byline Text"] = byline_candidates[0].get_text(strip=True)[:120]
    else:
        out["Byline Text"] = None

    # ── PUBLICATION DATES ────────────────────────────────────────────────────
    # OG article dates
    pub_time = soup.find("meta", property="article:published_time")
    out["OG Published Time"] = pub_time.get("content") if pub_time else None

    mod_time = soup.find("meta", property="article:modified_time")
    out["OG Modified Time"] = mod_time.get("content") if mod_time else None

    # Schema datePublished / dateModified (from schema tags, already parsed elsewhere
    # — if schema extractor already returns these, skip; otherwise check raw JSON-LD)
    import json, re
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            graphs = data.get("@graph", [data])
            for g in graphs if isinstance(graphs, list) else [graphs]:
                if not out.get("Schema Published Date"):
                    out["Schema Published Date"] = g.get("datePublished")
                if not out.get("Schema Modified Date"):
                    out["Schema Modified Date"] = g.get("dateModified")
                if not out.get("Schema Author Name"):
                    author = g.get("author")
                    if isinstance(author, dict):
                        out["Schema Author Name"] = author.get("name")
                    elif isinstance(author, str):
                        out["Schema Author Name"] = author
        except Exception:
            pass

    # Time element (HTML5 datetime attribute)
    time_el = soup.find("time", attrs={"datetime": True})
    out["Has Time Element"] = time_el is not None
    out["Time Element Datetime"] = time_el.get("datetime") if time_el else None

    # ── TRUST SIGNALS ────────────────────────────────────────────────────────
    text_lower = page_text.lower()
    full_html = str(soup)

    # About page link anywhere on page
    about_links = soup.find_all("a", href=re.compile(r"/about", re.I))
    out["Links to About Page"] = len(about_links) > 0

    # Contact info patterns in text
    phone_pattern = re.compile(r'\+?[\d\s\-\(\)]{7,15}(?:ext|x)?[\d\s]{0,5}')
    has_phone = bool(phone_pattern.search(page_text))
    out["Has Phone Number"] = has_phone

    # Email address
    email_pattern = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
    out["Has Email Address"] = bool(email_pattern.search(page_text))

    # Privacy policy / Terms of service links
    privacy_links = soup.find_all("a", href=re.compile(r"privacy|gdpr|popia|data-policy", re.I))
    out["Has Privacy Policy Link"] = len(privacy_links) > 0

    terms_links = soup.find_all("a", href=re.compile(r"terms|conditions|legal|disclaimer", re.I))
    out["Has Terms Link"] = len(terms_links) > 0

    # Social profile links
    social_patterns = re.compile(r"twitter\.com|x\.com|linkedin\.com|facebook\.com|instagram\.com|youtube\.com|tiktok\.com", re.I)
    social_links = [a.get("href") for a in soup.find_all("a", href=social_patterns)]
    out["Social Profile Link Count"] = len(social_links)
    out["Has Social Links"] = len(social_links) > 0

    # ── AUTHORITY SIGNALS ───────────────────────────────────────────────────
    # External links to authoritative sources
    ext_links = [
        a.get("href") for a in soup.find_all("a", href=True)
        if a.get("href", "").startswith("http")
        and urlparse(a.get("href", "")).netloc != urlparse(page_url).netloc
    ]
    out["External Link Count"] = len(ext_links)

    # Wikipedia, .gov, .edu, .org external citations
    authority_domains = re.compile(r"wikipedia\.org|\.gov\.|\.edu\.|who\.int|worldbank\.org|un\.org", re.I)
    out["Has Authority External Links"] = any(authority_domains.search(l) for l in ext_links)

    # ── E-E-A-T COMPOSITE SCORE ─────────────────────────────────────────────
    # Simple additive score (0-10) — more signals = higher trust
    score = 0
    if out.get("Meta Author") or out.get("OG Article Author") or out.get("Schema Author Name"):
        score += 2
    if out.get("Has Byline Element"):
        score += 1
    if out.get("OG Published Time") or out.get("Schema Published Date"):
        score += 1
    if out.get("OG Modified Time") or out.get("Schema Modified Date"):
        score += 1
    if out.get("Has Privacy Policy Link"):
        score += 1
    if out.get("Has Terms Link"):
        score += 1
    if out.get("Has Social Links"):
        score += 1
    if out.get("Has Phone Number") or out.get("Has Email Address"):
        score += 1
    if out.get("Links to About Page"):
        score += 1
    out["E-E-A-T Signal Score"] = score  # 0-10

    return out
```

### 2B — Integrate into data assembler

Find where `BeautifulSoup` (soup) object is available in `data_assembler.py`. Call the extractor:

```python
from hype_frog.extractors.eeat import extract_eeat_signals

eeat_data = extract_eeat_signals(soup=soup, page_url=url, page_text=rendered_text or "")
extra_values.update(eeat_data)
```

### 2C — New columns to add to Main sheet

Group: "E-E-A-T & Trust Signals"
- `E-E-A-T Signal Score` (int 0-10)
- `Schema Author Name`
- `Meta Author`
- `Has Byline Element` (bool)
- `Byline Text`
- `Schema Published Date`
- `Schema Modified Date`
- `OG Published Time`
- `OG Modified Time`
- `Has Time Element` (bool)
- `Has Privacy Policy Link` (bool)
- `Has Terms Link` (bool)
- `Has Social Links` (bool)
- `Social Profile Link Count` (int)
- `Has Phone Number` (bool)
- `Has Email Address` (bool)
- `Links to About Page` (bool)
- `Has Authority External Links` (bool)

### 2D — New registry rules

```python
IssueRule(severity="Warning", name="Low E-E-A-T Signal Score (<3)",
    fn=lambda r: (r.get("E-E-A-T Signal Score") or 0) < 3, scope="url"),
IssueRule(severity="Observation", name="No Author Attribution",
    fn=lambda r: (
        not r.get("Schema Author Name")
        and not r.get("Meta Author")
        and not r.get("Has Byline Element")
    ), scope="url"),
IssueRule(severity="Observation", name="No Publication Date",
    fn=lambda r: (
        not r.get("OG Published Time")
        and not r.get("Schema Published Date")
    ), scope="url"),
IssueRule(severity="Warning", name="No Privacy Policy Link",
    fn=lambda r: not r.get("Has Privacy Policy Link"), scope="site"),
IssueRule(severity="Warning", name="No Terms Link",
    fn=lambda r: not r.get("Has Terms Link"), scope="site"),
```

---

## PART 3 — Proper Duplicate Content Detection

### Current problem (confirmed from audit)
- 129/265 AMC pages (49%) flagged as "Probable Draft or Duplicate Page"
- 164/265 pages have < 50 words — median word count is 29
- The current rule conflates thin content (low word count) with actual duplication
- Result: inflated and misleading duplicate count

### 3A — Add content hashing for similarity detection

Install `python-simhash`:
```bash
pip install simhash
```
Add to requirements. Verify it's available before use.

Create `src/hype_frog/analysis/content_similarity.py`:

```python
"""
Separate thin content detection from genuine duplicate content detection.
"""
from __future__ import annotations
import re
import hashlib
from typing import Any

try:
    from simhash import Simhash
    SIMHASH_AVAILABLE = True
except ImportError:
    SIMHASH_AVAILABLE = False


def _normalise_text(text: str) -> str:
    """Strip noise before hashing — lowercase, collapse whitespace, strip HTML artefacts."""
    t = text.lower()
    t = re.sub(r'[^\w\s]', ' ', t)          # remove punctuation
    t = re.sub(r'\s+', ' ', t).strip()       # collapse whitespace
    return t


def _shingle(text: str, k: int = 3) -> list[str]:
    """Split text into k-word shingles for simhash."""
    words = text.split()
    return [" ".join(words[i:i+k]) for i in range(len(words) - k + 1)]


def compute_content_fingerprint(text: str) -> int | None:
    """Return simhash fingerprint (64-bit int) for content similarity comparison."""
    if not SIMHASH_AVAILABLE:
        return None
    normalised = _normalise_text(text)
    if len(normalised.split()) < 10:
        return None  # Too short to fingerprint meaningfully
    return Simhash(_shingle(normalised)).value


def simhash_distance(h1: int, h2: int) -> int:
    """Hamming distance between two simhash values (0=identical, 64=completely different)."""
    x = h1 ^ h2
    return bin(x).count('1')


def classify_page_duplication(
    url: str,
    title: str | None,
    word_count: int,
    content_hash: int | None,
    all_hashes: dict[str, int],  # url → hash for all crawled pages
    thin_threshold: int = 200,
    similarity_threshold: int = 8,  # simhash distance <= 8 = near-duplicate (out of 64)
) -> dict[str, Any]:
    """
    Returns classification dict:
    - Thin Content: word count below threshold
    - Near-Duplicate Content: simhash distance <= threshold vs another page
    - Draft/Test Page: URL pattern signals draft
    - Probable Duplicate Title: same title as another page
    These are SEPARATE flags, not collapsed into one.
    """
    out: dict[str, Any] = {
        "Is Thin Content": False,
        "Thin Content Word Count": word_count,
        "Is Near Duplicate": False,
        "Near Duplicate Of": None,
        "Content Similarity Score": None,
        "Is Draft or Test Page": False,
        "Draft Signal": None,
    }

    # ── THIN CONTENT ────────────────────────────────────────────────────────
    if word_count < thin_threshold:
        out["Is Thin Content"] = True

    # ── DRAFT/TEST URL PATTERN ───────────────────────────────────────────────
    import re
    draft_patterns = re.compile(
        r'(-copy\b|-copy-\d+|-test\b|-draft\b|-temp\b|-old\b|-backup\b|-bak\b|-v\d+\b|/staging/|/dev/)',
        re.I
    )
    match = draft_patterns.search(url)
    if match:
        out["Is Draft or Test Page"] = True
        out["Draft Signal"] = match.group(0)

    # ── NEAR-DUPLICATE CONTENT ──────────────────────────────────────────────
    if content_hash is not None and SIMHASH_AVAILABLE:
        closest_url = None
        closest_dist = 64  # max possible

        for other_url, other_hash in all_hashes.items():
            if other_url == url:
                continue
            if other_hash is None:
                continue
            dist = simhash_distance(content_hash, other_hash)
            if dist < closest_dist:
                closest_dist = dist
                closest_url = other_url

        if closest_dist <= similarity_threshold and closest_url:
            out["Is Near Duplicate"] = True
            out["Near Duplicate Of"] = closest_url
            # Convert distance to similarity %: 0 distance = 100%, 64 distance = 0%
            out["Content Similarity Score"] = round((1 - closest_dist / 64) * 100, 1)

    return out
```

### 3B — Two-pass integration

The similarity check requires comparing against all other pages, so it must be a post-crawl enrichment pass, not per-page during crawl.

Find the post-crawl enrichment pipeline (`enrichment_flow.py` or similar). Add a new enrichment step:

```python
async def enrich_content_similarity(crawl_rows: list[ExtraRowPayload]) -> None:
    """Post-crawl pass: compute content fingerprints and find near-duplicates."""
    from hype_frog.analysis.content_similarity import compute_content_fingerprint, classify_page_duplication

    # Step 1: compute fingerprint for all rows
    hashes: dict[str, int | None] = {}
    for row in crawl_rows:
        text = row.values.get("Body Text") or row.values.get("Word Count (Body)", "")
        word_count = int(row.values.get("Word Count (Body)") or 0)
        url = row.values.get("URL", "")
        if isinstance(text, str):
            fp = compute_content_fingerprint(text)
        else:
            fp = None
        hashes[url] = fp
        row.values["Content Fingerprint"] = fp

    # Step 2: classify each page against the full fingerprint set
    valid_hashes = {u: h for u, h in hashes.items() if h is not None}
    for row in crawl_rows:
        url = row.values.get("URL", "")
        word_count = int(row.values.get("Word Count (Body)") or 0)
        title = row.values.get("Title")
        content_hash = hashes.get(url)
        classification = classify_page_duplication(
            url=url,
            title=title,
            word_count=word_count,
            content_hash=content_hash,
            all_hashes=valid_hashes,
        )
        row.values.update(classification)
```

**Note on body text:** The fingerprint needs the page's body text. Check what column/value stores the rendered body text in the crawl row. If it's not currently preserved as a value (it may be discarded after word count is calculated), update the pipeline to retain a text excerpt (first 2000 chars) for fingerprinting, then discard after the enrichment pass to avoid bloating the dataset.

### 3C — Update registry rules

**Remove or rename the existing "Probable Draft or Duplicate Page" rule.** Replace with separate rules:

```python
IssueRule(severity="Warning", name="Thin Content (<200 words)",
    fn=lambda r: r.get("Is Thin Content") is True, scope="url"),
IssueRule(severity="Critical", name="Near-Duplicate Content",
    fn=lambda r: r.get("Is Near Duplicate") is True, scope="url"),
IssueRule(severity="Warning", name="Draft or Test Page (URL pattern)",
    fn=lambda r: r.get("Is Draft or Test Page") is True, scope="url"),
```

### 3D — New columns

Add to Main sheet group "Content Quality":
- `Is Thin Content` (bool)
- `Is Near Duplicate` (bool)
- `Near Duplicate Of` (URL string)
- `Content Similarity Score` (float 0-100%)
- `Is Draft or Test Page` (bool)
- `Draft Signal` (string — the matching pattern)

### 3E — Test criteria

- AMC: `Is Thin Content` should flag ~164 pages (those with < 200 words)
- AMC: `Is Near Duplicate` should flag 0-5 pages (no actual near-duplicates expected)
- AMC: `Is Draft or Test Page` should flag `/amc-conference-speakers-2026-copy` and `/awards-2026-test`
- The previous "Probable Draft or Duplicate Page" count of 129 should split into ~164 thin + ~2 draft/test + minimal near-duplicates

---

## PART 4 — Checkpoint / Resume

### 4A — New checkpoint module

Create `src/hype_frog/core/checkpoint.py`:

```python
"""
Crawl checkpoint: save and restore BFS queue state to enable resume on failure.
"""
from __future__ import annotations
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class CheckpointState:
    crawl_target: str
    checkpoint_version: int = 1
    created_at: float = 0.0
    updated_at: float = 0.0
    urls_completed: list[str] = None
    queue_pending: list[tuple[str, int, str | None]] = None  # (url, depth, parent)
    queued_set: list[str] = None
    completed_row_count: int = 0

    def __post_init__(self):
        if self.urls_completed is None:
            self.urls_completed = []
        if self.queue_pending is None:
            self.queue_pending = []
        if self.queued_set is None:
            self.queued_set = []
        if self.created_at == 0.0:
            self.created_at = time.time()


class CrawlCheckpointer:
    def __init__(self, checkpoint_path: str, every_n: int = 50):
        self.path = Path(checkpoint_path)
        self.every_n = every_n
        self._counter = 0

    def should_save(self) -> bool:
        self._counter += 1
        return self.every_n > 0 and self._counter % self.every_n == 0

    def save(self, state: CheckpointState) -> None:
        state.updated_at = time.time()
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "crawl_target": state.crawl_target,
                    "checkpoint_version": state.checkpoint_version,
                    "created_at": state.created_at,
                    "updated_at": state.updated_at,
                    "urls_completed": list(state.urls_completed),
                    "queue_pending": state.queue_pending,
                    "queued_set": list(state.queued_set),
                    "completed_row_count": state.completed_row_count,
                },
                f,
                indent=2,
            )
        os.replace(tmp, self.path)  # atomic rename

    def load(self) -> CheckpointState | None:
        if not self.path.exists():
            return None
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return CheckpointState(**data)
        except Exception as e:
            print(f"[checkpoint] Could not load checkpoint: {e}")
            return None

    def delete(self) -> None:
        if self.path.exists():
            self.path.unlink()
```

### 4B — Integrate into crawl runner

**File:** `src/hype_frog/orchestration/crawl_runner.py`

Find the BFS loop in `execute_crawl`. Read it fully before modifying.

Add these parameters to the crawl configuration / CLI:
- `checkpoint_every: int = 0` (0 = disabled, N = save every N completed URLs)
- `checkpoint_path: str | None = None` (defaults to `{output_dir}/{target_domain}_checkpoint.json`)
- `resume_from: str | None = None` (path to checkpoint file to resume from)

**On crawl start — check for resume:**
```python
checkpointer = None
if checkpoint_every > 0:
    cp_path = checkpoint_path or f"{output_dir}/{target_domain}_checkpoint.json"
    checkpointer = CrawlCheckpointer(cp_path, every_n=checkpoint_every)
    existing = checkpointer.load()
    if existing and resume_from:
        # Restore state
        bfs_queue = deque(
            (url, depth, parent)
            for url, depth, parent in existing.queue_pending
        )
        queued_urls = set(existing.queued_set)
        completed_urls = set(existing.urls_completed)
        print(f"[checkpoint] Resuming from {len(completed_urls)} completed URLs")
    else:
        completed_urls = set()
```

**Inside BFS loop — after processing each URL:**
```python
# After appending result to results list:
if checkpointer and checkpointer.should_save():
    state = CheckpointState(
        crawl_target=target_url,
        urls_completed=list(completed_urls),
        queue_pending=list(bfs_queue),  # list of (url, depth, parent) tuples
        queued_set=list(queued_urls),
        completed_row_count=len(results),
    )
    checkpointer.save(state)
    print(f"[checkpoint] Saved at {len(completed_urls)} URLs")
```

**On successful completion:** delete the checkpoint file so it doesn't interfere with the next run:
```python
if checkpointer:
    checkpointer.delete()
```

### 4C — Add to CLI / config

Find where CLI arguments are defined. Add:
```
--checkpoint-every N    Save checkpoint every N pages (default: 0 = disabled)
--checkpoint-path PATH  Path for checkpoint file
--resume                Resume from existing checkpoint (uses checkpoint-path)
```

Add to `Audit Run Details` output:
- `Checkpoint Every: {N}`
- `Checkpoint Path: {path or "N/A"}`
- `Resumed From Checkpoint: {True/False}`

---

## PART 5 — Conditional Formatting on Main Sheet

### 5A — Find the Main sheet formatting function

From previous context: `adjust_sheet_format` in `src/hype_frog/reporter/sheets/tables_impl.py` is called for every sheet. Find this function and add conditional formatting calls for the Main sheet.

### 5B — Implement conditional formatting

Add a new function `apply_main_sheet_conditional_formatting(writer, worksheet)` called from `adjust_sheet_format` when `sheet_name == "Main"`:

```python
from openpyxl.formatting.rule import ColorScaleRule, CellIsRule, DataBarRule, IconSetRule
from openpyxl.styles import PatternFill, Font
from openpyxl.utils import get_column_letter


def apply_main_sheet_conditional_formatting(worksheet) -> None:
    """Apply traffic-light and data-bar formatting to Main sheet key columns."""

    # Find column letters by header name
    col_map: dict[str, str] = {}
    for cell in worksheet[1]:
        if cell.value:
            col_map[str(cell.value)] = get_column_letter(cell.column)

    max_row = worksheet.max_row
    if max_row < 2:
        return

    def col_range(col_name: str) -> str | None:
        letter = col_map.get(col_name)
        if not letter:
            return None
        return f"{letter}2:{letter}{max_row}"

    # ── SEO Health Score (0-100): Red → Orange → Green ───────────────────────
    rng = col_range("SEO Health Score")
    if rng:
        worksheet.conditional_formatting.add(rng, ColorScaleRule(
            start_type="num", start_value=0,   start_color="FFC7CE",
            mid_type="num",   mid_value=50,    mid_color="FFCC99",
            end_type="num",   end_value=100,   end_color="C6EFCE",
        ))

    # ── Mobile PSI Score (0-100): Red → Orange → Green ─────────────────────
    for col_name in ["Mobile PSI Score", "Desktop PSI Score",
                     "Lighthouse Performance (Mobile)", "Lighthouse Accessibility (Mobile)",
                     "Lighthouse Best Practices (Mobile)", "Lighthouse SEO Score (Mobile)"]:
        rng = col_range(col_name)
        if rng:
            worksheet.conditional_formatting.add(rng, ColorScaleRule(
                start_type="num", start_value=0,  start_color="FFC7CE",
                mid_type="num",   mid_value=50,   mid_color="FFCC99",
                end_type="num",   end_value=100,  end_color="C6EFCE",
            ))

    # ── AEO Readiness Score ──────────────────────────────────────────────────
    rng = col_range("AEO Readiness Score")
    if rng:
        worksheet.conditional_formatting.add(rng, ColorScaleRule(
            start_type="num", start_value=0,  start_color="FFC7CE",
            mid_type="num",   mid_value=50,   mid_color="FFCC99",
            end_type="num",   end_value=100,  end_color="C6EFCE",
        ))

    # ── Lab LCP Mobile: < 2.5s green, 2.5-4.0 orange, > 4.0 red ────────────
    rng = col_range("Lab LCP (Mobile) (s)")
    if rng:
        worksheet.conditional_formatting.add(rng, ColorScaleRule(
            start_type="num", start_value=0,   start_color="C6EFCE",
            mid_type="num",   mid_value=2.5,   mid_color="FFCC99",
            end_type="num",   end_value=10.0,  end_color="FFC7CE",
        ))

    # ── Status Code: highlight 4xx/5xx red ──────────────────────────────────
    rng = col_range("Status Code")
    if rng:
        worksheet.conditional_formatting.add(rng, CellIsRule(
            operator="greaterThanOrEqual", formula=["400"],
            fill=PatternFill("solid", fgColor="00FFC1C1"),
            font=Font(bold=True, color="00991B1B"),
        ))
        worksheet.conditional_formatting.add(rng, CellIsRule(
            operator="equal", formula=['"Timeout"'],
            fill=PatternFill("solid", fgColor="00FFCC99"),
            font=Font(bold=True, color="00924012"),
        ))

    # ── Word Count: data bar ─────────────────────────────────────────────────
    rng = col_range("Word Count (Body)")
    if rng:
        worksheet.conditional_formatting.add(rng, DataBarRule(
            start_type="num", start_value=0,
            end_type="num", end_value=2000,
            color="4472C4",
        ))

    # ── E-E-A-T Signal Score: Red → Green ───────────────────────────────────
    rng = col_range("E-E-A-T Signal Score")
    if rng:
        worksheet.conditional_formatting.add(rng, ColorScaleRule(
            start_type="num", start_value=0,  start_color="FFC7CE",
            mid_type="num",   mid_value=5,    mid_color="FFCC99",
            end_type="num",   end_value=10,   end_color="C6EFCE",
        ))

    # ── Schema Error Count: 0=green, >0=red ─────────────────────────────────
    rng = col_range("Schema Error Count")
    if rng:
        worksheet.conditional_formatting.add(rng, CellIsRule(
            operator="greaterThan", formula=["0"],
            fill=PatternFill("solid", fgColor="00FFC7CE"),
        ))
        worksheet.conditional_formatting.add(rng, CellIsRule(
            operator="equal", formula=["0"],
            fill=PatternFill("solid", fgColor="00C6EFCE"),
        ))

    # ── Click Depth: -1 (orphan) highlight ───────────────────────────────────
    rng = col_range("Click Depth")
    if rng:
        worksheet.conditional_formatting.add(rng, CellIsRule(
            operator="equal", formula=["-1"],
            fill=PatternFill("solid", fgColor="00FFCC99"),
            font=Font(italic=True),
        ))

    # ── Page Size (KB): > 1024 = red (>1MB) ─────────────────────────────────
    rng = col_range("Page Size (KB)")
    if rng:
        worksheet.conditional_formatting.add(rng, CellIsRule(
            operator="greaterThan", formula=["1024"],
            fill=PatternFill("solid", fgColor="00FFC7CE"),
        ))

    # ── Severity Badge: colour by value ─────────────────────────────────────
    rng = col_range("Severity Badge")
    if rng:
        for val, colour in [("Critical", "00FFC1C1"), ("Warning", "00FFCC99"),
                             ("Observation", "00DBEAFE"), ("Unmeasured", "00E5E7EB")]:
            worksheet.conditional_formatting.add(rng, CellIsRule(
                operator="equal", formula=[f'"{val}"'],
                fill=PatternFill("solid", fgColor=colour),
            ))

    # ── Is Thin Content / Is Near Duplicate / Is Draft ───────────────────────
    for col_name in ["Is Thin Content", "Is Near Duplicate", "Is Draft or Test Page"]:
        rng = col_range(col_name)
        if rng:
            worksheet.conditional_formatting.add(rng, CellIsRule(
                operator="equal", formula=["TRUE"],
                fill=PatternFill("solid", fgColor="00FFC7CE"),
            ))

    # ── Content Age (days): > 365 = orange, > 730 = red ─────────────────────
    rng = col_range("Content Age (days)")
    if rng:
        worksheet.conditional_formatting.add(rng, CellIsRule(
            operator="greaterThan", formula=["730"],
            fill=PatternFill("solid", fgColor="00FFC7CE"),
        ))
        worksheet.conditional_formatting.add(rng, CellIsRule(
            operator="greaterThan", formula=["365"],
            fill=PatternFill("solid", fgColor="00FFCC99"),
        ))
```

Note on openpyxl ARGB: fills use `00RRGGBB` format (alpha=00 = opaque in Excel). All colour values above follow this convention.

---

## PART 6 — Quick Wins Tab

### 6A — Define "Quick Win" criteria

A Quick Win is an issue that satisfies ALL of:
- Effort ≤ 4 hours (from FixPlan `Est. Hours`)
- Affects at least 1 URL with either: GSC Clicks > 0 OR Business Risk Score > 100

Rank by: `(GSC Clicks of affected URL × Business Risk Score) / Est. Hours`

Cap at 15 rows.

### 6B — New sheet builder

Create the builder function (add to `src/hype_frog/reporter/sheets/merged_builders.py` or a new file):

```python
def build_quick_wins_rows(
    extra_rows: list[dict],
    fixplan_rows: list[dict],
    summary_rules: list,
) -> list[dict]:
    """
    Build Quick Wins tab: top 15 high-impact low-effort URL+issue combinations.
    """
    from hype_frog.rules.registry import IssueRule

    # Index fixplan by issue name
    fp_index: dict[str, dict] = {}
    for fp_row in fixplan_rows:
        name = fp_row.get("Issue Type", "")
        fp_index[name] = fp_row

    rows: list[dict] = []
    seen: set[tuple] = set()  # (url, issue) dedup

    for rule in summary_rules:
        rule_name = rule.name if hasattr(rule, "name") else rule[1]
        fp = fp_index.get(rule_name)
        if not fp:
            continue
        hours = fp.get("Est. Hours", 99)
        if hours > 4:
            continue  # not a quick win by effort threshold

        rule_fn = rule.fn if hasattr(rule, "fn") else rule[2]
        for row in extra_rows:
            url = row.get("URL", "")
            try:
                if not rule_fn(row):
                    continue
            except Exception:
                continue
            if (url, rule_name) in seen:
                continue
            seen.add((url, rule_name))

            clicks = float(row.get("GSC Clicks") or 0)
            risk = float(row.get("Business Risk Score") or 0)
            if clicks == 0 and risk <= 100:
                continue  # no traffic and low risk — skip

            composite = (clicks * (risk / 100) + risk) / max(hours, 0.5)
            rows.append({
                "Priority Score": round(composite, 1),
                "URL": url,
                "Issue": rule_name,
                "Severity": rule.severity if hasattr(rule, "severity") else rule[0],
                "Effort (hrs)": hours,
                "Owner": fp.get("Owner", ""),
                "GSC Clicks (30d)": int(clicks),
                "Business Risk Score": risk,
                "Recommended Fix": fp.get("Recommended Fix", ""),
                "Sprint": fp.get("Aging/Priority", ""),
                "Revenue Risk": fp.get("Revenue Risk", ""),
                "Jump to FixPlan": fp.get("Jump to Details", ""),
            })

    # Sort by composite score descending, cap at 15
    rows.sort(key=lambda r: r["Priority Score"], reverse=True)
    return rows[:15]
```

### 6C — Register the new sheet

Add to the export sequence and sheet registry. The sheet should appear after `FixPlan` in the workbook order and get tab colour `#ED7D31` (matching the FixPlan orange group).

### 6D — Column formatting

Apply to the Quick Wins sheet:
- Header row: fill `2F3A4A`, font white bold
- `Priority Score` column: data bar formatting
- `Severity` column: colour-coded same as Main sheet
- `Effort (hrs)` column: green fill for ≤2hrs, amber for 3-4hrs
- Freeze row 1

---

## PART 7 — Broken Link Impact Ranking Tab

### 7A — Critical finding from AMC data

`/amc-conference-2025-delegate-packages` has **507 internal links pointing to it** from across the site — the single most-linked broken page. The current output doesn't surface this. A client needs to see this ranked by impact immediately.

### 7B — New sheet builder

Add to `src/hype_frog/reporter/sheets/merged_builders.py`:

```python
def build_broken_link_impact_rows(
    link_inventory_rows: list[dict],
    extra_rows: list[dict],
) -> list[dict]:
    """
    For each broken destination URL, aggregate:
    - How many source pages link to it
    - Which source pages (list)
    - Total GSC clicks of source pages (impact proxy)
    - Whether it was in the sitemap
    Rank by: source_page_clicks + (inbound_count × 10)
    """
    from collections import defaultdict

    # Index extra_rows by URL for GSC clicks and status
    url_index: dict[str, dict] = {r.get("URL", ""): r for r in extra_rows}

    # Find broken links from inventory
    broken_targets: dict[str, dict] = defaultdict(lambda: {
        "source_urls": [],
        "source_clicks_total": 0,
        "anchor_texts": [],
        "status_code": None,
    })

    for link in link_inventory_rows:
        target = link.get("Target URL", "")
        status = link.get("Status Code")
        link_type = link.get("Link Type", "")

        # Only internal broken links
        if link_type not in ("Internal", "internal"):
            continue
        try:
            sc = int(status)
            if sc < 400:
                continue
        except (TypeError, ValueError):
            if str(status).lower() not in ("timeout", "error"):
                continue
            sc = str(status)

        source = link.get("Source URL", "")
        anchor = link.get("Anchor Text", "")
        source_row = url_index.get(source, {})
        source_clicks = float(source_row.get("GSC Clicks") or 0)

        entry = broken_targets[target]
        entry["status_code"] = sc
        if source not in entry["source_urls"]:
            entry["source_urls"].append(source)
            entry["source_clicks_total"] += source_clicks
        if anchor and anchor not in entry["anchor_texts"]:
            entry["anchor_texts"].append(anchor)

    # Build output rows
    output_rows: list[dict] = []
    for target_url, data in broken_targets.items():
        inbound_count = len(data["source_urls"])
        clicks = data["source_clicks_total"]
        priority = clicks + (inbound_count * 10)

        # Determine recommended action
        sc = data["status_code"]
        if isinstance(sc, int) and sc == 404:
            action = "Restore page OR set up 301 redirect to nearest equivalent"
        elif isinstance(sc, str):
            action = "Investigate — page is timing out"
        else:
            action = f"Investigate {sc} response"

        output_rows.append({
            "Priority Score": round(priority, 0),
            "Broken URL": target_url,
            "Status Code": data["status_code"],
            "Inbound Link Count": inbound_count,
            "Source Page Clicks Total": int(clicks),
            "Source Pages (first 5)": " | ".join(
                s.replace("https://africanmarketingconfederation.org", "")
                for s in data["source_urls"][:5]
            ),
            "Anchor Texts Used": " | ".join(data["anchor_texts"][:5]),
            "Recommended Action": action,
        })

    output_rows.sort(key=lambda r: r["Priority Score"], reverse=True)
    return output_rows
```

### 7C — Register the new sheet

Add after `Link Inventory` in export sequence. Tab colour: same `#A6A6A6` as Link Inventory (data group).

Apply header row formatting: fill `2F3A4A`, font white bold. `Priority Score` column: data bar. `Status Code` column: red fill conditional on values >= 400. `Inbound Link Count` column: data bar.

---

## PART 8 — Content Freshness Signals

### 8A — Extract freshness data during crawl

In `data_assembler.py`, find where HTTP response headers are stored. Add extraction of:

```python
def extract_freshness_signals(
    response_headers: dict[str, str],
    soup: BeautifulSoup,
    extra_values: dict,
) -> None:
    """Extract publication and modification dates from headers, meta tags, and schema."""
    import re
    from datetime import datetime, timezone

    # ── HTTP HEADERS ────────────────────────────────────────────────────────
    last_modified_raw = response_headers.get("Last-Modified") or response_headers.get("last-modified")
    extra_values["HTTP Last-Modified"] = last_modified_raw

    # ── META / OG TAGS ──────────────────────────────────────────────────────
    pub_time = soup.find("meta", property="article:published_time")
    extra_values["Published Date"] = pub_time.get("content") if pub_time else None

    mod_time = soup.find("meta", property="article:modified_time")
    extra_values["Last Modified Date"] = mod_time.get("content") if mod_time else (
        last_modified_raw  # fall back to HTTP header
    )

    # ── SCHEMA datePublished / dateModified ─────────────────────────────────
    # (These may already be extracted by Part 2 E-E-A-T — check before duplicating)
    if not extra_values.get("Published Date"):
        extra_values["Published Date"] = extra_values.get("Schema Published Date")
    if not extra_values.get("Last Modified Date"):
        extra_values["Last Modified Date"] = extra_values.get("Schema Modified Date")

    # ── CALCULATE CONTENT AGE ───────────────────────────────────────────────
    best_date_str = extra_values.get("Last Modified Date") or extra_values.get("Published Date")
    content_age_days = None
    if best_date_str:
        try:
            import dateutil.parser
            best_date = dateutil.parser.parse(str(best_date_str))
            if best_date.tzinfo is None:
                best_date = best_date.replace(tzinfo=timezone.utc)
            now = datetime.now(tz=timezone.utc)
            content_age_days = (now - best_date).days
        except Exception:
            pass

    extra_values["Content Age (days)"] = content_age_days

    # ── FRESHNESS STATUS ────────────────────────────────────────────────────
    if content_age_days is None:
        extra_values["Freshness Status"] = "Unknown"
    elif content_age_days <= 90:
        extra_values["Freshness Status"] = "Fresh (< 3 months)"
    elif content_age_days <= 365:
        extra_values["Freshness Status"] = "Recent (3-12 months)"
    elif content_age_days <= 730:
        extra_values["Freshness Status"] = "Ageing (1-2 years)"
    else:
        extra_values["Freshness Status"] = "Stale (> 2 years)"
```

Install `python-dateutil` if not already a dependency.

### 8B — New columns to add to Main sheet

Group: "Content Freshness"
- `Published Date` (date string)
- `Last Modified Date` (date string — best available: schema → OG → HTTP header)
- `HTTP Last-Modified` (raw HTTP header value)
- `Content Age (days)` (integer — days since last modification)
- `Freshness Status` (string: Fresh / Recent / Ageing / Stale / Unknown)

### 8C — New registry rules

```python
IssueRule(severity="Observation", name="Stale Content (>2 years)",
    fn=lambda r: (r.get("Content Age (days)") or 0) > 730, scope="url"),
IssueRule(severity="Observation", name="Ageing Content (1-2 years)",
    fn=lambda r: 365 < (r.get("Content Age (days)") or 0) <= 730, scope="url"),
IssueRule(severity="Observation", name="No Publication or Modification Date",
    fn=lambda r: r.get("Freshness Status") == "Unknown", scope="url"),
```

### 8D — Test criteria

- On AMC: most pages should show `Freshness Status = "Unknown"` (WordPress site with no article meta dates on non-article pages)
- Conference/event pages likely have OG dates if WordPress SEO plugin is active
- The `HTTP Last-Modified` header should be populated for some pages (server-set)

---

## TESTING AFTER ALL PARTS

Run the full test crawl:
```bash
python -m hype_frog crawl \
  --sitemap https://africanmarketingconfederation.org/page-sitemap.xml \
  --psi-key [AMC_PSI_KEY] \
  --gsc-credentials [AMC_OAUTH_PATH] \
  --mode accurate \
  --checkpoint-every 50 \
  --output ./test_outputs/amc_top8_$(date +%Y%m%d_%H%M%S).xlsx
```

**Expected outcomes:**

| Check | Expected for AMC |
|---|---|
| `Schema Present` | False for all 265 pages |
| `No Schema Markup` rule | 265 rows in IssueInventory |
| `E-E-A-T Signal Score` | 0-2 for most pages (low trust signals) |
| `Is Thin Content` | ~164 pages (< 200 words) |
| `Is Near Duplicate` | < 5 pages |
| `Is Draft or Test Page` | 2-3 pages (-copy, -test slugs) |
| `Probable Draft or Duplicate Page` rule | REMOVED (replaced by 3 separate rules) |
| Checkpoint file | Exists at ~50, ~100, ~150, ~200 URL marks during crawl |
| Main sheet conditional formatting | SEO Health Score column shows red→green gradient |
| `Quick Wins` tab | Exists, 15 rows max, sorted by Priority Score |
| `Broken Link Impact` tab | Exists, first row = `/amc-conference-2025-delegate-packages` with Inbound Link Count ~507 |
| `Content Age (days)` | Populated for pages with HTTP Last-Modified or OG dates |
| Total new columns in Main | ~35 new columns across all 8 parts |

---

## UPDATE AUDIT_FIX_LOG.md

```markdown
## Top 8 Expansion — LI-HF-EXPAND-P0

| Part | Description | Status | Test Passed |
|------|-------------|--------|-------------|
| 1 | Schema validation | ⬜ | ⬜ |
| 2 | E-E-A-T signal capture | ⬜ | ⬜ |
| 3 | Proper duplicate detection | ⬜ | ⬜ |
| 4 | Checkpoint/resume | ⬜ | ⬜ |
| 5 | Conditional formatting Main | ⬜ | ⬜ |
| 6 | Quick Wins tab | ⬜ | ⬜ |
| 7 | Broken Link Impact tab | ⬜ | ⬜ |
| 8 | Content freshness signals | ⬜ | ⬜ |
```
