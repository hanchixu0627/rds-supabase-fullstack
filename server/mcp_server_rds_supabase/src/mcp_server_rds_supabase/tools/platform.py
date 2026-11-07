"""Realtime, cron, vector, edge function, log, advisor and storage config tools."""

from typing import Any

from huaweicloud_mcp_core import ToolRisk, guard

from ..server import mcp
from ..service.platform_service import AdvisorType, LogService, PlatformService
from ..service.support import as_text


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def list_realtime_publications() -> Any:
    """Lists PostgreSQL publications, often used by Supabase Realtime.

    Scenario: inspect publication configuration when troubleshooting Supabase
    Realtime replication.

    Args:
        (none)

    Returns:
        Rows of publication oid, name, owner OID and the enabled event flags
        per publication.
    """
    return as_text(await PlatformService().list_realtime_publications())


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def list_cron_jobs() -> Any:
    """Lists all scheduled cron jobs from pg_cron extension. Returns empty array if pg_cron is not installed.

    Scenario: review scheduled jobs and their schedules before changing or
    debugging background work.

    Args:
        (none)

    Returns:
        Rows of job id, schedule, command, node, database, username and
        active flag per cron job, ordered by jobid.
    """
    return as_text(await PlatformService().list_cron_jobs())


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def list_vector_indexes() -> Any:
    """Lists all pgvector indexes (ivfflat, hnsw) in the database. Returns empty array if pgvector is not installed or no vector indexes exist.

    Scenario: find vector indexes and their definitions before tuning
    semantic search workloads.

    Args:
        (none)

    Returns:
        Rows of index name, table name, schema name, index method and index
        definition per vector index.
    """
    return as_text(await PlatformService().list_vector_indexes())


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def get_logs(service: LogService, limit: int = 100) -> dict[str, Any]:
    """Gets logs for a Supabase service. Attempts to query the analytics stack first, then falls back to PostgreSQL CSV logs. Returns logs from the last 24 hours. Note: Log availability depends on your self-hosted installation configuration.

    Scenario: inspect recent service logs to diagnose errors or unexpected
    behaviour.

    Args:
        service: The service to fetch logs for (postgres, auth, storage, realtime, postgrest)
        limit: Maximum number of log entries to return (default: 100, max: 1000)

    Returns:
        Log entries with the resolved source, or an empty result with an
        explanatory message when no log source is available.
    """
    return await PlatformService().get_logs(service=service, limit=limit)


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def get_advisors(type: AdvisorType) -> dict[str, Any]:
    """Gets security or performance advisory notices for the database. Based on Supabase Splinter linting rules. Helps identify issues like missing RLS policies, unindexed foreign keys, and other common problems.

    Scenario: run linting checks to surface security or performance risks
    before they escalate.

    Args:
        type: The type of advisors to retrieve (security or performance)

    Returns:
        Issues with code, name, level, description, detail, remediation and
        affected object, plus the issue type and total count.
    """
    return await PlatformService().get_advisors(type=type)


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def get_storage_config(bucket_id: str | None = None) -> dict[str, Any]:
    """Gets storage configuration for Supabase Storage buckets. Returns bucket settings including file size limits, allowed MIME types, and public/private status.

    Scenario: review bucket settings and global storage limits before
    adjusting upload constraints.

    Args:
        bucket_id: Optional bucket ID to get config for a specific bucket. If omitted, returns all buckets.

    Returns:
        Bucket rows with size limits, MIME types and visibility plus the
        global max file size limit and bucket count.
    """
    return await PlatformService().get_storage_config(bucket_id=bucket_id)


@mcp.tool()
@guard(risk=ToolRisk.WRITE)
async def update_storage_config(
    bucket_id: str,
    file_size_limit: int | None = None,
    allowed_mime_types: list[str] | None = None,
    public: bool | None = None,
) -> dict[str, Any]:
    """Updates storage configuration for a Supabase Storage bucket. Can modify file size limits, allowed MIME types, and public/private status.

    Scenario: tighten a bucket's upload constraints or flip its visibility
    without touching other buckets.

    Args:
        bucket_id: The bucket ID to update
        file_size_limit: Maximum file size in bytes (0 or null for no limit)
        allowed_mime_types: Array of allowed MIME types (e.g., ["image/png", "image/jpeg"]). Empty array means all types allowed.
        public: Whether the bucket is publicly accessible

    Returns:
        Success flag, the updated bucket row (or null) and a message
        describing the outcome.
    """
    return await PlatformService().update_storage_config(
        bucket_id=bucket_id,
        file_size_limit=file_size_limit,
        allowed_mime_types=allowed_mime_types,
        public=public,
    )
