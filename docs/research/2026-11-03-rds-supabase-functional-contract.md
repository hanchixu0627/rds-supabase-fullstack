<task id="ses_e5df0e88bffeF4XttChOShw2dl" state="completed">
<task_result>
已完成全部源码的调查。以下是基于实际源码（路径均已标注）的完整功能契约文档。

# rds-supabase-mcp 功能契约（Python 1:1 重建规格）

**仓库根**： `/Users/fitz/work/projects/research/supabase/supabase-mcp/rds-supabase-mcp`
**核心源码**： `src/index.ts`（入口）、`src/client/index.ts`（客户端）、`src/tools/*.ts`（43 个工具 + types.ts + utils.ts）、`src/server/http-server.ts` 与 `src/server/auth-middleware.ts`（HTTP 传输层）

---

## 1. 入口与配置（`src/index.ts`）

### 1.1 CLI 选项与 env 变量（commander，`program.name('rds-supabase-mcp')`）

| CLI 选项 | env 变量 | 默认值 | 描述原文 |
|---|---|---|---|
| `--url <url>` | `SUPABASE_URL` | 无（必填） | `Supabase project URL` |
| `--anon-key <key>` | `SUPABASE_ANON_KEY` | 无（必填） | `Supabase anonymous key` |
| `--service-key <key>` | `SUPABASE_SERVICE_ROLE_KEY` | 无（可选） | `Supabase service role key (optional)` |
| `--db-url <url>` | `DATABASE_URL` | 无（可选） | `Direct database connection string (optional, for pg fallback)` |
| `--jwt-secret <secret>` | `SUPABASE_AUTH_JWT_SECRET` | 无 | `Supabase JWT secret (optional, needed for some tools)` |
| `--workspace-path <path>` | — | `process.cwd()` | `Workspace root path (for file operations)` |
| `--tools-config <path>` | — | 无（= 启用全部） | `Path to a JSON file specifying which tools to enable (e.g., { "enabledTools": ["tool1", "tool2"] }). If omitted, all tools are enabled.` |
| `--transport <type>` | — | `'stdio'` | `Transport mode: stdio or http (default: stdio)` |
| `--port <number>` | — | `'3000'`（字符串，后 `parseInt`） | `HTTP server port (default: 3000)` |
| `--host <string>` | — | `'127.0.0.1'` | `HTTP server host (default: 127.0.0.1)` |
| `--cors-origins <origins>` | — | 无（= localhost only） | `Comma-separated list of allowed CORS origins (default: localhost only)` |
| `--rate-limit-window <ms>` | — | `'60000'` | `Rate limit window in milliseconds (default: 60000)` |
| `--rate-limit-max <count>` | — | `'100'` | `Max requests per rate limit window (default: 100)` |
| `--request-timeout <ms>` | — | `'30000'` | `Request timeout in milliseconds (default: 30000)` |

> **注意**：本仓库**不存在** `--read-only`、`--versions` 等 CLI 选项（已逐行核对 `src/index.ts` L86-103）。只读语义只存在于 `execute_sql` 工具参数 `read_only` 中。

### 1.2 启动校验与报错原文（L107-127）

```
if (!options.url):
  console.error('Error: Supabase URL is required. Use --url or SUPABASE_URL.');
  throw new Error('Supabase URL is required.');

if (!options.anonKey):
  console.error('Error: Supabase Anon Key is required. Use --anon-key or SUPABASE_ANON_KEY.');
  throw new Error('Supabase Anon Key is required.');

transport !== 'stdio' && transport !== 'http':
  console.error('Error: Invalid transport. Must be "stdio" or "http".');
  throw new Error('Invalid transport mode.');

transport === 'http' && !options.jwtSecret:
  console.error('Error: --jwt-secret is required for HTTP transport mode.');
  throw new Error('JWT secret is required for HTTP mode.');
```

### 1.3 认证模式逻辑

- **必填**：`--url` + `--anon-key`（无两者之一即抛错，见上）。
- **可选增强**：`--service-key`（特权 RPC）、`--db-url`（pg 直连）。
- 没有“service key vs anon key + db-url”的互斥分支；分支发生在**工具执行层**：
  - `execute_sql` / `executeSqlWithFallback`：无 db-url 且无 service key 时返回错误（原文见 §2.5）。
  - 依赖 db-url 的工具各自抛自己的报错（见 §3 各工具）。

### 1.4 MCP Server 实例化、工具注册与传输

- 客户端先经 `SelfhostedSupabaseClient.create({supabaseUrl, supabaseAnonKey, supabaseServiceRoleKey, databaseUrl, jwtSecret})` 异步初始化。
- **工具注册**：`Map<string, AppTool>`，按以下**注册顺序**（即 ListTools 返回顺序）共 **43 个**：
  1. `list_tables` 2. `list_extensions` 3. `list_migrations` 4. `apply_migration` 5. `execute_sql` 6. `get_database_connections` 7. `get_database_stats` 8. `get_project_url` 9. `generate_typescript_types` 10. `rebuild_hooks` 11. `verify_jwt_secret` 12. `list_auth_users` 13. `get_auth_user` 14. `delete_auth_user` 15. `create_auth_user` 16. `update_auth_user` 17. `list_storage_buckets` 18. `list_storage_objects` 19. `list_realtime_publications` 20. `list_cron_jobs` 21. `list_vector_indexes` 22. `list_edge_functions` 23. `get_edge_function_details` 24. `get_logs` 25. `get_advisors` 26. `get_storage_config` 27. `update_storage_config` 28. `list_table_columns` 29. `list_indexes` 30. `list_constraints` 31. `list_foreign_keys` 32. `list_rls_policies` 33. `list_triggers` 34. `list_database_functions` 35. `get_function_definition` 36. `get_trigger_definition` 37. `get_rls_status` 38. `list_available_extensions` 39. `get_cron_job_history` 40. `list_edge_function_logs` 41. `get_index_stats` 42. `get_vector_index_stats` 43. `explain_query`
- **工具白名单过滤**（`--tools-config`）：读 JSON 文件，要求 `{ "enabledTools": ["..."] }` 且全为字符串；解析失败 → `console.error` 后**回退启用全部工具**；白名单中不存在的工具名 → `console.warn('Warning: Tool "<name>" specified in config file not found.')`；不在白名单的可用工具 → `console.error('Tool <name> disabled (not in config whitelist).')`。仓库根的 `mcp-tools.json` 是空白名单样例（`{"enabledTools": []}`）。
- **Server 实例**： `new Server({name: 'rds-supabase-mcp', version: '0.1.0'}, {capabilities})`；`ListTools` 返回 `Object.values(capabilities.tools)`，每项为 `{name, description: tool.description || 'Tool description missing', inputSchema: tool.mcpInputSchema}`。
- **CallTool 行为**（L282-357）：
  - 未注册工具：在可用表但被过滤 → `McpError(MethodNotFound, 'Tool "<name>" is available but not enabled by the current server configuration.')`；完全未知 → `McpError(MethodNotFound, 'Unknown tool: <name>')`。
  - HTTP 模式权限检查：`tool.privilegeLevel ?? 'regular'`；拒绝时 `console.error('[SECURITY] Access denied: User ... (role: ...) attempted to access <tool> (requires: ...)')` 并抛 `McpError(InvalidRequest, "Access denied: Tool '<tool>' requires '<level>' privilege. Your role '<role>' does not have sufficient permissions.")`。stdio 模式（无 userContext）跳过检查。
  - 参数用 zod `inputSchema.parse(request.params.arguments)` 校验。
  - ToolContext： `{selfhostedClient, workspacePath, user: userContext, log: (message, level='info') => console.error('[' + level.toUpperCase() + '] ' + message)}`。
  - 返回包装： `{content: [{type: 'text', text: typeof result === 'string' ? result : JSON.stringify(result, null, 2)}]}`。
  - 错误包装（不抛出，返回 isError）：前缀 `Error executing tool <toolName>: `；`z.ZodError` 追加 `Input validation failed: <path: message 逗号连接>`；`Error` 追加 `error.message`；否则 `String(error)`；返回 `{content: [{type:'text', text: errorMessage}], isError: true}`。
- **MCP annotations**：**完全没有**设置（grep 确认 `readOnlyHint/destructiveHint/idempotentHint/openWorldHint/annotations` 零命中）。能力声明仅 `tools`，无 `resources/prompts`。
- **传输**：stdio 用 `StdioServerTransport`，启动打印警告横幅（`WARNING: Stdio mode has NO authentication...`）；http 用 `HttpMcpServer`（见 §6）。

---

## 2. Client 层（`src/client/index.ts`）

### 2.1 总体结构

`SelfhostedSupabaseClient`（私有构造器 + 静态 `create()` 工厂，`create()` 内先构造再 `initialize()`）。持有：

- `supabase`： anon key 的 supabase-js 客户端（`createClient(supabaseUrl, supabaseAnonKey)`）；
- `supabaseServiceRole`： 仅当提供 service key 时创建；
- `pgPool`： 懒初始化的 node-postgres `Pool({connectionString: databaseUrl})`（**无 SSL 特殊配置**，完全交由连接串/驱动默认行为）；
- `rpcFunctionExists`: boolean。

**没有自研 PostgREST 封装** —— PostgREST 交互全部经由 supabase-js（RPC 走 `POST {supabaseUrl}/rest/v1/rpc/execute_sql`，header 由 supabase-js 自动带 `apikey` 与 `Authorization: Bearer <key>`，`Content-Type: application/json`）。

### 2.2 内嵌的 helper 函数 DDL（启动时可能自动部署，L19-50）

