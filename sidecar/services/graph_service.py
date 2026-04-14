"""
Graph service — manages graph.json for Reagraph visualization and stale article tracking.

graph.json serves a dual purpose:
1. Reagraph nodes/edges for the knowledge graph UI
2. source_map for stale article detection (source file -> wiki articles that cite it)

This module is the ONLY place graph.json is read/written.
"""

import json
from pathlib import Path
from typing import List, Optional

from services.paths import normalize_path


def _default_graph() -> dict:
    return {"nodes": [], "edges": [], "source_map": {}}


def load_graph(wiki_vault_path: str) -> dict:
    """
    Load graph.json from the wiki vault.

    Returns default empty graph if file is missing or corrupt.
    """
    graph_path = Path(wiki_vault_path) / "graph.json"
    if not graph_path.exists():
        return _default_graph()
    try:
        with open(graph_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Validate structure
        if not isinstance(data.get("nodes"), list):
            data["nodes"] = []
        if not isinstance(data.get("edges"), list):
            data["edges"] = []
        if not isinstance(data.get("source_map"), dict):
            data["source_map"] = {}
        return data
    except (json.JSONDecodeError, OSError):
        return _default_graph()


def save_graph(wiki_vault_path: str, graph: dict) -> None:
    """Write graph.json to the wiki vault."""
    graph_path = Path(wiki_vault_path) / "graph.json"
    with open(graph_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)


def add_node(
    graph: dict,
    node_id: str,
    label: str,
    path: str,
    category: str = "",
    batch_id: str = "",
) -> dict:
    """
    Add a concept node to the graph. Updates existing node if id matches.

    Returns the modified graph (mutated in place).
    """
    path = normalize_path(path)
    # Check if node already exists
    for node in graph["nodes"]:
        if node["id"] == node_id:
            node["label"] = label
            node["path"] = path
            node["category"] = category
            node["lastBatch"] = batch_id
            return graph

    graph["nodes"].append({
        "id": node_id,
        "label": label,
        "path": path,
        "category": category,
        "lastBatch": batch_id,
    })
    return graph


def remove_node(graph: dict, node_id: str) -> dict:
    """Remove a node and all its edges from the graph."""
    graph["nodes"] = [n for n in graph["nodes"] if n["id"] != node_id]
    graph["edges"] = [
        e for e in graph["edges"]
        if e["source"] != node_id and e["target"] != node_id
    ]
    return graph


def add_edge(
    graph: dict,
    source: str,
    target: str,
    edge_type: str = "wikilink",
) -> dict:
    """
    Add an edge between two concept nodes.
    Skips if identical edge already exists.
    """
    for edge in graph["edges"]:
        if edge["source"] == source and edge["target"] == target and edge["type"] == edge_type:
            return graph  # Already exists

    graph["edges"].append({
        "source": source,
        "target": target,
        "type": edge_type,
    })
    return graph


def update_source_map(
    graph: dict,
    source_path: str,
    article_paths: List[str],
) -> dict:
    """
    Update the source_map: which wiki articles cite a given source file.

    source_path: a clean-vault file (e.g., clean-vault/raw/paper.md)
    article_paths: list of wiki-vault article paths that cite this source
    """
    source_path = normalize_path(source_path)
    article_paths = [normalize_path(p) for p in article_paths]
    graph["source_map"][source_path] = article_paths
    return graph


def add_source_citation(
    graph: dict,
    source_path: str,
    article_path: str,
) -> dict:
    """Add a single article to a source's citation list."""
    source_path = normalize_path(source_path)
    article_path = normalize_path(article_path)

    if source_path not in graph["source_map"]:
        graph["source_map"][source_path] = []

    if article_path not in graph["source_map"][source_path]:
        graph["source_map"][source_path].append(article_path)

    return graph


def get_articles_citing(graph: dict, source_path: str) -> List[str]:
    """
    Look up all wiki articles that cite a given source file.

    This is the core of stale article detection: when a source changes,
    we find all articles that reference it and flag them as stale.
    """
    source_path = normalize_path(source_path)
    return graph.get("source_map", {}).get(source_path, [])


def get_node_by_id(graph: dict, node_id: str) -> Optional[dict]:
    """Look up a single node by its ID."""
    for node in graph["nodes"]:
        if node["id"] == node_id:
            return node
    return None


def get_all_source_paths(graph: dict) -> List[str]:
    """Get all source file paths that have citations in the graph."""
    return list(graph.get("source_map", {}).keys())
