"""Tests for the inspection tool group (fake client and sequenced outcomes)."""

import json
from typing import Any

import pytest
from huaweicloud_mcp_core import McpToolError, ToolRisk
from huaweicloud_mcp_core.security import get_tool_risk

from mcp_server_rds_supabase.service.inspection_service import InspectionService
from mcp_server_rds_supabase.tools import inspection as inspection_tools
from tests.conftest import FakeRdsSupabaseClient, make_settings

COLUMNS: list[dict[str, Any]] = [
    {
        "column_name": "id",
        "data_type": "integer",
        "is_nullable": False,
        "column_default": None,
        "description": None,
        "ordinal_position": 1,
        "character_maximum_length": None,
        "numeric_precision": 32,
        "numeric_scale": 0,
        "is_identity": True,
        "identity_generation": "BY DEFAULT",
        "is_generated": False,
        "generation_expression": None,
    }
]

SQL_ERROR = {
    "error": {"message": "permission denied for table pg_class", "code": "42501"}
}


class _SequencedClient:
    """Fake client returning one queued outcome per fallback SQL call."""

    def __init__(self, outcomes: list[Any]) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._outcomes = list(outcomes)

    async def execute_sql(self, **kwargs: Any) -> Any:
        self.calls.append(("execute_sql", kwargs))
        outcome = self._outcomes.pop(0) if self._outcomes else []
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _service(responses: dict[str, Any] | None = None) -> InspectionService:
    return InspectionService(
        client=FakeRdsSupabaseClient(responses),
        settings=make_settings(),
    )


def _sequenced_service(outcomes: list[Any]) -> InspectionService:
    return InspectionService(client=_SequencedClient(outcomes), settings=make_settings())


# ------------------------------------------------------- list_table_columns


async def test_list_table_columns_returns_rows() -> None:
    service = _service({"execute_sql": list(COLUMNS)})
    assert await service.list_table_columns(table="students") == COLUMNS
    name, kwargs = service._client.calls[0]
    assert name == "execute_sql"
    assert kwargs["read_only"] is True


async def test_list_table_columns_interpolates_schema_and_table() -> None:
    service = _service({"execute_sql": list(COLUMNS)})
    await service.list_table_columns(schema="app", table="students")
    query = service._client.calls[0][1]["query"]
    assert "FROM pg_catalog.pg_attribute a" in query
    assert "WHERE n.nspname = 'app'" in query
    assert "AND c.relname = 'students'" in query
    assert "ORDER BY a.attnum" in query


async def test_list_table_columns_rejects_invalid_schema() -> None:
    service = _service()
    with pytest.raises(McpToolError) as exc_info:
        await service.list_table_columns(schema="bad-schema", table="students")
    assert exc_info.value.code == "MCP_VALIDATION_ERROR"
    assert exc_info.value.message == "Invalid schema name: bad-schema"


async def test_list_table_columns_rejects_invalid_table() -> None:
    service = _service()
    with pytest.raises(McpToolError) as exc_info:
        await service.list_table_columns(table="students; DROP TABLE x")
    assert exc_info.value.message == "Invalid table name: students; DROP TABLE x"


async def test_list_table_columns_rejects_trailing_newline_identifier() -> None:
    service = _service()
    with pytest.raises(McpToolError) as exc_info:
        await service.list_table_columns(table="students\n")
    assert exc_info.value.message == "Invalid table name: students\n"


async def test_list_table_columns_raises_upstream_sql_error_message() -> None:
    service = _service({"execute_sql": SQL_ERROR})
    with pytest.raises(McpToolError) as exc_info:
        await service.list_table_columns(table="students")
    assert exc_info.value.code == "42501"
    assert exc_info.value.message == "permission denied for table pg_class"


async def test_list_table_columns_falls_back_when_message_missing() -> None:
    service = _service({"execute_sql": {"error": {"message": None, "code": None}}})
    with pytest.raises(McpToolError) as exc_info:
        await service.list_table_columns(table="students")
    assert exc_info.value.code == "MCP_SQL_ERROR"
    assert exc_info.value.message == "Failed to list table columns"


async def test_list_table_columns_not_found() -> None:
    service = _service({"execute_sql": []})
    with pytest.raises(McpToolError) as exc_info:
        await service.list_table_columns(schema="public", table="students")
    assert exc_info.value.code == "MCP_NOT_FOUND"
    assert exc_info.value.message == "Table public.students not found or has no columns."


# ------------------------------------------------------------- list_indexes


async def test_list_indexes_returns_rows() -> None:
    rows: list[dict[str, Any]] = [
        {
            "schema_name": "public",
            "table_name": "students",
            "index_name": "students_pkey",
            "index_type": "btree",
            "is_unique": True,
            "is_primary": True,
            "is_valid": True,
            "columns": "CREATE INDEX ...",
            "size": "16 kB",
            "definition": "CREATE UNIQUE INDEX ...",
        }
    ]
    service = _service({"execute_sql": rows})
    assert await service.list_indexes() == rows


async def test_list_indexes_default_query_excludes_system_schemas() -> None:
    service = _service()
    await service.list_indexes()
    query = service._client.calls[0][1]["query"]
    assert (
        "schemaname NOT IN ('pg_catalog', 'information_schema', 'pg_toast', "
        "'auth', 'storage', 'extensions', 'graphql', 'graphql_public', "
        "'pgbouncer', 'realtime', 'supabase_functions', 'supabase_migrations', "
        "'_realtime')" in query
    )
    assert "WHERE" in query


async def test_list_indexes_applies_schema_and_table_filters() -> None:
    service = _service()
    await service.list_indexes(schema="public", table="students")
    query = service._client.calls[0][1]["query"]
    assert "schemaname = 'public'" in query
    assert "tablename = 'students'" in query


async def test_list_indexes_include_system_drops_the_exclusion() -> None:
    service = _service()
    await service.list_indexes(include_system=True)
    query = service._client.calls[0][1]["query"]
    assert "schemaname NOT IN" not in query
    assert "WHERE" not in query


async def test_list_indexes_rejects_invalid_identifiers() -> None:
    service = _service()
    with pytest.raises(McpToolError) as exc_info:
        await service.list_indexes(schema="bad schema")
    assert exc_info.value.message == "Invalid schema name: bad schema"
    with pytest.raises(McpToolError) as exc_info:
        await service.list_indexes(table="bad;table")
    assert exc_info.value.message == "Invalid table name: bad;table"


async def test_list_indexes_raises_upstream_sql_error() -> None:
    service = _service({"execute_sql": SQL_ERROR})
    with pytest.raises(McpToolError) as exc_info:
        await service.list_indexes()
    assert exc_info.value.code == "42501"
    assert exc_info.value.message == "SQL Error (42501): permission denied for table pg_class"


