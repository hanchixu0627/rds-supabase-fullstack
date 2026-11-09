# 接入已有华为云 RDS Supabase

## 发现与选择

先读取项目记录和现有配置的非敏感字段，优先复用绑定的应用。确需发现时先查询 KooCLI 帮助：

```sh
hcloud RDS ListAiApplications --help
hcloud RDS ShowSupabaseApplication --help
```

这两个命令仅提供帮助发现入口，其完整参数未获独立复核；执行前通过当前帮助或 API Explorer 确认参数、分页和返回结构。按帮助传入实际区域/profile，只有 API 需要时解析 project ID。列表读完所有页，详情响应按敏感信息处理，提取应用 ID、状态和入口即可，不整段输出或存入环境记录。

筛选 Supabase 类型、所属项目/企业项目、区域、应用归属和可用状态；多个无法消歧的候选展示非敏感名称和 ID 后询问，不能选第一项。空结果与认证/权限失败分别报告。零候选时说明需要已有应用，不自动创建数据库；工具没有命令时查看当前官方 API Explorer 或由用户在控制台选定已有应用，不用普通 RDS 实例创建代替 Supabase。

## OBS 前端与访问入口

只为 OBS 项目接入后端时读取其源码、构建环境和 OBS/CDN 发布配置；仅有访问 URL 不足以注入 SDK。已有 Supabase URL 和公开 Key 可先验证 Data API，不必先取得华为云控制台认证。保留后端其他有效 origin 和回调，不将 Auth Site URL 切到临时预览地址来影响生产；这些共享配置不扩大本 skill 的托管支持范围。

生产域名、已有预览地址和实际本地地址分别记录。精确授权需要登录测试的预览回调，测试后在授权内移除临时条目，不放宽域名匹配。生产 URL 来自已核实的域名与 CDN 配置；缺少域名时先准备产物、本地预览和上线清单，不拼接未建立的地址。

HTTP 调试入口仅用于页面连通测试，不输入真实登录凭证或处理真实会话。正式登录需可信 HTTPS；自签名或浏览器忽略证书错误不算通过。OAuth 提供商或浏览器能力不支持该入口时明确阻碍，不扩大回调权限。托管环境能访问后端不代表用户浏览器能访问内网 API。

## 浏览器连接

优先 Publishable Key，现有华为云应用只提供 Anon Key 时兼容其实际能力，不强制迁移密钥体系。SDK 复用项目版本，客户端配置例如：

```ts
import { createClient } from '@supabase/supabase-js'

export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY,
)
```

这是 Vite 示例，已有 Anon Key 项目保留已采用的公开变量名。构建前验证两项非空、URL 是真实 HTTPS API 地址。Secret Key、Service Role Key、数据库密码与云凭证均不能注入客户端。公开 Key 不代表用户身份，也不替代 RLS。

## 连通性与权限

从实际用户网络检查 API 的 DNS、TLS 证书链和名称、Data API/Auth/Storage 所需能力；内网地址不能被公网浏览器直接使用。保持 TLS 校验，不以关闭验证或仅内网 curl 成功作为验收。保留已可用的公网配置；如需新增公网入口，另列后端网络变更及费用，在对应授权范围内执行。

在已授权范围内检查目标前端 origin 的 CORS（含实际请求的预检）、Auth Site URL、回调允许列表和 OAuth 提供商回调。最终域名确定后再配置精确地址，保留其他有效环境；本地回调与线上回调分开。前端环境变量改变需要重新构建。

只读检查表授权、RLS 策略及 Storage 策略是否符合业务；不能为连通测试关闭 RLS。通过获授权的测试账号 A/B 检查自身数据可见、跨用户私有数据不可见，匿名访问符合设计；公开数据按业务规则验收。写入、迁移和策略修改仅使用对应授权及测试对象。缺少测试账号或读权限时标记隔离“未验证”，不推断成功。

华为云能力以实际应用及官方文档为准，不能将 Supabase Cloud 的管理 API、项目创建或 Edge Functions 流程直接套用。前端上线与后端公网可达分别报告。

依据：[华为云 Data API](https://support.huaweicloud.com/usermanual-rds-pg/rds_supabase_23.html)、[Dashboard 能力](https://support.huaweicloud.com/usermanual-rds-pg/rds_supabase_04.html)、[Supabase Key 类型](https://supabase.com/docs/guides/getting-started/api-keys)。
