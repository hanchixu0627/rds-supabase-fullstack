"""Tests for the project tool group (fake client)."""

from typing import Any

import pytest

from mcp_server_rds_supabase.service.project_service import ProjectService
from mcp_server_rds_supabase.settings import RdsSupabaseSettings
from tests.conftest import FakeRdsSupabaseClient, make_settings

_TYPES_OUTPUT = "export type Foo = { id: number };\n"


def _service(
    responses: dict[str, Any] | None = None,
    settings: RdsSupabaseSettings | None = None,
) -> ProjectService:
    return ProjectService(
        client=FakeRdsSupabaseClient(responses),
        settings=settings or make_settings(),
    )


def _fake_run_ok(
    monkeypatch: pytest.MonkeyPatch, stdout: str = _TYPES_OUTPUT, stderr: str = ""
) -> None:
    async def fake_run(command: str) -> dict[str, Any]:
        return {"stdout": stdout, "stderr": stderr, "error": None}

    monkeypatch.setattr(
        "mcp_server_rds_supabase.service.support.run_external_command", fake_run
    )


async def test_get_project_url_returns_client_url() -> None:
    service = _service()
    assert await service.get_project_url() == {"project_url": "http://supabase.local"}


async def test_verify_jwt_secret_reports_not_configured() -> None:
    service = _service()
    assert await service.verify_jwt_secret() == {"jwt_secret_status": "not_configured"}


async def test_verify_jwt_secret_reports_found_without_echoing_it() -> None:
    class JwtFakeClient(FakeRdsSupabaseClient):
        def __init__(self, secret: str | None) -> None:
            super().__init__()
            self._jwt_secret = secret

        def get_jwt_secret(self) -> str | None:
            return self._jwt_secret

    service = ProjectService(
        client=JwtFakeClient("super-secret-value"),
        settings=make_settings(),
    )
    result = await service.verify_jwt_secret()
    assert result == {"jwt_secret_status": "found"}
    assert "super-secret-value" not in str(result)


async def test_rebuild_hooks_reports_success() -> None:
    service = _service({"execute_sql": [{"worker_restart": True}]})
    result = await service.rebuild_hooks()
    assert result == {"success": True, "message": "pg_net worker restart requested successfully."}
    assert service._client.calls == [
        ("execute_sql", {"query": "SELECT net.worker_restart()", "read_only": False})
    ]


async def test_rebuild_hooks_pg_net_missing_appends_hint() -> None:
    service = _service(
        {
            "execute_sql": {
                "error": {
                    "message": "function net.worker_restart() does not exist",
                    "code": "42883",
                }
            }
        }
    )
    result = await service.rebuild_hooks()
    assert result == {
        "success": False,
        "message": (
            "Failed to restart pg_net worker: function net.worker_restart() does not exist"
            " (Is pg_net installed and enabled?)"
        ),
    }


async def test_rebuild_hooks_other_error_has_no_hint_suffix() -> None:
    service = _service(
        {
            "execute_sql": {
                "error": {"message": "permission denied", "code": "42501"}
            }
        }
    )
    result = await service.rebuild_hooks()
    assert result == {
        "success": False,
        "message": "Failed to restart pg_net worker: permission denied",
    }


async def test_rebuild_hooks_without_channels_reports_config_error() -> None:
    service = _service(
        {
            "execute_sql": {
                "error": {
                    "message": (
                        "Neither direct database connection (DATABASE_URL) nor service role key "
                        "(SUPABASE_SERVICE_ROLE_KEY) is configured. Cannot execute SQL."
                    ),
                    "code": "MCP_CONFIG_ERROR",
                }
            }
        }
    )
    result = await service.rebuild_hooks()
    assert result == {
        "success": False,
        "message": (
            "Failed to restart pg_net worker: Neither direct database connection (DATABASE_URL) "
            "nor service role key (SUPABASE_SERVICE_ROLE_KEY) is configured. Cannot execute SQL."
        ),
    }


async def test_rebuild_hooks_wraps_exceptions() -> None:
    service = _service({"execute_sql": RuntimeError("boom")})
    result = await service.rebuild_hooks()
    assert result == {
        "success": False,
        "message": "Exception attempting to restart pg_net worker: boom",
    }


async def test_tool_functions_delegate_to_the_service(monkeypatch: pytest.MonkeyPatch) -> None:
    from mcp_server_rds_supabase.server import mcp
    from mcp_server_rds_supabase.tools import project as project_tools

    class StubService:
        async def get_project_url(self) -> dict[str, Any]:
            return {"project_url": "http://stub"}

        async def verify_jwt_secret(self) -> dict[str, Any]:
            return {"jwt_secret_status": "found"}

        async def rebuild_hooks(self) -> dict[str, Any]:
            return {"success": True, "message": "stub restart"}

        async def generate_typescript_types(
            self,
            *,
            included_schemas: list[str] | None = None,
            output_filename: str = "database.types.ts",
            output_path: str = "",
        ) -> dict[str, Any]:
            return {
                "included_schemas": included_schemas,
                "output_filename": output_filename,
                "output_path": output_path,
            }

    monkeypatch.setattr(project_tools, "ProjectService", StubService)
    assert await project_tools.get_project_url() == {"project_url": "http://stub"}
    assert await project_tools.verify_jwt_secret() == {"jwt_secret_status": "found"}
    assert await project_tools.rebuild_hooks() == {"success": True, "message": "stub restart"}
    assert await project_tools.generate_typescript_types(
        output_path="/tmp/database.types.ts"
    ) == {
        "included_schemas": ["public"],
        "output_filename": "database.types.ts",
        "output_path": "/tmp/database.types.ts",
    }
    assert await project_tools.generate_typescript_types(
        ["auth", "storage"], "custom.ts", output_path="/tmp/database.types.ts"
    ) == {
        "included_schemas": ["auth", "storage"],
        "output_filename": "custom.ts",
        "output_path": "/tmp/database.types.ts",
    }
    tools = {tool.name: tool for tool in await mcp.list_tools()}
    generate_schema = tools["generate_typescript_types"].input_schema
    assert generate_schema["required"] == ["output_path"]
    assert generate_schema["properties"]["included_schemas"]["default"] == ["public"]
    assert generate_schema["properties"]["output_filename"]["default"] == "database.types.ts"
