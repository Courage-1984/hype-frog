"""Third-party script inventory from PSI Lighthouse network-requests (A2)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from urllib.parse import urlparse

from hype_frog.core.url_normalization import normalize_url

KNOWN_THIRD_PARTIES: dict[str, tuple[str, str]] = {
    "googletagmanager.com": ("Google Tag Manager", "Tag Management"),
    "google-analytics.com": ("Google Analytics", "Analytics"),
    "googleads.g.doubleclick.net": ("Google Ads", "Advertising"),
    "connect.facebook.net": ("Meta Pixel", "Advertising"),
    "static.hotjar.com": ("Hotjar", "Analytics"),
    "cdn.segment.com": ("Segment", "Analytics"),
    "js.intercomcdn.com": ("Intercom", "Chat"),
    "cdn.hubspot.net": ("HubSpot", "Marketing"),
    "static.klaviyo.com": ("Klaviyo", "Marketing"),
    "cdn.cookielaw.org": ("OneTrust / CookieLaw", "Consent"),
    "consent.cookiebot.com": ("Cookiebot", "Consent"),
    "assets.calendly.com": ("Calendly", "Scheduling"),
    "embed.tawk.to": ("Tawk.to Chat", "Chat"),
    "widget.freshworks.com": ("Freshdesk", "Chat"),
    "cdn.onesignal.com": ("OneSignal", "Marketing"),
    "cdn.amplitude.com": ("Amplitude", "Analytics"),
    "bat.bing.com": ("Microsoft Ads", "Advertising"),
    "snap.licdn.com": ("LinkedIn Insight", "Advertising"),
    "px.ads.linkedin.com": ("LinkedIn Ads", "Advertising"),
}

CHAT_SERVICE_NAMES: frozenset[str] = frozenset(
    {"Intercom", "Tawk.to Chat", "Freshdesk"}
)
CONSENT_SERVICE_NAMES: frozenset[str] = frozenset(
    {"OneTrust / CookieLaw", "Cookiebot"}
)

SCRIPT_INVENTORY_COLUMNS: tuple[str, ...] = (
    "Domain",
    "Service Name",
    "Category",
    "Pages Found On",
    "Average Size (KB)",
    "Total Transferred (KB)",
    "Is Render Blocking",
)


def _match_third_party(url: str) -> tuple[str, str, str] | None:
    host = (urlparse(url).netloc or "").lower().lstrip("www.")
    if not host:
        return None
    for domain, (service, category) in KNOWN_THIRD_PARTIES.items():
        if host == domain or host.endswith(f".{domain}"):
            return domain, service, category
    return None


def _normalise_network_items(items: object) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        transfer = item.get("transferSize") or item.get("resourceSize") or 0
        try:
            transfer_kb = round(float(transfer) / 1024.0, 2)
        except (TypeError, ValueError):
            transfer_kb = 0.0
        out.append(
            {
                "url": url,
                "transfer_kb": transfer_kb,
                "resource_type": str(item.get("resourceType") or ""),
            }
        )
    return out


def summarise_page_third_party_scripts(
    network_items: object,
    *,
    render_blocking_urls: object = None,
) -> dict[str, Any]:
    """Return per-page third-party script summary for Main merge."""
    blocking = {
        str(url).strip()
        for url in (render_blocking_urls or [])
        if str(url).strip()
    }
    services: list[str] = []
    total_kb = 0.0
    script_count = 0
    has_ga = False
    has_gtm = False
    has_meta = False
    has_chat = False
    has_consent = False
    blocking_third_party = False

    for item in _normalise_network_items(network_items):
        match = _match_third_party(item["url"])
        if not match:
            continue
        _domain, service, _category = match
        script_count += 1
        total_kb += float(item["transfer_kb"])
        services.append(service)
        if service == "Google Analytics":
            has_ga = True
        if service == "Google Tag Manager":
            has_gtm = True
        if service == "Meta Pixel":
            has_meta = True
        if service in CHAT_SERVICE_NAMES:
            has_chat = True
        if service in CONSENT_SERVICE_NAMES:
            has_consent = True
        if item["url"] in blocking:
            blocking_third_party = True

    unique_services = sorted(set(services))
    return {
        "Third Party Script Count": script_count,
        "Third Party Scripts": ", ".join(unique_services) if unique_services else None,
        "Third Party Total Size (KB)": round(total_kb, 2) if script_count else None,
        "Has Google Analytics": has_ga,
        "Has Tag Manager": has_gtm,
        "Has Meta Pixel": has_meta,
        "Has Chat Widget": has_chat,
        "Has Consent Manager": has_consent,
        "Third Party JS Blocking": blocking_third_party,
    }


def enrich_third_party_script_fields(extra_rows: list[Any]) -> None:
    """Mutate extra row dicts with third-party columns from PSI network items."""
    for row in extra_rows:
        values = row if isinstance(row, dict) else row.values
        summary = summarise_page_third_party_scripts(
            values.get("PSI Network Items"),
            render_blocking_urls=values.get("PSI Render Blocking URLs"),
        )
        values.update(summary)


def build_script_inventory_rows(extra_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate third-party domains across the crawl for the Script Inventory sheet."""
    aggregate: dict[str, dict[str, Any]] = {}

    for row in extra_rows:
        page_url = str(row.get("URL") or row.get("Final URL") or "").strip()
        blocking = {
            str(url).strip()
            for url in (row.get("PSI Render Blocking URLs") or [])
            if str(url).strip()
        }
        for item in _normalise_network_items(row.get("PSI Network Items")):
            match = _match_third_party(item["url"])
            if not match:
                continue
            domain, service, category = match
            entry = aggregate.setdefault(
                domain,
                {
                    "Domain": domain,
                    "Service Name": service,
                    "Category": category,
                    "pages": set(),
                    "sizes_kb": [],
                    "render_blocking": False,
                },
            )
            if page_url:
                entry["pages"].add(normalize_url(page_url))
            entry["sizes_kb"].append(float(item["transfer_kb"]))
            if item["url"] in blocking:
                entry["render_blocking"] = True

    rows: list[dict[str, Any]] = []
    for entry in sorted(aggregate.values(), key=lambda item: item["Domain"]):
        sizes = entry["sizes_kb"]
        total_kb = round(sum(sizes), 2)
        avg_kb = round(total_kb / len(sizes), 2) if sizes else 0.0
        rows.append(
            {
                "Domain": entry["Domain"],
                "Service Name": entry["Service Name"],
                "Category": entry["Category"],
                "Pages Found On": len(entry["pages"]),
                "Average Size (KB)": avg_kb,
                "Total Transferred (KB)": total_kb,
                "Is Render Blocking": entry["render_blocking"],
            }
        )
    return rows
