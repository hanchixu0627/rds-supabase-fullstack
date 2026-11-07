"""Tests for the RdsSupabase client: RPC, direct pg, fallback and probe."""

import json
from typing import Any

import httpx
import pytest

from mcp_server_rds_supabase.client.rds_supabase_client import RdsSupabaseClient
from mcp_server_rds_supabase.settings import RdsSupabaseSettings


def _settings(**kwargs: Any) -> RdsSupabaseSettings:
    defaults: dict[str, Any] = {
        "url": "http://supabase.local",
        "anon_key": "anon-test-key",
        "workspace_path": "/workspace",
    }
    defaults.update(kwargs)
    return RdsSupabaseSettings(**defaults)


def _http(handler: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_rpc_success_returns_rows() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/rpc/execute_sql"
        assert request.headers["apikey"] == "anon-test-key"
        assert request.headers["authorization"] == "Bearer anon-test-key"
        assert json.loads(request.read()) == {"query": "SELECT 1", "read_only": False}
        return httpx.Response(200, json=[{"?column?": 1}])

    client = RdsSupabaseClient(_settings(), http_client=_http(handler))
    client.rpc_function_exists = True
    assert await client.execute_sql_via_rpc("SELECT 1") == [{"?column?": 1}]


async def test_rpc_without_flag_returns_client_error() -> None:
    client = RdsSupabaseClient(
        _settings(), http_client=_http(lambda r: httpx.Response(200, json=[]))
    )
    result = await client.execute_sql_via_rpc("SELECT 1")
    assert result == {
        "error": {
            "message": "execute_sql RPC function not found or client not properly initialized.",
            "code": "MCP_CLIENT_ERROR",
        }
    }


async def test_rpc_postgrest_error_is_passed_through() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "code": "42P01",
                "message": "relation does not exist",
                "details": "detail text",
                "hint": "hint text",
            },
        )

    client = RdsSupabaseClient(_settings(), http_client=_http(handler))
    client.rpc_function_exists = True
    assert await client.execute_sql_via_rpc("SELECT * FROM missing") == {
        "error": {
            "message": "relation does not exist",
            "code": "42P01",
            "details": "detail text",
            "hint": "hint text",
        }
    }


async def test_rpc_non_array_response_returns_format_error() -> None:
    client = RdsSupabaseClient(
        _settings(), http_client=_http(lambda r: httpx.Response(200, json={"a": 1}))
    )
    client.rpc_function_exists = True
    assert await client.execute_sql_via_rpc("SELECT 1") == {
        "error": {
            "message": "Unexpected response format from execute_sql RPC. Expected JSON array.",
            "code": "MCP_RPC_FORMAT_ERROR",
        }
    }


async def test_rpc_transport_failure_returns_exception_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = RdsSupabaseClient(_settings(), http_client=_http(handler))
    client.rpc_function_exists = True
    result = await client.execute_sql_via_rpc("SELECT 1")
    assert result["error"]["code"] == "MCP_RPC_EXCEPTION"  # type: ignore[index]
    assert (  # type: ignore[index]
        result["error"]["message"] == "Exception during RPC call: boom"
    )


