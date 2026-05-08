from __future__ import annotations

from collections import defaultdict
from urllib.parse import urlparse

import networkx as nx

from hype_frog.utils import normalize_url_key


def build_inlinks_map(
    extra_rows: list[dict[str, object]],
) -> defaultdict[str, set[str]]:
    crawled_set = {
        normalize_url_key(row.get("Final URL") or row.get("URL") or "")
        for row in extra_rows
        if (row.get("Final URL") or row.get("URL"))
    }
    inlinks_map: defaultdict[str, set[str]] = defaultdict(set)
    for row in extra_rows:
        source = normalize_url_key(row.get("Final URL") or row.get("URL") or "")
        for target in row.get("Internal Links List", []):
            t_norm = normalize_url_key(target)
            if t_norm in crawled_set and source:
                inlinks_map[t_norm].add(source)
    return inlinks_map


def compute_internal_link_intelligence(
    extra_rows: list[dict[str, object]], source_label: str
) -> dict[str, dict[str, object]]:
    graph = nx.DiGraph()
    crawled_urls = {
        normalize_url_key(row.get("Final URL") or row.get("URL"))
        for row in extra_rows
        if row.get("Final URL") or row.get("URL")
    }
    for url in crawled_urls:
        graph.add_node(url)
    for row in extra_rows:
        source = normalize_url_key(row.get("Final URL") or row.get("URL"))
        if not source:
            continue
        for target in row.get("Internal Links List", []):
            target_norm = normalize_url_key(target)
            if target_norm in crawled_urls:
                graph.add_edge(source, target_norm)

    homepage_candidates = sorted(
        [u for u in crawled_urls if urlparse(u).path in {"", "/"}],
        key=len,
    )
    source_candidate = f"https://{source_label.strip('/')}/"
    homepage = normalize_url_key(
        homepage_candidates[0] if homepage_candidates else source_candidate
    )

    click_depth: dict[str, int | None] = {}
    if homepage in graph:
        lengths = nx.single_source_shortest_path_length(graph, homepage)
        for node in graph.nodes:
            click_depth[node] = lengths.get(node)
    else:
        for node in graph.nodes:
            click_depth[node] = None

    orphan_map = {node: graph.in_degree(node) == 0 for node in graph.nodes}
    pagerank_map = (
        nx.pagerank(graph, alpha=0.85, max_iter=100) if graph.number_of_nodes() else {}
    )

    return {
        node: {
            "Click Depth": click_depth.get(node),
            "Orphan Pages": orphan_map.get(node, False),
            "Internal PageRank": round(float(pagerank_map.get(node, 0.0)), 6),
            "Internal Inlinks": int(graph.in_degree(node)),
        }
        for node in graph.nodes
    }
