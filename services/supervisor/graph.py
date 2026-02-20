"""
services/supervisor/graph.py
LangGraph state-machine definition. Each node is a discrete agent step.
The graph enforces the MCP → RAG → Web fallback chain deterministically.
"""
from __future__ import annotations

from langgraph.graph import StateGraph, END
from services.supervisor.state import AgentState
from services.supervisor import nodes


def build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    # ── Register nodes ────────────────────────────────────────────────────────
    g.add_node("classify",     nodes.classify_intent)
    g.add_node("ingest",       nodes.run_ingestion)
    g.add_node("vision",       nodes.run_vision)
    g.add_node("mcp_lookup",   nodes.run_mcp_lookup)
    g.add_node("rag_retrieve", nodes.run_rag_retrieve)
    g.add_node("web_search",   nodes.run_web_search)
    g.add_node("generate",     nodes.run_generation)
    g.add_node("critique",     nodes.run_critique)
    g.add_node("escalate",     nodes.escalate_tier)

    # ── Entry point ───────────────────────────────────────────────────────────
    g.set_entry_point("classify")

    # ── Classify → branch on intent ───────────────────────────────────────────
    g.add_conditional_edges(
        "classify",
        nodes.route_after_classify,
        {
            "ingest":      "ingest",
            "vision_then": "vision",
            "mcp":         "mcp_lookup",
            "rag":         "rag_retrieve",
            "web":         "web_search",
        },
    )

    # ── Ingestion always ends (no answer needed) ──────────────────────────────
    g.add_edge("ingest", END)

    # ── Vision feeds into primary route ───────────────────────────────────────
    g.add_conditional_edges(
        "vision",
        nodes.route_after_vision,
        {"mcp": "mcp_lookup", "rag": "rag_retrieve", "web": "web_search"},
    )

    # ── MCP result → generate (or escalate to RAG) ────────────────────────────
    g.add_conditional_edges(
        "mcp_lookup",
        nodes.should_escalate,
        {"generate": "generate", "escalate": "escalate"},
    )

    # ── RAG result → generate (or escalate to Web) ────────────────────────────
    g.add_conditional_edges(
        "rag_retrieve",
        nodes.should_escalate,
        {"generate": "generate", "escalate": "escalate"},
    )

    # ── Web result → always generate ─────────────────────────────────────────
    g.add_edge("web_search", "generate")

    # ── Escalate → next tier ──────────────────────────────────────────────────
    g.add_conditional_edges(
        "escalate",
        nodes.route_escalation,
        {"rag": "rag_retrieve", "web": "web_search", "end": END},
    )

    # ── Generate → critique ──────────────────────────────────────────────────
    g.add_edge("generate", "critique")

    # ── Critique → done (or re-escalate if below threshold) ──────────────────
    g.add_conditional_edges(
        "critique",
        nodes.should_re_escalate,
        {"done": END, "escalate": "escalate"},
    )

    return g.compile()


# Singleton compiled graph — import this in the Streamlit app
troubleshooter_graph = build_graph()
