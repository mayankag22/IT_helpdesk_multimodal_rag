"""
tests/test_critic_agent.py
Tests for the CriticAgent scoring logic.
Mocks the LLM to test parsing and clamping without a real Ollama instance.
"""
import sys
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCriticAgent:
    @patch("services.agents.critic_agent.ChatOllama")
    def test_high_confidence_response(self, mock_ollama_cls):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=json.dumps({
            "faithfulness": 0.92,
            "relevance":    0.88,
            "overall":      0.91,
            "label":        "HIGH",
            "explanation":  "Answer is fully grounded in source material.",
        }))
        mock_ollama_cls.return_value = mock_llm

        from services.agents.critic_agent import CriticAgent
        agent = CriticAgent()
        result = agent.score(
            user_query="What causes error 0x4F?",
            generated_answer="PCIe link failure — reseat the card.",
            sources=[{"text": "0x4F = PCIe failure", "file": "manual.pdf", "page": 4, "score": 0.95}],
        )
        assert result["label"] == "HIGH"
        assert result["overall"] >= 0.70

    @patch("services.agents.critic_agent.ChatOllama")
    def test_malformed_json_returns_medium(self, mock_ollama_cls):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="I think it's fine.")
        mock_ollama_cls.return_value = mock_llm

        from services.agents.critic_agent import CriticAgent
        agent = CriticAgent()
        result = agent.score("query", "answer", [])
        assert result["label"] == "MEDIUM"
        assert 0.0 <= result["overall"] <= 1.0

    @patch("services.agents.critic_agent.ChatOllama")
    def test_score_clamped_to_valid_range(self, mock_ollama_cls):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=json.dumps({
            "faithfulness": 1.5,    # above 1.0 — should be clamped
            "relevance":    -0.2,   # below 0.0 — should be clamped
            "overall":      2.0,
            "label":        "HIGH",
            "explanation":  "Test clamping.",
        }))
        mock_ollama_cls.return_value = mock_llm

        from services.agents.critic_agent import CriticAgent
        agent = CriticAgent()
        result = agent.score("q", "a", [])
        assert 0.0 <= result["faithfulness"] <= 1.0
        assert 0.0 <= result["relevance"] <= 1.0
        assert 0.0 <= result["overall"] <= 1.0
