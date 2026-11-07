"""Realtime, cron, vector, edge function, log, advisor and storage config services."""

from typing import Any, Literal

from huaweicloud_mcp_core import McpToolError

from ..client.rds_supabase_client import RdsSupabaseClient
from ..settings import RdsSupabaseSettings
from .support import is_sql_error_response, rows_or_raise

LogService = Literal["postgres", "auth", "storage", "realtime", "postgrest"]
AdvisorType = Literal["security", "performance"]

# Maps a log service to its _analytics table (dict lookup prevents injection).
_ANALYTICS_TABLES: dict[str, str] = {
    "postgres": "postgres_logs",
    "auth": "auth_logs",
    "storage": "storage_logs",
    "realtime": "realtime_logs",
    "postgrest": "postgrest_logs",
}

# Sort order for advisor issues: error first, then warning, then info.
_LEVEL_ORDER: dict[str, int] = {"error": 0, "warning": 1, "info": 2}

_CHECK_CRON_SCHEMA_SQL = """
            SELECT EXISTS (
                SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname = 'cron'
            ) AS exists
        """

_LIST_CRON_JOBS_SQL = """
            SELECT
                jobid,
                schedule,
                command,
                nodename,
                nodeport,
                database,
                username,
                active
            FROM cron.job
            ORDER BY jobid
        """

_LIST_VECTOR_INDEXES_SQL = """
            SELECT
                ix.relname AS index_name,
                t.relname AS table_name,
                n.nspname AS schema_name,
                am.amname AS index_method,
                pg_get_indexdef(i.indexrelid) AS index_definition
            FROM pg_index i
            JOIN pg_class t ON t.oid = i.indrelid
            JOIN pg_class ix ON ix.oid = i.indexrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            JOIN pg_am am ON am.oid = ix.relam
            WHERE am.amname IN ('ivfflat', 'hnsw')
            AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
            ORDER BY n.nspname, t.relname, ix.relname
        """

_CHECK_FUNCTIONS_SCHEMA_SQL = """
            SELECT EXISTS (
                SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname = 'supabase_functions'
            ) AS exists
        """

_CHECK_FUNCTIONS_TABLE_SQL = """
            SELECT EXISTS (
                SELECT 1 FROM pg_catalog.pg_tables
                WHERE schemaname = 'supabase_functions' AND tablename = 'functions'
            ) AS exists
        """

_CHECK_ANALYTICS_SCHEMA_SQL = """
        SELECT EXISTS (
            SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname = '_analytics'
        ) AS exists
    """

_CHECK_ANALYTICS_TABLE_SQL = """
        SELECT EXISTS (
            SELECT 1 FROM pg_catalog.pg_tables
            WHERE schemaname = '_analytics' AND tablename = '{table_name}'
        ) AS exists
    """

_ANALYTICS_LOGS_SQL = """
        SELECT
            timestamp::text,
            COALESCE(level, 'info') as level,
            message,
            metadata::jsonb as metadata
        FROM _analytics.{table_name}
        WHERE timestamp > NOW() - INTERVAL '24 hours'
        ORDER BY timestamp DESC
        LIMIT {limit}
    """

_CHECK_FILE_FDW_EXTENSION_SQL = """
        SELECT EXISTS (
            SELECT 1 FROM pg_extension WHERE extname = 'file_fdw'
        ) AS exists
    """

_CURRENT_LOGFILE_SQL = "SELECT pg_current_logfile() as logfile"

_CHECK_PGLOG_FOREIGN_TABLE_SQL = """
        SELECT EXISTS (
            SELECT 1 FROM pg_catalog.pg_foreign_table ft
            JOIN pg_catalog.pg_class c ON c.oid = ft.ftrelid
            WHERE c.relname = 'pglog'
        ) AS exists
    """

