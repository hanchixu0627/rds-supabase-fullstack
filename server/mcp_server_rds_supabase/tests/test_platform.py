"""Tests for the platform tool group (fake client and sequenced outcomes)."""

import json
from typing import Any

import pytest
from huaweicloud_mcp_core import McpToolError, ToolRisk
from huaweicloud_mcp_core.security import get_tool_risk

from mcp_server_rds_supabase.service.platform_service import PlatformService
from mcp_server_rds_supabase.tools import platform as platform_tools
from tests.conftest import FakeRdsSupabaseClient, make_settings

PUBLICATIONS: list[dict[str, Any]] = [
    {
        "oid": 16384,
        "pubname": "supabase_realtime",
        "pubowner": 10,
        "puballtables": True,
        "pubinsert": True,
        "pubupdate": True,
        "pubdelete": True,
        "pubtruncate": False,
        "pubviaroot": False,
    }
]

CRON_JOBS: list[dict[str, Any]] = [
    {
        "jobid": 1,
        "schedule": "* * * * *",
        "command": "SELECT 1",
        "nodename": "localhost",
        "nodeport": 5432,
        "database": "postgres",
        "username": "postgres",
        "active": True,
    }
]

VECTOR_INDEXES: list[dict[str, Any]] = [
    {
        "index_name": "docs_embedding_idx",
        "table_name": "docs",
        "schema_name": "public",
        "index_method": "hnsw",
        "index_definition": "CREATE INDEX ON public.docs USING hnsw (embedding)",
    }
]

EDGE_FUNCTIONS: list[dict[str, Any]] = [
    {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "name": "hello",
        "slug": "hello",
        "status": "ACTIVE",
        "version": 3,
        "created_at": "2026-01-01 00:00:00+00",
        "updated_at": "2026-01-02 00:00:00+00",
    }
]

EDGE_FUNCTION_DETAILS: dict[str, Any] = {
    **EDGE_FUNCTIONS[0],
    "verify_jwt": True,
    "import_map": False,
}

LOG_ROWS: list[dict[str, Any]] = [
    {
        "timestamp": "2026-01-01 00:00:00+00",
        "level": "info",
        "message": "request completed",
        "metadata": {"request_id": "abc"},
    }
]

CSV_LOG_ROWS: list[dict[str, Any]] = [
    {
        "timestamp": "2026-01-01 00:00:00+00",
        "level": "error",
        "message": "boom",
        "metadata": {"user_name": "postgres", "database_name": "postgres"},
    }
]

BUCKETS: list[dict[str, Any]] = [
    {
        "id": "photos",
        "name": "photos",
        "public": False,
        "file_size_limit": 5242880,
        "allowed_mime_types": ["image/png"],
        "avif_autodetection": None,
        "owner": "postgres",
        "created_at": "2026-01-01 00:00:00+00",
        "updated_at": "2026-01-02 00:00:00+00",
    }
]

UPDATED_BUCKET: dict[str, Any] = {
    "id": "photos",
    "name": "photos",
    "public": True,
    "file_size_limit": None,
    "allowed_mime_types": None,
}

SQL_ERROR = {"error": {"message": "permission denied for table pg_publication", "code": "42501"}}

NONE_SOURCE_MESSAGE = (
    "Log access not available for {service}. Self-hosted installations may need to configure "
    "the analytics stack or enable PostgreSQL CSV logging."
)


class _SequencedClient:
    """Fake client returning one queued outcome per SQL call."""

    def __init__(self, outcomes: list[Any]) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._outcomes = list(outcomes)

    async def execute_sql(self, **kwargs: Any) -> Any:
        self.calls.append(("execute_sql", kwargs))
        outcome = self._outcomes.pop(0) if self._outcomes else []
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def execute_sql_with_pg(self, **kwargs: Any) -> Any:
        self.calls.append(("execute_sql_with_pg", kwargs))
        outcome = self._outcomes.pop(0) if self._outcomes else []
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _service(responses: dict[str, Any] | None = None) -> PlatformService:
    return PlatformService(
        client=FakeRdsSupabaseClient(responses),
        settings=make_settings(),
    )


def _sequenced_service(outcomes: list[Any]) -> PlatformService:
    return PlatformService(client=_SequencedClient(outcomes), settings=make_settings())