# --------------------------------------------------------- list_constraints


async def test_list_constraints_returns_rows() -> None:
    rows: list[dict[str, Any]] = [
        {
            "schema_name": "public",
            "table_name": "students",
            "constraint_name": "students_pkey",
            "constraint_type": "PRIMARY KEY",
            "columns": ["id"],
            "definition": "PRIMARY KEY (id)",
            "is_deferrable": False,
            "initially_deferred": False,
        }
    ]
    service = _service({"execute_sql": rows})
    assert await service.list_constraints() == rows


async def test_list_constraints_maps_the_type_filter_to_its_code() -> None:
    service = _service()
    await service.list_constraints(constraint_type="PRIMARY KEY")
    query = service._client.calls[0][1]["query"]
    assert "c.contype = 'p'" in query


async def test_list_constraints_applies_table_filter() -> None:
    service = _service()
    await service.list_constraints(table="students")
    assert "rel.relname = 'students'" in service._client.calls[0][1]["query"]


async def test_list_constraints_include_system_drops_the_exclusion() -> None:
    service = _service()
    await service.list_constraints(include_system=True)
    query = service._client.calls[0][1]["query"]
    assert "n.nspname NOT IN" not in query
    assert "WHERE" not in query


async def test_list_constraints_rejects_invalid_schema() -> None:
    service = _service()
    with pytest.raises(McpToolError) as exc_info:
        await service.list_constraints(schema="bad(schema")
    assert exc_info.value.message == "Invalid schema name: bad(schema"


async def test_list_constraints_raises_upstream_sql_error() -> None:
    service = _service({"execute_sql": SQL_ERROR})
    with pytest.raises(McpToolError) as exc_info:
        await service.list_constraints()
    assert exc_info.value.message == "SQL Error (42501): permission denied for table pg_class"


# ------------------------------------------------------- list_foreign_keys


async def test_list_foreign_keys_returns_rows() -> None:
    rows: list[dict[str, Any]] = [
        {
            "constraint_name": "scores_student_id_fkey",
            "schema_name": "public",
            "table_name": "scores",
            "column_name": "student_id",
            "referenced_schema": "public",
            "referenced_table": "students",
            "referenced_column": "id",
            "update_rule": "NO ACTION",
            "delete_rule": "CASCADE",
            "is_deferrable": False,
            "initially_deferred": False,
        }
    ]
    service = _service({"execute_sql": rows})
    assert await service.list_foreign_keys() == rows


async def test_list_foreign_keys_default_query_keeps_the_foreign_key_gate() -> None:
    service = _service()
    await service.list_foreign_keys()
    query = service._client.calls[0][1]["query"]
    assert "WHERE tc.constraint_type = 'FOREIGN KEY'" in query
    assert (
        "tc.table_schema NOT IN ('pg_catalog', 'information_schema', 'auth', "
        "'storage', 'extensions', 'graphql', 'graphql_public', 'pgbouncer', "
        "'realtime', 'supabase_functions', 'supabase_migrations', '_realtime')" in query
    )
    assert "AND tc.table_schema NOT IN" in query


async def test_list_foreign_keys_applies_filters() -> None:
    service = _service()
    await service.list_foreign_keys(schema="public", table="scores")
    query = service._client.calls[0][1]["query"]
    assert "tc.table_schema = 'public'" in query
    assert "tc.table_name = 'scores'" in query


async def test_list_foreign_keys_rejects_invalid_table() -> None:
    service = _service()
    with pytest.raises(McpToolError) as exc_info:
        await service.list_foreign_keys(table="bad-table")
    assert exc_info.value.message == "Invalid table name: bad-table"


async def test_list_foreign_keys_raises_upstream_sql_error() -> None:
    service = _service({"execute_sql": SQL_ERROR})
    with pytest.raises(McpToolError) as exc_info:
        await service.list_foreign_keys()
    assert exc_info.value.message == "SQL Error (42501): permission denied for table pg_class"


# -------------------------------------------------------- list_rls_policies


async def test_list_rls_policies_returns_rows() -> None:
    rows: list[dict[str, Any]] = [
        {
            "schema_name": "public",
            "table_name": "students",
            "policy_name": "students_select_own",
            "command": "SELECT",
            "policy_type": "PERMISSIVE",
            "roles": ["authenticated"],
            "using_expression": "auth.uid() = user_id",
            "with_check_expression": None,
        }
    ]
    service = _service({"execute_sql": rows})
    assert await service.list_rls_policies() == rows


async def test_list_rls_policies_default_query_has_base_exclusion() -> None:
    service = _service()
    await service.list_rls_policies()
    query = service._client.calls[0][1]["query"]
    assert (
        "WHERE n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')" in query
    )


async def test_list_rls_policies_applies_filters() -> None:
    service = _service()
    await service.list_rls_policies(schema="public", table="students")
    query = service._client.calls[0][1]["query"]
    assert "n.nspname = 'public'" in query
    assert "c.relname = 'students'" in query


async def test_list_rls_policies_rejects_invalid_schema() -> None:
    service = _service()
    with pytest.raises(McpToolError) as exc_info:
        await service.list_rls_policies(schema="bad'schema")
    assert exc_info.value.message == "Invalid schema name: bad'schema"


async def test_list_rls_policies_raises_upstream_sql_error() -> None:
    service = _service({"execute_sql": SQL_ERROR})
    with pytest.raises(McpToolError) as exc_info:
        await service.list_rls_policies()
    assert exc_info.value.message == "SQL Error (42501): permission denied for table pg_class"


# ------------------------------------------------------------ list_triggers


async def test_list_triggers_returns_rows() -> None:
    rows: list[dict[str, Any]] = [
        {
            "schema_name": "public",
            "table_name": "students",
            "trigger_name": "set_updated_at",
            "trigger_timing": "BEFORE",
            "trigger_level": "ROW",
            "events": ["UPDATE"],
            "function_schema": "public",
            "function_name": "set_updated_at",
            "enabled": "ENABLED",
        }
    ]
    service = _service({"execute_sql": rows})
    assert await service.list_triggers() == rows


async def test_list_triggers_default_query_excludes_internal_triggers() -> None:
    service = _service()
    await service.list_triggers()
    query = service._client.calls[0][1]["query"]
    assert "NOT t.tgisinternal" in query
    assert (
        "n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')" in query
    )


async def test_list_triggers_applies_filters() -> None:
    service = _service()
    await service.list_triggers(schema="app", table="students")
    query = service._client.calls[0][1]["query"]
    assert "n.nspname = 'app'" in query
    assert "c.relname = 'students'" in query


