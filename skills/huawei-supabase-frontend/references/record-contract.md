# 发布记录契约

开始 OBS/CDN 发布、续跑、验收或回退并需要读写记录时读取。沿用 `schema_version=2` 的字段结构与状态语义，新记录仅用于 OBS/CDN；[验收与回退](deployment.md) 定义操作顺序。示例值均为虚构，不代表真实资源或验证结果。

## 文件与通用规则

默认文件为 `.hwsupabase/frontend/<环境>/environment.json`、`releases/<版本>/manifest.json`、`checks/<版本>/<check_id>.json`。目录排除 Git；备份及配置快照位于 web root 外的私有位置。每次验收或补验使用新的 `check_id` 和独立文件，同一路径不得覆盖已有事件。

- 新记录的 `schema_version` 为整数 `2`。公共必填字段即使未知也保留，值用 `null`；不要把 `null` 当作不存在或验收通过。
- 时间使用 RFC 3339 UTC，例如 `2026-11-07T08:00:00Z`；URL 使用实际完整地址，路径以 `/` 开头。SHA-256 使用 64 位小写十六进制。
- 可增加任务字段并保持版本 `2`；改变既有字段含义、类型或状态语义时升级主版本并另写迁移规则。
- Key、私钥、数据库密码、云凭证、cookie、token、用户数据及完整认证响应不入记录。环境变量仅记录名称、作用域和安全存储位置。

## environment.json

公共必填字段：

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `schema_version` | integer | 固定为 `2` |
| `environment` | string | 实际环境名称 |
| `hosting_kind` | string | 新记录固定为 `obs-cdn`；旧路线按下文兼容规则保留历史 |
| `provider` | string | 新记录为 `huawei-cloud` |
| `service` | string | 新记录为 `OBS+CDN` |
| `account_id` | string/null | 华为云账号的非秘密标识 |
| `stable_url` | string/null | 稳定入口，含 HTTP/HTTPS；尚未取得时为 `null` |
| `supabase_application_id` | string/null | 已有应用 ID |
| `supabase_https_url` | string/null | 浏览器使用的真实 HTTPS API |
| `current_service_version` | string/null | 最近查询确认的稳定入口实际服务版本；结果不明时保留最后确认值 |
| `current_success_version` | string/null | 最近通过适用验收的版本，失败候选不得写入 |
| `previous_success_version` | string/null | 最近一次成功稳定入口切换前的 `current_success_version`；首次发布为 `null` |
| `remote_release_status` | string | `not_published`、`publishing`、`published`、`failed`、`unknown` 之一；只描述远端发布，不代替验收 |
| `last_completed_stage` | string | `initialized`、`preflighted`、`built`、`candidate_verified`、`production_switched`、`production_verified`、`rollback_switched`、`rollback_verified` 之一 |
| `updated_at` | string | 本次记录更新时间 |
| `build` | object/null | 构建环境增量信息，见下表 |

新环境记录必须有 `obs_cdn` 对象，不写入其他托管路线的配置对象。

| 对象 | 必填字段 |
| --- | --- |
| `obs_cdn` | `profile`、`obs_region`、`rds_region`、`project_id`、`bucket`、`cdn_id`、`cdn_cname`、`dns_record_id`、`certificate_id`、`certificate_expires_at`、`delegation_scope`；未核实或不适用的值为 `null` |

`build` 为对象时，必填 `location`（`local`/`ci`）、`method`（`native`/`docker`）、`os`、`arch`、`node_version`、`package_manager`、`constraint_sources`（字符串数组）、`image_digest`、`last_build_result`。无值字段用 `null`；已有产物未经本次构建时整个 `build` 为 `null`，并以来源记录或 manifest 说明产物依据。

发布版本是一组可辨认、可验证的原产物及发布记录；源码提交不能代替当时产物。

## 状态不变量

每次发布、更新或回退都是新的当前操作；开始时按本次实际进度重新记录 `last_completed_stage`，上一操作的终态只保留在历史事件中，不作为本次阶段。

1. 上传或构建候选不改变三个版本字段。入口切换前失败时 `current_service_version` 保持原值，`remote_release_status=failed`。
2. 新候选确认切换后、验收前：`current_service_version` 为候选版本，两个成功版本字段保持原值，`remote_release_status=published`，`last_completed_stage=production_switched`。
3. 新候选验收通过：先将原 `current_success_version` 写入 `previous_success_version`，再把候选写入 `current_success_version` 和 `current_service_version`，设置 `last_completed_stage=production_verified`。
4. 候选切换后失败或结果不明：保留实际候选版本与最近成功版本，分别设置 `remote_release_status=failed` 或 `unknown`；不得把失败候选写成成功。
5. 回退切换前失败或结果不明：三个版本字段保留最后确认值，`remote_release_status=failed` 或 `unknown`，`last_completed_stage` 保持切换前状态；本次 `operation=rollback` 的 checks 事件记录目标版本和失败原因。
6. 回退确认切换后、验收前：`current_service_version` 为回退目标，两个成功版本字段保持原值，`remote_release_status=published`，`last_completed_stage=rollback_switched`。此后失败或结果不明仍保持该阶段，分别设置 `failed` 或 `unknown`，不得把目标写成已回退成功。
7. 回退验收通过也按第 3 条执行一次成功切换，设置 `last_completed_stage=rollback_verified`。被替换版本若从未验收通过，不写入 `previous_success_version`。
8. `production_verified` 或 `rollback_verified` 要求 `remote_release_status=published`，且 `current_service_version=current_success_version`。`production_switched` 或 `rollback_switched` 只要求实际服务版本已确认；即使它等于某个历史成功版本，也不得据此跳过本次验收。
9. 每次验收或补验写入新的 checks 事件文件并更新 environment 的 `updated_at`，不覆写历史事件或把旧证据当作本次结果。

