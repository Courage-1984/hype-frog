from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from hype_frog.core import get_logger
from hype_frog.core.models import ExtraRowPayload, MainRowPayload
from hype_frog.core.skipped_row_contract import apply_skipped_row_contract
from hype_frog.core.text_utils import status_class
from hype_frog.core.url_normalization import normalize_url_key
from hype_frog.extractors.robots import resolve_indexability_directive
from hype_frog.extractors.semantic_engine import (
    SemanticAnalyzer,
    get_default_analyzer,
)

logger = get_logger(__name__)


def readability_flesch(words: int, sentences: int, syllables: int) -> float | None:
    if words <= 0 or sentences <= 0:
        return None
    score = 206.835 - 1.015 * (words / sentences) - 84.6 * (syllables / words)
    bounded_score = max(0.0, min(100.0, score))
    return round(bounded_score, 2)


def url_depth(url: str) -> int:
    path = urlparse(url).path.strip("/")
    if not path:
        return 0
    return len([p for p in path.split("/") if p])


def _has_truthy_header(value: object) -> bool:
    """Treat any non-empty header (string or non-False scalar) as 'present'."""
    if value is None or value is False:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


# Open Graph / social preview image: accept common CMS variants, JSON-LD, and relative URLs.
_OG_IMAGE_META_PROPERTY = re.compile(
    r"^og:image$|^og:image:(?:url|secure_url)$",
    re.IGNORECASE,
)
_JSON_LD_IMAGE_KEYS = frozenset(
    {
        "image",
        "thumbnailurl",
        "primaryimageofpage",
        "screenshot",
        "logo",
        "contenturl",
        "embedurl",
    }
)


def _meta_tag_content(tag: object) -> str:
    if tag is None or not hasattr(tag, "get"):
        return ""
    raw = tag.get("content")
    return str(raw).strip() if raw is not None else ""


def _normalize_candidate_image_url(raw: str | None, base_url: str) -> str | None:
    """Return a usable absolute HTTP(S) image URL, or None."""
    s = (raw or "").strip().strip('"').strip("'")
    if not s:
        return None
    lower = s.lower()
    if lower.startswith(("javascript:", "data:", "vbscript:", "file:", "about:")):
        return None
    if lower.startswith("//"):
        s = "https:" + s
    elif not (lower.startswith("http://") or lower.startswith("https://")):
        try:
            s = urljoin(base_url, s)
        except Exception as exc:
            logger.debug("Could not resolve relative URL %r against %r: %s", s, base_url, exc)
            return None
    try:
        return normalize_url_key(s, keep_query=True)
    except Exception as exc:
        logger.debug("Could not normalise resolved URL %r: %s", s, exc)
        return None


