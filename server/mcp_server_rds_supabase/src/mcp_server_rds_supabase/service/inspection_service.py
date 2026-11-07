"""Database inspection catalog, definition and statistics services."""

import re
from typing import Any, Literal, NoReturn

from huaweicloud_mcp_core import McpToolError

from ..client.rds_supabase_client import RdsSupabaseClient
from ..settings import RdsSupabaseSettings
from .support import is_sql_error_response, rows_or_raise

ConstraintType = Literal["PRIMARY KEY", "FOREIGN KEY", "UNIQUE", "CHECK", "EXCLUDE"]
CronStatus = Literal["succeeded", "failed"]
ExplainFormat = Literal["json", "text", "yaml", "xml"]

_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_$]*$")
_LIKE_PATTERN = re.compile(r"^[a-zA-Z0-9_$%]+$")
_EXTENSION_LIKE_PATTERN = re.compile(r"^[a-zA-Z0-9_$%\-]+$")
_ARGUMENT_TYPES_PATTERN = re.compile(r"^[a-zA-Z0-9_$,\s\[\]()]+$")
_JOB_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\s]+$")
_FUNCTION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")
_WRITE_KEYWORD_PATTERN = re.compile(r"\b(INSERT|UPDATE|DELETE|TRUNCATE|DROP|ALTER|CREATE)\b")

# Sentinel distinguishing an absent JSON key from a present null, mirroring
# the difference between undefined and null in the upstream plan parsing.
_UNSET = object()

_CONSTRAINT_TYPE_CODES = {
    "PRIMARY KEY": "p",
    "FOREIGN KEY": "f",
    "UNIQUE": "u",
    "CHECK": "c",
    "EXCLUDE": "x",
}

_LIST_TABLE_COLUMNS_SQL = """
            SELECT
                a.attname AS column_name,
                pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
                NOT a.attnotnull AS is_nullable,
                pg_get_expr(d.adbin, d.adrelid) AS column_default,
                col_description(c.oid, a.attnum) AS description,
                a.attnum AS ordinal_position,
                CASE
                    WHEN a.atttypid = ANY(ARRAY[1042, 1043]) -- bpchar, varchar
                    THEN NULLIF(a.atttypmod, -1) - 4
                    ELSE NULL
                END AS character_maximum_length,
                CASE
                    WHEN a.atttypid = ANY(ARRAY[21, 23, 20, 1700]) -- int2, int4, int8, numeric
                    THEN ((a.atttypmod - 4) >> 16) & 65535
                    ELSE NULL
                END AS numeric_precision,
                CASE
                    WHEN a.atttypid = 1700 -- numeric
                    THEN (a.atttypmod - 4) & 65535
                    ELSE NULL
                END AS numeric_scale,
                a.attidentity != '' AS is_identity,
                CASE a.attidentity
                    WHEN 'a' THEN 'ALWAYS'
                    WHEN 'd' THEN 'BY DEFAULT'
                    ELSE NULL
                END AS identity_generation,
                a.attgenerated != '' AS is_generated,
                pg_get_expr(g.adbin, g.adrelid) AS generation_expression
            FROM pg_catalog.pg_attribute a
            JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
                AND a.attgenerated = ''
            LEFT JOIN pg_catalog.pg_attrdef g ON g.adrelid = a.attrelid AND g.adnum = a.attnum
                AND a.attgenerated != ''
            WHERE n.nspname = '{schema}'
              AND c.relname = '{table}'
              AND a.attnum > 0
              AND NOT a.attisdropped
            ORDER BY a.attnum
        """

_LIST_INDEXES_SQL = """
            SELECT
                i.schemaname AS schema_name,
                i.tablename AS table_name,
                i.indexname AS index_name,
                am.amname AS index_type,
                ix.indisunique AS is_unique,
                ix.indisprimary AS is_primary,
                ix.indisvalid AS is_valid,
                pg_catalog.pg_get_indexdef(ix.indexrelid, 0, true) AS columns,
                pg_size_pretty(pg_relation_size(ix.indexrelid)) AS size,
                i.indexdef AS definition
            FROM pg_indexes i
            JOIN pg_catalog.pg_class c ON c.relname = i.indexname
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace AND n.nspname = i.schemaname
            JOIN pg_catalog.pg_index ix ON ix.indexrelid = c.oid
            JOIN pg_catalog.pg_am am ON am.oid = c.relam
            {where_clause}
            ORDER BY i.schemaname, i.tablename, i.indexname
        """

