# Huawei Cloud RDS Supabase MCP Server

[中文说明](README_zh.md)

Management MCP server for Huawei Cloud RDS Supabase — a cloud-managed,
self-hosted Supabase deployment where the database is an RDS PostgreSQL
instance reachable through the Kong gateway (PostgREST RPC), with optional
direct database access for privileged operations.

## Version

Current version: 0.4.0; Python 3.10+; MCP Python SDK 2.x; transports: stdio and
Streamable HTTP; license: Apache-2.0 (see repository NOTICE for the MIT
derivation chain of the upstream TypeScript project).

## Overview

This server is a Python re-implementation of the TypeScript `rds-supabase-mcp`
tool surface (38 of the 43 upstream tools; five tools that can never work in
this cloud deployment were removed in 0.2.0, see CHANGELOG) on the shared
`huaweicloud_mcp_core` runtime: three-layer architecture (tools → service →
client), three-tier risk guardrails (READ / WRITE / DANGEROUS lanes, read-only
mode, protection lists, structured audit), and a hardened in-database
`execute_sql` RPC function. All tool names, parameters, defaults, return
shapes and error messages are kept identical to the upstream TypeScript
server; the adaptation adds the platform guardrail layer on top.

## Quick start

```bash
# Read-only mode against a running instance
HUAWEICLOUD_MCP_READ_ONLY=true \
SUPABASE_URL=https://your-instance \
SUPABASE_ANON_KEY=<anon-key> \
SUPABASE_SERVICE_ROLE_KEY=<service-key> \
uvx --from git+https://github.com/huaweicloud/rds-supabase-fullstack \
  --subdirectory server/mcp_server_rds_supabase \
  mcp-server-huaweicloud-rds-supabase
```

Standard stdio client configuration:

```json
{
  "mcpServers": {
    "rds-supabase": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/huaweicloud/rds-supabase-fullstack",
        "--subdirectory", "server/mcp_server_rds_supabase",
        "mcp-server-huaweicloud-rds-supabase"
      ],
      "env": {
        "SUPABASE_URL": "https://your-instance",
        "SUPABASE_ANON_KEY": "<anon-key>",
        "SUPABASE_SERVICE_ROLE_KEY": "<service-key>"
      }
    }
  }
}
```

## Category

Database / self-hosted Supabase on managed PostgreSQL / operations automation.

## Features

- 38 tools with identical names, parameters, defaults, return shapes and
  error messages — verified tool-by-tool against the TypeScript server
  (the five removed tools are documented in CHANGELOG 0.2.0).
- SQL execution over the Kong gateway via the hardened `execute_sql` RPC
  (service-role key) with an in-database `read_only` statement whitelist;
  direct database connections are not supported (removed in 0.4.0).
- Shared-core guardrails: risk lanes per tool, read-only mode, guardrail rules
  (block / confirm / warn), protected lists, JSONL audit, output masking.
- Tools-config whitelist (`{"enabledTools": [...]}`) with upstream fallback
  semantics.
- Startup probe of the `execute_sql` function (deploy `sql/mcp-execute-sql.sql`
  via the management console once; auto-deploy was removed with direct
  connections in 0.4.0).
- Dual transport (stdio and Streamable HTTP) with the standard runner.

## Available Tools