async def test_list_triggers_rejects_invalid_table() -> None:
    service = _service()
    with pytest.raises(McpToolError) as exc_info:
        await service.list_triggers(table="drop table")
    assert exc_info.value.message == "Invalid table name: drop table"


async def test_list_triggers_raises_upstream_sql_error() -> None:
    service = _service({"execute_sql": SQL_ERROR})
    with pytest.raises(McpToolError) as exc_info:
        await service.list_triggers()
    assert exc_info.value.message == "SQL Error (42501): permission denied for table pg_class"


# -------------------------------------------------- list_database_functions


async def test_list_database_functions_returns_rows() -> None:
    rows: list[dict[str, Any]] = [
        {
            "schema_name": "public",
            "function_name": "do_thing",
            "arguments": "integer, text",
            "return_type": "void",
            "language": "plpgsql",
            "volatility": "VOLATILE",
            "security_definer": True,
            "description": None,
        }
    ]
    service = _service({"execute_sql": rows})
    assert await service.list_database_functions() == rows


async def test_list_database_functions_default_query_has_base_conditions() -> None:
    service = _service()
    await service.list_database_functions()
    query = service._client.calls[0][1]["query"]
    assert (
        "WHERE n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')" in query
    )
    assert "n.nspname NOT LIKE 'pg_temp_%'" in query
    assert "p.prokind = 'f'" in query


async def test_list_database_functions_applies_all_filters() -> None:
    service = _service()
    await service.list_database_functions(
        schema="public", name_pattern="get_%", language="plpgsql"
    )
    query = service._client.calls[0][1]["query"]
    assert "n.nspname = 'public'" in query
    assert "p.proname LIKE 'get_%'" in query
    assert "l.lanname = 'plpgsql'" in query


async def test_list_database_functions_rejects_invalid_schema_and_language() -> None:
    service = _service()
    with pytest.raises(McpToolError) as exc_info:
        await service.list_database_functions(schema="bad schema")
    assert exc_info.value.message == "Invalid schema name: bad schema"
    with pytest.raises(McpToolError) as exc_info:
        await service.list_database_functions(language="plpgsql; DROP")
    assert exc_info.value.message == "Invalid language name: plpgsql; DROP"


async def test_list_database_functions_rejects_invalid_name_pattern() -> None:
    service = _service()
    with pytest.raises(McpToolError) as exc_info:
        await service.list_database_functions(name_pattern="bad;pattern")
    assert exc_info.value.code == "MCP_VALIDATION_ERROR"
    assert exc_info.value.message == (
        "Invalid name pattern: bad;pattern. Use only alphanumeric, underscore, "
        "dollar sign, and % wildcard."
    )


async def test_list_database_functions_raises_upstream_sql_error() -> None:
    service = _service({"execute_sql": SQL_ERROR})
    with pytest.raises(McpToolError) as exc_info:
        await service.list_database_functions()
    assert exc_info.value.message == "SQL Error (42501): permission denied for table pg_class"


# ---------------------------------------------------- get_function_definition


async def test_get_function_definition_returns_the_first_row() -> None:
    row: dict[str, Any] = {
        "schema_name": "public",
        "function_name": "do_thing",
        "arguments": "integer, text",
        "return_type": "void",
        "language": "plpgsql",
        "volatility": "VOLATILE",
        "security_definer": False,
        "definition": "CREATE FUNCTION ...",
    }
    service = _service({"execute_sql": [row, {"extra": "ignored"}]})
    assert await service.get_function_definition(function_name="do_thing") == row


async def test_get_function_definition_matches_argument_types() -> None:
    service = _service({"execute_sql": [{"schema_name": "public"}]})
    await service.get_function_definition(function_name="do_thing", argument_types="integer")
    query = service._client.calls[0][1]["query"]
    assert (
        "AND pg_catalog.pg_get_function_arguments(p.oid) = 'integer'" in query
    )
    assert "LIMIT 1" in query


async def test_get_function_definition_rejects_invalid_identifiers() -> None:
    service = _service()
    with pytest.raises(McpToolError) as exc_info:
        await service.get_function_definition(schema="bad-schema", function_name="do_thing")
    assert exc_info.value.message == "Invalid schema name: bad-schema"
    with pytest.raises(McpToolError) as exc_info:
        await service.get_function_definition(function_name="do thing")
    assert exc_info.value.message == "Invalid function name: do thing"
    with pytest.raises(McpToolError) as exc_info:
        await service.get_function_definition(
            function_name="do_thing", argument_types="integer; DROP"
        )
    assert exc_info.value.message == "Invalid argument types format: integer; DROP"


async def test_get_function_definition_raises_upstream_sql_error_message() -> None:
    service = _service({"execute_sql": SQL_ERROR})
    with pytest.raises(McpToolError) as exc_info:
        await service.get_function_definition(function_name="do_thing")
    assert exc_info.value.code == "42501"
    assert exc_info.value.message == "permission denied for table pg_class"


async def test_get_function_definition_not_found_without_arguments() -> None:
    service = _service({"execute_sql": []})
    with pytest.raises(McpToolError) as exc_info:
        await service.get_function_definition(schema="public", function_name="do_thing")
    assert exc_info.value.code == "MCP_NOT_FOUND"
    assert exc_info.value.message == "Function public.do_thing not found."


async def test_get_function_definition_not_found_with_argument_types() -> None:
    service = _service({"execute_sql": []})
    with pytest.raises(McpToolError) as exc_info:
        await service.get_function_definition(
            schema="public", function_name="do_thing", argument_types="integer, text"
        )
    assert exc_info.value.message == "Function public.do_thing(integer, text) not found."


async def test_get_function_definition_falls_back_when_message_missing() -> None:
    service = _service({"execute_sql": {"error": {"message": None, "code": None}}})
    with pytest.raises(McpToolError) as exc_info:
        await service.get_function_definition(function_name="do_thing")
    assert exc_info.value.message == "Failed to get function definition"


async def test_get_trigger_definition_falls_back_when_message_missing() -> None:
    service = _service({"execute_sql": {"error": {"message": None, "code": None}}})
    with pytest.raises(McpToolError) as exc_info:
        await service.get_trigger_definition(table="students", trigger_name="trg")
    assert exc_info.value.message == "Failed to get trigger definition"


# ---------------------------------------------------- get_trigger_definition


async def test_get_trigger_definition_returns_the_row() -> None:
    row: dict[str, Any] = {
        "schema_name": "public",
        "table_name": "students",
        "trigger_name": "set_updated_at",
        "trigger_timing": "BEFORE",
        "trigger_level": "ROW",
        "events": ["UPDATE"],
        "function_schema": "public",
        "function_name": "set_updated_at",
        "enabled": "ENABLED",
        "definition": "CREATE TRIGGER ...",
        "function_definition": "CREATE FUNCTION ...",
    }
    service = _service({"execute_sql": [row]})
    result = await service.get_trigger_definition(table="students", trigger_name="set_updated_at")
    assert result == row


