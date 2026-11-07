# Supabase Agent Skills 深度洞察与适配分析报告

| 项 | 值 |
|---|---|
| 研究对象 | `fitz-liujian/agent-skills`（`supabase/agent-skills` 快照，基线 commit `c9be0e9`） |
| 本地路径 | `/Users/fitz/work/projects/research/supabase/supabase-mcp/agent-skills` |
| 研究方法 | 主 SKILL.md 人工精读 + 3 个并行研究代理（规则库逐文件 / 依赖面逐项 / 工程基建逐层），交叉验证 |
| 分析日期 | 2026-11-06 |
| 目标 | 为「华为云 RDS Supabase」产出两个技能的正式适配方案，支撑对外发布 |

---

## 1. 执行摘要

**一句话定性**：这不是两个"产品使用手册"，而是一套**对抗 LLM 记忆过时与幻觉的 Agent 行为纪律体系**（`supabase` 主技能）加一套**量化收益驱动的 Postgres 规则引擎**（`supabase-postgres-best-practices`），两者以"操作层 + 质量层"分层互补。

**六条核心发现**：

1. **主技能的核心价值可平移，触点不可平移**——其价值在于行为纪律（先查 changelog、改后必验证、2-3 次失败即换路、安全清单强制过检），全部部署无关；但其 42 个外部依赖项中约三分之一指向我们不存在的能力（CLI、Management API、云 Dashboard、Edge Functions、声明式迁移）。
2. **规则库纯度极高，适配成本极低**——31 个规则文件中 17 个（54.8%）零云依赖可直接用，9 个（29.0%）仅需替换尾部 supabase.com 链接，仅 5 个（16.1%）需要改写正文；**DROP 为 0**。云浓度呈哑铃分布：Security & RLS 域最深（auth.uid()、平台角色、暴露 schema 术语），其余域几乎只剩链接。
3. **pg_cron / pgmq / pgvector / pg_net 在规则文件中零出现**——扩展名只出现在 SKILL.md 的 description 触发词里。我们未装 pg_cron 对规则库**零影响**。
4. **上游存在一个从未被发现的发布缺陷**：Release Please 的 `extra-files + expressions` 自动 bump SKILL.md 版本机制**从未生效**（`expressions` 非合法配置键 + 路径双重前缀 + 缺失文件静默跳过，三级源码证据），导致 SKILL.md frontmatter 版本（0.1.2 / 1.1.1）与 CHANGELOG（0.1.9 / 1.6.0）**长期漂移 7/5 个版本**。适配版必须用 pytest 硬校验堵住此漏洞，而非复刻。
5. **changelog 检查机制不宜一刀切删除**——实测确认 `supabase.com/changelog.md` 确为轻量索引，且**含自建栈破坏性变更**（2026-07-17 Kong→Envoy 网关切换、2026-05-18 PG15→17 升级路径——我们的栈正是 Kong 形态）。应降级保留为"栈升级场景必查"，而非常规任务强制项。
6. **两个技能 + 我们既有的管理技能可组成三层技能族**：`rds-supabase-mcp`（管理层，已有 v2.3.0）+ 适配版主技能（开发操作层）+ 适配版规则库（SQL 质量层），覆盖"平台管理 → 开发纪律 → 代码质量"全链路。

**四大约束（本报告的适配边界，用户固化）**：

| 约束 | 适配处置 |
|---|---|
| 无内置 Edge Functions | 全部边缘函数能力指向**华为云 FunctionGraph 工作流**；后续提供专用 Skill（TODO 占位） |
| 不支持 Supabase CLI | CLI 相关章节整节移除，SQL 主通道改写为自研 MCP `execute_sql` |
| 不支持 AI assist | 触发词与正文不引用任何 Supabase AI 能力 |
| 不支持 migration（无 supabase_migrations） | schema 变更走 init.sql 五步部署（现有能力）；迁移系统化能力由后续 supabase mcp 提供（TODO 占位） |

**五项实测结论（2026-11-06 真实例探针，详见 §6.3）**：`auth.uid()` 等辅助函数**不存在**（身份判定必须用 `request.jwt.claims` 模式）；anon/authenticated/service_role 三角色存在；pgvector 0.8.2 **已安装**（Vectors 触发词可保留）；pg_uuidv7 不可用；pg_stat_statements 可装未装（需 RDS 参数模板 + 重启）。

---

## 2. 研究对象与基准勘误

### 2.1 快照状态

| 技能 | SKILL.md 行数 | frontmatter 版本 | CHANGELOG 版本 | 触发 description 长度 |
|---|---|---|---|---|
| `supabase` | 155（<500 ✓） | `0.1.2` | `0.1.9`（2026-09-28） | 788 字符（<1024 ✓） |
| `supabase-postgres-best-practices` | 64（<500 ✓） | `1.1.1` | `1.6.0` | 834 字符（<1024 ✓） |

### 2.2 版本口径勘误（重要）

本快照 frontmatter 数字（0.1.2 / 1.1.1）**落后于** CHANGELOG 与 release manifest（0.1.9 / 1.6.0），但正文已含 0.1.9 特征内容（scoped PAT 段落、debugging 节）。这不是快照失真——上游 main 分支同样如此（见 §3.4 缺陷分析）。**适配基准取正文内容，不取 frontmatter 数字。**

