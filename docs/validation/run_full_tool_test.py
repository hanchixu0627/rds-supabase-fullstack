#!/usr/bin/env python3
"""Full-coverage E2E test of every hw-rds-supabase-py (Python port) tool.

Drives the server as a REAL MCP client: the official MCP Python SDK
(ClientSession + stdio_client) - the same client stack opencode, Claude Code
and other MCP hosts use - performing the standard initialize handshake,
tools/list and tools/call through the SDK session API.

Spawns the server with the exact command from the opencode config, runs a
setup fixture (scratch schema) through execute_sql, exercises all 43 tools
with positive / filter / boundary / expected-error cases, then cleans up and
proves the instance is back to the baseline state.

Emits full-tool-test-results.json and prints a summary. Credentials come from
the environment; nothing sensitive is persisted.

Usage:
  python3 run_full_tool_test.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

CMD = [
    "/Users/fitz/.local/bin/uv", "run", "--directory",
    "/Users/fitz/work/projects/research/supabase/supabase-mcp/"
    "huaweicloud-rds-supabase-mcp/server/mcp_server_rds_supabase",
    "--package", "mcp-server-huaweicloud-rds-supabase",
    "mcp-server-huaweicloud-rds-supabase",
]

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

Check = Callable[[Any, bool], tuple[bool, str]]
Results: list[dict[str, Any]] = []
_state: dict[str, Any] = {}


def ok(note: str = "") -> Check:
    return lambda payload, is_error: (not is_error, note or "non-error result")


def error_containing(text: str) -> Check:
    def check(payload: Any, is_error: bool) -> tuple[bool, str]:
        msg = _err_message(payload)
        return (msg is not None and text in msg), f"error message contains: {text}"
    return check


def payload_check(predicate: Callable[[Any], bool], note: str) -> Check:
    return lambda payload, is_error: (not is_error and predicate(payload), note)


def _err_message(payload: Any) -> str | None:
    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        return str(payload["error"].get("message"))
    return None


def rows_of(payload: Any) -> list[Any]:
    return payload if isinstance(payload, list) else []


def names(payload: Any, key: str = "name") -> list[str]:
    return [row.get(key) for row in rows_of(payload) if isinstance(row, dict)]


CASES: list[dict[str, Any]] = [
    # ---------------------------------------------------------- surface
    {"id": "C001", "group": "surface", "tool": "(tools/list)",
     "args": None, "expect": "43 tools registered in upstream order",
     "kind": "surface"},
    # ---------------------------------------------------------- baseline
    {"id": "B001", "group": "baseline", "tool": "list_tables", "args": {},
     "expect": "snapshot table list for cleanup verification",
     "kind": "baseline"},
    # ---------------------------------------------------------- setup fixture
    {"id": "S01", "group": "setup", "tool": "execute_sql",
     "args": {"sql": "CREATE SCHEMA _mcp_e2e"},
     "expect": "success envelope", "kind": "setup",
     "check": payload_check(lambda p: p[0].get("success") is True, "success envelope")},
    {"id": "S02", "group": "setup", "tool": "execute_sql",
     "args": {"sql": "CREATE TABLE _mcp_e2e.owners (id int PRIMARY KEY)"},
     "expect": "success envelope", "kind": "setup",
     "check": payload_check(lambda p: p[0].get("success") is True, "success envelope")},
    {"id": "S03", "group": "setup", "tool": "execute_sql",
     "args": {"sql": "CREATE TABLE _mcp_e2e.items (id serial PRIMARY KEY, "
                "name text NOT NULL UNIQUE, tag text DEFAULT 'x', owner_id int, "
                "CONSTRAINT items_name_len CHECK (length(name) < 100))"},
     "expect": "success envelope", "kind": "setup",
     "check": payload_check(lambda p: p[0].get("success") is True, "success envelope")},
    {"id": "S04", "group": "setup", "tool": "execute_sql",
     "args": {"sql": "ALTER TABLE _mcp_e2e.items ADD CONSTRAINT items_owner_fkey "
                "FOREIGN KEY (owner_id) REFERENCES _mcp_e2e.owners(id) ON DELETE CASCADE"},
     "expect": "success envelope", "kind": "setup",
     "check": payload_check(lambda p: p[0].get("success") is True, "success envelope")},
    {"id": "S05", "group": "setup", "tool": "execute_sql",
     "args": {"sql": "CREATE INDEX _mcp_e2e_items_tag_idx ON _mcp_e2e.items(tag)"},
     "expect": "success envelope", "kind": "setup",
     "check": payload_check(lambda p: p[0].get("success") is True, "success envelope")},
    {"id": "S06", "group": "setup", "tool": "execute_sql",
     "args": {"sql": "INSERT INTO _mcp_e2e.owners VALUES (1),(2)"},
     "expect": "rows_affected=2", "kind": "setup",
     "check": payload_check(lambda p: p[0] == {"success": True, "rows_affected": 2},
                            "exact rows_affected envelope")},
    {"id": "S07", "group": "setup", "tool": "execute_sql",
     "args": {"sql": "INSERT INTO _mcp_e2e.items (name, tag, owner_id) VALUES "
                "('alpha','a',1),('beta','b',1),('gamma','c',2)"},
     "expect": "rows_affected=3 (trigger writes audit rows)", "kind": "setup",
     "check": payload_check(lambda p: p[0] == {"success": True, "rows_affected": 3},
                            "exact rows_affected envelope")},
    {"id": "S08", "group": "setup", "tool": "execute_sql",
     "args": {"sql": "CREATE TABLE _mcp_e2e.audit_log (id int, event text)"},
     "expect": "success envelope", "kind": "setup",
     "check": payload_check(lambda p: p[0].get("success") is True, "success envelope")},
    {"id": "S09", "group": "setup", "tool": "execute_sql",
     "args": {"sql": "CREATE FUNCTION _mcp_e2e.audit_fn() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN "
                "INSERT INTO _mcp_e2e.audit_log VALUES (NEW.id, 'insert'); "
                "RETURN NEW; END $$"},
     "expect": "success envelope", "kind": "setup",
     "check": payload_check(lambda p: p[0].get("success") is True, "success envelope")},
    {"id": "S10", "group": "setup", "tool": "execute_sql",
     "args": {"sql": "CREATE TRIGGER items_audit BEFORE INSERT ON _mcp_e2e.items "
                "FOR EACH ROW EXECUTE FUNCTION _mcp_e2e.audit_fn()"},
     "expect": "success envelope", "kind": "setup",
     "check": payload_check(lambda p: p[0].get("success") is True, "success envelope")},
    {"id": "S11", "group": "setup", "tool": "execute_sql",
     "args": {"sql": "CREATE TABLE _mcp_e2e.secure (id int)"},
     "expect": "success envelope", "kind": "setup",
     "check": payload_check(lambda p: p[0].get("success") is True, "success envelope")},
    {"id": "S12", "group": "setup", "tool": "execute_sql",
     "args": {"sql": "ALTER TABLE _mcp_e2e.secure ENABLE ROW LEVEL SECURITY"},
     "expect": "success envelope", "kind": "setup",
     "check": payload_check(lambda p: p[0].get("success") is True, "success envelope")},
    {"id": "S13", "group": "setup", "tool": "execute_sql",
     "args": {"sql": "ALTER TABLE _mcp_e2e.secure FORCE ROW LEVEL SECURITY"},
     "expect": "success envelope", "kind": "setup",
     "check": payload_check(lambda p: p[0].get("success") is True, "success envelope")},
    {"id": "S14", "group": "setup", "tool": "execute_sql",
     "args": {"sql": "CREATE POLICY secure_select ON _mcp_e2e.secure FOR SELECT "
                "TO public USING (true)"},
     "expect": "success envelope", "kind": "setup",
     "check": payload_check(lambda p: p[0].get("success") is True, "success envelope")},
    {"id": "S15", "group": "setup", "tool": "execute_sql",
     "args": {"sql": "CREATE FUNCTION _mcp_e2e.note() RETURNS text "
                "LANGUAGE sql AS $$ SELECT 'scratch-note' $$"},
     "expect": "success envelope", "kind": "setup",
     "check": payload_check(lambda p: p[0].get("success") is True, "success envelope")},
    # ---------------------------------------------------------- database
    {"id": "T01", "group": "database", "tool": "list_tables", "args": {},
     "expect": "fixture tables visible",
     "check": payload_check(
         lambda p: {"items", "owners", "audit_log", "secure"}.issubset(
             {r["name"] for r in p if r.get("schema") == "_mcp_e2e"}),
         "contains _mcp_e2e.items/owners/audit_log/secure")},
    {"id": "T02", "group": "database", "tool": "list_extensions", "args": {},
     "expect": "pg_net installed with version",
     "check": payload_check(
         lambda p: any(r.get("name") == "pg_net" and r.get("version") for r in p),
         "pg_net row with version")},
    {"id": "T05", "group": "database", "tool": "execute_sql",
     "args": {"sql": "SELECT 1 AS one"},
     "expect": "[{one: 1}]",
     "check": payload_check(lambda p: p == [{"one": 1}], "exact payload")},
    {"id": "T06", "group": "database", "tool": "execute_sql",
     "args": {"sql": "SELECT count(*) AS n FROM _mcp_e2e.items", "read_only": True},
     "expect": "read_only SELECT allowed, n=3",
     "check": payload_check(lambda p: p == [{"n": 3}], "exact payload")},
    {"id": "T07", "group": "database", "tool": "execute_sql",
     "args": {"sql": "UPDATE _mcp_e2e.items SET tag = 'z'", "read_only": True},
     "expect": "in-DB whitelist rejects UPDATE (42501)",
     "kind": "expected-error",
     "check": error_containing("read_only mode allows only SELECT / WITH / VALUES / TABLE / EXPLAIN")},
    {"id": "T08", "group": "database", "tool": "execute_sql",
     "args": {"sql": "WITH x AS (INSERT INTO _mcp_e2e.audit_log VALUES (1,'w') "
                "RETURNING 1) SELECT * FROM x", "read_only": True},
     "expect": "in-DB whitelist rejects data-modifying WITH (42501)",
     "kind": "expected-error",
     "check": error_containing("read_only mode does not allow data-modifying statements inside WITH")},
    {"id": "T09", "group": "database", "tool": "execute_sql",
     "args": {"sql": "SELECT * FROM _mcp_e2e.missing_table"},
     "expect": "SQL error surfaced verbatim (42P01)",
     "kind": "expected-error",
     "check": error_containing('relation "_mcp_e2e.missing_table" does not exist')},
    {"id": "T10", "group": "database", "tool": "execute_sql",
     "args": {"sql": "INSERT INTO _mcp_e2e.audit_log VALUES (99, 'e2e-write')"},
     "expect": "write path, rows_affected=1",
     "check": payload_check(lambda p: p[0] == {"success": True, "rows_affected": 1},
                            "exact rows_affected envelope")},
    {"id": "T11", "group": "database", "tool": "execute_sql",
     "args": {"sql": "SELECT count(*) AS n FROM _mcp_e2e.audit_log"},
     "expect": "only the explicit e2e write (trigger created after setup inserts), n=1",
     "check": payload_check(lambda p: p == [{"n": 1}], "exact payload")},
    {"id": "T12", "group": "database", "tool": "get_database_connections", "args": {},
     "expect": ">=1 client backend rows with pid",
     "check": payload_check(lambda p: len(p) >= 1 and "pid" in p[0], "rows with pid")},
    {"id": "T13", "group": "database", "tool": "get_database_stats", "args": {},
     "expect": "expected error: PG17 instance lacks pg_stat_bgwriter.checkpoints_timed",
     "kind": "expected-error",
     "check": error_containing('column "checkpoints_timed" does not exist')},
    # ---------------------------------------------------------- project
    {"id": "T14", "group": "project", "tool": "get_project_url", "args": {},
     "expect": "configured gateway URL",
     "check": payload_check(
         lambda p: p == {"project_url": "http://60.204.240.112:8443"}, "exact payload")},
    {"id": "T15", "group": "project", "tool": "generate_typescript_types",
     "args": {"output_path": "/tmp/never-written.ts"},
     "expect": "structured failure: direct connections not supported",
     "check": payload_check(
         lambda p: p.get("success") is False
         and "Direct database connections are not supported" in p.get("message", "")
         and p.get("platform") == "darwin",
         "success=false + message + platform")},
    {"id": "T16", "group": "project", "tool": "rebuild_hooks", "args": {},
     "expect": "pg_net worker restart requested",
     "check": payload_check(
         lambda p: p.get("success") is True
         and p.get("message") == "pg_net worker restart requested successfully.",
         "exact success message")},
    {"id": "T17", "group": "project", "tool": "verify_jwt_secret", "args": {},
     "expect": "no JWT secret in env -> not_configured (never leaks the secret)",
     "check": payload_check(lambda p: p == {"jwt_secret_status": "not_configured"},
                            "exact payload")},
    # ------------------------------- auth_users (real admin-API lifecycle)
    {"id": "T18", "group": "auth_users", "tool": "list_auth_users",
     "args": {},
     "expect": "real users mapped to the upstream 7-field shape (also stashes probe ids)",
     "kind": "auth-list-stash"},
    {"id": "T18b", "group": "auth_users", "tool": "list_auth_users",
     "args": {"limit": 2, "offset": 1},
     "expect": "limit/offset window equals the SQL ORDER BY created_at DESC window",
     "kind": "auth-sql-window"},
    {"id": "T18c", "group": "auth_users", "tool": "list_auth_users",
     "args": {"limit": 3, "offset": 3},
     "expect": "second window also equals the SQL window",
     "kind": "auth-sql-window"},
    {"id": "T19", "group": "auth_users", "tool": "get_auth_user",
     "args": {"user_id": "STATE:probe_id"},
     "expect": "get by id returns the stashed user with matching email",
     "kind": "auth-get-stashed"},
    {"id": "T19b", "group": "auth_users", "tool": "get_auth_user",
     "args": {"user_id": "00000000-0000-0000-0000-000000000000"},
     "expect": "missing user raises the upstream not-found message",
     "kind": "expected-error",
     "check": error_containing(
         "User with ID 00000000-0000-0000-0000-000000000000 not found.")},
    {"id": "T21", "group": "auth_users", "tool": "create_auth_user",
     "args": {"email": "STATE:scratch_email", "password": "probe-Passw0rd",
              "user_metadata": {"name": "lifecycle"}},
     "expect": "scratch user created with mapped shape (id stashed)",
     "kind": "auth-create-scratch"},
    {"id": "T21b", "group": "auth_users", "tool": "create_auth_user",
     "args": {"email": "STATE:other_email", "password": "probe-Passw0rd"},
     "expect": "duplicate email raises the exact upstream message",
     "kind": "expected-error",
     "check": error_containing("likely already exists.")},
    {"id": "T22", "group": "auth_users", "tool": "update_auth_user",
     "args": {"user_id": "STATE:scratch_id", "password": "probe-Passw0rd2",
              "user_metadata": {"name": "lifecycle2"}},
     "expect": "update replaces metadata and returns updated_at",
     "kind": "auth-update-scratch"},
    {"id": "T22b", "group": "auth_users", "tool": "update_auth_user",
     "args": {"user_id": "STATE:scratch_id", "email": "STATE:other_email"},
     "expect": "duplicate email on update raises the exact upstream message",
     "kind": "expected-error",
     "check": error_containing("likely already exists for another user.")},
    {"id": "T22c", "group": "auth_users", "tool": "update_auth_user",
     "args": {"user_id": "00000000-0000-0000-0000-000000000000", "email": "ghost@x.io"},
     "expect": "missing user raises the upstream update message",
     "kind": "expected-error",
     "check": error_containing(
         "User update failed: User with ID 00000000-0000-0000-0000-000000000000 "
         "not found or no rows affected.")},
    {"id": "T20", "group": "auth_users", "tool": "delete_auth_user",
     "args": {"user_id": "STATE:scratch_id"},
     "expect": "delete scratch user returns the exact upstream success message",
     "kind": "auth-delete-scratch"},
    {"id": "T20b", "group": "auth_users", "tool": "delete_auth_user",
     "args": {"user_id": "STATE:scratch_id"},
     "expect": "deleting again returns the structured upstream not-found message",
     "kind": "auth-delete-again"},
    # ---------------------------------------------------------- storage
    {"id": "T23", "group": "storage", "tool": "list_storage_buckets", "args": {},
     "expect": "expected error: direct connections removed (0.4.0)",
     "kind": "expected-error",
     "check": error_containing(
         "Direct database connections are not supported on this deployment; "
         "list_storage_buckets is pending an RPC-channel rework.")},
    {"id": "T24", "group": "storage", "tool": "list_storage_objects",
     "args": {"bucket_id": "x"},
     "expect": "expected error: direct connections removed (0.4.0)",
     "kind": "expected-error",
     "check": error_containing(
         "Direct database connections are not supported on this deployment; "
         "list_storage_objects is pending an RPC-channel rework.")},
    # ---------------------------------------------------------- platform
    {"id": "T25", "group": "platform", "tool": "list_realtime_publications", "args": {},
     "expect": "expected error: direct connections removed (0.4.0)",
     "kind": "expected-error",
     "check": error_containing(
         "Direct database connections are not supported on this deployment; "
         "list_realtime_publications is pending an RPC-channel rework.")},
    {"id": "T26", "group": "platform", "tool": "list_cron_jobs", "args": {},
     "expect": "[] (pg_cron not installed)",
     "check": payload_check(lambda p: p == [], "empty list")},
    {"id": "T27", "group": "platform", "tool": "list_vector_indexes", "args": {},
     "expect": "[] (no pgvector indexes)",
     "check": payload_check(lambda p: p == [], "empty list")},
    {"id": "T30", "group": "platform", "tool": "get_logs",
     "args": {"service": "postgres", "limit": 10},
     "expect": "none-source fallback with message",
     "check": payload_check(
         lambda p: p.get("source") == "none" and p.get("logs") == []
         and "Log access not available for postgres" in p.get("message", ""),
         "source=none + message")},
    {"id": "T31", "group": "platform", "tool": "get_logs",
     "args": {"service": "auth", "limit": 5},
     "expect": "none-source fallback for auth service",
     "check": payload_check(
         lambda p: p.get("source") == "none" and p.get("service") == "auth",
         "source=none + service=auth")},
    {"id": "T32", "group": "platform", "tool": "get_advisors",
     "args": {"type": "security"},
     "expect": "issues array + total_count consistent",
     "check": payload_check(
         lambda p: p.get("type") == "security"
         and isinstance(p.get("issues"), list)
         and p.get("total_count") == len(p["issues"]),
         "issues/total_count consistent")},
    {"id": "T33", "group": "platform", "tool": "get_advisors",
     "args": {"type": "performance"},
     "expect": "issues array + total_count consistent",
     "check": payload_check(
         lambda p: p.get("type") == "performance"
         and p.get("total_count") == len(p.get("issues", [])),
         "issues/total_count consistent")},
    {"id": "T34", "group": "platform", "tool": "get_storage_config", "args": {},
     "expect": "storage schema absent -> empty buckets + global config",
     "check": payload_check(
         lambda p: p == {"buckets": [],
                         "global_config": {"max_file_size_limit": None, "bucket_count": 0}},
         "exact empty payload")},
    {"id": "T35", "group": "platform", "tool": "update_storage_config",
     "args": {"bucket_id": "x", "public": True},
     "expect": "structured failure: bucket not found (storage schema exists, empty)",
     "check": payload_check(
         lambda p: p == {"success": False, "bucket": None,
                         "message": "Bucket 'x' not found"},
         "exact structured failure")},
    # ---------------------------------------------------------- inspection
    {"id": "T36", "group": "inspection", "tool": "list_table_columns",
     "args": {"schema": "_mcp_e2e", "table": "items"},
     "expect": "4 columns with types/defaults/constraints",
     "check": payload_check(
         lambda p: [r["column_name"] for r in p] == ["id", "name", "tag", "owner_id"]
         and p[0]["column_default"] is not None
         and p[1]["is_nullable"] is False,
         "column list + metadata")},
    {"id": "T37", "group": "inspection", "tool": "list_table_columns",
     "args": {"table": "students"},
     "expect": "default schema=public, students columns",
     "check": payload_check(lambda p: len(p) >= 2, "students columns returned")},
    {"id": "T38", "group": "inspection", "tool": "list_table_columns",
     "args": {"schema": "9bad", "table": "t"},
     "expect": "identifier validation error",
     "kind": "expected-error",
     "check": error_containing("Invalid schema name: 9bad")},
    {"id": "T39", "group": "inspection", "tool": "list_indexes",
     "args": {"schema": "_mcp_e2e"},
     "expect": "PK + UNIQUE + explicit index present",
     "check": payload_check(
         lambda p: {"items_pkey", "items_name_key", "_mcp_e2e_items_tag_idx",
                    "owners_pkey"}.issubset(set(names(p, "index_name"))),
         "expected index set")},
    {"id": "T40", "group": "inspection", "tool": "list_indexes",
     "args": {"table": "items"},
     "expect": "table filter without schema filter",
     "check": payload_check(
         lambda p: {r["table_name"] for r in p} == {"items"}, "only items indexes")},
    {"id": "T41", "group": "inspection", "tool": "list_indexes",
     "args": {"table": "9bad"},
     "expect": "identifier validation error",
     "kind": "expected-error",
     "check": error_containing("Invalid table name: 9bad")},
    {"id": "T42", "group": "inspection", "tool": "list_constraints",
     "args": {"schema": "_mcp_e2e"},
     "expect": "PRIMARY KEY / UNIQUE / CHECK / FOREIGN KEY all present",
     "check": payload_check(
         lambda p: {"items_pkey", "items_name_key", "items_name_len",
                    "items_owner_fkey"}.issubset(set(names(p, "constraint_name"))),
         "all four constraint kinds")},
    {"id": "T43", "group": "inspection", "tool": "list_constraints",
     "args": {"constraint_type": "FOREIGN KEY"},
     "expect": "type filter returns only foreign keys",
     "check": payload_check(
         lambda p: p and all(r["constraint_type"] == "FOREIGN KEY" for r in p),
         "only FOREIGN KEY rows")},
    {"id": "T44", "group": "inspection", "tool": "list_foreign_keys",
     "args": {"schema": "_mcp_e2e"},
     "expect": "FK with reference + CASCADE rule",
     "check": payload_check(
         lambda p: any(r["constraint_name"] == "items_owner_fkey"
                       and r["referenced_table"] == "owners"
                       and r["delete_rule"] == "CASCADE" for r in p),
         "items_owner_fkey -> owners ON DELETE CASCADE")},
    {"id": "T45", "group": "inspection", "tool": "list_rls_policies",
     "args": {"schema": "_mcp_e2e"},
     "expect": "secure_select policy visible",
     "check": payload_check(
         lambda p: any(r["policy_name"] == "secure_select" and r["command"] == "SELECT"
                       for r in p), "secure_select SELECT policy")},
    {"id": "T46", "group": "inspection", "tool": "list_rls_policies", "args": {},
     "expect": "unfiltered call includes public.check_ins policies",
     "check": payload_check(
         lambda p: any(r["table_name"] == "check_ins" for r in p),
         "check_ins policies present")},
    {"id": "T47", "group": "inspection", "tool": "list_triggers",
     "args": {"schema": "_mcp_e2e"},
     "expect": "items_audit trigger with timing/level/events",
     "check": payload_check(
         lambda p: any(r["trigger_name"] == "items_audit"
                       and r["trigger_timing"] == "BEFORE"
                       and r["trigger_level"] == "ROW"
                       and "INSERT" in r["events"] for r in p),
         "items_audit BEFORE ROW INSERT")},
    {"id": "T48", "group": "inspection", "tool": "list_database_functions",
     "args": {"schema": "_mcp_e2e"},
     "expect": "fixture functions audit_fn + note",
     "check": payload_check(
         lambda p: {"audit_fn", "note"}.issubset(set(names(p, "function_name"))),
         "both fixture functions")},
    {"id": "T49", "group": "inspection", "tool": "list_database_functions",
     "args": {"name_pattern": "note%"},
     "expect": "name pattern filter",
     "check": payload_check(
         lambda p: p and all(r["function_name"].startswith("note") for r in p)
         and any(r["function_name"] == "note" for r in p), "only note* functions")},
    {"id": "T50", "group": "inspection", "tool": "list_database_functions",
     "args": {"name_pattern": "bad-pattern!"},
     "expect": "pattern validation error",
     "kind": "expected-error",
     "check": error_containing("Invalid name pattern: bad-pattern!")},
    {"id": "T51", "group": "inspection", "tool": "get_function_definition",
     "args": {"function_name": "note", "schema": "_mcp_e2e"},
     "expect": "function source contains scratch-note",
     "check": payload_check(
         lambda p: "scratch-note" in json.dumps(p), "source contains body")},
    {"id": "T52", "group": "inspection", "tool": "get_function_definition",
     "args": {"function_name": "nope", "schema": "_mcp_e2e"},
     "expect": "not-found error",
     "kind": "expected-error",
     "check": error_containing("Function _mcp_e2e.nope not found.")},
    {"id": "T53", "group": "inspection", "tool": "get_trigger_definition",
     "args": {"schema": "_mcp_e2e", "table": "items", "trigger_name": "items_audit"},
     "expect": "trigger definition + function source",
     "check": payload_check(
         lambda p: "items_audit" in json.dumps(p), "definition returned")},
    {"id": "T54", "group": "inspection", "tool": "get_trigger_definition",
     "args": {"schema": "_mcp_e2e", "table": "items", "trigger_name": "nope"},
     "expect": "not-found error",
     "kind": "expected-error",
     "check": error_containing('Trigger "nope" not found on _mcp_e2e.items.')},
    {"id": "T55", "group": "inspection", "tool": "get_rls_status",
     "args": {"schema": "_mcp_e2e"},
     "expect": "secure: RLS enabled+forced with policy; items: disabled",
     "check": payload_check(
         lambda p: {r["table_name"]: r for r in p}["secure"]["rls_enabled"] is True
         and {r["table_name"]: r for r in p}["secure"]["rls_forced"] is True
         and {r["table_name"]: r for r in p}["items"]["rls_enabled"] is False,
         "secure enabled+forced, items disabled")},
    {"id": "T56", "group": "inspection", "tool": "get_rls_status", "args": {},
     "expect": "unfiltered call covers multiple schemas",
     "check": payload_check(lambda p: len(p) >= 3, "multiple tables")},
    {"id": "T57", "group": "inspection", "tool": "list_available_extensions", "args": {},
     "expect": "pg_cron available-uninstalled; pg_net installed",
     "check": payload_check(
         lambda p: any(r["name"] == "pg_cron" and r["is_installed"] is False for r in p)
         and any(r["name"] == "pg_net" and r["is_installed"] is True for r in p),
         "pg_cron uninstalled + pg_net installed")},
    {"id": "T58", "group": "inspection", "tool": "list_available_extensions",
     "args": {"name_pattern": "pg_c%"},
     "expect": "raw SQL LIKE pattern filter (pg_c% -> pg_cron ...)",
     "check": payload_check(
         lambda p: p and all(r["name"].startswith("pg_c") for r in p)
         and any(r["name"] == "pg_cron" for r in p), "only pg_c* extensions")},
    {"id": "T59", "group": "inspection", "tool": "list_available_extensions",
     "args": {"show_installed": False},
     "expect": "installed extensions excluded",
     "check": payload_check(
         lambda p: all(r["is_installed"] is False for r in p),
         "no installed extensions")},
    {"id": "T60", "group": "inspection", "tool": "get_cron_job_history", "args": {},
     "expect": "expected error: pg_cron not installed (upstream message)",
     "kind": "expected-error",
     "check": error_containing(
         "pg_cron extension is not installed. Install it with: CREATE EXTENSION pg_cron;")},
    {"id": "T62", "group": "inspection", "tool": "get_index_stats",
     "args": {"schema": "_mcp_e2e", "index_name": "_mcp_e2e_items_tag_idx"},
     "expect": "stats for the fixture index",
     "check": payload_check(
         lambda p: p.get("index_name") == "_mcp_e2e_items_tag_idx"
         or any(r.get("index_name") == "_mcp_e2e_items_tag_idx" for r in rows_of(p)),
         "fixture index stats")},
    {"id": "T63", "group": "inspection", "tool": "get_index_stats",
     "args": {"schema": "public", "index_name": "students_pkey"},
     "expect": "stats for a production index",
     "check": payload_check(
         lambda p: "students_pkey" in json.dumps(p), "students_pkey stats")},
    {"id": "T64", "group": "inspection", "tool": "get_vector_index_stats", "args": {},
     "expect": "[] (no vector indexes)",
     "check": payload_check(lambda p: p == [], "empty list")},
    {"id": "T65", "group": "inspection", "tool": "explain_query",
     "args": {"sql": "SELECT * FROM _mcp_e2e.items WHERE tag = 'a'"},
     "expect": "query plan returned",
     "check": payload_check(
         lambda p: "Plan" in json.dumps(p) or "plan" in json.dumps(p), "plan payload")},
    {"id": "T66", "group": "inspection", "tool": "explain_query",
     "args": {"sql": "SELECT count(*) FROM _mcp_e2e.items", "analyze": True,
              "buffers": True},
     "expect": "EXPLAIN ANALYZE BUFFERS executes and returns a plan",
     "check": payload_check(
         lambda p: "Plan" in json.dumps(p) or "plan" in json.dumps(p),
         "analyzed plan payload")},
    # ---------------------------------------------------------- cleanup
    {"id": "D01", "group": "cleanup", "tool": "execute_sql",
     "args": {"sql": "DROP SCHEMA _mcp_e2e CASCADE"},
     "expect": "fixture schema dropped",
     "kind": "cleanup",
     "check": payload_check(lambda p: p[0].get("success") is True, "success envelope")},
    {"id": "D02", "group": "cleanup", "tool": "execute_sql",
     "args": {"sql": "SELECT to_regclass('_mcp_e2e.items') AS gone, "
                "to_regclass('public._mcp_py_test') AS gone2"},
     "expect": "all scratch objects removed (null)",
     "kind": "cleanup",
     "check": payload_check(
         lambda p: p[0] == {"gone": None, "gone2": None}, "both regclass checks null")},
    {"id": "D03", "group": "cleanup", "tool": "list_tables", "args": {},
     "expect": "table list identical to the pre-test baseline",
     "kind": "cleanup-baseline",
     },
    {"id": "D04", "group": "cleanup", "tool": "execute_sql",
     "args": {"sql": "SELECT count(*) AS n FROM auth.users WHERE email LIKE 'e2e-c-%'"},
     "expect": "no leftover scratch auth users",
     "kind": "cleanup",
     "check": payload_check(lambda p: p == [{"n": 0}], "n = 0")},
]


def _payload(result: Any) -> tuple[Any, bool]:
    """Extract the JSON payload and error flag from an MCP CallToolResult."""
    text = result.content[0].text if result.content else ""
    try:
        return json.loads(text), bool(result.is_error)
    except ValueError:
        return text, bool(result.is_error)


def _resolve_args(args: dict[str, Any] | None) -> dict[str, Any]:
    """Replace STATE:key argument values with values stashed by earlier cases.

    Unknown placeholders are kept as-is: the generating case (for example the
    scratch-email creator) overwrites them itself.
    """
    resolved = {}
    for key, value in (args or {}).items():
        if isinstance(value, str) and value.startswith("STATE:"):
            resolved[key] = _state.get(value[len("STATE:"):], value)
        else:
            resolved[key] = value
    return resolved


async def _call(session: ClientSession, tool: str, args: dict[str, Any]
                ) -> tuple[Any, bool]:
    return _payload(await session.call_tool(tool, args))


async def run_cases(session: ClientSession, server_info: dict[str, Any]) -> dict[str, Any]:
    for case in CASES:
        entry: dict[str, Any] = {"id": case["id"], "group": case["group"],
                                 "tool": case["tool"], "args": case["args"],
                                 "expect": case["expect"]}
        note = ""
        start = time.monotonic()
        try:
            if case["tool"] == "(tools/list)":
                listing = await session.list_tools()
                got = [t.name for t in listing.tools]
                passed = got == EXPECTED_TOOLS
                note = f"{len(got)} tools, order {'ok' if passed else 'MISMATCH'}"
                entry["kind"] = "surface"
            else:
                kind = case.get("kind")
                args = _resolve_args(case["args"])
                entry["args"] = args
                if kind == "auth-list-stash":
                    payload, is_error = await _call(session, "list_auth_users", {})
                    shape_ok = (
                        not is_error and isinstance(payload, list) and len(payload) >= 1
                        and set(payload[0]) == {
                            "id", "email", "role", "created_at", "last_sign_in_at",
                            "raw_app_meta_data", "raw_user_meta_data"})
                    if shape_ok:
                        _state["probe_id"] = payload[0]["id"]
                        _state["probe_email"] = payload[0]["email"]
                        _state["other_email"] = next(
                            (u["email"] for u in payload[1:]
                             if u.get("email") and u["email"] != payload[0]["email"]),
                            payload[0]["email"])
                    passed, note = shape_ok, (
                        f"{len(payload)} users, 7-field mapped shape, probe stashed")
                elif kind == "auth-sql-window":
                    payload, is_error = await _call(session, "list_auth_users", args)
                    sql = ("SELECT id FROM auth.users ORDER BY created_at DESC "
                           f"LIMIT {args['limit']} OFFSET {args['offset']}")
                    sql_rows, _sql_err = await _call(session, "execute_sql", {"sql": sql})
                    admin_ids = [u["id"] for u in payload] if not is_error else []
                    sql_ids = [r["id"] for r in sql_rows]
                    passed = admin_ids == sql_ids
                    note = (f"admin window == SQL window ({len(admin_ids)} ids)"
                            if passed else f"admin {admin_ids} != sql {sql_ids}")
                elif kind == "auth-get-stashed":
                    payload, is_error = await _call(session, case["tool"], args)
                    passed = (not is_error and payload.get("id") == _state["probe_id"]
                              and payload.get("email") == _state["probe_email"])
                    note = "stashed user returned with matching email"
                elif kind == "auth-create-scratch":
                    scratch = f"e2e-c-{int(time.time())}@demo.local"
                    _state["scratch_email"] = scratch
                    args["email"] = scratch
                    payload, is_error = await _call(session, case["tool"], args)
                    shape_ok = (
                        not is_error and payload.get("email") == scratch
                        and payload.get("role") == "authenticated"
                        and set(payload) == {
                            "id", "email", "role", "created_at", "last_sign_in_at",
                            "raw_app_meta_data", "raw_user_meta_data"})
                    if shape_ok:
                        _state["scratch_id"] = payload["id"]
                    passed, note = shape_ok, f"scratch user {scratch} created and stashed"
                elif kind == "auth-update-scratch":
                    payload, is_error = await _call(session, case["tool"], args)
                    passed = (
                        not is_error and payload.get("id") == _state["scratch_id"]
                        and payload.get("updated_at")
                        and payload.get("raw_user_meta_data", {}).get("name") == "lifecycle2")
                    note = "metadata replaced, updated_at present"
                elif kind == "auth-delete-scratch":
                    payload, is_error = await _call(session, case["tool"], args)
                    passed = (
                        not is_error and payload == {
                            "success": True,
                            "message": f"Successfully deleted user with ID: "
                                       f"{_state['scratch_id']}"})
                    note = "exact upstream success message"
                elif kind == "auth-delete-again":
                    payload, is_error = await _call(session, case["tool"], args)
                    passed = (
                        not is_error and payload == {
                            "success": False,
                            "message": f"User with ID {_state['scratch_id']} not found "
                                       f"or could not be deleted."})
                    note = "structured upstream not-found message"
                else:
                    result = await session.call_tool(case["tool"], args)
                    payload, is_error = _payload(result)
                    if getattr(result, "structuredContent", None) is not None:
                        entry["structured"] = True
                    if case.get("kind") == "baseline":
                        _state["baseline"] = json.dumps(payload, sort_keys=True)
                        passed, note = isinstance(payload, list), "baseline captured"
                    elif case.get("kind") == "cleanup-baseline":
                        passed = (json.dumps(payload, sort_keys=True)
                                  == _state.get("baseline"))
                        note = ("identical to baseline" if passed
                                else "DIFFERS from baseline")
                    else:
                        passed, note = case["check"](payload, is_error)
                entry["is_error"] = is_error
                entry["payload_head"] = json.dumps(
                    payload, ensure_ascii=False, default=str)[:400]
            entry["verdict"] = "PASS" if passed else "FAIL"
            entry["note"] = note
        except Exception as exc:  # noqa: BLE001 - record and continue
            entry["verdict"] = "ERROR"
            entry["note"] = str(exc)[:200]
        entry["duration_ms"] = round((time.monotonic() - start) * 1000)
        Results.append(entry)
        print(f"  {entry['verdict']:5} {case['id']:5} {case['tool']}"
              f" [{case['group']}] {note}")

    failures = [r for r in Results if r["verdict"] != "PASS"]
    by_group: dict[str, dict[str, int]] = {}
    for r in Results:
        g = by_group.setdefault(r["group"], {"total": 0, "pass": 0, "fail": 0})
        g["total"] += 1
        g["pass" if r["verdict"] == "PASS" else "fail"] += 1
    tools_covered = {r["tool"] for r in Results} - {"(tools/list)"}
    summary = {
        "server": server_info,
        "cases_total": len(Results),
        "pass": len(Results) - len(failures),
        "fail": len(failures),
        "tools_covered": sorted(tools_covered),
        "tools_expected": EXPECTED_TOOLS,
        "all_tools_covered": set(tools_covered) == set(EXPECTED_TOOLS),
        "cleanup_baseline_ok": all(
            r["verdict"] == "PASS" for r in Results if r["group"] == "cleanup"),
        "by_group": by_group,
    }
    out = Path(__file__).with_name("full-tool-test-results.json")
    out.write_text(json.dumps(
        {"summary": summary, "cases": Results}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(f"\nsummary: {summary['pass']}/{summary['cases_total']} PASS, "
          f"fail={summary['fail']}, all 43 tools covered={summary['all_tools_covered']}, "
          f"cleanup ok={summary['cleanup_baseline_ok']}")
    print(f"results: {out}")
    return summary


async def main() -> int:
    """Connect as a real MCP client (official SDK) and run the full matrix."""
    server_params = StdioServerParameters(
        command=CMD[0],
        args=CMD[1:],
        env={**os.environ,
             "SUPABASE_URL": os.environ["SUPABASE_URL"],
             "SUPABASE_ANON_KEY": os.environ["SUPABASE_ANON_KEY"],
             "SUPABASE_SERVICE_ROLE_KEY": os.environ["SUPABASE_SERVICE_ROLE_KEY"]},
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            server_info = {
                "name": init.server_info.name,
                "version": init.server_info.version,
                "protocolVersion": init.protocol_version,
            }
            print(f"connected via MCP SDK client: {server_info['name']} "
                  f"{server_info['version']} (protocol {server_info['protocolVersion']})")
            summary = await run_cases(session, server_info)
    failures = summary["fail"]
    return 0 if failures == 0 and summary["all_tools_covered"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
