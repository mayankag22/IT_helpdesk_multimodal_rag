"""
services/mcp_server/tools/error_lookup.py
SQLite-backed error code and manual section store.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS error_codes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT UNIQUE NOT NULL,
    category    TEXT,
    description TEXT,
    root_cause  TEXT,
    fix_steps   TEXT,
    severity    TEXT DEFAULT 'MEDIUM',
    "references"  TEXT
);

CREATE TABLE IF NOT EXISTS manual_sections (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id  TEXT UNIQUE NOT NULL,
    title       TEXT,
    content     TEXT,
    device      TEXT
);
"""


class ErrorLookup:
    def __init__(self, db_path: str = "/app/data/error_codes.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    # ── Lookup error code ──────────────────────────────────────────────────────
    def lookup(self, code: str) -> Optional[dict]:
        """Case-insensitive lookup for exact or prefix match."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM error_codes WHERE LOWER(code) = LOWER(?)", (code,)
            ).fetchone()
            if not row:
                # Try prefix match (e.g. "0x4" matches "0x4F")
                row = conn.execute(
                    "SELECT * FROM error_codes WHERE LOWER(code) LIKE LOWER(?)",
                    (f"{code}%",)
                ).fetchone()
        if row:
            return dict(row)
        return None

    # ── Lookup manual section ─────────────────────────────────────────────────
    def get_section(self, section_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM manual_sections WHERE section_id = ?", (section_id,)
            ).fetchone()
        return dict(row) if row else None

    # ── Seed helpers (called by scripts/seed_error_db.py) ────────────────────
    def seed_error(self, code: str, category: str, description: str,
                   root_cause: str, fix_steps: str, severity: str = "MEDIUM",
                   references: str = "") -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO error_codes
                   (code, category, description, root_cause, fix_steps, severity, "references")
                   VALUES (?,?,?,?,?,?,?)""",
                (code, category, description, root_cause, fix_steps, severity, references)
            )

    def seed_section(self, section_id: str, title: str, content: str, device: str = "") -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO manual_sections (section_id, title, content, device)
                   VALUES (?,?,?,?)""",
                (section_id, title, content, device)
            )
