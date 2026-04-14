"""
Tests for the setup crew's response parsing logic.

We don't test actual LLM calls (those hit external APIs) — we test
the JSON extraction/validation that runs on whatever the LLM returns.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sidecar"))

from agents.setup_crew import _parse_response


class TestParseResponse:
    def test_clean_json(self):
        raw = '{"ontology_md": "# Ontology", "agents_md": "# Agents", "suggested_categories": ["A", "B"]}'
        result = _parse_response(raw)
        assert result["ontology_md"] == "# Ontology"
        assert result["agents_md"] == "# Agents"
        assert result["suggested_categories"] == ["A", "B"]

    def test_json_in_code_fence(self):
        raw = '```json\n{"ontology_md": "# O", "agents_md": "# A", "suggested_categories": ["X"]}\n```'
        result = _parse_response(raw)
        assert result["ontology_md"] == "# O"

    def test_json_in_plain_fence(self):
        raw = '```\n{"ontology_md": "content", "agents_md": "agents", "suggested_categories": []}\n```'
        result = _parse_response(raw)
        assert result["ontology_md"] == "content"

    def test_json_with_surrounding_text(self):
        raw = 'Here is the result:\n{"ontology_md": "# O", "agents_md": "# A", "suggested_categories": ["C"]}\nDone!'
        result = _parse_response(raw)
        assert result["suggested_categories"] == ["C"]

    def test_missing_ontology_raises(self):
        raw = '{"ontology_md": "", "agents_md": "# A", "suggested_categories": []}'
        with pytest.raises(ValueError, match="ontology_md"):
            _parse_response(raw)

    def test_missing_agents_raises(self):
        raw = '{"ontology_md": "# O", "agents_md": "", "suggested_categories": []}'
        with pytest.raises(ValueError, match="agents_md"):
            _parse_response(raw)

    def test_no_json_at_all_raises(self):
        with pytest.raises((ValueError, Exception)):
            _parse_response("This is just plain text with no JSON")

    def test_defaults_missing_categories(self):
        raw = '{"ontology_md": "# O", "agents_md": "# A"}'
        result = _parse_response(raw)
        assert result["suggested_categories"] == []
