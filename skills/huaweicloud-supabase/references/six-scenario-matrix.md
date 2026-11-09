# 六场景子场景验收矩阵（0.3.8a1）

2026-11-07。目标是六场景完整交付；本版不是六场景全量验收完成。代码实现、离线验证、用户报告的旧版真云验证、新版真云验收分开记录。所有新增写工具未在本机调用业务云API。敏感请求统一见[本地引用](local-requests.md)。

通用步骤：发现能力和目标→查询状态→具体预览→用户确认→提交一次→任务/同步结果→资源回查→业务验证。通用异常：未知提交查本地账本和资源，不重复写、不删除账本；恢复配置是新的授权变更。下表每行均为独立验收单位。

| 用户目标 | 前置条件 | 操作步骤 | MCP工具／接口 | 确认内容 | 成功标准 | 异常恢复 | 当前状态 | 待确认项 |
|---|---|---|---|---|---|---|---|---|
| 创建：默认选配 | 用户成本/可用性要求；局点AZ | 明确Single→查候选→说明取舍 | plan_supabase_creation、list_supabase_flavors；GET ai-application/supabase/flavors | 具体候选与费用来源，不猜价格 | 需求逐项有对应配置；Ha明确不支持 | 无候选不编造 | 规划+候选查询已实现；真云未验 | 完整规格组合、报价与配额 |
| 创建：托管已有PG | PG可托管且有授权；秘密本地提供 | 查候选→核对网络/版本→准备请求 | list_supabase_manageable_instances、create_supabase_application；GET候选/POST创建 | PG身份及影响 | 应用+PG关联+业务可用 | 不删除原PG、不盲重试 | 候选查询+Single本地引用提交已实现；真云未验 | 后端PG版本/密码策略与实际完成验证；结构已按SDK更新 |
| 创建：新建PG | 网络、配额、计费授权 | 查资源→明确应用和PG配置→预览 | plan_supabase_creation；create_supabase_application；POST ai-application/supabases | 应用/PG规格、费用、归属 | 双资源及关联就绪、登录验证 | 区分新旧资源，部分成功不自动清理 | Single按需新PG提交已实现；真云未验 | 后端容量/版本边界实测；包周期与tags未开放 |
| 删除：仅应用 | normal应用、明确目标 | 预览→确认→删→任务→列表回查PG | delete_supabase_application；DELETE应用 | 不可逆、业务中断、PG保留计费 | 应用消失且PG独立回查保留 | 400不能单独证明删除完成 | 已实现；旧版用户真云验证应用消失 | PG独立存续证据、新版回归 |
| 删除：连同PG | 所有关联应用与PG影响清单 | 评估→另行具体授权 | 未开放PG级联 | 所有关联业务、备份、费用 | 全部批准对象删除且无误伤 | 不以直接删PG模拟级联 | 未实现 | 后端反向级联、保护、部分失败契约 |
| 访问：绑定已有EIP | EIP身份/地址、网络权限 | 预览→绑→任务→详情→连通 | change_supabase_eip；PUT public-eip | 公网暴露、费用、IP与应用 | 绑定状态+受控网络连通 | 查原状态，恢复需新计划 | 已实现；旧版真云验证 | 新版业务连通回归 |
| 访问：解绑EIP | 明确断网影响 | 省略IP字段→预览→解绑→回查 | change_supabase_eip | 中断公网，不代表释放计费 | 解绑状态+预期访问变化 | 新计划重新绑定 | 已实现；旧版真云验证 | 新版回归 |
| 访问：证书选择/购买 | 原生证书入口、适用规则 | 查询→核对域名有效期→用户购买 | plan_supabase_ssl仅规划；无购买工具 | 费用与适用范围 | 可选且兼容证书 | 不索取私钥、不自动支付 | 未实现原生发现/购买 | CCM接口/响应、计费授权 |
| 访问：SSL开启/关闭 | 有效证书ID（开启）；URL影响评估 | 预览→切换→任务→应用→Auth URL/登录验证 | change_supabase_ssl；POST switch-ssl | 两方向中断、证书、关联URL | 协议状态+登录/重定向正确 | 不全局替换URL；恢复新计划 | 已实现；真实验证未完成 | 证书资源、业务回归 |
| 访问：应用改密 | 受保护本地请求别名 | 预览→确认→提交→任务→可信登录验证 | change_supabase_application_password；PUT password | 仅应用账号、下游更新 | 新密码登录成功；秘密不进聊天 | 不承诺旧密码自动恢复 | 本版实现；离线验证 | 完整密码策略、真云登录验收 |
| 安全组：查询/选组 | 独立VPC入口与项目 | 分页列表→详情→关联影响核对 | list/show_supabase_security_group(s)；VPC v3 | 目标组、所有共享资源 | 组/规则可读且关联明确 | 权限/响应不符停止 | 本版实现；离线验证 | 共享关联全集接口、真云权限 |
| 安全组：建组 | VPC授权、命名 | 预览→创建201→详情 | create_supabase_security_group；POST security-groups | 不自动挂载、不等于放通 | 返回ID且回查组存在 | 未知提交查资源不重建 | 本版实现；离线验证 | 实际关联/挂载流程 |
| 安全组：放通入口 | 规范来源CIDR、实际端口、共享影响 | 查规则→预览→增201→回查/连通 | add_supabase_security_group_rule；POST security-group-rules | 单端口TCP、来源和共享范围 | 精确规则存在且授权来源可达 | 重复规则拒绝；不放宽到全网 | 本版实现；离线验证 | 真云响应/规则归一化差异 |
| 安全组：移除规则 | rule属于指定group | 查归属→预览→删204→回查 | delete_supabase_security_group_rule | 断网与共享业务影响 | 规则不存在、业务符合预期 | 不自动重建；新授权恢复 | 本版实现；离线验证 | 真云回查、共享影响确认 |
| ApiKey：列表/筛选 | 应用与权限 | 详情→分页筛选 | list_supabase_api_keys；GET api-keys | 只元数据 | 列表无明文、过滤正确 | 不猜测未支持过滤 | 已实现；旧版只读通过 | name/时间完整约束 |
| ApiKey：查看/复制值 | 独立安全输出通道 | 授权→指定key→可信交付 | deliver_supabase_api_key；GET api-key/{id}/value | 明文授权与审计 | 目标用户获取、模型/日志无值 | 不用Shell/HTTP绕过 | 本版本地文件交付已实现；真云未验 | Windows ACL/可信客户端验收；复制无独立API |
| ApiKey：重置 | 唯一normal key、下游切换计划 | 元数据→预览→重置→任务→旧新状态 | reset_supabase_api_key；PUT reset | 高风险、下游更新 | 旧deleted新normal+下游业务 | 不用旧ID找新值、不猜最新记录 | 已实现；旧版真云验证切换 | job新key可靠关联、安全交付、下游验证 |
| 业务：注册/匿名开关 | 当前Auth配置 | 部分更新→任务→回查→业务 | update_supabase_auth_flags；PUT auth-config | 精确布尔项和访问影响 | 值正确且注册行为符合要求 | 原值恢复新计划；可reconcile原accepted开关 | 已实现；旧版真云闭环 | 新版Agent回归 |
| 业务：URL配置 | 回调/域名设计明确 | 本地引用→预览→提交→Auth回查 | update_supabase_auth_config | 具体URL、不改无关SMTP主机 | 登录/重定向业务正常 | null清空不支持；旧配置恢复新计划 | 本版实现；离线验证 | 清空语义、真实登录 |
| 业务：GitHub OAuth | AppID/Secret本地输入 | 本地引用→预览→更新→配置/登录 | update_supabase_auth_config | provider启停、清空影响 | OAuth登录成功且Secret不返回 | 禁用不同时改嵌套配置 | 本版实现；离线验证 | 第三方回调实测 |
| 业务：SMTP | 邮箱服务资源与授权 | 本地引用→更新→配置/发信验证 | update_supabase_auth_config | 目标SMTP、认证/业务影响 | 用户收到正确邮件、秘密不返回 | 失败查任务/配置，不盲重发写 | 本版实现；离线验证 | 真实发信、完整字段业务校验 |
| 业务：邮件模板 | 已确认mailer_confirmation模板 | 配置subject/url→更新→发信验证 | update_supabase_auth_config | 模板URL与内容适用 | 实际邮件符合配置 | 未知模板拒绝 | 已实现该模板；离线验证 | 其他模板枚举和清空语义 |
| 业务：OBS Storage | OBS桶/身份权限，本地完整AKSK | 本地引用→预览→更新→任务→OBS验证 | update_supabase_storage；PUT storage | 桶、费用、启停、完整凭据替换 | 读写符合预期且无秘密外泄 | 省略SK须已启用且同AK；恢复新计划 | 本版实现；离线验证 | 省略规则已由SDK补充；真实对象读写待验 |

VPC依据：原生[建规则](https://support.huaweicloud.com/api-vpc/vpc_apiv3_0016.html)及[建组](https://support.huaweicloud.com/intl/en-us/api-vpc/vpc_apiv3_0010.html)契约。Console代理接口不能直接替代原生签名入口。

## 2026-11-07 SDK资料补充裁决
以资料后半部分完整definitions为实现依据：仅Single、已有PG必填三字段、新PG必填项包括volume/flavor等；前半片段较简略，不据此放宽。Delete完整paths为202，与旧版真实验证一致；早期200片段不覆盖该结论。应用删除保留PG，不承诺保留应用关联关系。规格AZ对象与早期字符串描述不一致，候选查询原样受限返回，不猜可售status枚举。
Storage省略SK部分更新规则已明确；实现前置已启用/同AK保护。证书仅CCM代理信息，原生发现/购买仍外部步骤；PG反向级联不实现为应用级联。创建密码/容量/版本限制由后端校验，本地不宣称全量策略校验。原始资料仅本地读取，未提交公开仓。
