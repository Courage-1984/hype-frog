from __future__ import annotations

import os
import re
from datetime import datetime
from urllib.parse import urlparse


def readability_flesch(words: int, sentences: int) -> float | None:
    if words <= 0 or sentences <= 0:
        return None
    return round(206.835 - 1.015 * (words / sentences), 2)


def normalize_text_hash(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def status_class(status_code: object) -> str:
    if isinstance(status_code, int):
        return f"{status_code // 100}xx"
    return str(status_code)


def url_depth(url: str) -> int:
    path = urlparse(url).path.strip("/")
    if not path:
        return 0
    return len([p for p in path.split("/") if p])


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
    name = os.path.basename(urlparse(src_url).path).lower()
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


def build_output_filename(source_label: str, full_suite: bool) -> str:
    source = sanitize_filename_part(urlparse(source_label if "://" in source_label else f"https://{source_label}").netloc or source_label)
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    base_name = f"SEO_AEO_Audit_{source}_{timestamp}"
    candidate = os.path.join(output_dir, f"{base_name}.xlsx")

    # Rare collision guard if multiple runs start within the same second.
    counter = 1
    while os.path.exists(candidate):
        candidate = os.path.join(output_dir, f"{base_name}_{counter}.xlsx")
        counter += 1

    return candidate
