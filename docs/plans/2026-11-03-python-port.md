# huaweicloud-rds-supabase-mcp Python 工程适配实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 把 TypeScript 版 `rds-supabase-mcp`（43 工具，云托管自建 Supabase MCP）以 Python 1:1 重建到 `huaweicloud-rds-supabase-mcp` 空仓中，格式与规范严格对齐 `huaweicloud-gaussdb-mcp` 标准案例（uv workspace + huaweicloud_mcp_core + 三层架构 + 三级风险护栏 + 90% 覆盖率门禁 + 双语文档 + CI/Docker/skill），全部 43 个工具能力零差异保留，并以双服务器端到端对比验证。

**Architecture:** 独立仓 uv workspace：`libs/huaweicloud_mcp_core`（从 gaussdb 案例逐字节 vendored，Apache-2.0）+ `server/mcp_server_rds_supabase`（本仓新建）。服务包三层：tools（`@mcp.tool()` + `@guard(risk=...)` 极薄注册，6 个模块按 TS 注册顺序分组）→ service（6 个 Service 类承接 TS 工具 `execute()` 体逻辑 1:1，错误以 `McpToolError` 抛出、消息原文保留）→ client（httpx 封装 PostgREST RPC + psycopg 封装 pg 直连 + fallback 链 + 启动期 RPC 探测/自动建函数）。

**Tech Stack:** Python ≥3.10 · uv workspace · `mcp` 2.x（core 的 build_server/run_standard）· httpx（PostgREST）· psycopg[binary]（pg 直连）· ruff + mypy strict + pytest（cov ≥90%）· hatchling。

**Spec:**
- `docs/research/2026-11-03-gaussdb-case-replication-spec.md` —— gaussdb 标准案例复制规范（格式/规约唯一依据）
- `docs/research/2026-11-03-rds-supabase-functional-contract.md` —— TS 版 43 工具功能契约（行为唯一依据）
- TS 源码（1:1 移植的事实来源）：`/Users/fitz/work/projects/research/supabase/supabase-mcp/rds-supabase-mcp/src/`
- gaussdb 案例（格式事实来源）：`/Users/fitz/work/projects/research/supabase/supabase-mcp/huaweicloud-gaussdb-mcp/`

## Global Constraints

1. **工具能力零差异**：43 个工具的注册名、description（英文原文逐字）、输入参数（名/类型/可选性/默认值）、SQL 原文、返回结构、错误消息英文原文，全部与 TS 版一致；注册顺序与 TS 一致（模块分组拼接后等于 TS 顺序）。
2. **格式对齐 gaussdb 案例**：根 pyproject 仅 workspace 声明（`package = false`）；发行名 `mcp-server-huaweicloud-rds-supabase`、包名 `mcp_server_rds_supabase`、入口脚本 `mcp-server-huaweicloud-rds-supabase = "mcp_server_rds_supabase.main:main"`；每工具 `@mcp.tool()` 上、`@guard(risk=...)` 下；docstring 五段式（一行祈使句 → `Scenario:` → `Args:` → `Returns:`）；三层单向依赖；ruff（line-length 100, select E/F/W/I/UP/B/SIM/RUF）+ mypy strict + pytest `--cov=src --cov-fail-under=90`；服务名 `rds-supabase`（服务器名 `huaweicloud-rds-supabase`）。
3. **风险分级保 parity**：34 个 READ、9 个 WRITE（apply_migration、execute_sql、generate_typescript_types、rebuild_hooks、delete/create/update_auth_user、update_storage_config）；**不引入 DANGEROUS+confirm 参数**（会改变默认行为，违反零差异）；需 confirm 的用户经 guardrails YAML confirm 规则获得（README 说明）。
4. **环境变量沿用 TS 名**：`SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_SERVICE_ROLE_KEY / DATABASE_URL / SUPABASE_AUTH_JWT_SECRET`；新增 `RDS_SUPABASE_WORKSPACE_PATH`（默认 cwd）、`RDS_SUPABASE_TOOLS_CONFIG`（对齐 TS `--tools-config` 能力）。guardrails 沿用 core 的 `HUAWEICLOUD_MCP_*`。
5. **自动建函数 DDL 采用 v4.1 加固版**（`sql/mcp-execute-sql.sql`，非 TS 内嵌 v1）——函数接口 `execute_sql(query text, read_only boolean) returns jsonb` 与 v1 相同，工具行为不变；read_only 门禁生效是本仓既定安全加固（CHANGELOG/README 声明）。
6. **许可证**：仓库 Apache-2.0（对齐 gaussdb 案例）+ `NOTICE` 声明 Python 版自 MIT（rds-supabase-mcp，上游 HenkDz 及贡献者 + 华为云开源开发者）衍生，保留合规链。
7. **留痕**：每 Task 一 commit；本计划 checkbox 随进度更新提交；E2E 证据落 `docs/validation/`。
8. 版本号 0.1.0（对齐 TS package.json）。

