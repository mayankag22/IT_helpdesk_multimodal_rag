"""
services/supervisor/nodes.py
One function per LangGraph graph node. Each function receives the full
AgentState, performs its step, and returns a dict of state updates.
"""
from __future__ import annotations

import json
import logging
from typing import Literal

from langchain_ollama import ChatOllama

from services.supervisor.state import AgentState
from services.supervisor.prompts import (
    SUPERVISOR_SYSTEM, SUPERVISOR_USER,
    CRITIC_SYSTEM,
)
from services.app.core.config import get_settings

log = logging.getLogger(__name__)
cfg = get_settings()


# ── Lazy imports to keep startup fast ─────────────────────────────────────────
def _llm():
    return ChatOllama(base_url=cfg.ollama_base_url, model=cfg.ollama_llm_model,
                      temperature=0, max_tokens=1024)


# ─────────────────────────────────────────────────────────────────────────────
# NODE: classify_intent
# ─────────────────────────────────────────────────────────────────────────────
def classify_intent(state: AgentState) -> dict:
    """Ask the LLM to classify intent and extract error codes."""
    llm = _llm()
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in state.get("chat_history", [])[-6:]
    )
    messages = [
        {"role": "system", "content": SUPERVISOR_SYSTEM.format(chat_history=history_text)},
        {"role": "user",   "content": SUPERVISOR_USER.format(
            user_query=state["user_query"],
            uploaded_files=state.get("uploaded_files", []),
        )},
    ]
    raw = llm.invoke(messages).content.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("Supervisor returned non-JSON: %s", raw)
        parsed = {"intent": "troubleshoot", "error_codes": [], "needs_vision": False, "primary_route": "rag"}

    return {
        "intent":      parsed.get("intent", "troubleshoot"),
        "error_codes": parsed.get("error_codes", []),
        "primary_route": parsed.get("primary_route", "rag"),
        "needs_vision":  parsed.get("needs_vision", False),
        "retry_count": 0,
        "source_tier": "",
    }


def route_after_classify(state: AgentState) -> str:
    if state["intent"] == "ingest":
        return "ingest"
    if state.get("needs_vision") and state.get("uploaded_files"):
        return "vision_then"
    return state.get("primary_route", "rag")


