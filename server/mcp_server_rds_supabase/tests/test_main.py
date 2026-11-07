"""Tests for the console entry point and the tools-config whitelist."""

import asyncio
import json
from pathlib import Path

import pytest

from mcp_server_rds_supabase.main import main
from mcp_server_rds_supabase.server import mcp
from mcp_server_rds_supabase.tools_config import apply_tools_config


def test_main_exits_when_url_is_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    assert capsys.readouterr().err == (
        "Error: Supabase URL is required. Use --url or SUPABASE_URL.\n"
    )


def test_main_exits_when_anon_key_is_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.local")
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    assert capsys.readouterr().err == (
        "Error: Supabase Anon Key is required. Use --anon-key or SUPABASE_ANON_KEY.\n"
    )


def test_main_probes_and_runs(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.local")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-test-key")

    async def fake_startup(settings: object) -> None:
        print("startup-ok", settings.url)  # type: ignore[attr-defined]

    import mcp_server_rds_supabase.main as main_module

    monkeypatch.setattr(main_module, "_startup", fake_startup)
    monkeypatch.setattr(main_module, "run_standard", lambda server, service_name: print("run-ok"))
    main()
    captured = capsys.readouterr()
    assert "startup-ok http://supabase.local" in captured.out
    assert "run-ok" in captured.out


def test_main_startup_failure_is_logged_and_server_still_runs(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.local")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-test-key")

    async def failing_startup(settings: object) -> None:
        raise RuntimeError("gateway down")

    import mcp_server_rds_supabase.main as main_module

    monkeypatch.setattr(main_module, "_startup", failing_startup)
    monkeypatch.setattr(main_module, "run_standard", lambda server, service_name: print("run-ok"))
    main()
    captured = capsys.readouterr()
    assert "Error during client initialization: gateway down" in captured.err
    assert "run-ok" in captured.out


async def test_tools_config_without_path_enables_all(
    capsys: pytest.CaptureFixture[str],
) -> None:
    await apply_tools_config(None, mcp)
    assert len(await mcp.list_tools()) == 38
    assert "enabling all available tools." in capsys.readouterr().err


async def test_tools_config_whitelist_filters_and_warns(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = tmp_path / "tools.json"
    config.write_text(
        json.dumps({"enabledTools": ["list_tables", "get_project_url", "ghost_tool", "  "]}),
        encoding="utf-8",
    )
    await apply_tools_config(str(config), mcp)
    captured = capsys.readouterr()
    remaining = {tool.name for tool in await mcp.list_tools()}
    assert remaining == {"list_tables", "get_project_url"}
    assert 'Warning: Tool "ghost_tool" specified in config file not found.' in captured.err
    assert "Tool execute_sql disabled (not in config whitelist)." in captured.err
    assert "Whitelisting tools based on config: list_tables, get_project_url" in captured.err


async def test_tools_config_invalid_format_falls_back_to_all(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "tools.json"
    config.write_text('{"enabledTools": "not-a-list"}', encoding="utf-8")
    await apply_tools_config(str(config), mcp)
    captured = capsys.readouterr()
    assert len(await mcp.list_tools()) == 38
    assert "Falling back to enabling all tools due to config error." in captured.err
    assert 'Invalid config file format. Expected { "enabledTools": ["tool1", ...] }.' in (
        captured.err
    )


async def test_tools_config_non_string_entries_fall_back_to_all(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "tools.json"
    config.write_text('{"enabledTools": ["list_tables", 42]}', encoding="utf-8")
    await apply_tools_config(str(config), mcp)
    captured = capsys.readouterr()
    assert len(await mcp.list_tools()) == 38
    assert (
        'Invalid config file content. "enabledTools" must be an array of strings.'
        in captured.err
    )


async def test_tools_config_missing_file_falls_back_to_all(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    await apply_tools_config(str(tmp_path / "missing.json"), mcp)
    captured = capsys.readouterr()
    assert len(await mcp.list_tools()) == 38
    assert "Tool configuration file not found at" in captured.err
    assert "Falling back to enabling all tools due to config error." in captured.err


async def test_tools_config_empty_whitelist_disables_everything(
    tmp_path: Path,
) -> None:
    config = tmp_path / "tools.json"
    config.write_text('{"enabledTools": []}', encoding="utf-8")
    await apply_tools_config(str(config), mcp)
    assert await mcp.list_tools() == []


@pytest.fixture(autouse=True)
def _restore_all_tools() -> None:
    """Restore the canonical 43-tool registration after whitelist tests.

    remove_tool is destructive on the shared server, so the fixture re-adds
    every tool function in upstream order once a test narrowed the registry.
    """
    yield
    asyncio.run(_restore_canonical_registration())


async def _restore_canonical_registration() -> None:
    from mcp_server_rds_supabase.tools import (
        auth_users,
        database,
        inspection,
        platform,
        project,
        storage,
    )

    name_to_fn: dict[str, object] = {}
    for module in (database, project, auth_users, storage, platform, inspection):
        for attr in dir(module):
            if attr in _ALL_TOOL_NAMES:
                name_to_fn[attr] = getattr(module, attr)
    current = [tool.name for tool in await mcp.list_tools()]
    if current == _ALL_TOOL_NAMES:
        return
    for name in current:
        mcp.remove_tool(name)
    for name in _ALL_TOOL_NAMES:
        mcp.add_tool(name_to_fn[name])  # type: ignore[arg-type]
    assert [tool.name for tool in await mcp.list_tools()] == _ALL_TOOL_NAMES


_ALL_TOOL_NAMES = [
    "list_tables",
    "list_extensions",
    "execute_sql",
    "get_database_connections",
    "get_database_stats",
    "get_project_url",
    "generate_typescript_types",
    "rebuild_hooks",
    "verify_jwt_secret",
    "list_auth_users",
    "get_auth_user",
    "delete_auth_user",
    "create_auth_user",
    "update_auth_user",
    "list_storage_buckets",
    "list_storage_objects",
    "list_realtime_publications",
    "list_cron_jobs",
    "list_vector_indexes",
    "get_logs",
    "get_advisors",
    "get_storage_config",
    "update_storage_config",
    "list_table_columns",
    "list_indexes",
    "list_constraints",
    "list_foreign_keys",
    "list_rls_policies",
    "list_triggers",
    "list_database_functions",
    "get_function_definition",
    "get_trigger_definition",
    "get_rls_status",
    "list_available_extensions",
    "get_cron_job_history",
    "get_index_stats",
    "get_vector_index_stats",
    "explain_query",
]
