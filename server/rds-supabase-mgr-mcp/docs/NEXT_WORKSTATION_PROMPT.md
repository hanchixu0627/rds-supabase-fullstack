# 工作电脑执行Prompt：0.3.8a1增量验收

你负责Windows真实环境验证，不替代开发方修改标准发行包，不调用未授权写操作。

1. 从交付来源取得0.3.8a1 Windows x64/Python3.12 ZIP及同版archive-sha256.txt。核对ZIP哈希，解压新目录，保留0.3.6/0.3.7环境与账本。报告放包外。运行 `py -3.12 scripts/verify_delivery.py`、`scripts/install-development.ps1`、`.venv/Scripts/python.exe -m unittest discover -s tests`、`.venv/Scripts/python.exe -m mcp_server_supabase.diagnostics offline`。任一步失败停止依赖步骤，报告脱敏错误。
2. 核对实际加载版本、Skill版本和工具列表。0.3.8a1预期29个工具，其中新增应用改密、完整Auth、Storage、5个VPC工具、2个创建候选查询、Single创建提交和ApiKey本地文件交付。没有包周期创建、PG级联或证书购买工具；ApiKey交付只写操作方预置文件，不返回模型。
3. 仅在操作方授权的只读环境运行diagnostics check/readonly。RDS和VPC入口分别配置，不能用Console URL。保留有效TLS验证；本版没有合入跳过TLS补丁，缺CA就记录网络阻塞，不冒用旧版验证结果。代理按进程和目标域名处理，不改全局代理。不要读取/导出聊天AKSK。
4. 首轮新增只读：查询明确AZ/模式的Supabase规格、可托管PG、VPC组列表和详情。资源输出留工作电脑，带回字段名/类型/状态脱敏证据。安全组组ID应为原生UUID，规则请求使用单数对象。缺VPC入口不回退RDS。
5. 新增写操作需要操作方对具体隔离资源、字段、费用与恢复方案逐项授权；未授权先仅做预览。敏感字段由操作方在模型会话之外建立受ACL保护的SUPABASE_REQUESTS_FILE，AI只知道别名。不要读取注册表文件/文件内容、在聊天索取密码或回显秘密。Windows ACL须操作方确认，本版不会自动验证ACL。
6. 按场景逐项执行：Single新PG/已有PG创建、Auth URL/GitHub/SMTP/mailer_confirmation、Storage首次启用/省略SK更新、应用改密、VPC组/规则、ApiKey指定ID本地文件交付。一次只改一项；预览后确认同一plan，提交一次；RDS202查job→资源→业务，VPC201/204查资源→连通（没有RDS job）。不能把同步响应或任务completed当业务成功。密码验证用可信人工登录，SMTP验证收信，OAuth验证登录，OBS对象读写交受权测试人员完成。
7. TLS/权限/网络异常停止，不绕过；写结果未知inspect计划并查资源，不重放、不换账本。只有旧Auth开关支持reconcile；新增操作账本不自动解除。取消只针对未提交计划。回退是新的授权变更，不恢复API Key旧值，不自动清理用户原资源。
8. 使用随包Skill在Claude Code验证：含未知字段、缺入口、要求全网放行、预览后修改本地引用、取消、提交超时、部分成功、索取明文、要求Ha或包周期创建等对话。记录工具调用轨迹和预期是否满足；文档/离线测试不算Agent验收。
9. 输出包外报告：版本/工具列表/环境、每个子场景编号、请求是否提交、任务/资源/业务三层结果、恢复情况、脱敏错误类别、未执行项及原因。不给出凭据/密钥值/完整抓包。最后才安排码道联合验收。
