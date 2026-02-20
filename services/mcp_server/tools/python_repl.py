"""
services/mcp_server/tools/python_repl.py
Sandboxed Python REPL using RestrictedPython.
Only safe builtins are allowed. No file I/O, no subprocess, no imports.
"""
from __future__ import annotations

import io
import logging
from typing import Tuple

from RestrictedPython import compile_restricted, safe_globals, safe_builtins, limited_builtins

log = logging.getLogger(__name__)

# Whitelist of safe builtins available inside the sandbox
_SAFE_BUILTINS = {**safe_builtins, **limited_builtins,
                  "print": print, "len": len, "range": range,
                  "int": int, "float": float, "str": str,
                  "list": list, "dict": dict, "set": set, "tuple": tuple,
                  "abs": abs, "max": max, "min": min, "sum": sum,
                  "sorted": sorted, "enumerate": enumerate, "zip": zip,
                  "isinstance": isinstance, "bool": bool}

MAX_OUTPUT_CHARS = 2000
TIMEOUT_SECONDS  = 5


class SafeRepl:
    def execute(self, snippet: str) -> Tuple[str, str]:
        """
        Execute `snippet` in a restricted environment.
        Returns (stdout_output, error_message).
        Empty error_message means success.
        """
        # Capture stdout
        buf = io.StringIO()

        try:
            code = compile_restricted(snippet, filename="<diagnostic>", mode="exec")
        except SyntaxError as exc:
            return "", f"SyntaxError: {exc}"

        globs = {**safe_globals, "__builtins__": _SAFE_BUILTINS}

        import sys
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            exec(code, globs)  # noqa: S102  (intentional sandboxed exec)
        except Exception as exc:
            sys.stdout = old_stdout
            return "", f"{type(exc).__name__}: {exc}"
        finally:
            sys.stdout = old_stdout

        output = buf.getvalue()[:MAX_OUTPUT_CHARS]
        log.info("REPL executed snippet (%d chars). Output: %s", len(snippet), output[:80])
        return output, ""
