# Supabase MCP + Skill：本地一条命令使用指南

文档更新：2026-11-09。本指南只介绍新的本地启动包，不使用 npm。

## 开始使用

**前提：Windows x64，Claude Code 已安装并能正常对话。无需预装 Python 或 Node.js。**

从[下载页](https://github.com/hanchixu0627/rds-supabase-fullstack/releases/tag/supabase-local-client-v0.1.0-dev)获取 `supabase-local-client-0.1.0-dev-windows-x64.zip`，使用同页 SHA256 文件核对后解压。在解压目录打开 PowerShell，只执行：

```powershell
powershell -NoProfile -File .\start-supabase.ps1
```

等待安装完成，**Claude 会自动打开**。你不需要手动安装依赖、复制 Skill、编辑 MCP 配置或另起 MCP 服务。

程序自动完成：准备独立 Python → 安装 MCP → 安装专项 Skill → 配置只读连接 → 离线自检 → 启动 Claude。Claude 首次要求确认项目或工具时，按提示确认；安装器不会跳过客户端信任检查。

打开后，直接用自然语言说：

> 查询当前 Supabase MCP 能力，说明可以做什么，本次不要访问云资源。

已有云访问配置时，可以继续说：

> 列出我的 Supabase 应用，不做修改。

**以后使用仍执行同一个命令。** 程序复用已安装环境，不重复安装，不清空执行账本。

## 连接你的云资源

安装只解决工具接入，云访问还需要你自己的身份和网络。请通过公司允许的本地环境配置方式，使启动终端获得下列变量；已有这些配置的用户无需重复设置。

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

此启动包默认只读，不会因一句“确认”自动开启写权限。当前简化入口用于安装和只读体验；真实写入仍须操作方在受控环境启用权限，并对具体变更预览确认。功能清单不等于所有场景已完成真实验收。

## 文件放在哪里

自动安装到 `%LOCALAPPDATA%\HuaweiCloudSupabaseLocal`：

- `runtime`：独立 MCP 运行环境。
- `workspace`：自动进入的 Claude 使用目录，含 MCP 配置及完整专项 Skill。
- `state\plans.sqlite3`：固定本地执行账本，不要删除来重试请求。

启动时只加载本入口的 MCP 配置，避免与原用户级 Supabase 服务重复连接；不改动旧测试环境，不迁移旧账本。旧环境有未决变更时，继续在原环境核对。

## 当前版本与遇到问题时怎么办

业务 MCP/Skill：**0.3.8a2**；本地启动包：**0.1.0-dev 开发预览**。

- 已完成安装逻辑测试、Windows依赖解析和交付文件校验；**Windows端到端安装及Claude交互仍待实际验收**。
- 首次没有匹配 Python 时需要联网下载并校验运行时；依赖随包提供。该包不是“完全离线、无任何前置”的安装。
- 暂只支持 Windows x64。macOS、Linux、ARM64 不使用此包。
- 如果启动失败，保留错误反馈即可；不要删除账本、关闭TLS或全局放宽执行策略。
- 如果已安装配置被修改，程序会停止并保留文件，不自动覆盖。升级及写权限迁移另行处理。

下载和解压属于获取文件；本指南的“一条命令”指本地包到位后，一次完成安装、配置并进入Claude。

维护旧环境才需要阅读[历史手工安装说明](MANUAL_INSTALL_LEGACY.md)。实现和维护说明见[本地启动器](../local-client/README.md)，完整功能边界见[六场景矩阵](SIX_SCENARIO_MATRIX.md)。