`CREATE_EXECUTE_SQL_FUNCTION`（原文）：
```sql
CREATE OR REPLACE FUNCTION public.execute_sql(query text, read_only boolean DEFAULT false)
RETURNS jsonb -- Using jsonb is generally preferred over json
LANGUAGE plpgsql
AS $$
DECLARE
  result jsonb;
BEGIN
  -- Note: SET TRANSACTION READ ONLY might not behave as expected within a function
  -- depending on the outer transaction state. Handle read-only logic outside if needed.

  -- Execute the dynamic query and aggregate results into a JSONB array
  EXECUTE 'SELECT COALESCE(jsonb_agg(t), ''[]''::jsonb) FROM (' || query || ') t' INTO result;

  RETURN result;
EXCEPTION
  WHEN others THEN
    -- Rethrow the error with context, including the original SQLSTATE
    RAISE EXCEPTION 'Error executing SQL (SQLSTATE: %): % ', SQLSTATE, SQLERRM;
END;
$$;
```
`GRANT_EXECUTE_SQL_FUNCTION`（原文）：
```sql
-- Revoke any existing grants to ensure clean state
REVOKE ALL ON FUNCTION public.execute_sql(text, boolean) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.execute_sql(text, boolean) FROM authenticated;
REVOKE ALL ON FUNCTION public.execute_sql(text, boolean) FROM anon;
-- Grant only to service_role for privileged operations
GRANT EXECUTE ON FUNCTION public.execute_sql(text, boolean) TO service_role;
```
> 注：`sql/mcp-execute-sql.sql` 是另一份（更严格的 SECURITY DEFINER + 只读门禁版）DDL，**仅作为手工部署参考，不被代码引用**；代码运行时使用的是上面的内嵌版本（**无只读门禁**，read_only 只透传给函数参数）。

### 2.3 方法 → 端点/RPC/SQL 完整映射

| 方法 | 调用目标 | 行为 |
|---|---|---|
| `executeSqlViaRpc(query, readOnly=false)` | anon 客户端 `supabase.rpc('execute_sql', {query, read_only})` | 函数不存在时返回 `{error:{message:'execute_sql RPC function not found or client not properly initialized.', code:'MCP_CLIENT_ERROR'}}`；PostgREST error → `{error:{message, code, details, hint}}`；data 非数组 → `{error:{message:'Unexpected response format from execute_sql RPC. Expected JSON array.', code:'MCP_RPC_FORMAT_ERROR'}}`；异常 → `{error:{message:'Exception during RPC call: <msg>', code:'MCP_RPC_EXCEPTION'}}` |
| `executeSqlViaServiceRoleRpc(query, readOnly=false)` | service role 客户端同上 RPC | 无 service key → `{error:{message:'Service role key not configured. Cannot execute privileged SQL via RPC.', code:'MCP_CONFIG_ERROR'}}`；其余同上（异常消息为 `Exception during Service Role RPC call: <msg>`） |
| `executeSqlWithPg(query)` | pg 直连 `client.query(query)`，**不支持参数化** | 无 db-url → `{error:{message:'DATABASE_URL is not configured. Cannot execute SQL directly.', code:'MCP_CONFIG_ERROR'}}`；成功返回 `result.rows`；失败 → `{error:{message, code: pg错误code或'PG_ERROR'}}`（**注意：忽略 readOnly 参数**） |
| `executeTransactionWithPg(callback)` | pg 直连，`BEGIN` → callback → `COMMIT`，异常 `ROLLBACK` 后**重抛** | 无 db-url 抛 `'DATABASE_URL is not configured. Cannot execute transaction directly.'`；池不可用抛 `'pg Pool not available for transaction.'` |
| `ensurePgPool()`（私有） | 懒建池 | 无 db-url 抛 `'DATABASE_URL is not configured. Cannot initialize pg pool.'`；首次建池会试连一次，失败则 `pool.end()` 置空并抛 `'Failed to connect pg pool: <msg>'`；池后台错误日志 `'PG Pool Error: Unexpected error on idle client'` |
| `checkAndCreateRpcFunction()`（私有，`initialize()` 调用） | 先（优先 service role 客户端，否则 anon）`rpc('execute_sql', {query: 'SELECT 1'})` | 无错 → `rpcFunctionExists=true`；错误码 `42883` 或 `PGRST202` → 视为函数缺失，**仅当 service key 且 db-url 同时存在**才依次 `executeSqlWithPg(CREATE_EXECUTE_SQL_FUNCTION)`、`executeSqlWithPg(GRANT_EXECUTE_SQL_FUNCTION)`、`executeSqlWithPg("NOTIFY pgrst, 'reload schema'")` 并置 `rpcFunctionExists=true`；创建失败抛 `'Failed to create execute_sql function/notify: <msg>'`；其他错误码抛 `'Error checking for execute_sql function: <msg>'`；外层异常抛 `'Exception during RPC function check/creation: <msg>'`。`initialize()` 捕获所有异常**只打日志不中断启动**（`'Error during client initialization:'`） |

### 2.4 Getter / 状态

`getSupabaseUrl()`、`getAnonKey()`、`getServiceRoleKey()`、`getJwtSecret()`、`getDbUrl()`、`isPgAvailable()`（= `!!databaseUrl`）、`isServiceRoleAvailable()`（= service 客户端已建）。

### 2.5 共享工具函数（`src/tools/utils.ts`）

- `redactDatabaseUrl(url)`: URL 解析成功则密码替换为 `****`；失败则正则 `/:([^:@]+)@/ → ':****@'`。
- `sanitizeErrorForLogging(error)`: Error → `[code] message` 或 `message`；对象取 message/code；否则 `String(error)`。
- `isSqlErrorResponse(result)`: 判 `result.error !== undefined`。
- `handleSqlResponse<T>(result, schema)`: 有 error → 抛 `` `SQL Error (${result.error.code}): ${result.error.message}` ``；schema.parse 失败（ZodError）→ 抛 `` `Schema validation failed: ${issues.map(e => `${e.path.join('.')}: ${e.message}`).join(', ')}` ``；其他抛 `` `Unexpected validation error: ${validationError}` ``。
- `runExternalCommand(command)`: `child_process.exec`；返回 `{stdout, stderr, error:null}` 或失败时 `{stdout: execError.stdout||'', stderr: execError.stderr||execError.message, error}`。
- **`executeSqlWithFallback(client, sql, readOnly=true)`（核心编排）**，优先级：
  1. `client.isPgAvailable()` → `console.info('Using direct database connection (bypassing JWT)...')` → `executeSqlWithPg(sql)`（**readOnly 被忽略**）；
  2. 否则 `client.isServiceRoleAvailable()` → `console.info('Using service role RPC method...')` → `executeSqlViaServiceRoleRpc(sql, readOnly)`；
  3. 都不可用 → 返回 `{error:{message:'Neither direct database connection (DATABASE_URL) nor service role key (SUPABASE_SERVICE_ROLE_KEY) is configured. Cannot execute SQL.', code:'MCP_CONFIG_ERROR'}}`。

### 2.6 响应数据类型（`src/types/index.ts`）

- `SqlSuccessResponse = Record<string, unknown>[]`（行数组；RPC 下空结果为 `[]`，因函数 `COALESCE(jsonb_agg(t),'[]'::jsonb)`）
- `SqlErrorResponse = {error: {message: string; code?; details?; hint?}}`
- `SqlExecutionResult = SqlSuccessResponse | SqlErrorResponse`

---

## 3. 43 个工具逐个规格（按注册顺序）

通用约定（适用于每个工具）：
- 工具对象字段： `name / description / inputSchema(zod) / mcpInputSchema(静态JSON Schema，ListTools展示用) / outputSchema(zod) / privilegeLevel?`。
- 所有走 `executeSqlWithFallback` 的工具默认 `readOnly=true`（个别标注除外）。
- 成功返回值经 index.ts 包装为 `content[0].text = JSON.stringify(result, null, 2)`。
- 无特别说明时“错误透传"= execute 出错 → index.ts 的 `Error executing tool <name>: <msg>` + `isError: true`。

---

### 3.1 `list_tables`（`src/tools/list_tables.ts`）
- **description**: `Lists all accessible tables in the connected database, grouped by schema.`
- **输入**： 无参数（`z.object({})`；mcpInputSchema `properties:{}, required:[]`）。
- **执行**： `executeSqlWithFallback(client, SQL, true)` → `handleSqlResponse(result, ListTablesOutputSchema)`。SQL 原文：
```sql
SELECT
    n.nspname as schema,
    c.relname as name,
    pgd.description as comment
FROM
    pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    LEFT JOIN pg_catalog.pg_description pgd ON pgd.objoid = c.oid AND pgd.objsubid = 0
WHERE
    c.relkind = 'r' -- r = ordinary table
    AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
    AND n.nspname NOT LIKE 'pg_temp_%'
    AND n.nspname NOT LIKE 'pg_toast_temp_%'
     -- Exclude Supabase internal schemas
    AND n.nspname NOT IN ('auth', 'storage', 'extensions', 'graphql', 'graphql_public', 'pgbouncer', 'realtime', 'supabase_functions', 'supabase_migrations', '_realtime')
    AND has_schema_privilege(n.oid, 'USAGE')
    AND has_table_privilege(c.oid, 'SELECT')
ORDER BY
    n.nspname,
    c.relname
```
- **返回**： `[{schema, name, comment?}]`（comment 可 null 可缺省）。空 → `[]`。
- **错误**： SQL/配置错误按 handleSqlResponse/透传规则。

### 3.2 `list_extensions`（`list_extensions.ts`）
- **description**: `Lists all installed PostgreSQL extensions in the database.`
- **输入**： 无。
- **执行**： `executeSqlWithFallback(client, SQL, true)`：
```sql
SELECT
    pe.extname AS name,
    pn.nspname AS schema,
    pe.extversion AS version,
    pd.description
FROM
    pg_catalog.pg_extension pe
    LEFT JOIN pg_catalog.pg_namespace pn ON pn.oid = pe.extnamespace
    LEFT JOIN pg_catalog.pg_description pd ON pd.objoid = pe.oid AND pd.classoid = 'pg_catalog.pg_extension'::regclass
WHERE
    pe.extname != 'plpgsql' -- Exclude the default plpgsql extension
ORDER BY
    pe.extname
```
- **返回**： `[{name, schema, version, description?}]`。

