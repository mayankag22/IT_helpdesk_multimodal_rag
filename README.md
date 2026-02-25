# 🤖 Multimodal Agentic RAG — Technical Troubleshooter

> Upload a PDF manual, paste a screenshot of the error, describe the symptom — get a grounded, cited diagnosis.

![Architecture](docs/architecture.svg)

---

## ✨ What it does

This is a **fully local, zero-cloud-cost** AI troubleshooting assistant that runs as two Docker containers on your laptop. A user can upload PDF manuals, device schematics, or screenshots of error screens alongside a text description of the problem. An orchestrated network of specialised agents diagnoses the issue using a deterministic fallback chain:

1. **MCP Server** (fastest): looks up the exact error code in a local SQLite database
2. **RAG Agent** (secondary): hybrid ChromaDB + BM25 retrieval over uploaded documents, reranked by a cross-encoder
3. **Web Search** (last resort): DuckDuckGo (free) or Tavily

Before any answer reaches the user, a **Critic Agent** scores it for faithfulness and relevance. If the score is below the configured threshold (default 0.70), the Supervisor automatically escalates to the next tier.
