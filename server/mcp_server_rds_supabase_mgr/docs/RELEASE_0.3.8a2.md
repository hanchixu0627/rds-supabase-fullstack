# 0.3.8a2 Windows验收修正版

修复test_legacy_database_keeps_records测试夹具使用sqlite3.connect事务上下文但未关闭连接的问题，Windows会在清理临时目录时报WinError32。增加跨平台关闭断言，保留原有旧账本迁移兼容性断言；不跳过失败，不忽略清理错误。

产品业务代码、29工具及安全策略保持0.3.8a1不变。修正版需工作电脑重新验收，不能把macOS本地测试结果记作Windows通过。Skill仅版本标注更新。

0.3.8a1用户报告为123通过/1error，安装和离线诊断通过，详见WORKSTATION_0.3.8a1_RESULTS.md。SDK CA配置说明更正为REQUESTS_CA_BUNDLE；不关闭TLS、不假设证书文件已存在。后续流程见NEXT_WORKSTATION_PROMPT.md。
