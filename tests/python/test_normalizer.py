"""
Unit tests for the ingestion normalizer — routing, slugification,
title extraction, and markdown ingestion.

PDF and URL ingestion are tested via mocks since they depend on
external services (Marker, Firecrawl).
"""

import os
import sys
import time
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sidecar"))

from services.ingestion.normalizer import (
    detect_source_type,
    slugify,
    extract_title_from_markdown,
    ingest_markdown,
    ingest_pdf,
    ingest_url,
    IngestResult,
)


# ─── detect_source_type ────────────────────────────────────────────

class TestDetectSourceType:
    def test_pdf(self):
        assert detect_source_type("paper.pdf") == "pdf"

    def test_pdf_uppercase(self):
        assert detect_source_type("Paper.PDF") == "pdf"

    def test_markdown(self):
        assert detect_source_type("notes.md") == "md"

    def test_markdown_alt_ext(self):
        assert detect_source_type("readme.markdown") == "md"

    def test_txt(self):
        assert detect_source_type("data.txt") == "md"

    def test_unknown(self):
        assert detect_source_type("image.png") == "unknown"

    def test_no_extension(self):
        assert detect_source_type("Makefile") == "unknown"

    def test_full_path(self):
        assert detect_source_type("/home/user/docs/paper.pdf") == "pdf"

    def test_windows_path(self):
        assert detect_source_type("C:\\Users\\docs\\notes.md") == "md"


# ─── slugify ───────────────────────────────────────────────────────

class TestSlugify:
    def test_basic(self):
        assert slugify("Hello World") == "hello-world"

    def test_special_chars(self):
        assert slugify("A Paper: With (Special) Chars!") == "a-paper-with-special-chars"

    def test_already_slug(self):
        assert slugify("my-slug") == "my-slug"

    def test_long_text_truncated(self):
        long_title = "A" * 200
        result = slugify(long_title)
        assert len(result) <= 80

    def test_unicode(self):
        result = slugify("Café Résumé")
        assert "caf" in result

    def test_empty(self):
        assert slugify("") == ""

    def test_whitespace(self):
        assert slugify("  multiple   spaces  ") == "multiple-spaces"


# ─── extract_title_from_markdown ───────────────────────────────────

class TestExtractTitle:
    def test_h1_heading(self):
        assert extract_title_from_markdown("# My Title\n\nContent here") == "My Title"

    def test_no_heading_uses_first_line(self):
        result = extract_title_from_markdown("Just some text\nMore text")
        assert result == "Just some text"

    def test_frontmatter_skipped(self):
        md = "---\ntitle: meta\n---\n# Actual Title\n\nBody"
        assert extract_title_from_markdown(md) == "Actual Title"

    def test_empty_content(self):
        assert extract_title_from_markdown("") == "Untitled"

    def test_only_frontmatter(self):
        md = "---\ntitle: meta\n---\n"
        assert extract_title_from_markdown(md) == "Untitled"

    def test_long_first_line_truncated(self):
        long_line = "A" * 200
        result = extract_title_from_markdown(long_line)
        assert len(result) <= 100


# ─── ingest_markdown ──────────────────────────────────────────────