### 2.3 文件计数勘误

最佳实践技能的 `references/` 实为 **34 个文件 = 31 个规则文件 + 3 个元文件**（`_sections.md` / `_contributing.md` / `_template.md`），前缀分布：query- 5、conn- 4、data- 4、lock- 4、monitor- 3、schema- 6、security- 3、advanced- 2。

---

## 3. 仓库工程体系洞察

### 3.1 分发体系（三通道）

| 通道 | 机制 | 对我们的可行性 |
|---|---|---|
| `npx skills add <owner>/<repo>` | 识别仓库 `skills/<name>/SKILL.md` 结构，安装到各 agent 技能目录（18+ agent 兼容） | **立即可用**（我们的仓库已有 `skills/` 结构即被识别） |
| GitHub Release tarball + `dist/index.json` | `.well-known` HTTP 服务发现（schema `agentskills.io/discovery/0.2.0`），条目含 name/type/description/url/digest（sha256） | 内部部署**不需要**；对外提供发现服务时再建 |
| Claude Code 插件市场 | 根 `.claude-plugin/marketplace.json` 定义 plugin → skills 目录映射 | 低成本可选（27 行样板） |

**关键机制细节**：tarball 为**确定性构建**（`portable: true`、`mtime = epoch 0`），字节级可重现，digest 稳定；`index.json` 不含 version 字段——版本由 release tag 承载；description 直接进发现层，其质量因此是分发资产而非仅仅是触发器。

### 3.2 发布流水线

Release Please **三包模型**：根包 `"."`（兜底 release，产统一 `v{version}` tag）+ 每个 skill 一个包（`skip-github-release: true`，CHANGELOG 与 manifest 随合并的 release PR 提交，不产独立 tag）。conventional commits 驱动：`feat:` → minor、`fix:` → patch；scope 隔离（`fix(supabase):` 只 bump 对应技能）；一个合并 release PR 只 bump 被改动技能。两技能同日联动发版的现象（6-02、6-05、7-10、7-30）即此机制的结果。

### 3.3 质量门真相

上游的格式正确性保障**不是测试，而是文档纪律 + 两个隐式机器检查点**：

1. `test/sanity.test.ts`（159 行）——**实为端到端安装冒烟测试**（拷贝 `skills/` 到临时目录、真实执行 `npx skills add`、断言恰好安装白名单技能），**没有任何字段级断言**；格式校验隐式委托给 skills CLI。
2. `scripts/build-release.ts`（95 行）——构建时用 gray-matter 校验 frontmatter `name`/`description` 存在性（仅存在性 + 类型，无格式/长度规则），缺失即 throw。

**字段级硬约束的唯一权威是 AGENTS.md**（`CLAUDE.md` 为其符号链接），对照 agentskills.io 官方 spec 与官方 Python 校验器 `skills-ref`：name（1-64 字符、小写字母数字连字符、须匹配目录名）、description（1-1024 字符、必须同时含"做什么"+"何时触发"、触发信息不得放正文）、正文 <500 行、禁创建 README.md/INSTALLATION_GUIDE.md/QUICK_REFERENCE.md、CHANGELOG.md 禁止手编。

### 3.4 重大发现：版本自动 bump 从未生效（上游缺陷）

**观察**：所有 `chore: release main` 提交从不触碰任何 SKILL.md（git 历史 --stat 验证）；frontmatter 版本长期落后 manifest 7/5 个版本；上游 main 同样如此。

**三级源码证据链**：

1. `expressions` **不是 release-please 的合法配置键**——官方 schema 中 generic extra-files 仅接受 `type`/`path`/`glob`，且 generic updater 只识别 `x-release-please-version` 等注解，SKILL.md 无注解则 no-op；
2. extra-files 路径按**包目录相对**解析——包 `skills/supabase` 配 `path: "skills/supabase/SKILL.md"` 被解析为 `skills/supabase/skills/supabase/SKILL.md`（不存在）；`changelog-path: "CHANGELOG.md"` 工作正常恰证明了解析规则；
3. 缺失文件被**静默跳过**（`createIfMissing: false` → warn + continue）——流水线"正常"运转，漂移无人察觉。

**适配结论**：不复刻 `expressions` 模式；用 pytest 硬断言 `SKILL.md metadata.version == manifest 版本`（§7.6 A6），把上游的静默漂移变成 CI 硬失败。**这是我们的适配版可以比上游更稳的第一个点。**

---

## 4. 主技能 `supabase` 深度洞察

### 4.1 本质定性：行为纪律层，不是产品手册

155 行中没有一处产品功能介绍。它的四个组成部分全部是**对 agent 行为的约束**：

| 组成 | 行号 | 性质 |
|---|---|---|
| 六大 Core Principles | 11-76 | 行为纪律 + 安全知识（防静默漏洞） |
| Supabase CLI 节 | 78-95 | 工具使用纪律（`--help` 发现、版本门槛、令牌卫生） |
| Supabase MCP Server 节 | 97-115 | 连接排查纪律（四步顺序化） |
| Schema Changes / Debugging / Docs 节 | 117-150 | 工作流纪律（先查文档、advisors 前置、以验证收尾） |

