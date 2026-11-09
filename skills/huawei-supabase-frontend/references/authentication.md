# 统一初始化、认证复用与只读预检

管理华为云资源需有效的认证上下文和目标区域，不强制创建永久 AK/SK。优先复用用户指定或当前有效 profile，确认目标账号；需要补充认证时按运行环境选择。只读取模式、区域、profile 名称等必要元数据，展示前过滤秘密字段，不输出整个配置文件。

| 环境 | 认证选择与前提 |
| --- | --- |
| 已有有效 profile | 沿用其 AKSK、SSO 或 AssumeRole 等已有模式，不覆盖配置或擅自切换账号。 |
| 本机且组织已启用 IAM 身份中心 | 使用 SSO；需要门户 URL、身份中心所在区域及获分配的账号/权限集，用户完成登录。 |
| CloudShell | 可作为用户登录控制台后的在线执行环境；先验证当前 shell 的 KooCLI 认证。浏览器登录不代表本机 CLI 已登录，不复制 CloudShell 凭证到本机。 |
| 以上条件不具备 | 使用官方配置流程配置 AKSK；临时 AK/SK 必须连同 SecurityToken 使用。不要让用户在聊天中粘贴密钥。 |

已有 AssumeRole 配置需保留其源 profile 和委托关系；认证失败不自动创建委托、启用身份中心或授予额外权限。

## 首次永久 AK/SK：一次终端初始化

默认使用官方 Huawei Cloud DevKit 的统一入口，不另做配置助手。使用已核对的 npm 发布包 **1.1.13**（要求 Node.js ≥22）；执行时沿用该固定版本及核对帮助，不使用浮动 latest。DevKit 负责初始化，KooCLI 负责云操作，skill 负责部署流程；不要求安装整套 DevKit 插件或其他 skills。

1. **检查复用条件。** 已有 KooCLI 与 OBS 认证可用时直接使用。只检查必要元数据：当前/目标 profile、认证模式、区域、工具路径，以及 DevKit 凭证库和默认 OBS 配置是否存在；秘密不得回显。首次永久 AK/SK 且无冲突时才走下面的统一入口。
2. **检查工具。** 在初始化所在机器检查 Node 与 npm；Node 不足或缺失时报告缺项，不自动安装、升级或切换，亦不改变前端项目版本。KooCLI 缺失且任务允许准备工具时执行 `npx --yes huaweicloud-devkit@1.1.13 install-hcloud`，再验证 `hcloud version` 和 `hcloud obs help`。首次 KooCLI 隐私声明由客户阅读并接受，不静默代为同意。此命令可能下载安装，不能用于只读预检。下载失败保持现状，不直接采用输出中的 latest 一键安装命令。
3. **交付一条初始化命令。** 区域来自客户已选目标，以下为 macOS/Linux 北京四示例；客户在自己的真实终端执行，按提示输入 AK、SK，永久凭证的 Security Token 留空。不得让客户把密钥输入聊天，也不得由 agent 将真实密钥转录到工具调用。Windows PowerShell 在当前会话设置 `$env:HW_REGION` 后执行同一 npx 命令。

```sh
HW_REGION=cn-north-4 npx --yes huaweicloud-devkit@1.1.13 auth init
```

该版本没有交互询问区域，未提供时默认北京四，因此必须显式设置目标区域。它还优先读取已有 `HW_ACCESS_KEY`、`HW_SECRET_KEY`、`HW_SECURITY_TOKEN` 环境变量；初始化前检查是否存在注入身份并核实归属，不显示值、不把不同来源的凭证混用。可指导客户在不含旧注入变量的终端执行。

4. **分别验收。** 初始化后重新核实实际 profile、账号、区域和 OBS Endpoint；按下节执行所需服务与目标桶的只读查询。报告“配置已完成 / 云 API 可用 / OBS 可用”各自状态，进程退出码、凭证文件存在或 DevKit 的 synchronized 输出都不能代替服务权限验证。缺 KooCLI 时该版本仍可能写入 OBS/凭证库并返回成功，必须标记为部分完成。
5. **后续复用。** 环境记录只保存认证方式、profile、区域、工具版本及验证结果。更新应用不重复初始化；失效时修复相同身份，换账号/区域时重新核对。DevKit 输出的 `install --target all` 是可选插件建议，本 skill 不自动执行。

### 已有环境与兼容边界

- **不是无损导入工具。** 1.1.13 的永久凭证初始化会删除并重建当前 KooCLI profile，覆写默认 `~/.obsutilconfig`，并写入 `~/.config/huaweicloud/credentials.json`。多账号、自定义 OBS 配置或共享机器不能直接套用首次初始化命令。先保留受限备份、列出受影响配置及默认身份变更；只有已有授权覆盖迁移才执行，否则复用原配置。中断后核对部分写入状态，按快照恢复，不能连续重跑覆盖其他身份。
- **存储边界。** DevKit 凭证库与 OBS 配置含可读取的秘密，不能宣称全部加密。文件留在用户目录、限制为本人访问（macOS/Linux 0600，Windows 检查 ACL）；备份同样保护，不放项目内、不上传。工具内部可能将密钥传给 KooCLI 子进程参数，不宣称进程列表完全不可见；共享主机优先保留组织已有认证方式。
- **已有加密配置。** 不自行解密 KooCLI、不关闭加密。需要统一迁移时，客户在终端重新输入一次凭证；不承诺从任意 profile 自动导出秘密。
- **临时凭证。** 1.1.13 的 `auth init` 会将 SecurityToken 写入 OBS/凭证库，却未把它传入 KooCLI 配置命令，因此临时 AK/SK 不走此简化入口。沿用官方专用流程并同时验证令牌完整性、有效期及两端身份；不删除令牌来消除错误。
- **SSO / AssumeRole。** 保留既有认证流程，不转换为永久 AK/SK。
- **自动同步。** `auth sync` 也会改写配置，不作为每次部署的默认步骤。只有已明确使用 DevKit 管理的永久凭证环境且需要修复时才使用，之后重新验收。若使用官方连接器，先发现当前会话实际可用的工具及其能力，不假定某个同步工具必然存在。

