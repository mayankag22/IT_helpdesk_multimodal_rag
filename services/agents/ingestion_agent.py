"""
services/agents/ingestion_agent.py
Handles PDF, image, and plain-text file ingestion into ChromaDB.
Uses file-hash caching to skip already-processed files.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from ingestion.pdf_processor import PDFProcessor
from ingestion.image_processor import ImageProcessor
from ingestion.embedder import Embedder
from ingestion.chroma_client import ChromaClient
from services.app.core.config import get_settings

log = logging.getLogger(__name__)
cfg = get_settings()

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
PDF_EXTENSIONS   = {".pdf"}
TEXT_EXTENSIONS  = {".txt", ".md", ".rst", ".log"}


class IngestionAgent:
    def __init__(self):
        self.pdf_proc   = PDFProcessor(chunk_size=cfg.chunk_size, chunk_overlap=cfg.chunk_overlap)
        self.img_proc   = ImageProcessor()
        self.embedder   = Embedder()
        self.chroma     = ChromaClient(persist_dir=cfg.chroma_persist_dir)

    # ── Public API ─────────────────────────────────────────────────────────────
    def ingest_file(self, file_path: str, session_id: str) -> dict:
        path = Path(file_path)
        ext  = path.suffix.lower()
        file_hash = self._hash(path)

        # Skip if already indexed
        if self.chroma.doc_exists(file_hash, session_id):
            log.info("Skipping %s — already indexed.", path.name)
            return {"file": path.name, "summary": f"{path.name} already indexed (cached)", "chunks": 0}

        if ext in PDF_EXTENSIONS:
            chunks = self.pdf_proc.process(str(path))
        elif ext in IMAGE_EXTENSIONS:
            chunks = self.img_proc.process(str(path))   # → calls VisionAgent internally
        elif ext in TEXT_EXTENSIONS:
            chunks = self._process_text(path)
        else:
            return {"file": path.name, "summary": f"Unsupported type: {ext}", "chunks": 0}

        # Tag every chunk with hash so we can skip on re-run
        for c in chunks:
            c["metadata"]["file_hash"] = file_hash
            c["metadata"]["session_id"] = session_id

        embeddings = self.embedder.embed_chunks(chunks)
        self.chroma.upsert(chunks, embeddings, session_id)

        log.info("Ingested %d chunks from %s", len(chunks), path.name)
        return {"file": path.name, "summary": f"{len(chunks)} chunks indexed from {path.name}", "chunks": len(chunks)}

    # ── Helpers ────────────────────────────────────────────────────────────────
    @staticmethod
    def _hash(path: Path) -> str:
        h = hashlib.sha256()
        h.update(path.read_bytes())
        return h.hexdigest()[:16]

    @staticmethod
    def _process_text(path: Path) -> list[dict]:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(chunk_size=cfg.chunk_size, chunk_overlap=cfg.chunk_overlap)
        text = path.read_text(errors="replace")
        raw_chunks = splitter.split_text(text)
        return [
            {"text": c, "metadata": {"source": path.name, "page": 0, "type": "text"}}
            for c in raw_chunks
        ]