# ------------------------------------------------------ list_realtime_publications


async def test_list_realtime_publications_reports_unsupported_channel() -> None:
    service = _service()
    with pytest.raises(McpToolError) as exc_info:
        await service.list_realtime_publications()
    assert exc_info.value.code == "MCP_UNSUPPORTED_OPERATION"
    assert exc_info.value.message == (
        "Direct database connections are not supported on this deployment; "
        "list_realtime_publications is pending an RPC-channel rework."
    )


# --------------------------------------------------------------- list_cron_jobs


async def test_list_cron_jobs_returns_jobs_when_schema_present() -> None:
    service = _sequenced_service([[{"exists": True}], list(CRON_JOBS)])
    assert await service.list_cron_jobs() == CRON_JOBS
    assert [c[0] for c in service._client.calls] == [
        "execute_sql",
        "execute_sql",
    ]
    assert service._client.calls[0][1] == {
        "query": (
            "\n            SELECT EXISTS (\n"
            "                SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname = 'cron'\n"
            "            ) AS exists\n        "
        ),
        "read_only": True,
    }
    assert "FROM cron.job" in service._client.calls[1][1]["query"]
    assert "ORDER BY jobid" in service._client.calls[1][1]["query"]
    assert service._client.calls[1][1]["read_only"] is True


async def test_list_cron_jobs_returns_empty_when_schema_missing() -> None:
    service = _sequenced_service([[{"exists": False}]])
    assert await service.list_cron_jobs() == []
    assert len(service._client.calls) == 1


async def test_list_cron_jobs_returns_empty_when_check_errors() -> None:
    service = _sequenced_service([SQL_ERROR])
    assert await service.list_cron_jobs() == []


async def test_list_cron_jobs_returns_empty_when_check_returns_no_rows() -> None:
    service = _sequenced_service([[]])
    assert await service.list_cron_jobs() == []


async def test_list_cron_jobs_raises_upstream_error_from_final_query() -> None:
    service = _sequenced_service([[{"exists": True}], SQL_ERROR])
    with pytest.raises(McpToolError) as exc_info:
        await service.list_cron_jobs()
    assert exc_info.value.message == (
        "SQL Error (42501): permission denied for table pg_publication"
    )


# ----------------------------------------------------------- list_vector_indexes


async def test_list_vector_indexes_returns_rows() -> None:
    service = _service({"execute_sql": list(VECTOR_INDEXES)})
    assert await service.list_vector_indexes() == VECTOR_INDEXES
    query = service._client.calls[0][1]["query"]
    assert "WHERE am.amname IN ('ivfflat', 'hnsw')" in query
    assert "pg_get_indexdef(i.indexrelid) AS index_definition" in query
    assert service._client.calls[0][1]["read_only"] is True


async def test_list_vector_indexes_returns_empty_without_pgvector() -> None:
    service = _service({"execute_sql": []})
    assert await service.list_vector_indexes() == []


async def test_list_vector_indexes_raises_upstream_sql_error() -> None:
    service = _service({"execute_sql": SQL_ERROR})
    with pytest.raises(McpToolError) as exc_info:
        await service.list_vector_indexes()
    assert exc_info.value.code == "42501"



# ---------------------------------------------------------------------- get_logs


async def test_get_logs_reads_from_the_analytics_stack() -> None:
    service = _sequenced_service([[{"exists": True}], [{"exists": True}], list(LOG_ROWS)])
    result = await service.get_logs(service="auth", limit=50)
    assert result == {"logs": LOG_ROWS, "source": "analytics", "service": "auth"}


async def test_get_logs_interpolates_the_analytics_table_and_limit() -> None:
    service = _sequenced_service([[{"exists": True}], [{"exists": True}], list(LOG_ROWS)])
    await service.get_logs(service="postgres", limit=250)
    queries = [c[1]["query"] for c in service._client.calls]
    assert "tablename = 'postgres_logs'" in queries[1]
    assert "FROM _analytics.postgres_logs" in queries[2]
    assert "COALESCE(level, 'info') as level" in queries[2]
    assert "metadata::jsonb as metadata" in queries[2]
    assert "INTERVAL '24 hours'" in queries[2]
    assert "LIMIT 250" in queries[2]


