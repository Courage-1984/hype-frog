from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow

from hype_frog.core import get_logger

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
logger = get_logger(__name__)

_PROJECT_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[3]

_CACHE_TTL_SECONDS = 24 * 60 * 60
_ROW_LIMIT = 25_000


def _inspection_cache_db_path() -> Path:
    cache_dir = _REPO_ROOT / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "gsc_inspection.sqlite"


def _open_inspection_cache_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_inspection_cache_db_path(), timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS gsc_inspection_cache (
            inspection_url TEXT NOT NULL PRIMARY KEY,
            response_body TEXT NOT NULL,
            fetched_at REAL NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def _inspection_cache_get(
    conn: sqlite3.Connection, inspection_url: str
) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT response_body, fetched_at FROM gsc_inspection_cache WHERE inspection_url = ?",
        (inspection_url,),
    ).fetchone()
    if not row:
        return None
    body, fetched_at = row
    if time.time() - float(fetched_at) > _CACHE_TTL_SECONDS:
        conn.execute(
            "DELETE FROM gsc_inspection_cache WHERE inspection_url = ?",
            (inspection_url,),
        )
        conn.commit()
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        conn.execute(
            "DELETE FROM gsc_inspection_cache WHERE inspection_url = ?",
            (inspection_url,),
        )
        conn.commit()
        return None


def _inspection_cache_put(
    conn: sqlite3.Connection, inspection_url: str, payload: dict[str, Any]
) -> None:
    conn.execute(
        """
        INSERT INTO gsc_inspection_cache (inspection_url, response_body, fetched_at)
        VALUES (?, ?, ?)
        ON CONFLICT(inspection_url) DO UPDATE SET
            response_body = excluded.response_body,
            fetched_at = excluded.fetched_at
        """,
        (inspection_url, json.dumps(payload, separators=(",", ":"), sort_keys=True), time.time()),
    )
    conn.commit()


def _normalize_url(url: str) -> str:
    return str(url or "").strip().rstrip("/")


def _extract_host(target_url: str) -> str:
    parsed = urlparse(target_url)
    if parsed.netloc:
        return parsed.netloc.lower()
    if parsed.path:
        return parsed.path.split("/")[0].lower()
    return ""


def _build_candidate_site_urls(target_url: str) -> list[str]:
    host = _extract_host(target_url)
    if not host:
        return []
    host_no_www = host.replace("www.", "")
    return [
        f"sc-domain:{host_no_www}",
        f"https://{host_no_www}/",
        f"http://{host_no_www}/",
        f"https://www.{host_no_www}/",
        f"http://www.{host_no_www}/",
    ]


def _load_credentials(credentials_path: Path, token_path: Path) -> Credentials:
    creds: Credentials | None = None
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except Exception:
            creds = None
    if not creds or not creds.valid:
        logger.info("No valid token found, initiating browser auth.")
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    else:
        logger.info("Loaded existing GSC token")
    return creds


