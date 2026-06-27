"""Publication and modification date extraction from headers, meta tags, and schema."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from hype_frog.config import (
    get_content_age_ageing_days,
    get_content_age_recent_days,
    get_content_age_stale_days,
)


def extract_freshness_signals(
    response_headers: dict[str, str],
    soup: BeautifulSoup,
    extra_values: dict[str, Any],
) -> None:
    """Extract publication and modification dates; mutates ``extra_values`` in place."""
    last_modified_raw = response_headers.get("Last-Modified") or response_headers.get(
        "last-modified"
    )
    extra_values["HTTP Last-Modified"] = last_modified_raw
    if last_modified_raw and not extra_values.get("Last-Modified"):
        extra_values["Last-Modified"] = last_modified_raw

    pub_time = soup.find("meta", property="article:published_time")
    if pub_time and pub_time.get("content"):
        extra_values["Published Date"] = pub_time.get("content")

    mod_time = soup.find("meta", property="article:modified_time")
    if mod_time and mod_time.get("content"):
        extra_values["Last Modified Date"] = mod_time.get("content")
    elif last_modified_raw is not None:
        extra_values["Last Modified Date"] = last_modified_raw

    if not extra_values.get("Published Date"):
        extra_values["Published Date"] = extra_values.get("Schema Published Date")
    if not extra_values.get("Last Modified Date"):
        extra_values["Last Modified Date"] = extra_values.get("Schema Modified Date")

    best_date_str = extra_values.get("Last Modified Date") or extra_values.get(
        "Published Date"
    )
    content_age_days: int | None = None
    if best_date_str:
        try:
            best_date = date_parser.parse(str(best_date_str))
            if best_date.tzinfo is None:
                best_date = best_date.replace(tzinfo=timezone.utc)
            content_age_days = (datetime.now(tz=timezone.utc) - best_date).days
        except Exception:
            content_age_days = None

    extra_values["Content Age (days)"] = content_age_days

    recent_days = get_content_age_recent_days()
    ageing_days = get_content_age_ageing_days()
    stale_days = get_content_age_stale_days()

    if content_age_days is None:
        extra_values["Freshness Status"] = "Unknown"
    elif content_age_days <= recent_days:
        extra_values["Freshness Status"] = "Fresh (< 3 months)"
    elif content_age_days <= ageing_days:
        extra_values["Freshness Status"] = "Recent (3-12 months)"
    elif content_age_days <= stale_days:
        extra_values["Freshness Status"] = "Ageing (1-2 years)"
    else:
        extra_values["Freshness Status"] = "Stale (> 2 years)"

    if extra_values.get("Last Modified Date"):
        extra_values["Modified Date"] = extra_values["Last Modified Date"]
