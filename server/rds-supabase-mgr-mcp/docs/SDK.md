# SDK 接入与迁移（0.3.7a1）

## 当前交付
MCP 使用华为云 Python SDK Core 处理 AK/SK 签名、可选 STS token、TLS 和请求发送，业务层沿用已核实 API 契约。它不是已发布的 Supabase UniSDK 或生成式 RDS Supabase 模型 SDK。SDK 底层仍发送 REST 请求；采用 SDK 不会使尚未上线的服务接口自动可用。

本轮核查可获取的 SDK Core/RDS 发布版本为 3.1.220；启动材料中的 3.1.222+、Supabase 方法名与任务状态模型不能作为已验证事实。生成式 SDK 到位后核对实际包、方法签名、请求/响应模型，再替换传输适配层；不改工具确认和 Skill 工作流。

## 配置
在可信的 MCP 宿主本地配置或受保护进程环境设置：

| 变量 | 用途 |
|---|---|
| SUPABASE_TRANSPORT=sdk_core | 显式启用 SDK；为兼容既有部署，未配置仍为 rest |
| SUPABASE_RDS_ENDPOINT | 已核验原生服务 HTTPS origin，不含路径；不是 Console 代理 |
| HUAWEICLOUD_PROJECT_ID | 目标项目 |
| HUAWEICLOUD_ACCESS_KEY / HUAWEICLOUD_SECRET_KEY | 身份凭据，不作为工具输入 |
| HUAWEICLOUD_SECURITY_TOKEN | 使用临时凭据时设置，与 AK/SK 配套 |
| HUAWEICLOUD_MCP_READ_ONLY=true | 首次联调保持只读 |
| SUPABASE_ENABLE_WRITES=false | 默认禁用云端写入 |

示例见 examples/mcp-sdk.example.json，不含凭据。SDK 模式不使用 HUAWEICLOUD_AUTH_TOKEN。凭据在客户端启动时读取；更新凭据后重启，并重新预览确认。无 Token/AKSK 自动回退或浏览器 Cookie 复用。不要将凭据发给模型或写入仓库。

先运行 `python -m mcp_server_supabase.diagnostics check`（仅语法/依赖检查），再运行 `python -m mcp_server_supabase.diagnostics offline`（隔离凭据，无云调用）。真实只读检查需在可访问测试环境按 WORKSTATION.md 显式启用。当前无法用离线测试证明服务接受 AK/SK、签名路径正确或 IAM 权限完整。

## 能力和恢复
已实现的查询、SSL、EIP、仅删应用、ApiKey 重置、注册开关均共享 SDK 适配器，工具契约不变。创建、安全组、改密和敏感配置不会因为接入 SDK 被自动开放，见 BLOCKERS.md。

保留写前预览、10分钟计划、目标状态复查、凭据绑定、本地持久防重放、未知结果核对。SDK 禁用自动重试与重定向；202只表示受理。任务终态仍未确认，不采用示例中的 Completed 等推测值。SDK 原始异常不对外输出，也不记录带资源 URL 的底层异常日志；保留工具层审计和脱敏错误。

SDK Core 在完整接收后执行 1MiB 响应检查，不等同于 REST 适配器的流量读取上限；流式限流和服务端响应规格需生产加固。超时为连接10秒/读取30秒，不是整个任务总时限。

## 验收与后续
本地 HTTP fixture 使用真实 SDK 签名/序列化，检查空 body、SSL null、分页、错误、防重放及凭据切换；不声称已做真实云、Windows实机或码道验收。
待完成：正式生成式SDK及模型证据、服务入口/IAM策略、任务终态和状态回查、剩余六场景契约与秘密通道、依赖安全冲突、Windows实机及码道验收。SDK依赖版本升级后必须重跑适配器测试，包括内部日志钩子的兼容性。

## CA配置核实（0.3.8a2）
当前SDK Core3.1.220使用Requests Session；本程序未显式设置HttpConfig.ssl_ca_cert。SDK模式可通过进程级REQUESTS_CA_BUNDLE指向可信CA PEM，不能只用SSL_CERT_FILE就宣称SDK已配置CA。REST标准库传输与SDK的CA来源不同。不要关闭TLS或推测历史证书仍存在。CA/代理环境配置必须传入实际MCP子进程；模型服务代理和云API目标的直连规则分别核实。