### 3.3 `list_migrations`（`list_migrations.ts`）
- **description**: `Lists applied database migrations recorded in supabase_migrations.schema_migrations table.`
- **输入**： 无。
- **执行**： `executeSqlWithFallback`:
```sql
SELECT
    version,
    name,
    inserted_at
FROM
    supabase_migrations.schema_migrations
ORDER BY
    version
```
- **返回**： `[{version: string, name: string, inserted_at: string}]`。表不存在时错误经 handleSqlResponse 抛出（如 `SQL Error (42P01): ...`）。

### 3.4 `apply_migration`（`apply_migration.ts`）—— `privilegeLevel: 'privileged'`
- **description**: `Applies a SQL migration script and records it in the supabase_migrations.schema_migrations table within a transaction.`
- **输入**： `version: string`（`The migration version string (e.g., '20240101120000').`，必填）；`name: string?`（`An optional descriptive name for the migration.`）；`sql: string`（`The SQL DDL content of the migration.`，必填）。
- **执行**： 前置 `client.isPgAvailable()`，否则抛 `'Direct database connection (DATABASE_URL) is required for applying migrations but is not configured or available.'`。然后 `executeTransactionWithPg`：① `pgClient.query(input.sql)`；② `pgClient.query('INSERT INTO supabase_migrations.schema_migrations (version, name) VALUES ($1, $2);', [input.version, input.name ?? ''])`。
- **返回**： `{success: true, version: <version>, message: "Migration <version> applied successfully."}`。
- **错误**： 任何失败抛 `` `Failed to apply migration ${input.version}: ${errorMessage}` ``（事务回滚后）。

### 3.5 `execute_sql`（`execute_sql.ts`）—— `privilegeLevel: 'privileged'`
- **description**: `Executes an arbitrary SQL query against the database. SECURITY: Requires service_role key or direct database connection.`
- **输入**： `sql: string`（`The SQL query to execute.`，必填）；`read_only: boolean = false`（`Hint for the RPC function whether the query is read-only (best effort).`）。
- **执行**：
  1. 若 `!isPgAvailable() && !isServiceRoleAvailable()` 抛：
     `'execute_sql requires either a direct database connection (DATABASE_URL) or a service role key (SUPABASE_SERVICE_ROLE_KEY) to be configured. This tool cannot be used with only the anon key for security reasons.'`
  2. 审计日志：`[AUDIT] SQL execution by user=<email|userId|'unknown (stdio mode)'> role=<role>: <queryPreview>`；queryPreview 超 200 字符截断为 `前200字... [truncated, <总长> chars total]`。
  3. `executeSqlWithFallback(client, input.sql, input.read_only)` → `handleSqlResponse(result, z.array(z.unknown()))`。
- **返回**： 行数组（任意对象数组；RPC 路径下非行返回语句由内嵌函数聚合成 `[]`）。

### 3.6 `get_database_connections`（`get_database_connections.ts`）
- **description**: `Retrieves information about active database connections from pg_stat_activity.`
- **输入**： 无。
- **执行**： `executeSqlWithFallback`:
```sql
SELECT
    pid,
    datname,
    usename,
    application_name,
    client_addr::text, -- Cast inet to text
    backend_start::text, -- Cast timestamp to text
    state,
    query
FROM
    pg_stat_activity
WHERE
    backend_type = 'client backend' -- Exclude background workers, etc.
    -- Optionally filter out self?
    -- AND pid != pg_backend_pid()
ORDER BY
    backend_start
```
- **返回**： `[{pid: number, datname?, usename?, application_name?, client_addr?, backend_start?, state?, query?}]`（均 nullable 除 pid）。

### 3.7 `get_database_stats`（`get_database_stats.ts`）
- **description**: `Retrieves statistics about database activity and the background writer from pg_stat_database and pg_stat_bgwriter.`
- **输入**： 无。
- **执行**： `Promise.all` 并行两条 `executeSqlWithFallback`：
```sql
-- getDbStatsSql
SELECT
    datname, numbackends, xact_commit::text, xact_rollback::text, blks_read::text, blks_hit::text,
    tup_returned::text, tup_fetched::text, tup_inserted::text, tup_updated::text, tup_deleted::text,
    conflicts::text, temp_files::text, temp_bytes::text, deadlocks::text, checksum_failures::text,
    checksum_last_failure::text, blk_read_time, blk_write_time, stats_reset::text
FROM pg_stat_database
```
```sql
-- getBgWriterStatsSql
SELECT
    checkpoints_timed::text, checkpoints_req::text, checkpoint_write_time, checkpoint_sync_time,
    buffers_checkpoint::text, buffers_clean::text, maxwritten_clean::text, buffers_backend::text,
    buffers_backend_fsync::text, buffers_alloc::text, stats_reset::text
FROM pg_stat_bgwriter
```
- **返回**： `{database_stats: [...], bgwriter_stats: [...]}`（bigint 均为字符串，double/numbackends 为数字，均 nullable）。

### 3.8 `get_project_url`（`get_project_url.ts`）
- **description**: `Returns the configured Supabase project URL for this server.`
- **输入**： 无。**执行**： `client.getSupabaseUrl()`。
- **返回**： `{project_url: <启动传入的 url>}`。

### 3.9 `generate_typescript_types`（`generate_typescript_types.ts`）
- **description**: `` Generates TypeScript types from the database schema using the Supabase CLI (`supabase gen types`) and downloads the file to the specified absolute path. The tool returns the current platform (win32, darwin, linux) to help with path formatting. Requires DATABASE_URL configuration and Supabase CLI installed. ``
- **输入**： `included_schemas: string[] = ['public']`（`Database schemas to include in type generation.`）；`output_filename: string = 'database.types.ts'`（`Filename to save the generated types to in the workspace root.`，**实际被忽略**）；`output_path: string`（必填，`Absolute path where to save the file. If provided, output_filename will be ignored.`）。
- **执行**（外部 CLI）：
  1. 无 db-url → 返回 `{success:false, message:'Error: DATABASE_URL is not configured. Cannot generate types.', platform: <process.platform>}`。
  2. 每个 schema 过 `sanitizeSchemaName`（正则 `^[a-zA-Z_][a-zA-Z0-9_-]*$`，违规抛 `Invalid schema name "<截断50字符并以?脱敏>": must start with a letter or underscore and contain only alphanumeric characters, underscores, or hyphens`，以 `{success:false, message, platform}` 返回）。
  3. 命令：`` supabase gen types typescript --db-url "<dbUrl>" --schema "<schemas逗号连接>" ``（日志中 db-url 经 `redactDatabaseUrl` 脱敏）。
  4. `runExternalCommand` 失败 → `{success:false, message: "Command failed: <stderr或error.message>", platform}`；stderr 非致命。
  5. 输出路径 `normalizeOutputPath(output_path, context.workspacePath)`：去 `\0`、`\`→`/`、resolve；Windows 盘符修正；**越出 workspace 抛** `Output path must be within workspace directory: <resolvedWorkspace>`（以 `{success:false, message:'Invalid output path "<input.output_path>": <err>', platform}` 返回）。
  6. `mkdirSync(dir, {recursive:true})`（EEXIST 忽略）→ `writeFileSync(outputPath, stdout, 'utf8')`。
- **返回**（成功）： `{success:true, message:"Types generated successfully and saved to <outputPath>.[\nWarnings:\n<stderr>]", types: <stdout原文>, file_path: <outputPath>, platform: <process.platform>}`；写文件失败 → `{success:false, message:"Type generation succeeded but failed to save file: <err>. Platform: <platform>. Attempted path: <outputPath>", types: stdout, platform}`；外层异常 → `{success:false, message:"Exception during type generation: <err>. Platform: <platform>", platform}`。

### 3.10 `rebuild_hooks`（`rebuild_hooks.ts`）—— `privilegeLevel: 'privileged'`
- **description**: `Attempts to restart the pg_net worker. Requires the pg_net extension to be installed and available.`
- **输入**： 无。
- **执行**： `executeSqlWithFallback(client, 'SELECT net.worker_restart()', false)`（readOnly=false）。
- **返回**： 成功 `{success:true, message:'pg_net worker restart requested successfully.'}`；结果含 error → `{success:false, message: "Failed to restart pg_net worker: <err.message>" + (err.code==='42883' ? ' (Is pg_net installed and enabled?)' : '')}`；异常 → `{success:false, message:"Exception attempting to restart pg_net worker: <msg>"}`（**不抛错，始终结构化返回**）。

### 3.11 `verify_jwt_secret`（`verify_jwt_secret.ts`）—— `privilegeLevel: 'regular'`
- **description**: `Checks if the Supabase JWT secret is configured for this server.`
- **输入**： 无。**执行**： `client.getJwtSecret()` 真值判定。
- **返回**： 有 → `{jwt_secret_status: 'found'}`；无 → `{jwt_secret_status: 'not_configured'}`（**不回显任何 secret 内容**）。

### 3.12 `list_auth_users`（`list_auth_users.ts`）
- **description**: `Lists users from the auth.users table.`
- **输入**： `limit: int 正数 = 50`（`Max number of users to return`）；`offset: int 非负 = 0`（`Number of users to skip`）。
- **执行**： 无 db-url 抛 `'Direct database connection (DATABASE_URL) is required to list auth users.'`。`executeSqlWithPg`（**不走 fallback，pg 专用**）：
```sql
SELECT
    id, email, role, raw_app_meta_data, raw_user_meta_data,
    created_at::text, -- Cast timestamp to text for JSON
    last_sign_in_at::text -- Cast timestamp to text for JSON
FROM
    auth.users
ORDER BY
    created_at DESC
