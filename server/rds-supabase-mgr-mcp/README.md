> Directory integration and source installation: [MIGRATION.md](docs/MIGRATION.md). This is the cloud control-plane MCP; the existing sibling server remains separate.

# Supabase management MCP — 0.3.8a1

Local stdio MCP with a real HTTP transport, not a mock-success adapter. No cloud validation has been performed.

## Implemented tools
- `list_supabase_applications`, `show_supabase_application`
- `list_supabase_api_keys` (metadata only), `show_supabase_auth_config`
- `show_supabase_job`, `wait_supabase_job` (task status only; resource/business verification remains pending)
- `change_supabase_ssl`, `change_supabase_eip`
- `delete_supabase_application` (retains PG), `reset_supabase_api_key`
- `update_supabase_auth_flags` (explicit registration/anonymous booleans only)
- Three existing capability/planning tools remain available; creation planning is not creation execution.

## Configure and run
Install this package and `../../libs/huaweicloud_mcp_core` into a project virtual environment. Run `mcp_server_supabase` for stdio.

Supply environment variables through the trusted MCP host configuration, never through tool arguments:
- `SUPABASE_RDS_ENDPOINT`: verified HTTPS service origin, without path, query or user information. Console proxy endpoints are not accepted as a substitute for a verified service endpoint.
- `HUAWEICLOUD_PROJECT_ID`: target project.
- `HUAWEICLOUD_AUTH_TOKEN`: externally provisioned service token; read on each request. No browser cookie login or token exchange is implemented.
- `SUPABASE_ENABLE_WRITES=true`: explicit server-side write opt-in, off by default.
- `HUAWEICLOUD_MCP_READ_ONLY=true`: blocks writes regardless of opt-in.
- Shared core protection/audit configuration applies. Logs go to stderr.

Default `confirm=false` persists a ten-minute plan and returns `plan_id`. Confirm the reviewed intent and call again with the same parameters, `confirm=true` and that plan ID. Binding covers endpoint, project, credential digest, resource path, method and normalized payload. The service re-reads target state/protection before atomically claiming the plan. A plan can submit only once.

`SUPABASE_STATE_FILE` selects the SQLite ledger (default user-local state directory). It stores digests, plan IDs, status and job IDs, never request bodies or tokens. Protect this directory with user-only permissions, including Windows ACLs. Keep the same ledger across restarts and local processes. `inspect_supabase_plan` reads records without cloud calls.

Accepted/unknown/submitted equivalent intents remain blocked even under a new plan. There is currently no automated resolution/release operation: reconcile with an operator before any future repeated change; do not delete the ledger to bypass protection. Credential rotation changes plan binding; this mechanism is not cloud-side idempotency or protection across independent state databases. A crash after claim but before send conservatively leaves submitted state. The MCP cannot prove a human saw a confirmation; the host must enforce its approval UX.

REST HTTP client rejects non-HTTPS endpoints (loopback is only an explicit test constructor option), never follows redirects, caps response bytes, uses a 30s timeout and never retries. Unknown write results require reconciliation. 202 is accepted, not completed. Target responses not matching the verified top-level id/status shape fail closed for writes pending endpoint validation.

`show_supabase_job` is a single request; `wait_supabase_job` provides bounded read-only observations using the public RDS single-job schema. Supabase live compatibility remains unverified. Public responses are filtered for secret fields, capped and additionally masked by core middleware. Data contract/schema compatibility must be verified before real usage.

## Verification
`python -m unittest discover -s tests -v`

`python tests/smoke_stdio.py`

Tests exercise a local HTTP server (not cloud API), request bodies, pagination, secret filtering, readonly behavior, preview, state rejection and no redirect/retry. Skill host behavior is not covered by these unit tests.

See `BLOCKERS.md` for unimplemented scope. This is a development release, not six-scene production acceptance.

## Input and cancellation contract (0.3.7a1)
Unknown top-level tool arguments are rejected before invocation, without echoing supplied names/values. Tools/list advertises additionalProperties=false. Invalid types/field constraints still use the existing SDK/service validation; this is not a complete input coercion redesign.