| Tool | Purpose | Risk |
|---|---|---|
| `list_tables` | List accessible tables grouped by schema | READ |
| `list_extensions` | List installed PostgreSQL extensions | READ |
| `execute_sql` | Run arbitrary SQL (service-role or direct connection) | WRITE |
| `get_database_connections` | Active client backends from pg_stat_activity | READ |
| `get_database_stats` | pg_stat_database + pg_stat_bgwriter snapshot | READ |
| `get_project_url` | Return the configured Supabase project URL | READ |
| `generate_typescript_types` | Generate TS types via the Supabase CLI | WRITE |
| `rebuild_hooks` | Restart the pg_net worker | WRITE |
| `verify_jwt_secret` | Check whether the JWT secret is configured | READ |
| `list_auth_users` | List auth users via the auth admin API | READ |
| `get_auth_user` | Fetch one auth user by ID (auth admin API) | READ |
| `delete_auth_user` | Delete an auth user by ID (auth admin API) | WRITE |
| `create_auth_user` | Create an auth user (auth admin API, hashing by GoTrue) | WRITE |
| `update_auth_user` | Update auth user fields (auth admin API) | WRITE |
| `list_storage_buckets` | List storage buckets (direct connection) | READ |
| `list_storage_objects` | List objects in a bucket with prefix filter | READ |
| `list_realtime_publications` | List publications (direct connection) | READ |
| `list_cron_jobs` | List pg_cron jobs (empty when not installed) | READ |
| `list_vector_indexes` | List ivfflat / hnsw indexes | READ |
| `get_logs` | Service logs (analytics → CSV → none cascade) | READ |
| `get_advisors` | Security / performance advisory checks | READ |
| `get_storage_config` | Storage bucket configuration | READ |
| `update_storage_config` | Update bucket limits / MIME types / visibility | WRITE |
| `list_table_columns` | Column metadata for a table | READ |
| `list_indexes` | Indexes with definitions and sizes | READ |
| `list_constraints` | PK / FK / UNIQUE / CHECK / EXCLUDE constraints | READ |
| `list_foreign_keys` | Foreign-key relationships | READ |
| `list_rls_policies` | Row Level Security policies | READ |
| `list_triggers` | Table triggers | READ |
| `list_database_functions` | User-defined functions | READ |
| `get_function_definition` | Full source of a database function | READ |
| `get_trigger_definition` | Full definition of a trigger | READ |
| `get_rls_status` | RLS enablement status per table | READ |
| `list_available_extensions` | Extensions available for installation | READ |
| `get_cron_job_history` | pg_cron job execution history | READ |
| `get_index_stats` | Usage statistics for one index | READ |
| `get_vector_index_stats` | Usage statistics for vector indexes | READ |
| `explain_query` | EXPLAIN a query with optional ANALYZE | READ |

Seven tools mutate state (`WRITE`): `execute_sql`,
`generate_typescript_types`, `rebuild_hooks`, `delete_auth_user`,
`create_auth_user`, `update_auth_user` and `update_storage_config`. Upstream
tools carry no `confirm` parameter, so no tool is classified DANGEROUS — the
default behaviour stays identical to the TypeScript server. Operators who
want explicit confirmation can add a `confirm` guardrail rule (see
Configuration) without changing tool signatures.

### execute_sql channel and the hardened function

`execute_sql` calls the `public.execute_sql(query, read_only)` RPC with the
service-role key (the only supported channel since 0.4.0). The repo ships the hardened function definition at
`sql/mcp-execute-sql.sql` (service_role-only access, in-database `read_only`
statement whitelist, first-keyword dispatch, grants restricted to
service_role). Deploy it once via psql or the management console:

Deploy it once through the cloud management console (for example the
postgres-meta `/pg/query` channel); the server probes for it at startup.

When the RPC function is missing, the server logs a warning at startup;
deploy the definition via the management console to enable the channel.

## Usage Guide

### Prerequisites