## Review Focus（最可能咬人的输入/工况 → 归属任务的测试）

1. fallback 链次序与错误兜底：无 db-url 无 service key 时 34 个 SQL 工具统一返回 `MCP_CONFIG_ERROR`（'Neither direct database connection...' 原文）→ Task 4 exemplar + 各模块测试断言。
2. PostgREST 非 200 错误形状（code/message/details/hint 透传）与 `MCP_RPC_FORMAT_ERROR`（data 非数组）→ Task 3 test_client。
3. 标识符校验（schema/table/pattern 正则）拒绝恶意输入的报错原文 → Task 9 inspection 模块逐工具断言。
4. `apply_migration` 事务性（sql 失败时 INSERT 不执行、rollback）→ Task 4 test_database。
5. auth 五件套的参数化查询与 23505 唯一冲突消息 → Task 6 test_auth_users。
6. 工具白名单：`enabledTools` 过滤 + 未知名 warn + 非白名单禁用 → Task 10 test_tools。
7. 只读模式 `HUAWEICLOUD_MCP_READ_ONLY=1` 拦 9 个 WRITE、放 34 个 READ → Task 10 middleware 测试。
8. 未声明 @guard 的工具被 middleware 以 `MCP_GUARDRAIL_ERROR` 拒绝（防漏标）→ Task 10 EXPECTED 注册表全量断言 43 项。

---

### Task 1: 仓库脚手架 + vendored core + 根文件

**Files:**
- Create: `pyproject.toml`、`.gitignore`（抄 gaussdb）、`LICENSE`（Apache-2.0 全文，抄 gaussdb）、`NOTICE`
- Create: `libs/huaweicloud_mcp_core/**`（从 gaussdb 案例逐字节复制，含 tests）
- Create: `docs/`（已就位：plans/research/validation）

**Steps:**
- [x] 从 `huaweicloud-gaussdb-mcp` 复制 `libs/huaweicloud_mcp_core`（`rsync -a --exclude .venv`）与根 `.gitignore`、`LICENSE`
- [x] 写根 `pyproject.toml`（workspace members 换成 `server/mcp_server_rds_supabase`）
- [x] 写 `NOTICE`（Apache-2.0 主体 + MIT 衍生声明：基于 rds-supabase-mcp（HenkDz/selfhosted-supabase-mcp 及贡献者 nightness/calclavia/dalisys/moatus + 华为云开源开发者，MIT）；huaweicloud_mcp_core vendored 自 huaweicloud-gaussdb-mcp（Apache-2.0））
- [x] `git add -A && git commit -m "chore: scaffold workspace, vendor huaweicloud_mcp_core, add license and research docs"`

### Task 2: 环境与包骨架

**Files:**
- Create: `server/mcp_server_rds_supabase/pyproject.toml`（gaussdb 服务包 pyproject 结构；dependencies = huaweicloud-mcp-core + httpx + psycopg[binary]；无华为云 SDK 行与 mypy overrides）
- Create: `src/mcp_server_rds_supabase/{__init__.py,main.py,server.py,settings.py}`、`client/__init__.py`、`service/__init__.py`、`tools/__init__.py`（1 行 docstring）
- Create: `sql/mcp-execute-sql.sql`（从 rds-supabase-mcp 复制 v4.1）
- Create: `tests/{__init__.py,conftest.py}`

