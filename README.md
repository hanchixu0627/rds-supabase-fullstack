# huaweicloud-mcp

> **语言切换：** [English](./README_en.md) | 中文

华为云 MCP Server 共享仓库：为每个华为云服务提供场景化的 MCP 工具，支持本地（stdio）
与远程（streamable-http）部署。

## MCP Server 列表

### 管理与治理

- **[RFS MCP](server/mcp_server_rfs/README.md)**：资源编排服务——HCL 模板一键部署为资源栈、
  执行计划干跑预览、失败部署根因诊断、安全下线。
- **[RC MCP](server/mcp_server_rc/README.md)**：资源中心——全局资源检索与分组管理、资源关系
  查询、ResourceQL 高级查询。

### 数据库

- **[RDS Supabase MCP](server/mcp_server_rds_supabase/README_zh.md)**：华为云 RDS PostgreSQL 上的
  自建 Supabase（BaaS）平台管理——库表结构与数据查询、RLS 安全策略、SQL 执行（init.sql 迁移
  部署）、GoTrue 用户管理、存储桶配置、advisors 诊断。自带 vendored 核心库（1.2.0）与独立
  uv 锁，支持 Docker 部署。

## 开发者文档

完整开发指南见 [docs/development/](docs/development/README.md)，按功能特性拆为 10 篇：核心包逐模块 API、
工具场景化方法论、service/client 层、护栏、输出错误、三层测试、从零建服务实战、
工程化与发布。参考实现：`server/mcp_server_rfs/`；脚手架：`docs/development/template/`。

## 核心能力（所有服务共享）

- 简化认证：`HUAWEICLOUD_ACCESS_KEY / SECRET_KEY / REGION`，project_id 经 IAM 自动解析
- 安全护栏：风险分级（READ/WRITE/DANGEROUS）、DANGEROUS 二次确认、资源保护名单、
  输出脱敏、结构化审计（默认开启）
- 输出治理：结构化 JSON + token 预算（默认 20 条、字段白名单、超长截断）
- 只读模式：`HUAWEICLOUD_MCP_READ_ONLY=true` 一键拦截全部写操作

## 快速开始

```bash
cd server/mcp_server_rfs
uv sync
export HUAWEICLOUD_ACCESS_KEY=... HUAWEICLOUD_SECRET_KEY=... HUAWEICLOUD_REGION=cn-north-4
uv run mcp_server_rfs
```

## 新服务接入

参见 [docs/08-new-service-walkthrough.md](docs/development/08-new-service-walkthrough.md)：
提 issue → 复制脚手架模板 → 三层开发 → 自测 → 双语 README → PR 审查。

## Agent Skills

`skills/` 目录提供按 Agent Skills 开放标准编写的技能（可用 `npx skills add` 安装）：

- **[rds-supabase-mcp](skills/rds-supabase-mcp/SKILL.md)**：RDS Supabase MCP 服务器使用技能——
  安装配置、38 工具用法、init.sql 五步部署流程与验证方法。
- **[rds-supabase](skills/rds-supabase/SKILL.md)**：RDS Supabase 平台应用开发技能——客户端集成、
  认证、schema 变更、RLS 调试速查与服务端计算路由。
- **[rds-supabase-postgres-best-practices](skills/rds-supabase-postgres-best-practices/SKILL.md)**：
  Postgres 最佳实践规则库——按症状直达规则文件，含华为云 RDS 部署专属规则。
- **[huawei-supabase-frontend](skills/huawei-supabase-frontend/SKILL.md)**：私有 OBS＋CDN 静态前端部署技能——构建环境准备、接入已有华为云 RDS Supabase、版本发布、更新、回退与真实入口验收。
- **[huaweicloud-mcp-dev](skills/huaweicloud-mcp-dev/SKILL.md)**：本仓库 MCP 服务器开发指南。

## License

MIT
