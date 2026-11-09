---
name: rds-supabase-mcp
description: '华为云 RDS Supabase 管理技能：服务 Web 全栈开发流程，管理部署在华为云 RDS PostgreSQL 上的自建 Supabase 平台（Kong 网关、PostgREST、GoTrue、Storage、Realtime）。Web 应用开发中，后端代码以 init.sql 迁移脚本（DDL、GRANT 等初始化 SQL）形式存在，经本技能部署为数据库层定义，前端经 REST API 直接消费。Use when：RDS Supabase 实例创建完成或选定后，动态安装本 MCP 服务器（凭网关 URL 与 API Key，见 references/install.md）；开发中执行后端代码 init.sql 迁移脚本（建表、授权、RLS、函数）；查询数据库结构与数据；管理登录用户；配置存储桶；检查行级安全（RLS）与安全建议；排查连接与执行计划。本 MCP 服务器基于 HenkDz/selfhosted-supabase-mcp 改进。平台客户端集成见 rds-supabase 技能；SQL 与 schema 质量规则见 rds-supabase-postgres-best-practices 技能。'
license: MIT
metadata:
  tags: [huawei-cloud, rds, supabase, postgresql, mcp, database, baas]
  version: "2.6.0"
---

# 华为云 RDS Supabase 管理

## 概述

华为云 RDS Supabase 是运行在华为云 RDS PostgreSQL 之上的自建 Supabase 平台。Supabase 提供后端即服务（BaaS）能力：Kong 网关统一入口，PostgREST 将数据库表发布为 REST API，GoTrue 负责用户认证，Storage 与 Realtime 开箱即用，应用端无需自建后端服务。

在 Web 全栈开发流程中，本技能承担后端环节，按两个阶段展开。**实例接入**：RDS Supabase 实例由流程动态创建或选定，实例就绪后配置信息（网关 URL 与 API Key）方可获得，此时按 references/install.md 一句话完成 MCP 服务器的动态安装。**后端开发**：Web 应用的后端代码以 init.sql 迁移脚本（DDL、GRANT 等初始化 SQL）形式组织，经 `execute_sql` 部署为数据库层的定义与配置（表结构、授权、行级安全策略、函数），前端经 REST API 直接消费。

自建 Supabase 不提供云平台控制台，日常管理缺少工具支持。本 MCP 服务器（`mcp-server-huaweicloud-rds-supabase`）基于 HenkDz/selfhosted-supabase-mcp 改进，将数据库结构查询、SQL 执行、用户管理、存储配置、安全检查等管理能力封装为 MCP 工具，供 AI 助手调用。相对原版本的主要整改：

- `execute_sql` 采用加固后的数据库函数：仅 service_role 可调用；`read_only` 模式在数据库层面强制只读白名单
- 移除直连数据库通道：SQL 经由 PostgREST RPC 执行，用户管理经由 GoTrue 管理 API 完成
- 用户管理改用官方管理 API：密码哈希与邮箱确认由 GoTrue 统一处理，不再直接写 `auth.users` 表
- 引入安全管控：工具按读/写分级；支持只读模式、操作拦截与二次确认规则、调用审计日志、敏感信息脱敏
- 移除不适配当前部署形态的工具（迁移记录、Edge Functions 等）

完整链路：Web 全栈开发流程（实例创建 / 选定）→ 动态安装（references/install.md）→ AI 助手 → MCP 工具 → service 层 → client（PostgREST RPC / GoTrue 管理 API）。

典型用例：

1. 实例接入：实例创建或选定后，凭网关 URL 与 API Key 按 references/install.md 动态安装 → `get_project_url` 验证
2. 了解现状：`list_tables` → `list_table_columns` → `get_rls_status`
3. 部署后端定义：AI 生成 init.sql（建表、授权、RLS 策略、函数）→ `execute_sql` 执行 → 查询确认
4. 安全检查：`get_advisors` + `get_rls_status` 核查对外表的权限与 RLS 覆盖
5. 数据排查：`execute_sql`（`read_only=true`）逐层查询
6. 用户管理：`list/get/create/update/delete_auth_user`

## 适用范围

**触发条件**（满足任一即启用本技能）：

1. Web 全栈开发流程中，RDS Supabase 实例创建完成或选定，需要动态安装本 MCP 服务器（references/install.md）
2. Web 应用开发中执行后端代码：init.sql 迁移脚本（DDL、GRANT 等初始化 SQL）的编写与部署
3. 查询或修改 RDS Supabase 实例的数据库结构与数据
4. 管理平台登录用户
5. 检查行级安全（RLS）、处理安全或性能建议
6. 排查平台运行问题（连接、执行计划、扩展）

