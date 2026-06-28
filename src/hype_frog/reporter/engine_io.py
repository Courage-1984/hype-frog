from __future__ import annotations

import gc
import re
from typing import Any
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import pandas as pd
from openpyxl.utils import get_column_letter

from hype_frog.checkpoint.cache import AuditCache
from hype_frog.core import get_logger
from hype_frog.core.models import ExtraRowPayload, MainRowPayload
from hype_frog.core.url_normalization import normalize_url_key
from hype_frog.pipeline.broken_links import link_inventory_broken_per_source_formula

logger = get_logger(__name__)

_ILLEGAL_XLSX_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]")
_INVALID_SHEET_CHARS_RE = re.compile(r"[:\\/*?\[\]]")

# Chunks at or above this size trigger an explicit ``gc.collect()`` after
# their rows are flushed. Tuned to balance teardown cost against the cost of
# 10k+ row audits keeping deserialised JSON dicts alive for too long.
_GC_COLLECT_CHUNK_THRESHOLD: int = 1000


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


def apply_link_intelligence_summary_broken_formulas(workbook: Any) -> None:
    """Set Broken Internal Links Count and Actionable Fixes on Summary rows from Link Inventory."""
    try:
        names = list(workbook.sheetnames)
    except Exception as exc:
        logger.debug("Could not read workbook sheet names: %s", exc)
        return
    if "Link Intelligence" not in names or "Link Inventory" not in names:
        return
    ws = workbook["Link Intelligence"]
    headers: dict[str, int] = {}
    for col in range(1, ws.max_column + 1):
        key = str(ws.cell(1, col).value or "").strip()
        if key:
            headers[key] = col
    rt_col = headers.get("Record Type")
    brk_col = headers.get("Broken Internal Links Count")
    act_col = headers.get("Actionable Fixes")
    if not rt_col or not brk_col:
        return
    brk_letter = get_column_letter(brk_col)
    for row in range(2, ws.max_row + 1):
        if str(ws.cell(row, rt_col).value or "").strip() != "Summary":
            continue
        formula = link_inventory_broken_per_source_formula(f"$A{row}")
        ws.cell(row=row, column=brk_col, value=formula)
        if act_col:
            ws.cell(
                row=row,
                column=act_col,
                value=(
                    f'=IF({brk_letter}{row}>0,"Fix "&{brk_letter}{row}&'
                    f'" broken links (See Link Inventory tab for details).","")'
                ),
            )


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
    except Exception as exc:
        logger.debug("Could not sanitise Excel URL %r: %s", raw, exc)
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
    """Stream cached rows into ``sheet_name`` without holding the full set in RAM.

    Each chunk is materialised once, written to the worksheet, then
    explicitly cleared so deserialised JSON dictionaries become collectable
    immediately. When ``chunk_size`` exceeds ``_GC_COLLECT_CHUNK_THRESHOLD``
    a manual ``gc.collect()`` is triggered after every chunk to keep the
    high-water mark flat on 10k+ page audits.
    """
    ws = writer.book.create_sheet(title=_safe_sheet_name(sheet_name))
    writer.sheets[sheet_name] = ws
    ws.append(columns)
    rows_written = 0
    aggressive_gc = chunk_size >= _GC_COLLECT_CHUNK_THRESHOLD
    for chunk in cache.iter_results_chunked(chunk_size):
        for result in chunk:
            payload = result.get(payload_key) or {}
            ws.append([_sanitize_excel_value(payload.get(col)) for col in columns])
            rows_written += 1
            if isinstance(payload, dict):
                payload.clear()
            if isinstance(result, dict):
                result.clear()
        chunk.clear()
        del chunk
        if aggressive_gc:
            collected = gc.collect()
            logger.debug(
                "Streamed chunk to %s; gc reclaimed %s objects (rows=%s).",
                sheet_name,
                collected,
                rows_written,
            )
