"""
ingestion/chroma_client.py
ChromaDB embedded client wrapper with session-namespaced collections.
"""
from __future__ import annotations

import logging
from typing import Optional

import chromadb
from chromadb.config import Settings

log = logging.getLogger(__name__)


class ChromaClient:
    def __init__(self, persist_dir: str = "./vector_store"):
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        log.info("ChromaDB initialised at %s", persist_dir)

    def _collection(self, session_id: str = "default"):
        """Each session gets its own collection (namespace isolation)."""
        name = f"session_{session_id[:32]}" if session_id else "default"
        return self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, chunks: list[dict], embeddings: list[list[float]], session_id: str = "default"):
        col = self._collection(session_id)
        ids        = [f"{session_id}_{i}_{hash(c['text'])}" for i, c in enumerate(chunks)]
        documents  = [c["text"] for c in chunks]
        metadatas  = [c.get("metadata", {}) for c in chunks]
        col.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
        log.info("Upserted %d chunks into collection '%s'", len(chunks), col.name)

    def query(self, embedding: list[float], session_id: str = "default", n_results: int = 5) -> list[dict]:
        col = self._collection(session_id)
        if col.count() == 0:
            return []
        results = col.query(query_embeddings=[embedding], n_results=min(n_results, col.count()))
        chunks = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            chunks.append({
                "text":   doc,
                "source": meta.get("source", "unknown"),
                "page":   meta.get("page"),
                "score":  1 - dist,   # cosine distance → similarity
                "metadata": meta,
            })
        return chunks

    def get_all(self, session_id: str = "default") -> list[dict]:
        """Return all documents in a collection (for BM25 indexing)."""
        col = self._collection(session_id)
        if col.count() == 0:
            return []
        results = col.get()
        chunks = []
        for doc, meta in zip(results["documents"], results["metadatas"]):
            chunks.append({"text": doc, "source": meta.get("source", "?"), "page": meta.get("page"), "metadata": meta})
        return chunks

    def doc_exists(self, file_hash: str, session_id: str = "default") -> bool:
        """Check if a file (by hash) has already been ingested."""
        col = self._collection(session_id)
        results = col.get(where={"file_hash": file_hash})
        return len(results["ids"]) > 0