async def test_get_trigger_definition_includes_the_function_by_default() -> None:
    service = _service({"execute_sql": []})
    with pytest.raises(McpToolError):
        await service.get_trigger_definition(table="students", trigger_name="trg")
    query = service._client.calls[0][1]["query"]
    assert "pg_catalog.pg_get_functiondef(p.oid) AS function_definition" in query
    assert "WHERE n.nspname = 'public'" in query
    assert "AND c.relname = 'students'" in query
    assert "AND t.tgname = 'trg'" in query


async def test_get_trigger_definition_excludes_the_function_on_demand() -> None:
    service = _service({"execute_sql": []})
    with pytest.raises(McpToolError):
        await service.get_trigger_definition(
            table="students", trigger_name="trg", include_function=False
        )
    assert "NULL AS function_definition" in service._client.calls[0][1]["query"]


async def test_get_trigger_definition_rejects_invalid_trigger_name() -> None:
    service = _service()
    with pytest.raises(McpToolError) as exc_info:
        await service.get_trigger_definition(table="students", trigger_name="bad trigger")
    assert exc_info.value.message == "Invalid trigger name: bad trigger"


async def test_get_trigger_definition_raises_upstream_sql_error_message() -> None:
    service = _service({"execute_sql": SQL_ERROR})
    with pytest.raises(McpToolError) as exc_info:
        await service.get_trigger_definition(table="students", trigger_name="trg")
    assert exc_info.value.code == "42501"
    assert exc_info.value.message == "permission denied for table pg_class"


async def test_get_trigger_definition_not_found() -> None:
    service = _service({"execute_sql": []})
    with pytest.raises(McpToolError) as exc_info:
        await service.get_trigger_definition(
            schema="public", table="students", trigger_name="trg"
        )
    assert exc_info.value.code == "MCP_NOT_FOUND"
    assert exc_info.value.message == 'Trigger "trg" not found on public.students.'


# ------------------------------------------------------------ get_rls_status


async def test_get_rls_status_returns_rows() -> None:
    rows: list[dict[str, Any]] = [
        {
            "schema_name": "public",
            "table_name": "students",
            "rls_enabled": True,
            "rls_forced": False,
            "policy_count": 2,
        }
    ]
    service = _service({"execute_sql": rows})
    assert await service.get_rls_status() == rows


async def test_get_rls_status_default_query_gates_on_ordinary_tables() -> None:
    service = _service()
    await service.get_rls_status()
    query = service._client.calls[0][1]["query"]
    assert "c.relkind = 'r'" in query
    assert (
        "n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast', 'auth', "
        "'storage', 'extensions', 'graphql', 'graphql_public', 'pgbouncer', "
        "'realtime', 'supabase_functions', 'supabase_migrations', '_realtime')" in query
    )


async def test_get_rls_status_applies_filters() -> None:
    service = _service()
    await service.get_rls_status(schema="public", table="students")
    query = service._client.calls[0][1]["query"]
    assert "n.nspname = 'public'" in query
    assert "c.relname = 'students'" in query


async def test_get_rls_status_rejects_invalid_table() -> None:
    service = _service()
    with pytest.raises(McpToolError) as exc_info:
        await service.get_rls_status(table="bad'table")
    assert exc_info.value.message == "Invalid table name: bad'table"


async def test_get_rls_status_raises_upstream_sql_error() -> None:
    service = _service({"execute_sql": SQL_ERROR})
    with pytest.raises(McpToolError) as exc_info:
        await service.get_rls_status()
    assert exc_info.value.message == "SQL Error (42501): permission denied for table pg_class"


# -------------------------------------------------- list_available_extensions


async def test_list_available_extensions_returns_rows() -> None:
    rows: list[dict[str, Any]] = [
        {
            "name": "vector",
            "default_version": "0.8.0",
            "installed_version": None,
            "is_installed": False,
            "comment": "vector data type and ivfflat/hnsw access methods",
        }
    ]
    service = _service({"execute_sql": rows})
    assert await service.list_available_extensions() == rows


async def test_list_available_extensions_default_query_has_no_where() -> None:
    service = _service()
    await service.list_available_extensions()
    query = service._client.calls[0][1]["query"]
    assert "FROM pg_available_extensions" in query
    assert "WHERE" not in query


async def test_list_available_extensions_only_not_installed() -> None:
    service = _service()
    await service.list_available_extensions(show_installed=False)
    assert "installed_version IS NULL" in service._client.calls[0][1]["query"]


async def test_list_available_extensions_applies_name_pattern() -> None:
    service = _service()
    await service.list_available_extensions(name_pattern="vec%")
    assert "name LIKE 'vec%'" in service._client.calls[0][1]["query"]


async def test_list_available_extensions_rejects_invalid_name_pattern() -> None:
    service = _service()
    with pytest.raises(McpToolError) as exc_info:
        await service.list_available_extensions(name_pattern="bad;pattern")
    assert exc_info.value.code == "MCP_VALIDATION_ERROR"
    assert exc_info.value.message == (
        "Invalid name pattern: bad;pattern. Use only alphanumeric, underscore, "
        "hyphen, dollar sign, and % wildcard."
    )


async def test_list_available_extensions_raises_upstream_sql_error() -> None:
    service = _service({"execute_sql": SQL_ERROR})
    with pytest.raises(McpToolError) as exc_info:
        await service.list_available_extensions()
    assert exc_info.value.message == "SQL Error (42501): permission denied for table pg_class"


# ---------------------------------------------------- get_cron_job_history


async def test_get_cron_job_history_returns_rows() -> None:
    rows: list[dict[str, Any]] = [
        {
            "jobid": 1,
            "jobname": "nightly-vacuum",
            "schedule": "0 3 * * *",
            "runid": 10,
            "status": "succeeded",
            "start_time": "2026-01-01 03:00:00+00",
            "end_time": "2026-01-01 03:00:02+00",
            "return_message": None,
        }
    ]
    service = _sequenced_service([[{"installed": True}], rows])
    assert await service.get_cron_job_history() == rows
    check_call, history_call = service._client.calls
    assert "pg_cron" in check_call[1]["query"]
    assert check_call[1]["read_only"] is True
    assert "FROM cron.job j" in history_call[1]["query"]