**洞察**：该技能区别于普通文档的核心价值是对抗 LLM 固有缺陷——过时记忆（Principle 1 强制查 changelog）、未验证输出（Principle 2 "A fix without verification is incomplete"）、死循环（Principle 3 "2-3 attempts then stop"）。版本演化史证实这是维护重点：debugging workflows（#112）、changelog 检查（#74）均为此类。**适配时必须保留全部纪律性措辞（must/MUST/never），只替换纪律的指向对象。**

### 4.2 六大核心原则逐条解剖

| # | 原则 | 行号 | 部署无关性 | 适配判定 |
|---|---|---|---|---|
| 1 | 先查 changelog 验证时效 | 13-16 | **部分**——机制优秀，但强制每次 fetch 会诱导云平台特性建议；**该源确实覆盖自建栈破坏性变更**（Kong→Envoy 2026-07-17、PG15→17 2026-05-18） | **改写为三级**：常规任务不强制 fetch；栈升级场景必查 self-hosted 条目；组件版本以部署内实际为准（MCP 结构查询确认） |
| 2 | 改后必验证 | 18-19 | 完全无关 | **原样保留**；验证通道具体化为 MCP execute_sql / 结构查询工具 |
| 3 | 错误恢复不循环 | 21-22 | 完全无关 | **原样保留**；"logs" 具体化为 Kong/PostgREST/GoTrue/Realtime 容器日志 + RDS 控制台日志 |
| 4 | Data API 暴露两层性 | 24-28 | 核心事实成立（GRANT 与 RLS 是两层；自建栈默认 ACL 同样来自初始化 SQL）；**Dashboard settings 页面不存在** | **改写**：页面引用 → `pg_default_acl` SQL 自检 + `alter default privileges` 管理（SQL 现成可用，RDS PG17 行为一致） |
| 5 | 暴露 schema 全表启用 RLS | 30-31 | 原则本体关键且通用 | **保留 + 定义改写**："exposed schema" 判定依据改为 PostgREST `db-schemas` 配置（默认 public）经 Kong 暴露 |
| 6 | 安全清单 | 33-76 | 主体保留 | §4.3 |

### 4.3 安全清单解剖（14 条）

| 分组 | 条目数 | 判定 |
|---|---|---|
| Auth 与 session（user_metadata 禁入授权 / 删用户不失效令牌 / JWT claims 新鲜度） | 3 | **全部保留**——GoTrue 自建栈行为逐条一致（`raw_user_meta_data` 同样可被用户修改、`auth.sessions` 表存在）；补一句执行通道：sign-out 走自研 MCP auth 工具组 |
| API key 与客户端暴露 | 2 | service_role 条**改写**（§7.2 专项）；scoped PAT 条**删除**（无 Management API），原位替换为自研 MCP 两层只读机制（`read_only` 参数 + `HUAWEICLOUD_MCP_READ_ONLY`） |
| RLS / 视图 / 特权代码 | 7 | **6 条原样保留**（security_invoker 在 PG17 直接可用且可删旧版本分支；UPDATE 需 SELECT policy；auth.role() 弃用；BOLA；USING+WITH CHECK；SECURITY DEFINER 两连条）；1 条末句替换（`supabase db advisors` → MCP `get_advisors`） |
| Storage 访问控制 | 1 | **保留 + 现状标注**——规则适用于桶策略模型，但当前对象后端无 S3 凭证，对象级操作不可用；OBS 接入后全量生效 |
| 供应链安全 | 1 | **保留**（supabase-js 分发与部署形态无关；pin 版本 + lockfile + 审计 manifest） |

### 4.4 外部依赖面全景

42 个依赖项、13 个 supabase.com URL。逐节处置结论：

| 章节 | 行号 | 处置 | 要点 |
|---|---|---|---|
| Core Principles | 11-76 | 保留为主 | 2 条改写、1 条删除替换、1 条暂缓标注 |
| **Supabase CLI** | 78-95 | **整节删除，原位重建** | 替换为"自研 MCP 工具清单"节（38 工具分组）；保留"以注册表为准，不凭记忆猜工具名"的纪律 |
| Supabase MCP Server | 97-115 | **改写为自研 MCP** | 保留四步排查骨架（可达性 curl → 配置 → 鉴权 → 权限），全部指向换为我们的事实 |
| Documentation | 117-123 | 改写 | 去 `search_docs`（我们无此工具）；docs `.md` 直取机制保留（对 PostgREST/GoTrue 组件行为有效） |
| Schema Changes Option A（声明式） | 129-131 | **删除** | `supabase/schemas/` + `config.toml` + pg-delta 工作流不存在 |
| Schema Changes Option B（命令式） | 133-146 | **改写（语义升级）** | `execute_sql` 单事务原子批次在我们形态下语义更强；`apply_migration` gotcha 替换为红线条款（无迁移历史表、禁触 `public.migrations`）；`db pull/migration list` 替换为 Git 变更目录 + MCP 结构查询验证 |
| Debugging | 148-150 | 改写 | 云日志体系不存在 → 分层排查清单（DB 侧 pg_stat_activity / 服务侧容器日志 / 平台侧 RDS 控制台）；supabase 调试文档降级为 PostgREST/GoTrue 错误语义参考 |
| Reference Guides（反馈） | 152-155 | 保留 + 改造 | §7.5 |

