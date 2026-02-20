#!/usr/bin/env bash
# scripts/setup.sh
# One-time setup: pull Ollama models and seed the error database.
# Run AFTER `docker compose up ollama` has started.

set -e

OLLAMA_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
LLM_MODEL="${OLLAMA_LLM_MODEL:-llama3.1:8b}"
VISION_MODEL="${OLLAMA_VISION_MODEL:-llava:7b}"
EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Multimodal RAG Troubleshooter — Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Wait for Ollama to be ready ───────────────────────────────────────────────
echo "⏳  Waiting for Ollama at $OLLAMA_URL …"
until curl -sf "$OLLAMA_URL/api/tags" > /dev/null 2>&1; do
    sleep 2
done
echo "✅  Ollama is ready."

# ── Pull models ───────────────────────────────────────────────────────────────
echo ""
echo "📦  Pulling models (this may take 10–30 min on first run):"
echo "    LLM:     $LLM_MODEL"
echo "    Vision:  $VISION_MODEL"
echo "    Embed:   $EMBED_MODEL"
echo ""

curl -s -X POST "$OLLAMA_URL/api/pull" -d "{\"name\":\"$LLM_MODEL\"}"    | tail -1
curl -s -X POST "$OLLAMA_URL/api/pull" -d "{\"name\":\"$VISION_MODEL\"}" | tail -1
curl -s -X POST "$OLLAMA_URL/api/pull" -d "{\"name\":\"$EMBED_MODEL\"}"  | tail -1

echo ""
echo "✅  All models pulled."

# ── Seed error database ───────────────────────────────────────────────────────
echo ""
echo "🗄️   Seeding error code database …"
python scripts/seed_error_db.py

# ── Create required directories ───────────────────────────────────────────────
mkdir -p services/vector_store data/uploads monitoring evaluation/results

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅  Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Copy .env.example → .env and review settings"
echo "  2. Run: docker compose up --build"
echo "  3. Open: http://localhost:8501"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
