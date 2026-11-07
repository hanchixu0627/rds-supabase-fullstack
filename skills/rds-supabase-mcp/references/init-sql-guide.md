# init.sql 编写规范（后端定义迁移脚本）

init.sql 是后端定义的迁移脚本（建表、授权、行级安全策略、函数等），经 MCP 的 `execute_sql` 执行部署。整批在同一个事务里：任何一条语句失败，整批自动回滚。

## 1. 可重复执行（同一脚本跑多次不报错）

| 场景 | 写法 |
|---|---|
| 建表 | `CREATE TABLE IF NOT EXISTS public.t (...)` |
| 函数/视图/触发器 | `CREATE OR REPLACE FUNCTION/POLICY` |
| 列新增 | `ALTER TABLE t ADD COLUMN IF NOT EXISTS c text` |
| 索引 | `CREATE INDEX IF NOT EXISTS i ON t (c)` |
| 种子数据 | `INSERT ... ON CONFLICT (pk) DO NOTHING` |
| 权限 | `GRANT`（天然可重复） |

## 2. 整批一个事务，失败自动回滚

- 整个脚本**一批执行**：`execute_sql("stmt1; stmt2; ...")`——任何一条失败，整批自动回滚（实测：`CREATE; INSERT; SELECT 1/0` → 全部回滚，零残留）
- 分批规则（仅超长脚本）：按依赖排序——先表、后索引/约束、再函数/触发器、再 RLS 策略、最后 GRANT + NOTIFY；**各批独立提交**
- 无法在事务里执行的语句（放进批次必然失败）：`CREATE DATABASE`、`ALTER SYSTEM`、`DROP DATABASE`、涉及其他数据库的语句

## 3. RLS 清单（每张对外表必做）

```sql
ALTER TABLE public.t ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.t FORCE ROW LEVEL SECURITY;          -- 建议：owner 也受策略约束
CREATE POLICY t_select ON public.t
    FOR SELECT TO authenticated USING (user_id = auth.uid());
```

- 无策略 + ENABLE = 全拒（安全默认）；漏 ENABLE = 裸奔（advisors 0013 会报）
- 写策略同时给 `USING`（可见性）与 `WITH CHECK`（可写性）
- 内部表（仅 service_role 用）可不暴露给 anon/authenticated

## 4. GRANT 清单（最小授权与 API 暴露）

```sql
GRANT USAGE ON SCHEMA public TO anon;                  -- 通常已具备
GRANT SELECT ON public.t TO anon;                      -- 只读对外
GRANT SELECT, INSERT, UPDATE ON public.t TO authenticated;
NOTIFY pgrst, 'reload schema';                         -- 热更新，表立即成为端点
```

- PostgREST 只暴露**有授权**的表：`GRANT SELECT` 即 `GET /rest/v1/t` 上线
- 撤回暴露：`REVOKE ... FROM anon; NOTIFY pgrst, 'reload schema';`

## 5. 部署后验证（以查询结果为准）

```sql
-- 经 MCP 目录工具回读：
--   list_tables / list_table_columns / list_constraints  → 结构落地
--   get_rls_status / list_rls_policies                  → 策略生效
--   get_advisors(type=security)                         → 无新增问题
-- HTTP：GET /rest/v1/t（anon key）→ 200
```

## 6. 命名与组织

- 对外表放 `public`；内部表放独立 schema（如 `app_internal`）且不 GRANT
- 策略命名 `<table>_<action>[_<role>]`（如 `posts_select_authenticated`）
- 脚本内对象顺序：表 → 约束/索引 → 函数 → 触发器 → RLS → GRANT → NOTIFY
