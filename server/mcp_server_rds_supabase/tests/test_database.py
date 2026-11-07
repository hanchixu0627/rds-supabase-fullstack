"""Tests for the database tool group (fake client)."""

import json
from typing import Any

import pytest
from huaweicloud_mcp_core import McpToolError

from mcp_server_rds_supabase.service.database_service import DatabaseService
from tests.conftest import FakeRdsSupabaseClient, make_settings

ROWS: list[dict[str, Any]] = [{"schema": "public", "name": "students", "comment": None}]


def _service(responses: dict[str, Any] | None = None) -> DatabaseService:
    return DatabaseService(
        client=FakeRdsSupabaseClient(responses or {"execute_sql": list(ROWS)}),
        settings=make_settings(),
    )


async def test_list_tables_returns_rows() -> None:
    service = _service()
    assert await service.list_tables() == ROWS
    assert service._client.calls[0][0] == "execute_sql"


async def test_list_tables_passes_the_upstream_sql() -> None:
    service = _service()
    await service.list_tables()
    call = service._client.calls[0]
    assert call[0] == "execute_sql"
    assert call[1]["read_only"] is True
    assert "pg_catalog.pg_class" in call[1]["query"]
    assert "supabase_migrations" in call[1]["query"]


async def test_sql_error_raises_upstream_message() -> None:
    service = _service(
        {
            "execute_sql": {
                "error": {"message": "relation does not exist", "code": "42P01"}
            }
        }
    )
    with pytest.raises(McpToolError) as exc_info:
        await service.list_tables()
    assert exc_info.value.message == "SQL Error (42P01): relation does not exist"
    assert exc_info.value.code == "42P01"


async def test_fallback_config_error_raises_upstream_message() -> None:
    service = _service(
        {
            "execute_sql": {
                "error": {
                    "message": (
                        "Service role key (SUPABASE_SERVICE_ROLE_KEY) is not configured. "
                        "Cannot execute SQL."
                    ),
                    "code": "MCP_CONFIG_ERROR",
                }
            }
        }
    )
    with pytest.raises(McpToolError) as exc_info:
        await service.list_tables()
    assert exc_info.value.message == (
        "SQL Error (MCP_CONFIG_ERROR): Service role key (SUPABASE_SERVICE_ROLE_KEY) "
        "is not configured. Cannot execute SQL."
    )


async def test_list_extensions_returns_rows() -> None:
    service = _service(
        {
            "execute_sql": [
                {"name": "pg_net", "schema": "extensions", "version": "0.20.2", "description": None}
            ]
        }
    )
    assert await service.list_extensions() == [
        {"name": "pg_net", "schema": "extensions", "version": "0.20.2", "description": None}
    ]


async def test_execute_sql_requires_privileged_channel() -> None:
    service = _service()
    with pytest.raises(McpToolError) as exc_info:
        await service.execute_sql(sql="SELECT 1")
    assert exc_info.value.message == (
        "execute_sql requires a service role key (SUPABASE_SERVICE_ROLE_KEY) "
        "to be configured. This tool cannot be used with only the anon key "
        "for security reasons."
    )


async def test_execute_sql_returns_rows_with_read_only_flag() -> None:
    service = _service({"execute_sql": [{"?column?": 1}]})
    service._client.service_role_available = True
    assert await service.execute_sql(sql="SELECT 1", read_only=True) == [{"?column?": 1}]
    call = service._client.calls[0]
    assert call[1] == {"query": "SELECT 1", "read_only": True}


async def test_execute_sql_truncates_long_audit_preview(capfd: pytest.CaptureFixture[str]) -> None:
    service = _service({"execute_sql": []})
    service._client.service_role_available = True
    long_sql = "SELECT " + "x" * 300
    await service.execute_sql(sql=long_sql)
    captured = capfd.readouterr()
    assert "[AUDIT] SQL execution by user=unknown (stdio mode): SELECT xxx" in captured.err
    assert f"[truncated, {len(long_sql)} chars total]" in captured.err


async def test_get_database_connections_returns_rows() -> None:
    service = _service({"execute_sql": [{"pid": 100, "state": "idle"}]})
    assert await service.get_database_connections() == [{"pid": 100, "state": "idle"}]


async def test_get_database_stats_combines_both_snapshots() -> None:
    service = _service({"execute_sql": [{"datname": "supabase_db"}]})
    result = await service.get_database_stats()
    assert result == {
        "database_stats": [{"datname": "supabase_db"}],
        "bgwriter_stats": [{"datname": "supabase_db"}],
    }
    fallback_calls = [c for c in service._client.calls if c[0] == "execute_sql"]
    assert len(fallback_calls) == 2
    assert "pg_stat_database" in fallback_calls[0][1]["query"]
    assert "pg_stat_bgwriter" in fallback_calls[1][1]["query"]


async def test_tool_functions_delegate_to_the_service(monkeypatch: pytest.MonkeyPatch) -> None:
    from mcp_server_rds_supabase.tools import database as database_tools

    class StubService:
        async def list_tables(self) -> list[dict[str, Any]]:
            return [{"schema": "public", "name": "t"}]

        async def execute_sql(self, *, sql: str, read_only: bool) -> list[dict[str, Any]]:
            return [{"echo": sql, "read_only": read_only}]

    monkeypatch.setattr(database_tools, "DatabaseService", StubService)
    assert json.loads(await database_tools.list_tables()) == [{"schema": "public", "name": "t"}]
    assert json.loads(await database_tools.execute_sql("SELECT 1", True)) == [
        {"echo": "SELECT 1", "read_only": True}
    ]
