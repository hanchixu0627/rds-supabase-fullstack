# hw-rds-supabase-py 全工具端到端测试报告（v0.3.0，38 工具）

- 日期：2026-11-05（auth 用户组 0.3.0 admin API 改造后的回归）
- 被测：`mcp-server-huaweicloud-rds-supabase` **0.3.0**（38 工具；auth 五件套经官方 GoTrue auth admin API 通道）
- **测试方式：真实 MCP 客户端**——官方 MCP Python SDK（`ClientSession` + `stdio_client`），标准握手（协议 2025-11-25）、`list_tools`、`call_tool`
- 目标实例：华为云 RDS Supabase（完整栈：Kong + PostgREST + GoTrue + Storage API + RDS PG）
- 机器可读证据：`full-tool-test-results.json`；可复跑：`python3 docs/validation/run_full_tool_test.py`
- 历史版本：43 工具/86 用例（git 历史）、38 工具/81 用例（0a46a86）

## 结论

| 指标 | 结果 |
|---|---|
| 用例总数 | **89** |
| 通过 | **89** |
| 失败 | **0** |
| 工具覆盖 | **38/38** |
| **auth 用户组（新增）** | **13/13 全过**：真实创建→读取→更新（metadata 替换+updated_at）→重复邮箱（422/500+23505 上游原文）→删除→二次删除→404 验证 |
| 分页正确性 | limit/offset 窗口与 SQL `ORDER BY created_at DESC` 通道**逐一比对一致**（2 窗口） |
| Supabase 数据清理 | **通过**（schema CASCADE + regclass 空校验 + list_tables 基线一致 + auth scratch 用户 n=0） |
| 总判定 | **全部通过**（exit=0） |

## 分组概览

| 分组 | 用例 | 通过 | 失败 |
|---|---:|---:|---:|
| 表层 | 1 | 1 | 0 |
| 基线 | 1 | 1 | 0 |
| 夹具搭建 | 15 | 15 | 0 |
| database 组 | 11 | 11 | 0 |
| project 组 | 4 | 4 | 0 |
| auth_users 组（真实生命周期） | 12 | 12 | 0 |
| storage 组 | 2 | 2 | 0 |
| platform 组 | 9 | 9 | 0 |
| inspection 组 | 30 | 30 | 0 |
| 清理 | 4 | 4 | 0 |

## auth_users 组生命周期用例明细

| 用例 | 工具 | 验证内容 | 结果 |
|---|---|---|---|
| T18 | `list_auth_users` | 真实用户列表、7 字段映射形状（app_metadata→raw_app_meta_data） | PASS |
| T18b | `list_auth_users` | limit=2/offset=1 窗口与 SQL 通道 id 序列一致 | PASS |
| T18c | `list_auth_users` | limit=3/offset=3 窗口与 SQL 通道 id 序列一致 | PASS |
| T19 | `get_auth_user` | 按 ID 读取真实用户，email 匹配 | PASS |
| T19b | `get_auth_user` | 不存在用户 → 上游原文 'User with ID ... not found.' | PASS |
| T21 | `create_auth_user` | 真实创建 scratch 用户（GoTrue 哈希、email_confirm） | PASS |
| T21b | `create_auth_user` | 重复邮箱 → 422/email_exists → 上游原文 'likely already exists.' | PASS |
| T22 | `update_auth_user` | 真实更新（metadata 全量替换 + updated_at 返回） | PASS |
| T22b | `update_auth_user` | 更新重复邮箱 → 500/23505 → 上游原文 'for another user.' | PASS |
| T22c | `update_auth_user` | 更新不存在用户 → 上游原文 not-found | PASS |
| T20 | `delete_auth_user` | 真实删除 → 上游原文成功消息 | PASS |
| T20b | `delete_auth_user` | 再次删除 → 结构化上游 not-found 消息 | PASS |

## 已知行为差异（auth 组，文档化）

1. 时间戳为 GoTrue ISO 8601 格式（上游为 Postgres 文本格式）；字段名映射回上游 7 字段形状。
2. `role` 参数仅保签名：create 不透传（GoTrue 恒为 authenticated）；update 仅 role 时明确报 unsupported。
3. GoTrue 会自动丰富 metadata（provider/providers/email_verified），上游裸 SQL 不会。
4. 通道前提：`SUPABASE_SERVICE_ROLE_KEY`（无需 DATABASE_URL）。