def _resolve_credentials_path(filename: str) -> Path:
    """Resolve OAuth client secrets with ``./secrets`` preferred."""
    base = Path(filename)
    if base.is_absolute():
        return base
    candidates = (
        _REPO_ROOT / "secrets" / base.name,
        _PROJECT_DIR / base,
        _REPO_ROOT / base,
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return _REPO_ROOT / "secrets" / base.name


def _resolve_token_path(filename: str) -> Path:
    """Resolve OAuth token path with ``./secrets`` as canonical write location."""
    base = Path(filename)
    if base.is_absolute():
        return base
    return _REPO_ROOT / "secrets" / base.name


def _resolve_site_url(service: Any, target_url: str) -> str | None:
    candidates = _build_candidate_site_urls(target_url)
    if not candidates:
        return None
    try:
        site_entries = service.sites().list().execute().get("siteEntry", [])
    except Exception:
        site_entries = []
    available = {str(entry.get("siteUrl") or "") for entry in site_entries}
    for candidate in candidates:
        if candidate in available:
            return candidate
    return None


def _rows_to_page_metrics(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    page_metrics: dict[str, dict[str, float]] = {}
    for row in rows:
        page = str((row.get("keys") or [""])[0] or "").strip()
        if not page:
            continue
        clicks = float(row.get("clicks") or 0.0)
        impressions = float(row.get("impressions") or 0.0)
        ctr = float(row.get("ctr") or 0.0)
        position = float(row.get("position") or 0.0)
        payload = {
            "GSC Clicks": clicks,
            "GSC Impressions": impressions,
            "GSC CTR": ctr,
            "GSC Average Position": position,
        }
        page_metrics[_normalize_url(page)] = payload
        page_metrics[page] = payload
    return page_metrics


def _parse_inspection_to_row_fields(payload: dict[str, Any]) -> dict[str, str | None]:
    """Map URL Inspection JSON into extra-row string fields."""
    result = payload.get("inspectionResult") or {}
    idx = result.get("indexStatusResult") or {}
    verdict = idx.get("verdict")
    coverage_state = idx.get("coverageState")
    google_canonical = idx.get("googleCanonical")
    crawl_state = idx.get("pageFetchState")
    robots_state = idx.get("robotsTxtState")
    last_crawl = idx.get("lastCrawlTime") or idx.get("last_crawl_time")
    last_crawl_str = str(last_crawl).strip() if last_crawl is not None else None
    return {
        "GSC Inspection Coverage": "Inspected",
        "GSC Inspection Verdict": str(verdict) if verdict is not None else None,
        "GSC Inspection Coverage State": str(coverage_state) if coverage_state is not None else None,
        "GSC Inspection Google Canonical": str(google_canonical) if google_canonical is not None else None,
        "GSC Inspection Crawl State": str(crawl_state) if crawl_state is not None else None,
        "GSC Inspection Robots State": str(robots_state) if robots_state is not None else None,
        "GSC Inspection Last Crawl": last_crawl_str,
    }


def _inspect_url_sync(
    service: Any,
    site_url: str,
    inspection_url: str,
    conn: sqlite3.Connection,
    cache_lock: threading.Lock,
) -> dict[str, str | None]:
    cached = _inspection_cache_get(conn, inspection_url)
    if cached is not None:
        return _parse_inspection_to_row_fields(cached)
    try:
        payload = (
            service.urlInspection()
            .index()
            .inspect(body={"inspectionUrl": inspection_url, "siteUrl": site_url})
            .execute()
        )
    except HttpError as exc:
        logger.warning("GSC URL Inspection failed for %s: %s", inspection_url, exc)
        return {
            "GSC Inspection Coverage": "Error",
            "GSC Inspection Verdict": None,
            "GSC Inspection Coverage State": None,
            "GSC Inspection Google Canonical": None,
            "GSC Inspection Crawl State": None,
            "GSC Inspection Robots State": None,
            "GSC Inspection Last Crawl": None,
        }
    with cache_lock:
        _inspection_cache_put(conn, inspection_url, payload)
    return _parse_inspection_to_row_fields(payload)


@dataclass(frozen=True)
class GSCEnrichmentContext:
    """Bulk Search Analytics plus handles for optional URL Inspection."""

    page_metrics: dict[str, dict[str, float]]
    analytics_query_succeeded: bool
    service: Any | None
    site_url: str | None


def load_gsc_enrichment_context(
    target_url: str,
    credentials_file: str = "client_secrets.json",
    token_file: str = "token.json",
) -> GSCEnrichmentContext:
    """Resolve property and run a single ``searchanalytics.query`` (up to 25k ``page`` rows)."""
    credentials_path = _resolve_credentials_path(credentials_file)
    if not credentials_path.exists():
        return GSCEnrichmentContext({}, False, None, None)

    token_path = _resolve_token_path(token_file)
    creds = _load_credentials(credentials_path=credentials_path, token_path=token_path)
    service = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    site_url = _resolve_site_url(service, target_url)
    if not site_url:
        return GSCEnrichmentContext({}, False, service, None)

    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=29)
    request_body: dict[str, Any] = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dimensions": ["page"],
        "rowLimit": _ROW_LIMIT,
        "startRow": 0,
    }

    try:
        response = (
            service.searchanalytics()
            .query(siteUrl=site_url, body=request_body)
            .execute()
        )
    except HttpError as exc:
        logger.warning("GSC bulk search analytics query failed for %s: %s", site_url, exc)
        return GSCEnrichmentContext({}, False, service, site_url)

    rows = list(response.get("rows") or [])
    if len(rows) >= _ROW_LIMIT:
        logger.warning(
            "GSC bulk query returned %s rows (rowLimit=%s); additional rows are omitted in this run.",
            len(rows),
            _ROW_LIMIT,
        )
    page_metrics = _rows_to_page_metrics(rows)
    return GSCEnrichmentContext(page_metrics, True, service, site_url)