async def test_get_logs_analytics_schema_missing_degrades_to_none() -> None:
    service = _sequenced_service([[{"exists": False}]])
    result = await service.get_logs(service="auth")
    assert result == {
        "logs": [],
        "source": "none",
        "service": "auth",
        "message": NONE_SOURCE_MESSAGE.format(service="auth"),
    }
    assert len(service._client.calls) == 1


async def test_get_logs_analytics_table_missing_degrades_to_none() -> None:
    service = _sequenced_service([[{"exists": True}], [{"exists": False}]])
    result = await service.get_logs(service="auth")
    assert result["source"] == "none"
    assert result["message"] == NONE_SOURCE_MESSAGE.format(service="auth")


async def test_get_logs_analytics_query_error_degrades_to_none() -> None:
    service = _sequenced_service([[{"exists": True}], [{"exists": True}], SQL_ERROR])
    result = await service.get_logs(service="auth")
    assert result["source"] == "none"
    assert result["logs"] == []


async def test_get_logs_falls_back_to_csv_logs_for_postgres() -> None:
    service = _sequenced_service(
        [
            [{"exists": False}],  # _analytics schema
            [{"exists": True}],  # file_fdw extension
            [{"logfile": "/var/log/postgresql.csv"}],
            [{"exists": True}],  # pglog foreign table
            list(CSV_LOG_ROWS),
        ]
    )
    result = await service.get_logs(service="postgres", limit=5)
    assert result == {"logs": CSV_LOG_ROWS, "source": "csv", "service": "postgres"}
    assert service._client.calls[2][1]["query"] == "SELECT pg_current_logfile() as logfile"
    query = service._client.calls[4][1]["query"]
    assert "WHEN error_severity = 'ERROR' THEN 'error'" in query
    assert "jsonb_build_object(" in query
    assert "FROM pglog" in query
    assert "LIMIT 5" in query


async def test_get_logs_csv_requires_file_fdw() -> None:
    service = _sequenced_service([[{"exists": False}], [{"exists": False}]])
    result = await service.get_logs(service="postgres")
    assert result["source"] == "none"
    assert result["message"] == NONE_SOURCE_MESSAGE.format(service="postgres")


async def test_get_logs_csv_requires_a_current_logfile() -> None:
    service = _sequenced_service(
        [[{"exists": False}], [{"exists": True}], [{"logfile": None}]]
    )
    result = await service.get_logs(service="postgres")
    assert result["source"] == "none"


async def test_get_logs_csv_requires_the_pglog_foreign_table() -> None:
    service = _sequenced_service(
        [
            [{"exists": False}],
            [{"exists": True}],
            [{"logfile": "/var/log/postgresql.csv"}],
            [{"exists": False}],
        ]
    )
    result = await service.get_logs(service="postgres")
    assert result["source"] == "none"


async def test_get_logs_csv_query_error_degrades_to_none() -> None:
    service = _sequenced_service(
        [
            [{"exists": False}],
            [{"exists": True}],
            [{"logfile": "/var/log/postgresql.csv"}],
            [{"exists": True}],
            SQL_ERROR,
        ]
    )
    result = await service.get_logs(service="postgres")
    assert result["source"] == "none"


async def test_get_logs_non_postgres_services_skip_the_csv_fallback() -> None:
    service = _sequenced_service([[{"exists": False}]])
    result = await service.get_logs(service="storage", limit=10)
    assert result["source"] == "none"
    assert len(service._client.calls) == 1


# ------------------------------------------------------------------ get_advisors


def _advisor_row(code: str, name: str, level: str) -> dict[str, Any]:
    return {
        "code": code,
        "name": name,
        "level": level,
        "description": f"{name} description",
        "detail": f"Table: public.{name}",
        "remediation": f"fix {name}",
        "affected_object": f"public.{name}",
    }