async def test_get_cron_job_history_checks_the_extension_first() -> None:
    service = _sequenced_service([[{"installed": False}]])
    with pytest.raises(McpToolError) as exc_info:
        await service.get_cron_job_history()
    assert exc_info.value.code == "MCP_EXTENSION_NOT_INSTALLED"
    assert exc_info.value.message == (
        "pg_cron extension is not installed. Install it with: CREATE EXTENSION pg_cron;"
    )
    assert len(service._client.calls) == 1


async def test_get_cron_job_history_reports_check_failure() -> None:
    service = _service({"execute_sql": SQL_ERROR})
    with pytest.raises(McpToolError) as exc_info:
        await service.get_cron_job_history()
    assert exc_info.value.code == "MCP_SQL_ERROR"
    assert exc_info.value.message == "Failed to check pg_cron extension status."


async def test_get_cron_job_history_reports_empty_check_result() -> None:
    service = _sequenced_service([[]])
    with pytest.raises(McpToolError) as exc_info:
        await service.get_cron_job_history()
    assert exc_info.value.message == "Failed to check pg_cron extension status."


async def test_get_cron_job_history_rejects_invalid_jobname() -> None:
    service = _sequenced_service([])
    with pytest.raises(McpToolError) as exc_info:
        await service.get_cron_job_history(jobname="bad;job")
    assert exc_info.value.code == "MCP_VALIDATION_ERROR"
    assert exc_info.value.message == (
        "Invalid job name pattern: bad;job. Use only alphanumeric, underscore, "
        "hyphen, and space characters."
    )


async def test_get_cron_job_history_applies_all_filters() -> None:
    service = _sequenced_service([[{"installed": True}], []])
    await service.get_cron_job_history(jobid=5, jobname="nightly", status="failed", limit=10)
    query = service._client.calls[1][1]["query"]
    assert "j.jobid = 5" in query
    assert "j.jobname ILIKE '%nightly%'" in query
    assert "r.status = 'failed'" in query
    assert "LIMIT 10" in query


async def test_get_cron_job_history_clamps_the_limit() -> None:
    service = _sequenced_service([[{"installed": True}], []])
    await service.get_cron_job_history(limit=5000)
    assert "LIMIT 1000" in service._client.calls[1][1]["query"]
    service = _sequenced_service([[{"installed": True}], []])
    await service.get_cron_job_history(limit=0)
    assert "LIMIT 1" in service._client.calls[1][1]["query"]


async def test_get_cron_job_history_default_query_has_no_where() -> None:
    service = _sequenced_service([[{"installed": True}], []])
    await service.get_cron_job_history()
    query = service._client.calls[1][1]["query"]
    assert "WHERE" not in query
    assert "LIMIT 100" in query


async def test_get_cron_job_history_raises_upstream_sql_error() -> None:
    service = _sequenced_service([[{"installed": True}], SQL_ERROR])
    with pytest.raises(McpToolError) as exc_info:
        await service.get_cron_job_history()
    assert exc_info.value.message == "SQL Error (42501): permission denied for table pg_class"


# ------------------------------------------------------------ get_index_stats


async def test_get_index_stats_returns_the_row() -> None:
    row: dict[str, Any] = {
        "schema_name": "public",
        "table_name": "students",
        "index_name": "students_pkey",
        "index_type": "btree",
        "is_unique": True,
        "is_primary": True,
        "is_valid": True,
        "number_of_scans": 42,
        "tuples_read": 420,
        "tuples_fetched": 410,
        "index_size": "16 kB",
        "table_size": "8192 bytes",
        "index_size_bytes": 16384,
        "table_size_bytes": 8192,
        "usage_ratio": "80.00%",
    }
    service = _service({"execute_sql": [row]})
    assert await service.get_index_stats(index_name="students_pkey") == row


async def test_get_index_stats_interpolates_schema_and_index() -> None:
    service = _service({"execute_sql": []})
    with pytest.raises(McpToolError):
        await service.get_index_stats(schema="app", index_name="idx")
    query = service._client.calls[0][1]["query"]
    assert "FROM pg_stat_user_indexes s" in query
    assert "WHERE s.schemaname = 'app'" in query
    assert "AND s.indexrelname = 'idx'" in query


async def test_get_index_stats_rejects_invalid_identifiers() -> None:
    service = _service()
    with pytest.raises(McpToolError) as exc_info:
        await service.get_index_stats(schema="bad schema", index_name="idx")
    assert exc_info.value.code == "MCP_VALIDATION_ERROR"
    assert exc_info.value.message == (
        "Invalid schema name: bad schema. Must be a valid SQL identifier."
    )
    with pytest.raises(McpToolError) as exc_info:
        await service.get_index_stats(index_name="bad;index")
    assert exc_info.value.message == (
        "Invalid index name: bad;index. Must be a valid SQL identifier."
    )


async def test_get_index_stats_raises_upstream_sql_error_message() -> None:
    service = _service({"execute_sql": SQL_ERROR})
    with pytest.raises(McpToolError) as exc_info:
        await service.get_index_stats(index_name="idx")
    assert exc_info.value.code == "42501"
    assert exc_info.value.message == "permission denied for table pg_class"


async def test_get_index_stats_not_found() -> None:
    service = _service({"execute_sql": []})
    with pytest.raises(McpToolError) as exc_info:
        await service.get_index_stats(schema="public", index_name="idx")
    assert exc_info.value.code == "MCP_NOT_FOUND"
    assert exc_info.value.message == 'Index "idx" not found in schema "public".'


async def test_get_index_stats_falls_back_when_message_missing() -> None:
    service = _service({"execute_sql": {"error": {"message": None, "code": None}}})
    with pytest.raises(McpToolError) as exc_info:
        await service.get_index_stats(index_name="idx")
    assert exc_info.value.message == "Failed to get index stats"


# ---------------------------------------------------- get_vector_index_stats


async def test_get_vector_index_stats_returns_rows() -> None:
    rows: list[dict[str, Any]] = [
        {
            "schemaname": "public",
            "tablename": "docs",
            "indexname": "docs_embedding_idx",
            "index_type": "HNSW",
            "idx_scan": 3,
            "idx_tup_read": 300,
            "idx_tup_fetch": 30,
            "index_size": "152 MB",
            "index_size_bytes": 159383552,
        }
    ]
    service = _sequenced_service([[{"installed": True}], rows])
    assert await service.get_vector_index_stats() == rows
    check_call, stats_call = service._client.calls
    assert "extname = 'vector'" in check_call[1]["query"]
    assert "WITH vector_indexes AS (" in stats_call[1]["query"]


async def test_get_vector_index_stats_checks_the_extension_first() -> None:
    service = _sequenced_service([[{"installed": False}]])
    with pytest.raises(McpToolError) as exc_info:
        await service.get_vector_index_stats()
    assert exc_info.value.code == "MCP_EXTENSION_NOT_INSTALLED"
    assert exc_info.value.message == (
        "pgvector extension is not installed. Install it with: CREATE EXTENSION vector;"
    )
    assert len(service._client.calls) == 1