# ─────────────────────────────────────────────────────────────────────────────
# NODE: run_ingestion
# ─────────────────────────────────────────────────────────────────────────────
def run_ingestion(state: AgentState) -> dict:
    from services.agents.ingestion_agent import IngestionAgent
    agent = IngestionAgent()
    results = []
    for fp in state.get("uploaded_files", []):
        result = agent.ingest_file(fp, session_id=state["session_id"])
        results.append(result)
    summary = "; ".join(r["summary"] for r in results)
    return {
        "generated_answer": f"✅ Ingestion complete: {summary}",
        "confidence_label": "HIGH",
        "confidence_score": 1.0,
        "critic_explanation": "Ingestion step — no answer quality check needed.",
        "source_tier": "ingestion",
        "sources": [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE: run_vision
# ─────────────────────────────────────────────────────────────────────────────
def run_vision(state: AgentState) -> dict:
    from services.agents.vision_agent import VisionAgent
    agent = VisionAgent()
    image_files = [f for f in state.get("uploaded_files", [])
                   if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp"))]
    if not image_files:
        return {"vision_context": None}
    context_parts = []
    for img_path in image_files:
        ctx = agent.describe_image(img_path)
        context_parts.append(ctx)
    return {"vision_context": "\n\n".join(context_parts)}


def route_after_vision(state: AgentState) -> str:
    return state.get("primary_route", "rag")


# ─────────────────────────────────────────────────────────────────────────────
# NODE: run_mcp_lookup
# ─────────────────────────────────────────────────────────────────────────────
def run_mcp_lookup(state: AgentState) -> dict:
    from services.agents.mcp_agent import MCPAgent
    agent = MCPAgent()
    results = []
    for code in state.get("error_codes", []):
        r = agent.search_error_code(code)
        if r:
            results.append(r)
    if not results:
        return {"mcp_result": None}
    return {
        "mcp_result": results[0] if len(results) == 1 else results,
        "source_tier": "mcp",
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE: run_rag_retrieve
# ─────────────────────────────────────────────────────────────────────────────
def run_rag_retrieve(state: AgentState) -> dict:
    from services.agents.rag_agent import RAGAgent
    agent = RAGAgent()
    query = state["user_query"]
    if state.get("vision_context"):
        query = f"{query}\n\nVisual context: {state['vision_context']}"
    chunks = agent.retrieve(query=query, session_id=state["session_id"])
    return {
        "rag_chunks": chunks,
        "source_tier": "rag",
        "sources": [{"text": c["text"], "page": c.get("page"), "file": c.get("source"), "score": c.get("score")}
                    for c in chunks],
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE: run_web_search
# ─────────────────────────────────────────────────────────────────────────────
def run_web_search(state: AgentState) -> dict:
    from services.agents.web_search_agent import WebSearchAgent
    agent = WebSearchAgent()
    results = agent.search(state["user_query"])
    return {
        "web_results": results,
        "source_tier": "web",
        "sources": [{"text": r["snippet"], "file": r["url"], "score": None} for r in results],
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE: run_generation
# ─────────────────────────────────────────────────────────────────────────────
def run_generation(state: AgentState) -> dict:
    from services.agents import rag_agent, mcp_agent  # noqa: avoid circular at module level
    from langchain_ollama import ChatOllama as _Ollama
    from services.supervisor.prompts import RAG_SYSTEM, RAG_USER, MCP_SYSTEM, WEB_SYSTEM

    llm = _Ollama(base_url=cfg.ollama_base_url, model=cfg.ollama_llm_model,
                  temperature=0.1, max_tokens=1500)
    tier = state.get("source_tier", "rag")
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in state.get("chat_history", [])[-6:]
    )

    if tier == "mcp" and state.get("mcp_result"):
        prompt = MCP_SYSTEM.format(mcp_result=json.dumps(state["mcp_result"], indent=2))
        messages = [{"role": "system", "content": prompt}]
    elif tier == "web" and state.get("web_results"):
        prompt = WEB_SYSTEM.format(web_results=json.dumps(state["web_results"], indent=2),
                                   user_query=state["user_query"])
        messages = [{"role": "system", "content": prompt}]
    else:
        context_text = "\n\n---\n\n".join(
            f"[{c.get('source','?')} p.{c.get('page','?')}]\n{c['text']}"
            for c in state.get("rag_chunks", [])
        )
        if state.get("vision_context"):
            context_text = f"[Visual Context]\n{state['vision_context']}\n\n---\n\n" + context_text
        messages = [
            {"role": "system", "content": RAG_SYSTEM.format(context=context_text, chat_history=history_text)},
            {"role": "user",   "content": RAG_USER.format(user_query=state["user_query"])},
        ]

    answer = llm.invoke(messages).content.strip()
    return {"generated_answer": answer}


# ─────────────────────────────────────────────────────────────────────────────
# NODE: run_critique
# ─────────────────────────────────────────────────────────────────────────────
def run_critique(state: AgentState) -> dict:
    from services.agents.critic_agent import CriticAgent
    agent = CriticAgent()
    result = agent.score(
        user_query=state["user_query"],
        generated_answer=state["generated_answer"],
        sources=state.get("sources", []),
    )
    return {
        "confidence_score": result["overall"],
        "confidence_label": result["label"],
        "critic_explanation": result["explanation"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE: escalate  (tier counter bump)
# ─────────────────────────────────────────────────────────────────────────────
def escalate_tier(state: AgentState) -> dict:
    return {"retry_count": state.get("retry_count", 0) + 1}


# ─────────────────────────────────────────────────────────────────────────────
# Routing helpers
# ─────────────────────────────────────────────────────────────────────────────
def should_escalate(state: AgentState) -> Literal["generate", "escalate"]:
    tier = state.get("source_tier", "")
    if tier == "mcp" and not state.get("mcp_result"):
        return "escalate"
    if tier == "rag" and not state.get("rag_chunks"):
        return "escalate"
    return "generate"


def route_escalation(state: AgentState) -> Literal["rag", "web", "end"]:
    tier = state.get("source_tier", "mcp")
    retry = state.get("retry_count", 0)
    if retry >= 2:
        return "end"
    if tier == "mcp":
        return "rag"
    return "web"


def should_re_escalate(state: AgentState) -> Literal["done", "escalate"]:
    score = state.get("confidence_score", 1.0)
    retry = state.get("retry_count", 0)
    if score < cfg.critic_threshold and retry < 2:
        return "escalate"
    return "done"
