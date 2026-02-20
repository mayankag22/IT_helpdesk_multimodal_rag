"""
services/agents/vision_agent.py
Converts an image file to a structured technical description using LLaVA:7b
running locally via Ollama. The returned text is then treated as a regular
text chunk and embedded into ChromaDB alongside PDF content.
"""
from __future__ import annotations

import base64
import logging
from pathlib import Path

import httpx

from services.app.core.config import get_settings
from services.supervisor.prompts import VISION_SYSTEM

log = logging.getLogger(__name__)
cfg = get_settings()


class VisionAgent:
    """Calls the Ollama /api/generate endpoint with vision input."""

    def __init__(self):
        self.model   = cfg.ollama_vision_model
        self.base_url = cfg.ollama_base_url.rstrip("/")

    def describe_image(self, image_path: str) -> str:
        """Return a structured natural-language description of the image."""
        path = Path(image_path)
        if not path.exists():
            log.warning("Image not found: %s", image_path)
            return ""

        b64 = base64.b64encode(path.read_bytes()).decode()
        payload = {
            "model":  self.model,
            "prompt": VISION_SYSTEM,
            "images": [b64],
            "stream": False,
            "options": {"temperature": 0, "num_predict": 512},
        }

        try:
            with httpx.Client(timeout=120) as client:
                resp = client.post(f"{self.base_url}/api/generate", json=payload)
                resp.raise_for_status()
                description = resp.json().get("response", "").strip()
                log.info("Vision description for %s: %s…", path.name, description[:80])
                return f"[Image: {path.name}]\n{description}"
        except httpx.HTTPError as exc:
            log.error("Vision API error: %s", exc)
            return f"[Vision extraction failed for {path.name}]"
