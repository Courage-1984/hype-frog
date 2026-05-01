from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd

_ILLEGAL_XLSX_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
_INVALID_SHEET_CHARS_RE = re.compile(r"[:\\/*?\[\]]")


def sanitize_excel_string(value: object) -> object:
    if not isinstance(value, str):
        return value
    return _ILLEGAL_XLSX_CHARS_RE.sub("", value)


def sanitize_excel_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, (float, np.floating)):
        if math.isnan(float(value)) or math.isinf(float(value)):
            return ""
    if isinstance(value, str):
        return sanitize_excel_string(value)
    return value


def sanitize_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    sanitized: list[dict[str, object]] = []
    for row in rows:
        sanitized.append({k: sanitize_excel_value(v) for k, v in row.items()})
    return sanitized


def sanitize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    clean_df = df.copy()
    clean_df = clean_df.replace([np.inf, -np.inf], np.nan)
    clean_df = clean_df.fillna("")
    date_like_tokens = (
        "date",
        "time",
        "timestamp",
        "lastmod",
        "updated",
        "modified",
        "published",
    )
    for col in clean_df.columns:
        col_name = str(col).strip().lower()
        if isinstance(clean_df[col].dtype, pd.DatetimeTZDtype):
            clean_df[col] = clean_df[col].dt.tz_localize(None).astype(str)
            clean_df[col] = clean_df[col].replace("NaT", "")
            continue
        if pd.api.types.is_datetime64_any_dtype(clean_df[col].dtype):
            clean_df[col] = clean_df[col].astype(str).replace("NaT", "")
            continue
        if pd.api.types.is_object_dtype(
            clean_df[col].dtype
        ) or pd.api.types.is_string_dtype(clean_df[col].dtype):
            if any(token in col_name for token in date_like_tokens):
                parsed_dt = pd.to_datetime(
                    clean_df[col], errors="coerce", utc=True, format="mixed"
                )
                if parsed_dt.notna().any():
                    clean_df[col] = (
                        parsed_dt.dt.tz_localize(None).astype(str).replace("NaT", "")
                    )
                    continue
            clean_df[col] = clean_df[col].map(sanitize_excel_value)
    return clean_df


def safe_sheet_name(name: str) -> str:
    sanitized = _INVALID_SHEET_CHARS_RE.sub("_", str(name or "Sheet"))
    sanitized = sanitized[:31]
    return sanitized or "Sheet"


def to_excel_safe(
    df: pd.DataFrame, writer: pd.ExcelWriter, sheet_name: str, **kwargs
) -> None:
    safe_df = sanitize_dataframe(df)
    safe_df.columns = [
        str(col).replace("\n", " ").replace("\r", " ").strip()[:255]
        or f"Column_{idx + 1}"
        for idx, col in enumerate(safe_df.columns)
    ]
    safe_df.to_excel(writer, sheet_name=safe_sheet_name(sheet_name), **kwargs)
