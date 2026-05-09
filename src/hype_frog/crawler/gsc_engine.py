from __future__ import annotations

from datetime import date, timedelta
import logging
from pathlib import Path
from urllib.parse import urlparse

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parents[1]


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
        REPO_ROOT / "secrets" / base.name,
        PROJECT_ROOT / base,
        REPO_ROOT / base,
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return REPO_ROOT / "secrets" / base.name


def _resolve_token_path(filename: str) -> Path:
    """Resolve OAuth token path with ``./secrets`` as canonical write location."""
    base = Path(filename)
    if base.is_absolute():
        return base
    return REPO_ROOT / "secrets" / base.name


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
    # Only query Search Console for properties visible to the authenticated user.
    return None


def fetch_gsc_page_metrics(
    target_url: str,
    credentials_file: str = "client_secrets.json",
    token_file: str = "token.json",
) -> dict[str, dict[str, float]]:
    credentials_path = _resolve_credentials_path(credentials_file)
    if not credentials_path.exists():
        return {}

    token_path = _resolve_token_path(token_file)

    creds = _load_credentials(credentials_path=credentials_path, token_path=token_path)
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
    try:
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
    except HttpError as exc:
        logger.warning("GSC query failed for %s: %s", site_url, exc)
        return {}

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
        logger.warning("GSC OAuth bootstrap skipped; credentials file missing: %s", credentials_path)
        return False, str(token_path)
    try:
        _load_credentials(credentials_path=credentials_path, token_path=token_path)
    except Exception as exc:
        logger.warning("GSC OAuth bootstrap failed: %s", exc)
        return False, str(token_path)
    return True, str(token_path)
