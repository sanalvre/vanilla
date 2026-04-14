"""
Unit tests for vault manager — directory creation and validation.

These tests are critical: vault structure integrity is the foundation
everything else builds on.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sidecar"))

from services.vault_manager import (
    create_vault_structure,
    validate_vault_structure,
    DEFAULT_GRAPH_JSON,
)


class TestCreateVaultStructure:
    def test_creates_all_directories(self, tmp_path):
        result = create_vault_structure(str(tmp_path))

        # Clean vault
        assert (tmp_path / "clean-vault").is_dir()
        assert (tmp_path / "clean-vault" / "raw").is_dir()
        assert (tmp_path / "clean-vault" / "notes").is_dir()

        # Wiki vault
        assert (tmp_path / "wiki-vault").is_dir()
        assert (tmp_path / "wiki-vault" / "concepts").is_dir()
        assert (tmp_path / "wiki-vault" / "staging").is_dir()
        assert (tmp_path / "wiki-vault" / "staging" / ".meta").is_dir()

    def test_creates_wiki_files(self, tmp_path):
        create_vault_structure(str(tmp_path))

        assert (tmp_path / "wiki-vault" / "AGENTS.md").is_file()
        assert (tmp_path / "wiki-vault" / "ontology.md").is_file()
        assert (tmp_path / "wiki-vault" / "index.md").is_file()
        assert (tmp_path / "wiki-vault" / "graph.json").is_file()

    def test_graph_json_is_valid(self, tmp_path):
        create_vault_structure(str(tmp_path))

        with open(tmp_path / "wiki-vault" / "graph.json") as f:
            data = json.load(f)

        assert data["nodes"] == []
        assert data["edges"] == []
        assert data["source_map"] == {}

    def test_agents_md_contains_rules(self, tmp_path):
        create_vault_structure(str(tmp_path))

        content = (tmp_path / "wiki-vault" / "AGENTS.md").read_text()
        assert "Never write to the clean vault" in content
        assert "frontmatter" in content

    def test_custom_ontology_content(self, tmp_path):
        custom = "# My Custom Ontology\n\nThis is my domain."
        create_vault_structure(str(tmp_path), ontology_content=custom)

        content = (tmp_path / "wiki-vault" / "ontology.md").read_text()
        assert content == custom

    def test_custom_agents_content(self, tmp_path):
        custom = "# Custom AGENTS.md\n\nMy rules."
        create_vault_structure(str(tmp_path), agents_content=custom)

        content = (tmp_path / "wiki-vault" / "AGENTS.md").read_text()
        assert content == custom

    def test_does_not_overwrite_existing(self, tmp_path):
        # First creation
        create_vault_structure(str(tmp_path))

        # Manually modify a file
        agents_path = tmp_path / "wiki-vault" / "AGENTS.md"
        agents_path.write_text("User modified this", encoding="utf-8")

        # Second creation should NOT overwrite
        create_vault_structure(str(tmp_path))
        assert agents_path.read_text() == "User modified this"

    def test_returns_normalized_paths(self, tmp_path):
        result = create_vault_structure(str(tmp_path))

        # Paths should use forward slashes
        assert "\\" not in result["clean_vault_path"]
        assert "\\" not in result["wiki_vault_path"]
        assert "clean-vault" in result["clean_vault_path"]
        assert "wiki-vault" in result["wiki_vault_path"]

    def test_idempotent(self, tmp_path):
        """Calling create twice should not fail or lose data."""
        create_vault_structure(str(tmp_path))
        create_vault_structure(str(tmp_path))

        assert (tmp_path / "clean-vault" / "raw").is_dir()
        assert (tmp_path / "wiki-vault" / "AGENTS.md").is_file()


class TestValidateVaultStructure:
    def test_valid_structure_no_warnings(self, tmp_path):
        create_vault_structure(str(tmp_path))
        warnings = validate_vault_structure(str(tmp_path))
        assert warnings == []

    def test_missing_clean_vault(self, tmp_path):
        create_vault_structure(str(tmp_path))
        (tmp_path / "clean-vault" / "raw").rmdir()
        (tmp_path / "clean-vault" / "notes").rmdir()
        (tmp_path / "clean-vault").rmdir()

        warnings = validate_vault_structure(str(tmp_path))
        assert any("clean-vault/" in w for w in warnings)

    def test_missing_wiki_file(self, tmp_path):
        create_vault_structure(str(tmp_path))
        (tmp_path / "wiki-vault" / "graph.json").unlink()

        warnings = validate_vault_structure(str(tmp_path))
        assert any("graph.json" in w for w in warnings)

    def test_empty_directory_all_warnings(self, tmp_path):
        warnings = validate_vault_structure(str(tmp_path))
        assert len(warnings) >= 2  # At least clean-vault and wiki-vault missing
