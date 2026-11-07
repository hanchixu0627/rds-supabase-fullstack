"""Storage bucket and object catalog tools."""

from typing import Any

from huaweicloud_mcp_core import ToolRisk, guard

from ..server import mcp
from ..service.storage_service import StorageService
from ..service.support import as_text


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def list_storage_buckets() -> Any:
    """Lists all storage buckets in the project.

    Scenario: inspect bucket configuration, size limits and allowed MIME
    types before uploading files or tightening access.

    Args:
        (none)

    Returns:
        Rows of id, name, owner, public flag, avif autodetection, file size
        limit, allowed MIME types and timestamps, one per storage bucket.
    """
    return as_text(await StorageService().list_storage_buckets())


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def list_storage_objects(
    bucket_id: str, limit: int = 100, offset: int = 0, prefix: str | None = None
) -> Any:
    """Lists objects within a specific storage bucket, optionally filtering by prefix.

    Scenario: browse the files of one bucket, paging through results and
    narrowing them by path prefix.

    Args:
        bucket_id: The ID of the bucket to list objects from.
        limit: Max number of objects to return
        offset: Number of objects to skip
        prefix: Filter objects by a path prefix (e.g., 'public/')

    Returns:
        Rows of id, name, bucket, owner, version, mimetype, size, metadata
        and timestamps per object, ordered by name.
    """
    return as_text(await StorageService().list_storage_objects(
        bucket_id=bucket_id, limit=limit, offset=offset, prefix=prefix
    ))
