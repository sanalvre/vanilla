"""
Integration tests for the FastAPI sidecar endpoints.

Uses FastAPI's TestClient (httpx-based) to test the actual HTTP contract
without starting a real server. Covers Phase 1 + Phase 2 endpoints.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "sidecar"))

from main import app, config as app_config
from db.database import init_db
from db import database as db_module
from db import repository as repo


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    """Initialize a fresh DB for each test."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    yield
    if db_module._connection:
        db_module._connection.close()
    db_module._connection = None


@pytest.fixture
def client():
    return TestClient(app)


# ─── System Endpoints ───────────────────────────────────────────────

class TestHealthEndpoint:
    def test_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestStatusEndpoint:
    def test_returns_idle(self, client):
        response = client.get("/status")
        assert response.status_code == 200
        data = response.json()
        assert data["agent_status"] == "idle"
        assert data["pending_proposals"] == 0
        assert data["current_phase"] is None
        assert data["last_run"] is None

    def test_reflects_pending_proposals(self, client):
        repo.create_proposal("batch_001", "/path", "Test batch")
        response = client.get("/status")
        assert response.json()["pending_proposals"] == 1

    def test_reflects_last_run(self, client):
        repo.create_agent_run("run_001")
        repo.complete_agent_run("run_001", status="complete", tokens_used=500)
        response = client.get("/status")
        data = response.json()
        assert data["last_run"] is not None
        assert data["last_run"]["id"] == "run_001"
        assert data["last_run"]["tokens_used"] == 500


# ─── Vault Endpoints ────────────────────────────────────────────────

class TestVaultStructureEndpoint:
    def test_returns_uninitialized(self, client):
        response = client.get("/vault/structure")
        assert response.status_code == 200
        data = response.json()
        assert "initialized" in data
        assert "clean_vault_path" in data
        assert "wiki_vault_path" in data
        assert "warnings" in data