_CSV_LOGS_SQL = """
            SELECT
                log_time::text as timestamp,
                CASE
                    WHEN error_severity = 'ERROR' THEN 'error'
                    WHEN error_severity = 'WARNING' THEN 'warn'
                    WHEN error_severity = 'LOG' THEN 'info'
                    ELSE 'debug'
                END as level,
                message,
                jsonb_build_object(
                    'user_name', user_name,
                    'database_name', database_name,
                    'process_id', process_id,
                    'sql_state_code', sql_state_code
                ) as metadata
            FROM pglog
            WHERE log_time > NOW() - INTERVAL '24 hours'
            ORDER BY log_time DESC
            LIMIT {limit}
        """

# SQL queries for security checks (ported from Supabase Splinter)
_SECURITY_CHECKS: dict[str, str] = {
    # 0013 - RLS disabled in public schema
    "rls_disabled_in_public": """
        SELECT
            '0013' as code,
            'rls_disabled_in_public' as name,
            'warning' as level,
            'Tables in the public schema without Row Level Security enabled' as description,
            format('Table: %I.%I', n.nspname, c.relname) as detail,
            'Enable RLS with: ALTER TABLE ' || quote_ident(n.nspname)
                || '.' || quote_ident(c.relname) || ' ENABLE ROW LEVEL SECURITY;' as remediation,
            format('%I.%I', n.nspname, c.relname) as affected_object
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'r'
            AND n.nspname = 'public'
            AND NOT c.relrowsecurity
            AND c.relname NOT LIKE 'pg_%'
            AND c.relname NOT LIKE '_pg_%'
    """,

    # 0007 - Policy exists but RLS disabled
    "policy_exists_rls_disabled": """
        SELECT
            '0007' as code,
            'policy_exists_rls_disabled' as name,
            'warning' as level,
            'Tables with RLS policies defined but RLS is disabled' as description,
            format('Table: %I.%I has policies but RLS is disabled', n.nspname,
                c.relname) as detail,
            'Enable RLS with: ALTER TABLE ' || quote_ident(n.nspname)
                || '.' || quote_ident(c.relname) || ' ENABLE ROW LEVEL SECURITY;' as remediation,
            format('%I.%I', n.nspname, c.relname) as affected_object
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'r'
            AND NOT c.relrowsecurity
            AND EXISTS (
                SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid = c.oid
            )
    """,

    # 0008 - RLS enabled but no policy
    "rls_enabled_no_policy": """
        SELECT
            '0008' as code,
            'rls_enabled_no_policy' as name,
            'error' as level,
            'Tables with RLS enabled but no policies defined (blocks all access)' as description,
            format('Table: %I.%I has RLS enabled but no policies', n.nspname, c.relname) as detail,
            'Add a policy or disable RLS if not needed' as remediation,
            format('%I.%I', n.nspname, c.relname) as affected_object
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'r'
            AND c.relrowsecurity
            AND NOT EXISTS (
                SELECT 1 FROM pg_catalog.pg_policy p WHERE p.polrelid = c.oid
            )
            AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
    """,

    # 0002 - Auth users exposed via view
    "auth_users_exposed": """
        SELECT
            '0002' as code,
            'auth_users_exposed' as name,
            'error' as level,
            'Views exposing auth.users data' as description,
            format('View: %I.%I may expose auth.users', n.nspname, c.relname) as detail,
            'Review and restrict the view definition or add proper RLS' as remediation,
            format('%I.%I', n.nspname, c.relname) as affected_object
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_catalog.pg_depend d ON d.objid = c.oid
        JOIN pg_catalog.pg_class dep_c ON dep_c.oid = d.refobjid
        JOIN pg_catalog.pg_namespace dep_n ON dep_n.oid = dep_c.relnamespace
        WHERE c.relkind IN ('v', 'm')
            AND n.nspname = 'public'
            AND dep_n.nspname = 'auth'
            AND dep_c.relname = 'users'
    """,
}

