"""
services/agents/critic_agent.py
Quality gate: evaluates generated answers for faithfulness and relevance.
Uses the same local LLM as the Supervisor — no extra cost.
"""
from __future__ import annotations

import json
import logging

from langchain_ollama import ChatOllama

from services.supervisor.prompts import CRITIC_SYSTEM
from services.app.core.config import get_settings

log = logging.getLogger(__name__)
cfg = get_settings()


class CriticAgent:
    def __init__(self):
        self.llm = ChatOllama(
            base_url=cfg.ollama_base_url,
            model=cfg.ollama_llm_model,
            temperature=0,
            max_tokens=256,   # critic only needs a JSON score blob
        )

    def score(self, user_query: str, generated_answer: str, sources: list[dict]) -> dict:
        """
        Returns:
            {faithfulness, relevance, overall, label, explanation}
        """
        prompt = CRITIC_SYSTEM.format(
            user_query=user_query,
            generated_answer=generated_answer,
            sources=json.dumps(sources, indent=2),
        )
        raw = self.llm.invoke([{"role": "user", "content": prompt}]).content.strip()

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("Critic returned non-JSON: %s", raw[:120])
            result = {
                "faithfulness": 0.5,
                "relevance":    0.5,
                "overall":      0.5,
                "label":        "MEDIUM",
                "explanation":  "Could not parse critic output.",
            }

        # Clamp values to valid range
        for key in ("faithfulness", "relevance", "overall"):
            result[key] = max(0.0, min(1.0, float(result.get(key, 0.5))))

        log.info(
            "Critic score: overall=%.2f label=%s — %s",
            result["overall"], result["label"], result.get("explanation", "")
        )
        return result
