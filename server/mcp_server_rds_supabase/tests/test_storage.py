"""Tests for the storage tool group (direct connections removed in 0.4.0)."""

import pytest
from huaweicloud_mcp_core import McpToolError

from mcp_server_rds_supabase.service.storage_service import StorageService
from mcp_server_rds_supabase.tools import storage as storage_tools
from tests.conftest import FakeRdsSupabaseClient, make_settings


async def test_list_storage_buckets_reports_unsupported_channel() -> None:
    service = StorageService(client=FakeRdsSupabaseClient(), settings=make_settings())
    with pytest.raises(McpToolError) as exc_info:
        await service.list_storage_buckets()
    assert exc_info.value.code == "MCP_UNSUPPORTED_OPERATION"
    assert exc_info.value.message == (
        "Direct database connections are not supported on this deployment; "
        "list_storage_buckets is pending an RPC-channel rework."
    )


async def test_list_storage_objects_reports_unsupported_channel() -> None:
    service = StorageService(client=FakeRdsSupabaseClient(), settings=make_settings())
    with pytest.raises(McpToolError) as exc_info:
        await service.list_storage_objects(bucket_id="b", limit=10, offset=0, prefix="p/")
    assert exc_info.value.code == "MCP_UNSUPPORTED_OPERATION"
    assert exc_info.value.message == (
        "Direct database connections are not supported on this deployment; "
        "list_storage_objects is pending an RPC-channel rework."
    )


async def test_tool_functions_delegate_to_the_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StubService:
        async def list_storage_buckets(self) -> list[dict]:
            return [{"id": "bucket-1", "name": "public"}]

        async def list_storage_objects(
            self, *, bucket_id: str, limit: int = 100, offset: int = 0,
            prefix: str | None = None,
        ) -> list[dict]:
            return [
                {
                    "bucket_id": bucket_id,
                    "limit": limit,
                    "offset": offset,
                    "prefix": prefix,
                }
            ]

    monkeypatch.setattr(storage_tools, "StorageService", StubService)
    import json

    assert json.loads(await storage_tools.list_storage_buckets()) == [
        {"id": "bucket-1", "name": "public"}
    ]
    assert json.loads(
        await storage_tools.list_storage_objects("bucket-1", 5, 5, prefix="p/")
    ) == [{"bucket_id": "bucket-1", "limit": 5, "offset": 5, "prefix": "p/"}]