`cancel_supabase_plan(plan_id)` atomically revokes a prepared local plan, including after process restart. Repeated cancellation is idempotent. Once submission starts, cancellation is refused: it does not cancel or roll back a cloud job. Cancellation is a local WRITE tool and obeys shared read-only/guardrail policy, but does not require the cloud-write opt-in. An expired plan cannot submit even if its stored state still says prepared.

EIP unbind rejects non-null binding IDs/addresses rather than silently discarding them. `get_supabase_capabilities` reports cloud_verified=false and separates available operations from remaining scope.

See [tool contract](docs/TOOL_CONTRACTS.md) and [recovery rules](docs/RECOVERY.md). These distinguish target requirements from current capabilities. Live IAM validation and generated SDK integration, live task reconciliation and six-scene acceptance remain pending.

Requirement target: [MCP requirements](docs/REQUIREMENTS.md), [acceptance matrix](docs/ACCEPTANCE.md), [open questions](docs/OPEN_QUESTIONS.md). Product documents are synchronized from the local requirement baseline; target scope does not imply implementation.

## Workstation integration before CodeArts (0.3.7a1)
Run `python -m mcp_server_supabase.diagnostics offline` for isolated stdio checks without cloud credentials or calls. Run `python -m mcp_server_supabase.diagnostics check` to validate configuration syntax without network access. Only an operator in an authorized test environment should run `python -m mcp_server_supabase.diagnostics readonly --allow-cloud-read`; optional `--application-id` and `--job-id` add scoped reads. This CLI never submits cloud writes and reports summary checks only, not raw resource values or credentials. See [workstation guide](docs/WORKSTATION.md).

Key metadata supports status/type/ID/sorting filters and uses a six-field output whitelist. Reset now performs an application-scoped exact-ID metadata lookup immediately before claiming the plan, requiring exactly one normal record. Failed preflight leaves the plan prepared with no cloud write. Backend authorization/state validation remains essential because the cloud may change after local checks. Key name/time filters and new-key correlation remain pending.

## Recovery metadata (0.3.7a1)
HTTP failures expose error.recovery with category, next_action and automatic_retry=false. Submitted writes override transport categories with submission_unknown and plan_id; no HTTP code alone proves a write had no side effects. Raw backend error bodies are not returned. This is recovery guidance, not automatic reconciliation or unlocking. Existing errors without recovery remain compatible.

## Platform delivery
Windows x64 / 64-bit CPython 3.12 is the first delivery target, not yet a Windows-accepted release. See [compatibility matrix and Windows checklist](docs/COMPATIBILITY.md). The installer verifies target architecture and all manifest files before creating its environment. macOS development tests are recorded separately from Windows acceptance.

## SDK transport (0.3.7a1)
Use `SUPABASE_TRANSPORT=sdk_core` for Huawei SDK Core signed requests. See [SDK setup and migration](docs/SDK.md). Existing REST token mode remains the default for compatibility; no automatic credential fallback. This is not a generated Supabase SDK.

## 0.3.7a1 supplemental contract review
See [implemented changes, conflicting evidence and acceptance](docs/SUPPLEMENT_REVIEW.md). Job output now uses whitelisted normalized task status instead of arbitrary raw response fields.

## Auth reconciliation (0.3.7a1)
`reconcile_supabase_auth_plan` verifies the recorded job and fresh Auth values before ending an accepted local execution. Only matching Auth flag plans are supported. It performs cloud reads and a local ledger write; requires local WRITE permission but no cloud-write opt-in. See [contract and limitations](docs/RECONCILIATION.md) and [workstation prompt](docs/NEXT_WORKSTATION_PROMPT.md).

## 0.3.8a1：六场景增量交付

本版增加12个工具（总计29个）：应用改密、Auth提供方/模板/URL、OBS配置、VPC组查询/创建/规则增删、创建候选发现、Single创建提交及ApiKey本地交付。敏感请求通过操作方受保护的本地别名提供，详见[配置说明](docs/LOCAL_REQUESTS.md)。

请从[子场景验收矩阵](docs/SIX_SCENARIO_MATRIX.md)核对已实现、未实现及待真实验证项。包周期创建、PG级联、证书原生发现/购买、宿主级秘密保险库仍未完成；此版不能称六场景全量生产验收通过。Windows联调使用[执行Prompt](docs/NEXT_WORKSTATION_PROMPT.md)，码道仍在最后。
