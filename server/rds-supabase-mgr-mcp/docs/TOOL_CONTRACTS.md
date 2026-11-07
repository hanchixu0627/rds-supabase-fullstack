# MCP 工具契约

契约版本 v0.4；运行包版本见 ../README.md。本文件区分已提供工具和目标能力；目标能力不意味着可调用。内部 REST 路径和抓包保留在本地证据库，不在这里复刻。

## 通用输入输出

输入以 tools/list 公布的 schema 为准。所有工具拒绝未知顶层字段；不得将未知字段值回显到错误。凭据不作工具参数。application_id/key_id/job_id 均使用查询所得真实标识，不靠名称猜测。
写工具默认 confirm=false，返回 status=confirmation_required、application_id、action、changes、resource_path、plan_id、expires_at、execution=not_executed，以及适用的 warnings/follow_up。该预览目前不代表已做在线可执行性验证。
执行须同参数 confirm=true + plan_id，服务端写开关开启且未只读；服务端检查身份/参数摘要与当前目标状态。HTTP 202 返回 status=accepted、job_id、complete=false；不代表完成。
错误沿用共享核心 error.code/message/hint 等字段；调用方同时检查结构化 error，不能仅检查 MCP is_error。未知参数错误不附带原始参数值。

## 本轮提供的工具

| 工具 | 输入（?可选） | 输出/语义 | 风险 |
|---|---|---|---|
| get_supabase_capabilities | 无 | 已实现子集、缺失能力；cloud_verified=false，不探测云状态 | READ |
| plan_supabase_creation | manage_type=newly_instance/existed_instance | planning_only，缺失契约；不是执行方案，无提交 | READ |
| plan_supabase_ssl | enable_ssl?=true | 证书选择步骤/缺口；无提交 | READ |
| list_supabase_applications | limit?=10, offset?=0 | 应用列表（可能含其他类型），脱敏并限长 | READ |
| show_supabase_application | application_id | 应用状态；非完成证明 | READ |
| list_supabase_api_keys | application_id, limit?=10, offset?=0, status?, key_type?, key_id?, sort_key?=created_time, sort_dir?=desc | 元数据白名单；name/时间过滤尚未开放 | READ |
| show_supabase_auth_config | application_id | 配置查询，秘密排除 | READ |
| show_supabase_job | job_id | 原始状态证据、completion_verified=false；不推断终态 | READ |
| change_supabase_ssl | application_id, enable_ssl, cert_id?, confirm?, plan_id? | 开启需证书ID；关闭null；不自动改URL | WRITE |
| change_supabase_eip | application_id, is_bind, public_ip_id?, public_ip_address?, confirm?, plan_id? | 绑定需要ID和IPv4；解绑不得携带非空绑定参数 | WRITE |
| delete_supabase_application | application_id, confirm?, plan_id? | 仅删应用保留PG；无请求体 | DANGEROUS |
| reset_supabase_api_key | application_id, key_id, confirm?, plan_id? | 重置，无明文；提交前按应用和ID查询唯一normal记录，新记录关联仍待补齐 | DANGEROUS |
| update_supabase_auth_flags | application_id, enable_account_sign_up?, enable_anonymous_users?, confirm?, plan_id? | 至少一个明确布尔值；省略/null不修改 | WRITE |
| inspect_supabase_plan | plan_id | 本地 state/job_id/expires_at，completion_verified=false | READ |
| cancel_supabase_plan | plan_id | 仅 prepared→cancelled；重复取消幂等；不取消云任务 | WRITE（本地账本） |

本地取消不受 SUPABASE_ENABLE_WRITES 云写开关约束，但仍服从共享核心只读/保护规则。被只读策略阻断时停止操作并等待计划失效；禁止删除账本绕过。未知计划返回 MCP_NOT_FOUND；已提交计划拒绝取消。

## 目标工具族（未冻结签名，不得按下表虚构调用）

| 场景 | 待提供的业务能力 | 冻结签名前置 |
|---|---|---|
| 创建 | 发现候选、要求覆盖、推荐、预览、提交、结果查询 | 创建字段依赖/响应/资源归属 |
| 删除 | 关联影响查询、级联方案及执行 | 完整影响范围、保护和部分失败契约 |
| 访问 | 证书发现/适用性、受控改密、费用引导 | 原生CCM契约、安全输入；采购范围决策 |
| 安全组 | 列表详情、建组、规则变更方案和执行 | 原生鉴权/响应/共享影响证据 |
| ApiKey | 过滤查询、受控查看值、重置后定位 | 明文通道、新旧记录关联字段 |
| 业务配置 | 配置查询、非敏感差异、受控局部更新 | 字段清空/保留规则及秘密引用 |

## 目标结果模型与兼容

最终结果需独立表达 submission、task、resource_verification、business_verification 四个维度。该模型是设计要求，当前返回仍以现有字段为准；未迁移前 Skill 不得假定字段已经存在。任务终态只能映射有契约依据的值；未验证使用 unknown/not_checked。
未来适配层以业务动作、非敏感结果和分类错误为边界，REST 与 SDK 不直接暴露各自模型到 Skill。字段删除/语义变更需要新契约版本和兼容矩阵；新增可选字段先验证旧 Skill。

0.3.2a1：ApiKey输出白名单为id/name/status/type/created_time/updated_time；响应包裹data/total_count不符则拒绝。重置前检查不替代后端授权/状态校验。

## 0.3.7a1增量
任务单次判定、有界只读观察及补充资料冲突处置见[采纳与验收说明](SUPPLEMENT_REVIEW.md)。任务completed不等于资源/业务验收，账本不自动解除。创建信息已补充，秘密通道及剩余约束仍待完成。

0.3.7a1更新：Auth accepted计划可按[对账契约](RECONCILIATION.md)验证并结束；unknown及其他动作不解除。业务验收、资源并发控制和完整秘密通道仍待完成。

## 0.3.8a1 新增工具

总计29个工具；新增12个。`change_supabase_application_password`、`update_supabase_auth_config`、`update_supabase_storage`只接受application_id/request_ref/confirm/plan_id，schema和安全边界见[本地引用](LOCAL_REQUESTS.md)。应用改密为DANGEROUS，Auth/Storage为WRITE；沿用应用状态检查、两阶段确认、异步202/job和本地防重复账本。

VPC工具：list_supabase_security_groups(limit=10,marker=null)、show_supabase_security_group(group_id)、create_supabase_security_group(name,confirm=false,plan_id=null)、add_supabase_security_group_rule(group_id,source_cidr,port=8443,confirm=false,plan_id=null)、delete_supabase_security_group_rule(group_id,rule_id,confirm=false,plan_id=null)。查为READ、建组WRITE、规则增删DANGEROUS。独立VPC入口；原生v3单对象；创建201/删除204，无RDS job。回查与业务成功另验，ledger保留accepted。

新增create_supabase_application(request_ref,confirm=false,plan_id=null)与deliver_supabase_api_key(application_id,key_id,delivery_ref,confirm=false,plan_id=null)，均为DANGEROUS，安全输入/输出和结构见LOCAL_REQUESTS.md。

创建候选：list_supabase_flavors(az_code,mode)和list_supabase_manageable_instances()为READ；返回creation_ready=false，不能当创建提交/费用报价或完整分页库存。
