"""
ingestion/embedder.py
Embedding via nomic-embed-text running in Ollama.
Batch-friendly: embeds lists of chunks efficiently.
"""
from __future__ import annotations

import logging

import httpx

from services.app.core.config import get_settings

log = logging.getLogger(__name__)
cfg = get_settings()

EMBED_ENDPOINT = "/api/embeddings"


class Embedder:
    def __init__(self):
        self.base_url = cfg.ollama_base_url.rstrip("/")
        self.model    = cfg.ollama_embed_model

    def embed_text(self, text: str) -> list[float]:
        return self._call(text)

    def embed_chunks(self, chunks: list[dict]) -> list[list[float]]:
        return [self._call(c["text"]) for c in chunks]

    def _call(self, text: str) -> list[float]:
        payload = {"model": self.model, "prompt": text}
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(f"{self.base_url}{EMBED_ENDPOINT}", json=payload)
                resp.raise_for_status()
                return resp.json()["embedding"]
        except Exception as exc:
            log.error("Embedding failed: %s", exc)
            # Return zero vector on failure — will score low in retrieval
            return [0.0] * 768