async def test_get_vector_index_stats_empty_check_reports_not_installed() -> None:
    service = _sequenced_service([[]])
    with pytest.raises(McpToolError) as exc_info:
        await service.get_vector_index_stats()
    assert exc_info.value.message == (
        "pgvector extension is not installed. Install it with: CREATE EXTENSION vector;"
    )


async def test_get_vector_index_stats_check_error_propagates_message() -> None:
    service = _service({"execute_sql": SQL_ERROR})
    with pytest.raises(McpToolError) as exc_info:
        await service.get_vector_index_stats()
    assert exc_info.value.code == "42501"
    assert exc_info.value.message == "permission denied for table pg_class"


async def test_get_vector_index_stats_check_error_falls_back() -> None:
    service = _service({"execute_sql": {"error": {"message": None, "code": None}}})
    with pytest.raises(McpToolError) as exc_info:
        await service.get_vector_index_stats()
    assert exc_info.value.code == "MCP_SQL_ERROR"
    assert exc_info.value.message == "Failed to check pgvector extension status."


async def test_get_vector_index_stats_rejects_invalid_identifiers() -> None:
    service = _sequenced_service([])
    with pytest.raises(McpToolError) as exc_info:
        await service.get_vector_index_stats(schema="bad schema")
    assert exc_info.value.message == (
        "Invalid schema name: bad schema. Must be a valid SQL identifier."
    )
    with pytest.raises(McpToolError) as exc_info:
        await service.get_vector_index_stats(table="bad;table")
    assert exc_info.value.message == (
        "Invalid table name: bad;table. Must be a valid SQL identifier."
    )
    with pytest.raises(McpToolError) as exc_info:
        await service.get_vector_index_stats(indexname="bad;index")
    assert exc_info.value.message == (
        "Invalid index name: bad;index. Must be a valid SQL identifier."
    )


async def test_get_vector_index_stats_applies_filters() -> None:
    service = _sequenced_service([[{"installed": True}], []])
    await service.get_vector_index_stats(schema="public", table="docs", indexname="idx")
    query = service._client.calls[1][1]["query"]
    assert "s.schemaname = 'public'" in query
    assert "s.relname = 'docs'" in query
    assert "s.indexrelname = 'idx'" in query


async def test_get_vector_index_stats_default_query_keeps_the_where_anchor() -> None:
    service = _sequenced_service([[{"installed": True}], []])
    await service.get_vector_index_stats()
    query = service._client.calls[1][1]["query"]
    assert "WHERE 1=1" in query
    assert "s.schemaname =" not in query


async def test_get_vector_index_stats_raises_upstream_sql_error() -> None:
    service = _sequenced_service([[{"installed": True}], SQL_ERROR])
    with pytest.raises(McpToolError) as exc_info:
        await service.get_vector_index_stats()
    assert exc_info.value.message == "SQL Error (42501): permission denied for table pg_class"


# ------------------------------------------------------------- explain_query


async def test_explain_query_parses_the_json_plan_with_timings() -> None:
    plan: list[dict[str, Any]] = [
        {"Plan": {"Node Type": "Seq Scan"}, "Planning Time": 0.42, "Execution Time": 1.5}
    ]
    service = _service({"execute_sql": [{"QUERY PLAN": plan}]})
    result = await service.explain_query(sql="SELECT 1")
    assert result == {
        "query": "SELECT 1",
        "plan": plan,
        "format": "json",
        "analyzed": False,
        "planning_time_ms": 0.42,
        "execution_time_ms": 1.5,
    }
    call = service._client.calls[0]
    assert call[1]["query"] == "EXPLAIN (FORMAT JSON, COSTS true) SELECT 1"
    assert call[1]["read_only"] is True


async def test_explain_query_key_order_matches_the_upstream_object() -> None:
    plan: list[dict[str, Any]] = [{"Plan": {}, "Planning Time": 0.1, "Execution Time": 0.2}]
    service = _service({"execute_sql": [{"QUERY PLAN": plan}]})
    result = await service.explain_query(sql="SELECT 1", analyze=True)
    assert list(result) == [
        "query",
        "plan",
        "format",
        "analyzed",
        "planning_time_ms",
        "execution_time_ms",
        "warnings",
    ]


async def test_explain_query_analyze_executes_with_write_warning() -> None:
    service = _service({"execute_sql": []})
    await service.explain_query(sql="INSERT INTO t VALUES (1)", analyze=True)
    call = service._client.calls[0]
    assert call[1]["read_only"] is False
    assert call[1]["query"].startswith(
        "EXPLAIN (FORMAT JSON, ANALYZE true, COSTS true, TIMING true) INSERT INTO t VALUES (1)"
    )


async def test_explain_query_analyze_warns_on_write_and_keeps_timing() -> None:
    service = _service({"execute_sql": [{"QUERY PLAN": []}]})
    result = await service.explain_query(sql="DELETE FROM t", analyze=True)
    assert result["warnings"] == [
        "⚠️ CRITICAL: ANALYZE will EXECUTE this DELETE query and MODIFY DATA!"
    ]
    assert result["analyzed"] is True


async def test_explain_query_analyze_warns_on_mixed_cte_queries() -> None:
    service = _service({"execute_sql": []})
    result = await service.explain_query(
        sql="WITH moved AS (DELETE FROM t RETURNING *) SELECT * FROM moved", analyze=True
    )
    assert result["warnings"] == [
        "⚠️ WARNING: Query may contain MIXED/CTE operations. ANALYZE will execute the query."
    ]


async def test_explain_query_analyze_notes_execution_for_reads() -> None:
    service = _service({"execute_sql": []})
    result = await service.explain_query(sql="SELECT 1", analyze=True)
    assert result["warnings"] == [
        "Note: ANALYZE will execute the query to measure actual timing."
    ]


async def test_explain_query_without_analyze_has_no_warnings() -> None:
    service = _service({"execute_sql": [{"QUERY PLAN": []}]})
    result = await service.explain_query(sql="SELECT 1")
    assert "warnings" not in result


async def test_explain_query_builds_the_full_options_list() -> None:
    service = _service({"execute_sql": []})
    await service.explain_query(
        sql="SELECT 1",
        analyze=True,
        format="text",
        verbose=True,
        costs=False,
        buffers=True,
        timing=False,
        settings=True,
    )
    assert service._client.calls[0][1]["query"] == (
        "EXPLAIN (FORMAT TEXT, ANALYZE true, VERBOSE true, COSTS false, "
        "BUFFERS true, TIMING false, SETTINGS true) SELECT 1"
    )