LIMIT ${limit}
OFFSET ${offset}
```
（limit/offset 由 zod 保证为整数，直接内插。）
- **返回**： `[AuthUser]`，AuthUser = `{id: uuid, email: email|null, role: string|null, created_at: string|null, last_sign_in_at: string|null, raw_app_meta_data: object|null, raw_user_meta_data: object|null}`。日志 `Found <n> users.`。

### 3.13 `get_auth_user`（`get_auth_user.ts`）
- **description**: `Retrieves details for a specific user from auth.users by their ID.`
- **输入**： `user_id: string(uuid)`（`The UUID of the user to retrieve.`，必填）。
- **执行**： 无 db-url 抛 `'Direct database connection (DATABASE_URL) is required to get auth user details.'`。`executeTransactionWithPg` + **参数化**查询：
```sql
SELECT id, email, role, raw_app_meta_data, raw_user_meta_data, created_at::text, last_sign_in_at::text
FROM auth.users WHERE id = $1
```
- **返回**： 单个 AuthUser 对象（非数组）。行数为 0 → 抛 `` `User with ID ${user_id} not found.` ``；行验证失败抛 `` `Output validation failed: <zod issues>` ``。

### 3.14 `delete_auth_user`（`delete_auth_user.ts`）—— `privilegeLevel: 'privileged'`
- **description**: `Deletes a user from auth.users by their ID. Requires service_role key and direct DB connection.`
- **输入**： `user_id: string(uuid)`（必填）。
- **执行**： 无 db-url 抛 `'Direct database connection (DATABASE_URL) is required for deleting users but is not configured or available.'`。`executeTransactionWithPg` 执行 `DELETE FROM auth.users WHERE id = $1`。
- **返回**： rowCount===1 → `{success:true, message:"Successfully deleted user with ID: <user_id>"}`；否则 `{success:false, message:"User with ID <user_id> not found or could not be deleted."}`。异常抛 `` `Failed to delete user ${user_id}: ${errorMessage}` ``。

### 3.15 `create_auth_user`（`create_auth_user.ts`）—— `privilegeLevel: 'privileged'`
- **description**: `Creates a new user directly in auth.users. WARNING: Requires plain password, insecure. Use with extreme caution.`
- **输入**： `email: string(email)`（`The email address for the new user.`，必填）；`password: string min 6`（`Plain text password (min 6 chars). WARNING: Insecure.`，必填）；`role?: string`（`User role.`）；`app_metadata?: object`；`user_metadata?: object`。
- **执行**： 无 db-url 抛 `'Direct database connection (DATABASE_URL) is required to create an auth user directly.'`。事务内：
  1. 探测 pgcrypto：`SELECT crypt('test', gen_salt('bf'))`，失败抛 `'Failed to execute crypt function. Ensure pgcrypto extension is enabled in the database.'`。
  2. 参数化 INSERT（params: `[email, password, role || 'authenticated', JSON.stringify(app_metadata || {}), JSON.stringify(user_metadata || {})]`）：
```sql
INSERT INTO auth.users (
    instance_id, email, encrypted_password, role,
    raw_app_meta_data, raw_user_meta_data, 
    aud, email_confirmed_at, confirmation_sent_at -- Set required defaults
)
VALUES (
    COALESCE(current_setting('app.instance_id', TRUE), '00000000-0000-0000-0000-000000000000')::uuid,
    $1, crypt($2, gen_salt('bf')),
    $3,
    $4::jsonb,
    $5::jsonb,
    'authenticated', now(), now()
)
RETURNING id, email, role, raw_app_meta_data, raw_user_meta_data, created_at::text, last_sign_in_at::text;
```
- **返回**： 创建的 AuthUser（含 id）。
- **错误**： 空结果抛 `'User creation failed, no user returned after insert.'`；PG `23505` → `` `User creation failed: Email '${email}' likely already exists.` ``；其他 DB 错误 → `Database error (<code>): <msg>` / `Database error code: <code>` / `Database error during user creation: <msg>`。

### 3.16 `update_auth_user`（`update_auth_user.ts`）—— `privilegeLevel: 'privileged'`
- **description**: `Updates fields for a user in auth.users. WARNING: Password handling is insecure. Requires service_role key and direct DB connection.`
- **输入**： `user_id: uuid`（必填）；`email?`（`New email address.`）；`password?`（min 6，`New plain text password (min 6 chars). WARNING: Insecure.`）；`role?`；`app_metadata?`（`New app metadata (will overwrite existing).`）；`user_metadata?`（`New user metadata (will overwrite existing).`）。**zod `.refine`**：五者至少一个，否则报 `"At least one field to update (email, password, role, app_metadata, user_metadata) must be provided."`。
- **执行**： 无 db-url 抛 `'Direct database connection (DATABASE_URL) is required to update auth user details.'`。动态 SET 子句（均参数化，user_id 为最后一个参数）：`email = $n`、`encrypted_password = crypt($n, gen_salt('bf'))`、`role = $n`、`raw_app_meta_data = $n::jsonb`（metadata 一律 `JSON.stringify` 后整体覆盖）、`raw_user_meta_data = $n::jsonb`，并附加 `updated_at = NOW()`：
```sql
UPDATE auth.users
SET <updates逗号连接>, updated_at = NOW()
WHERE id = $<last>
RETURNING id, email, role, raw_app_meta_data, raw_user_meta_data, created_at::text, updated_at::text, last_sign_in_at::text;
```
  若更新密码则先探测 pgcrypto，失败抛 `'Failed to execute crypt function for password update. Ensure pgcrypto extension is enabled.'`。
- **返回**： 更新后的用户（含 `updated_at`）。
- **错误**： 0 行抛 `` `User update failed: User with ID ${user_id} not found or no rows affected.` ``；email 更新遇 `23505` → `` `User update failed: Email '${email}' likely already exists for another user.` ``；其余同 create 的错误族（`Database error during user update: ...`）。

### 3.17 `list_storage_buckets`（`list_storage_buckets.ts`，default export）
- **description**: `Lists all storage buckets in the project.`
- **输入**： 无。
- **执行**： 无 db-url 抛 `'Direct database connection (DATABASE_URL) is required to list storage buckets.'`。`executeSqlWithPg`：
```sql
SELECT id, name, owner, public, avif_autodetection, file_size_limit, allowed_mime_types,
       created_at::text, updated_at::text
FROM storage.buckets;
```
- **返回**： `[{id, name, owner|null, public: bool, avif_autodetection: bool, file_size_limit: number|null, allowed_mime_types: string[]|null, created_at|null, updated_at|null}]`。

### 3.18 `list_storage_objects`（`list_storage_objects.ts`，default export）
- **description**: `Lists objects within a specific storage bucket, optionally filtering by prefix.`
- **输入**： `bucket_id: string`（必填）；`limit: int正 = 100`；`offset: int非负 = 0`；`prefix?: string`（`Filter objects by a path prefix (e.g., 'public/')`）。
- **执行**： 无 db-url 抛 `'Direct database connection (DATABASE_URL) is required to list storage objects.'`。事务内**全参数化**：
```sql
SELECT id, name, bucket_id, owner, version,
       metadata ->> 'mimetype' AS mimetype,
       metadata ->> 'size' AS size,
       metadata, created_at::text, updated_at::text, last_accessed_at::text
FROM storage.objects
WHERE bucket_id = $1
[AND name LIKE $2]           -- 仅当 prefix 提供，参数为 `<prefix>%`
ORDER BY name ASC NULLS FIRST
LIMIT $n OFFSET $m;
```
- **返回**： `[{id, name|null, bucket_id, owner|null, version|null, mimetype|null, size: number|null(metadatasize字符串parseInt，NaN→null), metadata|null, created_at|null, updated_at|null, last_accessed_at|null}]`。

### 3.19 `list_realtime_publications`（`list_realtime_publications.ts`，default export）
- **description**: `Lists PostgreSQL publications, often used by Supabase Realtime.`
- **输入**： 无。
- **执行**： 无 db-url 抛 `'Direct database connection (DATABASE_URL) is required to list publications.'`。`executeSqlWithPg`：
```sql
SELECT oid, pubname, pubowner, puballtables, pubinsert, pubupdate, pubdelete, pubtruncate, pubviaroot
FROM pg_catalog.pg_publication;
```
- **返回**： `[{oid:int, pubname, pubowner:int, puballtables: bool, pubinsert: bool, pubupdate: bool, pubdelete: bool, pubtruncate: bool, pubviaroot: bool}]`。

### 3.20 `list_cron_jobs`（`list_cron_jobs.ts`）
- **description**: `Lists all scheduled cron jobs from pg_cron extension. Returns empty array if pg_cron is not installed.`
- **输入**： 无。
- **执行**（两步，`executeSqlWithFallback`）：
```sql
SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname = 'cron') AS exists
```
  exists=false 或无法确认（warn `'Could not verify pg_cron installation'`）→ 返回 `[]`；否则：
```sql
SELECT jobid, schedule, command, nodename, nodeport, database, username, active
FROM cron.job ORDER BY jobid
```
- **返回**： `[{jobid:number, schedule, command, nodename, nodeport:number, database, username, active:bool}]`。

### 3.21 `list_vector_indexes`（`list_vector_indexes.ts`）
- **description**: `Lists all pgvector indexes (ivfflat, hnsw) in the database. Returns empty array if pgvector is not installed or no vector indexes exist.`
- **输入**： 无。
- **执行**： `executeSqlWithFallback`:
```sql
SELECT
    ix.relname AS index_name, t.relname AS table_name, n.nspname AS schema_name,
    am.amname AS index_method, pg_get_indexdef(i.indexrelid) AS index_definition
