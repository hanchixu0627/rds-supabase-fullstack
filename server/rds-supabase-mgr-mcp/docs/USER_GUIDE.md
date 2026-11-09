# 华为云 Supabase MCP + Skill 用户指南

适用版本：0.3.8a2开发预发行版。文档更新：2026-11-09。

本工具让你在Claude Code等支持本地MCP的助手中，用自然语言查询和管理华为云Supabase。MCP负责调用云接口，专项Skill负责理解需求、补充信息、展示影响及指导确认。先完成本地接入，再验证真实云访问；当前开发版尚未完成生产发布验收。

## 1. 能做什么

| 场景 | 当前支持 |
|---|---|
| 创建应用 | 查询候选；Single模式关联已有PG或按需新建PG |
| 删除应用 | 删除Supabase应用，保留PG；PG可能继续计费 |
| 访问控制 | 已有EIP绑定/解绑、SSL开关、应用账号改密 |
| 安全组 | 查询、创建、指定TCP端口规则增删 |
| ApiKey | 元数据查询、重置、指定Key交付到受保护本地文件 |
| 业务配置 | 注册开关、Auth URL、GitHub、SMTP、确认邮件模板和OBS |

暂不支持Ha、包周期创建、应用删除级联PG、自动购买证书或EIP、修改EIP带宽。SQL和数据操作属于独立数据面能力。证书由用户在外部流程准备；共享安全组影响需先核对。

## 2. 安装前准备

推荐安装路径为Windows x64 + Python3.12，使用PowerShell。先确认：

```powershell
py -3.12 --version
claude --version
```

Claude Code需已安装，并且能正常与所配置的模型对话。本包不安装Claude或配置模型账号。机器无法访问GitHub时，可由另一台可访问的电脑下载两个附件后，通过公司允许的方式传输。

macOS开发机已进行过本地验证，但下述ZIP包含Windows依赖，不适用于macOS/Linux/ARM64。其他系统需使用源码及匹配平台的依赖，不能直接运行此Windows安装命令。

## 3. 下载与一行安装

