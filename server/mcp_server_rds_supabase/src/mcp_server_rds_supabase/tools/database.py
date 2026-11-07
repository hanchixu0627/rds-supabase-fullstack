"""Database catalog and SQL execution tools."""

from typing import Any

from huaweicloud_mcp_core import ToolRisk, guard

from ..server import mcp
from ..service.database_service import DatabaseService
from ..service.support import as_text


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def list_tables() -> Any:
    """Lists all accessible tables in the connected database, grouped by schema.

    Scenario: inspect the database structure before querying data or planning
    a migration.

    Args:
        (none)

    Returns:
        Rows of schema, name and optional comment, one per accessible table.
    """
    return as_text(await DatabaseService().list_tables())


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def list_extensions() -> Any:
    """Lists all installed PostgreSQL extensions in the database.

    Scenario: verify extension availability before using extension features
    such as pgvector, pg_cron or pg_net.

    Args:
        (none)

    Returns:
        Rows of name, schema, version and optional description per extension.
    """
    return as_text(await DatabaseService().list_extensions())


@mcp.tool()
@guard(risk=ToolRisk.WRITE)
async def execute_sql(sql: str, read_only: bool = False) -> Any:
    """Executes an arbitrary SQL query against the database. SECURITY: Requires a service_role key.

    Scenario: run a reviewed statement beyond the scenario tools. With
    read_only=true the in-database gate restricts the statement to the
    SELECT / WITH / VALUES / TABLE / EXPLAIN whitelist.

    Args:
        sql: The SQL query to execute.
        read_only: Hint for the RPC function whether the query is read-only (best effort).

    Returns:
        The array of rows returned by the SQL query.
    """
    return as_text(await DatabaseService().execute_sql(sql=sql, read_only=read_only))


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def get_database_connections() -> Any:
    """Retrieves information about active database connections from pg_stat_activity.

    Scenario: inspect client backends to diagnose connection exhaustion or
    long-running sessions.

    Args:
        (none)

    Returns:
        Rows of pid, database, user, application, client address, backend
        start, state and last query for client backends.
    """
    return as_text(await DatabaseService().get_database_connections())


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def get_database_stats() -> dict[str, Any]:
    """Retrieves statistics about database activity and the background writer from pg_stat_database and pg_stat_bgwriter.

    Scenario: check transaction throughput, cache hits, temporary file usage
    and checkpoint pressure in one combined snapshot.

    Args:
        (none)

    Returns:
        database_stats rows from pg_stat_database and bgwriter_stats rows
        from pg_stat_bgwriter.
    """
    return await DatabaseService().get_database_stats()
