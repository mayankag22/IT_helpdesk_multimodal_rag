"""
services/supervisor/state.py
Shared state TypedDict that flows through every LangGraph node.
"""
from __future__ import annotations
from typing import Annotated, Any, Optional
from typing_extensions import TypedDict
import operator


class AgentState(TypedDict):
    # ── Input ────────────────────────────────────────────────────────────────
    session_id: str
    user_query: str
    uploaded_files: list[str]          # file paths inside the container

    # ── Extracted signals ────────────────────────────────────────────────────
    error_codes: list[str]             # e.g. ["0x4F", "ERR_LINK_DOWN"]
    intent: str                        # "troubleshoot" | "ingest" | "general"

    # ── Resolution outputs ────────────────────────────────────────────────────
    mcp_result: Optional[dict]         # raw MCP tool response
    rag_chunks: list[dict]             # retrieved + reranked chunks
    web_results: list[dict]            # DuckDuckGo / Tavily results
    vision_context: Optional[str]      # LLaVA image description

    # ── Generation ───────────────────────────────────────────────────────────
    generated_answer: str
    source_tier: str                   # "mcp" | "rag" | "web"
    sources: list[dict]                # [{text, page, file, score}]

    # ── Quality gate ─────────────────────────────────────────────────────────
    confidence_score: float            # 0.0 – 1.0
    confidence_label: str              # "HIGH" | "MEDIUM" | "LOW"
    critic_explanation: str

    # ── Conversation memory ───────────────────────────────────────────────────
    # Annotated with operator.add so LangGraph appends new turns automatically
    chat_history: Annotated[list[dict], operator.add]

    # ── Internal control ─────────────────────────────────────────────────────
    retry_count: int
    error: Optional[str]               # set if a node raises an exception
