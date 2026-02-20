"""
ingestion/image_processor.py
Image → vision description → text chunk, ready for ChromaDB.
Calls VisionAgent internally so image context lands in the same index as PDFs.
"""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


class ImageProcessor:
    def process(self, image_path: str) -> list[dict]:
        # Import here to avoid circular import at module level
        from services.agents.vision_agent import VisionAgent
        path = Path(image_path)
        agent = VisionAgent()
        description = agent.describe_image(image_path)
        if not description:
            log.warning("Vision returned empty description for %s", path.name)
            return []
        return [{
            "text": description,
            "metadata": {
                "source": path.name,
                "page":   0,
                "type":   "image_vision",
            },
        }]