async def test_get_advisors_security_sorts_issues_by_level() -> None:
    rows = [
        [_advisor_row("0013", "rls_disabled_in_public", "warning")],
        [_advisor_row("0007", "policy_exists_rls_disabled", "warning")],
        [_advisor_row("0008", "rls_enabled_no_policy", "error")],
        [_advisor_row("0002", "auth_users_exposed", "error")],
    ]
    service = _sequenced_service(rows)
    result = await service.get_advisors(type="security")
    assert result["type"] == "security"
    assert result["total_count"] == 4
    assert [issue["code"] for issue in result["issues"]] == ["0008", "0002", "0013", "0007"]
    queries = [c[1]["query"] for c in service._client.calls]
    assert "'rls_disabled_in_public' as name" in queries[0]
    assert "'policy_exists_rls_disabled' as name" in queries[1]
    assert "'rls_enabled_no_policy' as name" in queries[2]
    assert "'auth_users_exposed' as name" in queries[3]
    assert all(c[1]["read_only"] is True for c in service._client.calls)


async def test_get_advisors_fills_row_level_defaults() -> None:
    service = _sequenced_service(
        [
            [
                {
                    "code": None,
                    "name": None,
                    "level": None,
                    "description": None,
                    "detail": None,
                    "remediation": None,
                    "affected_object": None,
                }
            ],
            [],
            [],
            [],
        ]
    )
    result = await service.get_advisors(type="security")
    assert result["issues"] == [
        {
            "code": "",
            "name": "rls_disabled_in_public",
            "level": "warning",
            "description": "",
            "detail": None,
            "remediation": None,
            "affected_object": None,
        }
    ]


async def test_get_advisors_skips_checks_that_return_errors() -> None:
    service = _sequenced_service(
        [SQL_ERROR, [], [_advisor_row("0008", "rls_enabled_no_policy", "error")], []]
    )
    result = await service.get_advisors(type="security")
    assert [issue["code"] for issue in result["issues"]] == ["0008"]
    assert result["total_count"] == 1


async def test_get_advisors_skips_checks_that_raise() -> None:
    service = _sequenced_service([RuntimeError("boom"), [], [], []])
    result = await service.get_advisors(type="security")
    assert result == {"issues": [], "type": "security", "total_count": 0}


async def test_get_advisors_performance_runs_the_performance_checks() -> None:
    service = _sequenced_service([[], [], [], []])
    result = await service.get_advisors(type="performance")
    assert result == {"issues": [], "type": "performance", "total_count": 0}
    queries = [c[1]["query"] for c in service._client.calls]
    assert "c.contype = 'f'" in queries[0]
    assert "'missing_primary_key' as name" in queries[1]
    assert "'unused_index' as name" in queries[2]
    assert "'duplicate_index' as name" in queries[3]


# ------------------------------------------------------------- get_storage_config


async def test_get_storage_config_returns_empty_when_schema_missing() -> None:
    service = _sequenced_service([[{"exists": False}]])
    result = await service.get_storage_config()
    assert result == {
        "buckets": [],
        "global_config": {"max_file_size_limit": None, "bucket_count": 0},
    }
    assert len(service._client.calls) == 1


async def test_get_storage_config_returns_buckets_and_global_stats() -> None:
    service = _sequenced_service(
        [
            [{"exists": True}],
            list(BUCKETS),
            [{"max_file_size_limit": 5242880, "bucket_count": 3}],
        ]
    )
    result = await service.get_storage_config()
    assert result == {
        "buckets": BUCKETS,
        "global_config": {"max_file_size_limit": 5242880, "bucket_count": 3},
    }
    queries = [c[1]["query"] for c in service._client.calls]
    assert "FROM storage.buckets" in queries[1]
    assert "avif_autodetection" in queries[1]
    assert "MAX(file_size_limit) as max_file_size_limit" in queries[2]
    assert "COUNT(*) as bucket_count" in queries[2]
    assert all(c[1]["read_only"] is True for c in service._client.calls)


async def test_get_storage_config_filters_by_bucket_id_with_escaping() -> None:
    service = _sequenced_service(
        [
            [{"exists": True}],
            list(BUCKETS),
            [{"max_file_size_limit": None, "bucket_count": 1}],
        ]
    )
    await service.get_storage_config(bucket_id="ph'otos")
    query = service._client.calls[1][1]["query"]
    assert "WHERE id = 'ph''otos'" in query
    assert "ORDER BY name" in query


async def test_get_storage_config_defaults_stats_when_query_returns_nothing() -> None:
    service = _sequenced_service([[{"exists": True}], list(BUCKETS), []])
    result = await service.get_storage_config()
    assert result["global_config"] == {"max_file_size_limit": None, "bucket_count": 1}