async def test_explain_query_text_format_maps_the_plan_rows() -> None:
    service = _service(
        {
            "execute_sql": [
                {"QUERY PLAN": "Seq Scan on t"},
                {"query plan": "  Filter: (id > 1)"},
                {"other": "row"},
            ]
        }
    )
    result = await service.explain_query(sql="SELECT 1", format="text")
    assert result["plan"] == ["Seq Scan on t", "  Filter: (id > 1)", {"other": "row"}]
    assert "planning_time_ms" not in result
    assert "execution_time_ms" not in result


async def test_explain_query_json_format_with_empty_rows_omits_the_plan() -> None:
    service = _service({"execute_sql": []})
    result = await service.explain_query(sql="SELECT 1")
    assert result == {"query": "SELECT 1", "format": "json", "analyzed": False}


async def test_explain_query_json_format_non_list_plan_passes_through() -> None:
    service = _service({"execute_sql": [{"QUERY PLAN": {"Plan": {}}}]})
    result = await service.explain_query(sql="SELECT 1")
    assert result["plan"] == {"Plan": {}}


async def test_explain_query_wraps_sql_errors() -> None:
    service = _service(
        {
            "execute_sql": {
                "error": {"message": 'syntax error at or near "FROM"', "code": "42601"}
            }
        }
    )
    with pytest.raises(McpToolError) as exc_info:
        await service.explain_query(sql="SELEC 1")
    assert exc_info.value.code == "42601"
    assert exc_info.value.message == 'Failed to explain query: syntax error at or near "FROM"'


async def test_explain_query_error_fallback_doubles_up() -> None:
    service = _service({"execute_sql": {"error": {"message": None, "code": None}}})
    with pytest.raises(McpToolError) as exc_info:
        await service.explain_query(sql="SELECT 1")
    assert exc_info.value.code == "MCP_SQL_ERROR"
    assert exc_info.value.message == "Failed to explain query: Failed to explain query"


_TOOL_NAMES = (
    "list_table_columns",
    "list_indexes",
    "list_constraints",
    "list_foreign_keys",
    "list_rls_policies",
    "list_triggers",
    "list_database_functions",
    "get_function_definition",
    "get_trigger_definition",
    "get_rls_status",
    "list_available_extensions",
    "get_cron_job_history",
    "get_index_stats",
    "get_vector_index_stats",
    "explain_query",
)


# --------------------------------------------------------- tools layer


def test_tool_risk_lanes_match_the_group() -> None:
    for name in _TOOL_NAMES:
        assert get_tool_risk(name) is ToolRisk.READ, name


def test_tool_docstrings_start_with_upstream_descriptions() -> None:
    tools = {name: getattr(inspection_tools, name) for name in _TOOL_NAMES}
    upstream = {
        "list_table_columns": (
            "Lists all columns for a table with detailed metadata including types, "
            "defaults, and constraints."
        ),
        "list_indexes": (
            "Lists all indexes in the database with their definitions and sizes. "
            "Can filter by schema and/or table."
        ),
        "list_constraints": (
            "Lists all constraints (PRIMARY KEY, FOREIGN KEY, UNIQUE, CHECK, EXCLUDE) "
            "in the database. Can filter by schema, table, and type."
        ),
        "list_foreign_keys": (
            "Lists all foreign key relationships in the database. "
            "Can filter by schema and/or table."
        ),
        "list_rls_policies": (
            "Lists all Row Level Security (RLS) policies in the database. "
            "Can filter by schema and/or table name."
        ),
        "list_triggers": "Lists all triggers on tables. Can filter by schema and/or table name.",
        "list_database_functions": (
            "Lists all user-defined database functions (stored procedures). Can filter "
            "by schema, name pattern, or language. Identifies SECURITY DEFINER "
            "functions which may have elevated privileges."
        ),
        "get_function_definition": (
            "Gets the full source code definition of a database function. "
            "Use argument_types if there are overloaded functions with the same name."
        ),
        "get_trigger_definition": (
            "Gets the full definition of a trigger, optionally including its function "
            "source code."
        ),
        "get_rls_status": (
            "Checks if Row Level Security (RLS) is enabled on tables and shows the "
            "number of policies. Can filter by schema and/or table."
        ),
        "list_available_extensions": (
            "Lists all PostgreSQL extensions available for installation, "
            "including those already installed."
        ),
        "get_cron_job_history": (
            "Gets execution history for pg_cron jobs including status and timing. "
            "Requires pg_cron to be installed."
        ),
        "get_index_stats": (
            "Gets detailed statistics for a specific index including usage counts and size."
        ),
        "get_vector_index_stats": (
            "Gets usage statistics and size information for pgvector indexes."
        ),
        "explain_query": (
            "Gets the execution plan for a SQL query. WARNING: With ANALYZE enabled, "
            "the query is actually executed which will modify data for write operations."
        ),
    }
    for name, function in tools.items():
        docstring = function.__doc__ or ""
        assert docstring.splitlines()[0] == upstream[name], name


