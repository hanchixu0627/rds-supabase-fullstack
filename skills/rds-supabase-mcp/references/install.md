# 一句话动态安装（AI Agent 执行路径）

面向 AI Agent 的最短安装流程：收集三项连接信息，写入客户端 MCP 配置，验证即完成。本 MCP 服务器在 Web 全栈开发流程中随实例动态接入：RDS Supabase 实例完成创建或选定后，配置信息（网关 URL 与 API Key）方可获得，随即按本文一次执行到位。完整安装说明（Docker 部署、环境变量全表、护栏规则、execute_sql 函数部署）见 mcp-installation-guide.md。

## 需向用户收集的三项信息

| 环境变量 | 含义 | 形态 |
|---|---|---|
| SUPABASE_URL | 实例网关基础 URL（Kong 统一入口） | 协议 + 地址 + 端口 |
| SUPABASE_ANON_KEY | 匿名 API Key（anon 角色 JWT） | eyJ 开头的 JWT 字符串 |
| SUPABASE_SERVICE_ROLE_KEY | service_role API Key | eyJ 开头的 JWT 字符串；SQL 执行与用户管理必需 |

要点：

- 三项信息由 Web 全栈开发流程注入或由用户提供，逐字核对，不做推断
- SUPABASE_URL 是网关地址，不是数据库直连地址
- service_role key 绕过 RLS：仅安装到可信环境；首次接入可在 env 中叠加 `"HUAWEICLOUD_MCP_READ_ONLY": "true"` 先行只读验证
- 密钥只写入本地客户端配置，不得提交到仓库或出现在日志中

## 前置条件

- 客户端环境已安装 uv（含 uvx）：`curl -LsSf https://astral.sh/uv/install.sh | sh`
- 数据库侧已部署 `sql/mcp-execute-sql.sql` 加固函数；未部署时仅 execute_sql 不可用，不影响其余工具（见 mcp-installation-guide.md）

## 配置模板（stdio，本地推荐）

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
        "SUPABASE_URL": "<SUPABASE_URL>",
        "SUPABASE_ANON_KEY": "<SUPABASE_ANON_KEY>",
        "SUPABASE_SERVICE_ROLE_KEY": "<SUPABASE_SERVICE_ROLE_KEY>"
      }
    }
  }
}
```

## 配置样例（stdio，已填充，值为演示用）

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
        "SUPABASE_URL": "http://supabase.example.com:8443",
        "SUPABASE_ANON_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.<anon 载荷>.<anon 签名>",
        "SUPABASE_SERVICE_ROLE_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.<service_role 载荷>.<service_role 签名>"
      }
    }
  }
}
```

## 远程部署接入（streamable-http）

服务器经 Docker 部署（Dockerfile 见 `server/mcp_server_rds_supabase/`）后，客户端仅需：

```json
{
  "mcpServers": {
    "rds-supabase": {
      "type": "streamable_http",
      "url": "http://<部署主机>:8000/mcp"
    }
  }
}
```

## 执行步骤

1. 向用户收集三项信息（上表），逐字核对
2. 将模板中的 `<...>` 占位符替换为实际值，写入所用客户端的 MCP 配置——常见位置：opencode 的 `opencode.jsonc`、Claude Desktop 的 `claude_desktop_config.json`、Cursor 的 `.cursor/mcp.json`，均为 `mcpServers` 结构
3. 重启客户端或重载 MCP 配置；首次启动 uvx 需拉取依赖，稍候
4. 验证：
   - `get_project_url` 返回值应与 SUPABASE_URL 一致
   - `list_tables` 返回表清单（或明确的错误说明）
   - 完整验证清单见 verification-method.md
5. 安装完成后向用户报告：接入方式（stdio / streamable-http）、只读模式状态、execute_sql 可用性

## 失败排查

- 依赖拉取失败：检查网络；私有仓库需配置 Git 凭证
- 401 / 403：核对密钥与 URL（应为网关地址，非数据库地址）
- execute_sql 报函数缺失：部署 `sql/mcp-execute-sql.sql`（见 mcp-installation-guide.md）
- 其余错误码与含义见 related-tools.md
