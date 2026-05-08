from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse


def normalize_text_hash(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def status_class(status_code: object) -> str:
    if isinstance(status_code, int):
        return f"{status_code // 100}xx"
    return str(status_code)


def word_count_band(count: int) -> str:
    if count < 300:
        return "Thin"
    if count < 800:
        return "OK"
    return "Strong"


def image_extension(src_url: str) -> str:
    path = urlparse(src_url).path.lower()
    for ext in [".webp", ".avif", ".jpg", ".jpeg", ".png", ".gif", ".svg"]:
        if path.endswith(ext):
            return ext.replace(".", "")
    return "other"


def looks_generic_image_filename(src_url: str) -> bool:
    name = Path(urlparse(src_url).path).name.lower()
    if not name:
        return False
    return bool(re.match(r"^(img|image|dsc|photo|pic)[-_]?\d+\.[a-z0-9]+$", name))


def to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def sanitize_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", str(value or "").strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("._-")
    return cleaned or "audit"
