# Changelog

All notable user-visible changes are recorded here. This project follows
semantic versioning.

## [Unreleased]

### Added

- Skill `huawei-supabase-frontend` v0.1.0: private OBS + CDN static frontend
  deployment, integration with existing Huawei Cloud RDS Supabase applications,
  build environment preparation, versioned updates and rollbacks. Includes
  self-contained operation references, the v2 release record contract, four
  JSON examples, and a read-only default prompt.

- Skills v2.5.0 (`rds-supabase-mcp`): added `references/install.md`, a one-shot
  AI-agent installation runbook — collect SUPABASE_URL, SUPABASE_ANON_KEY and
  SUPABASE_SERVICE_ROLE_KEY from the user, render the `mcpServers` config from
  the stdio / streamable-http templates, and verify; the skill description now
  also triggers on installation requests.
- Integrated the rds-supabase capability into `huaweicloud/rds-supabase-fullstack`:
  the MCP server now lives at `server/mcp_server_rds_supabase` with its shared
  core vendored at `vendor/huaweicloud_mcp_core` (path dependency, standalone
  `uv.lock`, server-local `Dockerfile`); the three skills, validation docs,
  examples and the skills contract validator moved with it, and install URLs
  now point at the new repository home
  (`git+https://github.com/huaweicloud/rds-supabase-fullstack#subdirectory=server/mcp_server_rds_supabase`).

### Changed

- Repositioned the `rds-supabase-mgr` skill as "RDS Supabase 全托管生命周期管理"
  (fully-managed lifecycle management): the SKILL.md title and description now
  state the creation / configuration / secure-access / deletion lifecycle
  scope explicitly; operational content is unchanged.
- Renamed the control-plane skill `huaweicloud-supabase` to `rds-supabase-mgr`
  (directory and SKILL.md name) to align with the renamed mgr server
  `mcp_server_rds_supabase_mgr`. Skill content is unchanged; README, the mgr
  server docs (USER_GUIDE, MIGRATION, RELEASE_0.3.8a1), MCP config example
  labels and the validate_skills exemption entry were updated. The server's
  local state directory default (`~/.local/state/huaweicloud-supabase`) is
  intentionally retained to preserve existing execution ledgers.
- Renamed the control-plane server directory `server/rds-supabase-mgr-mcp` to
  `server/mcp_server_rds_supabase_mgr` to match the `mcp_server_*` convention
  (management plane: RDS Supabase instance lifecycle — creation, configuration,
  secure access, deletion). Directory-only rename: the Python
  distribution/module/CLI (`mcp_server_supabase`) and its path dependency on
  `../../libs/huaweicloud_mcp_core` are unchanged; README and MIGRATION.md
  references updated.
- Skills v2.6.0 (`rds-supabase-mcp`): SKILL.md repositioned for the Web
  full-stack development pipeline. The description and overview now lead with
  the two-stage flow — dynamic installation once the RDS Supabase instance is
  created or selected (install.md), then backend development where backend
  code ships as init.sql migration scripts (DDL, GRANT and other
  initialization SQL); added an "instance onboarding" workflow section ahead
  of the general workflow and wired install.md into the prerequisites,
  triggers, boundary table and reference routing.
- Skills v0.2.0: professional skill-authoring pass (superpowers
  writing-skills + Anthropic best practices). `rds-supabase`: removed
  workflow summary from the description (SDO shortcut trap), added
  overview and a skill-routing table, tightened RLS checklist items via
  cross-references to rule files, added a symptom-first debugging quick
  reference (42501, empty results, prepared-statement errors, 403 on new
  tables). `rds-supabase-postgres-best-practices`: description keyword
  coverage extended (N+1, OFFSET pagination, deadlock, upsert, FK
  indexes, JSONB, full-text search, pooling), added a 33-row
  symptom-to-rule-file index table and a grep hint for retrieval.

### Fixed

- Scheduled-task routing corrected: pg_cron is a platform capability (only
  the current test instance lacks it). `rds-supabase` v0.2.1 routes
  scheduled jobs to pg_cron; FunctionGraph now covers serverless compute
  and webhooks only. `rds-supabase-postgres-best-practices` v0.3.0 adds
  the `rds-scheduled-jobs` rule (UTC scheduling, parameter-template
  precondition, job inspection) with description trigger and index row.
  `rds-supabase-mcp` v2.4.1 moves get_cron_job_history back to the
  available tool group (6 deployment-unavailable tools remain).

### Added

- Skill `rds-supabase` v0.1.0: platform development skill adapted from
  supabase/agent-skills `supabase` (MIT, baseline c9be0e9) - agent discipline
  principles and security checklist adapted to the deployment, MCP-first
  workflows (execute_sql single-transaction batches), FunctionGraph routing
  for serverless compute, skill-feedback mechanism.
- Skill `rds-supabase-postgres-best-practices` v0.1.0: Postgres rule library
  adapted from supabase/agent-skills (MIT, baseline c9be0e9) - 31 upstream
  rules (17 verbatim, 9 link-replaced, 5 rewritten for the deployment:
  JWT-claims identity, RDS parameter template, UUIDv7 guidance) plus 3 new
  `rds-` rules (jwt-claims-rls, parameter-template, auth-helpers).
- Repo-level skills contract validator `scripts/validate_skills.py`
  (format contract A1-A7; includes the version-drift tripwire missing
  upstream).
- `UPSTREAM.md`: MIT attribution and derivation record for the two adapted
  skills; per-skill `LICENSE` files bundle the upstream MIT notice.

