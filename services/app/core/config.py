"""
services/app/core/config.py
Central settings — loaded once at startup from .env via python-dotenv.
"""
from __future__ import annotations
import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # ── Ollama ──────────────────────────────────────────────────────────────
    ollama_base_url: str = Field("http://localhost:11434", env="OLLAMA_BASE_URL")
    ollama_llm_model: str = Field("llama3.1:8b", env="OLLAMA_LLM_MODEL")
    ollama_vision_model: str = Field("llava:7b", env="OLLAMA_VISION_MODEL")
    ollama_embed_model: str = Field("nomic-embed-text", env="OLLAMA_EMBED_MODEL")

    # ── MCP Server ──────────────────────────────────────────────────────────
    mcp_server_url: str = Field("http://localhost:8000", env="MCP_SERVER_URL")
    mcp_api_key: str = Field("changeme", env="MCP_API_KEY")

    # ── ChromaDB ────────────────────────────────────────────────────────────
    chroma_persist_dir: str = Field("./vector_store", env="CHROMA_PERSIST_DIR")

    # ── Retrieval ────────────────────────────────────────────────────────────
    chunk_size: int = Field(512, env="CHUNK_SIZE")
    chunk_overlap: int = Field(64, env="CHUNK_OVERLAP")
    top_k_results: int = Field(5, env="TOP_K_RESULTS")
    rerank_top_n: int = Field(3, env="RERANK_TOP_N")
    critic_threshold: float = Field(0.70, env="CRITIC_THRESHOLD")

    # ── Web Search ──────────────────────────────────────────────────────────
    tavily_api_key: str = Field("", env="TAVILY_API_KEY")

    # ── Observability ───────────────────────────────────────────────────────
    langsmith_api_key: str = Field("", env="LANGSMITH_API_KEY")
    langsmith_project: str = Field("multimodal-rag-troubleshooter", env="LANGSMITH_PROJECT")
    langchain_tracing_v2: bool = Field(False, env="LANGCHAIN_TRACING_V2")

    # ── Optional Cloud Fallback ──────────────────────────────────────────────
    openai_api_key: str = Field("", env="OPENAI_API_KEY")
    enable_openai_fallback: bool = Field(False, env="ENABLE_OPENAI_FALLBACK")

    # ── Logging ─────────────────────────────────────────────────────────────
    runs_log_path: str = Field("./runs.jsonl", env="RUNS_LOG_PATH")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Singleton settings object — import this everywhere."""
    s = Settings()
    # Propagate LangSmith env vars if tracing is enabled
    if s.langchain_tracing_v2 and s.langsmith_api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = s.langsmith_api_key
        os.environ["LANGCHAIN_PROJECT"] = s.langsmith_project
    return s
