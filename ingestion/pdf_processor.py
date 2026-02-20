"""
ingestion/pdf_processor.py
PyMuPDF-based PDF → chunked text with metadata.
"""
from __future__ import annotations

import logging
from pathlib import Path

import fitz  # PyMuPDF
from langchain.text_splitter import RecursiveCharacterTextSplitter

log = logging.getLogger(__name__)


class PDFProcessor:
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def process(self, pdf_path: str) -> list[dict]:
        path = Path(pdf_path)
        doc  = fitz.open(str(path))
        chunks = []
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            if not text:
                continue
            for chunk_text in self.splitter.split_text(text):
                chunks.append({
                    "text": chunk_text,
                    "metadata": {
                        "source": path.name,
                        "page":   page_num,
                        "type":   "pdf",
                    },
                })
        log.info("PDF %s → %d chunks across %d pages", path.name, len(chunks), len(doc))
        doc.close()
        return chunks