### Changed

- Skill `rds-supabase-mcp` v2.4.0: frontmatter `name` aligned with the
  directory rename (huawei-cloud-rds-supabase-manage -> rds-supabase-mcp),
  description now carries explicit trigger context and cross-routes to the
  new skills.

### Changed

- Skill v2.3.0: release-grade editorial pass over the skill and its
  references. Fixed a tool-name error (get_rls_policies ->
  list_rls_policies), completed the tool table with the seven
  deployment-unavailable tools, added explicit trigger conditions to the
  scope section, and documented the two-layer read-only mechanism
  (execute_sql read_only vs HUAWEICLOUD_MCP_READ_ONLY). Redundant and
  colloquial wording was removed throughout. execute_sql is documented
  with its hierarchy clear: the primary function is running arbitrary SQL;
  executing DDL/migration scripts (init.sql) to deploy the backend
  definition is its typical use. Positioning: an improvement of
  HenkDz/selfhosted-supabase-mcp managing the self-hosted Supabase BaaS
  platform on Huawei Cloud RDS.

## [0.4.0] - 2026-11-05

### Removed

- Direct database connections: `DATABASE_URL` (the upstream `--db-url`) is no
  longer accepted, and the psycopg dependency, the pg-first fallback chain,
  the transaction helpers and the startup auto-deploy of the `execute_sql`
  function were removed with it. The cloud instance is only reachable through
  the Kong gateway; `execute_sql` now requires the service-role key and runs
  exclusively over the hardened RPC channel.

### Changed

- `execute_sql` precheck message updated (service-role key only).
- `list_storage_buckets`, `list_storage_objects` and
  `list_realtime_publications` now report that direct connections are
  unsupported (RPC-channel rework pending).
- `generate_typescript_types` returns a structured failure explaining that
  direct connections are not supported (rework decision pending).

## [0.3.0] - 2026-11-05

### Changed

- The auth users tool group (`list_auth_users`, `get_auth_user`,
  `create_auth_user`, `update_auth_user`, `delete_auth_user`) now operates
  through the official GoTrue auth admin API (`/auth/v1/admin/users`) with the
  service-role key instead of requiring a direct database connection, making
  all five tools usable on the cloud-managed instance (verified end-to-end:
  full create/read/update/delete lifecycle, pagination cross-checked against
  the SQL channel).

### Added

- Client support for the auth admin API (GET/POST/PUT/DELETE with the
  service-role key, transport-error envelopes).

### Deprecated

- Upstream deviations kept for signature parity and documented: field names
  mapped back to the upstream shape (app_metadata -> raw_app_meta_data),
  timestamps in GoTrue ISO 8601 text, role create/update has no effect (the
  admin API always assigns 'authenticated'; role-only updates fail with a
  clear message).

## [0.2.0] - 2026-11-04

### Removed

- `apply_migration` and `list_migrations`: the cloud-managed instance has no
  direct database connection and no `supabase_migrations` bookkeeping table,
  so both tools could never succeed in this deployment. Schema changes go
  through `execute_sql`.
- `list_edge_functions`, `get_edge_function_details` and
  `list_edge_function_logs`: the Edge Functions runtime is not part of this
  deployment, so the tools had no data source.

  The tool surface now intentionally differs from the upstream TypeScript
  server (38 tools instead of 43); the E2E comparison driver records this as
  an intentional deviation. `generate_typescript_types` is retained pending a
  rework decision.

## [0.1.0] - 2026-11-04

### Added

- Python re-implementation of the TypeScript `rds-supabase-mcp` server with
  all 43 upstream tools: identical names, parameters, defaults, return shapes
  and error messages; upstream registration order preserved.
- Shared `huaweicloud_mcp_core` vendored into the workspace (config /
  credentials / errors / security guard / guardrails / output envelopes /
  standard runner), matching the `huaweicloud-gaussdb-mcp` repository form.
- Three-layer package structure: `tools` (thin registration with
  `@mcp.tool()` + `@guard(risk=...)`), `service` (upstream execute() logic,
  exact upstream error text), `client` (httpx PostgREST RPC, psycopg direct
  access, fallback chain, startup RPC probe and hardened auto-deploy).
- Risk lanes for every tool: 35 READ, 8 WRITE; read-only mode, guardrail
  rules, protected lists, JSONL audit and output masking from the shared core.
- Upstream tools-config whitelist (`RDS_SUPABASE_TOOLS_CONFIG`) with upstream
  fallback semantics and messages.
- Hardened `execute_sql` SQL asset (`sql/mcp-execute-sql.sql`): service_role
  only, in-database `read_only` statement whitelist, first-keyword dispatch;
  embedded verbatim in the client (drift-checked by tests).
- Bilingual READMEs (root and server), CONTRIBUTING, SECURITY, Dockerfile,
  CI workflow, examples, and the agent skill package
  `skills/rds-supabase-mcp`.
- Engineering trail under `docs/`: implementation plan, GaussDB case
  replication spec, upstream functional contract, and E2E validation evidence.

### Changed

- Auto-deployed `execute_sql` function upgraded from the upstream embedded
  v1 definition to the hardened v4.1 asset (identical call interface;
  `read_only` now enforced in-database) — a deliberate security carry-over
  from the upstream repository's hardened deployment.

### **Validation**

- 291 unit tests, 95.45% coverage (gate: 90%); ruff and mypy strict clean.
- E2E dual-server comparison against the TypeScript server on a live Huawei
  RDS Supabase instance; evidence in `docs/validation/`.
