"""
Integration tests for the FastAPI sidecar endpoints.

Uses FastAPI's TestClient (httpx-based) to test the actual HTTP contract
without starting a real server.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "sidecar"))

from main import app
from db.database import init_db
from db import database as db_module


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    """Initialize a fresh DB for each test."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    yield
    db_module._connection.close()
    db_module._connection = None


@pytest.fixture
def client():
    return TestClient(app)


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


class TestVaultStructureEndpoint:
    def test_returns_uninitialized(self, client):
        response = client.get("/vault/structure")
        assert response.status_code == 200
        data = response.json()
        # Config hasn't been set up, so should reflect default state
        assert "initialized" in data
        assert "clean_vault_path" in data
        assert "wiki_vault_path" in data
