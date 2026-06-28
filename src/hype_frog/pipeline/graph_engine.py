from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from urllib.parse import urlparse

import networkx as nx

from hype_frog.core.models import ExtraRowPayload, MainRowPayload
from hype_frog.core.url_normalization import normalize_url_key


# Click Depth uses -1 for nodes with no path from the detected homepage (export-safe int;
# distinct from ``Orphan Pages``, which is derived from in-degree in this module).
CLICK_DEPTH_UNREACHABLE = -1


def _find_homepage(crawled_urls: list[str]) -> str | None:
    """Find the homepage URL using path matching with trailing-slash tolerance."""
    for url in crawled_urls:
        path = urlparse(url).path
        if path in {"", "/", "//"}:
            return url
    if crawled_urls:
        return min(crawled_urls, key=lambda u: (len(urlparse(u).path), len(u)))
    return None


def _row_values(
    row: ExtraRowPayload | MainRowPayload | Mapping[str, object],
) -> Mapping[str, object]:
    if isinstance(row, (ExtraRowPayload, MainRowPayload)):
        return row.values
    return row


def build_inlinks_map(
    extra_rows: list[ExtraRowPayload] | list[Mapping[str, object]],
) -> defaultdict[str, set[str]]:
    crawled_set = {
        normalize_url_key(values.get("Final URL") or values.get("URL") or "")
        for row in extra_rows
        if ((values := _row_values(row)).get("Final URL") or values.get("URL"))
    }
    inlinks_map: defaultdict[str, set[str]] = defaultdict(set)
    for row in extra_rows:
        values = _row_values(row)
        source = normalize_url_key(values.get("Final URL") or values.get("URL") or "")
        for target in values.get("Internal Links List", []):
            t_norm = normalize_url_key(target)
            if t_norm in crawled_set and source:
                inlinks_map[t_norm].add(source)
    return inlinks_map


def compute_internal_link_intelligence(
    extra_rows: list[ExtraRowPayload] | list[Mapping[str, object]],
    *,
    main_rows: list[MainRowPayload] | None = None,
) -> dict[str, dict[str, object]]:
    graph = nx.DiGraph()
    crawled_urls = set()
    if main_rows:
        crawled_urls = {
            normalize_url_key(_row_values(row).get("URL"))
            for row in main_rows
            if _row_values(row).get("URL")
        }
    if not crawled_urls:
        crawled_urls = {
            normalize_url_key(values.get("Final URL") or values.get("URL"))
            for row in extra_rows
            if ((values := _row_values(row)).get("Final URL") or values.get("URL"))
        }
    for url in crawled_urls:
        graph.add_node(url)
    for row in extra_rows:
        values = _row_values(row)
        source = normalize_url_key(values.get("Final URL") or values.get("URL"))
        if not source:
            continue
        for target in values.get("Internal Links List", []):
            target_norm = normalize_url_key(target)
            if target_norm in crawled_urls:
                graph.add_edge(source, target_norm)

    homepage = _find_homepage(sorted(crawled_urls))
    click_depth: dict[str, int] = {}
    if homepage and homepage in graph:
        lengths = nx.single_source_shortest_path_length(graph, homepage)
        for node in graph.nodes:
            click_depth[node] = lengths.get(node, CLICK_DEPTH_UNREACHABLE)
    else:
        for node in graph.nodes:
            click_depth[node] = CLICK_DEPTH_UNREACHABLE

    # Orphan Pages uses in-degree (no internal inlinks within the crawl graph), not Click Depth.
    orphan_map = {node: graph.in_degree(node) == 0 for node in graph.nodes}
    pagerank_map = (
        nx.pagerank(graph, alpha=0.85, max_iter=100) if graph.number_of_nodes() else {}
    )

    return {
        node: {
            "Click Depth": (depth := click_depth.get(node, CLICK_DEPTH_UNREACHABLE)),
            "Reachable from Homepage": depth != CLICK_DEPTH_UNREACHABLE,
            "Orphan Pages": orphan_map.get(node, False),
            "Internal PageRank": round(float(pagerank_map.get(node, 0.0)), 6),
            "Internal Inlinks": int(graph.in_degree(node)),
        }
        for node in graph.nodes
    }
