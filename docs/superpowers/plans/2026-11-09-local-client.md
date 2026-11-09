# 本地一条命令接入实施计划

用户已确认：不发布 npm；Windows 本地一条命令完成运行环境、MCP、Skill、客户端接入并启动 Claude。

- [ ] 使用固定版本 uv Windows 二进制及已校验0.3.8a2依赖，自动准备独立 Python3.12.10，无需 Node/npm或系统Python。
- [ ] PowerShell 入口校验交付清单、独占安装锁，复用本地运行环境；不改全局环境、不关闭TLS、不绕过执行策略。
- [ ] Python 安装逻辑先测试再实现：失败不激活、已安装不重复安装、修改配置保留、账本固定、旧安装不覆盖。
- [ ] 完整 Skill 放独立项目目录，生成只读 MCP 配置。使用 strict-mcp-config 避免加载旧 Supabase 实例；启动 Claude 而非仅输出下一步命令。
- [ ] 制作本地ZIP和校验文件，更新指南；Windows 端到端未测明确记录，不冒充已通过。
- [ ] 同步个人开发分支及组织 develop 文档/代码PR，不发布npm。

版本：客户端local-client-0.1.0-dev，业务MCP/Skill仍0.3.8a2。使用用户继承凭据，不把凭据写配置。首次缺Python时联网下载受校验运行时；网络受限应报阻塞，不能承诺全离线零前置。