### 4.5 版本演化与维护重心（对适配版的启示）

2026-06 至 09：主技能发 7 版、规则库发 5 版，约 3-6 周一版。三个维护焦点：

1. **安全指导是最高频主题**（SECURITY DEFINER/auth.role()/BOLA → 供应链 → scoped PAT 贯穿全部版本）——我们的适配版应把安全清单当一等维护对象，栈变更时同步审校；
2. **agent 行为纪律持续加固**——适配版必须保留 must/never 级措辞；
3. **description 被当作正式工程对象迭代**（#194 trigger-rich 优化）——我们 v2.3.0 的 5 条固化触发条件与此实践同源，延续。

### 4.6 反馈机制设计（值得整体移植）

四步流程：征得同意 → 按模板起草（**强制定位到 file + section**，保证可复现）→ 建 Issue（标题 `user-feedback: <summary>`）→ 回传 URL（失败给兜底链接）。agent 模板与人工模板（`.github/ISSUE_TEMPLATE/`）字段同构，双入口同一格式。

---

## 5. 最佳实践技能 `supabase-postgres-best-practices` 深度洞察

### 5.1 本质定性：面向任意 Postgres 的规则引擎

SKILL.md:3 自我声明 *"for Postgres running anywhere"*——**全库零依赖** Supabase CLI、Dashboard、Management API、supabase-js、Supavisor、云配额（grep 验证 0 命中）。它是"由 Supabase 维护的通用规则库"，天然适配自建形态。

### 5.2 规则库结构

**三层索引**：SKILL.md 优先级表（8 分区 × impact 降序）→ `_sections.md` 分区定义（`## N. Title (prefix)` 三件套）→ 按文件名前缀自动归组的具体规则。**单个规则文件从不在索引中被点名**——新增华为云专属分区只需新前缀文件 + `_sections.md` 追加区块 + SKILL.md 表加行，索引自动成立。

**规则文件格式契约**（31 文件 100% 遵循，可复用于我们新增规则）：

```yaml
---
title: 动作导向祈使句标题（与正文 H2 逐字相同）
impact: CRITICAL|HIGH|MEDIUM-HIGH|MEDIUM|LOW-MEDIUM|LOW   # 6 级
impactDescription: 量化收益（如 "5-10x faster multi-column queries"）
tags: 逗号分隔关键词
---
```

正文：1-2 句问题说明 → `**Incorrect:**`（反模式 SQL + why 注释）→ `**Correct:**`（正确模式 + 量化收益注释）→ 可选变体 → 末行固定单链接 `Reference:`。写作五原则：具体转换模式（禁哲学式建议）、错误优先、量化影响、自包含可运行示例、语义化命名。

### 5.3 云浓度分析（哑铃分布）

| 领域 | 云特性密度 |
|---|---|
| **Security & RLS** | **最高**（3/3 全中）：auth.uid() ×6 行、anon/authenticated/service_role 角色 ×2 文件、"non-exposed schema" 术语、链接 ×3 |
| Connection Mgmt | 次高：链接 ×3 + **5432/6543 端口约定** ×1（Supavisor 云端口） |
| Monitoring | 高：链接 ×3 + `create extension pg_stat_statements` 隐含云预载前提 ×1 |
| Data / Query / Advanced / Schema | 低：仅链接；schema 域仅 pg_uuidv7 ×1 文件 |
| **Locking** | **零**（完全纯净） |

supabase.com 链接共 13 处，全部位于文件末行 Reference。**云依赖的本质是"平台符号"（身份函数、预置角色、端口、扩展目录、暴露 schema 术语），不是技术内核**——InitPlan 包装、SKIP LOCKED、keyset 分页等语义 100% 通用。

### 5.4 KEEP / ADAPT / DROP 判定（31 个规则文件）

| 判定 | 数量 | 占比 | 说明 |
|---|---|---|---|
| KEEP | 17 | 54.8% | 正文零云依赖，原文可用 |
| ADAPT-轻 | 9 | 29.0% | 仅替换尾部链接（→ postgresql.org / 华为云文档） |
| ADAPT-重 | 5 | 16.1% | 正文含平台符号需改写（见下表） |
| DROP | 0 | 0% | — |

**ADAPT-重清单**：

