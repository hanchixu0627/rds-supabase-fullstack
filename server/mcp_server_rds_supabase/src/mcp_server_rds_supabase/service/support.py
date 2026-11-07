"""Shared helpers for the service layer, mirroring the upstream utils module."""

import asyncio
import json
import logging
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from huaweicloud_mcp_core import McpToolError

from ..client.rds_supabase_client import SqlExecutionResult

logger = logging.getLogger(__name__)


def is_sql_error_response(result: SqlExecutionResult) -> bool:
    """Type guard mirroring the upstream isSqlErrorResponse."""
    return isinstance(result, dict) and "error" in result


def rows_or_raise(result: SqlExecutionResult) -> list[dict[str, Any]]:
    """Handle a SQL result: raise the upstream error text or return rows.

    Upstream runtime output-schema validation is intentionally replaced by the
    typed service signatures and the test suite.
    """
    if is_sql_error_response(result):
        error: dict[str, Any] = result["error"]
        code = error.get("code")
        message = error.get("message")
        raise McpToolError(str(code) if code else "MCP_SQL_ERROR", f"SQL Error ({code}): {message}")
    return [dict(row) for row in result]


def redact_database_url(url: str) -> str:
    """Replace the password in a database URL for safe logging."""
    try:
        parts = urlsplit(url)
        if parts.password:
            hostinfo = parts.hostname or ""
            if parts.port:
                hostinfo = f"{hostinfo}:{parts.port}"
            userinfo = parts.username or ""
            return urlunsplit((parts.scheme, f"{userinfo}:****@{hostinfo}", parts.path, "", ""))
        return url
    except ValueError:
        return re.sub(r":([^:@]+)@", ":****@", url)


def sanitize_error_for_logging(error: BaseException | dict[str, Any] | Any) -> str:
    """Extract only safe properties from an error for logging."""
    if isinstance(error, BaseException):
        code = getattr(error, "code", None)
        text = str(error)
        return f"[{code}] {text}" if code else text
    if isinstance(error, dict):
        raw = error.get("message")
        code = error.get("code")
        if isinstance(raw, str):
            return f"[{code}] {raw}" if isinstance(code, str) else raw
    return str(error)


async def run_external_command(command: str) -> dict[str, Any]:
    """Run a shell command, mirroring the upstream promisified exec helper."""
    try:
        proc = await asyncio.create_subprocess_shell(
            command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        decoded_out = stdout.decode(errors="replace")
        decoded_err = stderr.decode(errors="replace")
        if proc.returncode != 0:
            error = f"Command exited with code {proc.returncode}"
            return {"stdout": decoded_out, "stderr": decoded_err or error, "error": error}
        return {"stdout": decoded_out, "stderr": decoded_err, "error": None}
    except Exception as exc:
        return {"stdout": "", "stderr": str(exc), "error": str(exc)}


def as_text(result: Any) -> str:
    """Serialize a tool result like the upstream wrapper (JSON.stringify, indent 2).

    The MCP 2.x SDK flattens raw list returns into one text block per row;
    serializing here keeps the upstream single-text payload shape (and renders
    a null result as the JSON text "null").
    """
    return json.dumps(result, ensure_ascii=False, indent=2)
