# Auth执行记录对账：0.3.7a1

## 本轮范围
新增reconcile_supabase_auth_plan，只处理已受理的注册/匿名布尔变更。对账不调用云写接口，不解除未知结果或其他场景。参数为plan_id、application_id及原预览中明确修改的enable_account_sign_up/enable_anonymous_users；必须与原计划完全一致，不添加其他当前值。

工具读取原记录中的job_id，不接受调用方指定任务。当前endpoint、project、凭据、目标、方法与请求体共同重算摘要，必须匹配原记录。查询原job为completed→查询正确且正常的应用→Auth字段必须为布尔并符合预期→SQLite事务把accepted变为verified并保存检查时间。任何不一致保持原记录，不自动重试写请求。

verified表示在resource_checked_at观察到任务及资源符合目标。business_verified和completion_verified仍为false，不能代替业务行为测试。旧plan仍不可重放；将来新变更必须新预览/确认。该机制不是云端幂等、资源锁或持续状态监控，无法消除读取后外部并发变更。

此工具更新本地账本，按WRITE权限保护：HUAWEICLOUD_MCP_READ_ONLY=false；可以并建议保持SUPABASE_ENABLE_WRITES=false进行对账。后者禁止云端写入，不禁止本地对账。若组织护栏阻止工具，不绕过。

## 兼容性与限制
保留原plans表结构，新增verification表，旧记录不丢失。历史Auth accepted计划只有在原参数、原凭据/入口/项目和原job均可验证时才可对账；不得为了对账重新使用已失效身份。prepared/submitted/unknown/cancelled/verified等状态均不执行解除。不提供人工强制解锁或任意绑定job功能。

升级前停MCP进程并备份稳定状态文件，升级后仍使用同一SUPABASE_STATE_FILE。不把测试fixture账本用于真云。若程序回退，不恢复陈旧账本覆盖后续执行历史。现阶段只有Auth支持该流程；SSL/EIP/删除/Key等未决记录仍按原保护策略处理。

## 测试目标
匹配任务与资源才结束；身份/参数/状态/布尔类型错误不结束；GET失败保留accepted；并发对账只能有一次成功；进程重启能读证据；旧SQLite数据保留；新计划可独立确认而旧计划仍不可重放。

## 验收基线
0.3.6a1用户报告在Windows源码editable安装通过87测、真实读写和专项Skill验证。云端验证使用工作电脑本地TLS跳过补丁，并非未修改发布包的安全连接验收。本轮不操作凭据，不复制内部原始资料，不合入未经专项验证的TLS跳过开关。0.3.7a1标准代码继续默认校验证书；可信CA/统一代理、秘密通道和剩余六场景为后续批次。不能要求工作电脑为测试本轮立即替换已通过的旧环境。
