"""
services/agents/rag_agent.py
Hybrid retrieval: ChromaDB dense search + BM25 keyword search,
fused and reranked by ms-marco-MiniLM cross-encoder.
"""
from __future__ import annotations

import logging
from typing import Optional

from ingestion.chroma_client import ChromaClient
from ingestion.embedder import Embedder
from services.app.core.config import get_settings

log = logging.getLogger(__name__)
cfg = get_settings()

# Lazy-loaded to avoid heavy import at module level
_reranker = None


def _get_reranker():
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", max_length=512)
        log.info("Cross-encoder reranker loaded.")
    return _reranker


class RAGAgent:
    def __init__(self):
        self.chroma   = ChromaClient(persist_dir=cfg.chroma_persist_dir)
        self.embedder = Embedder()

    def retrieve(self, query: str, session_id: Optional[str] = None) -> list[dict]:
        """
        Returns top-N reranked chunks relevant to `query`.
        Each chunk: {text, source, page, score}
        """
        top_k = cfg.top_k_results * 2   # over-retrieve before reranking

        # ── Dense retrieval (ChromaDB) ─────────────────────────────────────────
        query_embed = self.embedder.embed_text(query)
        dense_results = self.chroma.query(
            embedding=query_embed,
            session_id=session_id,
            n_results=top_k,
        )

        # ── Sparse retrieval (BM25) ────────────────────────────────────────────
        bm25_results = self._bm25_retrieve(query, session_id, top_k)

        # ── Fuse results (deduplicate by text hash) ────────────────────────────
        seen   = set()
        merged = []
        for chunk in dense_results + bm25_results:
            key = chunk["text"][:80]
            if key not in seen:
                seen.add(key)
                merged.append(chunk)

        if not merged:
            log.warning("No chunks retrieved for query: %s", query[:60])
            return []

        # ── Rerank ────────────────────────────────────────────────────────────
        reranker = _get_reranker()
        pairs    = [(query, c["text"]) for c in merged]
        scores   = reranker.predict(pairs)

        for chunk, score in zip(merged, scores):
            chunk["score"] = float(score)

        merged.sort(key=lambda c: c["score"], reverse=True)
        top = merged[: cfg.rerank_top_n]
        log.info("Returning %d reranked chunks (top score %.3f)", len(top), top[0]["score"] if top else 0)
        return top

    # ── BM25 ─────────────────────────────────────────────────────────────────
    def _bm25_retrieve(self, query: str, session_id: Optional[str], top_k: int) -> list[dict]:
        try:
            from rank_bm25 import BM25Okapi
            all_chunks = self.chroma.get_all(session_id=session_id)
            if not all_chunks:
                return []
            tokenised_corpus = [c["text"].lower().split() for c in all_chunks]
            bm25 = BM25Okapi(tokenised_corpus)
            scores = bm25.get_scores(query.lower().split())
            ranked = sorted(zip(all_chunks, scores), key=lambda x: x[1], reverse=True)
            return [c for c, s in ranked[:top_k] if s > 0]
        except Exception as exc:
            log.warning("BM25 retrieval failed: %s", exc)
            return []
