"""
services/agents/mcp_agent.py
HTTP client that calls the MCP server tools.
Implements retry-with-backoff for reliability.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

from services.app.core.config import get_settings

log = logging.getLogger(__name__)
cfg = get_settings()

MAX_RETRIES = 3
BACKOFF_BASE = 1.5   # seconds


class MCPAgent:
    def __init__(self):
        self.base_url = cfg.mcp_server_url.rstrip("/")
        self.headers  = {
            "X-API-Key":    cfg.mcp_api_key,
            "Content-Type": "application/json",
        }

    # ── Tool: search_error_code ───────────────────────────────────────────────
    def search_error_code(self, code: str) -> Optional[dict]:
        return self._call("/tools/search_error_code", {"code": code})

    # ── Tool: get_manual_section ──────────────────────────────────────────────
    def get_manual_section(self, section_id: str) -> Optional[dict]:
        return self._call("/tools/get_manual_section", {"section_id": section_id})

    # ── Tool: run_diagnostic ─────────────────────────────────────────────────
    def run_diagnostic(self, snippet: str) -> Optional[dict]:
        return self._call("/tools/run_diagnostic", {"snippet": snippet})

    # ── Internal HTTP caller with retry ──────────────────────────────────────
    def _call(self, endpoint: str, payload: dict) -> Optional[dict]:
        url = f"{self.base_url}{endpoint}"
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                with httpx.Client(timeout=15) as client:
                    resp = client.post(url, json=payload, headers=self.headers)
                    resp.raise_for_status()
                    data = resp.json()
                    if data.get("found"):
                        log.info("MCP %s → found result on attempt %d", endpoint, attempt)
                        return data
                    log.info("MCP %s → not found", endpoint)
                    return None
            except httpx.HTTPStatusError as exc:
                log.warning("MCP HTTP %d on attempt %d: %s", exc.response.status_code, attempt, exc)
            except httpx.RequestError as exc:
                log.warning("MCP connection error on attempt %d: %s", attempt, exc)
            if attempt < MAX_RETRIES:
                time.sleep(BACKOFF_BASE ** attempt)
        log.error("MCP %s failed after %d attempts", endpoint, MAX_RETRIES)
        return None
