# 华为云 RDS Supabase MCP 服务器

[English](README.md)

面向华为云 RDS Supabase（云端托管的自建 Supabase：数据库为 RDS PostgreSQL 实例，外部经
Kong 网关以 PostgREST RPC 访问）的管理 MCP 服务器，可选直连数据库执行特权操作。

## 版本

当前版本：0.4.0；Python 3.10+；MCP Python SDK 2.x；传输：stdio 与 Streamable HTTP；
许可证：Apache-2.0（上游 TypeScript 项目的 MIT 衍生链见仓库 NOTICE）。

## 概述

本服务器是 TypeScript 版 `rds-supabase-mcp` 工具面（上游 43 个工具中保留 38 个；
0.2.0 移除了在本云部署形态下无法工作的 5 个工具，见 CHANGELOG）在共享
`huaweicloud_mcp_core` 运行时上的 1:1 Python 重建：三层架构（tools → service →
client）、三级风险护栏（READ / WRITE / DANGEROUS 车道、只读模式、保护名单、结构化审计）
与库内加固版 `execute_sql` RPC 函数。全部工具名、参数、默认值、返回结构与错误消息与
上游 TypeScript 服务器保持一致；适配层在其上叠加平台护栏。

## 快速开始

```bash
# 只读模式连接运行中的实例
HUAWEICLOUD_MCP_READ_ONLY=true \
SUPABASE_URL=https://your-instance \
SUPABASE_ANON_KEY=<anon-key> \
SUPABASE_SERVICE_ROLE_KEY=<service-key> \
uvx --from git+https://github.com/huaweicloud/rds-supabase-fullstack \
  --subdirectory server/mcp_server_rds_supabase \
  mcp-server-huaweicloud-rds-supabase
```

标准 stdio 客户端配置：

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

## 分类

数据库 / 托管 PostgreSQL 上的自建 Supabase / 运维自动化。

## 特性

- 38 个工具：名称、参数、默认值、返回结构与错误消息逐一一致（与 TypeScript 服务器逐
  工具端到端比对验证；移除的 5 个工具见 CHANGELOG 0.2.0）。
- 经 Kong 网关的 SQL 执行：加固版 `execute_sql` RPC（service-role 密钥）+ 库内
  `read_only` 语句白名单；直连不支持（0.4.0 已移除）。
- 共享核护栏：每工具风险车道、只读模式、guardrail 规则（block / confirm / warn）、
  保护名单、JSONL 审计、输出脱敏。
- tools-config 白名单（`{"enabledTools": [...]}`），语义与上游回退行为一致。
- RPC 函数缺失且同时具备 service-role 密钥与直连时，启动期自动部署加固版
  `execute_sql` 并通知 PostgREST 重载 schema 缓存。
- 双传输（stdio 与 Streamable HTTP），标准运行入口。

## 可用工具

