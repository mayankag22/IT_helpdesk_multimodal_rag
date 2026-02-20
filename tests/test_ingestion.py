"""
tests/test_ingestion.py
Tests for PDF processing, embedding, and ChromaDB upsert/query.
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPDFProcessor:
    def test_process_sample_pdf(self, tmp_path):
        """Create a minimal PDF and verify chunking."""
        pytest.importorskip("fitz")
        import fitz
        from ingestion.pdf_processor import PDFProcessor

        pdf_path = tmp_path / "test.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "This is a test document. " * 50)
        doc.save(str(pdf_path))
        doc.close()

        processor = PDFProcessor(chunk_size=100, chunk_overlap=10)
        chunks = processor.process(str(pdf_path))

        assert len(chunks) > 0
        for c in chunks:
            assert "text" in c
            assert c["metadata"]["source"] == "test.pdf"
            assert c["metadata"]["type"] == "pdf"


class TestChromaClient:
    def test_upsert_and_query(self, tmp_path):
        from ingestion.chroma_client import ChromaClient

        client = ChromaClient(persist_dir=str(tmp_path / "chroma"))
        chunks = [
            {"text": "PCIe link failure on slot 2", "metadata": {"source": "manual.pdf", "page": 1, "type": "pdf"}},
            {"text": "Disk full on volume /data",   "metadata": {"source": "logs.txt",   "page": 0, "type": "text"}},
        ]
        embeddings = [[0.1] * 768, [0.9] * 768]

        client.upsert(chunks, embeddings, session_id="test-session")
        results = client.query(embedding=[0.1] * 768, session_id="test-session", n_results=1)

        assert len(results) >= 1
        assert "text" in results[0]

    def test_doc_exists(self, tmp_path):
        from ingestion.chroma_client import ChromaClient

        client = ChromaClient(persist_dir=str(tmp_path / "chroma2"))
        chunks = [{"text": "test", "metadata": {"source": "f.pdf", "page": 1, "type": "pdf", "file_hash": "abc123"}}]
        client.upsert(chunks, [[0.5] * 768], session_id="s1")

        assert client.doc_exists("abc123", "s1") is True
        assert client.doc_exists("nothere", "s1") is False
