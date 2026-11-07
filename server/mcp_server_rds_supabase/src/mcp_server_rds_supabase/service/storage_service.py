"""Storage bucket and object catalog services."""

from typing import Any

from huaweicloud_mcp_core import McpToolError

from ..client.rds_supabase_client import RdsSupabaseClient
from ..settings import RdsSupabaseSettings


class StorageService:
    """Implementations of the storage tool group."""

    def __init__(
        self,
        client: RdsSupabaseClient | None = None,
        settings: RdsSupabaseSettings | None = None,
    ) -> None:
        self._client = client or RdsSupabaseClient.shared()
        self._settings = settings or self._client.settings

    async def list_storage_buckets(self) -> list[dict[str, Any]]:
        """List storage buckets from the storage.buckets catalog."""
        raise McpToolError(
            "MCP_UNSUPPORTED_OPERATION",
            "Direct database connections are not supported on this deployment; "
            "list_storage_buckets is pending an RPC-channel rework.",
        )

    async def list_storage_objects(
        self,
        *,
        bucket_id: str,
        limit: int = 100,
        offset: int = 0,
        prefix: str | None = None,
    ) -> list[dict[str, Any]]:
        """List the objects of one bucket with an optional name prefix filter."""
        raise McpToolError(
            "MCP_UNSUPPORTED_OPERATION",
            "Direct database connections are not supported on this deployment; "
            "list_storage_objects is pending an RPC-channel rework.",
        )