| 工具 | 用途 | 风险 |
|---|---|---|
| `list_tables` | 按schema列出可访问的表 | READ |
| `list_extensions` | 列出已安装的 PostgreSQL 扩展 | READ |
| `execute_sql` | 执行任意 SQL（service-role 或直连） | WRITE |
| `get_database_connections` | pg_stat_activity 活跃客户端后端 | READ |
| `get_database_stats` | pg_stat_database + pg_stat_bgwriter 快照 | READ |
| `get_project_url` | 返回配置的 Supabase 项目 URL | READ |
| `generate_typescript_types` | 经 Supabase CLI 生成 TS 类型 | WRITE |
| `rebuild_hooks` | 重启 pg_net worker | WRITE |
| `verify_jwt_secret` | 检查 JWT secret 是否配置 | READ |
| `list_auth_users` | 经 auth admin API 列出用户 | READ |
| `get_auth_user` | 按 ID 查单个 auth 用户（auth admin API） | READ |
| `delete_auth_user` | 按 ID 删除 auth 用户（auth admin API） | WRITE |
| `create_auth_user` | 创建 auth 用户（auth admin API，GoTrue 负责哈希） | WRITE |
| `update_auth_user` | 更新 auth 用户字段（auth admin API） | WRITE |
| `list_storage_buckets` | 列出存储桶（需直连） | READ |
| `list_storage_objects` | 按前缀列出桶内对象 | READ |
| `list_realtime_publications` | 列出 publication（需直连） | READ |
| `list_cron_jobs` | 列出 pg_cron 任务（未装返回空） | READ |
| `list_vector_indexes` | 列出 ivfflat / hnsw 索引 | READ |
| `get_logs` | 服务日志（analytics → CSV → none 级联） | READ |
| `get_advisors` | 安全 / 性能体检检查 | READ |
| `get_storage_config` | 存储桶配置 | READ |
| `update_storage_config` | 更新桶限额 / MIME / 可见性 | WRITE |
| `list_table_columns` | 表列元数据 | READ |
| `list_indexes` | 索引定义与大小 | READ |
| `list_constraints` | PK / FK / UNIQUE / CHECK / EXCLUDE | READ |
| `list_foreign_keys` | 外键关系 | READ |
| `list_rls_policies` | 行级安全策略 | READ |
| `list_triggers` | 表触发器 | READ |
| `list_database_functions` | 用户自定义函数 | READ |
| `get_function_definition` | 数据库函数完整源码 | READ |
| `get_trigger_definition` | 触发器完整定义 | READ |
| `get_rls_status` | 各表 RLS 启用状态 | READ |
| `list_available_extensions` | 可安装扩展 | READ |
| `get_cron_job_history` | pg_cron 执行历史 | READ |
| `get_index_stats` | 单索引使用统计 | READ |
| `get_vector_index_stats` | 向量索引使用统计 | READ |
| `explain_query` | EXPLAIN（可选 ANALYZE） | READ |

7 个工具改变状态（`WRITE`）：`execute_sql`、`generate_typescript_types`、
`rebuild_hooks`、`delete_auth_user`、`create_auth_user`、`update_auth_user`、
`update_storage_config`。上游工具不带
`confirm` 参数，因此没有工具归入 DANGEROUS——默认行为与 TypeScript 服务器完全一致。
需要显式二次确认的运维方可加 `confirm` guardrail 规则（见配置），不改变工具签名。

### execute_sql 通道与加固函数

`execute_sql` 以 service-role 密钥调用
`public.execute_sql(query, read_only)` RPC。仓库附带加固版函数定义
`sql/mcp-execute-sql.sql`（仅 service_role 可调用、库内 `read_only` 语句白名单、首关键词
分发、授权收敛）。首次部署：

经云管理通道（如 postgres-meta `/pg/query`）部署一次即可；服务器启动期会探测。

RPC 函数缺失时启动期仅告警提示；请经管理通道部署一次该定义以启用 SQL 通道
（0.4.0 已随直连移除自动建函数）。

## 使用指南

### 前置条件