FROM pg_index i
JOIN pg_class t ON t.oid = i.indrelid
JOIN pg_class ix ON ix.oid = i.indexrelid
JOIN pg_namespace n ON n.oid = t.relnamespace
JOIN pg_am am ON am.oid = ix.relam
WHERE am.amname IN ('ivfflat', 'hnsw')
AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
ORDER BY n.nspname, t.relname, ix.relname
```
- **返回**： `[{index_name, table_name, schema_name, index_method, index_definition}]`；空时 log `'No pgvector indexes found (pgvector may not be installed or no indexes created)'`。

### 3.22 `list_edge_functions`（`list_edge_functions.ts`）
- **description**: `Lists all deployed Supabase Edge Functions. Returns empty array if edge functions are not available or none are deployed.`
- **输入**： 无。
- **执行**（三步检查，均为 `executeSqlWithFallback`）：① schema 存在性 `SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname = 'supabase_functions') AS exists`；② 表存在性 `SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_tables WHERE schemaname = 'supabase_functions' AND tablename = 'functions') AS exists`；任一不存在/无法确认 → 返回 `[]`；③：
```sql
SELECT id, name, slug, status, version, created_at::text, updated_at::text
FROM supabase_functions.functions ORDER BY name
```
- **返回**： `[{id: uuid, name, slug, status|null, version: number|null, created_at|null, updated_at|null}]`。

### 3.23 `get_edge_function_details`（`get_edge_function_details.ts`）
- **description**: `Gets detailed information about a specific Supabase Edge Function by ID or slug. Returns null if not found or edge functions are not available.`
- **输入**： `function_identifier: string`（`The function ID (UUID) or slug to look up`，必填）。
- **执行**： 同 3.22 的两步存在性检查（不存在 → 返回 `null`）；单引号转义（`'`→`''`）后：
```sql
SELECT id, name, slug, status, version, created_at::text, updated_at::text, verify_jwt, import_map
FROM supabase_functions.functions
WHERE id::text = '<escaped>' OR slug = '<escaped>'
LIMIT 1
```
- **返回**： 单个对象 `{id, name, slug, status|null, version|null, created_at|null, updated_at|null, verify_jwt: bool|null, import_map: bool|null}`；未找到 → `null`（log `Edge function not found: <id>`）。

### 3.24 `get_logs`（`get_logs.ts`）
- **description**: `Gets logs for a Supabase service. Attempts to query the analytics stack first, then falls back to PostgreSQL CSV logs. Returns logs from the last 24 hours. Note: Log availability depends on your self-hosted installation configuration.`
- **输入**： `service: enum('postgres'|'auth'|'storage'|'realtime'|'postgrest')`（必填）；`limit: number min1 max1000 = 100`（`Maximum number of log entries to return (default: 100, max: 1000)`）。
- **执行**（级联 fallback）：
  1. **analytics 栈**：查 `_analytics` schema 存在 → service→表名映射（postgres→`postgres_logs`, auth→`auth_logs`, storage→`storage_logs`, realtime→`realtime_logs`, postgrest→`postgrest_logs`）→ 查 `_analytics.<表>` 存在 → 查询（近 24 小时，`timestamp::text`、`COALESCE(level,'info')`、`message`、`metadata::jsonb`，`ORDER BY timestamp DESC LIMIT <limit>`）。任一失败返回 null 继续降级。
  2. 仅 `service==='postgres'`：**CSV 日志**：`file_fdw` 扩展存在 → `SELECT pg_current_logfile()` → 存在 `pglog` 外表则查询（severity→level 映射 ERROR→error/WARNING→warn/LOG→info/其他→debug；metadata 由 user_name/database_name/process_id/sql_state_code 构造 jsonb）。
  3. 都失败 → 返回：
```json
{"logs": [], "source": "none", "service": "<service>",
 "message": "Log access not available for <service>. Self-hosted installations may need to configure the analytics stack or enable PostgreSQL CSV logging."}
```
- **返回**： `{logs: [{timestamp|null, level|null, message|null, metadata|null}], source: 'analytics'|'csv'|'none', service: <enum>, message?}`。analytics 成功时无 message 字段。

### 3.25 `get_advisors`（`get_advisors.ts`）
- **description**: `Gets security or performance advisory notices for the database. Based on Supabase Splinter linting rules. Helps identify issues like missing RLS policies, unindexed foreign keys, and other common problems.`
- **输入**： `type: enum('security'|'performance')`（必填）。
- **执行**： 按 type 选取检查组，逐个 `executeSqlWithFallback`（单项失败仅 warn 并跳过）：
  - **securityChecks**（顺序）： `rls_disabled_in_public`(0013/warning)、`policy_exists_rls_disabled`(0007/warning)、`rls_enabled_no_policy`(0008/error)、`auth_users_exposed`(0002/error)。每条 SQL 产出 `code/name/level/description/detail/remediation/affected_object` 列（SQL 原文见 `get_advisors.ts` L46-125，含精确的 remediation 文本如 `'Enable RLS with: ALTER TABLE ' || quote_ident(...) || ' ENABLE ROW LEVEL SECURITY;'`）。
  - **performanceChecks**（顺序）： `unindexed_foreign_keys`(0001/warning)、`missing_primary_keys`(0004/warning，排除全部 Supabase 内部 schema 列表见 L172)、`unused_indexes`(0005/info)、`duplicate_indexes`(0009/warning)（L128-220）。
  - 每行规整：缺省值 `name→checkName`、`level→'warning'`、detail/remediation/affected_object 缺省为 null；按 level 排序（error=0, warning=1, info=2）。
- **返回**： `{issues: [{code, name, level, description, detail|null, remediation|null, affected_object|null}], type, total_count}`。

### 3.26 `get_storage_config`（`get_storage_config.ts`）
- **description**: `Gets storage configuration for Supabase Storage buckets. Returns bucket settings including file size limits, allowed MIME types, and public/private status.`
- **输入**： `bucket_id?: string`（`Optional bucket ID to get config for a specific bucket. If omitted, returns all buckets.`）。
- **执行**： ① `storage` schema 存在性检查，缺失 → `{buckets: [], global_config: {max_file_size_limit: null, bucket_count: 0}}`；② 桶查询（bucket_id 提供则 `WHERE id = '<转义>'`）`SELECT id, name, public, file_size_limit, allowed_mime_types, avif_autodetection, owner::text, created_at::text, updated_at::text FROM storage.buckets [WHERE ...] ORDER BY name`；③ 全局统计 `SELECT MAX(file_size_limit) as max_file_size_limit, COUNT(*) as bucket_count FROM storage.buckets`。
- **返回**： `{buckets: [...], global_config: {max_file_size_limit: number|null, bucket_count: number}}`（统计查询异常时 bucket_count 回退为 buckets.length）。

### 3.27 `update_storage_config`（`update_storage_config.ts`）—— `privilegeLevel: 'privileged'`
- **description**: `Updates storage configuration for a Supabase Storage bucket. Can modify file size limits, allowed MIME types, and public/private status.`
- **输入**： `bucket_id: string`（必填）；`file_size_limit?: number min 0`（`Maximum file size in bytes (0 or null for no limit)`）；`allowed_mime_types?: string[]`（`Array of allowed MIME types (e.g., ["image/png", "image/jpeg"]). Empty array means all types allowed.`）；`public?: boolean`。
- **执行**： ① storage schema 缺失 → `{success:false, bucket:null, message:'Storage schema not found - Storage may not be configured'}`；② 桶存在性（id 单引号转义）缺失 → `{success:false, bucket:null, message:"Bucket '<id>' not found"}`；③ 动态 SET：`file_size_limit = 0 → 'NULL'`（0 即无限制），否则原数值；`allowed_mime_types` 空数组 → `NULL`，否则 `ARRAY['<转义后各类型', ...]`；`public = true/false`；④ 无任何更新字段 → `{success:false, bucket:null, message:'No updates specified. Provide at least one of: file_size_limit, allowed_mime_types, or public'}`；⑤ 追加 `updated_at = NOW()`，`executeSqlWithFallback(client, UPDATE, false)`（readOnly=false）：
```sql
UPDATE storage.buckets
SET <updates逗号连接>
WHERE id = '<escaped>'
RETURNING id, name, public, file_size_limit, allowed_mime_types
```
- **返回**： 成功 `{success:true, bucket:{...返回行}, message:"Successfully updated bucket '<id>'"}`；0 行 → `{success:false, bucket:null, message:'Update executed but no rows returned'}`；更新错误 → `{success:false, bucket:null, message:"Failed to update bucket: <err>"}`；解析失败 → `{success:false, bucket:null, message:"Failed to parse update result: <err>"}`（**全部结构化返回，不抛错**）。

### 3.28 `list_table_columns`（`list_table_columns.ts`）—— `privilegeLevel: 'regular'`
- **description**: `Lists all columns for a table with detailed metadata including types, defaults, and constraints.`
- **输入**： `schema: string = 'public'`（`Schema name (defaults to public).`）；`table: string`（`Table name to get columns for.`，必填）。
- **执行**： 标识符校验 `^[a-zA-Z_][a-zA-Z0-9_$]*$`，违规抛 `` `Invalid schema name: ${schema}` `` / `` `Invalid table name: ${table}` ``。SQL（内插，含 char 长度/numeric 精度换算、identity/generation 信息，全文见 L67-108）→ `executeSqlWithFallback` → `isSqlErrorResponse` 时抛 `result.error.message || 'Failed to list table columns'`。
- **返回**： `[{column_name, data_type, is_nullable, column_default|null, description|null, ordinal_position, character_maximum_length|null, numeric_precision|null, numeric_scale|null, is_identity, identity_generation|null, is_generated, generation_expression|null}]`。
- **空结果**： 抛 `` `Table ${schema}.${table} not found or has no columns.` ``。