**Interfaces (Produces):**
- `RdsSupabaseSettings`（frozen dataclass：url、anon_key、service_role_key、db_url、jwt_secret、workspace_path、tools_config_path 全 `repr=False` 敏感项；`from_env()` 缺 url/anon 抛 `McpToolError("MCP_CONFIG_ERROR", "Error: Supabase URL is required. Use --url or SUPABASE_URL.")` 同款消息) — `settings.py`
- `main()`：from_env 失败 → stderr 原文 + `SystemExit(1)`；成功 → 尽力 `check_and_create_rpc_function()`（try/except 只 log 'Error during client initialization:...'）→ `run_standard(mcp, service_name="rds-supabase")`
- `mcp = build_server("rds-supabase", version=__version__)`（server.py，尾部 import tools 各模块，`# noqa: E402,F401`）

**Steps:**
- [x] 安装 uv：`curl -LsSf https://astral.sh/uv/install.sh | sh`（`~/.local/bin/uv`）
- [x] 写 pyproject + 骨架 + sql 资产 + 空 conftest（先只含 `clean_env` autouse fixture：删 `SUPABASE_*/DATABASE_URL/RDS_SUPABASE_*/HUAWEICLOUD_*`）
- [x] `uv sync --all-packages --all-groups` 成功；`uv run --package mcp-server-huaweicloud-rds-supabase python -c "import mcp_server_rds_supabase"` 成功
- [x] commit

### Task 3: Client 层（parity 核心）

**Files:**
- Create: `src/mcp_server_rds_supabase/client/rds_supabase_client.py`
- Test: `tests/test_client.py`

**Interfaces (Produces):** `RdsSupabaseClient`（`__init__(settings: RdsSupabaseSettings | None = None, http_client: httpx.AsyncClient | None = None, pg_factory=None)` —— 后两者为测试注入点）：
- `async execute_sql_via_rpc(query, read_only=False)` / `async execute_sql_via_service_role_rpc(...)` → `SqlExecutionResult = list[dict] | {"error": {message, code?, details?, hint?}}`（错误形状与消息原文 1:1：'execute_sql RPC function not found or client not properly initialized.'/'MCP_CLIENT_ERROR'、'Unexpected response format from execute_sql RPC. Expected JSON array.'/'MCP_RPC_FORMAT_ERROR'、'Exception during RPC call: ...'/'MCP_RPC_EXCEPTION'、'Service role key not configured. ...'/'MCP_CONFIG_ERROR'）
- `async execute_sql_with_pg(query)` → rows/`{"error":...}`（psycopg dict_row；pgcode 透传；忽略 read_only —— TS 同）
- `async execute_transaction_with_pg(fn)` → BEGIN/COMMIT/ROLLBACK + 重抛
- `async execute_sql_with_fallback(query, read_only=True)` → pg > service RPC > `{"error":{"message":"Neither direct database connection (DATABASE_URL) nor service role key (SUPABASE_SERVICE_ROLE_KEY) is configured. Cannot execute SQL.","code":"MCP_CONFIG_ERROR"}}`
- `async check_and_create_rpc_function()` → 探测 `rpc('execute_sql',{query:'SELECT 1'})`（service 优先）；42883/PGRST202 且 service key+db url 同时存在 → 经 pg 执行 `_CREATE_EXECUTE_SQL_FUNCTION`（v4.1 常量）+ `NOTIFY pgrst, 'reload schema'`
- getters：`get_supabase_url/get_anon_key/get_service_role_key/get_jwt_secret/get_db_url/is_pg_available/is_service_role_available`
- `_CREATE_EXECUTE_SQL_FUNCTION` 常量 = v4.1 全文；**测试断言常量 == sql/mcp-execute-sql.sql 文件内容**（防漂移）

**Steps:**
- [x] 失败测试先行：MockTransport 模拟 PostgREST 200 数组/非数组/非 200 错误体/网络异常；fake pg_factory 模拟 rows/错误/事务回滚；断言 fallback 三分支与消息原文
- [x] 实现 client；`uv run pytest tests/test_client.py -v` 全绿
- [x] ruff + mypy 过；commit

