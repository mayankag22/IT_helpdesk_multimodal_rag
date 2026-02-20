"""
services/app/streamlit_app.py
Streamlit chat UI — entry point for the user-facing interface.
"""
from __future__ import annotations

# ── Path bootstrap ─────────────────────────────────────────────────────────
# MUST be the very first thing before any project imports.
#
# Root cause of "ModuleNotFoundError: No module named 'services'":
#   Streamlit launches scripts with its own sys.path that does NOT include
#   the project root (/app), even when WORKDIR and PYTHONPATH are set in
#   the Dockerfile. Python resolves imports at the moment the 'import'
#   statement executes, so patching sys.path here (before any project
#   import) is the most reliable cross-platform fix.
#
# __file__ is  /app/services/app/streamlit_app.py
# .parents[2]  is  /app   ← the project root we need on sys.path
import sys as _sys
from pathlib import Path as _Path

_PROJECT_ROOT = str(_Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in _sys.path:
    _sys.path.insert(0, _PROJECT_ROOT)
# ──────────────────────────────────────────────────────────────────────────

import json
import logging
import time
import uuid
from pathlib import Path

import streamlit as st

from services.app.core.config import get_settings
from services.supervisor.graph import troubleshooter_graph
from monitoring.logging_config import log_run

cfg = get_settings()
log = logging.getLogger(__name__)

UPLOAD_DIR = Path("/app/data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

CONFIDENCE_BADGE = {
    "HIGH":   "🟢 HIGH CONFIDENCE",
    "MEDIUM": "🟡 MEDIUM CONFIDENCE",
    "LOW":    "🔴 LOW CONFIDENCE",
}

SOURCE_TIER_LABEL = {
    "mcp":       "🔧 MCP Error Database",
    "rag":       "📚 Document Knowledge Base",
    "web":       "🌐 Web Search",
    "ingestion": "📥 File Ingestion",
}


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="🤖 AI Troubleshooter",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main():
    # ── Session state init ────────────────────────────────────────────────────
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())[:8]
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "uploaded_paths" not in st.session_state:
        st.session_state.uploaded_paths = []

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.title("📁 Knowledge Base")
        st.caption(f"Session: `{st.session_state.session_id}`")
        st.divider()

        uploaded = st.file_uploader(
            "Upload files",
            type=["pdf", "txt", "md", "png", "jpg", "jpeg"],
            accept_multiple_files=True,
            help="PDFs (manuals), images (screenshots), or text (error logs)",
        )

        if uploaded:
            new_paths = []
            for uf in uploaded:
                dest = UPLOAD_DIR / f"{st.session_state.session_id}_{uf.name}"
                dest.write_bytes(uf.read())
                new_paths.append(str(dest))
            if new_paths:
                st.session_state.uploaded_paths = list(
                    set(st.session_state.uploaded_paths + new_paths)
                )
                st.success(f"{len(new_paths)} file(s) queued for ingestion.")

        if st.session_state.uploaded_paths:
            st.write("**Indexed files:**")
            for p in st.session_state.uploaded_paths:
                st.caption(f"• {Path(p).name.split('_', 1)[-1]}")

        st.divider()
        if st.button("🗑️ Clear session"):
            st.session_state.clear()
            st.rerun()

        st.divider()
        st.caption("**Stack:** Ollama · LangGraph · ChromaDB · FastAPI")
        st.caption("**Models:** llama3.1:8b · llava:7b · nomic-embed-text")

    # ── Main chat area ────────────────────────────────────────────────────────
    st.title("🤖 Multimodal AI Troubleshooter")
    st.caption("Upload manuals, screenshots, or describe your problem. I'll diagnose it.")

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("meta"):
                _render_meta(msg["meta"])

    # ── Chat input ────────────────────────────────────────────────────────────
    if prompt := st.chat_input("Describe the issue or paste an error code…"):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("🔍 Analysing…"):
                t0 = time.time()
                result = _run_graph(prompt)
                latency_ms = int((time.time() - t0) * 1000)

            answer = result.get("generated_answer", "I was unable to find an answer.")
            st.markdown(answer)

            meta = {
                "confidence_label":  result.get("confidence_label", "LOW"),
                "confidence_score":  result.get("confidence_score", 0.0),
                "critic_explanation": result.get("critic_explanation", ""),
                "source_tier":       result.get("source_tier", ""),
                "sources":           result.get("sources", []),
                "error_codes":       result.get("error_codes", []),
                "latency_ms":        latency_ms,
                "agent_trace":       _build_trace(result),
            }
            _render_meta(meta)

            st.session_state.chat_history.append(
                {"role": "assistant", "content": answer, "meta": meta}
            )

            log_run({
                "session_id":       st.session_state.session_id,
                "query":            prompt,
                "answer":           answer,
                "source_tier":      result.get("source_tier"),
                "confidence_score": result.get("confidence_score"),
                "latency_ms":       latency_ms,
            })

        st.session_state.uploaded_paths = []


def _run_graph(query: str) -> dict:
    initial_state = {
        "session_id":         st.session_state.session_id,
        "user_query":         query,
        "uploaded_files":     st.session_state.uploaded_paths,
        "chat_history":       [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.chat_history[-10:]
        ],
        "error_codes":        [],
        "intent":             "",
        "mcp_result":         None,
        "rag_chunks":         [],
        "web_results":        [],
        "vision_context":     None,
        "generated_answer":   "",
        "source_tier":        "",
        "sources":            [],
        "confidence_score":   0.0,
        "confidence_label":   "LOW",
        "critic_explanation": "",
        "retry_count":        0,
        "error":              None,
    }
    try:
        return troubleshooter_graph.invoke(initial_state)
    except Exception as exc:
        log.exception("Graph execution failed: %s", exc)
        return {
            "generated_answer": f"⚠️ An error occurred: {exc}",
            "source_tier": "error",
        }


def _render_meta(meta: dict):
    label = meta.get("confidence_label", "LOW")
    score = meta.get("confidence_score", 0.0)
    tier  = meta.get("source_tier", "")

    col1, col2, col3 = st.columns(3)
    col1.metric("Confidence", CONFIDENCE_BADGE.get(label, label))
    col2.metric("Score", f"{score:.2f}")
    col3.metric("Source", SOURCE_TIER_LABEL.get(tier, tier))

    sources = meta.get("sources", [])
    if sources:
        with st.expander(f"📎 Sources ({len(sources)})", expanded=False):
            for s in sources:
                file_info  = s.get("file", "")
                page_info  = f", p.{s['page']}" if s.get("page") else ""
                score_info = f" · score {s['score']:.3f}" if s.get("score") is not None else ""
                st.caption(f"• {file_info}{page_info}{score_info}")
                if s.get("text"):
                    st.text(s["text"][:200] + "…")

    if meta.get("agent_trace"):
        with st.expander("🧠 Agent Trace", expanded=False):
            st.code(meta["agent_trace"], language="yaml")

    if meta.get("critic_explanation"):
        st.caption(f"💡 {meta['critic_explanation']}")

    st.caption(f"⏱️ {meta.get('latency_ms', '?')} ms")


def _build_trace(state: dict) -> str:
    return "\n".join([
        f"intent:       {state.get('intent', '?')}",
        f"error_codes:  {state.get('error_codes', [])}",
        f"needs_vision: {bool(state.get('vision_context'))}",
        f"source_tier:  {state.get('source_tier', '?')}",
        f"retry_count:  {state.get('retry_count', 0)}",
        f"rag_chunks:   {len(state.get('rag_chunks', []))} retrieved",
        f"mcp_result:   {'found' if state.get('mcp_result') else 'not found'}",
        f"web_results:  {len(state.get('web_results', []))} results",
        f"confidence:   {state.get('confidence_label')} ({state.get('confidence_score', 0):.2f})",
    ])


if __name__ == "__main__":
    main()
