"""
Tests for agent pipeline utilities and fileback agent.

We don't test the full pipeline end-to-end (requires LLM calls).
We test: JSON parsing, slugification, frontmatter extraction, fileback
file operations, and the pipeline status state machine.
"""

import os
import sys
import json
import shutil
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sidecar"))

from agents.pipeline import (
    _parse_json_response,
    _slugify,
    _estimate_tokens,
    AgentPipelineStatus,
)
from agents.fileback import (
    _extract_frontmatter,
    _extract_wikilinks,
    _update_index,
)


# ─── Pipeline Utilities ──────────────────────────────────────────

class TestParseJsonResponse:
    def test_clean_json_object(self):
        result = _parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_clean_json_array(self):
        result = _parse_json_response('[{"action": "create"}]')
        assert result == [{"action": "create"}]

    def test_json_in_code_fence(self):
        raw = '```json\n{"title": "Test"}\n```'
        result = _parse_json_response(raw)
        assert result["title"] == "Test"

    def test_json_with_surrounding_text(self):
        raw = 'Here is the result:\n[{"a": 1}]\nDone.'
        result = _parse_json_response(raw)
        assert result == [{"a": 1}]

    def test_invalid_json_raises(self):
        with pytest.raises((ValueError, Exception)):
            _parse_json_response("not json at all")


class TestSlugify:
    def test_basic(self):
        assert _slugify("Machine Learning") == "machine-learning"

    def test_special_chars(self):
        assert _slugify("C++ Programming!") == "c-programming"

    def test_empty(self):
        assert _slugify("") == "untitled"


class TestEstimateTokens:
    def test_rough_estimate(self):
        assert _estimate_tokens("abcd") == 1
        assert _estimate_tokens("a" * 400) == 100


class TestPipelineStatus:
    def test_initial_state(self):
        status = AgentPipelineStatus()
        assert status.running is False
        assert status.current_phase is None
        assert status.total_tokens == 0


# ─── Fileback Utilities ──────────────────────────────────────────

class TestExtractFrontmatter:
    def test_basic_frontmatter(self):
        content = "---\ntitle: Test Article\ncategory: science\n---\n\nBody here."
        fm = _extract_frontmatter(content)
        assert fm["title"] == "Test Article"
        assert fm["category"] == "science"

    def test_list_values(self):
        content = "---\ntitle: Test\nsources:\n  - source1.md\n  - source2.md\n---\n\nBody."
        fm = _extract_frontmatter(content)
        assert fm["sources"] == ["source1.md", "source2.md"]

    def test_no_frontmatter(self):
        assert _extract_frontmatter("Just a body") == {}

    def test_empty_values(self):
        content = "---\ntitle: Test\nbatch_id: batch_run_123\nstatus: draft\n---\n"
        fm = _extract_frontmatter(content)
        assert fm["batch_id"] == "batch_run_123"
        assert fm["status"] == "draft"


class TestExtractWikilinks:
    def test_finds_links(self):
        content = "See [[Machine Learning]] and [[Neural Networks]]."
        links = _extract_wikilinks(content)
        assert links == ["Machine Learning", "Neural Networks"]

    def test_no_links(self):
        assert _extract_wikilinks("No links here.") == []


class TestUpdateIndex:
    def test_appends_new_articles(self, tmp_path):
        wiki = tmp_path / "wiki-vault"
        wiki.mkdir()
        index = wiki / "index.md"
        index.write_text("# Wiki Index\n\n## Concepts\n")

        _update_index(wiki, [{"title": "New Concept", "filename": "new-concept.md"}])

        content = index.read_text()
        assert "[[New Concept]]" in content
        assert "concepts/new-concept.md" in content

    def test_no_duplicates(self, tmp_path):
        wiki = tmp_path / "wiki-vault"
        wiki.mkdir()
        index = wiki / "index.md"
        link_line = "- [[Existing]] \u2014 `concepts/existing.md`"
        index.write_text(f"# Wiki Index\n\n{link_line}\n", encoding="utf-8")

        _update_index(wiki, [{"title": "Existing", "filename": "existing.md"}])

        content = index.read_text(encoding="utf-8")
        assert content.count("[[Existing]]") == 1

    def test_creates_index_if_missing(self, tmp_path):
        wiki = tmp_path / "wiki-vault"
        wiki.mkdir()

        _update_index(wiki, [{"title": "First", "filename": "first.md"}])

        index = wiki / "index.md"
        assert index.exists()
        assert "[[First]]" in index.read_text()