### 3.29 `list_indexes`（`list_indexes.ts`）—— `privilegeLevel: 'regular'`
- **description**: `Lists all indexes in the database with their definitions and sizes. Can filter by schema and/or table.`
- **输入**： `schema?`（`Filter indexes by schema name.`）；`table?`；`include_system: boolean = false`（`Include indexes on system tables.`）。
- **执行**： 标识符校验（同上，违规 `Invalid schema name: ...`/`Invalid table name: ...`）。`include_system=false` 时排除 schema 列表 `('pg_catalog','information_schema','pg_toast','auth','storage','extensions','graphql','graphql_public','pgbouncer','realtime','supabase_functions','supabase_migrations','_realtime')`；schema/table 过滤 `schemaname = '...'`/`tablename = '...'`。主查询（`pg_indexes` join `pg_class/pg_namespace/pg_index/pg_am`，输出 `pg_get_indexdef(ix.indexrelid,0,true) AS columns`、`pg_size_pretty(...)`、`ORDER BY schemaname, tablename, indexname`，全文见 L87-106）。
- **返回**： `[{schema_name, table_name, index_name, index_type, is_unique, is_primary, is_valid, columns, size, definition}]`。

### 3.30 `list_constraints`（`list_constraints.ts`）—— `privilegeLevel: 'regular'`
- **description**: `Lists all constraints (PRIMARY KEY, FOREIGN KEY, UNIQUE, CHECK, EXCLUDE) in the database. Can filter by schema, table, and type.`
- **输入**： `schema?`；`table?`；`constraint_type?: enum('PRIMARY KEY','FOREIGN KEY','UNIQUE','CHECK','EXCLUDE')`；`include_system = false`。
- **执行**： 标识符校验同上；type→contype 映射 `{PRIMARY KEY:'p', FOREIGN KEY:'f', UNIQUE:'u', CHECK:'c', EXCLUDE:'x'}`；SQL 基于 `pg_constraint`（contype CASE 转可读名、`ARRAY(...)` 列名按序、`pg_get_constraintdef`，`ORDER BY nspname, relname, conname`，全文 L105-132）。
- **返回**： `[{schema_name, table_name, constraint_name, constraint_type, columns: string[], definition, is_deferrable, initially_deferred}]`。

### 3.31 `list_foreign_keys`（`list_foreign_keys.ts`）—— `privilegeLevel: 'regular'`
- **description**: `Lists all foreign key relationships in the database. Can filter by schema and/or table.`
- **输入**： `schema?`；`table?`；`include_system = false`（`Include foreign keys in system schemas.`）。
- **执行**： 标识符校验；include_system=false 排除 `('pg_catalog','information_schema','auth','storage','extensions','graphql','graphql_public','pgbouncer','realtime','supabase_functions','supabase_migrations','_realtime')`（注意：与 list_indexes 相比**少了 pg_toast**，用 `AND` 前缀拼接）。SQL 基于 `information_schema.table_constraints/key_column_usage/constraint_column_usage/referential_constraints` join `pg_constraint`，`WHERE tc.constraint_type = 'FOREIGN KEY'`（全文 L88-116）。
- **返回**： `[{constraint_name, schema_name, table_name, column_name, referenced_schema, referenced_table, referenced_column, update_rule, delete_rule, is_deferrable, initially_deferred}]`。