| 文件 | 改动点 |
|---|---|
| `conn-prepared-statements.md` | 5432/6543 云端口约定 → 部署方自管池端口表述 |
| `monitor-pg-stat-statements.md` | 补 `shared_preload_libraries` + 重启前置（RDS 上为参数模板 + 控制台重启）；**实测确认**该扩展可装未装 |
| `schema-primary-keys.md` | **实测确认** pg_uuidv7 不可用（可用 uuid 扩展仅 uuid-ossp，不含 v7）→ 主推应用层生成 UUIDv7 或文件自带的时间前缀 text 方案；`uuid_generate_v7()` 疑似笔误（pg_uuidv7 的函数名实为 `uuidv7()`）一并修正 |
| `security-rls-basics.md` | **实测确认**：auth schema 含全部 GoTrue 表但**零函数**——`auth.uid()` 不存在；`anon`/`authenticated`/`service_role` 角色存在（`TO` 子句可用），`authenticator`/`supabase_admin`/`supabase_auth_admin` 缺失。`:41-48` 的 auth.uid() 段**必须改写**为 PostgREST claims 模式：`current_setting('request.jwt.claims', true)::jsonb->>'sub'` |
| `security-rls-performance.md` | `(select auth.uid())` InitPlan 包装技术保留，示例函数替换为 claims 模式等价函数（如 `(select current_setting('request.jwt.claims', true)::jsonb->>'sub')` 或部署统一辅助函数后包装之）；`:50` 角色清单与实际角色对齐；"non-exposed schema" → PostgREST `db-schemas` 表述 |

### 5.5 RDS 特有注意（源自部署形态，非源文件）

4 个文件含 `alter system` 或 SUSET 参数（`conn-limits`、`conn-idle-timeout`、`lock-deadlock-prevention`、`monitor-pg-stat-statements`）——华为云 RDS 非超级用户无 `ALTER SYSTEM` 权限，**须改写为"通过 RDS 控制台参数模板设置"的执行通道**。这是规则库之外的部署形态增量，应形成新的华为云专属规则（§7.4）。

### 5.6 版本约束

零文件显式提及 PG 版本号；4 处隐式版本门槛（`include` 覆盖索引 PG11+、`idle_session_timeout` PG14+、`gen_random_uuid()` PG13+、PG15 public schema 默认权限收紧）在 PG17 全部满足，无需降级处理。

---

## 6. 部署形态差距分析

### 6.1 形态对照

| 维度 | 上游假设（云平台） | RDS Supabase 实况 | 差距性质 |
|---|---|---|---|
| 入口 | 多区域平台 + Dashboard | Kong `:8443` 唯一入口（约 60s 超时） | 触点替换 |
| SQL 通道 | CLI `db query` / MCP | **自研 MCP `execute_sql`**（PostgREST RPC，单事务原子批次，read_only 白名单） | 语义升级（更强） |
| 用户管理 | Dashboard / Management API | 自研 MCP auth 工具组（GoTrue admin API） | 触点替换 |
| 安全建议 | `supabase db advisors` | 自研 MCP `get_advisors`（Splinter lint SQL） | 触点替换 |
| 迁移 | supabase_migrations 表 + CLI 工作流 | **无**（init.sql 五步部署；平台 `public.migrations` 禁触） | 模型替换 |
| 边缘函数 | Edge Functions（Deno） | **华为云 FunctionGraph 工作流**（专用 Skill TODO） | 能力重定向 |
| AI assist | 平台 AI 能力 | **无** | 排除 |
| 连接池 | Supavisor 托管 | 部署方自管（PgBouncer 类） | 责任转移 |
| 日志 | Logs Explorer / ClickHouse | 容器日志 + RDS 控制台 | 通道替换 |
| 文档 | search_docs MCP + supabase.com docs | docs `.md` 直取（组件行为部分）+ web search | 降级可用 |
| 密钥体系 | publishable/secret 双层 + scoped PAT | anon JWT / service_role JWT（静态无过期，Kong 层校验）+ MCP 两层只读 | 模型改写 |

### 6.2 四大约束的边界固化

1. **Edge Functions → FunctionGraph**：上游 description 触发词中的 "Edge Functions" 移除；正文 Debugging 节的 Edge Function 崩溃场景移除；新增路由条款："服务端计算/定时任务/Webhook → 华为云 FunctionGraph 工作流（专用技能规划中，当前参考华为云 FunctionGraph 官方文档）"。**占位设计**：在适配版主技能正文中以固定措辞引用，待专用 Skill 发布后改为一行触发路由。
2. **无 CLI**：整节删除并原位重建为自研 MCP 工具清单；所有 `supabase <cmd>` 引用逐处替换。
3. **无 AI assist**：触发词与正文零引用。
4. **无 migration**：Option A/B 工作流合并改写为 init.sql 五步部署（与既有 `rds-supabase-mcp` 技能的部署工作流**保持同一套术语**：预检 → 审查 → 部署 → 授权暴露 → 查询确认）；**占位设计**：正文注明"结构化迁移系统由后续 supabase mcp 版本提供"，触发词暂不收录 migration 相关词以免误导。

### 6.3 实测探针结果（2026-11-06，真实例，经自研 MCP execute_sql / list_available_extensions）