### Task 4: Exemplar 模块 database（7 工具）

**Files:**
- Create: `src/mcp_server_rds_supabase/service/database_service.py`、`src/mcp_server_rds_supabase/tools/database.py`
- Test: `tests/test_database.py`、`tests/test_tools.py`（EXPECTED 风险注册表，先 7 项）
- Modify: `server.py` 尾部加 `from .tools import database`

**工具（TS 注册序 #1-7，源文件同名 .ts）:** list_tables、list_extensions、list_migrations（READ）；apply_migration、execute_sql（WRITE）；get_database_connections、get_database_stats（READ）

**Exemplar 形态（全部模块照此）:**

```python
# tools/database.py
"""Database catalog and SQL execution tools."""

from typing import Any

from huaweicloud_mcp_core import ToolRisk, guard

from ..server import mcp
from ..service.database_service import DatabaseService


@mcp.tool()
@guard(risk=ToolRisk.READ)
async def list_tables() -> dict[str, Any]:
    """Lists all accessible tables in the connected database, grouped by schema.

    Scenario: inspect the database schema before running SQL or applying a migration.

    Args:
        (none)

    Returns:
        Rows of schema, name and comment, mirroring the upstream tool payload.
    """
    return await DatabaseService().list_tables()
```

（docstring 首行 = TS description 逐字；`Scenario:`/`Returns:` 按 gaussdb 五段式补写；无参数工具 Args 段写 `(none)`。）

```python
# service/database_service.py —— 方法体 1:1 承接 TS 工具 execute()
class DatabaseService:
    def __init__(self, client: RdsSupabaseClient | None = None,
                 settings: RdsSupabaseSettings | None = None) -> None:
        self._settings = settings or RdsSupabaseSettings.from_env()
        self._client = client or RdsSupabaseClient(self._settings)

    async def list_tables(self) -> list[dict[str, Any]]:
        result = await self._client.execute_sql_with_fallback(_LIST_TABLES_SQL, read_only=True)
        return _rows(result)   # 有 error → raise McpToolError(code, f"SQL Error ({code}): {message}") 原文
```

**Steps:**
- [x] 失败测试先行（FakeRdsSupabaseClient：`__getattr__` 动态 async 方法记录 calls、responses 字典供返回值/错误形状；getters 显式设属性）——覆盖 7 工具：正常 rows、SQL error 抛 McpToolError 原文、apply_migration 无 db-url 报错原文 + 事务回滚语义、execute_sql 前置校验原文（'execute_sql requires either a direct database connection...'）
- [x] 实现 service + tools；EXPECTED 注册表 7 项断言风险级
- [x] 全 gates 绿；commit

### Task 5–9: 其余五个模块（并行 subagent）

每个 Task 同 Task 4 模式：`tools/<mod>.py` + `service/<mod>_service.py` + `tests/test_<mod>.py`；subagent 指令含：exemplar 全文、gaussdb 规约要点、TS 源文件清单（逐工具读源码移植，SQL/消息/默认值逐字）、契约报告路径、gates 命令。完成后我审查 + 集成 commit。

- [x] **Task 5 project.py（#8-11）**：get_project_url（READ）、generate_typescript_types（WRITE，subprocess 调 `supabase` CLI、路径安全校验、platform 三值 darwin/linux/win32、消息原文）、rebuild_hooks（WRITE，结构化 {success,...} 不抛错）、verify_jwt_secret（READ，'found'/'not_configured'）
- [x] **Task 6 auth_users.py（#12-16）**：list/get（READ）+ delete/create/update（WRITE）；pg 专用（不走 fallback）；参数化查询、crypt/pgcrypto 探测、23505 消息原文、metadata JSON 序列化、动态 SET 子句（update）
- [x] **Task 7 storage.py（#17-18）**：list_storage_buckets、list_storage_objects（READ，pg 专用，prefix LIKE 参数化）
- [x] **Task 8 platform.py（#19-27）**：list_realtime_publications、list_cron_jobs（两步存在性→[]）、list_vector_indexes、list_edge_functions（三步检查→[]）、get_edge_function_details（单引号转义、null）、get_logs（analytics→CSV→none 级联 + message 原文）、get_advisors（security 4 项/performance 4 项检查 SQL 原文、level 排序、{issues,total_count,type}）、get_storage_config（schema 缺失兜底）、update_storage_config（WRITE，结构化返回不抛错、动态 SET、0→NULL）
- [x] **Task 9 inspection.py（#28-43）**：list_table_columns、list_indexes、list_constraints、list_foreign_keys、list_rls_policies、list_triggers、list_database_functions、get_function_definition、get_trigger_definition、get_rls_status、list_available_extensions、get_cron_job_history、list_edge_function_logs、get_index_stats、get_vector_index_stats、explain_query（全 READ；标识符校验报错原文；各 SQL 原文；get_rls_status 三参任选）