# SQL queries for performance checks (ported from Supabase Splinter)
_PERFORMANCE_CHECKS: dict[str, str] = {
    # 0001 - Unindexed foreign keys
    "unindexed_foreign_keys": """
        SELECT
            '0001' as code,
            'unindexed_foreign_keys' as name,
            'warning' as level,
            'Foreign keys without covering indexes can impact performance' as description,
            format('FK on %I.%I (%s) lacks an index', cn.nspname, c.conrelid::regclass::text,
                array_to_string(ARRAY(
                    SELECT a.attname FROM unnest(c.conkey) WITH ORDINALITY AS u(attnum, i)
                    JOIN pg_attribute a ON a.attnum = u.attnum AND a.attrelid = c.conrelid
                    ORDER BY u.i
                ), ', ')) as detail,
            'Create an index on the foreign key columns' as remediation,
            c.conrelid::regclass::text as affected_object
        FROM pg_catalog.pg_constraint c
        JOIN pg_catalog.pg_namespace cn ON cn.oid = c.connamespace
        WHERE c.contype = 'f'
            AND NOT EXISTS (
                SELECT 1 FROM pg_catalog.pg_index i
                WHERE i.indrelid = c.conrelid
                    AND c.conkey <@ i.indkey::int2[]
            )
            AND cn.nspname NOT IN ('pg_catalog', 'information_schema')
    """,

    # 0004 - Missing primary keys
    "missing_primary_keys": """
        SELECT
            '0004' as code,
            'missing_primary_key' as name,
            'warning' as level,
            'Tables without primary keys are inefficient at scale' as description,
            format('Table: %I.%I has no primary key', n.nspname, c.relname) as detail,
            'Add a primary key to the table' as remediation,
            format('%I.%I', n.nspname, c.relname) as affected_object
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'r'
            AND NOT EXISTS (
                SELECT 1 FROM pg_catalog.pg_constraint con
                WHERE con.conrelid = c.oid AND con.contype = 'p'
            )
            AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast', 'cron',
                'extensions', 'graphql', 'graphql_public', 'realtime', 'storage',
                'supabase_functions', 'supabase_migrations', 'vault', 'pgsodium',
                'pgsodium_masks', 'auth', 'net', '_realtime')
    """,

    # 0005 - Unused indexes
    "unused_indexes": """
        SELECT
            '0005' as code,
            'unused_index' as name,
            'info' as level,
            'Indexes with zero scans that may be candidates for removal' as description,
            format('Index: %I.%I on %I.%I has had 0 scans', sn.nspname, i.relname,
                tn.nspname, t.relname) as detail,
            'Consider dropping the index if it is not needed' as remediation,
            format('%I.%I', sn.nspname, i.relname) as affected_object
        FROM pg_catalog.pg_stat_user_indexes s
        JOIN pg_catalog.pg_index ix ON ix.indexrelid = s.indexrelid
        JOIN pg_catalog.pg_class i ON i.oid = s.indexrelid
        JOIN pg_catalog.pg_class t ON t.oid = s.relid
        JOIN pg_catalog.pg_namespace sn ON sn.oid = i.relnamespace
        JOIN pg_catalog.pg_namespace tn ON tn.oid = t.relnamespace
        WHERE s.idx_scan = 0
            AND NOT ix.indisunique
            AND NOT ix.indisprimary
            AND sn.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
    """,

    # 0009 - Duplicate indexes
    "duplicate_indexes": """
        SELECT
            '0009' as code,
            'duplicate_index' as name,
            'warning' as level,
            'Duplicate indexes waste storage and slow writes' as description,
            format('Indexes %I and %I on %I.%I have identical definitions',
                i1.relname, i2.relname, tn.nspname, t.relname) as detail,
            'Consider dropping one of the duplicate indexes' as remediation,
            format('%I.%I', sn.nspname, i1.relname) as affected_object
        FROM pg_catalog.pg_index x1
        JOIN pg_catalog.pg_index x2 ON x1.indrelid = x2.indrelid AND x1.indexrelid < x2.indexrelid
        JOIN pg_catalog.pg_class i1 ON i1.oid = x1.indexrelid
        JOIN pg_catalog.pg_class i2 ON i2.oid = x2.indexrelid
        JOIN pg_catalog.pg_class t ON t.oid = x1.indrelid
        JOIN pg_catalog.pg_namespace sn ON sn.oid = i1.relnamespace
        JOIN pg_catalog.pg_namespace tn ON tn.oid = t.relnamespace
        WHERE x1.indkey = x2.indkey
            AND x1.indclass = x2.indclass
            AND x1.indoption = x2.indoption
            AND sn.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
    """,
}

