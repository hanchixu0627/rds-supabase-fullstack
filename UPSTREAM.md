# Upstream Attribution

Parts of the skills in this repository are derived from
[supabase/agent-skills](https://github.com/supabase/agent-skills) (MIT License,
Copyright (c) 2026 Supabase), baseline commit `c9be0e9`.

| Skill | Upstream package | Derivation |
|---|---|---|
| `skills/rds-supabase` | `skills/supabase` | Rewritten for the Huawei Cloud RDS Supabase deployment: CLI/Management-API/cloud-dashboard touchpoints removed or replaced with the self-hosted MCP server; schema changes routed through the init.sql single-transaction workflow; serverless compute routed to Huawei Cloud FunctionGraph; security checklist adapted to the deployment (JWT-claims identity, static service_role key). |
| `skills/rds-supabase-postgres-best-practices` | `skills/supabase-postgres-best-practices` | Rule bodies largely verbatim (the library targets "Postgres running anywhere"); 9 reference links re-pointed to postgresql.org/pgbouncer.org; 5 rules rewritten where they relied on standard-stack helpers (`auth.uid()`) or cloud conventions (Supavisor ports, one-click extensions); 3 new `rds-` rules added for deployment-specific concerns. |
| `skills/rds-supabase-mcp` | — | Original content (server management skill). |

Each derived skill bundles the upstream MIT license text in its `LICENSE` file;
the original copyright notice and permission notice are retained as required by
the MIT License, and modifications are licensed under MIT as well.

The full adaptation analysis (dependency inventory, KEEP/ADAPT/DROP decisions,
upstream defect findings) is in
`docs/research/2026-11-06-agent-skills-insight-and-adaptation.md`.
