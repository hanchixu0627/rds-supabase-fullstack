---
name: rds-supabase-postgres-best-practices
description: 'Postgres 最佳实践规则库（华为云 RDS Supabase 部署）。编写或修改任何存入 Postgres 数据库的内容之前加载：建表与改表（列类型选择）、schema 设计、RLS 策略、索引、触发器、数据库函数、主键与 UUID 选型、批量导入、数据恢复。诊断场景同样加载：慢查询、高 CPU、超时、EXPLAIN 执行计划、连接耗尽、连接池、锁等待、死锁、表膨胀、N+1 查询、OFFSET 深分页、upsert、外键索引缺失、JSONB 查询慢、全文检索、定时任务（pg_cron）、跨用户或跨租户数据可见。华为云 RDS 部署专属：JWT claims 身份判定（request.jwt.claims）、参数模板（ALTER SYSTEM 无权限）、身份辅助函数、PostgREST 暴露面。单列变更与单条查询同样适用。'
license: MIT
metadata:
  version: "0.3.0"
  author: fitz-liujian
  derived-from: "supabase/agent-skills@c9be0e9 (MIT)"
---

# 华为云 RDS Supabase Postgres 最佳实践

## 概述

源自 Supabase 维护的通用 Postgres 规则库（"for Postgres running anywhere"），针对华为云 RDS Supabase 自建部署适配（身份判定、参数通道、扩展可用性），并新增 rds- 分区承载部署专属规则。每条规则含 Incorrect/Correct 对照与量化收益。**先按下方索引定位规则文件，再按规则修改 SQL。**

## 何时应用

- 编写 SQL 查询、设计或修改 schema（建表、改列、选型）
- 实现索引、优化查询、排查性能问题
- 编写或优化 RLS 策略
- 配置连接池、连接数、超时参数
- 排查锁等待、死锁、表膨胀
- 涉及华为云 RDS 部署形态的参数、身份、暴露面问题

不适用于：MCP 服务器操作与实例管理（`rds-supabase-mcp` 技能）、客户端集成与平台调试（`rds-supabase` 技能）。

## 症状与任务索引

| 症状 / 任务 | 规则文件（references/ 下） |
|---|---|
| 慢查询、WHERE/JOIN 列缺索引 | `query-missing-indexes.md` |
| 多列条件过滤 | `query-composite-indexes.md` |
| 索引类型选型（JSONB/数组→GIN、几何/范围→GiST、时序大表→BRIN） | `query-index-types.md` |
| 只查询少量列、想避免回表 | `query-covering-indexes.md` |
| 查询恒带同一过滤条件 | `query-partial-indexes.md` |
| 连接耗尽、高并发、是否池化 | `conn-pooling.md` |
| max_connections、work_mem 预算 | `conn-limits.md` |
| `prepared statement "..." does not exist` | `conn-prepared-statements.md` |
| 空闲连接堆积 | `conn-idle-timeout.md` |
| 多租户数据隔离、RLS 入门 | `security-rls-basics.md` |
| RLS 策略导致查询变慢 | `security-rls-performance.md` |
| 最小授权、角色权限划分 | `security-privileges.md` |
| 主键选型（serial vs identity、UUID 碎片化） | `schema-primary-keys.md` |
| 迁移中加约束报 `42601` | `schema-constraints.md` |
| 列类型选择（text/timestamptz/numeric/bool） | `schema-data-types.md` |
| JOIN 慢、`on delete cascade` 慢 | `schema-foreign-key-indexes.md` |
| 标识符大小写问题 | `schema-lowercase-identifiers.md` |
| 大表（亿级行）清理与裁剪 | `schema-partitioning.md` |
| 循环内逐条查询（N+1） | `data-n-plus-one.md` |
| 批量插入慢 | `data-batch-inserts.md` |
| 深分页越来越慢（OFFSET） | `data-pagination.md` |
| 先查后插竞态、insert-or-update | `data-upsert.md` |
| 锁争用、事务里调外部 API | `lock-short-transactions.md` |
| 多 worker 队列互相阻塞 | `lock-skip-locked.md` |
| 死锁 | `lock-deadlock-prevention.md` |
| 应用级互斥（锁表行做锁） | `lock-advisory.md` |
| 找出最耗资源的查询 | `monitor-pg-stat-statements.md` |
| 读不懂执行计划 | `monitor-explain-analyze.md` |
| 统计信息过期、计划漂移 | `monitor-vacuum-analyze.md` |
| `LIKE '%x%'` 慢、需要排序的搜索 | `advanced-full-text-search.md` |
| JSONB 包含查询慢 | `advanced-jsonb-indexing.md` |
| RLS 身份判定（auth.uid() 不存在） | `rds-jwt-claims-rls.md` |
| `ALTER SYSTEM` 报 permission denied | `rds-parameter-template.md` |
| 部署 auth.uid() 等价辅助函数 | `rds-auth-helpers.md` |
| 定时任务、cron 调度、时区陷阱 | `rds-scheduled-jobs.md` |

也可直接检索：`grep -il "关键词" references/`（如 `grep -il "deadlock" references/`）。

## 规则分区（按影响降序）

| 优先级 | 分区 | 影响 | 前缀 |
|---|---|---|---|
| 1 | 查询性能 | CRITICAL | `query-` |
| 2 | 连接管理 | CRITICAL | `conn-` |
| 3 | 安全与 RLS | CRITICAL | `security-` |
| 4 | schema 设计 | HIGH | `schema-` |
| 5 | 并发与锁 | MEDIUM-HIGH | `lock-` |
| 6 | 数据访问模式 | MEDIUM | `data-` |
| 7 | 监控与诊断 | LOW-MEDIUM | `monitor-` |
| 8 | 高级特性 | LOW | `advanced-` |
| 9 | 华为云 RDS 部署 | CRITICAL | `rds-` |

## 使用方式

每条规则包含：问题说明、Incorrect 反模式、Correct 正确模式（均含成因注释与量化收益）、参考链接。新增规则遵循 `references/_contributing.md` 的格式契约。

## 参考文档

- https://www.postgresql.org/docs/current/
- https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- https://support.huaweicloud.com/rds/index.html
