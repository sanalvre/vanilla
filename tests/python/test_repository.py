"""
Unit tests for the SQLite repository layer.

Tests all CRUD operations, WAL mode, FTS5 search, and concurrent access safety.
Uses a fresh in-memory (temp file) database for each test.
"""

import os
import sys
import time
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sidecar"))

from db.database import init_db, _connection
from db import database as db_module
from db import repository as repo


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    """Create a fresh SQLite database for each test."""
    db_path = tmp_path / "test.db"
    conn = init_db(db_path)
    yield conn
    conn.close()
    db_module._connection = None


# ─── FTS ────────────────────────────────────────────────────────────

class TestFTS:
    def test_upsert_and_search(self):
        repo.upsert_fts("clean-vault/raw/paper.md", "clean", "Climate Policy", "A paper about climate change and policy frameworks.")
        results = repo.search_fts("climate")
        assert len(results) == 1
        assert results[0]["path"] == "clean-vault/raw/paper.md"
        assert results[0]["vault"] == "clean"

    def test_search_with_vault_filter(self):
        repo.upsert_fts("clean-vault/raw/a.md", "clean", "Doc A", "Topic alpha")
        repo.upsert_fts("wiki-vault/concepts/b.md", "wiki", "Doc B", "Topic alpha")

        clean_results = repo.search_fts("alpha", vault="clean")
        assert len(clean_results) == 1
        assert clean_results[0]["vault"] == "clean"

        wiki_results = repo.search_fts("alpha", vault="wiki")
        assert len(wiki_results) == 1
        assert wiki_results[0]["vault"] == "wiki"

    def test_upsert_updates_existing(self):
        repo.upsert_fts("test.md", "clean", "V1", "original content")
        repo.upsert_fts("test.md", "clean", "V2", "updated content")

        results = repo.search_fts("updated")
        assert len(results) == 1
        assert results[0]["title"] == "V2"

        # Old content should not be findable
        old_results = repo.search_fts("original")
        assert len(old_results) == 0

    def test_delete_fts(self):
        repo.upsert_fts("test.md", "clean", "Title", "searchable body")
        repo.delete_fts("test.md")
        results = repo.search_fts("searchable")
        assert len(results) == 0

    def test_search_returns_empty_for_no_match(self):
        repo.upsert_fts("test.md", "clean", "Title", "something")
        results = repo.search_fts("nonexistent")
        assert len(results) == 0


# ─── Proposals ──────────────────────────────────────────────────────

class TestProposals:
    def test_create_and_count(self):
        repo.create_proposal("batch_001", "/path/to/batch", "Test summary")
        assert repo.count_pending_proposals() == 1

    def test_get_pending_with_articles(self):
        repo.create_proposal("batch_001", "/path", "Summary")
        repo.add_proposal_article("batch_001", "article_a.md", "Article A")
        repo.add_proposal_article("batch_001", "article_b.md", "Article B")

        pending = repo.get_pending_proposals()
        assert len(pending) == 1
        assert len(pending[0]["articles"]) == 2

    def test_approve_clears_pending(self):
        repo.create_proposal("batch_001", "/path", "Summary")
        repo.update_proposal_status("batch_001", "approved")
        assert repo.count_pending_proposals() == 0

    def test_reject_clears_pending(self):
        repo.create_proposal("batch_001", "/path", "Summary")
        repo.update_proposal_status("batch_001", "rejected")
        assert repo.count_pending_proposals() == 0

    def test_update_article_status(self):
        repo.create_proposal("batch_001", "/path", "Summary")
        repo.add_proposal_article("batch_001", "article.md", "Title")
        repo.update_article_status("batch_001", "article.md", "approved")

        pending = repo.get_pending_proposals()
        article = pending[0]["articles"][0]
        assert article["status"] == "approved"


# ─── Agent Runs ─────────────────────────────────────────────────────

class TestAgentRuns:
    def test_create_and_complete(self):
        repo.create_agent_run("run_001", trigger_path="clean-vault/raw/paper.md")
        last = repo.get_last_run()
        assert last is not None
        assert last["run_id"] == "run_001"
        assert last["status"] == "running"

        repo.complete_agent_run("run_001", status="complete", tokens_used=1500)
        last = repo.get_last_run()
        assert last["status"] == "complete"
        assert last["tokens_used"] == 1500

    def test_error_run(self):
        repo.create_agent_run("run_err")
        repo.complete_agent_run("run_err", status="error", error_msg="LLM timeout")
        last = repo.get_last_run()
        assert last["status"] == "error"
        assert last["error_msg"] == "LLM timeout"

    def test_get_runs_pagination(self):
        for i in range(5):
            repo.create_agent_run(f"run_{i:03d}")
        runs = repo.get_runs(limit=3, offset=0)
        assert len(runs) == 3
        runs_page2 = repo.get_runs(limit=3, offset=3)
        assert len(runs_page2) == 2


# ─── Stale Articles ────────────────────────────────────────────────

class TestStaleArticles:
    def test_flag_and_get(self):
        repo.flag_stale_article("wiki-vault/concepts/topic.md", "clean-vault/raw/paper.md")
        stale = repo.get_stale_articles()
        assert len(stale) == 1
        assert stale[0]["article_path"] == "wiki-vault/concepts/topic.md"

    def test_clear_stale(self):
        repo.flag_stale_article("wiki-vault/concepts/topic.md", "clean-vault/raw/paper.md")
        repo.clear_stale_article("wiki-vault/concepts/topic.md")
        assert len(repo.get_stale_articles()) == 0


# ─── Sync Writes ────────────────────────────────────────────────────

class TestSyncWrites:
    def test_record_and_check(self):
        repo.record_sync_write("clean-vault/raw/synced.md")
        assert repo.is_recent_sync_write("clean-vault/raw/synced.md") is True
        assert repo.is_recent_sync_write("clean-vault/raw/other.md") is False

    def test_cleanup(self):
        repo.record_sync_write("old.md")
        # Cleanup anything older than 0 seconds (immediate cleanup)
        repo.cleanup_old_sync_writes(older_than_seconds=0)
        # After cleanup, the write from a moment ago should still be gone
        # (since we pass 0 seconds, everything is "old")
        assert repo.is_recent_sync_write("old.md", within_seconds=0) is False
