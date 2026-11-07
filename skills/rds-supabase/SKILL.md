---
name: rds-supabase
description: '华为云 RDS Supabase 平台开发技能（自建 Supabase 栈：Kong 网关、PostgREST、GoTrue 认证、Storage、Realtime、pgvector）。Use when：使用 supabase-js / @supabase/ssr 客户端库或 Next.js、React、SvelteKit、Astro、Remix 集成；认证问题（login、logout、sessions、JWT、cookies、getSession、getUser、RLS）；schema 变更与 init.sql 部署；REST/Data API 行为异常（permission denied、schema cache、42501、超时、表不可见）；Postgres 错误与性能问题（慢查询、索引、连接、锁）；Storage 故障、Realtime 断连；向量检索；服务端计算与定时任务。不适用于：MCP 服务器操作与实例管理（rds-supabase-mcp）、SQL 与 schema 质量规则（rds-supabase-postgres-best-practices）。'
license: MIT
metadata:
  version: "0.2.1"
  author: fitz-liujian
  derived-from: "supabase/agent-skills@c9be0e9 (MIT)"
---

# 华为云 RDS Supabase 开发

## 概述

本平台是运行在华为云 RDS PostgreSQL 上的自建 Supabase 栈：应用端通过 Kong 网关访问 PostgREST 数据 API、GoTrue 认证、Storage 与 Realtime，后端逻辑以数据库层定义（表结构、授权、RLS 策略、函数）为主。开发纪律：**组件版本以部署内实测为准，改后必验证，先定位层再修复。**

## 技能路由

| 任务 | 使用 |
|---|---|
| 客户端集成、认证排查、Data API 行为、调试、FunctionGraph | 本技能 |
| MCP 服务器操作、init.sql 五步部署规程、用户与存储管理 | `rds-supabase-mcp` 技能 |
| SQL 编写与 schema 设计质量、慢查询/索引/锁优化 | `rds-supabase-postgres-best-practices` 技能 |
| FunctionGraph 工作流编排 | 华为云 FunctionGraph 官方文档（专用技能规划中） |

## 核心原则

**1. 组件版本以部署内实测为准。** 组件版本由部署方冻结，行为可能与最新文档不一致。实施平台功能前用 MCP `execute_sql` 确认（`select version()`、`pg_extension`）；涉及栈升级时检查 `https://supabase.com/changelog.md` 中的 self-hosted 条目（重点：网关与 PG 大版本变更）。

**2. 改后必验证。** 任何修复后必须运行测试查询确认生效；未经验证的修复视为未完成。验证通道：MCP `execute_sql` 与结构查询工具。

**3. 错误恢复不循环。** 同一方法失败 2-3 次即停止换路。按层排查：数据库（`pg_stat_activity`）→ 服务容器日志（Kong / PostgREST / GoTrue / Realtime）→ RDS 控制台日志。

**4. 表暴露是两层机制。** 表能否经 REST API 访问由 GRANT 决定；能访问哪些行由 RLS 决定。默认权限自检：

```sql
select * from pg_default_acl;

-- 需要停止新表自动暴露时：
alter default privileges for role postgres in schema public
  revoke all on tables from anon, authenticated, service_role;
```

**5. 暴露 schema 中的表必须全部启用 RLS。** 暴露 schema 指列入 PostgREST `db-schemas` 配置的 schema（默认 public）。启用后按真实访问模型编写策略，不要对所有表套用同一身份谓词。

**6. 安全清单。** 凡涉及认证、RLS、视图、存储或用户数据的任务，逐条过检：

- **认证与会话**
  - 禁止用 `user_metadata`（`raw_user_meta_data`）做授权判定：该字段用户可自行修改且会进入 JWT。授权数据放 `app_metadata`（`raw_app_meta_data`）。
  - 删除用户不会使已签发的 JWT 失效：先登出或吊销会话（经 MCP auth 工具组，走 GoTrue admin API）；敏感操作建议校验 `auth.sessions`。
  - JWT claims 在令牌刷新前可能不是最新值。
- **API 密钥**
  - `service_role` 密钥禁止进入前端代码或客户端环境变量。本部署中它是静态、不过期的 JWT，经 Kong 网关校验，持有者绕过全部 RLS；只允许存在于服务端凭据存储（MCP 服务器环境、FunctionGraph 函数环境变量）。前端只用 `anon` 密钥；Next.js 中任何 `NEXT_PUBLIC_` 前缀变量都会进入浏览器。泄露处置为运维级流程（轮换 JWT secret 并同步全部服务），按严重事故处理。
  - MCP 两层只读：`execute_sql` 的 `read_only` 参数限制单次语句类型（白名单 SELECT、WITH、VALUES、TABLE、EXPLAIN）；`HUAWEICLOUD_MCP_READ_ONLY` 在服务器层拦截全部写工具。
- **RLS 与特权代码**（示例见 best-practices 技能 `security-rls-basics`、`security-rls-performance`）
  - 视图默认绕过 RLS：PG17 一律 `create view ... with (security_invoker = true)`。
  - UPDATE 依赖 SELECT 策略：没有 SELECT 策略时更新静默返回 0 行。
  - 策略目标角色用 `TO` 子句指定；`TO authenticated` 单独使用是只认证不授权（BOLA/IDOR），必须叠加所有权谓词——身份判定用 `request.jwt.claims`（本部署无 `auth.uid()`，见 best-practices 技能 `rds-jwt-claims-rls`）。
  - UPDATE 策略必须同时写 `USING` 与 `WITH CHECK`，否则用户可把行的归属改给他人。
  - `security definer` 函数以创建者权限运行并绕过其所访问表的 RLS：禁止用它"解决"权限报错；优先 `security invoker`。
  - public schema 中的 `security definer` 函数默认对所有角色可调用（PG 对新函数默认向 PUBLIC 授予 EXECUTE）。确需使用时：放入未暴露 schema、函数体内显式校验调用者身份、回收 EXECUTE；变更后运行 MCP `get_advisors`（type=security）。