_LIST_CONSTRAINTS_SQL = """
            SELECT
                n.nspname AS schema_name,
                rel.relname AS table_name,
                c.conname AS constraint_name,
                CASE c.contype
                    WHEN 'p' THEN 'PRIMARY KEY'
                    WHEN 'f' THEN 'FOREIGN KEY'
                    WHEN 'u' THEN 'UNIQUE'
                    WHEN 'c' THEN 'CHECK'
                    WHEN 'x' THEN 'EXCLUDE'
                    ELSE c.contype::text
                END AS constraint_type,
                ARRAY(
                    SELECT a.attname
                    FROM unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord)
                    JOIN pg_catalog.pg_attribute a ON a.attrelid = c.conrelid
                        AND a.attnum = k.attnum
                    ORDER BY k.ord
                ) AS columns,
                pg_get_constraintdef(c.oid) AS definition,
                c.condeferrable AS is_deferrable,
                c.condeferred AS initially_deferred
            FROM pg_catalog.pg_constraint c
            JOIN pg_catalog.pg_class rel ON rel.oid = c.conrelid
            JOIN pg_catalog.pg_namespace n ON n.oid = rel.relnamespace
            {where_clause}
            ORDER BY n.nspname, rel.relname, c.conname
        """

_LIST_FOREIGN_KEYS_SQL = """
            SELECT
                tc.constraint_name,
                tc.table_schema AS schema_name,
                tc.table_name,
                kcu.column_name,
                ccu.table_schema AS referenced_schema,
                ccu.table_name AS referenced_table,
                ccu.column_name AS referenced_column,
                rc.update_rule,
                rc.delete_rule,
                c.condeferrable AS is_deferrable,
                c.condeferred AS initially_deferred
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            JOIN information_schema.referential_constraints rc
                ON tc.constraint_name = rc.constraint_name
                AND tc.table_schema = rc.constraint_schema
            JOIN pg_catalog.pg_constraint c
                ON c.conname = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
            {where_clause}
            ORDER BY tc.table_schema, tc.table_name, tc.constraint_name
        """

_LIST_RLS_POLICIES_SQL = """
            SELECT
                n.nspname AS schema_name,
                c.relname AS table_name,
                pol.polname AS policy_name,
                CASE pol.polcmd
                    WHEN 'r' THEN 'SELECT'
                    WHEN 'a' THEN 'INSERT'
                    WHEN 'w' THEN 'UPDATE'
                    WHEN 'd' THEN 'DELETE'
                    WHEN '*' THEN 'ALL'
                    ELSE pol.polcmd::text
                END AS command,
                CASE pol.polpermissive
                    WHEN true THEN 'PERMISSIVE'
                    ELSE 'RESTRICTIVE'
                END AS policy_type,
                COALESCE(
                    ARRAY(SELECT
                        r.rolname FROM pg_catalog.pg_roles r WHERE r.oid = ANY(pol.polroles)),
                    ARRAY['public']::text[]
                ) AS roles,
                pg_catalog.pg_get_expr(pol.polqual, pol.polrelid) AS using_expression,
                pg_catalog.pg_get_expr(pol.polwithcheck, pol.polrelid) AS with_check_expression
            FROM pg_catalog.pg_policy pol
            JOIN pg_catalog.pg_class c ON c.oid = pol.polrelid
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE {where_clause}
            ORDER BY n.nspname, c.relname, pol.polname
        """

_LIST_TRIGGERS_SQL = """
            SELECT
                n.nspname AS schema_name,
                c.relname AS table_name,
                t.tgname AS trigger_name,
                CASE
                    WHEN t.tgtype::int & 2 > 0 THEN 'BEFORE'
                    WHEN t.tgtype::int & 64 > 0 THEN 'INSTEAD OF'
                    ELSE 'AFTER'
                END AS trigger_timing,
                CASE WHEN t.tgtype::int & 1 > 0 THEN 'ROW' ELSE 'STATEMENT' END AS trigger_level,
                ARRAY_REMOVE(ARRAY[
                    CASE WHEN t.tgtype::int & 4 > 0 THEN 'INSERT' END,
                    CASE WHEN t.tgtype::int & 8 > 0 THEN 'DELETE' END,
                    CASE WHEN t.tgtype::int & 16 > 0 THEN 'UPDATE' END,
                    CASE WHEN t.tgtype::int & 32 > 0 THEN 'TRUNCATE' END
                ], NULL) AS events,
                pn.nspname AS function_schema,
                p.proname AS function_name,
                CASE t.tgenabled
                    WHEN 'O' THEN 'ENABLED'
                    WHEN 'D' THEN 'DISABLED'
                    WHEN 'R' THEN 'REPLICA'
                    WHEN 'A' THEN 'ALWAYS'
                    ELSE t.tgenabled::text
                END AS enabled
            FROM pg_catalog.pg_trigger t
            JOIN pg_catalog.pg_class c ON c.oid = t.tgrelid
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_catalog.pg_proc p ON p.oid = t.tgfoid
            JOIN pg_catalog.pg_namespace pn ON pn.oid = p.pronamespace
            WHERE {where_clause}
            ORDER BY n.nspname, c.relname, t.tgname
        """

