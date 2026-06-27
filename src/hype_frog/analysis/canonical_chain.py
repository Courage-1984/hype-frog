"""Post-crawl canonical chain resolution (B1)."""

from __future__ import annotations

from typing import Any

from hype_frog.core.status_codes import is_redirect_status, is_success_status
from hype_frog.core.url_normalization import normalize_url

MAX_CANONICAL_CHAIN_DEPTH = 5


def _norm(url: object) -> str:
    if not url:
        return ""
    try:
        return normalize_url(str(url), keep_query=True)
    except Exception:
        return str(url).strip().rstrip("/")


def build_canonical_target_map(
    extra_rows: list[dict[str, Any]],
) -> dict[str, str]:
    """Map crawled URL keys to declared canonical targets."""
    graph: dict[str, str] = {}
    for row in extra_rows:
        canonical = _norm(row.get("Canonical URL"))
        if not canonical:
            continue
        for key in (_norm(row.get("URL")), _norm(row.get("Final URL"))):
            if key:
                graph[key] = canonical
    return graph


def _target_status(
    url: str,
    *,
    status_by_url: dict[str, object],
    extra_by_url: dict[str, dict[str, Any]],
) -> tuple[object, bool, bool]:
    """Return (status_code, points_to_redirect, points_to_non_200)."""
    status = status_by_url.get(url)
    extra = extra_by_url.get(url, {})
    if status is None and extra:
        status = extra.get("Status Code")
    redirect = is_redirect_status(status) or int(extra.get("Redirect Chain Length") or 0) > 0
    non_200 = status is not None and not is_success_status(status) and not redirect
    return status, redirect, non_200


def resolve_canonical_chain_fields(
    *,
    source_url: str,
    canonical_url: str | None,
    target_map: dict[str, str],
    status_by_url: dict[str, object],
    extra_by_url: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Resolve canonical hop chain for one crawled URL."""
    start = _norm(source_url)
    first_target = _norm(canonical_url)
    defaults: dict[str, Any] = {
        "Canonical Chain Depth": 0,
        "Canonical Chain Final": start or None,
        "Canonical Chain": None,
        "Canonical Loop Detected": False,
        "Canonical Points to Redirect": False,
        "Canonical Points to Non-200": False,
    }
    if not start or not first_target or first_target == start:
        return defaults

    chain: list[str] = [start]
    visited: set[str] = {start}
    current = first_target
    loop = False
    points_redirect = False
    points_non_200 = False

    for _ in range(MAX_CANONICAL_CHAIN_DEPTH):
        if current in visited:
            loop = True
            chain.append(current)
            break
        chain.append(current)
        visited.add(current)
        _, hop_redirect, hop_non_200 = _target_status(
            current,
            status_by_url=status_by_url,
            extra_by_url=extra_by_url,
        )
        points_redirect = points_redirect or hop_redirect
        points_non_200 = points_non_200 or hop_non_200
        next_target = target_map.get(current)
        if not next_target or next_target == current:
            break
        current = next_target

    depth = max(0, len(chain) - 1)
    final = chain[-1] if chain else start
    display = " → ".join(chain) if depth > 0 else None
    return {
        "Canonical Chain Depth": depth,
        "Canonical Chain Final": final or None,
        "Canonical Chain": display,
        "Canonical Loop Detected": loop,
        "Canonical Points to Redirect": points_redirect,
        "Canonical Points to Non-200": points_non_200,
    }


def enrich_extra_rows_canonical_chains(
    extra_rows: list[dict[str, Any]],
    *,
    status_by_url: dict[str, object],
) -> None:
    """Mutate extra row dicts in place with canonical chain columns."""
    target_map = build_canonical_target_map(extra_rows)
    extra_by_url: dict[str, dict[str, Any]] = {}
    for row in extra_rows:
        for key in (_norm(row.get("URL")), _norm(row.get("Final URL"))):
            if key:
                extra_by_url[key] = row

    for row in extra_rows:
        fields = resolve_canonical_chain_fields(
            source_url=str(row.get("URL") or ""),
            canonical_url=row.get("Canonical URL"),
            target_map=target_map,
            status_by_url=status_by_url,
            extra_by_url=extra_by_url,
        )
        row.update(fields)


__all__ = [
    "MAX_CANONICAL_CHAIN_DEPTH",
    "build_canonical_target_map",
    "enrich_extra_rows_canonical_chains",
    "resolve_canonical_chain_fields",
]
