"""
monitoring/logging_config.py
Structured JSON logging → runs.jsonl for offline analysis.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path(os.getenv("RUNS_LOG_PATH", "./runs.jsonl"))
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)


def log_run(data: dict) -> None:
    """Append a structured run record to runs.jsonl."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        **data,
    }
    try:
        with LOG_PATH.open("a") as f:
            f.write(json.dumps(record) + "\n")
    except OSError as exc:
        logging.getLogger(__name__).warning("Could not write to runs.jsonl: %s", exc)
