"""Database catalog, migration and SQL execution services."""

import asyncio
import sys
from typing import Any

from huaweicloud_mcp_core import McpToolError

from ..client.rds_supabase_client import RdsSupabaseClient
from ..settings import RdsSupabaseSettings
from .support import rows_or_raise

_LIST_TABLES_SQL = """
            SELECT
                n.nspname as schema,
                c.relname as name,
                pgd.description as comment
            FROM
                pg_catalog.pg_class c
            JOIN
                pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN
                pg_catalog.pg_description pgd ON pgd.objoid = c.oid AND pgd.objsubid = 0
            WHERE
                c.relkind = 'r' -- r = ordinary table
                AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                AND n.nspname NOT LIKE 'pg_temp_%'
                AND n.nspname NOT LIKE 'pg_toast_temp_%'
                 -- Exclude Supabase internal schemas
                AND n.nspname NOT IN ('auth', 'storage', 'extensions', 'graphql',
                    'graphql_public', 'pgbouncer', 'realtime', 'supabase_functions',
                    'supabase_migrations', '_realtime')
                AND has_schema_privilege(n.oid, 'USAGE')
                AND has_table_privilege(c.oid, 'SELECT')
            ORDER BY
                n.nspname,
                c.relname
"""

_LIST_EXTENSIONS_SQL = """
            SELECT
                pe.extname AS name,
                pn.nspname AS schema,
                pe.extversion AS version,
                pd.description
            FROM
                pg_catalog.pg_extension pe
            LEFT JOIN
                pg_catalog.pg_namespace pn ON pn.oid = pe.extnamespace
            LEFT JOIN
                pg_catalog.pg_description pd ON pd.objoid = pe.oid
                    AND pd.classoid = 'pg_catalog.pg_extension'::regclass
            WHERE
                pe.extname != 'plpgsql' -- Exclude the default plpgsql extension
            ORDER BY
                pe.extname
"""

_GET_CONNECTIONS_SQL = """
            SELECT
                pid,
                datname,
                usename,
                application_name,
                client_addr::text, -- Cast inet to text
                backend_start::text, -- Cast timestamp to text
                state,
                query
            FROM
                pg_stat_activity
            WHERE
                backend_type = 'client backend' -- Exclude background workers, etc.
                -- Optionally filter out self?
                -- AND pid != pg_backend_pid()
            ORDER BY
                backend_start
"""

_GET_DB_STATS_SQL = """
            SELECT
                datname,
                numbackends,
                xact_commit::text,
                xact_rollback::text,
                blks_read::text,
                blks_hit::text,
                tup_returned::text,
                tup_fetched::text,
                tup_inserted::text,
                tup_updated::text,
                tup_deleted::text,
                conflicts::text,
                temp_files::text,
                temp_bytes::text,
                deadlocks::text,
                checksum_failures::text,
                checksum_last_failure::text,
                blk_read_time,
                blk_write_time,
                stats_reset::text
            FROM pg_stat_database
"""

_GET_BGWRITER_STATS_SQL = """
            SELECT
                checkpoints_timed::text,
                checkpoints_req::text,
                checkpoint_write_time,
                checkpoint_sync_time,
                buffers_checkpoint::text,
                buffers_clean::text,
                maxwritten_clean::text,
                buffers_backend::text,
                buffers_backend_fsync::text,
                buffers_alloc::text,
                stats_reset::text
            FROM pg_stat_bgwriter
"""


class DatabaseService:
    """Implementations of the database tool group."""

    def __init__(
        self,
        client: RdsSupabaseClient | None = None,
        settings: RdsSupabaseSettings | None = None,
    ) -> None:
        self._client = client or RdsSupabaseClient.shared()
        self._settings = settings or self._client.settings

    async def list_tables(self) -> list[dict[str, Any]]:
        """List accessible tables, excluding system and Supabase internal schemas."""
        result = await self._client.execute_sql(
            query=_LIST_TABLES_SQL, read_only=True
        )
        return rows_or_raise(result)

    async def list_extensions(self) -> list[dict[str, Any]]:
        """List installed PostgreSQL extensions."""
        result = await self._client.execute_sql(
            query=_LIST_EXTENSIONS_SQL, read_only=True
        )
        return rows_or_raise(result)

    async def execute_sql(self, *, sql: str, read_only: bool = False) -> list[dict[str, Any]]:
        """Execute arbitrary SQL via the privileged channels."""
        if not self._client.is_service_role_available():
            raise McpToolError(
                "MCP_CONFIG_ERROR",
                "execute_sql requires a service role key (SUPABASE_SERVICE_ROLE_KEY) "
                "to be configured. This tool cannot be used with only the anon key "
                "for security reasons.",
            )
        query_preview = (
            f"{sql[:200]}... [truncated, {len(sql)} chars total]" if len(sql) > 200 else sql
        )
        # Mirrors the upstream [AUDIT] line for the stdio mode (no HTTP user context).
        print(
            f"[AUDIT] SQL execution by user=unknown (stdio mode): {query_preview}",
            file=sys.stderr,
            flush=True,
        )
        result = await self._client.execute_sql(query=sql, read_only=read_only)
        return rows_or_raise(result)

    async def get_database_connections(self) -> list[dict[str, Any]]:
        """List client backends from pg_stat_activity."""
        result = await self._client.execute_sql(
            query=_GET_CONNECTIONS_SQL, read_only=True
        )
        return rows_or_raise(result)

    async def get_database_stats(self) -> dict[str, Any]:
        """Combine pg_stat_database and pg_stat_bgwriter snapshots."""
        db_result, bgwriter_result = await asyncio.gather(
            self._client.execute_sql(query=_GET_DB_STATS_SQL, read_only=True),
            self._client.execute_sql(query=_GET_BGWRITER_STATS_SQL, read_only=True),
        )
        return {
            "database_stats": rows_or_raise(db_result),
            "bgwriter_stats": rows_or_raise(bgwriter_result),
        }
