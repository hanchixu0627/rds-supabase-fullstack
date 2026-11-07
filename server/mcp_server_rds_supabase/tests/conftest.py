"""Shared fixtures: environment isolation and injectable fakes."""

import os
from typing import Any

import pytest

from mcp_server_rds_supabase.settings import RdsSupabaseSettings

_CLEAN_PREFIXES = (
    "SUPABASE_",
    "DATABASE_URL",
    "RDS_SUPABASE_",
    "HUAWEICLOUD_",
    "MCP_SERVER_",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate every test from the developer's real credentials."""
    for name in list(os.environ):
        if name.startswith(_CLEAN_PREFIXES):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HUAWEICLOUD_SKIP_DEVKIT_CREDENTIALS", "1")


def make_settings(**kwargs: Any) -> RdsSupabaseSettings:
    """Deterministic settings with no secrets, overridable per test."""
    defaults: dict[str, Any] = {
        "url": "http://supabase.local",
        "anon_key": "anon-test-key",
        "workspace_path": "/workspace",
    }
    defaults.update(kwargs)
    return RdsSupabaseSettings(**defaults)


@pytest.fixture
def settings() -> RdsSupabaseSettings:
    return make_settings()


class FakeRdsSupabaseClient:
    """Dynamic fake: records calls, returns configured responses."""

    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._responses = responses or {}
        self.settings: RdsSupabaseSettings | None = None
        self.service_role_available = False

    def __getattr__(self, name: str) -> Any:
        async def _method(**kwargs: Any) -> Any:
            calls = self.__dict__["calls"]
            calls.append((name, kwargs))
            response = self.__dict__["_responses"].get(name)
            if isinstance(response, Exception):
                raise response
            return [] if response is None else response

        return _method

    def is_service_role_available(self) -> bool:
        return self.service_role_available

    def get_supabase_url(self) -> str:
        return "http://supabase.local"

    def get_anon_key(self) -> str:
        return "anon-test-key"

    def get_service_role_key(self) -> str | None:
        return "service-test-key" if self.service_role_available else None

    def get_jwt_secret(self) -> str | None:
        return None


@pytest.fixture
def fake_client() -> FakeRdsSupabaseClient:
    return FakeRdsSupabaseClient()