- Python 3.10+ 与 [uv](https://docs.astral.sh/uv/)
- 运行中的 RDS Supabase（或自建 Supabase）实例
- anon 密钥；无直连时执行 SQL 需 service-role 密钥
- 直连数据库不支持（0.4.0）；service-role 密钥是唯一特权通道
- 可选：PATH 中的 Supabase CLI（`generate_typescript_types`）

### 安装

```bash
# uvx（无需检出）
uvx --from git+https://github.com/huaweicloud/rds-supabase-fullstack \
  --subdirectory server/mcp_server_rds_supabase \
  mcp-server-huaweicloud-rds-supabase

# 从检出目录 pip 安装
pip install ./server/mcp_server_rds_supabase
```

## 配置

### 环境变量

| 变量 | 必需 | 说明 |
|---|---|---|
| `SUPABASE_URL` | 是 | Supabase 网关基础 URL |
| `SUPABASE_ANON_KEY` | 是 | 匿名密钥 |
| `SUPABASE_SERVICE_ROLE_KEY` | 否 | service-role 密钥；启用 RPC SQL 通道 |
| `SUPABASE_AUTH_JWT_SECRET` | 否 | JWT secret（`verify_jwt_secret` 检查） |
| `RDS_SUPABASE_WORKSPACE_PATH` | 否 | 文件输出的工作区根（默认 cwd） |
| `RDS_SUPABASE_TOOLS_CONFIG` | 否 | `{"enabledTools": [...]}` JSON 白名单路径 |
| `HUAWEICLOUD_MCP_READ_ONLY` | 否 | `true` 拦截全部 WRITE 工具 |
| `HUAWEICLOUD_MCP_GUARDRAILS_CONFIG` | 否 | YAML guardrail 规则（block / confirm / warn） |
| `HUAWEICLOUD_MCP_PROTECTED_IDS` | 否 | 逗号分隔保护资源 ID |
| `HUAWEICLOUD_MCP_PROTECTED_NAMES` | 否 | 逗号分隔保护名称 |
| `HUAWEICLOUD_MCP_PROTECTED_TAGS` | 否 | 逗号分隔保护标签 |
| `HUAWEICLOUD_MCP_AUDIT_FILE` | 否 | JSONL 审计文件（审计恒写 stderr） |
| `MCP_SERVER_HOST` / `MCP_SERVER_PORT` | 否 | Streamable HTTP 监听（默认 0.0.0.0:8000） |

说明：

- 未配置 `SUPABASE_SERVICE_ROLE_KEY` 时，SQL 类工具返回配置错误；
  存储/公开化列表工具报告直连不支持（RPC 改造待做）；
  auth 用户工具经 auth admin API（仅需 service-role 密钥）。
- 护栏中间件会对输出中类密钥键名/值做脱敏（共享核安全属性，不可关闭）。
- `confirm` 规则示例——对每次 `execute_sql` 执行要求确认，工具签名不变：

```yaml
rules:
  - id: confirm-execute-sql
    action: confirm
    message: "Review the SQL statement before executing it."
    match:
      tools: ["execute_sql"]
```

### 凭证安全

密钥只经环境变量传入；严禁粘贴到 issue、日志或文档。泄露处置见仓库 SECURITY.md。

## 以 UVX 启动 Streamable HTTP

```bash
MCP_SERVER_HOST=0.0.0.0 MCP_SERVER_PORT=8000 \
uvx --from git+https://github.com/huaweicloud/rds-supabase-fullstack \
  --subdirectory server/mcp_server_rds_supabase \
  mcp-server-huaweicloud-rds-supabase -t streamable-http
```

端点为 `/mcp`。上游 TypeScript 的 HTTP 鉴权中间件（JWT bearer、角色权限、CORS、限流）
不在本移植范围内——stdio 是主传输；HTTP 模式请自行在网络层防护。

## 示例

先摸底 schema，再核查 RLS 状态：

1. `list_tables` → 发现 `public.students`
2. `get_rls_status` → 检查 RLS 是否启用
3. `get_advisors`（`type="security"`）→ 查看体检问题
4. `execute_sql`（`read_only=true`）→ 进一步 SELECT 排查

## 客户端兼容性

| 客户端 | 传输 | 说明 |
|---|---|---|
| 任意 MCP 客户端（Claude Code、opencode、AgentArts 等） | stdio | 主模式 |
| HTTP 客户端 | Streamable HTTP | 端点 `/mcp`；需网络层鉴权 |

## 权限

- 只读操作：anon 密钥 + RPC 通道所需 service-role 密钥。
- 写操作（8 个 WRITE 工具）：service-role 密钥或直连；巡检类 Agent 建议
  `HUAWEICLOUD_MCP_READ_ONLY=true`。
- 仅需 service-role 密钥（RPC + auth admin API 双通道）。

## 开发、测试与发布

```bash
uv sync --frozen --all-packages --all-groups
uv run --package mcp-server-huaweicloud-rds-supabase ruff check server/mcp_server_rds_supabase/src server/mcp_server_rds_supabase/tests
(cd server/mcp_server_rds_supabase && uv run --package mcp-server-huaweicloud-rds-supabase mypy src)
uv run --package mcp-server-huaweicloud-rds-supabase pytest server/mcp_server_rds_supabase/tests
uv build --package huaweicloud-mcp-core && uv build --package mcp-server-huaweicloud-rds-supabase
```

241 个测试，覆盖率门槛 90%（当前 94%）。端到端验证证据见仓库根 `docs/validation/`。

## 贡献与支持

见仓库根 CONTRIBUTING.md。安全问题按 SECURITY.md 私密上报；严禁在 issue 中粘贴密钥。

## 许可证

Apache License 2.0。Python 实现衍生自 MIT 许可的上游 `rds-supabase-mcp`（HenkDz 及
贡献者）；见 NOTICE。
