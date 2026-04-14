"""
Unit tests for the ingestion job queue — job lifecycle,
status tracking, active job filtering, and cleanup.
"""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sidecar"))

from services.ingestion.job_queue import IngestJobQueue, IngestJob, JobStatus


class TestIngestJobQueue:
    @pytest.fixture
    def queue(self):
        """Fresh queue for each test."""
        return IngestJobQueue()

    def test_create_job(self, queue):
        job = queue.create_job(source_type="pdf", source_path="/path/to/paper.pdf")
        assert job.job_id.startswith("ingest_")
        assert job.source_type == "pdf"
        assert job.source_path == "/path/to/paper.pdf"
        assert job.status == JobStatus.PENDING
        assert job.progress == 0.0

    def test_create_url_job(self, queue):
        job = queue.create_job(source_type="url", source_url="https://example.com")
        assert job.source_url == "https://example.com"
        assert job.source_path is None

    def test_get_job(self, queue):
        job = queue.create_job(source_type="md", source_path="/notes.md")
        retrieved = queue.get_job(job.job_id)
        assert retrieved is job

    def test_get_nonexistent_job(self, queue):
        assert queue.get_job("nonexistent_id") is None

    def test_update_status(self, queue):
        job = queue.create_job(source_type="pdf", source_path="/paper.pdf")
        queue.update_job(job.job_id, status=JobStatus.PROCESSING, progress=0.5)

        updated = queue.get_job(job.job_id)
        assert updated.status == JobStatus.PROCESSING
        assert updated.progress == 0.5

    def test_update_complete(self, queue):
        job = queue.create_job(source_type="md", source_path="/notes.md")
        queue.update_job(
            job.job_id,
            status=JobStatus.COMPLETE,
            progress=1.0,
            output_path="clean-vault/raw/notes.md",
        )

        updated = queue.get_job(job.job_id)
        assert updated.status == JobStatus.COMPLETE
        assert updated.output_path == "clean-vault/raw/notes.md"
        assert updated.completed_at is not None

    def test_update_error(self, queue):
        job = queue.create_job(source_type="pdf", source_path="/bad.pdf")
        queue.update_job(
            job.job_id,
            status=JobStatus.ERROR,
            error="Conversion failed",
        )

        updated = queue.get_job(job.job_id)
        assert updated.status == JobStatus.ERROR
        assert updated.error == "Conversion failed"
        assert updated.completed_at is not None

    def test_update_nonexistent_job_noop(self, queue):
        """Updating a nonexistent job should not raise."""
        queue.update_job("fake_id", status=JobStatus.COMPLETE)
        # No exception raised

    def test_get_active_jobs(self, queue):
        j1 = queue.create_job(source_type="pdf", source_path="/a.pdf")
        j2 = queue.create_job(source_type="md", source_path="/b.md")
        j3 = queue.create_job(source_type="url", source_url="https://example.com")

        # Complete one
        queue.update_job(j2.job_id, status=JobStatus.COMPLETE, progress=1.0)

        active = queue.get_active_jobs()
        active_ids = [j["job_id"] for j in active]
        assert j1.job_id in active_ids
        assert j3.job_id in active_ids
        assert j2.job_id not in active_ids

    def test_get_active_jobs_empty(self, queue):
        assert queue.get_active_jobs() == []

    def test_to_dict(self, queue):
        job = queue.create_job(source_type="pdf", source_path="/paper.pdf")
        d = job.to_dict()
        assert d["job_id"] == job.job_id
        assert d["status"] == "pending"
        assert d["progress"] == 0.0
        assert d["source_type"] == "pdf"
        assert d["output_path"] is None
        assert d["error"] is None

    def test_cleanup_old_jobs(self, queue):
        j1 = queue.create_job(source_type="md", source_path="/old.md")
        queue.update_job(j1.job_id, status=JobStatus.COMPLETE, progress=1.0)

        # Hack: backdate the completed_at
        queue.get_job(j1.job_id).completed_at = time.time() - 7200  # 2 hours ago

        j2 = queue.create_job(source_type="md", source_path="/recent.md")
        queue.update_job(j2.job_id, status=JobStatus.COMPLETE, progress=1.0)

        removed = queue.cleanup_old_jobs(max_age_seconds=3600)
        assert removed == 1
        assert queue.get_job(j1.job_id) is None
        assert queue.get_job(j2.job_id) is not None

    def test_cleanup_does_not_remove_active(self, queue):
        j1 = queue.create_job(source_type="pdf", source_path="/active.pdf")
        queue.update_job(j1.job_id, status=JobStatus.PROCESSING, progress=0.3)

        removed = queue.cleanup_old_jobs(max_age_seconds=0)
        assert removed == 0
        assert queue.get_job(j1.job_id) is not None

    def test_unique_job_ids(self, queue):
        ids = set()
        for _ in range(100):
            job = queue.create_job(source_type="md", source_path="/test.md")
            ids.add(job.job_id)
        assert len(ids) == 100


class TestJobStatus:
    def test_enum_values(self):
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.PROCESSING.value == "processing"
        assert JobStatus.COMPLETE.value == "complete"
        assert JobStatus.ERROR.value == "error"

    def test_string_comparison(self):
        """JobStatus inherits from str, so comparisons work."""
        assert JobStatus.PENDING == "pending"
        assert JobStatus.COMPLETE == "complete"
