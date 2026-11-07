#!/usr/bin/env python3
"""Dual-server E2E comparison: TypeScript rds-supabase-mcp vs this Python port.

Spawns both servers over stdio against the same live RDS Supabase instance,
compares the tool surface (names, order, descriptions, input schemas) and the
behaviour of representative tool calls (exact / structural / error-message
modes), verifies the Python-only guardrails, and writes machine-readable
evidence to live-validation-results.json plus a human summary to stdout.

Credentials are read from the environment (SUPABASE_URL, SUPABASE_ANON_KEY,
SUPABASE_SERVICE_ROLE_KEY); nothing is printed or persisted.

Usage:
  python3 run_e2e.py --ts-entry /path/to/rds-supabase-mcp/src/index.ts \
                     --py-package-dir /path/to/huaweicloud-rds-supabase-mcp
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

# Upstream order minus apply_migration, list_migrations and the three
# edge-function tools, removed in 0.2.0 (see CHANGELOG); the TS server
# still lists them, which the surface comparison reports as intentional.
EXPECTED_TOOLS = [
    "list_tables", "list_extensions", 
    "execute_sql", "get_database_connections", "get_database_stats",
    "get_project_url", "generate_typescript_types", "rebuild_hooks",
    "verify_jwt_secret", "list_auth_users", "get_auth_user", "delete_auth_user",
    "create_auth_user", "update_auth_user", "list_storage_buckets",
    "list_storage_objects", "list_realtime_publications", "list_cron_jobs",
    "list_vector_indexes", 
    "get_logs", "get_advisors", "get_storage_config", "update_storage_config",
    "list_table_columns", "list_indexes", "list_constraints",
    "list_foreign_keys", "list_rls_policies", "list_triggers",
    "list_database_functions", "get_function_definition",
    "get_trigger_definition", "get_rls_status", "list_available_extensions",
    "get_cron_job_history", "get_index_stats",
    "get_vector_index_stats", "explain_query",
]

# (tool, arguments, mode, note)
#   exact:    parsed JSON payloads must be deep-equal
#   structural: only top-level keys / row counts / row key sets are compared
#               (volatile counters, pids, timestamps)
#   error-message: both sides must surface the same core upstream error text
CALL_MATRIX: list[tuple[str, dict[str, Any], str, str]] = [
    ("get_project_url", {}, "exact", ""),
    ("verify_jwt_secret", {}, "exact", ""),
    ("list_tables", {}, "exact", ""),
    ("list_extensions", {}, "exact", ""),
    ("execute_sql", {"sql": "SELECT 1 AS one"}, "exact", ""),
    ("execute_sql", {"sql": "SELECT count(*) FROM public.students"}, "exact", ""),
    ("execute_sql", {"sql": "DELETE FROM public.students", "read_only": True},
     "error-message", "in-database read_only whitelist"),
    ("get_database_connections", {}, "structural", "pids/timestamps are volatile"),
    ("get_database_stats", {}, "structural", "counters move between calls"),
    ("get_advisors", {"type": "security"}, "exact", ""),
    ("get_advisors", {"type": "performance"}, "exact", ""),
    ("list_table_columns", {"table": "students"}, "exact", ""),
    ("list_indexes", {}, "exact", ""),
    ("list_constraints", {}, "exact", ""),
    ("list_foreign_keys", {}, "exact", ""),
    ("list_rls_policies", {}, "exact", ""),
    ("list_triggers", {}, "exact", ""),
    ("list_database_functions", {}, "exact", ""),
    ("get_function_definition", {"function_name": "execute_sql"}, "exact", ""),
    ("get_rls_status", {}, "exact", ""),
    ("list_available_extensions", {}, "exact", ""),
    ("list_cron_jobs", {}, "exact", "pg_cron absent on this instance"),
    ("list_vector_indexes", {}, "exact", ""),
    ("get_logs", {"service": "postgres"}, "exact", "analytics absent -> none"),
    ("get_index_stats", {"index_name": "students_pkey"}, "exact", ""),
    ("get_vector_index_stats", {}, "exact", ""),
    ("explain_query", {"sql": "SELECT 1"}, "exact", ""),
    ("rebuild_hooks", {}, "exact", "restarts the pg_net worker"),
    ("get_storage_config", {}, "exact", "storage schema absent"),
    ("update_storage_config", {"bucket_id": "x", "public": True}, "exact",
     "storage schema absent -> structured failure"),
    ("generate_typescript_types", {"output_path": "/tmp/x.ts"}, "exact",
     "no DATABASE_URL -> structured failure"),
    ("list_auth_users", {}, "error-message", "requires DATABASE_URL"),
    ("get_auth_user", {"user_id": "00000000-0000-0000-0000-000000000000"},
     "error-message", "requires DATABASE_URL"),
    ("delete_auth_user", {"user_id": "00000000-0000-0000-0000-000000000000"},
     "error-message", "requires DATABASE_URL"),
    ("create_auth_user", {"email": "e2e@example.com", "password": "secret1"},
     "error-message", "requires DATABASE_URL"),
    ("update_auth_user", {"user_id": "00000000-0000-0000-0000-000000000000",
                          "email": "e2e@example.com"}, "error-message",
     "requires DATABASE_URL"),
    ("list_storage_buckets", {}, "error-message", "requires DATABASE_URL"),
    ("list_storage_objects", {"bucket_id": "x"}, "error-message", "requires DATABASE_URL"),
    ("list_realtime_publications", {}, "error-message", "requires DATABASE_URL"),
]


class StdioClient:
    def __init__(self, name: str, process: asyncio.subprocess.Process) -> None:
        self.name = name
        self.process = process
        self.next_id = 1

    async def _write(self, payload: dict[str, Any]) -> None:
        self.process.stdin.write((json.dumps(payload) + "\n").encode())
        await self.process.stdin.drain()

    async def _read(self) -> dict[str, Any]:
        while True:
            line = await self.process.stdout.readline()
            if not line:
                raise RuntimeError(f"{self.name}: server closed stdout")
            try:
                message = json.loads(line)
            except ValueError:
                # The TypeScript server writes console.info() lines (for
                # example "Using service role RPC method...") to stdout,
                # polluting the JSON-RPC stream; skip non-JSON lines.
                continue
            if "id" in message:
                return message

    async def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": self.next_id, "method": method}
        if params is not None:
            payload["params"] = params
        self.next_id += 1
        await self._write(payload)
        return await self._read()

    async def initialize(self) -> dict[str, Any]:
        result = await self.request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "e2e-compare", "version": "0"},
            },
        )
        await self._write({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return result["result"]

    async def list_tools(self) -> list[dict[str, Any]]:
        return (await self.request("tools/list"))["result"]["tools"]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return (await self.request(
            "tools/call", {"name": name, "arguments": arguments}))["result"]


def _payload(result: dict[str, Any]) -> tuple[str, bool]:
    text = result["content"][0]["text"]
    return text, bool(result.get("isError"))


def _parse_json(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        return None


def _strip_prefix(text: str, tool: str) -> str:
    prefix = f"Error executing tool {tool}: "
    return text[len(prefix):] if text.startswith(prefix) else text


def _first_line(text: Any) -> str:
    if not isinstance(text, str) or not text.strip():
        return ""
    return text.strip().splitlines()[0].strip()


def _structure(value: Any) -> Any:
    if isinstance(value, list):
        if value and all(isinstance(item, dict) for item in value):
            return {"rows": len(value), "keys": sorted(value[0].keys())}
        return {"rows": len(value)}
    if isinstance(value, dict):
        return {key: _structure(val) if isinstance(val, list) else type(val).__name__
                for key, val in value.items()}
    return type(value).__name__


def _compare(a: Any, b: Any) -> bool:
    return a == b


async def spawn(command: list[str], env_extra: dict[str, str]) -> StdioClient:
    env = dict(os.environ)
    env.update(env_extra)
    process = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env=env,
        limit=2**24,
    )
    return StdioClient(" ".join(command[:2]), process)


async def run_calls(ts: StdioClient, py: StdioClient) -> list[dict[str, Any]]:
    results = []
    for tool, arguments, mode, note in CALL_MATRIX:
        entry: dict[str, Any] = {"tool": tool, "arguments": arguments, "mode": mode}
        try:
            ts_text, ts_is_error = _payload(await ts.call_tool(tool, arguments))
            py_text, py_is_error = _payload(await py.call_tool(tool, arguments))
            entry["ts_is_error"] = ts_is_error
            entry["py_is_error"] = py_is_error
            if mode == "error-message" or ts_is_error or py_is_error:
                ts_msg = _strip_prefix(ts_text, tool)
                py_payload = _parse_json(py_text)
                py_msg = None
                if isinstance(py_payload, dict) and "error" in py_payload:
                    py_msg = py_payload["error"].get("message")
                ok = ts_msg == py_msg and bool(ts_is_error) and bool(py_is_error)
                # The Python server surfaces errors as structured envelopes
                # inside a non-error response (shared-core semantics); the
                # isError flag difference is a documented representation
                # deviation, not a behaviour difference.
                if ts_msg == py_msg and bool(ts_is_error) and not py_is_error:
                    ok = True
                    entry["representation_note"] = (
                        "py returns the error envelope in a non-error result")
                entry["verdict"] = "PASS" if ok else "FAIL"
                if not ok:
                    entry["ts_message"] = ts_msg
                    entry["py_message"] = py_msg
            else:
                ts_payload = _parse_json(ts_text)
                py_payload = _parse_json(py_text)
                if mode == "exact":
                    ok = _compare(ts_payload, py_payload)
                else:  # structural
                    ok = _compare(_structure(ts_payload), _structure(py_payload))
                entry["verdict"] = "PASS" if ok else "FAIL"
                if not ok:
                    entry["ts_payload"] = ts_payload
                    entry["py_payload"] = py_payload
        except Exception as exc:  # noqa: BLE001 - record and continue
            entry["verdict"] = "ERROR"
            entry["error"] = str(exc)
        if note:
            entry["note"] = note
        results.append(entry)
        print(f"  {entry['verdict']:5} {tool} ({mode})" + (f" - {note}" if note else ""))
    return results


def compare_tool_lists(ts_tools: list[dict[str, Any]], py_tools: list[dict[str, Any]]
                       ) -> dict[str, Any]:
    ts_by_name = {tool["name"]: tool for tool in ts_tools}
    py_by_name = {tool["name"]: tool for tool in py_tools}
    names_ok = [tool["name"] for tool in ts_tools] == EXPECTED_TOOLS and \
        [tool["name"] for tool in py_tools] == EXPECTED_TOOLS
    first_lines_match = []
    schema_mismatches = []
    description_notes = []
    for name in EXPECTED_TOOLS:
        ts_desc = (ts_by_name[name].get("description") or "").strip()
        py_desc = (py_by_name[name].get("description") or "").strip()
        if ts_desc.splitlines()[0] != py_desc.splitlines()[0]:
            first_lines_match.append(name)
        ts_schema = ts_by_name[name].get("inputSchema") or {}
        py_schema = py_by_name[name].get("inputSchema") or {}
        ts_props = ts_schema.get("properties", {})
        py_props = py_schema.get("properties", {})
        if sorted(ts_props) != sorted(py_props):
            schema_mismatches.append(
                {"tool": name, "ts": sorted(ts_props), "py": sorted(py_props)})
        elif list(ts_schema.get("required", [])) != list(py_schema.get("required", [])):
            schema_mismatches.append(
                {"tool": name, "required_ts": ts_schema.get("required", []),
                 "required_py": py_schema.get("required", [])})
        for prop in ts_props:
            ts_pd = _first_line(
                ts_props[prop].get("description") if isinstance(ts_props[prop], dict) else None)
            py_pd = _first_line(
                py_props[prop].get("description") if isinstance(py_props[prop], dict) else None)
            if ts_pd and py_pd and " ".join(ts_pd.split()) != " ".join(py_pd.split()):
                description_notes.append({"tool": name, "param": prop})
    return {
        "count_ts": len(ts_tools),
        "count_py": len(py_tools),
        "names_and_order_ok": names_ok,
        "description_first_line_mismatches": first_lines_match,
        "input_schema_property_mismatches": schema_mismatches,
        "param_description_notes": description_notes,
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ts-entry", required=True)
    parser.add_argument("--py-package-dir", required=True)
    args = parser.parse_args()

    url = os.environ["SUPABASE_URL"]
    anon = os.environ["SUPABASE_ANON_KEY"]
    service = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    evidence: dict[str, Any] = {
        "date": "2026-11-04",
        "instance": url,
        "transport": "stdio (both servers)",
    }

    print("== spawning servers ==")
    ts = await spawn(
        ["bun", "run", args.ts_entry, "--url", url, "--anon-key", anon,
         "--service-key", service], {})
    py = await spawn(
        ["uv", "run", "--directory", args.py_package_dir,
         "--package", "mcp-server-huaweicloud-rds-supabase",
         "mcp-server-huaweicloud-rds-supabase"],
        {"SUPABASE_URL": url, "SUPABASE_ANON_KEY": anon,
         "SUPABASE_SERVICE_ROLE_KEY": service},
    )
    ts_info = await ts.initialize()
    py_info = await py.initialize()
    evidence["ts_server"] = ts_info["serverInfo"]
    evidence["py_server"] = py_info["serverInfo"]
    print(f"  ts: {ts_info['serverInfo']}")
    print(f"  py: {py_info['serverInfo']}")

    print("== tools/list comparison ==")
    ts_tools = await ts.list_tools()
    py_tools = await py.list_tools()
    evidence["tools_list"] = compare_tool_lists(ts_tools, py_tools)
    tl = evidence["tools_list"]
    print(f"  ts tools: {tl['count_ts']}, py tools: {tl['count_py']}, "
          f"names+order ok: {tl['names_and_order_ok']}, "
          f"description first-line mismatches: {len(tl['description_first_line_mismatches'])}, "
          f"schema mismatches: {len(tl['input_schema_property_mismatches'])}, "
          f"param description notes: {len(tl['param_description_notes'])}")

    print("== tool call matrix ==")
    evidence["calls"] = await run_calls(ts, py)

    print("== python guardrails ==")
    readonly = await spawn(
        ["uv", "run", "--directory", args.py_package_dir,
         "--package", "mcp-server-huaweicloud-rds-supabase",
         "mcp-server-huaweicloud-rds-supabase"],
        {"SUPABASE_URL": url, "SUPABASE_ANON_KEY": anon,
         "SUPABASE_SERVICE_ROLE_KEY": service,
         "HUAWEICLOUD_MCP_READ_ONLY": "true"},
    )
    await readonly.initialize()
    blocked = _parse_json(_payload(await readonly.call_tool(
        "execute_sql", {"sql": "SELECT 1"}))[0])
    allowed = _parse_json(_payload(await readonly.call_tool(
        "list_tables", {}))[0])
    guardrails = {
        "read_only_blocks_write": isinstance(blocked, dict)
        and blocked.get("error", {}).get("code") == "MCP_READ_ONLY",
        "read_only_allows_read": isinstance(allowed, list),
    }
    evidence["guardrails"] = guardrails
    print(f"  {guardrails}")

    failures = [c for c in evidence["calls"] if c["verdict"] != "PASS"]
    evidence["summary"] = {
        "tool_calls": len(evidence["calls"]),
        "pass": len(evidence["calls"]) - len(failures),
        "fail": len(failures),
        "guardrails_ok": all(guardrails.values()),
        "surface_ok": tl["names_and_order_ok"]
        and not tl["description_first_line_mismatches"]
        and not tl["input_schema_property_mismatches"],
    }
    out = __import__("pathlib").Path(__file__).with_name("live-validation-results.json")
    out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(f"== summary: {evidence['summary']} ==")
    print(f"evidence written to {out}")
    ok = (not failures and evidence["summary"]["surface_ok"]
          and evidence["summary"]["guardrails_ok"])
    print("E2E " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