打开[0.3.8a2下载页](https://github.com/hanchixu0627/rds-supabase-fullstack/releases/tag/supabase-dev-v0.3.8a2)，下载：

- `supabase-development-0.3.8a2-windows-x64-py312.zip`
- 同一版本的`archive-sha256.txt`

选择Release附件，不用GitHub自动生成的Source code替代离线安装包。这是个人fork的开发交付，组织集成见[PR #7](https://github.com/huaweicloud/rds-supabase-fullstack/pull/7)，不等于组织正式发行。

在下载目录核对ZIP的SHA256，与同版校验文件中的摘要逐字一致后解压：

```powershell
Get-FileHash .\supabase-development-0.3.8a2-windows-x64-py312.zip -Algorithm SHA256
```

例如解压到 `D:\Supabase\0.3.8a2`，在PowerShell执行这一行即可安装：

```powershell
& 'D:\Supabase\0.3.8a2\scripts\install-development.ps1'
```

请把示例路径替换成实际目录。该命令检查Windows/Python架构及包内清单，创建独立`.venv`，从随包wheels离线安装，运行依赖一致性检查及MCP离线诊断。成功应显示 `Development installation completed`，诊断 `passed: true`。此过程不调用业务云API。

这是“解压后单行安装”，不包含自动下载安装Claude、云账号配置或自动授权云写。执行策略被公司限制时交IT按允许方式处理，不需要全局关闭策略。目录已存在`.venv`时使用新解压目录；不要覆盖旧环境。安装前不要把报告或自定义文件放进解压目录，否则完整性校验会失败。

## 4. 安装专项Skill

安装成功后新建独立交互目录，例如 `D:\Supabase\claude-test`。不要把含凭据或原始内部资料的目录直接作为Agent工作目录。

使用下面一行把专项Skill复制到项目级位置：

```powershell
New-Item -ItemType Directory -Force 'D:\Supabase\claude-test\.claude\skills' | Out-Null; Copy-Item -Recurse 'D:\Supabase\0.3.8a2\skill' 'D:\Supabase\claude-test\.claude\skills\huaweicloud-supabase'
```

确认最终存在 `.claude\skills\huaweicloud-supabase\SKILL.md` 和完整references目录。已有同名Skill时先核对版本，不反复复制嵌套目录。使用的是Supabase专项Skill，不是huaweicloud-mcp-dev开发Skill。

## 5. 接入Claude Code

在交互目录创建`.mcp.json`，例如：

```json
{
  "mcpServers": {
    "supabase-test": {
      "command": "D:\\Supabase\\0.3.8a2\\.venv\\Scripts\\python.exe",
      "args": ["-m", "mcp_server_supabase.main"],
      "env": {
        "SUPABASE_TRANSPORT": "sdk_core",
        "HUAWEICLOUD_MCP_READ_ONLY": "true",
        "SUPABASE_ENABLE_WRITES": "false",
        "SUPABASE_STATE_FILE": "D:\\Supabase\\private-state\\plans.sqlite3"
      }
    }
  }
}
```

路径必须替换为实际绝对路径；JSON中的反斜杠需要双写。账本目录位于交互目录外，由运行账户保护并保持路径稳定；不要为重复执行而删除或更换账本。配置文件不填写AK/SK。

进入交互目录并启动：

```powershell
Set-Location 'D:\Supabase\claude-test'
claude --strict-mcp-config --mcp-config .\.mcp.json
```

首次按客户端提示确认项目及MCP。输入 `/mcp` 检查连接；实际工具列表应包含29个工具。输入 `/huaweicloud-supabase` 明确加载专项Skill，再输入：

> 查询当前MCP能力，说明支持哪些Supabase场景；本次不访问云资源。

这一步验证自然语言、Skill和工具连接，不需要云凭据。Skill不是鉴权机制，不能因其加载成功就宣称云服务可用。客户端版本不同，具体提示界面可能不同；以实际工具列表和调用结果为准。

## 6. 配置真实云访问

由用户在可信本地环境向Claude启动进程提供下列变量，不发送到聊天、不写入项目或公开仓库：

| 配置 | 用途 |
|---|---|
| SUPABASE_RDS_ENDPOINT | 当前局点的原生RDS HTTPS入口，不是Console地址或/rest代理 |
| HUAWEICLOUD_PROJECT_ID | 与局点一致的项目ID |
| HUAWEICLOUD_ACCESS_KEY、HUAWEICLOUD_SECRET_KEY | 具备所需权限的AK/SK |
| HUAWEICLOUD_SECURITY_TOKEN | 仅临时凭据时使用匹配的STS token |
| SUPABASE_VPC_ENDPOINT | 安全组场景独立的原生VPC入口，由环境负责人确认 |
| REQUESTS_CA_BUNDLE | 需要自定义CA时指定可信本地PEM文件 |

入口、IAM权限及API开放情况以实际局点为准。不要把浏览器可登录Console等同于Python SDK能够访问。MCP子进程必须继承配置；更新后重启Claude。模型服务代理和云API网络分开处理，不统一设置全局NO_PROXY=*，不关闭TLS验证。SDK模式仅设置SSL_CERT_FILE不能保证采用该CA。

CLI也需使用与Claude相同的sdk_core和只读配置；`.mcp.json`中的env不会自动配置当前PowerShell。请由操作方在该终端设置非秘密模式变量：

```powershell
$env:SUPABASE_TRANSPORT='sdk_core'; $env:HUAWEICLOUD_MCP_READ_ONLY='true'; $env:SUPABASE_ENABLE_WRITES='false'
```


在同一可信配置环境中先运行：

```powershell
& 'D:\Supabase\0.3.8a2\.venv\Scripts\python.exe' -m mcp_server_supabase.diagnostics check
```

该命令只检查格式和依赖。通过后，在已授权测试项目执行真实只读检查：

```powershell
& 'D:\Supabase\0.3.8a2\.venv\Scripts\python.exe' -m mcp_server_supabase.diagnostics readonly --allow-cloud-read
```


## 7. 用自然语言操作

先保持只读，逐条尝试：

| 用户输入 | 应有行为 |
|---|---|
| 列出当前项目的Supabase应用，不做修改 | 查询应用并说明分页范围 |
| 查询应用〈ID〉的EIP绑定情况，解释解绑影响 | 查询详情，不提交解绑 |
| 我要创建Ha模式应用，先检查是否支持 | 明确不支持，不擅自改成Single |
| 我想用已有PG创建Single应用，先说明需要哪些信息 | 查询/澄清配置，不索取聊天明文密码 |
| 列出应用〈ID〉的ApiKey类型和状态，不查看值 | 仅元数据查询 |
| 我想开放8443，但还没确定来源，先别改 | 澄清来源和共享影响，不默认全网放行 |

需要真实修改时，先选择允许变更的隔离测试资源。由操作方将该MCP配置改为 `HUAWEICLOUD_MCP_READ_ONLY=false` 和 `SUPABASE_ENABLE_WRITES=true` 并重启。Agent不得自行修改权限配置。权限开启后仍必须预览并确认具体变更。

例如EIP解绑对话：
1. “为应用〈ID〉预览解绑EIP，暂不执行。”
2. 核对目标、原绑定、服务中断及费用说明。
3. “确认执行刚才预览的解绑，仅限这个应用。”
4. 要求查询任务、回查应用；实际公网连通由测试人员验证。
5. 需要恢复时，用原EIP ID和地址生成新计划，再确认恢复。

202只表示受理，任务completed不等于业务验证完成。提交超时先查计划/任务/资源，不重复提交。取消未提交计划不等于取消已提交云任务。测试结束后恢复只读并重启。

密码、SMTP、OAuth及OBS秘密由可信操作方通过本地引用提供；ApiKey只交付到受保护文件，不让Agent读取内容。详见[本地秘密输入输出](LOCAL_REQUESTS.md)。Windows文件ACL需操作方设置；此机制不是宿主秘密保险库。

## 8. 开发者的测试背景与已知结果

以下是测试背景，不是产品自动采用的默认账号或环境。

| 项目 | 已有记录 |
|---|---|
| 真实环境验证机 | Windows x64；Python3.12.10；PowerShell5.1 |
| Windows版本报告 | 10.0.26100.4652；以实际系统信息为准 |
| 云测试局点 | 乌兰察布cn-north-7；RDS入口rds.cn-north-7.myhuaweicloud.com |
| 云资源 | 专用隔离Supabase及关联PG；不公开项目ID、资源ID或凭据 |
| SDK/MCP依赖基线 | huaweicloudsdkcore3.1.220、mcp2.3.0、共享core1.0.0 |
| 本机开发/交互验证 | macOS；Claude Code2.1.85；0.3.8a2能力查询对话成功 |
| 工作电脑Claude记录 | 曾报告Claude Code2.1.123，当前部署时重新核对 |
| 0.3.6a1历史真云结果 | 应用/Key元数据查询、Auth开关、Key重置、EIP解绑/恢复、应用删除；当时使用测试机TLS跳过补丁，不能替代安全TLS验收 |
| 0.3.8a1 Windows结果 | 安装/离线诊断通过；124项中123通过、1个SQLite测试清理错误 |
| 0.3.8a2本地结果 | 修复该测试；124项通过、覆盖率93.09%；Windows修正版复验尚待报告 |
| 当前安全默认值 | 首次接入只读、关闭云写；TLS验证开启；不自动支付、不自动释放资源 |

旧版本接口通过不代表本版全部29工具、全部六场景或全部模型都已通过。当前SDK Core负责签名和传输，尚未接入正式生成式Supabase产品SDK。依赖安全策略、可信CA/代理、Windows新包、真实新增场景、Agent轨迹和码道联合验收仍有待完成项。当前发行包面向开发验证，不建议直接用于生产。

## 9. 常见问题

| 现象 | 处理 |
|---|---|
| GitHub下载失败 | 两附件一起传输；不要用旧包冒充新版 |
| 安装校验失败 | 使用新解压目录，报告放目录外，核对同版摘要 |
| MCP连接失败 | 检查Python绝对路径、安装结果、进程日志，不先修改云权限 |
| 工具数量/版本不符 | 检查是否启动了旧环境并重启客户端 |
| Skill未加载 | 检查项目目录、SKILL.md路径及references，显式调用专项Skill |
| 入口/项目检查失败 | 检查原生入口及局点项目对应关系 |
| TLS失败 | 配置可信CA；缺CA记录阻塞，不关TLS |
| 代理504 | 确认云目标是否应直连及进程代理；保持模型服务代理可用 |
| 只读阻止修改 | 由操作方确认测试范围再配置写权限，Agent不能绕过 |
| 修改结果未知 | inspect计划、查任务/资源；不要删除账本或重新提交 |

需要反馈时提供版本、阶段、用例、脱敏错误类别和任务/资源/业务结论，不提供凭据或完整抓包。完整范围见[六场景矩阵](SIX_SCENARIO_MATRIX.md)，联调执行单见[NEXT_WORKSTATION_PROMPT.md](NEXT_WORKSTATION_PROMPT.md)。
