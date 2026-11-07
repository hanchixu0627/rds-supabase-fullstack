# 工具参考

完整清单与风险分级见 [server README](../../../../server/mcp_server_rds_supabase/README_zh.md)。

## 通道矩阵（v0.4.0，直连已移除）

| 通道 | 条件 | 覆盖工具 |
|---|---|---|
| RPC（execute_sql 函数） | SUPABASE_SERVICE_ROLE_KEY | 全部 SQL 类工具（**唯一 SQL 通道**） |
| auth admin API | SUPABASE_SERVICE_ROLE_KEY | auth 用户五件套 |
| （无 service key） | — | 仅 get_project_url / verify_jwt_secret 等本地工具；SQL 类返回 MCP_CONFIG_ERROR |

## 工具分组

| 角色 | 工具 |
|---|---|
| **SQL 执行** | execute_sql（主要功能：执行任意 SQL；执行 init.sql 迁移脚本时整批一个事务、失败自动回滚；read_only 开关） |
| 结构查询 | list_tables / list_table_columns / list_indexes / list_constraints / list_foreign_keys / list_triggers / list_database_functions / get_function_definition / get_trigger_definition / get_rls_status / list_rls_policies |
| 安全检查 | get_advisors / get_rls_status |
| 运行态 | get_database_connections / get_logs / explain_query / list_extensions / list_available_extensions |
| 用户管理 | list/get/delete/create/update_auth_user |
| 其他 | get_storage_config / update_storage_config / rebuild_hooks / verify_jwt_secret / get_project_url / list_cron_jobs / list_vector_indexes / get_index_stats / get_vector_index_stats |

## 统一错误格式

工具错误统一为 `{"error": {code, message, hint}}`：

- `MCP_CONFIG_ERROR`：service-role 密钥未配置（SQL/auth 通道不可用）
- `MCP_UNSUPPORTED_OPERATION`：list_storage_buckets、list_storage_objects、list_realtime_publications（直连通道已移除，改造待做）
- `MCP_READ_ONLY`：只读模式拦截 WRITE 工具
- `MCP_GUARDRAIL_BLOCKED`：保护名单/规则拦截
- SQLSTATE（如 `42P01`/`22012`）：SQL 执行错误，message 为 `SQL Error (<code>): <详情>`；**整批执行失败会全部回滚**
