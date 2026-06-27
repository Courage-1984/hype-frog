from __future__ import annotations

import json
from typing import Any

from bs4 import BeautifulSoup

from hype_frog.core import get_logger

logger = get_logger(__name__)


def extract_json_ld_blocks(html: str) -> list[str]:
    """Return raw JSON string content from ``application/ld+json`` script tags."""
    soup = BeautifulSoup(html, "lxml")
    blocks: list[str] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (script.string or "").strip()
        if raw:
            blocks.append(raw)
    return blocks


def parse_jsonld_summary(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    schema_types: list[str] = []
    parse_errors = 0
    for script in scripts:
        raw = (script.string or "").strip()
        if not raw:
            continue
        try:
            parsed_json = json.loads(raw)
            nodes = parsed_json if isinstance(parsed_json, list) else [parsed_json]
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                atype = node.get("@type")
                if isinstance(atype, list):
                    schema_types.extend([str(t) for t in atype])
                elif atype:
                    schema_types.append(str(atype))
        except Exception as exc:
            logger.debug("JSON-LD parse error: %s", exc)
            parse_errors += 1
    uniq = sorted(set(schema_types))
    return {
        "schema_types": uniq,
        "schema_types_count": len(uniq),
        "schema_parse_errors": parse_errors,
    }
