# 技能行为评估记录（RED 基线 / GREEN 对照）

- 日期：2026-11-07（v0.2.0 提交 c500f08 后）
- 方法：每技能 3 场景；RED = 无技能基线代理（仅环境上下文）；GREEN = 加载 SKILL.md 的代理。均为独立新鲜上下文。
- 环境（两组相同）：华为云 RDS PG17 + 自建 Supabase 栈（Kong/PostgREST/GoTrue/Storage/Realtime）

## rds-supabase

| 场景 | 用户问题 | RED 基线行为 | GREEN（加载技能） | 判定 |
|---|---|---|---|---|
| S1 | 登录后 REST 返回空数组，数据存在 | 给出 `(request.jwt.claims::jsonb->>'sub')::uuid` —— **裸引用 GUC，SQL 不可执行**；无工具通道；无验证步骤 | `list_rls_policies` 工具 + `(select current_setting('request.jwt.claims', true)::jsonb ->> 'sub')` 正确写法（含 InitPlan 包装）+ 改后验证 | RED 失败 → GREEN 通过 |
| S2 | SQL 建表后 anon 403 | 第一动作查 `relrowsecurity`（**RLS 优先，方向颠倒**：403=GRANT 层） | 第一查 `has_table_privilege('anon',...)`，GRANT + `notify pgrst, 'reload schema'`，随后补 RLS | RED 失败 → GREEN 通过 |
| S3 | 每日定时清理任务 | **首选 pg_cron（本部署未装，执行必败）**，FunctionGraph 仅作退路 | 直接选 FunctionGraph 定时触发器 + service_role 仅存函数环境变量 | RED 失败 → GREEN 通过 |

## rds-supabase-postgres-best-practices

| 场景 | 用户问题 | RED 基线行为 | GREEN（加载技能） | 判定 |
|---|---|---|---|---|
| S4 | OFFSET 深分页变慢 | keyset 建议正确（通用知识），无规则引用 | keyset + 多列游标含全部排序列 + 命中 `data-pagination.md` | 基线强，GREEN 增强（可追溯） |
| S5 | RLS 策略致全表查询变慢 | `(request.jwt.claims)->>'customer_id'` —— **裸引用 GUC，SQL 不可执行** | `(select current_setting('request.jwt.claims', true)::jsonb->>'sub') = user_id` + 策略列索引 + 命中 `security-rls-performance.md` | RED 失败 → GREEN 通过 |
| S6 | `alter system` 报 permission denied | 基线即答对（控制台参数模板；环境上下文可推断） | 命中 `rds-parameter-template.md` + `pg_settings.pending_restart` 验证闭环 | 基线强，GREEN 增强（验证步骤） |

## 结论

1. **GREEN 6/6 通过**：正确 SQL 通道（current_setting 包装）、正确排查顺序（GRANT 先于 RLS）、正确选型（FunctionGraph）、检索命中（3 个目标规则文件全部命中）、验证闭环。
2. **RED 4/6 决定性失败**：S1/S5 的裸 GUC 引用 SQL 不可执行（正是 `rds-jwt-claims-rls` 规则防御的形态）；S2 方向颠倒；S3 首选不可用扩展。S4/S6 基线本身正确（如实记录：区分度低，技能价值为标准化与可追溯性）。
3. **无需 REFACTOR**：GREEN 无失败，未发现新漏洞。
4. 后续建议：技能内容变更时重跑本评估；新增规则时补充对应场景。


## 勘误（2026-11-07）

pg_cron 为平台能力，此前"本部署未装，执行必败"仅为当前测试实例状态，非平台形态限制。据此修正：S3 的 RED 判定不成立（pg_cron 即正确首选）；技能 v0.2.1/v0.3.0 已将定时任务路由修正为 pg_cron（含新增 `rds-scheduled-jobs` 规则），FunctionGraph 仅承接服务端计算与 Webhook。待具备 pg_cron 的环境复测。