- Python 3.10+ and [uv](https://docs.astral.sh/uv/)
- A running RDS Supabase (or self-hosted Supabase) instance
- An anon key plus a service-role key (SQL channel + auth admin API);
  direct database connections are not supported (removed in 0.4.0)

### Installation

```bash
# uvx (no checkout)
uvx --from git+https://github.com/huaweicloud/rds-supabase-fullstack \
  --subdirectory server/mcp_server_rds_supabase \
  mcp-server-huaweicloud-rds-supabase

# pip from a checkout
pip install ./server/mcp_server_rds_supabase
```

## Configuration

| Variable | Required | Description |
|---|---|---|
| `SUPABASE_URL` | Yes | Base URL of the Supabase gateway |
| `SUPABASE_ANON_KEY` | Yes | Anonymous key |
| `SUPABASE_SERVICE_ROLE_KEY` | No | Service-role key; enables the RPC SQL channel |
| `SUPABASE_AUTH_JWT_SECRET` | No | JWT secret (checked by `verify_jwt_secret`) |
| `RDS_SUPABASE_WORKSPACE_PATH` | No | Workspace root for file outputs (default: cwd) |
| `RDS_SUPABASE_TOOLS_CONFIG` | No | Path to `{"enabledTools": [...]}` JSON whitelist |
| `HUAWEICLOUD_MCP_READ_ONLY` | No | `true` blocks every WRITE tool |
| `HUAWEICLOUD_MCP_GUARDRAILS_CONFIG` | No | YAML guardrail rules (block / confirm / warn) |
| `HUAWEICLOUD_MCP_PROTECTED_IDS` | No | Comma-separated protected resource IDs |
| `HUAWEICLOUD_MCP_PROTECTED_NAMES` | No | Comma-separated protected names |
| `HUAWEICLOUD_MCP_PROTECTED_TAGS` | No | Comma-separated protected tags |
| `HUAWEICLOUD_MCP_AUDIT_FILE` | No | JSONL audit file (audit always emits to stderr) |
| `MCP_SERVER_HOST` / `MCP_SERVER_PORT` | No | Streamable HTTP listen address (0.0.0.0:8000) |

Notes:

- Without `SUPABASE_SERVICE_ROLE_KEY`, SQL tools return a configuration
  error. Storage/publication listing tools report that direct connections
  are unsupported (RPC rework pending). Auth user tools use the auth admin
  API (service-role key only).
- The guardrail middleware masks secret-like keys and values in tool output
  (a shared-core security property that cannot be disabled).
- A `confirm` rule example: requests confirmation before every `execute_sql`
  execution while leaving all tool signatures unchanged.

```yaml
rules:
  - id: confirm-execute-sql
    action: confirm
    message: "Review the SQL statement before executing it."
    match:
      tools: ["execute_sql"]
```

## Run with UVX

```bash
MCP_SERVER_HOST=0.0.0.0 MCP_SERVER_PORT=8000 \
uvx --from git+https://github.com/huaweicloud/rds-supabase-fullstack \
  --subdirectory server/mcp_server_rds_supabase \
  mcp-server-huaweicloud-rds-supabase -t streamable-http
```

The Streamable HTTP endpoint is `/mcp`. Protect it at the network layer: the
upstream TypeScript HTTP auth middleware (JWT bearer, role privileges, CORS,
rate limiting) is not part of this port — stdio is the primary transport.

## Examples

Inspect schema, then verify RLS posture:

1. `list_tables` → discover `public.students`
2. `get_rls_status` → check whether RLS is enabled
3. `get_advisors` with `type="security"` → review advisory issues
4. `execute_sql` with `read_only=true` for further SELECT investigation

## Client compatibility

| Client | Transport | Notes |
|---|---|---|
| Any MCP client (Claude Code, opencode, AgentArts, ...) | stdio | Primary mode |
| HTTP clients | Streamable HTTP | Endpoint `/mcp`; add network auth |

## Permissions

- Read-only operations: anon key + service-role key for the RPC channel.
- Write operations (9 WRITE tools): service-role key or direct connection;
  consider `HUAWEICLOUD_MCP_READ_ONLY=true` for inspection-only agents.
- Only the service-role key is required (RPC + auth admin API channels).

## Development, testing, and release

```bash
uv sync --frozen --all-packages --all-groups
uv run --package mcp-server-huaweicloud-rds-supabase ruff check server/mcp_server_rds_supabase/src server/mcp_server_rds_supabase/tests
(cd server/mcp_server_rds_supabase && uv run --package mcp-server-huaweicloud-rds-supabase mypy src)
uv run --package mcp-server-huaweicloud-rds-supabase pytest server/mcp_server_rds_supabase/tests
uv build --package huaweicloud-mcp-core && uv build --package mcp-server-huaweicloud-rds-supabase
```

241 tests, coverage gate 90% (currently 94%). E2E validation evidence lives
in `docs/validation/` at the repository root.

## Contributing and support

See the repository root CONTRIBUTING.md. Report security issues privately via
SECURITY.md; never paste keys into issues.

## License

Apache License 2.0. The Python implementation derives from the MIT-licensed
upstream `rds-supabase-mcp` (HenkDz and contributors); see NOTICE.