def _dedupe_preserve_order(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _append_schema_ld_image_value(val: object, bucket: list[str]) -> None:
    """Flatten JSON-LD image / ImageObject shapes into raw URL strings."""
    if val is None:
        return
    if isinstance(val, str):
        t = val.strip()
        if t:
            bucket.append(t)
        return
    if isinstance(val, dict):
        for key in ("url", "contentUrl", "embedUrl"):
            v = val.get(key)
            if isinstance(v, str) and v.strip():
                bucket.append(v.strip())
        vid = val.get("@id")
        if isinstance(vid, str) and vid.strip().startswith(("http://", "https://")):
            bucket.append(vid.strip())
        if isinstance(val.get("image"), (str, dict, list)):
            _append_schema_ld_image_value(val["image"], bucket)
        return
    if isinstance(val, list):
        for item in val:
            _append_schema_ld_image_value(item, bucket)


def _json_ld_walk_collect_images(obj: object, bucket: list[str], depth: int = 0) -> None:
    if depth > 18:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            lk = str(k).lower()
            if lk in _JSON_LD_IMAGE_KEYS:
                _append_schema_ld_image_value(v, bucket)
            elif isinstance(v, (dict, list)):
                _json_ld_walk_collect_images(v, bucket, depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            _json_ld_walk_collect_images(item, bucket, depth + 1)


def _json_ld_image_candidates(soup: BeautifulSoup) -> list[str]:
    out: list[str] = []
    for script in soup.find_all(
        "script",
        attrs={"type": lambda t: t and str(t).strip().lower() == "application/ld+json"},
    ):
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except Exception:
            continue
        nodes = parsed if isinstance(parsed, list) else [parsed]
        for node in nodes:
            _json_ld_walk_collect_images(node, out)
    return out


def _collect_raw_og_image_candidates(soup: BeautifulSoup) -> list[str]:
    """Document-order raw URL-ish strings from head tags then JSON-LD."""
    found: list[str] = []

    for tag in soup.find_all("meta", attrs={"property": _OG_IMAGE_META_PROPERTY}):
        c = _meta_tag_content(tag)
        if c:
            found.append(c)

    for tag in soup.find_all(
        "meta",
        attrs={
            "name": lambda n: n
            and str(n).strip().lower() in ("twitter:image", "twitter:image:src")
        },
    ):
        c = _meta_tag_content(tag)
        if c:
            found.append(c)

    for tag in soup.find_all(
        "meta",
        attrs={
            "property": lambda p: p
            and str(p).strip().lower() in ("twitter:image", "twitter:image:src")
        },
    ):
        c = _meta_tag_content(tag)
        if c:
            found.append(c)

    for tag in soup.find_all(
        "meta",
        attrs={"itemprop": lambda ip: ip and str(ip).strip().lower() == "image"},
    ):
        c = _meta_tag_content(tag)
        if c:
            found.append(c)

    for link in soup.find_all("link", attrs={"href": True, "rel": True}):
        rels = link.get("rel")
        rel_parts = rels if isinstance(rels, list) else ([rels] if rels else [])
        joined = " ".join(str(r).lower() for r in rel_parts)
        if "image_src" in joined:
            href = (link.get("href") or "").strip()
            if href:
                found.append(href)

    found.extend(_json_ld_image_candidates(soup))
    return _dedupe_preserve_order(found)


def resolve_best_og_image_url(soup: BeautifulSoup, resolved_url: str) -> str | None:
    """Pick the first normalizable OG / Twitter / link / JSON-LD image URL."""
    for raw in _collect_raw_og_image_candidates(soup):
        normalized = _normalize_candidate_image_url(raw, resolved_url)
        if normalized:
            return normalized
    return None


def init_rows(
    url: str, sitemap_meta: dict[str, dict[str, object]] | None
) -> tuple[MainRowPayload, ExtraRowPayload]:
    normalized_url = normalize_url_key(url)
    main_payload = MainRowPayload.model_validate(
        {
            "URL": normalized_url,
        }
    )
    extra_payload = ExtraRowPayload.model_validate(
        {
            "URL": normalized_url,
            "Param URL Flag": "?" in normalized_url,
            "URL Depth": url_depth(normalized_url),
        }
    )
    main_data = main_payload.values
    extra = extra_payload.values
    # sitemap_meta keys are normalised upstream in crawl_runner.execute_crawl()
    # using the same normalize_url_key(); look up by normalized_url (not the
    # raw url param) so this stays correct even if a future caller passes an
    # un-normalized URL.
    meta = (sitemap_meta or {}).get(normalized_url) or (sitemap_meta or {}).get(url)
    if meta:
        extra["Change Frequency"] = meta.get("changefreq")
        extra["Priority"] = meta.get("priority")
        extra["Last Updated"] = meta.get("lastmod")
        extra["Sitemap Image Count"] = meta.get("image_count")
        extra["Sitemap First Image"] = meta.get("first_image_url")
    return main_payload, extra_payload


def assemble_from_html(
    *,
    main_data: MainRowPayload,
    extra: ExtraRowPayload,
    html: str,
    resolved_url: str,
    semantic_analyzer: SemanticAnalyzer | None = None,
    depth: int = 0,
    response_headers: dict[str, str] | None = None,
) -> None:
    """Populate row payloads from rendered HTML.

    ``depth`` carries the BFS hop count from the seed URL (``0`` for the
    seed). The production crawler entrypoint currently passes the
    default; threading the live BFS distance through ``fetcher.py`` is a
    follow-up tracked outside this sprint's 4-file budget.
    """
    from hype_frog.crawler.data_assembler_phases import (
        HtmlAssemblyContext,
        apply_aeo_signals,
        apply_body_readability_and_semantic,
        apply_canonical_and_indexability,
        apply_crawl_depth_and_security,
        apply_eeat_and_freshness,
        apply_heading_outline,
        apply_hreflang,
        apply_image_inventory,
        apply_link_inventory,
        apply_og_social,
        apply_regional_authority,
        apply_schema_signals,
        apply_title_and_meta,
        parse_html_tree,
    )

    ctx = HtmlAssemblyContext(
        main_values=main_data.values,
        extra_values=extra.values,
        html=html,
        resolved_url=resolved_url,
        analyzer=semantic_analyzer or get_default_analyzer(),
        response_headers=response_headers,
    )
    apply_crawl_depth_and_security(ctx, depth=depth)
    parse_html_tree(ctx)
    apply_title_and_meta(ctx)
    apply_canonical_and_indexability(ctx)
    apply_hreflang(ctx)
    apply_og_social(ctx)
    apply_heading_outline(ctx)
    apply_body_readability_and_semantic(ctx)
    apply_aeo_signals(ctx)
    apply_regional_authority(ctx)
    apply_image_inventory(ctx)
    apply_schema_signals(ctx)
    apply_link_inventory(ctx)
    apply_eeat_and_freshness(ctx)
    if main_data.values.get("Extraction State") not in {"complete", "partial"}:
        main_data.values["Extraction State"] = "complete"
        extra.values["Extraction State"] = "complete"


def finalize_row_state(
    main_data: MainRowPayload,
    extra: ExtraRowPayload,
) -> None:
    main_values = main_data.values
    extra_values = extra.values

    if extra_values["Status Class"] is None:
        extra_values["Status Class"] = status_class(extra_values["Status Code"])
    status_val = extra_values["Status Code"]
    status_int = status_val if isinstance(status_val, int) else None
    indexability_reasons: list[str] = []
    if isinstance(status_val, str):
        status_normalized = status_val.strip().lower()
        if status_normalized in (
            "timeout",
            "error",
            "connection error",
            "dns error",
        ):
            indexability_reasons.append(f"Request {status_val}")
            main_values["Indexability"] = "Not Indexable"
    if status_int is not None and status_int >= 400:
        indexability_reasons.append(f"HTTP {status_int}")
        main_values["Indexability"] = "Not Indexable"
    if not indexability_reasons:
        directive_state = resolve_indexability_directive(
            extra_values.get("Meta Robots Raw"), extra_values.get("X-Robots-Tag")
        )
        indexability_reasons.append(
            "Noindex" if directive_state == "Noindex" else "Indexable"
        )
    extra_values["Indexability Reason"] = " | ".join(indexability_reasons)
    if main_values.get("Extraction State") not in {"complete", "partial"}:
        main_values["Extraction State"] = "skipped"
    extra_values["Extraction State"] = main_values["Extraction State"]
    if main_values["Extraction State"] == "skipped":
        apply_skipped_row_contract(main_values, extra_values)