| 探针 | 查询 | 结果 | 对适配的直接影响 |
|---|---|---|---|
| auth schema 函数 | `pg_proc` × `pg_namespace(nspname='auth')` | **零函数**（无 `auth.uid()`/`auth.jwt()`/`auth.role()`） | 上游所有 `auth.uid()` 示例必须替换为 `request.jwt.claims` 模式或先部署辅助函数（§7.4） |
| auth schema 对象 | `pg_class` × auth schema | 全部 GoTrue 表在位（users/sessions/refresh_tokens/mfa_*/oauth_*/saml_*/webauthn_*）+ `auth.schema_migrations`（GoTrue 内部迁移表，与 supabase_migrations 无关） | GoTrue 数据模型完整，删用户不失效令牌等安全条款成立的依据确认 |
| 平台角色 | `pg_roles` 过滤 | `anon`/`authenticated`/`service_role` **存在**；`authenticator`/`supabase_admin`/`supabase_auth_admin`/`supabase_storage_admin` **缺失** | `TO authenticated`/`TO anon` 子句可用；部署属**半初始化形态**（GoTrue 自建表 + 三角色在位，标准 supabase 初始化 SQL 的函数与管理员角色部分未执行）——安全清单中涉及 `supabase_auth_admin` 类角色的表述需剔除 |
| uuid 类扩展 | `pg_available_extensions` name ~ '%uuid%' | 仅 `uuid-ossp`（未装，v1/v4）；**无 pg_uuidv7** | `schema-primary-keys.md` 的 UUIDv7 方案不可用，改推应用层生成或时间前缀 text 方案 |
| 核心扩展 | 定向查询 | `pg_net` 0.20.2 已装、`vector`（pgvector）**0.8.2 已装**、`pg_stat_statements` 可装未装、`pg_cron` 可装未装、**无 pgmq** | **Vectors 触发词可保留**（pgvector 在位）；Cron/Queues 触发词移除（未装/不可用）；`monitor-pg-stat-statements.md` 改造必要性坐实（需 RDS 参数模板 + 重启后 `create extension`） |

**半初始化形态的洞察**：该部署的初始化状态介于"纯 GoTrue 自建"与"标准 Supabase 栈"之间——数据层完整、身份辅助函数层缺失。这决定了适配版技能的 RLS 身份判定**唯一可靠通道**是 PostgREST 的 `request.jwt.claims` GUC（`current_setting('request.jwt.claims', true)::jsonb->>'sub'`）；同时催生一条高价值新规则：部署统一的身份辅助函数（`auth.uid()` 等价物）作为平台 bootstrap 的可选整改项（§7.4 `rds-auth-helpers`）。

---

## 7. 适配整改方案

### 7.1 技能包设计（建议，待确认）

| 项 | 方案 | 理由 |
|---|---|---|
| 技能族 | `rds-supabase-mcp`（管理层，已有）+ `rds-supabase`（开发操作层，适配自主技能）+ `rds-supabase-postgres-best-practices`（质量层，适配自规则库） | 三层覆盖；命名遵循 agentskills.io 规则（小写连字符、匹配目录名） |
| 发布位置 | 先落主仓 `skills/`（复用现有 CI / validate 基建与统一版本管理），`npx skills add fitz-liujian/huaweicloud-rds-supabase-mcp` 即可分发；独立 agent-skills 仓留作后续分发升级 | 主仓技能族一致性优先 |
| 语言 | 与既有 `rds-supabase-mcp` 技能一致（中文正文 + 英文触发词混合的 description），规则库 Incorrect/Correct SQL 示例保持英文 SQL 惯例 | 对外发布的客户群与既有技能统一 |
| 版本策略 | 适配版从 `0.1.0` 起版（区别于上游版本线，避免与上游 0.1.9/1.6.0 混淆）；**不引入 Release Please**，版本由人工 bump + pytest 契约锁定（A6） | 上游自动 bump 已证实失效；我们仓库现有发版流程无需引入 Node 工具链 |
| 上游同步 | 保留 `UPSTREAM.md` 记录基线 commit `c9be0e9` 与改动清单，便于后续 diff 上游更新 | 长期维护成本控制 |

### 7.2 主技能逐节处置矩阵（核心交付物）

