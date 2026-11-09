# 工作电脑联调工具（码道协同前使用）

当前版本0.3.7a1，开发联调包，不是发布候选版本。Python>=3.10；开发验证使用3.12。准备项目虚拟环境并安装本地共享核心和MCP。不要把本项目未发布的包名当作可直接从公共包源下载的正式发行物。

## 一、不访问云的检查

在安装完成的虚拟环境中运行：

```sh
python -m mcp_server_supabase.diagnostics offline
```

使用隔离临时账本，去除继承的云身份/服务配置，通过真实stdio进程执行工具发现、能力查询、创建规划、SSL规划、SSL本地预览与取消。不会查询或修改云资源。它验证协议和本地流程，不验证真实API。

```sh
python -m mcp_server_supabase.diagnostics check
```

检查Python/包存在性、HTTPS服务地址格式、项目ID格式、所选传输的Token或AK/SK是否存在且不含换行。不输出配置值，不发请求；cloud_ready仅表示配置格式齐全，不能解释成身份有权限或网络连通。
退出码：0=本项检查通过；2=缺配置/未授权探测；1=检查失败。stdout为JSON摘要，可由测试人员保存；stderr不转发子进程原始错误内容。

## 二、工作电脑上的只读真实联调

先由接口同事确认原生API入口、网络及测试身份权限。浏览器可以登录不证明本地进程可直连。通过可信本机配置注入：
- SUPABASE_RDS_ENDPOINT：原生HTTPS origin，不含控制台路径。
- HUAWEICLOUD_PROJECT_ID：测试项目。
- HUAWEICLOUD_AUTH_TOKEN：测试身份Token，不通过命令行参数或聊天传递。

SDK Core模式已实现AK/SK及可选STS：设置SUPABASE_TRANSPORT=sdk_core，使用HUAWEICLOUD_ACCESS_KEY、HUAWEICLOUD_SECRET_KEY、可选HUAWEICLOUD_SECURITY_TOKEN；无需Token。详见SDK.md。devkit自动凭据读取尚未实现，不抓Cookie充当解决方案。

仅获得真实只读联调授权后执行：

```sh
python -m mcp_server_supabase.diagnostics readonly --allow-cloud-read
python -m mcp_server_supabase.diagnostics readonly --allow-cloud-read --application-id APP_ID
python -m mcp_server_supabase.diagnostics readonly --allow-cloud-read --job-id JOB_ID
```

第一条查询应用列表；指定应用后增加详情和Key元数据；指定任务后单次查询任务。CLI强制只读和云写关闭，不提供任意工具名或云写模式。查询摘要不含原始资源/任务字段；契约需要的脱敏终态样例仍应由后端/测试按受控流程记录，不能从摘要推断成功。

## 三、真实写场景执行单（工具具备，但此CLI不自动执行）

1. 明确测试资源、允许变更、费用、恢复与清理责任。
2. 正常MCP客户端查询目标/状态；不能使用离线诊断的fixture作真实资源。
3. 生成实际预览，核对参数和影响，用户确认。
4. 经授权开启写配置，使用同一计划提交一次；环境/身份变化须重新预览。
5. 保留plan/job关联；查询任务与资源。终态契约不明确则记录未决。
6. 超时先查记录，不重放。取消本地prepared计划不等于取消云任务。
7. 保存脱敏证据，关闭缺陷后回归。

这一步可以使用独立MCP测试客户端，无需码道。测试工具不是获取真实写操作授权的替代物。

## 四、交付清单与固定窗口

码道联合验收安排在真实API和发布预验收之后。提前准备本地包、共享核心依赖、固定依赖、目标平台离线依赖（如需要）、Skill、工具契约、测试证据、配置模板、校验和、升级回退说明。先验证目标工作电脑干净安装，再冻结版本。

当前依赖快照中SDK对pyasn1的上限与共享核心uv覆盖策略不一致，安全扫描和兼容决策尚未完成。不要将快照或本机成功直接认定为生产依赖锁；无需码道部门即可先解决此发布门槛。跨平台依赖包需明确操作系统和Python版本后生成，不能把macOS依赖目录直接拷到Windows。

通用本地MCP客户端配置参考 `../examples/mcp-local.example.json`，替换Python绝对路径，并通过客户端可信配置提供接口环境变量。此模板只用于准备，不代表已在码道目标版本验证；码道最终配置格式以协同验收时实际客户端要求为准。

## Windows Python 3.12 已确认

用户已确认Windows/Python3.12；开发包按x64准备，安装脚本会检查64位解释器和系统架构，ARM64需另行准备。解压后在PowerShell运行 `& .\scripts\install-development.ps1`；不要全局关闭脚本执行策略，若组织策略阻止脚本，按本地IT允许的方式执行等价安装命令。

脚本新建包内.venv，使用包内wheel离线安装并执行pip check、离线MCP检查；不覆盖已有环境、不连接云端。requirements-development.txt复制现有已测依赖，补齐Windows pywin32，不是安全批准的生产锁。保留前述pyasn1发布策略冲突，安装成功也不能解除发布门槛。此脚本需在实际Windows机器上验收，本机macOS不冒充Windows安装测试。
