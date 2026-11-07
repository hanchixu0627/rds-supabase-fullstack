"""Tests for the auth users tool group (GoTrue admin API channel)."""

import json
from typing import Any

import pytest
from huaweicloud_mcp_core import McpToolError

from mcp_server_rds_supabase.service.auth_users_service import AuthUsersService
from mcp_server_rds_supabase.tools import auth_users as auth_users_tools
from tests.conftest import make_settings

USER_ID = "5773cc6a-52a6-4554-8e58-2d7253257d96"

GOTRUE_USER: dict[str, Any] = {
    "id": USER_ID,
    "aud": "authenticated",
    "role": "authenticated",
    "email": "user@demo.edu",
    "phone": "",
    "identities": [],
    "is_anonymous": False,
    "created_at": "2026-10-31T01:52:48.687163+08:00",
    "last_sign_in_at": "2026-10-31T01:52:49.044582+08:00",
    "updated_at": "2026-10-31T01:52:49.100000+08:00",
    "email_confirmed_at": "2026-10-31T01:52:48.700000+08:00",
    "confirmed_at": "2026-10-31T01:52:48.700000+08:00",
    "app_metadata": {"provider": "email", "providers": ["email"]},
    "user_metadata": {"name": "User"},
}

MAPPED_USER: dict[str, Any] = {
    "id": USER_ID,
    "email": "user@demo.edu",
    "role": "authenticated",
    "created_at": "2026-10-31T01:52:48.687163+08:00",
    "last_sign_in_at": "2026-10-31T01:52:49.044582+08:00",
    "raw_app_meta_data": {"provider": "email", "providers": ["email"]},
    "raw_user_meta_data": {"name": "User"},
}


class SequencedClient:
    """Fake client whose admin methods return queued (status, body) tuples."""

    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, tuple, dict]] = []
        self.service_role_available = True

    def __getattr__(self, name: str) -> Any:
        async def method(*args: Any, **kwargs: Any) -> Any:
            calls = self.__dict__["calls"]
            calls.append((name, args, kwargs))
            item = self.__dict__["_responses"].pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        return method

    def is_service_role_available(self) -> bool:
        return self.service_role_available


def _service(responses: list[Any]) -> tuple[AuthUsersService, SequencedClient]:
    client = SequencedClient(responses)
    return AuthUsersService(client=client, settings=make_settings()), client


def _users(n: int) -> list[dict[str, Any]]:
    return [
        {**GOTRUE_USER, "id": f"00000000-0000-0000-0000-{i:012d}", "email": f"u{i}@x.io"}
        for i in range(n)
    ]


# ------------------------------------------------------------------ precheck

@pytest.mark.parametrize(
    ("method", "kwargs", "action"),
    [
        ("list_auth_users", {}, "list"),
        ("get_auth_user", {"user_id": USER_ID}, "get"),
        ("delete_auth_user", {"user_id": USER_ID}, "delete"),
        ("create_auth_user", {"email": "a@b.c", "password": "secret1"}, "create"),
        ("update_auth_user", {"user_id": USER_ID, "email": "a@b.c"}, "update"),
    ],
)
async def test_without_service_key_the_channel_error_is_exact(
    method: str, kwargs: dict[str, Any], action: str
) -> None:
    service, _client = _service([(200, {"users": []})])
    _client.service_role_available = False
    with pytest.raises(McpToolError) as exc_info:
        await getattr(service, method)(**kwargs)
    assert exc_info.value.message == (
        f"Service role key (SUPABASE_SERVICE_ROLE_KEY) is required to {action} auth users."
    )


# ---------------------------------------------------------------------- list

async def test_list_maps_gotrue_rows_to_the_upstream_shape() -> None:
    service, _client = _service([(200, {"users": [GOTRUE_USER]})])
    assert await service.list_auth_users(limit=50, offset=0) == [MAPPED_USER]


async def test_list_missing_last_sign_in_at_maps_to_none() -> None:
    raw = {k: v for k, v in GOTRUE_USER.items() if k != "last_sign_in_at"}
    service, _client = _service([(200, {"users": [raw]})])
    result = await service.list_auth_users(limit=1, offset=0)
    assert result[0]["last_sign_in_at"] is None
    assert result[0]["id"] == USER_ID


async def test_list_requests_the_aligned_page_for_plain_offset() -> None:
    users = _users(6)
    service, client = _service([(200, {"users": users[2:4]})])
    result = await service.list_auth_users(limit=2, offset=2)
    assert [u["id"] for u in result] == [users[2]["id"], users[3]["id"]]
    assert client.calls == [("auth_admin_list_users", (), {"page": 2, "per_page": 2})]


async def test_list_assembles_windows_spanning_two_pages() -> None:
    users = _users(5)
    service, client = _service(
        [(200, {"users": users[0:3]}), (200, {"users": users[3:5]})]
    )
    result = await service.list_auth_users(limit=3, offset=1)
    assert [u["id"] for u in result] == [users[1]["id"], users[2]["id"], users[3]["id"]]
    pages = [kwargs for _name, _args, kwargs in client.calls]
    assert pages == [{"page": 1, "per_page": 3}, {"page": 2, "per_page": 3}]


