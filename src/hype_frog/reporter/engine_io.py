from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import pandas as pd

from hype_frog.checkpoint.cache import AuditCache
from hype_frog.models import ExtraRowPayload, MainRowPayload
from hype_frog.utils import normalize_url_key

_ILLEGAL_XLSX_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
_INVALID_SHEET_CHARS_RE = re.compile(r"[:\\/*?\[\]]")


def _safe_sheet_name(name: str) -> str:
    cleaned = _INVALID_SHEET_CHARS_RE.sub("_", str(name or "Sheet"))
    cleaned = cleaned[:31]
    return cleaned or "Sheet"


def _sanitize_excel_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, str):
        return _ILLEGAL_XLSX_CHARS_RE.sub("", value)
    return value


def load_cached_rows(
    cache: AuditCache,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    main_rows: list[dict[str, Any]] = []
    extra_rows: list[dict[str, Any]] = []
    for result in cache.iter_results():
        main_rows.append(result["main"])
        extra_rows.append(result["extra"])
    return main_rows, extra_rows


def build_core_dataframes(
    cache: AuditCache,
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]], list[dict[str, Any]]]:
    main_rows, extra_rows = load_cached_rows(cache)
    return pd.DataFrame(main_rows), pd.DataFrame(extra_rows), main_rows, extra_rows


def _row_to_mapping(
    row: dict[str, Any] | MainRowPayload | ExtraRowPayload,
) -> dict[str, Any]:
    if isinstance(row, (MainRowPayload, ExtraRowPayload)):
        return row.values
    return row


def write_dict_rows_sheet(
    writer: Any,
    sheet_name: str,
    columns: list[str],
    rows: list[dict[str, Any] | MainRowPayload | ExtraRowPayload],
) -> None:
    """Write row payloads to sheet; conversion occurs right before write."""
    ws = writer.book.create_sheet(title=_safe_sheet_name(sheet_name))
    writer.sheets[sheet_name] = ws
    ws.append(columns)
    for row in rows:
        row_mapping = _row_to_mapping(row)
        ws.append([_sanitize_excel_value(row_mapping.get(col)) for col in columns])


def _sanitize_excel_url(url_value: Any) -> str:
    raw = str(url_value or "").strip()
    if not raw:
        return ""
    raw = "".join(ch for ch in raw if ord(ch) >= 32).replace('"', "").replace("'", "")
    if not raw.startswith(("http://", "https://")):
        return raw
    try:
        parts = urlsplit(raw)
        cleaned_path = quote(unquote(parts.path), safe="/:@-._~!$&()*+,;=")
        cleaned_query = quote(unquote(parts.query), safe="=&:@-._~!$()*+,;/?")
        cleaned_fragment = quote(unquote(parts.fragment), safe=":@-._~!$&()*+,;=/?")
        return urlunsplit(
            (parts.scheme, parts.netloc, cleaned_path, cleaned_query, cleaned_fragment)
        )
    except Exception:
        return raw


def _normalize_url_for_match(url_value: Any) -> str:
    return normalize_url_key(_sanitize_excel_url(url_value))


def write_cached_sheet_chunked(
    writer: Any,
    cache: AuditCache,
    sheet_name: str,
    columns: list[str],
    payload_key: str,
    chunk_size: int = 500,
) -> None:
    ws = writer.book.create_sheet(title=_safe_sheet_name(sheet_name))
    writer.sheets[sheet_name] = ws
    ws.append(columns)
    for chunk in cache.iter_results_chunked(chunk_size):
        for result in chunk:
            payload = result.get(payload_key, {})
            ws.append([_sanitize_excel_value(payload.get(col)) for col in columns])