| 适配版章节 | 来源 | 处置 | 关键内容 |
|---|---|---|---|
| 核心原则 1（时效验证） | SKILL.md:13-16 | 改写 | 三级：常规不强制 fetch / 栈升级必查 self-hosted changelog（重点盯 Kong→Envoy 类网关变更）/ 版本以部署内实测为准 |
| 核心原则 2-3（验证、恢复） | :18-22 | 原样保留 | 验证通道具体化（MCP 工具）；日志源具体化（容器 + RDS 控制台） |
| 核心原则 4（Data API 暴露） | :24-28 | 改写 | `pg_default_acl` 自检 SQL + `alter default privileges` 撤销语句内联；GRANT/RLS 两层性注释保留 |
| 核心原则 5（RLS 覆盖） | :30-31 | 保留 + 定义改写 | exposed schema = PostgREST `db-schemas` 经 Kong 暴露 |
| 核心原则 6（安全清单） | :33-76 | 主体保留 | §4.3 判定：11 保留 / 2 替换 / 1 标注；service_role 条采用专项改写文本（静态无过期 JWT / Kong 校验 / 泄露 = 轮换全部 JWT secret 的运维级事故） |
| **自研 MCP 工具清单**（新） | 原位替换 CLI 节 :78-95 | 重建 | 38 工具 8 分组清单 + "以注册表为准不猜工具名"纪律 + 两层只读机制 |
| 自研 MCP 排查 | 原 MCP 节 :97-115 | 改写 | 四步骨架保留（可达性 curl → 客户端配置 → 鉴权 → 只读拦截检查），全部指向自研事实 |
| 文档访问 | :117-123 | 改写 | 优先级：本技能 references → 组件文档 `.md` 直取 → web search |
| **部署后端定义（五步）** | Option B :133-146 改写 | 语义升级 | execute_sql 单事务原子批次；红线条款（无迁移历史表 / 禁触 public.migrations）；advisors 前置；Git 变更目录 + 结构查询验证；与 `rds-supabase-mcp` 技能同一套五步术语 |
| 调试工作流 | :148-150 | 改写 | 分层排查（DB `pg_stat_activity`/`pg_stat_statements` → 容器日志 → RDS 控制台）；错误语义参考降级保留 |
| FunctionGraph 路由（新） | 无 | 新增 | 服务端计算/定时任务/Webhook → FunctionGraph；专用技能 TODO 占位 |
| 技能反馈 | :152-155 | 改造 | 指向本仓 Issue；模板增加 "Platform delta?" 字段（区分上游行为 vs 华为云特有行为）；示例替换为真实场景 |

**触发 description 重写要点**：移除 Edge Functions / CLI / migrations / Logs Explorer / ClickHouse / pg_graphql 触发词；新增 self-hosted、RDS、Kong、PostgREST、GoTrue、FunctionGraph、init.sql、execute_sql 触发词；保留 supabase-js / @supabase/ssr / 框架集成 / auth 症状清单（login、sessions、JWT、cookies、getSession、getUser、RLS）——这部分部署无关且是高价值触发面。

### 7.3 规则库改造清单（14 个文件）

- **9 个 ADAPT-轻**：仅末行 Reference 链接替换（→ postgresql.org 官方文档 / 华为云 RDS 文档），正文零改动；
- **5 个 ADAPT-重**：按 §5.4 表逐项改写（端口表述 / 参数模板前置 / uuidv7 核实与笔误修正 / auth.uid() 段按实测定稿 / 角色清单对齐）；
- **配套**：SKILL.md 触发 description 增补华为云语境（RDS、自建栈、Kong 超时）；`_sections.md` 与优先级表追加华为云专属分区（§7.4）。

### 7.4 新增华为云专属规则（`rds-` 前缀分区候选）

当前 31 规则完全空白、且与我们的形态强相关（`rds-jwt-claims-rls` 与 `rds-auth-helpers` 经实测确认必要性，列为首批）：

| 规则 | impact | 依据 |
|---|---|---|
| `rds-jwt-claims-rls`：RLS 身份判定用 `current_setting('request.jwt.claims', true)::jsonb->>'sub'`（含 InitPlan 包装 `(select …)` 变体） | **CRITICAL** | §6.3 实测：auth.uid() 不存在，此为本部署唯一可靠通道 |
| `rds-auth-helpers`：部署统一身份辅助函数（`auth.uid()` 等价物，`security definer` + 最小授权）作为平台 bootstrap 可选整改 | HIGH | §6.3 半初始化形态；装好后上游规则示例可原样复用 |
| `rds-parameter-template`：参数变更走 RDS 控制台参数模板，非 `ALTER SYSTEM`（非超级用户无权限） | HIGH | §5.5，4 个既有规则文件的执行通道修正 |
| `rds-pool-ports`：自管 PgBouncer 事务/会话双端口规划与预备语句兼容 | HIGH | 替代 Supavisor 端口约定 |
| `rds-exposed-schemas`：PostgREST `db-schemas` 暴露面治理 | HIGH | "exposed schema" 概念的部署方表述 |
| `rds-outbound-http`：pg_net + FunctionGraph 的出站调用与定时任务范式（替代 pg_cron + Edge Functions） | MEDIUM-HIGH | 实测确认 pg_net 0.20.2 在位、pg_cron 未装 |
| `rds-kong-timeout`：60s 网关超时下的批次拆分 | MEDIUM | 实测约束 |

### 7.5 反馈闭环与 TODO 占位

- 反馈三件套移植：`references/skill-feedback.md` + `assets/feedback-issue-template.md` + 仓库 `.github/ISSUE_TEMPLATE/user-feedback.md`；提交命令化（`gh issue create -R …`）；私有仓库补充"不可达时直接交维护者"降级路径；模板加 "Platform delta?" 字段；
- **两个 TODO 占位**（正文固定措辞，发布后改路由）：
  - FunctionGraph 专用 Skill："服务端计算、定时任务、Webhook 处理使用华为云 FunctionGraph 工作流；专用操作技能规划中，当前参考华为云 FunctionGraph 官方文档"
  - 迁移系统："结构化迁移管理将由后续 supabase mcp 版本提供；当前 schema 变更使用 init.sql 五步部署"

### 7.6 发布契约测试（pytest，移植上游隐式契约为显式断言）