class TestIngestMarkdown:
    @pytest.fixture
    def vault_dir(self, tmp_path):
        """Create a temporary vault structure."""
        clean = tmp_path / "clean-vault"
        raw = clean / "raw"
        raw.mkdir(parents=True)
        return tmp_path

    @pytest.mark.asyncio
    async def test_ingest_new_file(self, vault_dir):
        # Create a source markdown file outside the vault
        source = vault_dir / "external" / "notes.md"
        source.parent.mkdir(parents=True)
        source.write_text("# My Notes\n\nSome content here.")

        clean_path = str(vault_dir / "clean-vault")
        result = await ingest_markdown(str(source), clean_path)

        assert result.success
        assert result.source_type == "md"
        assert result.title == "My Notes"
        assert "Some content here" in result.body
        assert "clean-vault/raw/" in result.output_path

        # Verify file was copied
        output_file = vault_dir / result.output_path
        assert output_file.exists()

    @pytest.mark.asyncio
    async def test_ingest_missing_file(self, vault_dir):
        clean_path = str(vault_dir / "clean-vault")
        result = await ingest_markdown("/nonexistent/file.md", clean_path)

        assert not result.success
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_dedup_filename(self, vault_dir):
        # Create a file already in raw/
        raw = vault_dir / "clean-vault" / "raw"
        (raw / "notes.md").write_text("existing content")

        # Create a different source file with the same name
        source = vault_dir / "external" / "notes.md"
        source.parent.mkdir(parents=True)
        source.write_text("# New Notes\n\nDifferent content.")

        clean_path = str(vault_dir / "clean-vault")
        result = await ingest_markdown(str(source), clean_path)

        assert result.success
        # Should have a deduped name (with timestamp)
        assert "notes" in result.output_path

    @pytest.mark.asyncio
    async def test_creates_raw_dir_if_missing(self, tmp_path):
        clean = tmp_path / "clean-vault"
        clean.mkdir()
        # raw/ does NOT exist yet

        source = tmp_path / "test.md"
        source.write_text("# Test\n\nBody.")

        result = await ingest_markdown(str(source), str(clean))
        assert result.success
        assert (clean / "raw").exists()


# ─── ingest_pdf ───────────────────────────────────────────────────

class TestIngestPdf:
    @pytest.fixture
    def vault_dir(self, tmp_path):
        clean = tmp_path / "clean-vault"
        (clean / "raw").mkdir(parents=True)
        return tmp_path

    @pytest.mark.asyncio
    async def test_missing_pdf(self, vault_dir):
        clean_path = str(vault_dir / "clean-vault")
        result = await ingest_pdf("/nonexistent/paper.pdf", clean_path)
        assert not result.success
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_pdf_marker_not_installed(self, vault_dir):
        # Create a dummy PDF file
        pdf = vault_dir / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4 dummy")

        clean_path = str(vault_dir / "clean-vault")

        with patch.dict("sys.modules", {"services.ingestion.marker_service": None}):
            # Force ImportError by making the import fail
            with patch(
                "services.ingestion.normalizer.ingest_pdf",
                wraps=ingest_pdf,
            ):
                # The actual function should handle ImportError gracefully
                result = await ingest_pdf(str(pdf), clean_path)
                # Marker might or might not be installed — either way should not crash
                assert isinstance(result, IngestResult)

    @pytest.mark.asyncio
    async def test_pdf_with_mocked_marker(self, vault_dir):
        """Test PDF ingestion with a mocked Marker conversion."""
        pdf = vault_dir / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4 dummy")
        clean_path = str(vault_dir / "clean-vault")
        expected_output = vault_dir / "clean-vault" / "raw" / "paper.md"

        async def mock_convert(src, dst):
            Path(dst).write_text("# Converted Paper\n\nContent from PDF.")
            return dst

        mock_module = MagicMock()
        mock_module.convert_pdf_marker = mock_convert

        with patch.dict("sys.modules", {"services.ingestion.marker_service": mock_module}):
            # Re-import to pick up the mock module
            import importlib
            import services.ingestion.normalizer as norm_mod
            importlib.reload(norm_mod)

            result = await norm_mod.ingest_pdf(str(pdf), clean_path)

            assert result.success
            assert result.source_type == "pdf"
            assert result.title == "Converted Paper"
            assert "Content from PDF" in result.body
            assert expected_output.exists()


# ─── ingest_url ───────────────────────────────────────────────────

class TestIngestUrl:
    @pytest.fixture
    def vault_dir(self, tmp_path):
        clean = tmp_path / "clean-vault"
        (clean / "raw").mkdir(parents=True)
        return tmp_path

    @pytest.mark.asyncio
    async def test_url_ingest_firecrawl_not_installed(self, vault_dir):
        """URL ingestion gracefully handles missing firecrawl."""
        clean_path = str(vault_dir / "clean-vault")

        # Re-import fresh to avoid cross-test reload issues
        import importlib
        import services.ingestion.normalizer as norm_mod
        importlib.reload(norm_mod)

        with patch.dict("sys.modules", {"services.ingestion.firecrawl_service": None}):
            result = await norm_mod.ingest_url("https://example.com", clean_path)
            assert result.success is False
            assert result.source_type == "url"
            assert "not installed" in (result.error or "").lower()