_LIST_DATABASE_FUNCTIONS_SQL = """
            SELECT
                n.nspname AS schema_name,
                p.proname AS function_name,
                pg_catalog.pg_get_function_arguments(p.oid) AS arguments,
                pg_catalog.pg_get_function_result(p.oid) AS return_type,
                l.lanname AS language,
                CASE p.provolatile
                    WHEN 'i' THEN 'IMMUTABLE'
                    WHEN 's' THEN 'STABLE'
                    WHEN 'v' THEN 'VOLATILE'
                    ELSE p.provolatile::text
                END AS volatility,
                p.prosecdef AS security_definer,
                obj_description(p.oid, 'pg_proc') AS description
            FROM pg_catalog.pg_proc p
            JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
            JOIN pg_catalog.pg_language l ON l.oid = p.prolang
            WHERE {where_clause}
            ORDER BY n.nspname, p.proname
        """

_GET_FUNCTION_DEFINITION_SQL = """
            SELECT
                n.nspname AS schema_name,
                p.proname AS function_name,
                pg_catalog.pg_get_function_arguments(p.oid) AS arguments,
                pg_catalog.pg_get_function_result(p.oid) AS return_type,
                l.lanname AS language,
                CASE p.provolatile
                    WHEN 'i' THEN 'IMMUTABLE'
                    WHEN 's' THEN 'STABLE'
                    WHEN 'v' THEN 'VOLATILE'
                    ELSE p.provolatile::text
                END AS volatility,
                p.prosecdef AS security_definer,
                pg_catalog.pg_get_functiondef(p.oid) AS definition
            FROM pg_catalog.pg_proc p
            JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
            JOIN pg_catalog.pg_language l ON l.oid = p.prolang
            WHERE {where_clause}
            AND p.prokind = 'f'
            LIMIT 1
        """

_GET_TRIGGER_DEFINITION_SQL = """
            SELECT
                n.nspname AS schema_name,
                c.relname AS table_name,
                t.tgname AS trigger_name,
                CASE
                    WHEN t.tgtype::int & 2 > 0 THEN 'BEFORE'
                    WHEN t.tgtype::int & 64 > 0 THEN 'INSTEAD OF'
                    ELSE 'AFTER'
                END AS trigger_timing,
                CASE WHEN t.tgtype::int & 1 > 0 THEN 'ROW' ELSE 'STATEMENT' END AS trigger_level,
                ARRAY_REMOVE(ARRAY[
                    CASE WHEN t.tgtype::int & 4 > 0 THEN 'INSERT' END,
                    CASE WHEN t.tgtype::int & 8 > 0 THEN 'DELETE' END,
                    CASE WHEN t.tgtype::int & 16 > 0 THEN 'UPDATE' END,
                    CASE WHEN t.tgtype::int & 32 > 0 THEN 'TRUNCATE' END
                ], NULL) AS events,
                pn.nspname AS function_schema,
                p.proname AS function_name,
                CASE t.tgenabled
                    WHEN 'O' THEN 'ENABLED'
                    WHEN 'D' THEN 'DISABLED'
                    WHEN 'R' THEN 'REPLICA'
                    WHEN 'A' THEN 'ALWAYS'
                    ELSE t.tgenabled::text
                END AS enabled,
                pg_catalog.pg_get_triggerdef(t.oid, true) AS definition,
                {function_definition} AS function_definition
            FROM pg_catalog.pg_trigger t
            JOIN pg_catalog.pg_class c ON c.oid = t.tgrelid
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_catalog.pg_proc p ON p.oid = t.tgfoid
            JOIN pg_catalog.pg_namespace pn ON pn.oid = p.pronamespace
            WHERE n.nspname = '{schema}'
              AND c.relname = '{table}'
              AND t.tgname = '{trigger_name}'
            LIMIT 1
        """

_GET_RLS_STATUS_SQL = """
            SELECT
                n.nspname AS schema_name,
                c.relname AS table_name,
                c.relrowsecurity AS rls_enabled,
                c.relforcerowsecurity AS rls_forced,
                COUNT(pol.polname)::int AS policy_count
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_catalog.pg_policy pol ON pol.polrelid = c.oid
            WHERE {where_clause}
            GROUP BY n.nspname, c.relname, c.relrowsecurity, c.relforcerowsecurity
            ORDER BY n.nspname, c.relname
        """

_LIST_AVAILABLE_EXTENSIONS_SQL = """
            SELECT
                name,
                default_version,
                installed_version,
                installed_version IS NOT NULL AS is_installed,
                comment
            FROM pg_available_extensions
            {where_clause}
            ORDER BY name
        """

_CHECK_CRON_EXTENSION_SQL = """
            SELECT EXISTS (
                SELECT 1 FROM pg_extension WHERE extname = 'pg_cron'
            ) as installed;
        """

