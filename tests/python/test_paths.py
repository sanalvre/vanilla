"""
Unit tests for path normalization utilities.

Tests cross-platform path handling — critical for frontmatter,
graph.json, and SQLite consistency between macOS and Windows.
"""

import os
import sys

# Add sidecar to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sidecar"))

from services.paths import (
    normalize_path,
    to_relative,
    to_absolute,
    is_clean_vault_path,
    is_wiki_vault_path,
)


class TestNormalizePath:
    def test_backslashes_converted(self):
        assert normalize_path("clean-vault\\raw\\paper.md") == "clean-vault/raw/paper.md"

    def test_forward_slashes_unchanged(self):
        assert normalize_path("clean-vault/raw/paper.md") == "clean-vault/raw/paper.md"

    def test_mixed_slashes(self):
        assert normalize_path("clean-vault\\raw/paper.md") == "clean-vault/raw/paper.md"

    def test_empty_string(self):
        assert normalize_path("") == ""

    def test_single_filename(self):
        assert normalize_path("paper.md") == "paper.md"

    def test_deep_nesting(self):
        result = normalize_path("a\\b\\c\\d\\e\\f.md")
        assert result == "a/b/c/d/e/f.md"


class TestToRelative:
    def test_basic_relative(self):
        result = to_relative(
            os.path.join("C:", "Users", "User", "Vanilla", "clean-vault", "raw", "paper.md"),
            os.path.join("C:", "Users", "User", "Vanilla"),
        )
        assert result == "clean-vault/raw/paper.md"

    def test_already_relative_style(self):
        # Even if we pass in a path that os.path.relpath can handle
        result = to_relative("/home/user/Vanilla/wiki-vault/concepts/topic.md", "/home/user/Vanilla")
        assert result == "wiki-vault/concepts/topic.md"


class TestToAbsolute:
    def test_absolute_reconstruction(self):
        root = os.path.join("C:", "Users", "User", "Vanilla") if os.name == "nt" else "/home/user/Vanilla"
        result = to_absolute("clean-vault/raw/paper.md", root)
        assert result.endswith(os.path.join("clean-vault", "raw", "paper.md"))
        assert os.path.isabs(result) or result.startswith("C:")


class TestVaultDetection:
    def test_clean_vault_path(self):
        assert is_clean_vault_path("clean-vault/raw/paper.md") is True
        assert is_clean_vault_path("clean-vault/notes/thoughts.md") is True

    def test_wiki_vault_path(self):
        assert is_wiki_vault_path("wiki-vault/concepts/topic.md") is True
        assert is_wiki_vault_path("wiki-vault/staging/batch_001/article.md") is True

    def test_not_vault_path(self):
        assert is_clean_vault_path("wiki-vault/concepts/topic.md") is False
        assert is_wiki_vault_path("clean-vault/raw/paper.md") is False

    def test_backslash_input(self):
        assert is_clean_vault_path("clean-vault\\raw\\paper.md") is True
        assert is_wiki_vault_path("wiki-vault\\concepts\\topic.md") is True