### 3.32 `list_rls_policies`（`list_rls_policies.ts`）—— `privilegeLevel: 'regular'`
- **description**: `Lists all Row Level Security (RLS) policies in the database. Can filter by schema and/or table name.`
- **输入**： `schema?`；`table?`。
- **执行**： 标识符校验；固定条件 `n.nspname NOT IN ('pg_catalog','information_schema','pg_toast')`；SQL 基于 `pg_policy`（polcmd 映射 r/a/w/d/*→SELECT/INSERT/UPDATE/DELETE/ALL；polpermissive→PERMISSIVE/RESTRICTIVE；roles `COALESCE(ARRAY(...), ARRAY['public'])`；`pg_get_expr(polqual/polwithcheck)`，全文 L77-105）。
- **返回**： `[{schema_name, table_name, policy_name, command, policy_type, roles: string[], using_expression|null, with_check_expression|null}]`。

### 3.33 `list_triggers`（`list_triggers.ts`）—— `privilegeLevel: 'regular'`
- **description**: `Lists all triggers on tables. Can filter by schema and/or table name.`
- **输入**： `schema?`；`table?`。
- **执行**： 标识符校验；固定条件 `NOT t.tgisinternal` + `n.nspname NOT IN ('pg_catalog','information_schema','pg_toast')`；SQL：tgtype 位运算解析 timing（&2→BEFORE，&64→INSTEAD OF，否则 AFTER）、level（&1→ROW/STATEMENT）、events 数组（&4 INSERT/&8 DELETE/&16 UPDATE/&32 TRUNCATE）、tgenabled→ENABLED/DISABLED/REPLICA/ALWAYS（全文 L79-112）。
- **返回**： `[{schema_name, table_name, trigger_name, trigger_timing, trigger_level, events: string[], function_schema, function_name, enabled}]`。

### 3.34 `list_database_functions`（`list_database_functions.ts`）—— `privilegeLevel: 'regular'`
- **description**: `Lists all user-defined database functions (stored procedures). Can filter by schema, name pattern, or language. Identifies SECURITY DEFINER functions which may have elevated privileges.`
- **输入**： `schema?`；`name_pattern?`（`Filter functions by name pattern (SQL LIKE pattern).`）；`language?`。
- **执行**： 标识符校验（schema/language）；name_pattern 校验 `^[a-zA-Z0-9_$%]+$`` 违规抛 `` `Invalid name pattern: ${name_pattern}. Use only alphanumeric, underscore, dollar sign, and % wildcard.` ``；固定条件排除系统 schema/`pg_temp_%` + `p.prokind = 'f'`；SQL 输出 `pg_get_function_arguments/pg_get_function_result/lanname/provolatile 映射 i/s/v→IMMUTABLE/STABLE/VOLATILE/prosecdef/obj_description`（全文 L92-112）。
- **返回**： `[{schema_name, function_name, arguments, return_type, language, volatility, security_definer, description|null}]`。

### 3.35 `get_function_definition`（`get_function_definition.ts`）—— `privilegeLevel: 'regular'`
- **description**: `Gets the full source code definition of a database function. Use argument_types if there are overloaded functions with the same name.`
- **输入**： `schema = 'public'`；`function_name: string`（必填）；`argument_types?: string`（`Argument types to disambiguate overloaded functions (e.g., "integer, text").`）。
- **执行**： 标识符校验（schema/function_name）；argument_types 校验 `^[a-zA-Z0-9_$,\s\[\]()]+$`` 违规抛 `` `Invalid argument types format: ${argument_types}` ``；WHERE `n.nspname='...' AND p.proname='...' [AND pg_get_function_arguments(p.oid) = '<argument_types>'] AND p.prokind='f' LIMIT 1`，SELECT 含 `pg_get_functiondef(p.oid) AS definition`（全文 L82-103）。
- **返回**： 单对象 `{schema_name, function_name, arguments, return_type, language, volatility, security_definer, definition}`。
- **空结果**： 抛 `` `Function ${schema}.${function_name}${argument_types ? `(${argument_types})` : ''} not found.` ``；错误 → `result.error.message || 'Failed to get function definition'`。

### 3.36 `get_trigger_definition`（`get_trigger_definition.ts`）—— `privilegeLevel: 'regular'`
- **description**: `Gets the full definition of a trigger, optionally including its function source code.`
- **输入**： `schema = 'public'`；`table: string`（必填）；`trigger_name: string`（必填）；`include_function: boolean = true`（`Include the trigger function source code.`）。
- **执行**： 三个标识符全部校验；SQL 同 list_triggers 的单条版 + `pg_get_triggerdef(t.oid, true) AS definition` + `include_function ? 'pg_catalog.pg_get_functiondef(p.oid)' : 'NULL' AS function_definition`（全文 L81-118）。
- **返回**： `{schema_name, table_name, trigger_name, trigger_timing, trigger_level, events, function_schema, function_name, enabled, definition, function_definition|null}`。
- **空结果**： 抛 `` `Trigger "${trigger_name}" not found on ${schema}.${table}.` ``。

### 3.37 `get_rls_status`（`get_rls_status.ts`）—— `privilegeLevel: 'regular'`
- **description**: `Checks if Row Level Security (RLS) is enabled on tables and shows the number of policies. Can filter by schema and/or table.`
- **输入**： `schema?`；`table?`。
- **执行**： 标识符校验；固定条件 `c.relkind = 'r'` + 排除全套 Supabase 内部 schema（含 pg_toast）；SQL：`c.relrowsecurity AS rls_enabled, c.relforcerowsecurity AS rls_forced, COUNT(pol.polname)::int AS policy_count`，LEFT JOIN pg_policy，GROUP BY（全文 L75-88）。
- **返回**： `[{schema_name, table_name, rls_enabled: bool, rls_forced: bool, policy_count: number}]`。

### 3.38 `list_available_extensions`（`list_available_extensions.ts`）—— `privilegeLevel: 'regular'`
- **description**: `Lists all PostgreSQL extensions available for installation, including those already installed.`
- **输入**： `show_installed: boolean = true`（`Include already installed extensions.`）；`name_pattern?: string`（`Filter by extension name pattern (SQL LIKE).`）。
- **执行**： name_pattern 校验 `^[a-zA-Z0-9_$%\-]+$`` 违规抛 `` `Invalid name pattern: ${name_pattern}. Use only alphanumeric, underscore, hyphen, dollar sign, and % wildcard.` ``；`show_installed=false` → `installed_version IS NULL`；SQL：
```sql
SELECT name, default_version, installed_version, installed_version IS NOT NULL AS is_installed, comment
FROM pg_available_extensions
[WHERE ...]
ORDER BY name
```
- **返回**： `[{name, default_version, installed_version|null, is_installed: bool, comment|null}]`。

### 3.39 `get_cron_job_history`（`get_cron_job_history.ts`）—— `privilegeLevel: 'regular'`
- **description**: `Gets execution history for pg_cron jobs including status and timing. Requires pg_cron to be installed.`
- **输入**： `jobid?: number`；`jobname?: string`；`limit = 100`（`Maximum number of records to return.`，**钳制 1..1000**：`Math.min(Math.max(1, limit), 1000)`）；`status?: enum('succeeded','failed')`。
- **执行**： jobname 校验 `^[a-zA-Z0-9_\-\s]+$`` 违规抛 `` `Invalid job name pattern: ${jobname}. Use only alphanumeric, underscore, hyphen, and space characters.` ``；pg_cron 扩展检查（`SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') as installed`），未安装抛 `'pg_cron extension is not installed. Install it with: CREATE EXTENSION pg_cron;'`，检查失败抛 `'Failed to check pg_cron extension status.'`；SQL（`cron.job` LEFT JOIN `cron.job_run_details`；`jobid → j.jobid = <n>`、`jobname → j.jobname ILIKE '%<jobname>%'`、`status → r.status = '<s>'`；`ORDER BY r.start_time DESC NULLS LAST LIMIT <safeLimit>`，全文 L118-133）。
- **返回**： `[{jobid, jobname|null, schedule, runid|null, status|null, start_time|null, end_time|null, return_message|null}]`。

### 3.40 `list_edge_function_logs`（`list_edge_function_logs.ts`）—— `privilegeLevel: 'regular'`
- **description**: `Lists execution logs for edge functions from the function_edge_logs table.`
- **输入**： `function_id?: string`（`Filter by function ID/slug.`，校验 `^[a-zA-Z0-9_\-]+$`` 违规抛 `` `Invalid function ID: ${function_id}. Use only alphanumeric, underscore, and hyphen characters.` ``）；`status_code?: number`；`errors_only?: boolean`（`Only show logs with errors (status >= 400).`）；`limit = 100`（**无钳制**，直接内插）。
- **执行**： `function_edge_logs` 表存在性检查（`information_schema.tables WHERE table_name = 'function_edge_logs'`）；检查失败抛 `'Failed to check for function_edge_logs table.'`；不存在抛：
```
'Edge function logs table (function_edge_logs) not found. This table is automatically created by Supabase when edge functions are invoked. Ensure edge functions have been executed at least once.'
```
（三段拼接为一条消息，含空格）。SQL（条件 `function_id = '<id>'`、`status_code = <n>`、`errors_only → status_code >= 400`；`request_duration_ms = EXTRACT(EPOCH FROM (request_end_time - request_start_time)) * 1000`；`ORDER BY request_start_time DESC LIMIT <limit>`，全文 L122-136）。
- **返回**： `[{execution_id|null, function_id, status_code|null, request_start_time, request_duration_ms|null, error_message|null, request_path|null, request_method|null}]`。

### 3.41 `get_index_stats`（`get_index_stats.ts`）—— `privilegeLevel: 'regular'`
- **description**: `Gets detailed statistics for a specific index including usage counts and size.`
- **输入**： `schema = 'public'`；`index_name: string`（必填）。
- **执行**： 双标识符校验（违规消息带后缀 `. Must be a valid SQL identifier.`：`` `Invalid schema name: ${schema}. Must be a valid SQL identifier.` `` / `` `Invalid index name: ${index_name}. Must be a valid SQL identifier.` ``）。SQL（`pg_stat_user_indexes` join `pg_index/pg_class/pg_am/pg_stat_user_tables`；`COALESCE(...,0)::bigint`；`pg_size_pretty`；usage_ratio = `ROUND((idx_scan/(seq_scan+idx_scan))*100, 2)::text || '%'`，分母 0 → NULL；`LIMIT 1`，全文 L77-106）。
- **返回**： 单对象 `{schema_name, table_name, index_name, index_type, is_unique, is_primary, is_valid, number_of_scans, tuples_read, tuples_fetched, index_size, table_size, index_size_bytes, table_size_bytes, usage_ratio|null}`。
- **空结果**： 抛 `` `Index "${index_name}" not found in schema "${schema}".` ``。

### 3.42 `get_vector_index_stats`（`get_vector_index_stats.ts`）—— `privilegeLevel: 'regular'`
- **description**: `Gets usage statistics and size information for pgvector indexes.`
- **输入**： `schema?`、`table?`、`indexname?`（描述分别为 `Filter by schema name.` / `Filter by table name.` / `Filter by index name.`）。
- **执行**： 三标识符校验（消息同 3.41 带 `. Must be a valid SQL identifier.`）；pgvector 扩展检查（`extname = 'vector'`），检查错误抛 `extensionCheck.error.message || 'Failed to check pgvector extension status.'`，未安装抛 `'pgvector extension is not installed. Install it with: CREATE EXTENSION vector;'`；SQL（CTE `vector_indexes`：`pg_indexes WHERE indexdef LIKE '%vector_%ops%'`，indexdef LIKE 判定 IVFFlat/HNSW/Unknown；主查询 join `pg_stat_user_indexes`，条件 `s.schemaname='<schema>'`/`s.relname='<table>'`/`s.indexrelname='<indexname>'`；`ORDER BY s.idx_scan DESC, index_size_bytes DESC`，全文 L115-145）。
- **返回**： `[{schemaname, tablename, indexname, index_type, idx_scan, idx_tup_read, idx_tup_fetch, index_size, index_size_bytes}]`。

### 3.43 `explain_query`（`explain_query.ts`）—— `privilegeLevel: 'privileged'`
- **description**: `Gets the execution plan for a SQL query. WARNING: With ANALYZE enabled, the query is actually executed which will modify data for write operations.`
- **输入**： `sql: string`（必填）；`analyze: boolean = false`；`format: enum('json','text','yaml','xml') = 'json'`；`verbose = false`；`costs = true`；`buffers = false`；`timing = true`；`settings = false`（描述原文见 L32-38，analyze 描述含 `WARNING: This WILL execute the query and modify data for write operations!`）。
- **执行**：
  1. `detectWriteQuery(sql)`：首关键词 INSERT/UPDATE/DELETE/TRUNCATE/DROP/ALTER/CREATE → high 置信写；正文含这些词 → medium（`MIXED/CTE`）；否则 SELECT/low。
  2. analyze 时生成 warnings：写+high → `⚠️ CRITICAL: ANALYZE will EXECUTE this <TYPE> query and MODIFY DATA!`；写+medium → `⚠️ WARNING: Query may contain <TYPE> operations. ANALYZE will execute the query.`；读 → `Note: ANALYZE will execute the query to measure actual timing.`
  3. EXPLAIN 选项组装顺序：`FORMAT <FORMAT大写>` → (`ANALYZE true`) → (`VERBOSE true`) → `COSTS <costs>` → (`BUFFERS true` 仅 analyze&&buffers) → (`TIMING <timing>` 仅 analyze) → (`SETTINGS true` 仅 settings)。最终 `EXPLAIN (<options逗号连接>) <sql>`。
  4. `executeSqlWithFallback(client, explainSql, isReadOnly)`，`isReadOnly = !analyze`（**analyze=true 时以读写模式执行**）。
  5. 结果解析：format=json → 取首行 `QUERY PLAN`（或 `query plan`）；若为数组取该数组并提取 `[0]['Planning Time']` / `[0]['Execution Time']`；其他格式 → rows 的 `QUERY PLAN`/`query plan`/原行数组。
- **返回**： `{query: sql, plan, format, analyzed: analyze, planning_time_ms?, execution_time_ms?, warnings?}`（warnings 空则省略字段）。
- **错误**： 统一抛 `` `Failed to explain query: ${errorMessage}` ``（含 `result.error.message || 'Failed to explain query'` 场景）。

---

## 4. categories（分组方式）

代码内**没有**任何分组/前缀机制（工具名即注册名，无 category 字段）。分组仅存在于 **README.md §3 工具总览**（文档层面）：

| README 分类 | 工具 | README 标注权限 |
|---|---|---|
| SQL 与执行计划 | `execute_sql`、`explain_query` | 特权 |
| 模式查看 | `list_tables`、`list_table_columns`、`list_indexes`、`list_constraints`、`list_foreign_keys`、`list_triggers`、`list_database_functions`、`get_function_definition`、`get_trigger_definition` | 常规 |
| 扩展与迁移 | `list_extensions`、`list_available_extensions`、`list_migrations`、`apply_migration` | 常规 / 特权 |
| 统计 | `get_database_connections`、`get_database_stats`、`get_index_stats`、`get_vector_index_stats`、`list_vector_indexes` | 常规 |
| 安全与 RLS | `list_rls_policies`、`get_rls_status`、`get_advisors` | 常规 |
| Auth 用户 | `list_auth_users`、`get_auth_user`、`create_auth_user`、`update_auth_user`、`delete_auth_user` | 常规 / 特权 |
| 存储 | `get_storage_config`、`update_storage_config`、`list_storage_buckets`、`list_storage_objects` | 常规 / 特权 |
| 实时 | `list_realtime_publications` | 常规 |
| 定时任务 | `list_cron_jobs`、`get_cron_job_history` | 常规 |
| Edge Functions | `list_edge_functions`、`get_edge_function_details`、`list_edge_function_logs` | 常规 |
| 开发辅助 | `generate_typescript_types`、`get_logs`、`rebuild_hooks`、`get_project_url`、`verify_jwt_secret` | 常规 / 特权 |

**代码级真实权限分级**（`privilegeLevel` 字段，缺省视为 `'regular'`）：
- **explicit privileged（8 个）**： `apply_migration`、`execute_sql`、`rebuild_hooks`、`delete_auth_user`、`create_auth_user`、`update_auth_user`、`update_storage_config`、`explain_query`
- **explicit regular（19 个）**： `verify_jwt_secret`、`get_vector_index_stats`、`list_edge_function_logs`、`list_table_columns`、`list_indexes`、`list_constraints`、`list_foreign_keys`、`list_rls_policies`、`list_triggers`、`list_database_functions`、`get_function_definition`、`get_trigger_definition`、`get_rls_status`、`list_available_extensions`、`get_cron_job_history`、`get_index_stats`、`list_table_columns`（同前）、`get_index_stats`（同前）、（其余见下）…完整清单：`verify_jwt_secret, get_vector_index_stats, list_edge_function_logs, list_table_columns, list_indexes, list_constraints, list_foreign_keys, list_rls_policies, list_triggers, list_database_functions, get_function_definition, get_trigger_definition, get_rls_status, list_available_extensions, get_cron_job_history, get_index_stats`
- **未标注（缺省 regular，16 个）**： `list_tables, list_extensions, list_migrations, get_database_connections, get_database_stats, get_project_url, generate_typescript_types, list_auth_users, get_auth_user, list_storage_buckets, list_storage_objects, list_realtime_publications, list_cron_jobs, list_vector_indexes, list_edge_functions, get_edge_function_details, get_logs, get_advisors, get_storage_config`

角色映射（`src/tools/types.ts`）：`service_role` → {regular, privileged}；`authenticated` → {regular}；`anon` → {}（无权限）；未知角色 → {regular}。

---

## 5. package.json（发布形态对照）

```json
{
  "name": "rds-supabase-mcp",
  "version": "0.1.0",
  "description": "Full-featured management MCP server for cloud-hosted Supabase instances without direct database access",
  "main": "dist/index.js",
  "bin": { "rds-supabase-mcp": "dist/index.js" },
  "files": ["dist", "README.md", "README.en.md", "LICENSE", "NOTICE"],
  "engines": { "node": ">=18" },
  "license": "MIT",
  "type": "module"
}
```
- 可执行名/包名：`rds-supabase-mcp`；MCP Server 声明名：`rds-supabase-mcp`，version `0.1.0`（与 package.json 一致）。
- 构建：`bun build src/index.ts --outdir dist --target node --banner "#!/usr/bin/env node"`。
- 运行依赖：`@modelcontextprotocol/sdk ^1.25.2`、`@supabase/supabase-js ^2.90.1`、`commander ^14.0.2`、`express ^5.2.1`、`jsonwebtoken ^9.0.3`、`pg ^8.17.1`、`zod ^4.3.5`。

---

## 6. 隐藏行为与默认值清单（Python 版必须逐字复现）

### 6.1 HTTP 传输模式（`src/server/http-server.ts` + `auth-middleware.ts`）
- 端点：`POST /mcp`（Streamable HTTP，**stateless**，`sessionIdGenerator: undefined`，每请求新建 transport+server）；`GET /mcp` → 405 `{error:'Method Not Allowed', message:'GET requests are not supported in stateless mode. Use POST for MCP requests.'}`；`DELETE /mcp` → 405 `{error:'Method Not Allowed', message:'Session termination is not supported in stateless mode.'}`；`GET /health` → `{status:'healthy'}`（无限流）。
- JWT 鉴权（仅 /mcp）：Bearer + HS256；`sub` 缺失 → `'Invalid token: missing subject (sub) claim'`；过期 → `'Token has expired'`；格式错 → `'Invalid Authorization header format. Expected: Bearer [token]'`；缺 header → `'Missing Authorization header'`；缺 token → `'Missing token in Authorization header'`；其他验证失败 → `` `Invalid token: <jwt库消息>` `` / 500 `'Failed to verify authentication token'`。userContext：`{userId: sub, email: email||null, role: role||'authenticated'}`。
- 限流：按 IP（`X-Forwarded-For` 首个优先）；响应头 `X-RateLimit-Limit/-Remaining/-Reset`；超限 429 `{error:'Too Many Requests', message:'Rate limit exceeded. Please try again later.', retryAfter}`；每 60s 清理过期条目。
- CORS：默认允许 `http://localhost:<port>`、`http://127.0.0.1:<port>`、`http://<host>:<port>`；支持 `*` 与 `http://xxx:*` 端口通配；不允许的 origin → OPTIONS 403 空 / 其他 403 `{error:'Forbidden', message:'Origin not allowed by CORS policy'}`；OPTIONS 合法 → 204。Allow-Headers: `Content-Type, Authorization, Accept, Mcp-Session-Id`；Expose: `Mcp-Session-Id`。
- 安全头：`X-Content-Type-Options: nosniff`、`X-Frame-Options: DENY`、`X-XSS-Protection: 1; mode=block`、`Strict-Transport-Security: max-age=31536000; includeSubDomains`、`Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`、`Referrer-Policy: no-referrer`、移除 `X-Powered-By`。
- 超时：默认 30000ms，504 `{error:'Gateway Timeout', message:'Request timed out after <ms>ms'}`；keepAliveTimeout=65000；内部错误 500 JSON-RPC `{jsonrpc:'2.0', error:{code:-32603, message:'Internal server error'}, id:null}`。
- 优雅关闭：SIGINT/SIGTERM → `console.error('Shutting down...')` → `httpServer.stop()` → `process.exit(0)`。

### 6.2 关键默认值汇总表

| 位置 | 参数/行为 | 默认值 |
|---|---|---|
| execute_sql | `read_only` | `false` |
| explain_query | `analyze/verbose/buffers/settings` | `false`；`format='json'`；`costs/timing=true`；**readOnly = !analyze** |
| list_auth_users | `limit/offset` | `50 / 0` |
| list_storage_objects | `limit/offset` | `100 / 0` |
| get_logs | `limit` | `100`（zod 限 1..1000） |
| list_edge_function_logs | `limit` | `100`（**不钳制**） |
| get_cron_job_history | `limit` | `100`（钳制 1..1000） |
| generate_typescript_types | `included_schemas / output_filename` | `['public'] / 'database.types.ts'`（output_filename 实际被忽略） |
| list_table_columns / get_function_definition / get_trigger_definition / get_index_stats | `schema` | `'public'` |
| list_indexes / list_constraints / list_foreign_keys | `include_system` | `false` |
| list_available_extensions | `show_installed` | `true` |
| get_trigger_definition | `include_function` | `true` |
| executeSqlWithFallback | `readOnly` | `true` |
| executeSqlViaRpc / executeSqlViaServiceRoleRpc | `readOnly` | `false` |
| get_logs 时间窗 | — | 近 24 小时（analytics 与 pglog 两路均是） |
| get_logs 级别缺省 | analytics `COALESCE(level,'info')`；pglog severity 映射 ERROR→error/WARNING→warn/LOG→info/其他→debug | — |

### 6.3 其他必须复现的细节
- **audit 日志**（execute_sql）：`[AUDIT] SQL execution by user=<email||userId||'unknown (stdio mode)'> role=<role>: <queryPreview>`，200 字符截断格式 `... [truncated, <n> chars total]`。
- **identifierPattern** `^[a-zA-Z_][a-zA-Z0-9_$]*$`（get_vector_index_stats/get_index_stats 版本违规消息带 `Must be a valid SQL identifier.` 后缀；其余工具版本不带）；`likePattern`（list_database_functions `^[a-zA-Z0-9_$%]+$`；list_available_extensions `^[a-zA-Z0-9_$%\-]+$`）；`argTypesPattern` `^[a-zA-Z0-9_$,\s\[\]()]+$`；`jobNamePattern` `^[a-zA-Z0-9_\-\s]+$`；`functionIdPattern` `^[a-zA-Z0-9_\-]+$`；generate_typescript_types 的 `sanitizeSchemaName` `^[a-zA-Z_][a-zA-Z0-9_-]*$`。
- **SQL 内插 vs 参数化**：auth 用户五件套、list_storage_objects、apply_migration 走 pg 参数化（`$n`）；其余工具标识符经正则校验后**直接字符串内插**（含 `get_edge_function_details` 的 `'`→`''` 转义、get_storage_config/update_storage_config 的同类转义、get_cron_job_history 的 ILIKE、list_edge_function_logs 的直接内插）。
- **空结果语义**：`execute_sql` 与多数 list 类返回 `[]`；`get_edge_function_details` 空 → `null`；`get_auth_user`/`get_function_definition`/`get_trigger_definition`/`get_index_stats` 空 → **抛错**（各消息见 §3）；`list_table_columns` 空表 → 抛错；`rebuild_hooks`/`update_storage_config`/`generate_typescript_types` 永不抛错（结构化 success:false）。
- **`execute_sql` RPC 空结果**：内嵌 plpgsql 函数 `COALESCE(jsonb_agg(t),'[]'::jsonb)` 保证空集 → `[]`。
- **`handleSqlResponse` 的 code 插值**： `` `SQL Error (${result.error.code}): ${result.error.message}` ``（code 可能为 undefined → 字符串 "undefined"）。
- **stdio 模式横幅**（L406-413）逐行复现：
```
WARNING: Stdio mode has NO authentication. All tools (including privileged
         tools) are accessible. Only use stdio mode with trusted local clients.
         For remote access, use HTTP mode with JWT authentication.
```
- **启动日志**：`Initializing Selfhosted Supabase MCP Server (transport: <t>)...`、`Supabase client initialized successfully.`、`RPC function 'public.execute_sql' status: Available|Unavailable`、`MCP Server connected to stdio.`、`Starting MCP Server in HTTP mode...` 等（Python 版建议保留同等 stderr 日志行为）。
- **ListTools 的 inputSchema 来源**：每个工具文件内的**静态 `mcpInputSchema` 对象**（非 zodToJsonSchema 动态生成；import 了 zodToJsonSchema 但未使用）。注意个别静态 schema 与 zod 有差异（如 create_auth_user 的 mcpInputSchema 里 role 带了 `default: 'authenticated'` 而 zod 无 default；generate_typescript_types 的 output_path 描述在静态 schema 中更详细），Python 版应分别按原文复刻两份定义。
- **错误透传总链**：工具抛 Error → index.ts catch → `{content:[{type:'text', text:"Error executing tool <name>: <msg>"}], isError:true}`；McpError（未知工具/权限拒绝）不经此包装。
</task_result>
</task>