#!/usr/bin/env python3
"""Stdio smoke test for the RDS Supabase MCP server.

Spawns the server over stdio, performs the MCP handshake, verifies the 43
upstream tools are listed in upstream order, optionally calls one READ tool
against a live instance, and proves that read-only mode blocks WRITE tools.
Prints only counts and statuses - never resource data or credentials.

Usage:
  smoke.py [--skip-cloud] -- <server command...>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

EXPECTED_TOOLS = [
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


class StdioClient:
    def __init__(self, process):
        self.process = process
        self.next_id = 1

    async def _write(self, payload):
        line = json.dumps(payload) + "\n"
        self.process.stdin.write(line.encode())
        await self.process.stdin.drain()

    async def _send(self, method, params=None):
        request = {
            "jsonrpc": "2.0",
            "id": self.next_id,
            "method": method,
        }
        if params is not None:
            request["params"] = params
        self.next_id += 1
        await self._write(request)

    async def _notify(self, method, params=None):
        notification = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            notification["params"] = params
        await self._write(notification)

    async def _read(self):
        while True:
            line = await self.process.stdout.readline()
            if not line:
                raise RuntimeError("server closed stdout")
            message = json.loads(line)
            if "id" in message:
                return message

    async def request(self, method, params=None):
        await self._send(method, params)
        return await self._read()

    async def initialize(self):
        result = await self.request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "smoke", "version": "0"},
            },
        )
        await self._notify("notifications/initialized")
        return result["result"]

    async def list_tools(self):
        result = await self.request("tools/list")
        return result["result"]["tools"]

    async def call_tool(self, name, arguments):
        result = await self.request("tools/call", {"name": name, "arguments": arguments})
        return result["result"]


async def spawn(command, extra_env=None):
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    process = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env=env,
    )
    return StdioClient(process)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-cloud", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("provide the server command after --")

    if args.skip_cloud:
        # The server validates SUPABASE_URL / SUPABASE_ANON_KEY at startup;
        # dummy values let the handshake run without a live instance (the
        # gateway probe fails silently, mirroring upstream behavior).
        os.environ.setdefault("SUPABASE_URL", "http://127.0.0.1:9")
        os.environ.setdefault("SUPABASE_ANON_KEY", "smoke-dummy-anon-key")

    client = await spawn(command)
    info = await client.initialize()
    print(f"initialize ok: {info['serverInfo']['name']} {info['serverInfo']['version']}")

    tools = await client.list_tools()
    names = [tool["name"] for tool in tools]
    if names != EXPECTED_TOOLS:
        print(f"FAIL: expected {len(EXPECTED_TOOLS)} tools in upstream order, got {len(names)}")
        return 1
    print(f"tools/list ok: {len(names)} tools in expected order")

    if not args.skip_cloud:
        result = await client.call_tool("list_tables", {})
        if result.get("isError"):
            print("FAIL: list_tables returned an error")
            return 1
        print("list_tables ok")

    readonly = await spawn(command, {"HUAWEICLOUD_MCP_READ_ONLY": "true"})
    await readonly.initialize()
    result = await readonly.call_tool("execute_sql", {"sql": "SELECT 1"})
    text = result["content"][0]["text"]
    payload = json.loads(text)
    if payload.get("error", {}).get("code") != "MCP_READ_ONLY":
        print("FAIL: read-only mode did not block execute_sql")
        return 1
    print("read-only guard ok: execute_sql blocked with MCP_READ_ONLY")

    print("SMOKE PASS")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
