# 华为云 Supabase MCP 与 Skill 用户指南

文档更新：2026-11-09。

通过 Claude Code，你可以用自然语言查询和管理华为云 Supabase。MCP 连接云服务接口，专项 Skill 帮助澄清需求、组织操作步骤并说明变更影响。

## 安装与启动

**前提：Windows x64，Claude Code 已安装并能正常对话。无需预装 Python 或 Node.js。**

从[下载页](https://github.com/hanchixu0627/rds-supabase-fullstack/releases/tag/supabase-local-client-v0.1.0-dev)获取 `supabase-local-client-0.1.0-dev-windows-x64.zip`，使用同页 SHA256 文件核对后解压。在解压目录打开 PowerShell，运行：

```powershell
powershell -NoProfile -File .\start-supabase.ps1
```

脚本会准备运行环境、安装 MCP 和专项 Skill，并在检查通过后打开 Claude。首次使用时，按 Claude 的提示确认项目信任和工具连接。

打开后，直接用自然语言说：

> 查询当前 Supabase MCP 能力，说明可以做什么，本次不要访问云资源。

已有云访问配置时，可以继续说：

> 列出我的 Supabase 应用，不做修改。

以后使用时，在解压目录重新运行上述脚本即可。程序会复用已安装的环境和操作记录。

## 连接你的云资源

查询真实云资源前，请准备具有对应权限的云身份，确认电脑可访问服务入口，并通过公司允许的本地环境配置方式，为启动终端设置下列变量。修改后重新启动客户端。

| 配置 | 用途 |
|---|---|
| `SUPABASE_RDS_ENDPOINT` | 对应局点的原生 RDS HTTPS 入口，不是 Console 网页地址 |
| `HUAWEICLOUD_PROJECT_ID` | 对应局点的项目 |
| `HUAWEICLOUD_ACCESS_KEY`、`HUAWEICLOUD_SECRET_KEY` | 测试或使用身份的 AK/SK |
| `HUAWEICLOUD_SECURITY_TOKEN` | 使用临时凭据时提供匹配的 token |
| `SUPABASE_VPC_ENDPOINT` | 安全组场景使用的原生 VPC 入口 |
| `REQUESTS_CA_BUNDLE` | 环境需要自定义可信 CA 时提供 PEM 文件路径 |

不要把凭据发送到聊天或提交到仓库。程序继承启动终端的配置，不复制其他 MCP 配置中的秘密。若凭据仅配置在旧 MCP 中，并不会自动迁移。模型代理与云 API 网络按实际环境分别配置，不关闭 TLS 验证。

## 可以怎样提问

| 场景 | 自然语言示例 |
|---|---|
| 创建 | 我想用已有 PG 创建 Single 应用，先说明需要哪些信息，不提交。 |
| 删除 | 删除这个应用会影响什么，底层 PG 是否保留？先不要删除。 |
| 访问控制 | 查询应用〈ID〉的 EIP 和 SSL 配置。 |
| 安全组 | 查看这个安全组，说明是否已有指定来源的 8443 入站规则。 |
| ApiKey | 列出应用〈ID〉的 ApiKey 元数据，不查看明文。 |
| 业务配置 | 查询应用〈ID〉的匿名注册和账号注册开关。 |

当前启动包默认只读，可用于查询资源和了解操作要求。执行变更需要由环境负责人配置写权限，并在查看目标、参数和影响后确认具体计划。当前启动包不提供写权限切换或旧环境迁移功能。

## 安装位置与操作记录

自动安装到 `%LOCALAPPDATA%\HuaweiCloudSupabaseLocal`：

- `runtime`：独立 MCP 运行环境。
- `workspace`：自动进入的 Claude 使用目录，含 MCP 配置及完整专项 Skill。
- `state\plans.sqlite3`：固定本地执行账本，不要删除来重试请求。

启动时只加载本入口的 MCP 配置，避免与原用户级 Supabase 服务重复连接；不改动旧测试环境，不迁移旧账本。旧环境有未决变更时，继续在原环境核对。

## 版本与问题处理

业务 MCP/Skill：**0.3.8a2**；本地启动包：**0.1.0-dev 开发预览**。

- 当前为开发预览，Windows 完整安装及 Claude 交互尚待验收，请先在测试环境使用。
- 首次没有匹配 Python 时需要联网下载运行时；其余依赖随包提供。
- 暂只支持 Windows x64。macOS、Linux、ARM64 不使用此包。
- 如果启动失败，保留错误反馈即可；不要删除账本、关闭TLS或全局放宽执行策略。
- 如果已安装配置被修改，程序会停止并保留文件，不自动覆盖。升级及写权限迁移另行处理。

维护旧环境可阅读[历史手工安装说明](MANUAL_INSTALL_LEGACY.md)。实现和维护说明见[本地启动器](../local-client/README.md)，完整功能边界见[六场景矩阵](SIX_SCENARIO_MATRIX.md)。