_CRON_JOB_HISTORY_SQL = """
            SELECT
                j.jobid,
                j.jobname,
                j.schedule,
                r.runid,
                r.status,
                r.start_time::text,
                r.end_time::text,
                r.return_message
            FROM cron.job j
            LEFT JOIN cron.job_run_details r ON j.jobid = r.jobid
            {where_clause}
            ORDER BY r.start_time DESC NULLS LAST
            LIMIT {safe_limit}
        """

_CHECK_EDGE_LOGS_TABLE_SQL = """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = 'function_edge_logs'
            ) as exists;
        """

_GET_INDEX_STATS_SQL = """
            SELECT
                s.schemaname AS schema_name,
                s.relname AS table_name,
                s.indexrelname AS index_name,
                am.amname AS index_type,
                i.indisunique AS is_unique,
                i.indisprimary AS is_primary,
                i.indisvalid AS is_valid,
                COALESCE(s.idx_scan, 0)::bigint AS number_of_scans,
                COALESCE(s.idx_tup_read, 0)::bigint AS tuples_read,
                COALESCE(s.idx_tup_fetch, 0)::bigint AS tuples_fetched,
                pg_size_pretty(pg_relation_size(s.indexrelid)) AS index_size,
                pg_size_pretty(pg_relation_size(s.relid)) AS table_size,
                pg_relation_size(s.indexrelid)::bigint AS index_size_bytes,
                pg_relation_size(s.relid)::bigint AS table_size_bytes,
                CASE
                    WHEN (st.seq_scan + st.idx_scan) > 0
                    THEN ROUND((st.idx_scan::numeric / (st.seq_scan + st.idx_scan)::numeric)
                        * 100, 2)::text || '%'
                    ELSE NULL
                END AS usage_ratio
            FROM pg_stat_user_indexes s
            JOIN pg_catalog.pg_index i ON i.indexrelid = s.indexrelid
            JOIN pg_catalog.pg_class c ON c.oid = s.indexrelid
            JOIN pg_catalog.pg_am am ON am.oid = c.relam
            JOIN pg_stat_user_tables st ON st.relid = s.relid
            WHERE s.schemaname = '{schema}'
              AND s.indexrelname = '{index_name}'
            LIMIT 1
        """

_CHECK_VECTOR_EXTENSION_SQL = """
            SELECT EXISTS (
                SELECT 1 FROM pg_extension WHERE extname = 'vector'
            ) as installed;
        """

_VECTOR_INDEX_STATS_SQL = """
            WITH vector_indexes AS (
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    CASE
                        WHEN indexdef LIKE '%USING ivfflat%' THEN 'IVFFlat'
                        WHEN indexdef LIKE '%USING hnsw%' THEN 'HNSW'
                        ELSE 'Unknown'
                    END AS index_type
                FROM pg_indexes
                WHERE indexdef LIKE '%vector_%ops%'
            )
            SELECT
                vi.schemaname,
                vi.tablename,
                vi.indexname,
                vi.index_type,
                COALESCE(s.idx_scan, 0) AS idx_scan,
                COALESCE(s.idx_tup_read, 0) AS idx_tup_read,
                COALESCE(s.idx_tup_fetch, 0) AS idx_tup_fetch,
                pg_size_pretty(pg_relation_size(s.indexrelid)) AS index_size,
                pg_relation_size(s.indexrelid) AS index_size_bytes
            FROM vector_indexes vi
            JOIN pg_stat_user_indexes s
                ON vi.schemaname = s.schemaname
                AND vi.indexname = s.indexrelname
            WHERE 1=1 {stats_where_clause}
            ORDER BY s.idx_scan DESC, index_size_bytes DESC
        """


def _check_identifier(value: str, label: str, suffix: str = "") -> None:
    """Validate a required SQL identifier against the upstream pattern."""
    if not _IDENTIFIER_PATTERN.fullmatch(value):
        raise McpToolError("MCP_VALIDATION_ERROR", f"Invalid {label}: {value}{suffix}")


def _check_optional_identifier(value: str | None, label: str, suffix: str = "") -> None:
    """Validate an identifier only when provided, mirroring JS truthiness."""
    if value and not _IDENTIFIER_PATTERN.fullmatch(value):
        raise McpToolError("MCP_VALIDATION_ERROR", f"Invalid {label}: {value}{suffix}")


def _raise_message_or(result: Any, fallback: str) -> NoReturn:
    """Raise the upstream `error.message || fallback` text as a tool error."""
    error: dict[str, Any] = result["error"]
    code = error.get("code")
    raise McpToolError(str(code) if code else "MCP_SQL_ERROR", error.get("message") or fallback)


