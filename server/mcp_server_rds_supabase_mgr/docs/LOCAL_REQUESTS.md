# 本地敏感请求引用与新增工具（0.3.8a1）

工具参数只传 `application_id`、`request_ref`、`confirm`、`plan_id`。凭据由操作方在模型会话之外输入本地JSON文件，设置绝对路径 `SUPABASE_REQUESTS_FILE` 后启动MCP。不把该文件存入代码仓、交付包、云盘或聊天。此文件不是密钥保险库；Windows必须由操作方配置仅运行账户和必要管理员可读的NTFS ACL，当前程序不自动验证Windows ACL。Unix强制当前用户所有且文件权限0600；拒绝符号链接、重复JSON键、超64KiB文件、任意路径别名。

文件格式是 `{ "操作别名": { "该操作的请求字段": "本地填写" } }`。别名仅1–64位字母、数字、下划线和连字符。工具会重新读取同一别名；内容改变使原计划签名不匹配。预览不含密码、OAuth Secret、SMTP密码、AK/SK或URL查询字符串。不要在非秘密字段放秘密。本机权限不能防止拥有同等文件权限的其他软件读取该文件。

| 工具 | 引用内容 | 限制与回查 |
|---|---|---|
| change_supabase_application_password | application_password | 只改Supabase账号；不接受instance_password。结构检查不是后端完整密码策略。任务完成后由测试人员登录验证；不回读密码 |
| update_supabase_auth_config | enable_account_sign_up、enable_anonymous_users、api_external_url、site_url、allow_redirect_urls、github_oauth_provider、email_oauth_provider、email_template_config | 仅提交显式字段，不补默认值；使用show_supabase_auth_config回查非秘密配置，再实际验证登录/邮件 |
| update_supabase_storage | enabled、type=obs、bucket_name、ak、sk | 启用要求完整桶名和凭据；禁用不能携带非空凭据。省略SK保留语义未采纳；任务与OBS访问分别验收 |

Auth嵌套字段：
- github_oauth_provider：enable_github、oauth_client_id、oauth_client_secret、redirect_uri。
- email_oauth_provider：enable_email_sign_up、enable_email_auto_confirm、smtp_config。
- smtp_config：smtp_host、smtp_port（整数1–65535）、smtp_user、smtp_pwd、smtp_admin_email、smtp_sender_name、smtp_max_frequency（非负整数）。
- email_template_config：当前仅 `mailer_confirmation` 对象，包含subject和/或url。
- allow_redirect_urls：逗号分隔URL字符串，最多10个；仅http/https，不允许URL内嵌用户名密码/片段。
- null清空、空嵌套对象、未知字段拒绝；禁用GitHub或邮件注册时，该provider只传对应false开关，避免后端清空配置造成误解。

上述为已确认结构的受限子集，后端完整策略仍权威。任何未支持的用户要求必须显式说明，不能静默移除后提交。写请求仍要求服务端开启写入、具体预览确认、目标normal且无current_actions、未保护、计划可执行。网络错误或响应不符记unknown，不能重试。

安全组工具使用单独 `SUPABASE_VPC_ENDPOINT`，同一项目身份、SDK签名和本地账本；缺入口不回退RDS。规则当前只支持单个TCP端口+规范CIDR，不支持全网/0。组和规则原生创建返回201，删规则返回204；202 dry-run不能当创建成功。需要人工核对组关联的全部资源；程序当前不能自动查询关联全集。已成功VPC写入记录保留accepted且无RDS job，回查后也不能自动解除/重放。

## SDK契约更新后的优先规则（同版补充）

Storage：首次启用必须SK。已启用组件更新可省略SK保持原值；MCP在提交前读取storage_component，只有enabled=true且AK与请求相同才允许省略，换身份须完整AK/SK。本节替代上文“省略SK未采纳”的早期描述。

创建：`create_supabase_application(request_ref, confirm=false, plan_id=null)`，DANGEROUS。引用对象必填name（4–64）、basic_config（region/vpc_id/subnet_id，可选time_zone）、version、mode=Single、flavor_ref、availability_zone（单AZ）、password、storage_component、显式manage_type。
- existed_instance：existing_instance包含instance_id、database_name（数据库用户名）、database_pwd；managed_instance省略或null。
- newly_instance：managed_instance包含datastore（type=PostgreSQL/version）、charge_info（仅charge_mode=postPaid）、flavor_ref、volume（type=CLOUDSSD/正整数size）、availability_zone（与应用一致）、security_group_id、password、enterprise_project_id。可选configuration_id、port（2100–9500）、data_vip。existing_instance省略或null。
- 顶层可选security_group_id和data_vip；不支持Ha、包周期、未确认tags结构或未知字段。local检查只保证已知结构；后端密码策略、PG最低版本、容量/可售范围及配额仍权威，不编造限制。创建时Storage启用必须全凭据。
- 返回202+job_id+application_id与可选instance_id/instance_job_id；分别观察资源任务。意外订单进入unknown，不能自动支付或重试。未接入X-Client-Token，幂等保护仅限当前本地账本；不能跨机器重复提交。

ApiKey：`deliver_supabase_api_key(application_id,key_id,delivery_ref,confirm=false,plan_id=null)`，DANGEROUS。引用对象为 `{ "output_file": "操作方选择的新文件绝对路径" }`。父目录须已存在、路径规范且非符号链接；Unix目录属于当前用户且0700，文件0600。Windows父目录须由操作方事先确认NTFS ACL仅受信用户可读，当前不自动核验。工具不返回文件路径或密钥，返回delivery_ref。需要本地写许可/写入开关，但云端只GET。

预览不创建文件；提交前核对应用和唯一normal key，独占创建文件后GET value，读取精确api_key字段、写文件并同步磁盘。不得覆盖已有文件；失败可能遗留空/部分文件，操作方核对后处理，Agent不能读取。输出文件、注册表和账本都不应置于Agent自动索引的工程目录。普通同权限AI/Shell仍可能读这些文件，隔离账户/宿主权限由部署方负责；这不是远程秘密保险库或已认证的码道安全控件。