- **存储**
  - Storage upsert 的桶策略需同时具备 INSERT、SELECT、UPDATE，只授 INSERT 时替换上传静默失败。本部署对象后端尚未接入凭证，对象级操作暂不可用；桶配置经 MCP storage 工具组，后端接入后本条全量生效。
- **供应链**
  - 安装 supabase 客户端包时锁定版本并提交 lockfile，审计依赖清单。

## 自研 MCP 服务器

平台操作经 `mcp-server-huaweicloud-rds-supabase`（38 工具）。**以工具注册表为准，不凭记忆猜测工具名或参数。**

| 分组 | 代表工具 |
|---|---|
| SQL 执行 | execute_sql（整批单事务，失败自动回滚；read_only 白名单） |
| 结构查询 | list_tables、list_table_columns、list_indexes、list_constraints、get_function_definition |
| 安全检查 | get_rls_status、list_rls_policies、get_advisors |
| 用户管理 | list/get/create/update/delete_auth_user（GoTrue admin API） |
| 运行排查 | get_database_connections、explain_query |
| 扩展 | list_extensions、list_available_extensions |
| 存储与平台 | get_storage_config、update_storage_config、verify_jwt_secret |

完整清单、参数确认规则与部署流程见 `rds-supabase-mcp` 技能。

连接排查（按序）：

1. 网关可达性：`curl -so /dev/null -w "%{http_code}" <SUPABASE_URL>/rest/v1/`——返回 401 或 200 均说明网关在服务。
2. 客户端配置：核对 `SUPABASE_URL` 与密钥。
3. 工具不可见：检查 MCP 客户端配置与服务器进程。
4. 权限报错：先确认是否被两层只读拦截，再验证 service_role 密钥有效性。

## 文档访问

实现平台功能前先查文档，按优先级：

1. 本技能与 `rds-supabase-postgres-best-practices` 技能的 references
2. supabase.com 文档页 URL 加 `.md` 后缀直取（对 PostgREST、GoTrue、Realtime、Storage 组件行为有效；忽略其中 Dashboard 操作）
3. Web search

## schema 变更与部署

变更脚本由 Git 目录管理；执行一律走 MCP `execute_sql`：整批单事务，任一语句失败整批自动回滚，不存在部分应用状态。

红线：

- 本部署无迁移历史表；平台 `public.migrations` 由发布流程管理，禁止读写，禁止模仿 supabase_migrations 建表。
- 结构化迁移系统将由后续 supabase mcp 版本提供。

五步流程（预检 → 审查 → 部署 → 授权暴露 → 查询确认）的完整规程与 init.sql 编写规范见 `rds-supabase-mcp` 技能。要点：破坏性语句逐条人工确认；对外表启用 RLS 并配策略；最小授权；GRANT 后 `notify pgrst, 'reload schema'`；以查询结果为准。提交前 `get_advisors`（security 与 performance）问题清零。

## 调试工作流

收到平台错误先按症状定位层，再修复：

| 症状 | 首查 |
|---|---|
| PostgREST `42501` permission denied | 报错信息自带精确 GRANT 提示，直接按提示补授权 |
| 接口返回空结果但数据存在 | RLS 策略（`get_rls_status` + `list_rls_policies`）；注意 UPDATE 无 SELECT 策略时静默 0 行 |
| `prepared statement "..." does not exist` | 连接池 transaction 模式与预备语句冲突（best-practices `conn-prepared-statements`） |
| 新建表 403 / 不可见 | 先查 GRANT（两层机制），再查 RLS |
| 慢查询 / 超时 | 数据库层：`explain (analyze, buffers)`；pg_stat_statements 需经 RDS 参数模板启用（best-practices `rds-parameter-template`）；Kong 网关约 60 秒超时 |
| 服务级错误 | Kong / PostgREST / GoTrue / Realtime 容器日志（部署方运维通道）→ RDS 控制台日志 |

组件错误码语义可查 supabase 调试文档（忽略云日志部分）。

## 服务端计算与定时任务

本平台无 Edge Functions。服务端计算与 Webhook 处理使用**华为云 FunctionGraph 工作流**（专用技能规划中，当前参考华为云 FunctionGraph 官方文档）。定时任务使用 pg_cron 在数据库内调度（编写规范见 best-practices 技能 `rds-scheduled-jobs`；实例未启用时经 RDS 参数模板配置，见 `rds-parameter-template`）。数据库侧出站 HTTP 使用 pg_net。

## 向量检索

pgvector 已安装。向量索引用 MCP `list_vector_indexes`、`get_index_stats`、`get_vector_index_stats` 查看；索引类型选型遵循 best-practices 技能的 `query-index-types` 规则。

## 参考指南

- **技能反馈** → [references/skill-feedback.md](references/skill-feedback.md)。**必须阅读场景**：用户报告本技能给出错误指导或缺少信息。