def _detect_write_query(sql: str) -> tuple[bool, str, str]:
    """Best-effort write-query detection, mirroring the upstream helper."""
    upper_sql = sql.upper().strip()
    for keyword in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "DROP", "ALTER", "CREATE"):
        if upper_sql.startswith(keyword):
            return True, keyword, "high"
    if _WRITE_KEYWORD_PATTERN.search(upper_sql):
        return True, "MIXED/CTE", "medium"
    return False, "SELECT", "low"


class InspectionService:
    """Implementations of the inspection tool group."""

    def __init__(
        self,
        client: RdsSupabaseClient | None = None,
        settings: RdsSupabaseSettings | None = None,
    ) -> None:
        self._client = client or RdsSupabaseClient.shared()
        self._settings = settings or self._client.settings

    async def list_table_columns(
        self, *, schema: str = "public", table: str
    ) -> list[dict[str, Any]]:
        """List the columns of one table with types, defaults and constraints."""
        _check_identifier(schema, "schema name")
        _check_identifier(table, "table name")
        sql = _LIST_TABLE_COLUMNS_SQL.format(schema=schema, table=table)
        result = await self._client.execute_sql(query=sql, read_only=True)
        if is_sql_error_response(result):
            _raise_message_or(result, "Failed to list table columns")
        rows: list[dict[str, Any]] = result
        if len(rows) == 0:
            raise McpToolError(
                "MCP_NOT_FOUND", f"Table {schema}.{table} not found or has no columns."
            )
        return [dict(row) for row in rows]

    async def list_indexes(
        self,
        *,
        schema: str | None = None,
        table: str | None = None,
        include_system: bool = False,
    ) -> list[dict[str, Any]]:
        """List indexes with definitions and sizes, with optional filters."""
        _check_optional_identifier(schema, "schema name")
        _check_optional_identifier(table, "table name")

        conditions: list[str] = []

        if not include_system:
            conditions.append(
                "schemaname NOT IN ('pg_catalog', 'information_schema', 'pg_toast', "
                "'auth', 'storage', 'extensions', 'graphql', 'graphql_public', "
                "'pgbouncer', 'realtime', 'supabase_functions', 'supabase_migrations', "
                "'_realtime')"
            )

        if schema:
            conditions.append(f"schemaname = '{schema}'")
        if table:
            conditions.append(f"tablename = '{table}'")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = _LIST_INDEXES_SQL.format(where_clause=where_clause)
        result = await self._client.execute_sql(query=sql, read_only=True)
        return rows_or_raise(result)

    async def list_constraints(
        self,
        *,
        schema: str | None = None,
        table: str | None = None,
        constraint_type: ConstraintType | None = None,
        include_system: bool = False,
    ) -> list[dict[str, Any]]:
        """List constraints with definitions, with optional filters."""
        _check_optional_identifier(schema, "schema name")
        _check_optional_identifier(table, "table name")

        conditions: list[str] = []

        if not include_system:
            conditions.append(
                "n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast', "
                "'auth', 'storage', 'extensions', 'graphql', 'graphql_public', "
                "'pgbouncer', 'realtime', 'supabase_functions', 'supabase_migrations', "
                "'_realtime')"
            )

        if schema:
            conditions.append(f"n.nspname = '{schema}'")
        if table:
            conditions.append(f"rel.relname = '{table}'")
        if constraint_type:
            # Map lookup prevents injection through the constraint type.
            type_code = _CONSTRAINT_TYPE_CODES.get(constraint_type)
            if type_code:
                conditions.append(f"c.contype = '{type_code}'")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = _LIST_CONSTRAINTS_SQL.format(where_clause=where_clause)
        result = await self._client.execute_sql(query=sql, read_only=True)
        return rows_or_raise(result)

    async def list_foreign_keys(
        self,
        *,
        schema: str | None = None,
        table: str | None = None,
        include_system: bool = False,
    ) -> list[dict[str, Any]]:
        """List foreign key relationships with optional filters."""
        _check_optional_identifier(schema, "schema name")
        _check_optional_identifier(table, "table name")

        conditions: list[str] = []

        if not include_system:
            conditions.append(
                "tc.table_schema NOT IN ('pg_catalog', 'information_schema', "
                "'auth', 'storage', 'extensions', 'graphql', 'graphql_public', "
                "'pgbouncer', 'realtime', 'supabase_functions', 'supabase_migrations', "
                "'_realtime')"
            )

        if schema:
            conditions.append(f"tc.table_schema = '{schema}'")
        if table:
            conditions.append(f"tc.table_name = '{table}'")

        where_clause = f"AND {' AND '.join(conditions)}" if conditions else ""
        sql = _LIST_FOREIGN_KEYS_SQL.format(where_clause=where_clause)
        result = await self._client.execute_sql(query=sql, read_only=True)
        return rows_or_raise(result)

    async def list_rls_policies(
        self, *, schema: str | None = None, table: str | None = None
    ) -> list[dict[str, Any]]:
        """List Row Level Security policies with optional filters."""
        _check_optional_identifier(schema, "schema name")
        _check_optional_identifier(table, "table name")

        conditions: list[str] = [
            "n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')",
        ]

        if schema:
            conditions.append(f"n.nspname = '{schema}'")
        if table:
            conditions.append(f"c.relname = '{table}'")

        where_clause = " AND ".join(conditions)
        sql = _LIST_RLS_POLICIES_SQL.format(where_clause=where_clause)
        result = await self._client.execute_sql(query=sql, read_only=True)
        return rows_or_raise(result)

    async def list_triggers(
        self, *, schema: str | None = None, table: str | None = None
    ) -> list[dict[str, Any]]:
        """List triggers with optional schema and table filters."""
        _check_optional_identifier(schema, "schema name")
        _check_optional_identifier(table, "table name")

        conditions: list[str] = [
            "NOT t.tgisinternal",  # Exclude internal triggers
            "n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')",
        ]

        if schema:
            conditions.append(f"n.nspname = '{schema}'")
        if table:
            conditions.append(f"c.relname = '{table}'")

        where_clause = " AND ".join(conditions)
        sql = _LIST_TRIGGERS_SQL.format(where_clause=where_clause)
        result = await self._client.execute_sql(query=sql, read_only=True)
        return rows_or_raise(result)

    async def list_database_functions(
        self,
        *,
        schema: str | None = None,
        name_pattern: str | None = None,
        language: str | None = None,
    ) -> list[dict[str, Any]]:
        """List user-defined functions with optional filters."""
        _check_optional_identifier(schema, "schema name")
        _check_optional_identifier(language, "language name")
        if name_pattern and not _LIKE_PATTERN.fullmatch(name_pattern):
            raise McpToolError(
                "MCP_VALIDATION_ERROR",
                f"Invalid name pattern: {name_pattern}. "
                "Use only alphanumeric, underscore, dollar sign, and % wildcard.",
            )

        conditions: list[str] = [
            "n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')",
            "n.nspname NOT LIKE 'pg_temp_%'",
            "p.prokind = 'f'",  # Functions only, not procedures or aggregates
        ]

        if schema:
            conditions.append(f"n.nspname = '{schema}'")
        if name_pattern:
            conditions.append(f"p.proname LIKE '{name_pattern}'")
        if language:
            conditions.append(f"l.lanname = '{language}'")

        where_clause = " AND ".join(conditions)
        sql = _LIST_DATABASE_FUNCTIONS_SQL.format(where_clause=where_clause)
        result = await self._client.execute_sql(query=sql, read_only=True)
        return rows_or_raise(result)

    async def get_function_definition(
        self, *, schema: str = "public", function_name: str, argument_types: str | None = None
    ) -> dict[str, Any]:
        """Get the source definition of one function."""
        _check_identifier(schema, "schema name")
        _check_identifier(function_name, "function name")
        if argument_types and not _ARGUMENT_TYPES_PATTERN.fullmatch(argument_types):
            raise McpToolError(
                "MCP_VALIDATION_ERROR", f"Invalid argument types format: {argument_types}"
            )

        where_clause = f"n.nspname = '{schema}' AND p.proname = '{function_name}'"

        if argument_types:
            # Use pg_get_function_arguments to match the argument signature
            where_clause += f" AND pg_catalog.pg_get_function_arguments(p.oid) = '{argument_types}'"

        sql = _GET_FUNCTION_DEFINITION_SQL.format(where_clause=where_clause)
        result = await self._client.execute_sql(query=sql, read_only=True)
        if is_sql_error_response(result):
            _raise_message_or(result, "Failed to get function definition")
        rows: list[dict[str, Any]] = result
        if len(rows) == 0:
            suffix = f"({argument_types})" if argument_types else ""
            raise McpToolError(
                "MCP_NOT_FOUND", f"Function {schema}.{function_name}{suffix} not found."
            )
        return dict(rows[0])

    async def get_trigger_definition(
        self,
        *,
        schema: str = "public",
        table: str,
        trigger_name: str,
        include_function: bool = True,
    ) -> dict[str, Any]:
        """Get the definition of one trigger and optionally its function."""
        _check_identifier(schema, "schema name")
        _check_identifier(table, "table name")
        _check_identifier(trigger_name, "trigger name")

        function_definition = (
            "pg_catalog.pg_get_functiondef(p.oid)" if include_function else "NULL"
        )
        sql = _GET_TRIGGER_DEFINITION_SQL.format(
            schema=schema,
            table=table,
            trigger_name=trigger_name,
            function_definition=function_definition,
        )
        result = await self._client.execute_sql(query=sql, read_only=True)
        if is_sql_error_response(result):
            _raise_message_or(result, "Failed to get trigger definition")
        rows: list[dict[str, Any]] = result
        if len(rows) == 0:
            raise McpToolError(
                "MCP_NOT_FOUND", f'Trigger "{trigger_name}" not found on {schema}.{table}.'
            )
        return dict(rows[0])

    async def get_rls_status(
        self, *, schema: str | None = None, table: str | None = None
    ) -> list[dict[str, Any]]:
        """Report RLS enablement and policy counts per table."""
        _check_optional_identifier(schema, "schema name")
        _check_optional_identifier(table, "table name")

        conditions: list[str] = [
            "c.relkind = 'r'",  # ordinary tables only
            "n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast', "
            "'auth', 'storage', 'extensions', 'graphql', 'graphql_public', "
            "'pgbouncer', 'realtime', 'supabase_functions', 'supabase_migrations', "
            "'_realtime')",
        ]

        if schema:
            conditions.append(f"n.nspname = '{schema}'")
        if table:
            conditions.append(f"c.relname = '{table}'")

        where_clause = " AND ".join(conditions)
        sql = _GET_RLS_STATUS_SQL.format(where_clause=where_clause)
        result = await self._client.execute_sql(query=sql, read_only=True)
        return rows_or_raise(result)

    async def list_available_extensions(
        self, *, show_installed: bool = True, name_pattern: str | None = None
    ) -> list[dict[str, Any]]:
        """List installable extensions, optionally filtering installed ones."""
        if name_pattern and not _EXTENSION_LIKE_PATTERN.fullmatch(name_pattern):
            raise McpToolError(
                "MCP_VALIDATION_ERROR",
                f"Invalid name pattern: {name_pattern}. Use only alphanumeric, "
                "underscore, hyphen, dollar sign, and % wildcard.",
            )

        conditions: list[str] = []

        if not show_installed:
            conditions.append("installed_version IS NULL")
        if name_pattern:
            conditions.append(f"name LIKE '{name_pattern}'")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = _LIST_AVAILABLE_EXTENSIONS_SQL.format(where_clause=where_clause)
        result = await self._client.execute_sql(query=sql, read_only=True)
        return rows_or_raise(result)

    async def get_cron_job_history(
        self,
        *,
        jobid: int | None = None,
        jobname: str | None = None,
        limit: int = 100,
        status: CronStatus | None = None,
    ) -> list[dict[str, Any]]:
        """List pg_cron job run history with status and timing."""
        if jobname and not _JOB_NAME_PATTERN.fullmatch(jobname):
            raise McpToolError(
                "MCP_VALIDATION_ERROR",
                f"Invalid job name pattern: {jobname}. Use only alphanumeric, "
                "underscore, hyphen, and space characters.",
            )

        extension_check = await self._client.execute_sql(
            query=_CHECK_CRON_EXTENSION_SQL, read_only=True
        )

        if not isinstance(extension_check, list) or len(extension_check) == 0:
            raise McpToolError("MCP_SQL_ERROR", "Failed to check pg_cron extension status.")

        if not extension_check[0].get("installed"):
            raise McpToolError(
                "MCP_EXTENSION_NOT_INSTALLED",
                "pg_cron extension is not installed. Install it with: CREATE EXTENSION pg_cron;",
            )

        conditions: list[str] = []

        if jobid is not None:
            # jobid is a validated number, safe to interpolate
            conditions.append(f"j.jobid = {jobid}")

        if jobname:
            conditions.append(f"j.jobname ILIKE '%{jobname}%'")

        if status:
            # status is a validated enum value, safe to interpolate
            conditions.append(f"r.status = '{status}'")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        safe_limit = min(max(1, limit), 1000)

        sql = _CRON_JOB_HISTORY_SQL.format(where_clause=where_clause, safe_limit=safe_limit)
        result = await self._client.execute_sql(query=sql, read_only=True)
        return rows_or_raise(result)

    async def get_index_stats(
        self, *, schema: str = "public", index_name: str
    ) -> dict[str, Any]:
        """Get usage and size statistics for one index."""
        _check_identifier(schema, "schema name", ". Must be a valid SQL identifier.")
        _check_identifier(index_name, "index name", ". Must be a valid SQL identifier.")

        sql = _GET_INDEX_STATS_SQL.format(schema=schema, index_name=index_name)
        result = await self._client.execute_sql(query=sql, read_only=True)
        if is_sql_error_response(result):
            _raise_message_or(result, "Failed to get index stats")
        rows: list[dict[str, Any]] = result
        if len(rows) == 0:
            raise McpToolError(
                "MCP_NOT_FOUND", f'Index "{index_name}" not found in schema "{schema}".'
            )
        return dict(rows[0])

    async def get_vector_index_stats(
        self,
        *,
        schema: str | None = None,
        table: str | None = None,
        indexname: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get usage and size statistics for pgvector indexes."""
        _check_optional_identifier(schema, "schema name", ". Must be a valid SQL identifier.")
        _check_optional_identifier(table, "table name", ". Must be a valid SQL identifier.")
        _check_optional_identifier(indexname, "index name", ". Must be a valid SQL identifier.")

        extension_check = await self._client.execute_sql(
            query=_CHECK_VECTOR_EXTENSION_SQL, read_only=True
        )

        if is_sql_error_response(extension_check):
            _raise_message_or(extension_check, "Failed to check pgvector extension status.")

        check_rows: list[dict[str, Any]] = extension_check
        if len(check_rows) == 0 or not check_rows[0].get("installed"):
            raise McpToolError(
                "MCP_EXTENSION_NOT_INSTALLED",
                "pgvector extension is not installed. Install it with: CREATE EXTENSION vector;",
            )

        stats_conditions: list[str] = []

        if schema:
            stats_conditions.append(f"s.schemaname = '{schema}'")

        if table:
            stats_conditions.append(f"s.relname = '{table}'")

        if indexname:
            stats_conditions.append(f"s.indexrelname = '{indexname}'")

        stats_where_clause = f"AND {' AND '.join(stats_conditions)}" if stats_conditions else ""

        sql = _VECTOR_INDEX_STATS_SQL.format(stats_where_clause=stats_where_clause)
        result = await self._client.execute_sql(query=sql, read_only=True)
        return rows_or_raise(result)

    async def explain_query(
        self,
        *,
        sql: str,
        analyze: bool = False,
        format: ExplainFormat = "json",
        verbose: bool = False,
        costs: bool = True,
        buffers: bool = False,
        timing: bool = True,
        settings: bool = False,
    ) -> dict[str, Any]:
        """Get the execution plan of a query, optionally analyzing it."""
        warnings: list[str] = []

        is_write, query_type, confidence = _detect_write_query(sql)

        if analyze:
            if is_write:
                if confidence == "high":
                    warnings.append(
                        f"⚠️ CRITICAL: ANALYZE will EXECUTE this {query_type} query and "
                        "MODIFY DATA!"
                    )
                else:
                    warnings.append(
                        f"⚠️ WARNING: Query may contain {query_type} operations. "
                        "ANALYZE will execute the query."
                    )
            else:
                warnings.append(
                    "Note: ANALYZE will execute the query to measure actual timing."
                )

        options: list[str] = []
        options.append(f"FORMAT {format.upper()}")
        if analyze:
            options.append("ANALYZE true")
        if verbose:
            options.append("VERBOSE true")
        options.append(f"COSTS {'true' if costs else 'false'}")
        if analyze and buffers:
            options.append("BUFFERS true")
        if analyze:
            options.append(f"TIMING {'true' if timing else 'false'}")
        if settings:
            options.append("SETTINGS true")

        explain_sql = f"EXPLAIN ({', '.join(options)}) {sql}"

        # ANALYZE actually executes the query, so the read-only gate only
        # applies while planning.
        is_read_only = not analyze

        try:
            result = await self._client.execute_sql(
                query=explain_sql, read_only=is_read_only
            )

            if is_sql_error_response(result):
                _raise_message_or(result, "Failed to explain query")

            rows: list[dict[str, Any]] = result

            plan: Any = None
            planning_time: Any = _UNSET
            execution_time: Any = _UNSET

            if format == "json":
                # JSON format returns an array with a single object holding 'QUERY PLAN'.
                if len(rows) > 0:
                    first_row = rows[0]
                    query_plan = first_row.get("QUERY PLAN") or first_row.get("query plan")
                    if isinstance(query_plan, list):
                        plan = query_plan
                        plan_obj = query_plan[0] if query_plan else None
                        if isinstance(plan_obj, dict):
                            if "Planning Time" in plan_obj:
                                planning_time = plan_obj["Planning Time"]
                            if "Execution Time" in plan_obj:
                                execution_time = plan_obj["Execution Time"]
                    else:
                        plan = query_plan
            else:
                # Text/YAML/XML format returns multiple rows.
                plan = [
                    row.get("QUERY PLAN") or row.get("query plan") or row for row in rows
                ]

            explained: dict[str, Any] = {"query": sql}
            if plan is not None:
                explained["plan"] = plan
            explained["format"] = format
            explained["analyzed"] = analyze
            if planning_time is not _UNSET:
                explained["planning_time_ms"] = planning_time
            if execution_time is not _UNSET:
                explained["execution_time_ms"] = execution_time
            if warnings:
                explained["warnings"] = warnings
            return explained
        except McpToolError as exc:
            raise McpToolError(exc.code, f"Failed to explain query: {exc.message}") from exc
        except Exception as exc:
            raise McpToolError("MCP_EXPLAIN_FAILED", f"Failed to explain query: {exc}") from exc