async def test_get_storage_config_nulls_non_numeric_max_limit() -> None:
    service = _sequenced_service(
        [[{"exists": True}], list(BUCKETS), [{"max_file_size_limit": "big", "bucket_count": 2}]]
    )
    result = await service.get_storage_config()
    assert result["global_config"] == {"max_file_size_limit": None, "bucket_count": 2}


async def test_get_storage_config_raises_upstream_sql_error() -> None:
    service = _sequenced_service([[{"exists": True}], SQL_ERROR])
    with pytest.raises(McpToolError) as exc_info:
        await service.get_storage_config()
    assert exc_info.value.message == (
        "SQL Error (42501): permission denied for table pg_publication"
    )


# ---------------------------------------------------------- update_storage_config


async def test_update_storage_config_reports_missing_storage_schema() -> None:
    service = _sequenced_service([[{"exists": False}]])
    result = await service.update_storage_config(bucket_id="photos", public=True)
    assert result == {
        "success": False,
        "bucket": None,
        "message": "Storage schema not found - Storage may not be configured",
    }
    assert len(service._client.calls) == 1


async def test_update_storage_config_reports_missing_bucket() -> None:
    service = _sequenced_service([[{"exists": True}], [{"exists": False}]])
    result = await service.update_storage_config(bucket_id="photos", public=True)
    assert result == {"success": False, "bucket": None, "message": "Bucket 'photos' not found"}
    assert "SELECT 1 FROM storage.buckets WHERE id = 'photos'" in (
        service._client.calls[1][1]["query"]
    )


async def test_update_storage_config_reports_missing_updates() -> None:
    service = _sequenced_service([[{"exists": True}], [{"exists": True}]])
    result = await service.update_storage_config(bucket_id="photos")
    assert result == {
        "success": False,
        "bucket": None,
        "message": (
            "No updates specified. Provide at least one of: file_size_limit, "
            "allowed_mime_types, or public"
        ),
    }


async def test_update_storage_config_applies_the_update() -> None:
    service = _sequenced_service(
        [[{"exists": True}], [{"exists": True}], [dict(UPDATED_BUCKET)]]
    )
    result = await service.update_storage_config(bucket_id="photos", public=True)
    assert result == {
        "success": True,
        "bucket": UPDATED_BUCKET,
        "message": "Successfully updated bucket 'photos'",
    }
    update_call = service._client.calls[2]
    assert update_call[0] == "execute_sql"
    assert update_call[1]["read_only"] is False
    assert "UPDATE storage.buckets" in update_call[1]["query"]
    assert "SET public = true, updated_at = NOW()" in update_call[1]["query"]
    assert "WHERE id = 'photos'" in update_call[1]["query"]
    assert "RETURNING id, name, public, file_size_limit, allowed_mime_types" in (
        update_call[1]["query"]
    )


async def test_update_storage_config_builds_the_dynamic_set_clause() -> None:
    service = _sequenced_service([[{"exists": True}], [{"exists": True}], []])
    await service.update_storage_config(
        bucket_id="b'x",
        file_size_limit=0,
        allowed_mime_types=["image/png'q", "image/jpeg"],
        public=False,
    )
    bucket_check_query = service._client.calls[1][1]["query"]
    assert "WHERE id = 'b''x'" in bucket_check_query
    update_query = service._client.calls[2][1]["query"]
    assert (
        "SET file_size_limit = NULL, "
        "allowed_mime_types = ARRAY['image/png''q', 'image/jpeg'], "
        "public = false, updated_at = NOW()" in update_query
    )
    assert "WHERE id = 'b''x'" in update_query


async def test_update_storage_config_uses_the_limit_value_directly() -> None:
    service = _sequenced_service([[{"exists": True}], [{"exists": True}], []])
    await service.update_storage_config(bucket_id="photos", file_size_limit=5242880)
    assert "SET file_size_limit = 5242880, updated_at = NOW()" in (
        service._client.calls[2][1]["query"]
    )


async def test_update_storage_config_clears_mime_types_with_an_empty_array() -> None:
    service = _sequenced_service([[{"exists": True}], [{"exists": True}], []])
    await service.update_storage_config(bucket_id="photos", allowed_mime_types=[])
    assert "SET allowed_mime_types = NULL, updated_at = NOW()" in (
        service._client.calls[2][1]["query"]
    )


