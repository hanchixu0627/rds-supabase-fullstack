"""Tests for tool registration, risk declaration and middleware behaviour."""

from typing import Any

from huaweicloud_mcp_core import ToolRisk
from huaweicloud_mcp_core.guardrails.audit import AuditLogger
from huaweicloud_mcp_core.guardrails.middleware import GuardrailsMiddleware
from huaweicloud_mcp_core.security import get_tool_risk

from mcp_server_rds_supabase.server import mcp
from tests.conftest import make_settings

# All 38 tools in upstream registration order. Deliberately removed for
# this cloud deployment (see CHANGELOG 0.2.0): apply_migration,
# list_migrations and the three edge-function tools. WRITE is used instead
# of DANGEROUS because the tools have no confirm parameter: the surface
# stays unchanged (guardrail confirm rules remain available).
EXPECTED: dict[str, ToolRisk] = {
    "list_tables": ToolRisk.READ,
    "list_extensions": ToolRisk.READ,
    "execute_sql": ToolRisk.WRITE,
    "get_database_connections": ToolRisk.READ,
    "get_database_stats": ToolRisk.READ,
    "get_project_url": ToolRisk.READ,
    "generate_typescript_types": ToolRisk.WRITE,
    "rebuild_hooks": ToolRisk.WRITE,
    "verify_jwt_secret": ToolRisk.READ,
    "list_auth_users": ToolRisk.READ,
    "get_auth_user": ToolRisk.READ,
    "delete_auth_user": ToolRisk.WRITE,
    "create_auth_user": ToolRisk.WRITE,
    "update_auth_user": ToolRisk.WRITE,
    "list_storage_buckets": ToolRisk.READ,
    "list_storage_objects": ToolRisk.READ,
    "list_realtime_publications": ToolRisk.READ,
    "list_cron_jobs": ToolRisk.READ,
    "list_vector_indexes": ToolRisk.READ,
    "get_logs": ToolRisk.READ,
    "get_advisors": ToolRisk.READ,
    "get_storage_config": ToolRisk.READ,
    "update_storage_config": ToolRisk.WRITE,
    "list_table_columns": ToolRisk.READ,
    "list_indexes": ToolRisk.READ,
    "list_constraints": ToolRisk.READ,
    "list_foreign_keys": ToolRisk.READ,
    "list_rls_policies": ToolRisk.READ,
    "list_triggers": ToolRisk.READ,
    "list_database_functions": ToolRisk.READ,
    "get_function_definition": ToolRisk.READ,
    "get_trigger_definition": ToolRisk.READ,
    "get_rls_status": ToolRisk.READ,
    "list_available_extensions": ToolRisk.READ,
    "get_cron_job_history": ToolRisk.READ,
    "get_index_stats": ToolRisk.READ,
    "get_vector_index_stats": ToolRisk.READ,
    "explain_query": ToolRisk.READ,
}

_EXPECTED_WRITE = {name for name, risk in EXPECTED.items() if risk is ToolRisk.WRITE}


def test_every_tool_declares_its_risk() -> None:
    for name, risk in EXPECTED.items():
        assert get_tool_risk(name) is risk, name


def test_risk_distribution_matches_the_upstream_privilege_model() -> None:
    assert len(EXPECTED) == 38
    assert len(_EXPECTED_WRITE) == 7
    assert {
            "execute_sql",
        "generate_typescript_types",
        "rebuild_hooks",
        "delete_auth_user",
        "create_auth_user",
        "update_auth_user",
        "update_storage_config",
    } == _EXPECTED_WRITE


async def test_registered_tools_match_expected_set_and_order() -> None:
    tools = await mcp.list_tools()
    assert [tool.name for tool in tools] == list(EXPECTED)


