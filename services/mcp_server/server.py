"""
services/mcp_server/server.py
FastAPI MCP microservice exposing three diagnostic tools:
  POST /tools/search_error_code
  POST /tools/get_manual_section
  POST /tools/run_diagnostic
Protected by a shared API key header (X-API-Key).
"""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from services.mcp_server.tools.error_lookup import ErrorLookup
from services.mcp_server.tools.python_repl import SafeRepl

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="MCP Server — Technical Troubleshooter",
    description="Model Context Protocol server exposing diagnostic tools.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

_error_lookup = ErrorLookup(db_path=os.getenv("DB_PATH", "/app/data/error_codes.db"))
_repl         = SafeRepl()
_API_KEY      = os.getenv("MCP_API_KEY", "changeme")


# ── Auth ──────────────────────────────────────────────────────────────────────
def verify_key(x_api_key: str = Header(...)):
    if x_api_key != _API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")


# ── Request / Response schemas ────────────────────────────────────────────────
class ErrorCodeRequest(BaseModel):
    code: str

class ManualSectionRequest(BaseModel):
    section_id: str

class DiagnosticRequest(BaseModel):
    snippet: str


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "mcp-server"}


@app.post("/tools/search_error_code", dependencies=[Depends(verify_key)])
def search_error_code(req: ErrorCodeRequest):
    """Look up a known error code in the SQLite database."""
    result = _error_lookup.lookup(req.code.strip())
    if result:
        return {"found": True, "code": req.code, **result}
    return {"found": False, "code": req.code, "message": "Error code not in database."}


@app.post("/tools/get_manual_section", dependencies=[Depends(verify_key)])
def get_manual_section(req: ManualSectionRequest):
    """Return a pre-indexed manual section by ID."""
    result = _error_lookup.get_section(req.section_id)
    if result:
        return {"found": True, **result}
    return {"found": False, "section_id": req.section_id, "message": "Section not found."}


@app.post("/tools/run_diagnostic", dependencies=[Depends(verify_key)])
def run_diagnostic(req: DiagnosticRequest):
    """Execute a sandboxed Python diagnostic snippet."""
    output, error = _repl.execute(req.snippet)
    if error:
        return {"success": False, "error": error}
    return {"success": True, "output": output}


@app.get("/tools")
def list_tools():
    """List available MCP tools (discovery endpoint)."""
    return {
        "tools": [
            {"name": "search_error_code",  "method": "POST", "path": "/tools/search_error_code"},
            {"name": "get_manual_section",  "method": "POST", "path": "/tools/get_manual_section"},
            {"name": "run_diagnostic",      "method": "POST", "path": "/tools/run_diagnostic"},
        ]
    }