def fetch_gsc_page_metrics(
    target_url: str,
    credentials_file: str = "client_secrets.json",
    token_file: str = "token.json",
) -> dict[str, dict[str, float]]:
    """Backward-compatible surface: only the page-keyed Search Analytics map."""
    return load_gsc_enrichment_context(
        target_url,
        credentials_file=credentials_file,
        token_file=token_file,
    ).page_metrics


def fetch_gsc_url_inspections_batch(
    service: Any,
    site_url: str,
    inspection_urls: list[str],
) -> dict[str, dict[str, str | None]]:
    """Run URL Inspection for each URL (sequential, SQLite-cached 24h). Keys match inspection URL strings."""
    if not inspection_urls or service is None or not site_url:
        return {}
    conn = _open_inspection_cache_db()
    cache_lock = threading.Lock()
    out: dict[str, dict[str, str | None]] = {}
    inspected_count = 0
    total = len(inspection_urls)
    log_every = 10
    logger.info(
        "GSC URL Inspection batch start: %s URLs (progress log every %s).",
        total,
        log_every,
    )
    started = time.perf_counter()
    try:
        for idx, raw_url in enumerate(inspection_urls, start=1):
            u = str(raw_url or "").strip()
            if not u:
                continue
            fields = _inspect_url_sync(service, site_url, u, conn, cache_lock)
            inspected_count += 1
            out[u] = fields
            out[_normalize_url(u)] = fields
            if idx == 1 or idx % log_every == 0 or idx == total:
                elapsed = time.perf_counter() - started
                logger.info(
                    "GSC URL Inspection progress: %s/%s (%.1fs elapsed).",
                    idx,
                    total,
                    elapsed,
                )
    finally:
        conn.close()
    logger.info(
        "GSC URL Inspection batch complete: %s/%s processed in %.1fs.",
        inspected_count,
        total,
        time.perf_counter() - started,
    )
    return out


def ensure_gsc_oauth_token(
    credentials_file: str = "client_secrets.json",
    token_file: str = "token.json",
) -> tuple[bool, str]:
    """Create or refresh the GSC OAuth token without running a crawl.

    Returns:
        ``(ok, token_path)`` where ``ok`` indicates whether credentials and token
        bootstrap succeeded, and ``token_path`` is the resolved token location.
    """
    credentials_path = _resolve_credentials_path(credentials_file)
    token_path = _resolve_token_path(token_file)
    if not credentials_path.exists():
        logger.warning(
            "GSC OAuth bootstrap skipped; credentials file missing: %s",
            credentials_path,
        )
        return False, str(token_path)
    try:
        _load_credentials(credentials_path=credentials_path, token_path=token_path)
    except Exception as exc:
        logger.warning("GSC OAuth bootstrap failed: %s", exc)
        return False, str(token_path)
    return True, str(token_path)


__all__ = [
    "GSCEnrichmentContext",
    "ensure_gsc_oauth_token",
    "fetch_gsc_page_metrics",
    "fetch_gsc_url_inspections_batch",
    "load_gsc_enrichment_context",
]
