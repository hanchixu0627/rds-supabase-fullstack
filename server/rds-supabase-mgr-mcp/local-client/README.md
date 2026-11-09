# 本地 MCP + Skill 一条命令启动包

不使用 npm，不需要 Node 或手动安装 Python。当前首版支持 Windows x64；业务 MCP/Skill 为0.3.8a2，客户端包装为0.1.0-dev。**安装逻辑测试已通过，Windows端到端尚待实测，不是生产正式版。**

先安装并登录 Claude Code，保证 `claude` 在终端可用。将本交付 ZIP 解压，在解压目录的 PowerShell 仅运行：

```powershell
powershell -NoProfile -File .\start-supabase.ps1
```

这一个命令会准备独立Python、离线安装MCP依赖、安装完整专项Skill、配置默认只读的MCP、自检并打开Claude；之后可直接描述需求。Claude首次信任确认仍需用户完成；不绕过宿主权限。启动使用严格MCP配置，避免加载原来用户级的重复Supabase服务。

再次使用执行同一命令，复用已安装环境和账本，不重复安装；不得为重试云写删除目录。下载/解压是获取文件步骤，不声称这条本地命令能凭空下载未知位置的ZIP。无需 npm、账号注册或手工复制 Skill/编辑 JSON。

首次无匹配 Python 时，随包固定 uv 将联网获取 Python3.12.10并校验；Python依赖随包离线提供。网络受限时会报准备失败，不能假定完全离线可安装。uv来自官方PyPI固定版本，构建时按SHA256校验；不使用远程脚本执行。不关闭TLS、不绕过执行策略，不写全局PATH/注册表。依赖预发行风险见BLOCKERS.md。

程序使用 `%LOCALAPPDATA%\HuaweiCloudSupabaseLocal`，其中 `runtime` 是独立环境、`workspace` 是专用Claude项目、`state\plans.sqlite3` 是固定账本。新客户端不迁移旧联调环境与账本，默认只读；旧环境未决写计划仍须在原环境核对，不要通过新账本绕过。Windows目录ACL由用户按公司要求管理。

云凭据、endpoint、project和可信CA须已由本地可信配置注入启动终端，才能查询真实云资源；本工具不会读取其他MCP配置中的秘密或索取聊天明文。仅继承当前进程环境，不擅自从注册表复制凭据。安装与初始欢迎提示不调用业务云API；Claude/模型网络仍按用户已有配置。

安装失败不激活Claude。重复执行时若已安装配置或Skill被改动，停止并保留文件，不悄悄覆盖。修改权限/升级旧版本不是此首版安装入口的功能；本轮用于只读体验，写验收继续使用已有受控环境。

维护者可用 `powershell -NoProfile -File .\start-supabase.ps1 -NoLaunch` 只验收安装，不启动模型会话。在Windows核对：无Python也可准备环境、工具发现、Skill发现、重启不重装、权限默认只读、原用户配置未变化。未实际执行的项目不能记录为通过。

资料依据：[uv Python管理](https://docs.astral.sh/uv/guides/install-python/)、[Claude CLI](https://code.claude.com/docs/en/cli-reference)。
