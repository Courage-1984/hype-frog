"""Lightweight competitor domain sampling for benchmark comparisons (B5)."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import aiohttp
from bs4 import BeautifulSoup

from hype_frog.core import get_logger
from hype_frog.crawler.sitemap import parse_sitemap

logger = get_logger(__name__)

COMPETITOR_BENCHMARK_COLUMNS: tuple[str, ...] = (
    "Metric",
    "Client Site",
)

_SAMPLE_PAGE_LIMIT = 10
_FETCH_TIMEOUT = aiohttp.ClientTimeout(total=20)


def _normalise_domain(domain: str) -> str:
    text = str(domain or "").strip().lower()
    text = re.sub(r"^https?://", "", text)
    return text.strip("/")


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _pct(true_count: int, total: int) -> float | None:
    if total <= 0:
        return None
    return round((true_count / total) * 100.0, 1)


def _extract_page_signals(html: str, url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html or "", "lxml")
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    meta = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    meta_desc = (meta.get("content") or "").strip() if meta else ""
    h1_count = len(soup.find_all("h1"))
    body_text = soup.get_text(" ", strip=True)
    word_count = len(body_text.split())
    question_headings = sum(
        1
        for tag in soup.find_all(re.compile(r"^h[2-4]$", re.I))
        if str(tag.get_text(" ", strip=True) or "").strip().endswith("?")
    )
    schema_types: set[str] = set()
    for script in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        nodes = payload if isinstance(payload, list) else [payload]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            schema_type = node.get("@type")
            if isinstance(schema_type, list):
                schema_types.update(str(item) for item in schema_type)
            elif schema_type:
                schema_types.add(str(schema_type))
    return {
        "title_present": bool(title),
        "meta_present": bool(meta_desc),
        "single_h1": h1_count == 1,
        "word_count": word_count,
        "question_headings": question_headings,
        "schema_present": bool(schema_types),
        "schema_count": len(schema_types),
        "aeo_proxy": _aeo_proxy_score(
            title_present=bool(title),
            meta_present=bool(meta_desc),
            single_h1=h1_count == 1,
            question_headings=question_headings,
            schema_present=bool(schema_types),
            word_count=word_count,
        ),
    }


def _aeo_proxy_score(
    *,
    title_present: bool,
    meta_present: bool,
    single_h1: bool,
    question_headings: int,
    schema_present: bool,
    word_count: int,
) -> float:
    score = 0.0
    if title_present:
        score += 15
    if meta_present:
        score += 15
    if single_h1:
        score += 15
    if question_headings > 0:
        score += 20
    if schema_present:
        score += 20
    if word_count >= 300:
        score += 15
    return min(100.0, score)


async def _fetch_html(session: aiohttp.ClientSession, url: str) -> str | None:
    try:
        async with session.get(url, timeout=_FETCH_TIMEOUT) as response:
            if response.status != 200:
                return None
            return await response.text()
    except Exception as exc:
        logger.warning("Competitor fetch failed for %s (%s)", url, exc)
        return None


async def _sample_urls_for_domain(
    session: aiohttp.ClientSession, domain: str
) -> list[str]:
    homepage = f"https://{domain}/"
    candidates = [homepage]
    sitemap_candidates = [
        f"https://{domain}/sitemap.xml",
        f"https://{domain}/sitemap_index.xml",
        f"https://{domain}/page-sitemap.xml",
    ]
    for sitemap_url in sitemap_candidates:
        try:
            urls, _meta, _files = await parse_sitemap(sitemap_url, session)
        except Exception as exc:
            logger.debug("Sitemap parse failed %r: %s", sitemap_url, exc)
            continue
        if urls:
            candidates.extend(urls[:_SAMPLE_PAGE_LIMIT])
            break
    deduped: list[str] = []
    seen: set[str] = set()
    for url in candidates:
        key = url.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(url)
        if len(deduped) >= _SAMPLE_PAGE_LIMIT + 1:
            break
    return deduped


async def _aggregate_domain_signals(
    session: aiohttp.ClientSession, domain: str
) -> dict[str, float | None]:
    urls = await _sample_urls_for_domain(session, domain)
    signals: list[dict[str, Any]] = []
    for url in urls:
        html = await _fetch_html(session, url)
        if not html:
            continue
        signals.append(_extract_page_signals(html, url))
        await asyncio.sleep(0.25)
    if not signals:
        return {
            "pages_sampled": 0.0,
            "title_coverage_pct": None,
            "meta_coverage_pct": None,
            "single_h1_pct": None,
            "schema_coverage_pct": None,
            "avg_word_count": None,
            "avg_question_headings": None,
            "avg_aeo_proxy_score": None,
        }
    total = len(signals)
    return {
        "pages_sampled": float(total),
        "title_coverage_pct": _pct(sum(1 for s in signals if s["title_present"]), total),
        "meta_coverage_pct": _pct(sum(1 for s in signals if s["meta_present"]), total),
        "single_h1_pct": _pct(sum(1 for s in signals if s["single_h1"]), total),
        "schema_coverage_pct": _pct(sum(1 for s in signals if s["schema_present"]), total),
        "avg_word_count": _avg([float(s["word_count"]) for s in signals]),
        "avg_question_headings": _avg([float(s["question_headings"]) for s in signals]),
        "avg_aeo_proxy_score": _avg([float(s["aeo_proxy"]) for s in signals]),
    }


def _client_aggregate(main_rows: list[dict[str, Any]], extra_rows: list[dict[str, Any]]) -> dict[str, float | None]:
    extra_by_url = {
        str(row.get("URL") or "").strip(): row for row in extra_rows if row.get("URL")
    }
    total = len(main_rows) or 1
    title_present = 0
    meta_present = 0
    single_h1 = 0
    schema_present = 0
    word_counts: list[float] = []
    question_counts: list[float] = []
    aeo_scores: list[float] = []
    for main in main_rows:
        url = str(main.get("URL") or "").strip()
        extra = extra_by_url.get(url, {})
        if not bool(extra.get("Title Missing")):
            title_present += 1
        if not bool(extra.get("Meta Description Missing")):
            meta_present += 1
        if int(float(extra.get("H1 Count") or 0)) == 1:
            single_h1 += 1
        if int(float(extra.get("Schema Types Count") or 0)) > 0:
            schema_present += 1
        word_counts.append(float(main.get("Word Count (Body)") or extra.get("Word Count") or 0))
        question_counts.append(float(extra.get("Question Heading Count") or 0))
        aeo_scores.append(float(extra.get("AEO Readiness Score") or 0))
    return {
        "pages_sampled": float(len(main_rows)),
        "title_coverage_pct": _pct(title_present, len(main_rows)),
        "meta_coverage_pct": _pct(meta_present, len(main_rows)),
        "single_h1_pct": _pct(single_h1, len(main_rows)),
        "schema_coverage_pct": _pct(schema_present, len(main_rows)),
        "avg_word_count": _avg(word_counts),
        "avg_question_headings": _avg(question_counts),
        "avg_aeo_proxy_score": _avg(aeo_scores),
    }


_METRIC_LABELS: tuple[tuple[str, str], ...] = (
    ("pages_sampled", "Pages Sampled"),
    ("title_coverage_pct", "Title Coverage (%)"),
    ("meta_coverage_pct", "Meta Description Coverage (%)"),
    ("single_h1_pct", "Single H1 Compliance (%)"),
    ("schema_coverage_pct", "Schema Coverage (%)"),
    ("avg_word_count", "Average Word Count"),
    ("avg_question_headings", "Average Question Headings"),
    ("avg_aeo_proxy_score", "Average AEO / Readiness Score"),
)


def build_competitor_benchmark_rows(
    *,
    client_label: str,
    client_metrics: dict[str, float | None],
    competitor_metrics: dict[str, dict[str, float | None]],
) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
    """Return comparison rows and dynamic column order."""
    columns = ("Metric", "Client Site", *tuple(competitor_metrics.keys()))
    rows: list[dict[str, Any]] = []
    for key, label in _METRIC_LABELS:
        row: dict[str, Any] = {
            "Metric": label,
            "Client Site": client_metrics.get(key),
        }
        for domain, metrics in competitor_metrics.items():
            row[domain] = metrics.get(key)
        rows.append(row)
    if not competitor_metrics:
        rows = [
            {
                "Metric": "No competitor domains configured",
                "Client Site": client_label,
            }
        ]
        columns = ("Metric", "Client Site")
    return rows, columns


async def benchmark_competitor_domains(
    *,
    client_label: str,
    main_rows: list[dict[str, Any]],
    extra_rows: list[dict[str, Any]],
    competitor_domains: list[str],
    session: aiohttp.ClientSession | None = None,
) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
    """Sample competitor domains and build a client-vs-competitors comparison table."""
    domains = [_normalise_domain(domain) for domain in competitor_domains if _normalise_domain(domain)]
    client_metrics = _client_aggregate(main_rows, extra_rows)
    if not domains:
        return build_competitor_benchmark_rows(
            client_label=client_label,
            client_metrics=client_metrics,
            competitor_metrics={},
        )

    owns_session = session is None
    session_obj = session or aiohttp.ClientSession()
    competitor_metrics: dict[str, dict[str, float | None]] = {}
    try:
        for domain in domains[:5]:
            competitor_metrics[domain] = await _aggregate_domain_signals(session_obj, domain)
    finally:
        if owns_session:
            await session_obj.close()

    return build_competitor_benchmark_rows(
        client_label=client_label,
        client_metrics=client_metrics,
        competitor_metrics=competitor_metrics,
    )