**边界**：

| 任务 | 归属 |
|---|---|
| 实例开通、续费、规格变更、备份策略 | 云平台控制台（本 MCP 不涉及） |
| MCP 服务器动态安装与配置（实例创建/选定后） | references/install.md（一句话动态安装）；references/mcp-installation-guide.md（完整指南） |
| `public.migrations` 表 | 平台内部对象：不读、不写、不依赖 |

## 前置条件

1. RDS Supabase 实例已创建完成或选定，三项配置信息已从开发流程获得：`SUPABASE_URL`（网关地址）、`SUPABASE_ANON_KEY`、`SUPABASE_SERVICE_ROLE_KEY`（SQL 执行与用户管理所必需）；据此按 references/install.md 动态安装本 MCP 服务器
2. 数据库已部署 `sql/mcp-execute-sql.sql`：创建受限的 `execute_sql` 函数（仅 service_role 可调用，`read_only` 语句白名单）
3. 仅需只读访问时，建议设置 `HUAWEICLOUD_MCP_READ_ONLY=true`

## 工作流

### 实例接入（动态安装）

Web 全栈开发流程中实例创建或选定后执行一次：从流程获得 `SUPABASE_URL`、`SUPABASE_ANON_KEY`、`SUPABASE_SERVICE_ROLE_KEY` → 按 references/install.md 写入客户端 MCP 配置并重载 → `get_project_url` 返回值与网关地址一致、`list_tables` 正常应答，即接入完成，进入开发工作流。

### 通用流程

先查询现状（`list_tables`、`list_table_columns`、`get_rls_status`），再执行写操作；每次写操作后查询确认结果。

### 部署后端定义（init.sql，五步）

`execute_sql` 的主要功能是执行 SQL；执行 init.sql（DDL 等迁移脚本）部署后端定义是其典型用法。流程如下：

```
init.sql → ① 预检 → ② 审查 → ③ 部署 → ④ 授权暴露 → ⑤ 查询确认
```

**① 预检（核对现状）**

- `list_tables` / `list_indexes` / `list_table_columns`：确认目标表、索引是否已存在，结构是否冲突
- `get_rls_status` / `list_rls_policies`：确认现有表的行级安全状态与策略
- 已存在的对象采用可重复执行的写法（IF NOT EXISTS、CREATE OR REPLACE），或改写为增量变更

**② 审查（四项强制检查）**

1. 可重复执行：同一脚本可多次执行——`CREATE TABLE IF NOT EXISTS`、`CREATE OR REPLACE`、`INSERT ... ON CONFLICT DO NOTHING`
2. 破坏性语句：`DROP`、`TRUNCATE`、`ALTER` 须逐条人工确认；禁止 `DROP ... CASCADE`
3. RLS 覆盖：每张对外暴露的表须启用行级安全并至少配置一条策略——仅启用而未配置策略将查询不到任何行，未启用则数据对所有角色可见（`get_advisors` 会报告）
4. 最小授权：仅向必要角色授予必要权限（如 `GRANT SELECT ON t TO anon`），避免过度授权

**③ 部署（整批单一事务）**

- `execute_sql`（`read_only=false`，默认）将整个脚本作为一批执行：同一事务内任一语句失败，整批自动回滚，不会出现部分生效的状态
- 脚本较长时拆分为多批，按依赖顺序编排（建表 → 索引 → 策略 → 授权），每批独立提交
- `CREATE DATABASE`、`ALTER SYSTEM` 等无法在事务中执行的语句，放入批次将导致执行失败
- 生产环境建议为 `execute_sql` 配置二次确认规则（见安装指南）

**④ 授权暴露**

```sql
GRANT SELECT ON public.<表名> TO anon;    -- 按需追加 INSERT/UPDATE 权限
NOTIFY pgrst, 'reload schema';            -- PostgREST 立即感知结构变更，无需重启
```

- PostgREST 仅暴露已授权的表：GRANT 后 `GET /rest/v1/<表名>`（anon key）即可访问；行级权限由 RLS 策略控制
- 未授权的表不会对外暴露

**⑤ 查询确认（以查询结果为准）**

- `list_tables` / `list_table_columns` / `list_constraints`：结构已生效
- `get_rls_status` / `list_rls_policies`：策略已生效
- `get_advisors`（type=security）：无新增问题项
- 可选：HTTP 请求 `GET /rest/v1/<表名>`，确认返回 200
- 变更是否生效，一律以查询到的实际状态为准，不依赖执行记录

