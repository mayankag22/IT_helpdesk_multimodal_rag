"""
tests/test_mcp_server.py
Unit tests for the MCP server tools.
Run: pytest tests/test_mcp_server.py -v
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── ErrorLookup tests ─────────────────────────────────────────────────────────
class TestErrorLookup:
    @pytest.fixture
    def store(self, tmp_path):
        from services.mcp_server.tools.error_lookup import ErrorLookup
        db = str(tmp_path / "test.db")
        s = ErrorLookup(db_path=db)
        s.seed_error(
            code="0x4F", category="PCIe", description="PCIe link failure",
            root_cause="Card not seated", fix_steps="Reseat card.", severity="HIGH"
        )
        s.seed_section("NIC-LED-AMBER", "LED States", "Amber = link failure", "NIC")
        return s

    def test_lookup_exact(self, store):
        result = store.lookup("0x4F")
        assert result is not None
        assert result["description"] == "PCIe link failure"

    def test_lookup_case_insensitive(self, store):
        assert store.lookup("0x4f") is not None

    def test_lookup_missing(self, store):
        assert store.lookup("NONEXISTENT") is None

    def test_get_section(self, store):
        s = store.get_section("NIC-LED-AMBER")
        assert s is not None
        assert "Amber" in s["content"]

    def test_get_section_missing(self, store):
        assert store.get_section("DOESNOTEXIST") is None


# ── SafeRepl tests ────────────────────────────────────────────────────────────
class TestSafeRepl:
    @pytest.fixture
    def repl(self):
        from services.mcp_server.tools.python_repl import SafeRepl
        return SafeRepl()

    def test_simple_arithmetic(self, repl):
        out, err = repl.execute("print(2 + 2)")
        assert err == ""
        assert "4" in out

    def test_list_comprehension(self, repl):
        out, err = repl.execute("print([x*2 for x in range(5)])")
        assert err == ""
        assert "8" in out

    def test_blocks_import(self, repl):
        out, err = repl.execute("import os\nprint(os.getcwd())")
        assert err != ""   # should raise an error

    def test_syntax_error(self, repl):
        out, err = repl.execute("def broken(")
        assert "SyntaxError" in err
