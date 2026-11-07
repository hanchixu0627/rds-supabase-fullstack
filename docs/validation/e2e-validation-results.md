# 端到端验证报告：Python 版与 TypeScript 版双服务器比对

- 日期：2026-11-04
- 机器可读证据：`live-validation-results.json`（由 `run_e2e.py` 生成，可复跑）
- 比对对象：
  - **TS**：`rds-supabase-mcp`（bun 直跑 `src/index.ts`，版本 0.1.0）
  - **PY**：本仓 `mcp_server_huaweicloud_rds_supabase`（uv 运行，版本 0.1.0，服务器名 `huaweicloud-rds-supabase`）
- 目标实例：华为云 RDS Supabase（Kong 网关），stdio 双进程同实例并发调用
- 凭证：仅经环境变量传入；证据中不含任何密钥

## 结论

| 维度 | 结果 |
|---|---|
| tools/list：43 个工具名与注册顺序 | **一致**（与 TS 上游顺序完全相同） |
| 工具 description 首行（上游原文逐字） | **43/43 一致** |
| inputSchema（属性名/required） | **43/43 一致** |
| 参数 description | **43/43 一致** |
| 工具调用矩阵（43 项：30 exact + 2 structural + 11 error-message） | **43/43 PASS** |
| Python 护栏：READ_ONLY 拦 8 个 WRITE、放行 READ | **通过** |
| 总判定 | **E2E PASS** |

## 调用矩阵说明

- **exact（30 项）**：双侧 JSON 载荷深度相等。覆盖：catalog 全家（tables/extensions/migrations/
  columns/indexes/constraints/foreign_keys/rls_policies/triggers/functions/definitions/
  rls_status/available_extensions）、execute_sql（`SELECT 1`、`SELECT count(*)`）、
  advisors 双类型、cron/vector/edge/logs/storage_config/explain/rebuild_hooks/
  generate_types 的结构化失败路径、update_storage_config 结构化失败路径等。
- **structural（2 项）**：`get_database_connections`（pid/时间戳易变）、`get_database_stats`
  （计数器随时间变化）——比较键集与行数结构。
  注：本实例为 PG17 形态，`pg_stat_bgwriter` 无 `checkpoints_timed` 列，双侧同报
  `SQL Error (42703): column "checkpoints_timed" does not exist`（消息逐字一致，经
  错误消息等价路径判定 PASS）。
- **error-message（11 项）**：无 `DATABASE_URL` 时 9 个直连工具（auth 五件套、storage 两件、
  publications、apply_migration）+ `execute_sql` 库内 `read_only` 白名单拒绝（42501）。
  双侧核心错误消息逐字一致。

## 已知表示层差异（行为等价，非能力差异）

1. **错误信封**：TS 以 `isError: true` + 文本 `Error executing tool <name>: <消息>` 报错；
   Python 按共享核规范返回结构化信封 `{"error": {code, message, hint}}`（12 项带
   representation_note）。**核心消息文本逐字一致**。
2. **输入运行时校验**：TS 的 zod 字段校验（如 email 格式）未按运行时行为移植（以类型签名
   + 测试替代）；矩阵使用合法入参验证公共路径。zod 拒绝分支（如非法 email）Python 会走到
   后续检查——文档化为既定偏差。
3. **输出脱敏**：共享核对输出中类密钥键/值自动脱敏（`***`），TS 无此行为；本实例表结构
   无命中列，比对不受影响。
4. **HTTP 鉴权中间件**：TS 的 http 模式（JWT/CORS/限流）不在移植范围；stdio 为主传输。
5. **自动建函数**：Python 版内嵌 v4.1 加固定义（接口与 v1 相同；`read_only` 在库内真实生效），
   本实例已预部署同版本，双侧行为一致。
6. **大整数精度**：>2^53 的 bigint 在 TS JSON 路径经 JS double 可能损失精度，Python 精确保留；
   本实例数据未命中。

## 护栏验证（Python 侧）

- `HUAWEICLOUD_MCP_READ_ONLY=true`：`execute_sql` 被拦（`MCP_READ_ONLY` 信封），
  `list_tables` 正常返回。
- 审计 JSONL 恒写 stderr（证据见运行日志；工具调用事件含 tool/risk/decision/params）。

## 复跑

```bash
export SUPABASE_URL=... SUPABASE_ANON_KEY=... SUPABASE_SERVICE_ROLE_KEY=...
python3 docs/validation/run_e2e.py \
  --ts-entry <path-to-rds-supabase-mcp>/src/index.ts \
  --py-package-dir server/mcp_server_rds_supabase
```

另：`skills/.../scripts/smoke.py --skip-cloud -- <server>` 提供无实例冒烟（握手 + 43 工具
顺序 + 只读拦截），CI 中执行。
