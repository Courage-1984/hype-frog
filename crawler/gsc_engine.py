from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


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
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _resolve_site_url(service, target_url: str) -> str | None:
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
    return candidates[0]


def fetch_gsc_page_metrics(
    target_url: str,
    credentials_file: str = "client_secrets.json",
    token_file: str = "token.json",
) -> dict[str, dict[str, float]]:
    credentials_path = Path(credentials_file)
    if not credentials_path.exists():
        return {}

    creds = _load_credentials(credentials_path=credentials_path, token_path=Path(token_file))
    service = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    site_url = _resolve_site_url(service, target_url)
    if not site_url:
        return {}

    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=29)
    request = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dimensions": ["page"],
        "rowLimit": 25000,
        "startRow": 0,
    }

    rows = []
    while True:
        response = (
            service.searchanalytics()
            .query(siteUrl=site_url, body=request)
            .execute()
        )
        batch_rows = response.get("rows", [])
        if not batch_rows:
            break
        rows.extend(batch_rows)
        if len(batch_rows) < request["rowLimit"]:
            break
        request["startRow"] += request["rowLimit"]

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