async def test_service_role_rpc_requires_key_then_succeeds() -> None:
    client = RdsSupabaseClient(
        _settings(), http_client=_http(lambda r: httpx.Response(200, json=[]))
    )
    client.rpc_function_exists = True
    assert await client.execute_sql_via_service_role_rpc("SELECT 1") == {
        "error": {
            "message": "Service role key not configured. Cannot execute privileged SQL via RPC.",
            "code": "MCP_CONFIG_ERROR",
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["apikey"] == "service-test-key"
        return httpx.Response(200, json=[{"ok": True}])

    client = RdsSupabaseClient(
        _settings(service_role_key="service-test-key"), http_client=_http(handler)
    )
    client.rpc_function_exists = True
    result = await client.execute_sql_via_service_role_rpc("SELECT 1", read_only=True)
    assert result == [{"ok": True}]


async def test_service_role_rpc_exception_has_service_label() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    client = RdsSupabaseClient(
        _settings(service_role_key="service-test-key"), http_client=_http(handler)
    )
    client.rpc_function_exists = True
    result = await client.execute_sql_via_service_role_rpc("SELECT 1")
    assert result["error"]["code"] == "MCP_RPC_EXCEPTION"  # type: ignore[index]
    assert (  # type: ignore[index]
        result["error"]["message"] == "Exception during Service Role RPC call: timed out"
    )


async def test_probe_marks_function_available_on_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.read()) == {"query": "SELECT 1"}
        return httpx.Response(200, json=[{"?column?": 1}])

    client = RdsSupabaseClient(
        _settings(service_role_key="service-test-key"), http_client=_http(handler)
    )
    await client.check_and_create_rpc_function()
    assert client.rpc_function_exists is True


async def test_probe_missing_function_without_service_key_stays_unavailable() -> None:
    client = RdsSupabaseClient(
        _settings(),
        http_client=_http(
            lambda r: httpx.Response(404, json={"code": "PGRST202", "message": "not found"})
        ),
    )
    await client.check_and_create_rpc_function()
    assert client.rpc_function_exists is False


async def test_probe_unexpected_error_code_raises() -> None:
    client = RdsSupabaseClient(
        _settings(service_role_key="service-test-key"),
        http_client=_http(
            lambda r: httpx.Response(400, json={"code": "42501", "message": "denied"})
        ),
    )
    with pytest.raises(RuntimeError, match=r"^Error checking for execute_sql function: denied$"):
        await client.check_and_create_rpc_function()


async def test_probe_transport_failure_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = RdsSupabaseClient(_settings(), http_client=_http(handler))
    with pytest.raises(RuntimeError, match=r"^Exception during RPC function check/creation: boom$"):
        await client.check_and_create_rpc_function()


def test_getters_reflect_settings() -> None:
    client = RdsSupabaseClient(
        _settings(service_role_key="service-test-key", jwt_secret="s")
    )
    assert client.get_supabase_url() == "http://supabase.local"
    assert client.get_anon_key() == "anon-test-key"
    assert client.get_service_role_key() == "service-test-key"
    assert client.get_jwt_secret() == "s"
    assert client.is_service_role_available() is True

    bare = RdsSupabaseClient(_settings())
    assert bare.is_service_role_available() is False


async def test_execute_sql_channel_delegates_to_the_service_role_rpc() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["apikey"] == "service-test-key"
        return httpx.Response(200, json=[{"src": "rpc"}])

    client = RdsSupabaseClient(
        _settings(service_role_key="service-test-key"), http_client=_http(handler)
    )
    client.rpc_function_exists = True
    assert await client.execute_sql("SELECT 1", read_only=True) == [{"src": "rpc"}]


async def test_execute_sql_without_service_key_is_config_error() -> None:
    client = RdsSupabaseClient(_settings())
    assert await client.execute_sql("SELECT 1") == {
        "error": {
            "message": (
                "Service role key (SUPABASE_SERVICE_ROLE_KEY) is not configured. "
                "Cannot execute SQL."
            ),
            "code": "MCP_CONFIG_ERROR",
        }
    }


async def test_shared_client_is_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    import mcp_server_rds_supabase.client.rds_supabase_client as client_module

    monkeypatch.setattr(client_module.RdsSupabaseClient, "_shared_client", None)
    monkeypatch.setattr(
        client_module.RdsSupabaseSettings,
        "from_env",
        classmethod(lambda cls: _settings()),
    )
    try:
        first = RdsSupabaseClient.shared()
        second = RdsSupabaseClient.shared()
        assert first is second
    finally:
        monkeypatch.setattr(client_module.RdsSupabaseClient, "_shared_client", None)


# ------------------------------------------------------------ auth admin API

async def test_auth_admin_list_users_sends_service_headers_and_params() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/auth/v1/admin/users"
        assert request.url.params["page"] == "2"
        assert request.url.params["per_page"] == "50"
        assert request.headers["apikey"] == "service-test-key"
        assert request.headers["authorization"] == "Bearer service-test-key"
        return httpx.Response(200, json={"aud": "authenticated", "users": []})

    client = RdsSupabaseClient(
        _settings(service_role_key="service-test-key"), http_client=_http(handler)
    )
    assert await client.auth_admin_list_users(page=2, per_page=50) == (
        200,
        {"aud": "authenticated", "users": []},
    )


async def test_auth_admin_get_user_targets_the_id_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/auth/v1/admin/users/abc-123"
        return httpx.Response(200, json={"id": "abc-123"})

    client = RdsSupabaseClient(
        _settings(service_role_key="service-test-key"), http_client=_http(handler)
    )
    assert await client.auth_admin_get_user("abc-123") == (200, {"id": "abc-123"})


async def test_auth_admin_create_and_update_forward_the_payload() -> None:
    seen: list[tuple[str, str, dict[str, Any]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, json.loads(request.read())))
        return httpx.Response(200, json={"id": "abc-123"})

    client = RdsSupabaseClient(
        _settings(service_role_key="service-test-key"), http_client=_http(handler)
    )
    payload = {"email": "a@b.c", "password": "secret1", "email_confirm": True}
    assert await client.auth_admin_create_user(payload) == (200, {"id": "abc-123"})
    assert await client.auth_admin_update_user("abc-123", {"email": "x@y.z"}) == (
        200,
        {"id": "abc-123"},
    )
    assert seen[0] == ("POST", "/auth/v1/admin/users", payload)
    assert seen[1] == ("PUT", "/auth/v1/admin/users/abc-123", {"email": "x@y.z"})


async def test_auth_admin_delete_handles_empty_and_json_bodies() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        return httpx.Response(200, json={})

    client = RdsSupabaseClient(
        _settings(service_role_key="service-test-key"), http_client=_http(handler)
    )
    assert await client.auth_admin_delete_user("abc-123") == (200, {})

    def empty_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"")

    client = RdsSupabaseClient(
        _settings(service_role_key="service-test-key"), http_client=_http(empty_handler)
    )
    assert await client.auth_admin_delete_user("abc-123") == (200, None)


async def test_auth_admin_transport_failure_returns_status_zero() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("gateway down")

    client = RdsSupabaseClient(
        _settings(service_role_key="service-test-key"), http_client=_http(handler)
    )
    status, body = await client.auth_admin_get_user("abc-123")
    assert status == 0
    assert "gateway down" in body["msg"]