## SSO

先核实本地 `hcloud configure set --help` 和 `hcloud configure sso --help`。以下变量来自已有配置或用户的身份中心信息；FRONTEND_PROFILE 使用已选定或新建且不冲突的名称。FRONTEND_SSO_REGION 是身份中心所在区域，可能与部署区域 FRONTEND_REGION 不同。

```sh
hcloud configure set --cli-profile="$FRONTEND_PROFILE" --cli-mode=SSO \
  --cli-region="$FRONTEND_REGION" --cli-sso-start-url="$FRONTEND_SSO_START_URL" \
  --cli-sso-region="$FRONTEND_SSO_REGION"
hcloud configure sso --cli-profile="$FRONTEND_PROFILE"
```

账号和权限集已明确时，可配置 `--cli-sso-account-name` 和 `--cli-sso-permission-set-name`；否则按官方交互选择已授权目标。登录、MFA 或门户授权交由用户完成，不索取密码、验证码或会话令牌。登录过期时续登相同 profile，成功后恢复只读预检。没有门户或权限分配时明确缺少的条件，不宣称普通控制台账号可直接 SSO 登录。

## 只读预检与错误诊断

复用选定 profile。先按所需服务查看本地 `hcloud RDS ListAiApplications --help`、`hcloud CDN --help` 或 OBS 工具帮助，再选择本次任务所需的只读查询；分页按对应命令规则读完。

只有目标 API 需要 project ID 时，才优先让 KooCLI 自动解析；保留用户指定项目。全局服务、桶访问与 RDS 区域项目不能混用同一 ID。自动解析受限且认证有效时，再查询官方 IAM 项目接口或使用已知目标 ID。

- 401、Unauthorized 或 APIGW.0301：先检查凭证有效期、临时令牌、SSO 会话和委托条件；保留脱敏请求 ID。不能仅凭错误认定密钥错误，也不能靠改填 project ID 绕过无效认证。
- 403：区分权限不足与策略拒绝，指出具体操作，不自动授予管理员权限。
- DNS、TLS、超时：报告网络阶段，保留 TLS 校验，不标记区域不支持。
- 查询为空：仅在查询成功且分页完整后报告不存在，不自动购买替代资源。

OBS 默认使用 `hcloud obs`，先运行 `hcloud obs help` / `hcloud obs help ls` 核对参数，并对已指定桶执行只读查询。仅在任务需要且有权限时列出所有桶；无全局列桶权限不等于目标桶不可用。OBS 配置仍独立于 KooCLI profile，多账号任务必须核对两端身份，不能只加 `--cli-profile` 就假定 OBS 已切换。已有独立 obsutil 或自定义 `-config` 配置继续复用。

认证成功以目标只读 API 响应为证；某一服务成功不代表其他服务权限足够。认证失败时继续可独立完成的本地构建与配置计划，云端状态标记未核实。首次凭证配置和 MFA 由用户通过官方交互完成，聊天及仓库不接收秘密。

## 官方依据

SSO 参数按当前 KooCLI 帮助复核；KooCLI 7.3.12 曾完成本地帮助核对；执行时仍核实实际版本、参数及服务能力，不将历史版本当作永久推荐。

- [访问凭证最佳实践](https://support.huaweicloud.com/bestpractice-iam/iam_0516.html)
- [SSO 登录](https://support.huaweicloud.com/usermanual-hcli/hcli_03_009.html)
- [认证模式](https://support.huaweicloud.com/usermanual-hcli/hcli_05_10.html)

统一入口来源：[DevKit 1.1.13 发布包](https://www.npmjs.com/package/huaweicloud-devkit/v/1.1.13)、[官方仓库](https://github.com/huaweicloud/huaweicloud-devkit)、[KooCLI 内置 OBS](https://support.huaweicloud.com/usermanual-hcli/hcli_04_009.html)。

官方参考：[KooCLI 概述](https://support.huaweicloud.com/intl/en-us/productdesc-hcli/hcli_01.html)。

官方参考：[JSON 参数输入](https://support.huaweicloud.com/usermanual-hcli/hcli_05_12.html)。

官方参考：[中国站 API Explorer](https://console.huaweicloud.com/apiexplorer/)。

官方参考：[国际站 API Explorer](https://console-intl.huaweicloud.com/apiexplorer/)。

官方参考：[KooCLI 配置参数](https://support.huaweicloud.com/usermanual-hcli/hcli_03_003_01.html)。
