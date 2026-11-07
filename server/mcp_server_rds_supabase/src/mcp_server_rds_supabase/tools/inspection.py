"""Database inspection catalog, definition and statistics tools."""

from typing import Any

from huaweicloud_mcp_core import ToolRisk, guard

from ..server import mcp
from ..service.inspection_service import (
    ConstraintType,
    CronStatus,
    ExplainFormat,
    InspectionService,
)
from ..service.support import as_text


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def list_table_columns(schema: str = "public", *, table: str) -> Any:
    """Lists all columns for a table with detailed metadata including types, defaults, and constraints.

    Scenario: inspect one table's shape before writing queries, migrations or
    validation logic.

    Args:
        schema: Schema name (defaults to public).
        table: Table name to get columns for.

    Returns:
        Rows of column name, type, nullability, default, description and
        identity or generation metadata per column, ordered by position.
    """
    return as_text(await InspectionService().list_table_columns(schema=schema, table=table))


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def list_indexes(
    schema: str | None = None, table: str | None = None, include_system: bool = False
) -> Any:
    """Lists all indexes in the database with their definitions and sizes. Can filter by schema and/or table.

    Scenario: review index coverage and sizes before optimizing a query or
    planning a migration.

    Args:
        schema: Filter indexes by schema name.
        table: Filter indexes by table name.
        include_system: Include indexes on system tables.

    Returns:
        Rows of schema, table, index name, type, uniqueness, validity,
        columns, size and definition per index.
    """
    return as_text(await InspectionService().list_indexes(
        schema=schema, table=table, include_system=include_system
    ))


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def list_constraints(
    schema: str | None = None,
    table: str | None = None,
    constraint_type: ConstraintType | None = None,
    include_system: bool = False,
) -> Any:
    """Lists all constraints (PRIMARY KEY, FOREIGN KEY, UNIQUE, CHECK, EXCLUDE) in the database. Can filter by schema, table, and type.

    Scenario: audit key, uniqueness and check rules before changing table
    structure or loading data.

    Args:
        schema: Filter by schema name.
        table: Filter by table name.
        constraint_type: Filter by constraint type.
        include_system: Include constraints in system schemas.

    Returns:
        Rows of schema, table, constraint name, type, columns, definition and
        deferrability per constraint.
    """
    return as_text(await InspectionService().list_constraints(
        schema=schema,
        table=table,
        constraint_type=constraint_type,
        include_system=include_system,
    ))


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def list_foreign_keys(
    schema: str | None = None, table: str | None = None, include_system: bool = False
) -> Any:
    """Lists all foreign key relationships in the database. Can filter by schema and/or table.

    Scenario: map referential dependencies before reordering deletions,
    dropping tables or importing data.

    Args:
        schema: Filter by schema name.
        table: Filter by table name.
        include_system: Include foreign keys in system schemas.

    Returns:
        Rows of constraint, schema, table, column, referenced schema, table
        and column plus cascade rules per foreign key.
    """
    return as_text(await InspectionService().list_foreign_keys(
        schema=schema, table=table, include_system=include_system
    ))


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def list_rls_policies(
    schema: str | None = None, table: str | None = None
) -> Any:
    """Lists all Row Level Security (RLS) policies in the database. Can filter by schema and/or table name.

    Scenario: review who can read or write which rows before tightening
    access or debugging permission surprises.

    Args:
        schema: Filter policies by schema name.
        table: Filter policies by table name.

    Returns:
        Rows of schema, table, policy name, command, policy type, roles and
        USING / WITH CHECK expressions per policy.
    """
    return as_text(await InspectionService().list_rls_policies(schema=schema, table=table))


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def list_triggers(
    schema: str | None = None, table: str | None = None
) -> Any:
    """Lists all triggers on tables. Can filter by schema and/or table name.

    Scenario: find trigger side effects before bulk updates, restores or
    schema changes.

    Args:
        schema: Filter triggers by schema name.
        table: Filter triggers by table name.

    Returns:
        Rows of schema, table, trigger name, timing, level, events, target
        function and enabled state per trigger.
    """
    return as_text(await InspectionService().list_triggers(schema=schema, table=table))


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def list_database_functions(
    schema: str | None = None, name_pattern: str | None = None, language: str | None = None
) -> Any:
    """Lists all user-defined database functions (stored procedures). Can filter by schema, name pattern, or language. Identifies SECURITY DEFINER functions which may have elevated privileges.

    Scenario: inventory stored functions and flag SECURITY DEFINER ones
    during a security or ownership review.

    Args:
        schema: Filter functions by schema name.
        name_pattern: Filter functions by name pattern (SQL LIKE pattern).
        language: Filter by language (e.g., plpgsql, sql).

    Returns:
        Rows of schema, function name, arguments, return type, language,
        volatility, security definer flag and description per function.
    """
    return as_text(await InspectionService().list_database_functions(
        schema=schema, name_pattern=name_pattern, language=language
    ))


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def get_function_definition(
    schema: str = "public", *, function_name: str, argument_types: str | None = None
) -> dict[str, Any]:
    """Gets the full source code definition of a database function. Use argument_types if there are overloaded functions with the same name.

    Scenario: read one function's source before patching, tuning or
    auditing its behaviour.

    Args:
        schema: Schema name (defaults to public).
        function_name: Name of the function.
        argument_types: Argument types to disambiguate overloaded functions (e.g., "integer, text").

    Returns:
        The function's schema, name, arguments, return type, language,
        volatility, security flag and full source definition.
    """
    return await InspectionService().get_function_definition(
        schema=schema, function_name=function_name, argument_types=argument_types
    )


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def get_trigger_definition(
    schema: str = "public", *, table: str, trigger_name: str, include_function: bool = True
) -> dict[str, Any]:
    """Gets the full definition of a trigger, optionally including its function source code.

    Scenario: inspect one trigger's timing, events and function body before
    editing or disabling it.

    Args:
        schema: Schema name (defaults to public).
        table: Table name the trigger is on.
        trigger_name: Name of the trigger.
        include_function: Include the trigger function source code.

    Returns:
        The trigger's schema, table, name, timing, level, events, enabled
        state, definition and optional function source.
    """
    return await InspectionService().get_trigger_definition(
        schema=schema,
        table=table,
        trigger_name=trigger_name,
        include_function=include_function,
    )


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def get_rls_status(
    schema: str | None = None, table: str | None = None
) -> Any:
    """Checks if Row Level Security (RLS) is enabled on tables and shows the number of policies. Can filter by schema and/or table.

    Scenario: verify which tables are protected by RLS and which carry
    policies, before an audit or after enabling RLS.

    Args:
        schema: Filter by schema name.
        table: Filter by table name.

    Returns:
        Rows of schema, table, RLS enabled and forced flags and policy count
        per table.
    """
    return as_text(await InspectionService().get_rls_status(schema=schema, table=table))


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def list_available_extensions(
    show_installed: bool = True, name_pattern: str | None = None
) -> Any:
    """Lists all PostgreSQL extensions available for installation, including those already installed.

    Scenario: check whether an extension such as pgvector or pg_cron can be
    enabled on this instance.

    Args:
        show_installed: Include already installed extensions.
        name_pattern: Filter by extension name pattern (SQL LIKE).

    Returns:
        Rows of name, default version, installed version, installed flag and
        comment per available extension.
    """
    return as_text(await InspectionService().list_available_extensions(
        show_installed=show_installed, name_pattern=name_pattern
    ))


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def get_cron_job_history(
    jobid: int | None = None,
    jobname: str | None = None,
    limit: int = 100,
    status: CronStatus | None = None,
) -> Any:
    """Gets execution history for pg_cron jobs including status and timing. Requires pg_cron to be installed.

    Scenario: review recent scheduled job runs and their failures after
    enabling pg_cron.

    Args:
        jobid: Filter by specific job ID.
        jobname: Filter by job name pattern.
        limit: Maximum number of records to return.
        status: Filter by execution status.

    Returns:
        Rows of job id, name, schedule, run id, status, start and end times
        and return message per job run.
    """
    return as_text(await InspectionService().get_cron_job_history(
        jobid=jobid, jobname=jobname, limit=limit, status=status
    ))


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def get_index_stats(schema: str = "public", *, index_name: str) -> dict[str, Any]:
    """Gets detailed statistics for a specific index including usage counts and size.

    Scenario: check scan counts and sizes to decide whether an index earns
    its write overhead.

    Args:
        schema: Schema name (defaults to public).
        index_name: Name of the index.

    Returns:
        The index's schema, table, type, uniqueness flags, scan and tuple
        statistics, sizes and usage ratio.
    """
    return await InspectionService().get_index_stats(schema=schema, index_name=index_name)


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def get_vector_index_stats(
    schema: str | None = None, table: str | None = None, indexname: str | None = None
) -> Any:
    """Gets usage statistics and size information for pgvector indexes.

    Scenario: measure vector index usage and growth after shipping
    semantic search workloads.

    Args:
        schema: Filter by schema name.
        table: Filter by table name.
        indexname: Filter by index name.

    Returns:
        Rows of schema, table, index name, index type, scan statistics and
        sizes per vector index.
    """
    return as_text(await InspectionService().get_vector_index_stats(
        schema=schema, table=table, indexname=indexname
    ))


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def explain_query(
    sql: str,
    analyze: bool = False,
    format: ExplainFormat = "json",
    verbose: bool = False,
    costs: bool = True,
    buffers: bool = False,
    timing: bool = True,
    settings: bool = False,
) -> dict[str, Any]:
    """Gets the execution plan for a SQL query. WARNING: With ANALYZE enabled, the query is actually executed which will modify data for write operations.

    Scenario: study a plan, its costs and optionally its real timings before
    tuning a slow query.

    Args:
        sql: The SQL query to analyze.
        analyze: Actually execute the query to get real timing. WARNING: This WILL execute the query and modify data for write operations!
        format: Output format for the plan.
        verbose: Include additional details in the plan.
        costs: Include estimated costs.
        buffers: Include buffer usage statistics (requires ANALYZE).
        timing: Include actual timing (requires ANALYZE).
        settings: Include non-default configuration settings.

    Returns:
        The query, its plan, the output format, whether it was analyzed,
        optional planning and execution times, and safety warnings.
    """
    return await InspectionService().explain_query(
        sql=sql,
        analyze=analyze,
        format=format,
        verbose=verbose,
        costs=costs,
        buffers=buffers,
        timing=timing,
        settings=settings,
    )