async def test_list_beyond_the_end_returns_empty() -> None:
    service, _client = _service([(200, {"users": []})])
    assert await service.list_auth_users(limit=10, offset=100) == []


async def test_list_short_page_stops_fetching() -> None:
    users = _users(2)
    service, client = _service([(200, {"users": users})])
    result = await service.list_auth_users(limit=50, offset=0)
    assert len(result) == 2
    assert len(client.calls) == 1


async def test_list_admin_error_is_wrapped() -> None:
    service, _client = _service([(500, {"msg": "boom"})])
    with pytest.raises(McpToolError) as exc_info:
        await service.list_auth_users(limit=10, offset=0)
    assert exc_info.value.message == (
        "Auth admin API returned 500 while trying to list auth users: boom"
    )


async def test_list_transport_failure_is_wrapped() -> None:
    service, _client = _service([(0, {"msg": "Exception during auth admin call: down"})])
    with pytest.raises(McpToolError) as exc_info:
        await service.list_auth_users(limit=10, offset=0)
    assert exc_info.value.message == (
        "Auth admin API request failed while trying to list auth users: "
        "Exception during auth admin call: down"
    )


# ----------------------------------------------------------------------- get

async def test_get_returns_the_mapped_user() -> None:
    service, _client = _service([(200, GOTRUE_USER)])
    assert await service.get_auth_user(user_id=USER_ID) == MAPPED_USER


async def test_get_missing_user_raises_the_upstream_message() -> None:
    service, _client = _service(
        [(404, {"code": 404, "error_code": "user_not_found", "msg": "User not found"})]
    )
    with pytest.raises(McpToolError) as exc_info:
        await service.get_auth_user(user_id=USER_ID)
    assert exc_info.value.message == f"User with ID {USER_ID} not found."


async def test_get_unexpected_status_is_wrapped() -> None:
    service, _client = _service([(502, {"msg": "bad gateway"})])
    with pytest.raises(McpToolError) as exc_info:
        await service.get_auth_user(user_id=USER_ID)
    assert exc_info.value.message == (
        "Auth admin API returned 502 while trying to get auth user details: bad gateway"
    )


# -------------------------------------------------------------------- delete

async def test_delete_success_returns_the_upstream_message() -> None:
    service, _client = _service([(200, {})])
    assert await service.delete_auth_user(user_id=USER_ID) == {
        "success": True,
        "message": f"Successfully deleted user with ID: {USER_ID}",
    }


async def test_delete_missing_returns_the_structured_upstream_message() -> None:
    service, _client = _service(
        [(404, {"code": 404, "error_code": "user_not_found", "msg": "User not found"})]
    )
    assert await service.delete_auth_user(user_id=USER_ID) == {
        "success": False,
        "message": f"User with ID {USER_ID} not found or could not be deleted.",
    }


# -------------------------------------------------------------------- create

async def test_create_maps_the_created_user() -> None:
    service, client = _service([(200, GOTRUE_USER)])
    result = await service.create_auth_user(
        email="user@demo.edu", password="secret1", role=None
    )
    assert result == MAPPED_USER
    _name, args, _kwargs = client.calls[0]
    assert args[0] == {
        "email": "user@demo.edu",
        "password": "secret1",
        "email_confirm": True,
    }


async def test_create_forwards_metadata_and_never_role() -> None:
    service, client = _service([(200, GOTRUE_USER)])
    await service.create_auth_user(
        email="user@demo.edu",
        password="secret1",
        role="supabase_admin",
        app_metadata={"x": 1},
        user_metadata={"y": 2},
    )
    _name, args, _kwargs = client.calls[0]
    assert args[0] == {
        "email": "user@demo.edu",
        "password": "secret1",
        "email_confirm": True,
        "app_metadata": {"x": 1},
        "user_metadata": {"y": 2},
    }


async def test_create_duplicate_email_raises_the_upstream_message() -> None:
    service, _client = _service(
        [(422, {"code": 422, "error_code": "email_exists",
                "msg": "A user with this email address has already been registered"})]
    )
    with pytest.raises(McpToolError) as exc_info:
        await service.create_auth_user(email="user@demo.edu", password="secret1")
    assert exc_info.value.message == (
        "User creation failed: Email 'user@demo.edu' likely already exists."
    )


async def test_create_other_failures_wrap_the_gotrue_message() -> None:
    service, _client = _service(
        [(422, {"code": 422, "error_code": "weak_password",
                "msg": "Password should be at least 6 characters"})]
    )
    with pytest.raises(McpToolError) as exc_info:
        await service.create_auth_user(email="user@demo.edu", password="1")
    assert exc_info.value.message == (
        "User creation failed: Password should be at least 6 characters"
    )


# -------------------------------------------------------------------- update

