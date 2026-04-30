from __future__ import annotations


def resolve_indexability_directive(
    meta_robots_content: str | None,
    x_robots_tag: str | None,
) -> str:
    meta_val = (meta_robots_content or "").lower()
    header_val = (x_robots_tag or "").lower()
    # Most restrictive directive wins.
    if "noindex" in header_val or "noindex" in meta_val:
        return "Noindex"
    return "Indexable"