async def test_tool_functions_delegate_to_the_service(monkeypatch: pytest.MonkeyPatch) -> None:
    class StubService:
        async def list_table_columns(
            self, *, schema: str, table: str
        ) -> list[dict[str, Any]]:
            return [{"schema": schema, "table": table}]

        async def list_indexes(
            self, *, schema: str | None, table: str | None, include_system: bool
        ) -> list[dict[str, Any]]:
            return [{"schema": schema, "table": table, "include_system": include_system}]

        async def list_constraints(
            self,
            *,
            schema: str | None,
            table: str | None,
            constraint_type: str | None,
            include_system: bool,
        ) -> list[dict[str, Any]]:
            return [
                {
                    "schema": schema,
                    "table": table,
                    "constraint_type": constraint_type,
                    "include_system": include_system,
                }
            ]

        async def list_foreign_keys(
            self, *, schema: str | None, table: str | None, include_system: bool
        ) -> list[dict[str, Any]]:
            return [{"schema": schema, "table": table, "include_system": include_system}]

        async def list_rls_policies(
            self, *, schema: str | None, table: str | None
        ) -> list[dict[str, Any]]:
            return [{"schema": schema, "table": table}]

        async def list_triggers(
            self, *, schema: str | None, table: str | None
        ) -> list[dict[str, Any]]:
            return [{"schema": schema, "table": table}]

        async def list_database_functions(
            self, *, schema: str | None, name_pattern: str | None, language: str | None
        ) -> list[dict[str, Any]]:
            return [{"schema": schema, "name_pattern": name_pattern, "language": language}]

        async def get_function_definition(
            self, *, schema: str, function_name: str, argument_types: str | None
        ) -> dict[str, Any]:
            return {
                "schema": schema,
                "function_name": function_name,
                "argument_types": argument_types,
            }

        async def get_trigger_definition(
            self,
            *,
            schema: str,
            table: str,
            trigger_name: str,
            include_function: bool,
        ) -> dict[str, Any]:
            return {
                "schema": schema,
                "table": table,
                "trigger_name": trigger_name,
                "include_function": include_function,
            }

        async def get_rls_status(
            self, *, schema: str | None, table: str | None
        ) -> list[dict[str, Any]]:
            return [{"schema": schema, "table": table}]

        async def list_available_extensions(
            self, *, show_installed: bool, name_pattern: str | None
        ) -> list[dict[str, Any]]:
            return [{"show_installed": show_installed, "name_pattern": name_pattern}]

        async def get_cron_job_history(
            self,
            *,
            jobid: int | None,
            jobname: str | None,
            limit: int,
            status: str | None,
        ) -> list[dict[str, Any]]:
            return [{"jobid": jobid, "jobname": jobname, "limit": limit, "status": status}]

        async def get_index_stats(self, *, schema: str, index_name: str) -> dict[str, Any]:
            return {"schema": schema, "index_name": index_name}

        async def get_vector_index_stats(
            self, *, schema: str | None, table: str | None, indexname: str | None
        ) -> list[dict[str, Any]]:
            return [{"schema": schema, "table": table, "indexname": indexname}]

        async def explain_query(
            self,
            *,
            sql: str,
            analyze: bool,
            format: str,
            verbose: bool,
            costs: bool,
            buffers: bool,
            timing: bool,
            settings: bool,
        ) -> dict[str, Any]:
            return {
                "sql": sql,
                "analyze": analyze,
                "format": format,
                "verbose": verbose,
                "costs": costs,
                "buffers": buffers,
                "timing": timing,
                "settings": settings,
            }

    monkeypatch.setattr(inspection_tools, "InspectionService", StubService)
    assert json.loads(await inspection_tools.list_table_columns(table="t")) == [
        {"schema": "public", "table": "t"}
    ]
    assert json.loads(await inspection_tools.list_table_columns("app", table="t")) == [
        {"schema": "app", "table": "t"}
    ]
    assert json.loads(await inspection_tools.list_indexes()) == [
        {"schema": None, "table": None, "include_system": False}
    ]
    assert json.loads(await inspection_tools.list_indexes("s", "t", True)) == [
        {"schema": "s", "table": "t", "include_system": True}
    ]
    assert json.loads(await inspection_tools.list_constraints()) == [
        {
            "schema": None,
            "table": None,
            "constraint_type": None,
            "include_system": False,
        }
    ]
    assert json.loads(await inspection_tools.list_constraints("s", "t", "UNIQUE", True)) == [
        {
            "schema": "s",
            "table": "t",
            "constraint_type": "UNIQUE",
            "include_system": True,
        }
    ]
    assert json.loads(await inspection_tools.list_foreign_keys()) == [
        {"schema": None, "table": None, "include_system": False}
    ]
    assert json.loads(await inspection_tools.list_foreign_keys("s", "t", True)) == [
        {"schema": "s", "table": "t", "include_system": True}
    ]
    assert json.loads(await inspection_tools.list_rls_policies()) == [
        {"schema": None, "table": None}
    ]
    assert json.loads(await inspection_tools.list_rls_policies("s", "t")) == [
        {"schema": "s", "table": "t"}
    ]
    assert json.loads(await inspection_tools.list_triggers()) == [
        {"schema": None, "table": None}
    ]
    assert json.loads(await inspection_tools.list_triggers("s", "t")) == [
        {"schema": "s", "table": "t"}
    ]
    assert json.loads(await inspection_tools.list_database_functions()) == [
        {"schema": None, "name_pattern": None, "language": None}
    ]
    assert json.loads(await inspection_tools.list_database_functions("s", "get_%", "sql")) == [
        {"schema": "s", "name_pattern": "get_%", "language": "sql"}
    ]
    assert await inspection_tools.get_function_definition(function_name="f") == {
        "schema": "public",
        "function_name": "f",
        "argument_types": None,
    }
    assert await inspection_tools.get_function_definition(
        "s", function_name="f", argument_types="integer"
    ) == {"schema": "s", "function_name": "f", "argument_types": "integer"}
    assert await inspection_tools.get_trigger_definition(
        table="t", trigger_name="tr"
    ) == {
        "schema": "public",
        "table": "t",
        "trigger_name": "tr",
        "include_function": True,
    }
    assert await inspection_tools.get_trigger_definition(
        "s", table="t", trigger_name="tr", include_function=False
    ) == {
        "schema": "s",
        "table": "t",
        "trigger_name": "tr",
        "include_function": False,
    }
    assert json.loads(await inspection_tools.get_rls_status()) == [
        {"schema": None, "table": None}
    ]
    assert json.loads(await inspection_tools.get_rls_status("s", "t")) == [
        {"schema": "s", "table": "t"}
    ]
    assert json.loads(await inspection_tools.list_available_extensions()) == [
        {"show_installed": True, "name_pattern": None}
    ]
    assert json.loads(await inspection_tools.list_available_extensions(False, "vec%")) == [
        {"show_installed": False, "name_pattern": "vec%"}
    ]
    assert json.loads(await inspection_tools.get_cron_job_history()) == [
        {"jobid": None, "jobname": None, "limit": 100, "status": None}
    ]
    assert json.loads(await inspection_tools.get_cron_job_history(5, "job", 10, "failed")) == [
        {"jobid": 5, "jobname": "job", "limit": 10, "status": "failed"}
    ]
    assert await inspection_tools.get_index_stats(index_name="i") == {
        "schema": "public",
        "index_name": "i",
    }
    assert await inspection_tools.get_index_stats("s", index_name="i") == {
        "schema": "s",
        "index_name": "i",
    }
    assert json.loads(await inspection_tools.get_vector_index_stats()) == [
        {"schema": None, "table": None, "indexname": None}
    ]
    assert json.loads(await inspection_tools.get_vector_index_stats("s", "t", "i")) == [
        {"schema": "s", "table": "t", "indexname": "i"}
    ]
    assert await inspection_tools.explain_query("SELECT 1") == {
        "sql": "SELECT 1",
        "analyze": False,
        "format": "json",
        "verbose": False,
        "costs": True,
        "buffers": False,
        "timing": True,
        "settings": False,
    }
    assert await inspection_tools.explain_query(
        "SELECT 1", True, "text", True, False, True, False, True
    ) == {
        "sql": "SELECT 1",
        "analyze": True,
        "format": "text",
        "verbose": True,
        "costs": False,
        "buffers": True,
        "timing": False,
        "settings": True,
    }