async def test_tool_descriptions_start_with_upstream_text() -> None:
    tools = {tool.name: tool for tool in await mcp.list_tools()}
    upstream_first_lines = {
        "list_tables": "Lists all accessible tables in the connected database, grouped by schema.",
        "list_extensions": "Lists all installed PostgreSQL extensions in the database.",
        "execute_sql": (
            "Executes an arbitrary SQL query against the database. "
            "SECURITY: Requires a service_role key."
        ),
        "get_database_connections": (
            "Retrieves information about active database connections from pg_stat_activity."
        ),
        "get_database_stats": (
            "Retrieves statistics about database activity and the background writer "
            "from pg_stat_database and pg_stat_bgwriter."
        ),
    }
    for name, first_line in upstream_first_lines.items():
        description = tools[name].description or ""
        assert description.splitlines()[0] == first_line, name


async def test_tool_input_schemas_match_upstream_shapes() -> None:
    tools = {tool.name: tool for tool in await mcp.list_tools()}
    assert tools["execute_sql"].input_schema["required"] == ["sql"]  # type: ignore[index]
    assert tools["execute_sql"].input_schema["properties"]["read_only"]["default"] is False  # type: ignore[index]
    assert tools["get_logs"].input_schema["required"] == ["service"]  # type: ignore[index]
    assert tools["get_advisors"].input_schema["required"] == ["type"]  # type: ignore[index]


def _middleware(read_only: bool = False) -> GuardrailsMiddleware:
    return GuardrailsMiddleware(read_only=read_only, rules=[], audit=AuditLogger())


class _Context:
    def __init__(self, name: str, arguments: dict[str, Any]) -> None:
        self.method = "tools/call"
        self.params = {"name": name, "arguments": arguments}


async def test_read_only_mode_blocks_write_and_allows_read() -> None:
    middleware = _middleware(read_only=True)

    async def call_read(_: Any) -> Any:
        return {"ok": True}

    result = await middleware(_Context("list_tables", {}), call_read)  # type: ignore[arg-type]
    assert result == {"ok": True}

    async def call_write(_: Any) -> Any:
        return {"ok": True}

    result = await middleware(_Context("execute_sql", {"sql": "SELECT 1"}), call_write)  # type: ignore[arg-type]
    assert result.structured_content == {  # type: ignore[comparison-overlap]
        "error": {
            "code": "MCP_READ_ONLY",
            "message": "Tool 'execute_sql' is blocked in read-only mode.",
            "hint": "Unset HUAWEICLOUD_MCP_READ_ONLY only in an approved write environment.",
        }
    }


async def test_undeclared_tool_is_rejected() -> None:
    middleware = _middleware()

    async def call(_: Any) -> Any:
        return {"ok": True}

    result = await middleware(_Context("not_a_tool", {}), call)  # type: ignore[arg-type]
    assert result.structured_content["error"]["code"] == "MCP_GUARDRAIL_ERROR"  # type: ignore[index]


async def test_mcp_tool_error_becomes_envelope() -> None:
    from huaweicloud_mcp_core import McpToolError

    middleware = _middleware()

    async def call(_: Any) -> Any:
        raise McpToolError("MCP_CONFIG_ERROR", "Direct database connection is required.")

    result = await middleware(  # type: ignore[arg-type]
        _Context("execute_sql", {"sql": "SELECT 1"}), call
    )
    assert result.structured_content == {  # type: ignore[comparison-overlap]
        "error": {
            "code": "MCP_CONFIG_ERROR",
            "message": "Direct database connection is required.",
            "hint": "Inspect the error message and adjust the tool call.",
        }
    }


async def test_services_default_to_the_shared_client(monkeypatch: Any) -> None:
    from mcp_server_rds_supabase.client.rds_supabase_client import RdsSupabaseClient
    from mcp_server_rds_supabase.service.database_service import DatabaseService

    sentinel = RdsSupabaseClient(make_settings())
    monkeypatch.setattr(RdsSupabaseClient, "_shared_client", sentinel)
    service = DatabaseService(settings=make_settings())
    assert service._client is sentinel
