# 工作电脑执行Prompt：Auth对账增量验收

将以下内容交给工作电脑AI。目标版本0.3.7a1；不得将下面步骤全部当作已获真实云写授权。

## 任务与边界
你负责Windows增量验收，不重新开发专项Skill，不操作、输出或持久化新的AK/SK，不修改系统/用户级全局环境，不删除执行账本，不自动升级其他依赖。码道验收最后安排。
已通过的0.3.6a1环境必须保留：原测试使用editable安装及TLS跳过本地补丁。本轮0.3.7a1没有合入该TLS开关，不要认为设置SUPABASE_INSECURE_SSL就生效。未经可信CA或明确批准的测试补丁方案，先完成离线验收并报告网络阻塞；不要自行关闭TLS、复制覆盖整份旧客户端或将补丁版报告为标准发行版。

## 1. 固定基线
记录OS/Python、MCP/SDK/core版本、实际Agent/模型版本、旧代码补丁diff、Skill来源和已通过用例编号。报告存放包外，脱敏后交付。不要收集全部环境变量或导出凭据。报告中不声称单元测试等价于Skill行为验收。
保存当前稳定状态文件的路径。停MCP进程后备份该文件到受保护本地位置；报告仅使用账本代号。不得恢复旧副本覆盖后续执行记录。

## 2. 独立安装与离线验收
从0.3.7a1开发Release下载指定Windows x64/Python3.12 ZIP和SHA256，核对后解压新目录。不要修改清单文件，安装前不要写报告到解压目录。保留原安装。
运行：
```powershell
py -3.12 .\scripts\verify_delivery.py
& .\scripts\install-development.ps1
& .\.venv\Scripts\python.exe -m unittest discover -s .\tests
& .\.venv\Scripts\python.exe -m mcp_server_supabase.diagnostics offline
```
各命令非零退出立即停在该步骤。不要绕过依赖校验或全局关闭执行策略。记录实际测试数和输出；只在真实执行后标通过。

## 3. 接入版本和网络
使用新venv Python绝对路径启动 `-m mcp_server_supabase.main`；加载包内完整skill目录。确认tools/list包含reconcile_supabase_auth_plan及原Auth工具。配置仅作用于MCP子进程：既有正确endpoint/project、sdk_core、稳定SUPABASE_STATE_FILE。模型代理和云API代理分开，保留原模型服务连接；按批准网络策略设置服务域名NO_PROXY例外。
先READ_ONLY=true、ENABLE_WRITES=false跑check和授权readonly；不能以配置通过替代TLS/网络/权限通过。如果旧环境可用而新环境失败，记录差异，不偷偷回退到旧服务继续宣称新版本通过。

## 4. 优先验证已有Auth accepted计划（只读云，无需新云写）
操作者选择一个自己明确掌握原参数和目标、且当前目标仍存在的accepted Auth计划。如果没有，不伪造或修改SQLite数据，转第5项等待具体写授权。
在操作者允许更新本地账本后，仅给MCP进程设置：
HUAWEICLOUD_MCP_READ_ONLY=false
SUPABASE_ENABLE_WRITES=false
重启服务，确保同一账本与身份。共享护栏仍有效，不用其他工具绕过。
调用inspect_supabase_plan，随后reconcile_supabase_auth_plan，传原plan_id、application_id和原预览中修改的布尔字段，不能追加其他字段，不传job_id。
若原值已被恢复，预期对账拒绝而账本仍accepted，这是正确行为，不为使它通过而再次改云状态。找不到历史目标也不得解除。
成功标准：原任务completed；工具回查目标与Auth值；返回verified/resource_verified=true，有检查时间；business_verified=false。记录MCP调用轨迹，确认对账过程中没有POST/PUT/DELETE。再inspect核对持久化记录。结束后恢复本地只读权限。

## 5. 仅当需要新增测试记录时：申请一项具体云写授权
列出隔离应用、开关原值/新值、恢复步骤和影响，让操作者确认后再执行。没有批准不修改资源。
获批准后：启用云写→按原流程预览/确认提交一次→观察任务→关闭云写、保留本地WRITE→对账→实际业务验证。恢复原值是独立变更，另行预览确认，并对恢复计划做同样核对。若失败/未知不重试、不删除账本。
禁止为了验证防重放而重复提交真实已完成变更；重复/并发/异常测试优先使用本地测试用例。两次调用对账中第二次被拒绝属于当前明确设计，不代表云操作失败。

## 6. Skill行为增量
固定一个模型，读取专项Skill的Auth对账规则。验证：
- 能区分accepted、task completed、resource verified、business verified；不能把verified宣称为业务成功。
- 用户说“再做一次”时，不复用旧plan或把对账当作新写授权。
- 对账不匹配、unknown、不支持场景或只读拦截时停止，不改库、不换身份、不循环。
仅在批准测试条件内使用真实资源；其他情形用离线/隔离模拟验证。

## 7. 返回报告
版本与包校验；是否有本地补丁；安装/测试结果；网络和TLS模式；Agent及模型；每项用例通过/失败/未执行及脱敏轨迹；对账前后状态；资源/业务验证分别记录；是否恢复权限及配置；缺陷复现步骤。
不要输出AK/SK、完整请求头、密码或原始数据库文件。不得将工作目录或整个环境上传GitHub。