| # | 校验 | 来源 |
|---|---|---|
| A1 | `skills/` 目录白名单严格相等（防止技能混入/改名失控） | sanity.test.ts L14-17 |
| A2 | frontmatter 字段集 ⊆ {name, description, license, allowed-tools, metadata, compatibility}；name NFKC + 1-64 字符 + `^[a-z0-9]+(-[a-z0-9]+)*$` + 匹配目录名；description 1-1024 字符；metadata.version 为 semver | 官方 skills-ref validator 语义 |
| A3 | 正文 <500 行 | AGENTS.md L152 |
| A4 | 禁含 README.md / INSTALLATION_GUIDE.md / QUICK_REFERENCE.md | AGENTS.md L217-225 |
| A5 | references 前缀与 `_sections.md` 分区一致 | AGENTS.md L50 |
| A6 | **版本一致性**：SKILL.md metadata.version == 发布清单版本（堵上游漂移漏洞） | 本报告 §3.4 |
| A7 | description 最低信号：长度 ≥80 且含触发词标记（"Use when" / "Triggers:" / "触发"） | #194 trigger-rich 实践 |

### 7.7 实施阶段划分（待批准后执行）

| 阶段 | 内容 | 产出 | 验证 |
|---|---|---|---|
| P1 契约基建 | pytest 契约测试 A1-A7 落地（先约束既有 `rds-supabase-mcp` 技能） | `tests/test_skill_contract.py` | CI 绿 |
| P2 规则库适配 | 31 文件迁移 + 14 文件改造 + `_sections.md`/SKILL.md 重写 + `rds-` 分区首批规则（先 2-3 条高价值） | `skills/rds-supabase-postgres-best-practices/` | 契约测试 + 内容评审 |
| P3 主技能适配 | §7.2 处置矩阵全量执行 | `skills/rds-supabase/SKILL.md` + references | 契约测试 + 双技能触发路由演练 |
| P4 反馈闭环 + 收尾 | 反馈三件套、UPSTREAM.md、双语 README 更新、CHANGELOG | 发布就绪 | 全量 CI + 人工终审 |

---

## 8. 关键决策点与风险

| # | 决策点 | 结论 | 状态 |
|---|---|---|---|
| D1 | 三个技能的触发边界（`rds-supabase` vs `rds-supabase-mcp` 在 schema 变更/调试/安全检查上有重叠） | 建议在三者 description 中显式互斥路由：rds-supabase-mcp = MCP 服务器管理与实例操作；rds-supabase = 平台开发与集成；best-practices = SQL/schema 质量前置。风险：路由不清会致误触发/双触发 | **待确认** |
| D2 | `security-rls-basics` 的 auth.uid() 段定稿 | **已实测定稿**（§6.3）：auth.uid() 不存在，改用 `request.jwt.claims` 模式；三平台角色在位，`TO` 子句可用 | ✅ 已解决 |
| D3 | pg_uuidv7 可用性 | **已实测定稿**（§6.3）：不可用；改推应用层生成 UUIDv7 或时间前缀 text 方案 | ✅ 已解决 |
| D4 | 是否引入 Release Please | 不引入（上游机制已证伪；人工 bump + A6 锁定） | 建议，待确认 |
| D5 | 规则库 31 文件的语言 | SQL 保持英文惯例，说明文字中文化；由 UPSTREAM.md 控制与上游的 diff 成本 | 建议，待确认 |
| D6 | Vectors / Cron / Queues 触发词去留 | **已实测**：pgvector 0.8.2 在位 → Vectors 保留；pg_cron 未装、无 pgmq → Cron/Queues 移除 | ✅ 已解决 |

---

## 9. 附录：数据汇总

| 指标 | 值 |
|---|---|
| 仓库基线 | `c9be0e9`（chore: release main #609） |
| 主技能依赖项总数 | 42（外部 URL 13 个） |
| 主技能整节处置 | 保留 4 节 / 改写 5 节 / 删除重建 1 节 / 删除 1 节 |
| 安全清单判定 | 11 保留 / 2 替换 / 1 暂缓标注 |
| 规则库判定 | KEEP 17 / ADAPT-轻 9 / ADAPT-重 5 / DROP 0 |
| 云特性分布 | Security&RLS 最深；Locking 零；链接 13 处全在末行 |
| 扩展提及 | pg_cron/pgmq/pgvector/pg_net 在规则文件中零出现 |
| PG 版本 | 零显式提及；4 处隐式门槛 PG17 全满足 |
| 上游缺陷 | extra-files expressions 三重失效；版本漂移 7/5 个版本 |
| 分发通道 | 3 条；`npx skills add` 对我们立即可用 |
| 实测探针 | auth.uid() 缺失；三平台角色在位；pgvector 0.8.2 已装；pg_uuidv7 不可用；pg_stat_statements 可装未装 |

---

*本报告由 3 个并行研究代理的调研结果与人工精读综合而成；所有 file:line 引用经交叉验证。D2/D3/D6 三项实测已于 2026-11-06 完成，结论并入正文；实施前仅余 D1/D4/D5 三项方案级决策待确认。*