async def test_update_storage_config_reports_update_errors_without_raising() -> None:
    service = _sequenced_service([[{"exists": True}], [{"exists": True}], SQL_ERROR])
    result = await service.update_storage_config(bucket_id="photos", public=True)
    assert result == {
        "success": False,
        "bucket": None,
        "message": "Failed to update bucket: permission denied for table pg_publication",
    }


async def test_update_storage_config_reports_empty_returning_rows() -> None:
    service = _sequenced_service([[{"exists": True}], [{"exists": True}], []])
    result = await service.update_storage_config(bucket_id="photos", public=True)
    assert result == {
        "success": False,
        "bucket": None,
        "message": "Update executed but no rows returned",
    }


_TOOL_NAMES = (
    "list_realtime_publications",
    "list_cron_jobs",
    "list_vector_indexes",
    "get_logs",
    "get_advisors",
    "get_storage_config",
    "update_storage_config",
)


# ------------------------------------------------------------------ tools layer


def test_tools_declare_risk_levels() -> None:
    for name in _TOOL_NAMES:
        expected = ToolRisk.WRITE if name == "update_storage_config" else ToolRisk.READ
        assert get_tool_risk(name) is expected, name


async def test_tool_functions_delegate_to_the_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StubService:
        async def list_realtime_publications(self) -> list[dict[str, Any]]:
            return [{"stub": "list_realtime_publications"}]

        async def list_cron_jobs(self) -> list[dict[str, Any]]:
            return [{"stub": "list_cron_jobs"}]

        async def list_vector_indexes(self) -> list[dict[str, Any]]:
            return [{"stub": "list_vector_indexes"}]

        async def get_logs(self, *, service: str, limit: int) -> dict[str, Any]:
            return {"stub": "get_logs", "service": service, "limit": limit}

        async def get_advisors(self, *, type: str) -> dict[str, Any]:
            return {"stub": "get_advisors", "type": type}

        async def get_storage_config(self, *, bucket_id: str | None) -> dict[str, Any]:
            return {"stub": "get_storage_config", "bucket_id": bucket_id}

        async def update_storage_config(
            self,
            *,
            bucket_id: str,
            file_size_limit: int | None,
            allowed_mime_types: list[str] | None,
            public: bool | None,
        ) -> dict[str, Any]:
            return {
                "stub": "update_storage_config",
                "bucket_id": bucket_id,
                "file_size_limit": file_size_limit,
                "allowed_mime_types": allowed_mime_types,
                "public": public,
            }

    monkeypatch.setattr(platform_tools, "PlatformService", StubService)
    assert json.loads(await platform_tools.list_realtime_publications()) == [
        {"stub": "list_realtime_publications"}
    ]
    assert json.loads(await platform_tools.list_cron_jobs()) == [
        {"stub": "list_cron_jobs"}
    ]
    assert json.loads(await platform_tools.list_vector_indexes()) == [
        {"stub": "list_vector_indexes"}
    ]
    assert await platform_tools.get_logs("postgres") == {
        "stub": "get_logs",
        "service": "postgres",
        "limit": 100,
    }
    assert await platform_tools.get_logs("auth", 5) == {
        "stub": "get_logs",
        "service": "auth",
        "limit": 5,
    }
    assert await platform_tools.get_advisors("security") == {
        "stub": "get_advisors",
        "type": "security",
    }
    assert await platform_tools.get_storage_config() == {
        "stub": "get_storage_config",
        "bucket_id": None,
    }
    assert await platform_tools.get_storage_config("b") == {
        "stub": "get_storage_config",
        "bucket_id": "b",
    }
    assert await platform_tools.update_storage_config("b") == {
        "stub": "update_storage_config",
        "bucket_id": "b",
        "file_size_limit": None,
        "allowed_mime_types": None,
        "public": None,
    }
    assert await platform_tools.update_storage_config(
        "b", 100, ["image/png"], True
    ) == {
        "stub": "update_storage_config",
        "bucket_id": "b",
        "file_size_limit": 100,
        "allowed_mime_types": ["image/png"],
        "public": True,
    }