### Task 10: 集成与 server 级机制

**Files:**
- Modify: `server.py`（六个模块 import 按序：database, project, auth_users, storage, platform, inspection —— 拼接注册序 == TS 43 序）
- Create/Modify: `tests/test_tools.py`（EXPECTED 43 项全量风险注册表；middleware 行为：READ_ONLY 拦 9 WRITE/放 34 READ、confirm 规则、未声明 @guard 拒绝；白名单：RDS_SUPABASE_TOOLS_CONFIG JSON → 禁用/未知名 warn）、`tests/test_main.py`
- Create: `src/mcp_server_rds_supabase/tools_config.py`（读 JSON enabledTools；实现方式：优先 FastMCP `remove_tool`，不可用则启动期过滤注册）

**Steps:**
- [x] 43 项注册表断言 + middleware 测试 + 白名单测试
- [x] stdio 冒烟：`initialize` → `tools/list` 返回恰 43 个工具、顺序与 TS 一致
- [x] 全 gates 绿；commit

### Task 11: 文档与仓配套（对齐 gaussdb 案例全家桶）

- [x] `server/mcp_server_rds_supabase/README.md` + `README_zh.md`（章节抄 gaussdb：Version/Overview/Quick start/Category/Features/Available Tools（`| Tool | Purpose | Risk |` 43 行）/Usage Guide/Configuration（环境变量表：SUPABASE_* + HUAWEICLOUD_MCP_* + 说明 v4.1 预部署步骤与 sql 文件）/Run with UVX/Examples/Client compatibility/Permissions/Development/License；中文版含 18+ 变量全表与护栏小节）
- [x] 根 `README.md`/`README_zh.md`（Highlights/Quick start/Security basics/Repository layout/Development/Documentation/Scope/Contributing/License）
- [x] `CHANGELOG.md`（0.1.0 - 2026-11-03，Added + **Validation** 节）、`CONTRIBUTING.md`、`SECURITY.md`（适配 Supabase 凭证暴露处置）、`Dockerfile` + `.dockerignore`（gaussdb 同构，包名替换）
- [x] `.github/workflows/ci.yml`（uv sync → ruff×3 → skill validate + smoke --skip-cloud → core mypy+pytest → server mypy+pytest → build×2）
- [x] `examples/`（stdio uvx JSON、streamable-http JSON、credentials.example.json、guardrails.example.yaml）
- [x] `skills/database/supabase/huawei-cloud-rds-supabase-manage/`（SKILL.md 中文 + references/（mcp-installation-guide.md、verification-method.md、related-tools.md）+ scripts/smoke.py + scripts/validate-skill.py）
- [x] commit

### Task 12: 锁定与构建

- [x] `uv lock`（uv.lock 入库，revision/members 对齐）
- [x] `uv build --package huaweicloud-mcp-core && uv build --package mcp-server-huaweicloud-rds-supabase` 成功
- [x] 本地全量跑 CI 等价命令序列；commit

### Task 13: 端到端双服务器验证 + 留痕 + 推送

