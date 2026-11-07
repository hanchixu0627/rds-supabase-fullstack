# 补充资料采纳与任务观察（0.3.7a1）

## 本轮实施
- 应用列表请求固定type=supabase；返回对象仍须核验身份，不能将服务端过滤等同于授权。
- show_supabase_job按单个job对象、匹配任务ID解释Running/Completed/Failed；输出task_status为running/completed/failed/unknown。
- wait_supabase_job为只读工具：默认3次、间隔2秒；最多10次、间隔1–5秒，工具等待预算50秒。预算耗尽返回observation_exhausted，不等于云任务失败。SDK底层在途读取线程可能在自身网络超时后才退出，不再追加请求，也没有云端取消。
- 未知状态、空响应、ID不符、jobs数组不按成功解析；unknown停止本轮观察。鉴权/权限/网络错误停止，不自动更换凭据或重放写操作。任务刚受理时可能暂不可见，用户可在后续明确观察预算内再次查询。
- completed只表示任务层成功；resource_verified、business_verified和completion_verified仍为false。资源回查、业务验证和账本解除尚未实现，不承诺完整闭环。
- 任务输出不透传entities及自由文本fail_reason，失败细节由操作方在授权控制台核对，避免秘密进入模型。
- 删除和EIP预览补充保留资源、业务中断和费用边界；不承诺“可再次操作”就是无损回滚。

## 证据与冲突处置
官方RDS[指定ID任务接口](https://support.huaweicloud.com/api-rds/rds_08_0001.html)定义响应为job对象，状态包含Running/Completed/Failed，终态process为空。故不使用资料中的jobs[0]或100%完成门槛。此公开契约仍须在Supabase测试环境确认适配，不代表已实测。

| 补充信息 | 采纳结论 / 剩余证据 |
|---|---|
| SDK方法签名 | 材料仍注明待发布核对，不能作为已存在的生成式SDK；继续使用SDK Core |
| 创建嵌套字段与包周期订单 | 更新需求基线；仍缺密码完整约束、PG版本/容量与计费限制、秘密引用通道、实时候选与响应关联；暂不开放提交。order_id不是job_id，不自动支付 |
| STS改用GlobalCredentials | 不采纳。已安装SDK中GlobalCredentials参数为domain_id，不支持示例project_id；项目级BasicCredentials附加security_token保持不变 |
| 401/403刷新并重试 | 不采纳自动重放；鉴权失败交由操作方核实，刷新后重启并重新确认未提交方案 |
| Storage启用SK必填 / 省略SK保留 | 同一资料仍冲突；需请求校验和更新逻辑的字段矩阵，暂不开写入 |
| VPC规则单对象、创建v3 | 与既有v2创建/v3规则数组证据冲突；待实际API版本和SDK序列化模型对应，不能直接替换 |
| PG端口5433 | 不作为默认；以实际实例端口核验 |
| 修改instance_password、启停 | 超出既定六场景应用密码边界，本轮不扩展 |
| Key重置“立即失效” | 仅agent成功原子切换时失效；HTTP202不代表旧Key已经失效，新Key关联仍待确认 |
| 证书SDK方法、购买/费用 | 方法及适用证书产品仍需实际包/官方契约核对，不猜测采购接口、价格或免费结论 |

内部补充资料原文不进入产品仓库和下载包。本文仅记录实现选择及待验证边界。

## 验收增量
匹配ID+Completed+空process→任务completed而业务未验证；错误ID/jobs数组/未知状态→unknown；Running观察耗尽→仍running且预算耗尽；Failed立即停止；401/403停止；仅GET且无账本变更。REST与SDK Core两条传输均回归。Windows、真实云、Agent与码道验收独立记录。