### SQL 排查

`execute_sql` 传 `read_only=true`：数据库层面仅允许 SELECT、WITH、VALUES、TABLE、EXPLAIN；确认无误后再执行写操作。

### 安全检查

`get_advisors`（security/performance）→ 依据每条 issue 的 remediation 处理 → `get_rls_status` / `list_rls_policies` 复核。

### 用户管理

`list_auth_users` → `get/create/update/delete_auth_user`（官方管理 API；密码哈希与邮箱确认由 GoTrue 处理）。

## 可用工具

| 分类 | 工具 | 说明 |
|---|---|---|
| SQL 执行 | execute_sql | 执行任意 SQL；执行迁移脚本（init.sql）部署后端定义时，整批为单一事务，失败自动回滚；支持 read_only 参数 |
| 结构查询 | list_tables, list_table_columns, list_indexes, list_constraints, list_foreign_keys, list_triggers, list_database_functions, get_function_definition, get_trigger_definition | 表、列、索引、约束、外键、触发器、函数定义 |
| 安全检查 | get_rls_status, list_rls_policies, get_advisors | RLS 状态、策略明细、安全与性能建议 |
| 运行排查 | get_database_connections, explain_query | 活跃连接、执行计划 |
| 扩展 | list_extensions, list_available_extensions | 已安装 / 可安装的扩展 |
| 用户管理 | list/get/create/update/delete_auth_user | 登录用户的增删改查 |
| 存储与平台 | get_storage_config, update_storage_config, rebuild_hooks, verify_jwt_secret, get_project_url, list_cron_jobs, get_cron_job_history, list_vector_indexes, get_index_stats, get_vector_index_stats | 存储配置、平台信息、定时任务、索引统计 |
| 不可用工具（当前部署） | list_storage_buckets, list_storage_objects, list_realtime_publications, generate_typescript_types, get_database_stats, get_logs | 此部署形态下无法提供数据，调用时返回明确的错误说明；详见 README |

## 参数确认

| 项 | 确认规则 |
|---|---|
| execute_sql.sql（迁移脚本） | 须通过第②步四项检查；采用可重复执行写法；不得包含无法在事务中执行的语句 |
| execute_sql.read_only | 排查场景必须为 true；部署后端定义时为 false |
| GRANT 对象与角色 | 遵循最小授权原则；对外表与内部表分别处理 |
| 用户写操作（user_id / email） | 不可逆操作，执行前逐字核对 |

## 输出格式

部署报告（部署后端定义时输出）：

```text
【部署前】
目标对象：<表 / 函数 / 策略 / 授权清单>
预检结果：<已存在的对象与冲突，或无冲突>
风险确认：<破坏性语句 / RLS 覆盖 / 授权范围>

【部署后】
执行结果：<success, rows_affected>（失败时说明整批已回滚）
对外暴露：<GRANT 明细 + /rest/v1/<表名>>
查询确认：<结构 / RLS / advisors 结果 / HTTP 200>
```

排查与日常写操作采用简要格式：目标对象、执行的操作、读写级别、执行后的查询确认结果。

## 验证方法

详见 references/verification-method.md：五步部署的逐项验证清单、只读模式验证（`HUAWEICLOUD_MCP_READ_ONLY=true` 时写工具被拦截）、事务回滚验证（构造含错误语句的批次，事后查询确认无残留）。

## 注意事项

- `read_only`（execute_sql 参数）与 `HUAWEICLOUD_MCP_READ_ONLY`（服务器只读模式）是两层独立机制：前者限制单次调用的语句类型，后者拦截全部写工具
- 对外表未启用 RLS 会被 `get_advisors(security)` 报告（0013/0007/0008）
- `public.migrations` 为平台内部对象：不读、不写、不依赖
- Kong 网关约 60 秒超时，超长脚本应拆分为多批执行
- 工具错误统一为 `{"error": {code, message, hint}}`，依据 hint 提示修正
- 输出中符合密钥特征的值自动脱敏（显示为 `***`）
- 每次工具调用均记录审计日志至 stderr；建议配置 `HUAWEICLOUD_MCP_AUDIT_FILE` 持久留存

## 参考文档

- references/install.md（实例创建/选定后的动态安装：凭三项配置信息一句话完成接入）
- references/init-sql-guide.md（init.sql 编写规范）
- references/verification-method.md（验证方法）
- references/related-tools.md（工具分组、访问通道与错误格式）
- references/mcp-installation-guide.md（服务器安装与配置）