- [x] 启动 TS 版（bun，rds-supabase-mcp/src/index.ts，凭证取自 `~/.config/opencode/opencode.jsonc`）与 Python 版（uv run）于同一实例
- [x] `tools/list` 双侧对比：43 名字、description 逐字、inputSchema 结构 diff = 0 差异
- [x] 代表性调用逐工具对比（jq 结构化 diff，容差注记）：list_tables、list_extensions、list_migrations、get_database_connections（结构对比）、get_database_stats、get_project_url、verify_jwt_secret、execute_sql（SELECT 1 / pg_sleep(0)）、get_advisors security+performance、list_table_columns(students)、list_indexes、list_constraints、list_foreign_keys、list_rls_policies、list_triggers、list_database_functions、get_function_definition(execute_sql)、list_available_extensions、list_cron_jobs、list_vector_indexes、list_edge_functions、get_logs、get_index_stats、explain_query、list_auth_users 等 db-url 工具的双侧同报错原文断言、rebuild_hooks 错误路径、get_cron_job_history、list_edge_function_logs、get_vector_index_stats、get_rls_status、get_storage_config、list_realtime_publications、update_storage_config（只读安全侧：双侧同报错——无 db-url）
- [x] Python 侧独立验证：READ_ONLY 模式拦 WRITE；guardrails confirm 规则生效演示；审计 JSONL 落盘证据
- [x] 证据写 `docs/validation/e2e-validation-results.md` + `live-validation-results.json`；CHANGELOG Validation 节引用
- [x] 更新本计划 checkbox 全勾；`git add -A && git commit`；推送 origin main（SSH over 443）

---

## 记录

| 日期 | 事件 |
|---|---|
| 2026-11-03 | 计划创建；两份调研报告入库（gaussdb 复制规范 973 行 / 功能契约 756 行） |
| 2026-11-03 | Task 1–4 完成：脚手架 c508f60、骨架 232d8d6、client 层 16600d2、database exemplar 9271e59 |
| 2026-11-03 | Task 5–9 完成（5 个并行 subagent）：project 21 测试 / auth_users 33 / storage 9 / platform 56 / inspection 114 |
| 2026-11-04 | Task 10–12 完成：集成 d97ed1d（43 工具 + 白名单 + 入口测试 95.45%）；文档/CI/Docker/skill/examples；uv.lock + 双 wheel 构建；stdio 冒烟 SMOKE PASS |
| 2026-11-05 | 直连通道彻底移除（v0.4.0）：删除 DATABASE_URL/--db-url、psycopg 依赖、pg 优先链、事务助手、启动自动建函数；execute_sql 仅走 service-role RPC；存储两件套与 publications 改报「直连不支持，RPC 改造待做」；generate_typescript_types 改为固定结构化失败；241 测试 @93.92% |
| 2026-11-05 | auth 用户组改造（v0.3.0，方案 C）：五件套经官方 GoTrue auth admin API 重写（httpx 直调 /auth/v1/admin/users，service-role 密钥）；字段映射回上游 7 字段形状、时间戳保持 GoTrue ISO 格式、role 仅保签名不透传；探针锁定行为（DESC 排序=SQL 一致、422/email_exists、500/23505、404/user_not_found）；272 单测 @95.11% + 真实例全生命周期回归 89/89 PASS（分页窗口与 SQL 通道交叉验证、重复邮箱原文断言、scratch 用户清理核验 D04 n=0） |
| 2026-11-04 | 工具面裁剪（v0.2.0）：依据可用性清单移除 5 个本部署无法工作的工具（apply_migration、list_migrations、边缘函数三件套）；generate_typescript_types 经用户确认保留；现存 38 工具、269 测试 @95.42%；文档/技能/验证驱动全同步；实例网关一度失联，恢复后完成 38 工具真实例回归：**81/81 PASS**（工具覆盖 38/38、清理基线一致），证据已更新 full-tool-test-results.json + full-tool-test-report.md |
| 2026-11-04 | Task 13 完成：双服务器 E2E 43/43 PASS（tools/list 全对齐 + 调用矩阵全过 + 护栏通过）；期间修复 3 个真实缺陷：list 返回被 SDK 按行拆块（25 工具改 as_text 序列化 + Any 注解）、apply_migration 预检查错误未按上游包裹、E2E 驱动需跳过 TS stdout 的 console.info 污染行。证据：docs/validation/{e2e-validation-results.md, live-validation-results.json, run_e2e.py} |