## manifest.json

必填字段：

| 字段 | 类型与规则 |
| --- | --- |
| `schema_version`、`version` | 整数 `2`、发布版本字符串 |
| `source_commit`、`built_at` | 源码提交与实际构建时间；无源码或未知时为 `null` |
| `build` | 与 environment 的 build 字段结构相同；必须记录当时事实，不被后续工具升级覆写 |
| `build_command`、`output_directory`、`lockfile_sha256` | 实际命令、产物目录、锁文件摘要；未知或不适用的值为 `null` |
| `files` | 对象数组，每项必填 `path`、`size`（非负整数）、`sha256`、`mime`、`cache_control` |
| `routes` | 对象，必填 `pages`、`assets`、`api` 三个字符串数组 |
| `entry_backup_path`、`config_backup_path` | 原入口及配置的私有备份位置；首次发布或不适用时为 `null` |
| `previous_version` | 前一版本；首次发布或未知时为 `null` |
| `refresh_scope` | 实际 CDN 刷新路径或 URL 字符串数组；无刷新操作时为空数组 |

## checks.json

每个文件代表一次独立验收事件。必填 `schema_version`、`check_id`、`version`、`checked_at`、`operation`、`supabase_required`、`overall_status`、`checks`，且 `checks` 至少有一项。

- `check_id` 是事件唯一标识，使用小写字母、数字和连字符；`operation` 为 `initial_release`、`update`、`rollback`、`recheck`；`supabase_required` 是布尔值，表示本次业务是否必须验收 Supabase。
- 所有事件必须覆盖 `entry`、`assets`、`routes`、`negative_paths`、`cache`；`supabase_required=true` 时增加 `supabase`；`operation=update` 或 `rollback` 时增加 `update_rollback`。每个 `name` 只能出现一次。`update_rollback` 按操作解释：更新验证新版可见及旧资源可用，回退验证指定原版本恢复；普通更新不要求切回旧版，回退演练须明确请求。
- 必需项不得以 `not_applicable` 代替验收，且必须具有 `access_mode=normal` 的实际结果。指定 Host/IP 的诊断可另记为检查项，但不能满足生产必需项。
- 任一检查为 `failed` 时 `overall_status=failed`。没有失败但缺少必需项，或必需项为 `unverified`、`not_applicable`、仅诊断结果时，`overall_status=partial`。只有全部必需项通过且其他已执行项通过或有理由地不适用时才为 `passed`；空数组、全 N/A 或无关检查不能构成整体通过。

`entry`、`assets` 标记 `passed` 时必须有 `request_method=GET`、整数 2xx `final_status`、非附件的 `content_disposition`（缺失可为 `null`）、`browser_status=passed`，并记录目标/最终 URL、Content-Type 与正文摘要。证据字段一致不代替实际内容验证；负面路径允许预期 4xx。

`checks` 每项必填：

| 字段 | 规则 |
| --- | --- |
| `name`、`status`、`target_url` | 检查名称；`passed`/`failed`/`unverified`/`not_applicable`；实际目标或 `null` |
| `request_method`、`final_url`、`access_mode` | 实际方法、最终 URL、`normal`/`resolve-diagnostic`；未执行时为 `null`，`access_mode` 仍须记录计划或实际模式 |
| `final_status`、`content_type`、`content_disposition` | 最终 HTTP 状态及响应头；未执行或缺失时为 `null` |
| `body_summary`、`browser_status`、`task_id` | 脱敏正文摘要、浏览器结果、适用任务 ID；未执行或不适用的值为 `null` |
| `reason` | 失败、未验证或不适用的具体原因；通过时为 `null` |

示例：[OBS 环境](examples/environment.obs.json)、[旧 OBS 记录](examples/environment.legacy.json)、[manifest](examples/manifest.example.json)、[checks](examples/checks.example.json)。

## 旧记录兼容

旧记录没有 `schema_version` 时不按 v2 补齐猜测值。既有 v2 的 `checks/<版本>.json` 作为单个历史事件读取并保留，后续补验写入新的 `checks/<版本>/<check_id>.json`，不得覆盖旧文件。已有桶/CDN 绑定只能作为 OBS 路线线索，查询核实后再写新记录；原值和历史文件保留，空记录不推断为 OBS。

旧 `hosting_kind=external` 等非 OBS 记录仅用于识别历史和报告范围限制，保留原提供方、配置及未知字段，不改标为 OBS、不自动迁移或操作其资源。历史 manifest 中的 `external_deployment_id` 原样保留；新 OBS manifest 无需此字段，旧 OBS 记录携带该字段不影响读取。此调整不改变既有 OBS 字段与状态的含义。

缺 GET、浏览器或验收字段只表示对应证据缺失，按 [回退与旧记录兼容](deployment.md#回退与旧记录兼容) 补验，不能自动判定历史版本失败或本次回退成功。
