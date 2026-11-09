# Control-plane migration

This directory imports the 0.3.7a1 control-plane MCP from personal development branches. It is separate from server/mcp_server_rds_supabase, which exposes instance/data-facing tools. No existing server or skill is replaced.

- Repository directory: server/mcp_server_rds_supabase_mgr (renamed from server/rds-supabase-mgr-mcp to match the mcp_server_* convention; the rename is directory-only)
- Python distribution/module/CLI retained: mcp_server_supabase
- Scenario Skill: skills/huaweicloud-supabase
- Shared dependency: ../../libs/huaweicloud_mcp_core (existing root 1.0.0 source matches the validated source); do not substitute the other server's vendored 1.2 runtime without compatibility tests.
- Source MCP commit: be64de0f5174adceb91fa3e163528e8a3bc14490
- Source Skill commit: 569f44f5236bf1227322e0ad8d94362ece5716ac

Development prerelease: partial six-scene implementation; generated product SDK, complete scenario delivery, trusted TLS/network and dependency security policy remain open. Do not infer production readiness from import or tests. No original internal handoff materials, environment files, credentials, execution databases, dependency binaries or release ZIPs are imported.

The repository name does not change the installed entry point. Existing mcp_server_supabase clients remain compatible. Release bundles are maintained separately; the PowerShell bundle installer expects bundled wheels and is not a source-checkout installer.

Source checkout: create a virtual environment, install ../../libs/huaweicloud_mcp_core then this package; install pytest and pytest-cov for the repository 80% coverage gate. Run pytest from this directory and python -m mcp_server_supabase.diagnostics offline. Never run real cloud calls in CI.

Migration validation: 97 tests passed with 92.02% line coverage, including stdio subprocesses (coverage subprocess patch). The repository 80% threshold is retained. Test dependencies require coverage>=7.10 and pytest-cov>=7 for this collection mode. This is local validation, not cloud or target CI acceptance.

Use a separate virtual environment for this control-plane server and the sibling instance/data-facing server, whose declared core dependency differs. Existing repository CI currently contains placeholder steps targeting main; this migration's coverage result was measured locally and is not an upstream CI result. Wiring develop-branch CI is a follow-up before treating the gate as automatically enforced.