async def test_update_requires_at_least_one_field() -> None:
    service, client = _service([])
    with pytest.raises(McpToolError) as exc_info:
        await service.update_auth_user(user_id=USER_ID)
    assert exc_info.value.message == (
        "At least one field to update (email, password, role, app_metadata, "
        "user_metadata) must be provided."
    )
    assert client.calls == []


async def test_update_role_only_is_unsupported_and_makes_no_call() -> None:
    service, client = _service([])
    with pytest.raises(McpToolError) as exc_info:
        await service.update_auth_user(user_id=USER_ID, role="authenticated")
    assert exc_info.value.message == (
        "Updating role is not supported through the auth admin API; "
        "provide email, password, app_metadata or user_metadata."
    )
    assert client.calls == []


async def test_update_empty_string_fields_do_not_count() -> None:
    service, client = _service([])
    with pytest.raises(McpToolError) as exc_info:
        await service.update_auth_user(user_id=USER_ID, email="", password="")
    assert "At least one field to update" in exc_info.value.message
    assert client.calls == []


async def test_update_returns_the_row_with_updated_at() -> None:
    service, client = _service([(200, GOTRUE_USER)])
    result = await service.update_auth_user(
        user_id=USER_ID, user_metadata={"name": "User"}
    )
    assert result == {**MAPPED_USER, "updated_at": GOTRUE_USER["updated_at"]}
    _name, args, _kwargs = client.calls[0]
    assert args[0] == USER_ID
    assert args[1] == {"user_metadata": {"name": "User"}}


async def test_update_empty_metadata_object_still_counts() -> None:
    service, client = _service([(200, GOTRUE_USER)])
    await service.update_auth_user(user_id=USER_ID, app_metadata={})
    _name, args, _kwargs = client.calls[0]
    assert args[1] == {"app_metadata": {}}


async def test_update_missing_user_raises_the_upstream_message() -> None:
    service, _client = _service(
        [(404, {"code": 404, "error_code": "user_not_found", "msg": "User not found"})]
    )
    with pytest.raises(McpToolError) as exc_info:
        await service.update_auth_user(user_id=USER_ID, email="new@x.io")
    assert exc_info.value.message == (
        f"User update failed: User with ID {USER_ID} not found or no rows affected."
    )


async def test_update_duplicate_email_raises_the_upstream_message() -> None:
    service, _client = _service(
        [(500, {"code": "23505",
                "message": 'duplicate key value violates unique constraint '
                           '"users_email_partial_key"',
                "detail": "Key (email)=(x@y.io) already exists."})]
    )
    with pytest.raises(McpToolError) as exc_info:
        await service.update_auth_user(user_id=USER_ID, email="x@y.io")
    assert exc_info.value.message == (
        "User update failed: Email 'x@y.io' likely already exists for another user."
    )


async def test_update_other_500s_wrap_the_gotrue_message() -> None:
    service, _client = _service([(500, {"code": "XX000", "message": "internal"})])
    with pytest.raises(McpToolError) as exc_info:
        await service.update_auth_user(user_id=USER_ID, email="new@x.io")
    assert exc_info.value.message == "User update failed: internal"


# ----------------------------------------------------------- tools delegation

async def test_tool_functions_delegate_to_the_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StubService:
        async def list_auth_users(self, *, limit: int = 50, offset: int = 0):
            return [{"id": "u1", "limit": limit, "offset": offset}]

        async def get_auth_user(self, *, user_id: str):
            return {"id": user_id}

        async def delete_auth_user(self, *, user_id: str):
            return {"success": True, "message": f"deleted {user_id}"}

        async def create_auth_user(self, *, email: str, password: str,
                                   role=None, app_metadata=None, user_metadata=None):
            return {"email": email, "password": password, "role": role,
                    "app_metadata": app_metadata, "user_metadata": user_metadata}

        async def update_auth_user(self, *, user_id: str, email=None, password=None,
                                   role=None, app_metadata=None, user_metadata=None):
            return {"id": user_id, "email": email, "password": password,
                    "role": role, "app_metadata": app_metadata,
                    "user_metadata": user_metadata}

    monkeypatch.setattr(auth_users_tools, "AuthUsersService", StubService)
    assert json.loads(await auth_users_tools.list_auth_users(10, 20)) == [
        {"id": "u1", "limit": 10, "offset": 20}
    ]
    assert await auth_users_tools.get_auth_user(USER_ID) == {"id": USER_ID}
    assert await auth_users_tools.delete_auth_user(USER_ID) == {
        "success": True,
        "message": f"deleted {USER_ID}",
    }
    assert await auth_users_tools.create_auth_user(
        "a@b.c", "secret1", app_metadata={"x": 1}
    ) == {"email": "a@b.c", "password": "secret1", "role": None,
          "app_metadata": {"x": 1}, "user_metadata": None}
    assert await auth_users_tools.update_auth_user(
        USER_ID, email="new@x.io"
    ) == {"id": USER_ID, "email": "new@x.io", "password": None, "role": None,
          "app_metadata": None, "user_metadata": None}