class TestVaultCreateEndpoint:
    def test_creates_vault(self, client, tmp_path):
        response = client.post("/vault/create", json={
            "base_path": str(tmp_path),
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "clean-vault" in data["clean_vault_path"]
        assert "wiki-vault" in data["wiki_vault_path"]

        # Verify directories exist
        assert (tmp_path / "clean-vault" / "raw").is_dir()
        assert (tmp_path / "wiki-vault" / "concepts").is_dir()
        assert (tmp_path / "wiki-vault" / "AGENTS.md").is_file()

    def test_creates_with_custom_ontology(self, client, tmp_path):
        response = client.post("/vault/create", json={
            "base_path": str(tmp_path),
            "ontology_content": "# Custom Ontology\nMy domain.",
            "agents_content": "# Custom AGENTS\nMy rules.",
        })
        assert response.status_code == 200
        assert (tmp_path / "wiki-vault" / "ontology.md").read_text() == "# Custom Ontology\nMy domain."


# ─── File Event Endpoints ───────────────────────────────────────────

class TestFileEventEndpoint:
    def test_queues_event(self, client):
        response = client.post("/internal/file-event", json={
            "path": "clean-vault/raw/test.md",
            "event_type": "create",
            "timestamp": 1713024000,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["queued"] is True


class TestAgentRunNow:
    def test_dispatches_pending(self, client):
        response = client.post("/agent/run-now")
        assert response.status_code == 200
        data = response.json()
        assert "dispatched" in data


# ─── Graph Endpoints ────────────────────────────────────────────────

class TestGraphEndpoint:
    def test_returns_empty_graph(self, client):
        response = client.get("/wiki/graph")
        assert response.status_code == 200
        data = response.json()
        assert data["nodes"] == []
        assert data["edges"] == []

    def test_returns_graph_after_vault_creation(self, client, tmp_path):
        # Create vault first
        client.post("/vault/create", json={"base_path": str(tmp_path)})
        response = client.get("/wiki/graph")
        assert response.status_code == 200
        data = response.json()
        assert "source_map" in data


class TestStaleEndpoint:
    def test_returns_empty_initially(self, client):
        response = client.get("/wiki/stale")
        assert response.status_code == 200
        assert response.json()["stale_articles"] == []

    def test_returns_flagged_articles(self, client):
        repo.flag_stale_article("wiki-vault/concepts/topic.md", "clean-vault/raw/paper.md")
        response = client.get("/wiki/stale")
        assert len(response.json()["stale_articles"]) == 1


# ─── Proposals Endpoint ─────────────────────────────────────────────

class TestProposalsEndpoint:
    def test_returns_empty_initially(self, client):
        response = client.get("/proposals")
        assert response.status_code == 200
        assert response.json()["batches"] == []

    def test_returns_pending_proposals(self, client):
        repo.create_proposal("batch_001", "/path", "Test batch")
        repo.add_proposal_article("batch_001", "article.md", "Test Article")
        response = client.get("/proposals")
        data = response.json()
        assert len(data["batches"]) == 1
        assert len(data["batches"][0]["articles"]) == 1


# ─── Search Endpoint ────────────────────────────────────────────────

class TestSearchEndpoint:
    def test_empty_query(self, client):
        response = client.get("/search?q=")
        assert response.status_code == 200
        assert response.json()["results"] == []

    def test_search_returns_results(self, client):
        repo.upsert_fts("clean-vault/raw/paper.md", "clean", "Climate Paper", "A paper about climate change.")
        response = client.get("/search?q=climate")
        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["vault"] == "clean"

    def test_search_with_vault_filter(self, client):
        repo.upsert_fts("clean-vault/raw/a.md", "clean", "Doc A", "Alpha topic")
        repo.upsert_fts("wiki-vault/concepts/b.md", "wiki", "Doc B", "Alpha topic")

        response = client.get("/search?q=alpha&vault=clean")
        assert len(response.json()["results"]) == 1

        response = client.get("/search?q=alpha&vault=wiki")
        assert len(response.json()["results"]) == 1


# ─── Runs Endpoint ──────────────────────────────────────────────────

class TestRunsEndpoint:
    def test_returns_empty(self, client):
        response = client.get("/runs")
        assert response.status_code == 200
        assert response.json()["runs"] == []

    def test_returns_run_history(self, client):
        repo.create_agent_run("run_001")
        response = client.get("/runs")
        runs = response.json()["runs"]
        assert len(runs) == 1
        assert runs[0]["run_id"] == "run_001"

    def test_pagination(self, client):
        for i in range(5):
            repo.create_agent_run(f"run_{i:03d}")
        response = client.get("/runs?limit=2&offset=0")
        assert len(response.json()["runs"]) == 2
        response = client.get("/runs?limit=2&offset=4")
        assert len(response.json()["runs"]) == 1


# ─── System Capabilities Endpoint ──────────────────────────────────

class TestCapabilitiesEndpoint:
    def test_returns_gpu_info(self, client):
        response = client.get("/system/capabilities")
        assert response.status_code == 200
        data = response.json()
        assert "gpu" in data
        assert "gpu_type" in data
        assert data["gpu_type"] in ("cuda", "mps", "none")
        assert "python_version" in data


# ─── Ingestion Endpoints ──────────────────────────────────────────

class TestIngestFileEndpoint:
    def test_requires_vault_initialized(self, client):
        """Ingest should fail if vault not initialized."""
        # Ensure vault is not initialized
        app_config.clean_vault_path = None
        response = client.post("/ingest/file?file_path=/test.pdf")
        assert response.status_code == 400
        assert "not initialized" in response.json()["detail"].lower()

    def test_rejects_unknown_file_type(self, client, tmp_path):
        app_config.clean_vault_path = str(tmp_path / "clean-vault")
        response = client.post("/ingest/file?file_path=/test.png")
        assert response.status_code == 400
        assert "unsupported" in response.json()["detail"].lower()

    def test_creates_job_for_markdown(self, client, tmp_path):
        app_config.clean_vault_path = str(tmp_path / "clean-vault")
        (tmp_path / "clean-vault" / "raw").mkdir(parents=True)

        md_file = tmp_path / "test.md"
        md_file.write_text("# Test\n\nContent")

        response = client.post(f"/ingest/file?file_path={md_file}")
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["job_id"].startswith("ingest_")

    def test_creates_job_for_pdf(self, client, tmp_path):
        app_config.clean_vault_path = str(tmp_path / "clean-vault")
        (tmp_path / "clean-vault" / "raw").mkdir(parents=True)

        pdf_file = tmp_path / "paper.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 dummy")

        response = client.post(f"/ingest/file?file_path={pdf_file}")
        assert response.status_code == 200
        assert "job_id" in response.json()


class TestIngestUrlEndpoint:
    def test_requires_vault_initialized(self, client):
        app_config.clean_vault_path = None
        response = client.post("/ingest/url", json={"url": "https://example.com"})
        assert response.status_code == 400

    def test_creates_job_for_url(self, client, tmp_path):
        app_config.clean_vault_path = str(tmp_path / "clean-vault")
        (tmp_path / "clean-vault" / "raw").mkdir(parents=True)

        response = client.post("/ingest/url", json={"url": "https://example.com"})
        assert response.status_code == 200
        assert "job_id" in response.json()


class TestIngestStatusEndpoint:
    def test_nonexistent_job(self, client):
        response = client.get("/ingest/status/fake_job_id")
        assert response.status_code == 404

    def test_returns_job_status(self, client, tmp_path):
        # Create a job by calling ingest endpoint
        app_config.clean_vault_path = str(tmp_path / "clean-vault")
        (tmp_path / "clean-vault" / "raw").mkdir(parents=True)

        md_file = tmp_path / "test.md"
        md_file.write_text("# Test")

        create_resp = client.post(f"/ingest/file?file_path={md_file}")
        job_id = create_resp.json()["job_id"]

        # Poll status
        response = client.get(f"/ingest/status/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["source_type"] == "md"
        assert data["status"] in ("pending", "processing", "complete", "error")


class TestIngestActiveEndpoint:
    def test_returns_active_jobs(self, client, tmp_path):
        app_config.clean_vault_path = str(tmp_path / "clean-vault")
        (tmp_path / "clean-vault" / "raw").mkdir(parents=True)

        response = client.get("/ingest/active")
        assert response.status_code == 200
        assert "jobs" in response.json()


# ─── LLM Validation Endpoint ──────────────────────────────────────

class TestLLMValidateEndpoint:
    def test_rejects_missing_key_for_cloud(self, client):
        """Cloud providers need an API key."""
        response = client.post("/llm/validate", json={
            "provider": "openai",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["error"]

    def test_returns_valid_shape(self, client):
        """Response always has valid + error fields."""
        response = client.post("/llm/validate", json={
            "provider": "openai",
            "api_key": "sk-fake",
            "model": "gpt-4o-mini",
        })
        assert response.status_code == 200
        data = response.json()
        assert "valid" in data
        assert "error" in data


# ─── Onboarding Generate Endpoint ─────────────────────────────────

class TestOnboardingGenerateEndpoint:
    def test_rejects_without_required_fields(self, client):
        """Should 422 if required fields missing."""
        response = client.post("/onboarding/generate-ontology", json={})
        assert response.status_code == 422


# ─── Status reflects pipeline state ──────────────────────────────

class TestStatusReflectsPipeline:
    def test_idle_by_default(self, client):
        response = client.get("/status")
        data = response.json()
        assert data["agent_status"] == "idle"
        assert data["current_phase"] is None


# ─── Proposal Approve/Reject Endpoints ────────────────────────────

class TestProposalApproveEndpoint:
    def test_rejects_without_wiki_vault(self, client):
        app_config.wiki_vault_path = None
        response = client.post("/proposals/batch_fake/approve")
        assert response.status_code == 400

    def test_approve_missing_batch(self, client, tmp_path):
        """Approving a batch with no staging dir returns 0 articles."""
        app_config.wiki_vault_path = str(tmp_path / "wiki-vault")
        (tmp_path / "wiki-vault" / "concepts").mkdir(parents=True)

        repo.create_proposal("batch_test", str(tmp_path), "Test batch")
        response = client.post("/proposals/batch_test/approve")
        assert response.status_code == 200
        data = response.json()
        assert data["articles_written"] == 0


class TestProposalRejectEndpoint:
    def test_reject_proposal(self, client):
        repo.create_proposal("batch_rej", "/path", "Reject me")
        response = client.post("/proposals/batch_rej/reject", json={"reason": "not relevant"})
        assert response.status_code == 200
        assert response.json()["status"] == "rejected"


# ─── Proposal Article Preview Endpoint ────────────────────────────

class TestProposalArticleEndpoint:
    def test_returns_404_for_missing(self, client, tmp_path):
        app_config.wiki_vault_path = str(tmp_path / "wiki-vault")
        response = client.get("/proposals/batch_x/article/nofile.md")
        assert response.status_code == 404

    def test_returns_article_content(self, client, tmp_path):
        wiki = tmp_path / "wiki-vault"
        staging = wiki / "staging" / "batch_abc"
        staging.mkdir(parents=True)
        (staging / "test-article.md").write_text("# Test\n\nContent.", encoding="utf-8")

        app_config.wiki_vault_path = str(wiki)
        response = client.get("/proposals/batch_abc/article/test-article.md")
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test-article.md"
        assert "Content." in data["content"]

    def test_rejects_path_traversal(self, client, tmp_path):
        app_config.wiki_vault_path = str(tmp_path / "wiki-vault")
        response = client.get("/proposals/batch_abc/article/..%2Fsecret.md")
        # Should be 400 or 404 — never serve path traversal
        assert response.status_code in (400, 404)
