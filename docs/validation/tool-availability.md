# hw-rds-supabase-py 工具可用性清单

> 2026-11-05 更新（0.3.0）：auth 用户五件套经官方 auth admin API 改造后**转为可用**（真实例
> 全生命周期 89/89 PASS）。当前状态：**可用 31 / 不可用 7 / 已移除 5（合计原 43，现存 38）**。
> 此前 0.2.0 已移除 `apply_migration`、`list_migrations` 与边缘函数三件套；
> `generate_typescript_types` 经决策保留待改造。0.4.0 已彻底移除直连通道（DATABASE_URL/pg 代码/psycopg 依赖），
> 存储两件套与 publications 的根因更新为「直连已移除，待 RPC 改造」。下表为原 43 工具的实测快照。

- 日期：2026-11-04（依据 `full-tool-test-results.json` 86 用例实测）
- 判定规则：**在当前部署形态（华为云 RDS Supabase：仅 Kong 网关 + service-role RPC 通道，直连已移除）下，工具能否完成其功能使命**。能 → 可用；恒报错或数据源在本部署中结构性缺失 → 不可用。
- 不可用 ≠ 异常：均列入后续改造或移除计划（见改造方向列）。

## 总览

| 判定 | 数量 |
|---|---:|
| 可用 | **26** |
| 不可用 | **17** |
| 合计 | 43 |

## 可用清单（26）

| # | 工具 | 实证（用例） | 说明 |
|---:|---|---|---|
| 1 | `execute_sql` | T05–T11, S×15, D01–D02 | 核心通道：读写全通、rows_affected 精确、read_only 白名单生效 |
| 2 | `list_tables` | T01, B001, D03 | 真实表清单 |
| 3 | `list_extensions` | T02 | 真实扩展清单（pg_net 等） |
| 4 | `get_database_connections` | T12 | 真实后端连接 |
| 5 | `get_project_url` | T14 | 返回网关 URL |
| 6 | `verify_jwt_secret` | T17 | 正确返回 not_configured（未配 secret 为真实状态，不泄露内容） |
| 7 | `rebuild_hooks` | T16 | pg_net 已装，worker 重启成功 |
| 8 | `get_advisors` | T32, T33 | 真实安全/性能体检报告 |
| 9 | `list_table_columns` | T36–T38 | 真实列元数据 + 标识符校验 |
| 10 | `list_indexes` | T39–T41 | 真实索引（含过滤/校验） |
| 11 | `list_constraints` | T42, T43 | 四类约束全验证 |
| 12 | `list_foreign_keys` | T44 | FK 关系 + CASCADE 规则 |
| 13 | `list_rls_policies` | T45, T46 | 真实策略 |
| 14 | `list_triggers` | T47 | 真实触发器 |
| 15 | `list_database_functions` | T48–T50 | 真实函数 + pattern 过滤/校验 |
| 16 | `get_function_definition` | T51, T52 | 真实源码 + not-found |
| 17 | `get_trigger_definition` | T53, T54 | 真实定义 + not-found |
| 18 | `get_rls_status` | T55, T56 | enabled/forced/policy_count 全验证 |
| 19 | `list_available_extensions` | T57–T59 | 真实可装扩展目录 |
| 20 | `get_index_stats` | T62, T63 | 真实索引统计 |
| 21 | `explain_query` | T65, T66 | 真实执行计划（含 ANALYZE+BUFFERS） |
| 22 | `list_cron_jobs` | T26 | 机制正常；pg_cron 未装 → 恒空（装扩展后即有数据） |
| 23 | `list_vector_indexes` | T27 | 机制正常；无向量索引 → 恒空（装 pgvector 建索引后即有数据） |
| 24 | `get_vector_index_stats` | T64 | 同上 |
| 25 | `get_storage_config` | T34 | storage schema 存在，当前无桶（建桶后即有数据） |
| 26 | `update_storage_config` | T35 | 机制正常，无桶时正确返回 Bucket not found |

