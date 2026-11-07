# huaweicloud-mcp

> **Language:** English | [中文](./README.md)

Huawei Cloud MCP Server shared repository: provides MCP tools for each Huawei Cloud service, supporting both local (stdio) and remote (streamable-http) deployment.

## MCP Server List

### Management & Governance

- **[RFS MCP](server/mcp_server_rfs/README_en.md)**: Resource Formation Service — one-click HCL template deployment as stacks, dry-run preview for execution plans, root-cause diagnosis for failed deployments, secure decommissioning.
- **[RC MCP](server/mcp_server_rc/README_en.md)**: Resource Center — global resource search and group management, resource relationship queries, advanced ResourceQL queries.

### Database

- **[RDS Supabase MCP](server/mcp_server_rds_supabase/README.md)**: Self-hosted Supabase (BaaS) on Huawei Cloud RDS PostgreSQL — schema and data inspection, RLS policies, SQL execution (init.sql migration deployment), GoTrue user management, storage bucket configuration, advisor diagnostics. Ships a vendored core library (1.2.0) with a standalone uv lock and Docker deployment.

## Developer Documentation

The complete development guide is available at [docs/development/](docs/development/README.md), split into 10 feature-focused documents: core package modular API, tool scenario methodology, service/client layers, guardrails, output & errors, three-tier testing, hands-on service creation from scratch, engineering & release. Reference implementation: `server/mcp_server_rfs/`; scaffold: `docs/development/template/`.

## Core Capabilities (Shared Across All Services)

- Simplified authentication: `HUAWEICLOUD_ACCESS_KEY / SECRET_KEY / REGION`, project_id auto-resolved via IAM
- Security guardrails: risk classification (READ/WRITE/DANGEROUS), double confirmation for DANGEROUS operations, resource protection allowlist, output desensitization, structured auditing (enabled by default)
- Output governance: structured JSON + token budget (default 20 items, field allowlist, truncation for oversized content)
- Read-only mode: `HUAWEICLOUD_MCP_READ_ONLY=true` one-click interception of all write operations

## Quick Start

```bash
cd server/mcp_server_rfs
uv sync
export HUAWEICLOUD_ACCESS_KEY=... HUAWEICLOUD_SECRET_KEY=... HUAWEICLOUD_REGION=cn-north-4
uv run mcp_server_rfs
```

## New Service Onboarding

See [docs/08-new-service-walkthrough.md](docs/development/08-new-service-walkthrough.md): open issue → copy scaffold template → three-tier development → self-test → bilingual README → PR review.

## Agent Skills

The `skills/` directory provides skills authored to the Agent Skills open standard (installable via `npx skills add`):

- **[rds-supabase-mcp](skills/rds-supabase-mcp/SKILL.md)**: RDS Supabase MCP server usage skill — installation and configuration, all 38 tools, the five-step init.sql deployment workflow, and verification methods.
- **[rds-supabase](skills/rds-supabase/SKILL.md)**: RDS Supabase platform application development skill — client integration, auth, schema changes, an RLS debugging quick reference, and serverless compute routing.
- **[rds-supabase-postgres-best-practices](skills/rds-supabase-postgres-best-practices/SKILL.md)**: Postgres best-practices rule library — symptom-to-rule-file index, including rules specific to the Huawei Cloud RDS deployment.
- **[huaweicloud-mcp-dev](skills/huaweicloud-mcp-dev/SKILL.md)**: development guide skill for MCP servers in this repository.

## License

MIT
