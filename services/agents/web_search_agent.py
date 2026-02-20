"""
services/agents/web_search_agent.py
Tertiary fallback: web search via DuckDuckGo (free, no API key) with
optional upgrade to Tavily when TAVILY_API_KEY is set.
"""
from __future__ import annotations

import logging
from typing import Optional

from services.app.core.config import get_settings

log = logging.getLogger(__name__)
cfg = get_settings()

MAX_RESULTS = 5


class WebSearchAgent:
    def search(self, query: str) -> list[dict]:
        """
        Returns list of {title, url, snippet} dicts.
        Uses Tavily if key is set, otherwise DuckDuckGo.
        """
        if cfg.tavily_api_key:
            return self._tavily_search(query)
        return self._ddg_search(query)

    # ── DuckDuckGo (free) ─────────────────────────────────────────────────────
    def _ddg_search(self, query: str) -> list[dict]:
        try:
            from duckduckgo_search import DDGS
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=MAX_RESULTS):
                    results.append({
                        "title":   r.get("title", ""),
                        "url":     r.get("href", ""),
                        "snippet": r.get("body", ""),
                    })
            log.info("DuckDuckGo returned %d results for: %s", len(results), query[:60])
            return results
        except Exception as exc:
            log.error("DuckDuckGo search failed: %s", exc)
            return []

    # ── Tavily (optional, better for technical queries) ───────────────────────
    def _tavily_search(self, query: str) -> list[dict]:
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=cfg.tavily_api_key)
            response = client.search(query=query, max_results=MAX_RESULTS, search_depth="advanced")
            results = []
            for r in response.get("results", []):
                results.append({
                    "title":   r.get("title", ""),
                    "url":     r.get("url", ""),
                    "snippet": r.get("content", ""),
                })
            log.info("Tavily returned %d results.", len(results))
            return results
        except Exception as exc:
            log.error("Tavily search failed: %s — falling back to DDG", exc)
            return self._ddg_search(query)