## 不可用清单（17）

| # | 工具 | 现象（实测） | 根因 | 改造方向 |
|---:|---|---|---|---|
| 1 | `list_migrations` | 恒报错 42P01（T03） | `supabase_migrations.schema_migrations` 表不存在 | **已移除（0.2.0）** |
| 2 | `apply_migration` | 恒报错需 DATABASE_URL（T04） | 仅支持 pg 直连事务 | **已移除（0.2.0）** |
| 3 | `generate_typescript_types` | 恒结构化失败（T15） | 0.4.0 起直连已移除（原需 DATABASE_URL + CLI） | 改造：经 RPC 内省拼装类型文本；或移除（价值场景弱） |
| 4 | `list_auth_users` | 恒报错需 DATABASE_URL（T18） | 仅 pg 直连（0.4.0 直连已移除） | **0.3.0 已改造为可用（auth admin API 通道）** |
| 5 | `get_auth_user` | 同上（T19） | 同上 | 同上 |
| 6 | `delete_auth_user` | 同上（T20） | 同上 | **0.3.0 已改造为可用（auth admin API）** |
| 7 | `create_auth_user` | 同上（T21） | 同上 + pgcrypto 依赖 | **0.3.0 已改造为可用（auth admin API）** |
| 8 | `update_auth_user` | 同上（T22） | 同上 | 同上 |
| 9 | `list_storage_buckets` | 直连已移除，报不支持（T23） | 仅 pg 直连 | 改走 RPC 查 `storage.buckets` |
| 10 | `list_storage_objects` | 同上（T24） | 同上 | 改走 RPC 查 `storage.objects` |
| 11 | `list_realtime_publications` | 同上（T25） | 仅 pg 直连 | 改走 RPC 查 `pg_publication` |
| 12 | `get_database_stats` | 恒报错 42703（T13） | 实例为 PG17，`pg_stat_bgwriter.checkpoints_timed` 列已移除 | 适配 PG17：改用 `pg_stat_checkpointer`（保留旧视图兼容） |
| 13 | `get_cron_job_history` | 恒报错 pg_cron 未装（T60） | 扩展未安装 | 安装 pg_cron 即可用；或降级为空列表（对齐 list_cron_jobs 的优雅语义） |
| 14 | `list_edge_functions` | 恒空（T28） | edge runtime 服务不存在于本部署（非 SQL 可创建） | **已移除（0.2.0）** |
| 15 | `get_edge_function_details` | 恒 null（T29） | 同上 | **已移除（0.2.0）** |
| 16 | `list_edge_function_logs` | 恒报错表不存在（T61） | 同上 | **已移除（0.2.0）** |
| 17 | `get_logs` | 恒返回 none+提示（T30, T31） | analytics 栈未部署、CSV 日志未开启，本部署无日志源 | 接入 RDS 日志通道（慢日志/审计日志）或移除 |

## 改造优先级建议

| 优先级 | 批次 | 内容 | 预期收益 |
|---|---|---|---|
| P0 | ~~直连件套 RPC 化~~ | ~~auth 五件套~~（**0.3.0 已经 admin API 落地**）；剩 `list_storage_buckets/objects`、`list_realtime_publications`（3 个）待改造（建议 storage 走 Storage API、publications 走 RPC） | +3 可用（31→34） |
| P1 | 快速修复 | `get_database_stats` 适配 PG17；`list_migrations` 初始化表 | +2 可用 |
| P1 | 决策类 | edge 三件套（**已移除**）+ `get_logs`：确认是否接入日志通道，否则移除 | 精简工具面 |
| P2 | 深改造 | `apply_migration`（**已移除**）、`generate_typescript_types`（保留待决策）、`get_cron_job_history` | +2 可用 |

> 注：改造会偏离上游 TS 行为（通道从 pg 直连改为 RPC），需同步更新 README 的通道矩阵与行为差异声明，并重跑双服务器 E2E 以显式记录新差异。