_CHECK_STORAGE_SCHEMA_SQL = """
            SELECT EXISTS (
                SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname = 'storage'
            ) AS exists
        """

_LIST_BUCKETS_SQL = """
            SELECT
                id,
                name,
                public,
                file_size_limit,
                allowed_mime_types,
                avif_autodetection,
                owner::text,
                created_at::text,
                updated_at::text
            FROM storage.buckets
        """

_BUCKET_STATS_SQL = """
            SELECT
                MAX(file_size_limit) as max_file_size_limit,
                COUNT(*) as bucket_count
            FROM storage.buckets
        """

_CHECK_BUCKET_EXISTS_SQL = """
            SELECT EXISTS (
                SELECT 1 FROM storage.buckets WHERE id = '{escaped_bucket_id}'
            ) AS exists
        """

_UPDATE_BUCKET_SQL = """
            UPDATE storage.buckets
            SET {updates}
            WHERE id = '{escaped_bucket_id}'
            RETURNING id, name, public, file_size_limit, allowed_mime_types
        """


def _first_row_truthy(result: Any, key: str = "exists") -> bool:
    """Mirror the upstream first-row flag check result[0]?.key."""
    return isinstance(result, list) and len(result) > 0 and bool(result[0].get(key))


class PlatformService:
    """Implementations of the platform tool group."""

    def __init__(
        self,
        client: RdsSupabaseClient | None = None,
        settings: RdsSupabaseSettings | None = None,
    ) -> None:
        self._client = client or RdsSupabaseClient.shared()
        self._settings = settings or self._client.settings

    async def list_realtime_publications(self) -> list[dict[str, Any]]:
        """List pg_publication rows (RPC rework pending; direct connections removed)."""
        raise McpToolError(
            "MCP_UNSUPPORTED_OPERATION",
            "Direct database connections are not supported on this deployment; "
            "list_realtime_publications is pending an RPC-channel rework.",
        )

    async def list_cron_jobs(self) -> list[dict[str, Any]]:
        """List cron.job rows, or an empty list when the cron schema is absent."""
        schema_check = await self._client.execute_sql(
            query=_CHECK_CRON_SCHEMA_SQL, read_only=True
        )
        if not _first_row_truthy(schema_check):
            return []
        result = await self._client.execute_sql(
            query=_LIST_CRON_JOBS_SQL, read_only=True
        )
        return rows_or_raise(result)

    async def list_vector_indexes(self) -> list[dict[str, Any]]:
        """List ivfflat/hnsw indexes (naturally empty when pgvector is absent)."""
        result = await self._client.execute_sql(
            query=_LIST_VECTOR_INDEXES_SQL, read_only=True
        )
        return rows_or_raise(result)

    async def get_logs(self, *, service: LogService, limit: int = 100) -> dict[str, Any]:
        """Fetch recent logs from the analytics stack or PostgreSQL CSV logs."""
        analytics_result = await self._try_analytics_logs(service=service, limit=limit)
        if analytics_result is not None:
            return analytics_result
        if service == "postgres":
            csv_result = await self._try_postgres_csv_logs(limit=limit)
            if csv_result is not None:
                return csv_result
        return {
            "logs": [],
            "source": "none",
            "service": service,
            "message": (
                f"Log access not available for {service}. Self-hosted installations may need "
                "to configure the analytics stack or enable PostgreSQL CSV logging."
            ),
        }

    async def _try_analytics_logs(
        self, *, service: LogService, limit: int
    ) -> dict[str, Any] | None:
        """Try the _analytics schema tables for the requested service."""
        schema_check = await self._client.execute_sql(
            query=_CHECK_ANALYTICS_SCHEMA_SQL, read_only=True
        )
        if not _first_row_truthy(schema_check):
            return None
        table_name = _ANALYTICS_TABLES.get(service)
        if table_name is None:
            return None
        table_check = await self._client.execute_sql(
            query=_CHECK_ANALYTICS_TABLE_SQL.format(table_name=table_name), read_only=True
        )
        if not _first_row_truthy(table_check):
            return None
        query_logs_sql = _ANALYTICS_LOGS_SQL.format(table_name=table_name, limit=limit)
        try:
            result = await self._client.execute_sql(
                query=query_logs_sql, read_only=True
            )
            if is_sql_error_response(result):
                return None
            logs = rows_or_raise(result)
            return {"logs": logs, "source": "analytics", "service": service}
        except Exception:
            return None

    async def _try_postgres_csv_logs(self, *, limit: int) -> dict[str, Any] | None:
        """Try the pglog foreign table over PostgreSQL CSV logs."""
        extension_check = await self._client.execute_sql(
            query=_CHECK_FILE_FDW_EXTENSION_SQL, read_only=True
        )
        if not _first_row_truthy(extension_check):
            return None
        log_file_result = await self._client.execute_sql(
            query=_CURRENT_LOGFILE_SQL, read_only=True
        )
        if not _first_row_truthy(log_file_result, "logfile"):
            return None
        foreign_table_check = await self._client.execute_sql(
            query=_CHECK_PGLOG_FOREIGN_TABLE_SQL, read_only=True
        )
        if _first_row_truthy(foreign_table_check):
            try:
                result = await self._client.execute_sql(
                    query=_CSV_LOGS_SQL.format(limit=limit), read_only=True
                )
                if is_sql_error_response(result):
                    return None
                logs = rows_or_raise(result)
                return {"logs": logs, "source": "csv", "service": "postgres"}
            except Exception:
                return None
        return None

    async def get_advisors(self, *, type: AdvisorType) -> dict[str, Any]:
        """Run the Splinter-style security or performance checks."""
        checks = _SECURITY_CHECKS if type == "security" else _PERFORMANCE_CHECKS
        all_issues: list[dict[str, Any]] = []
        for check_name, sql in checks.items():
            try:
                result = await self._client.execute_sql(query=sql, read_only=True)
                if is_sql_error_response(result):
                    continue
                if isinstance(result, list):
                    for row in result:
                        level = row.get("level")
                        all_issues.append(
                            {
                                "code": str(row.get("code") or ""),
                                "name": str(row.get("name") or check_name),
                                "level": "warning" if level is None else level,
                                "description": str(row.get("description") or ""),
                                "detail": str(row["detail"]) if row.get("detail") else None,
                                "remediation": (
                                    str(row["remediation"]) if row.get("remediation") else None
                                ),
                                "affected_object": (
                                    str(row["affected_object"])
                                    if row.get("affected_object")
                                    else None
                                ),
                            }
                        )
            except Exception:
                continue
        all_issues.sort(key=lambda issue: _LEVEL_ORDER[issue["level"]])
        return {"issues": all_issues, "type": type, "total_count": len(all_issues)}

    async def get_storage_config(self, *, bucket_id: str | None = None) -> dict[str, Any]:
        """Read bucket settings and global storage statistics."""
        schema_check = await self._client.execute_sql(
            query=_CHECK_STORAGE_SCHEMA_SQL, read_only=True
        )
        if not _first_row_truthy(schema_check):
            return {
                "buckets": [],
                "global_config": {"max_file_size_limit": None, "bucket_count": 0},
            }
        bucket_query = _LIST_BUCKETS_SQL
        if bucket_id:
            escaped_bucket_id = bucket_id.replace("'", "''")
            bucket_query += f" WHERE id = '{escaped_bucket_id}'"
        bucket_query += " ORDER BY name"
        buckets_result = await self._client.execute_sql(
            query=bucket_query, read_only=True
        )
        buckets = rows_or_raise(buckets_result)
        stats_result = await self._client.execute_sql(
            query=_BUCKET_STATS_SQL, read_only=True
        )
        global_config: dict[str, Any] = {
            "max_file_size_limit": None,
            "bucket_count": len(buckets),
        }
        if isinstance(stats_result, list) and len(stats_result) > 0:
            max_limit = stats_result[0].get("max_file_size_limit")
            bucket_count = stats_result[0].get("bucket_count")
            global_config = {
                "max_file_size_limit": (
                    max_limit if isinstance(max_limit, (int, float)) else None
                ),
                "bucket_count": int(bucket_count) if bucket_count else 0,
            }
        return {"buckets": buckets, "global_config": global_config}

    async def update_storage_config(
        self,
        *,
        bucket_id: str,
        file_size_limit: int | None = None,
        allowed_mime_types: list[str] | None = None,
        public: bool | None = None,
    ) -> dict[str, Any]:
        """Update bucket settings with a structured, non-throwing result."""
        schema_check = await self._client.execute_sql(
            query=_CHECK_STORAGE_SCHEMA_SQL, read_only=True
        )
        if not _first_row_truthy(schema_check):
            return {
                "success": False,
                "bucket": None,
                "message": "Storage schema not found - Storage may not be configured",
            }
        escaped_bucket_id = bucket_id.replace("'", "''")
        bucket_check = await self._client.execute_sql(
            query=_CHECK_BUCKET_EXISTS_SQL.format(escaped_bucket_id=escaped_bucket_id),
            read_only=True,
        )
        if not _first_row_truthy(bucket_check):
            return {
                "success": False,
                "bucket": None,
                "message": f"Bucket '{bucket_id}' not found",
            }
        updates: list[str] = []
        if file_size_limit is not None:
            limit_value = "NULL" if file_size_limit == 0 else file_size_limit
            updates.append(f"file_size_limit = {limit_value}")
        if allowed_mime_types is not None:
            if len(allowed_mime_types) == 0:
                updates.append("allowed_mime_types = NULL")
            else:
                escaped_types = ", ".join(
                    "'" + mime_type.replace("'", "''") + "'"
                    for mime_type in allowed_mime_types
                )
                updates.append(f"allowed_mime_types = ARRAY[{escaped_types}]")
        if public is not None:
            updates.append(f"public = {'true' if public else 'false'}")
        if len(updates) == 0:
            return {
                "success": False,
                "bucket": None,
                "message": (
                    "No updates specified. Provide at least one of: file_size_limit, "
                    "allowed_mime_types, or public"
                ),
            }
        updates.append("updated_at = NOW()")
        update_sql = _UPDATE_BUCKET_SQL.format(
            updates=", ".join(updates), escaped_bucket_id=escaped_bucket_id
        )
        update_result = await self._client.execute_sql(
            query=update_sql, read_only=False
        )
        if is_sql_error_response(update_result):
            error: dict[str, Any] = update_result["error"]
            return {
                "success": False,
                "bucket": None,
                "message": f"Failed to update bucket: {error.get('message')}",
            }
        try:
            updated_buckets = rows_or_raise(update_result)
            if len(updated_buckets) == 0:
                return {
                    "success": False,
                    "bucket": None,
                    "message": "Update executed but no rows returned",
                }
            return {
                "success": True,
                "bucket": updated_buckets[0],
                "message": f"Successfully updated bucket '{bucket_id}'",
            }
        except Exception as exc:
            return {
                "success": False,
                "bucket": None,
                "message": f"Failed to parse update result: {exc}",
            }
