# 工作电脑0.3.8a1阶段二结果（2026-11-07）

证据来源：用户提供工作电脑完整报告，非本机Windows复现。报告路径：`D:\download_from_web\verify-038a1-reports\02-阶段二离线验收报告.md`。不保存真实资源标识或凭据。

- 包内93文件校验、verify_delivery目标/校验、安装、pip check及6项离线诊断通过；加载MCP/Skill为0.3.8a1，29工具清单一致。
- unittest为124项中123通过、1error：test_legacy_database_keeps_records，Windows临时目录清理报WinError32。阶段二判定**安装/诊断通过，测试未全通过**。
- 本机核实测试代码用sqlite3.Connection事务上下文未close；增加“退出后连接已关闭”断言，在修复前失败。修复采用contextlib.closing，并保留事务上下文及旧记录兼容断言。未跳过测试，不改变产品账本状态。
- 外部同版archive-sha256.txt未传到工作电脑。报告中ZIP摘要与开发方此前发布校验一致：`a50a312526156a96eddb783d3389af243546933e99061ff13dc5d5eb2b59ee90`。这是事后交叉核对；包内清单不替代独立发布摘要。下一包需同时传两附件。
- 0.3.8a2作为不可变的新修正版发布，不覆盖0.3.8a1附件。工作电脑复验前不关闭Windows问题。
- 尚未执行本版云端只读/新增写/Agent/码道验收；保留旧环境和账本。配置检查不等于网络/鉴权成功，工具清单不等于接口可执行。

网络准备：RDS沿用此前验证项目/原生入口（由本地配置提供）；VPC入口待环境负责人确认。SDK Core3.1.220经Requests进行TLS验证，当前程序未显式设置HttpConfig.ssl_ca_cert，因此应使用REQUESTS_CA_BUNDLE指定可信CA；仅SSL_CERT_FILE不足以保证SDK采用。缺CA是独立网络阻塞，不再次绕过TLS。没有证据证明某个历史CA文件仍存在。
