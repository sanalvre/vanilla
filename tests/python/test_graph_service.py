"""
Unit tests for graph_service.py — graph.json read/write and stale article detection.

These tests are critical for the dual purpose of graph.json:
1. Reagraph visualization (nodes/edges)
2. Stale article tracking (source_map)
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sidecar"))

from services.graph_service import (
    load_graph,
    save_graph,
    add_node,
    remove_node,
    add_edge,
    update_source_map,
    add_source_citation,
    get_articles_citing,
    get_node_by_id,
    get_all_source_paths,
)


@pytest.fixture
def empty_graph():
    return {"nodes": [], "edges": [], "source_map": {}}


@pytest.fixture
def wiki_vault(tmp_path):
    """Create a wiki vault directory with an empty graph.json."""
    (tmp_path / "graph.json").write_text(
        json.dumps({"nodes": [], "edges": [], "source_map": {}}),
        encoding="utf-8",
    )
    return str(tmp_path)


class TestLoadGraph:
    def test_loads_valid_graph(self, wiki_vault):
        graph = load_graph(wiki_vault)
        assert graph["nodes"] == []
        assert graph["edges"] == []
        assert graph["source_map"] == {}

    def test_returns_default_if_missing(self, tmp_path):
        graph = load_graph(str(tmp_path))
        assert graph == {"nodes": [], "edges": [], "source_map": {}}

    def test_returns_default_if_corrupt(self, tmp_path):
        (tmp_path / "graph.json").write_text("not json", encoding="utf-8")
        graph = load_graph(str(tmp_path))
        assert graph == {"nodes": [], "edges": [], "source_map": {}}

    def test_repairs_missing_fields(self, tmp_path):
        (tmp_path / "graph.json").write_text('{"nodes": []}', encoding="utf-8")
        graph = load_graph(str(tmp_path))
        assert graph["edges"] == []
        assert graph["source_map"] == {}


class TestSaveGraph:
    def test_roundtrip(self, tmp_path):
        graph = {"nodes": [{"id": "test"}], "edges": [], "source_map": {}}
        save_graph(str(tmp_path), graph)
        loaded = load_graph(str(tmp_path))
        assert loaded["nodes"][0]["id"] == "test"


class TestAddNode:
    def test_adds_new_node(self, empty_graph):
        graph = add_node(empty_graph, "concept-a", "Concept A", "wiki-vault/concepts/concept-a.md")
        assert len(graph["nodes"]) == 1
        assert graph["nodes"][0]["id"] == "concept-a"
        assert graph["nodes"][0]["label"] == "Concept A"
        assert graph["nodes"][0]["path"] == "wiki-vault/concepts/concept-a.md"

    def test_updates_existing_node(self, empty_graph):
        graph = add_node(empty_graph, "concept-a", "V1", "path/v1.md")
        graph = add_node(graph, "concept-a", "V2", "path/v2.md")
        assert len(graph["nodes"]) == 1
        assert graph["nodes"][0]["label"] == "V2"

    def test_normalizes_path(self, empty_graph):
        graph = add_node(empty_graph, "test", "Test", "wiki-vault\\concepts\\test.md")
        assert graph["nodes"][0]["path"] == "wiki-vault/concepts/test.md"

    def test_sets_batch_id(self, empty_graph):
        graph = add_node(empty_graph, "test", "Test", "path.md", batch_id="batch_001")
        assert graph["nodes"][0]["lastBatch"] == "batch_001"


class TestRemoveNode:
    def test_removes_node_and_edges(self, empty_graph):
        graph = add_node(empty_graph, "a", "A", "a.md")
        graph = add_node(graph, "b", "B", "b.md")
        graph = add_edge(graph, "a", "b")
        graph = remove_node(graph, "a")
        assert len(graph["nodes"]) == 1
        assert graph["nodes"][0]["id"] == "b"
        assert len(graph["edges"]) == 0

    def test_remove_nonexistent_no_error(self, empty_graph):
        graph = remove_node(empty_graph, "nonexistent")
        assert len(graph["nodes"]) == 0


class TestAddEdge:
    def test_adds_edge(self, empty_graph):
        graph = add_edge(empty_graph, "a", "b")
        assert len(graph["edges"]) == 1
        assert graph["edges"][0]["source"] == "a"
        assert graph["edges"][0]["target"] == "b"
        assert graph["edges"][0]["type"] == "wikilink"

    def test_no_duplicate_edges(self, empty_graph):
        graph = add_edge(empty_graph, "a", "b")
        graph = add_edge(graph, "a", "b")
        assert len(graph["edges"]) == 1

    def test_different_types_allowed(self, empty_graph):
        graph = add_edge(empty_graph, "a", "b", "wikilink")
        graph = add_edge(graph, "a", "b", "references")
        assert len(graph["edges"]) == 2


class TestSourceMap:
    def test_update_source_map(self, empty_graph):
        graph = update_source_map(
            empty_graph,
            "clean-vault/raw/paper.md",
            ["wiki-vault/concepts/topic-a.md", "wiki-vault/concepts/topic-b.md"],
        )
        assert len(graph["source_map"]["clean-vault/raw/paper.md"]) == 2

    def test_add_source_citation(self, empty_graph):
        graph = add_source_citation(empty_graph, "clean-vault/raw/paper.md", "wiki-vault/concepts/topic.md")
        assert graph["source_map"]["clean-vault/raw/paper.md"] == ["wiki-vault/concepts/topic.md"]

    def test_no_duplicate_citations(self, empty_graph):
        graph = add_source_citation(empty_graph, "src.md", "article.md")
        graph = add_source_citation(graph, "src.md", "article.md")
        assert len(graph["source_map"]["src.md"]) == 1

    def test_normalizes_paths(self, empty_graph):
        graph = add_source_citation(empty_graph, "clean-vault\\raw\\paper.md", "wiki-vault\\concepts\\topic.md")
        assert "clean-vault/raw/paper.md" in graph["source_map"]


class TestGetArticlesCiting:
    def test_returns_citing_articles(self, empty_graph):
        graph = update_source_map(
            empty_graph,
            "clean-vault/raw/paper.md",
            ["wiki-vault/concepts/a.md", "wiki-vault/concepts/b.md"],
        )
        result = get_articles_citing(graph, "clean-vault/raw/paper.md")
        assert len(result) == 2

    def test_returns_empty_for_unknown_source(self, empty_graph):
        result = get_articles_citing(empty_graph, "nonexistent.md")
        assert result == []

    def test_normalizes_lookup_path(self, empty_graph):
        graph = update_source_map(empty_graph, "clean-vault/raw/paper.md", ["article.md"])
        result = get_articles_citing(graph, "clean-vault\\raw\\paper.md")
        assert len(result) == 1


class TestHelpers:
    def test_get_node_by_id(self, empty_graph):
        graph = add_node(empty_graph, "test", "Test", "path.md")
        node = get_node_by_id(graph, "test")
        assert node is not None
        assert node["label"] == "Test"

    def test_get_node_by_id_not_found(self, empty_graph):
        assert get_node_by_id(empty_graph, "missing") is None

    def test_get_all_source_paths(self, empty_graph):
        graph = add_source_citation(empty_graph, "src1.md", "a.md")
        graph = add_source_citation(graph, "src2.md", "b.md")
        paths = get_all_source_paths(graph)
        assert set(paths) == {"src1.md", "src2.md"}
