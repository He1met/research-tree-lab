# 真实首轮研究交接

首轮已完成真实官方下载、小样本审计、独立机制资料研究与实际费用情景反证。正式原档由主代理通过受控 Store 提交；本子任务没有写 store、Git 或任务调度。

## 待受控提交输入

- `research/bootstrap-v1/research_bundle.json`：12 条记录；3 轮（2 个独立根及 1 个真实发现派生后继）、2 份前向交易方案、2 个真实执行、4 产品能力卡、1 个采用研究发现的决定。
- SHA-256：`ecc7895fa0436b13f8ebcf8776e585e1d2176bf751fa32265e5b1f9463dd0d6f`。
- `research/bootstrap-v1/discovery_bundle.json`：A-H 八类与 I 独立复现，9 条种子；仅登记不等于执行九种策略。
- SHA-256：`4a3b4dcf1e63ee046869146c205a27c38a9a296b3ccb3f798d16238b9d3a344a`。
- 主 round 的 `disclosure.public_attachments` 已显式列出允许公开的自撰附件。

## 真实证据与边界

官方 ZIP：12,419 bytes，SHA-256 `34a7e077c89ade3d60e5afe26e615bcf2df10fdfab04930b62d185810e8f698c`；CSV 2,103 行、482 个合约，四目标各 3 行。原协议在打开数据前封存。样本日期与预定 UTC 日边界不一致，原协议未改；QQQ 实际非零资金费反证利率项零等于资金费零。

原件与官方文档现已复制到安装定义的稳定 `data_root` 下 `okx/research-bootstrap-20260923-v1/`，按文件逐项验证哈希，见该目录 `STABLE_COPY_RECEIPT.json`。`data/incoming/research-bootstrap/` 保留初始副本。原件只在本机，不能公开 Git 或 Release；官方条款未确认再分发许可。

本机完整审计可使用稳定目录的 ZIP 调用 `research/bootstrap-v1/audit_funding.py`。`verification_receipt.json` 确认原件 CRC/哈希、独立 Decimal 合计、同输入审计重算及派生情景重算一致。失败信息没有删除：先期 BTC 搜索无结果后，官方“全部”选项成功导出。

## 已冻结的前向方案

`p-btc-funding-short-20260923@1` 与 `p-btc-funding-long-control-20260923@1`，具体标的 BTC-USDT-SWAP、1 张 = 0.01 BTC。封存于 2026-09-22 18:02:02 UTC；计划 2026-09-23 00:05 入场，2026-09-24 00:05 退出（每次只容许随后 1 分钟内首个目标成交）。这些是研究模拟规则，未授权交易。

最近已取得资金费信号、交易数量、入/退出、重复进入、终点、费用情景与缺数处理完整保存于 `forward_plans.json`。未来目标成交/标记路径、实际结算费及真实手续费未齐，所以 `INCOMPLETE_DATA`，实际净收益为未知，执行条件 UNKNOWN。日复核不能清空持仓或重置累计费用；终点缺数继续 MISSING_DATA，不能强记 FINAL。相反方向对照只匹配绝对数量与时间，不具有同一市场 beta，不相加为账户收益。

## 公开派生恢复包

`research/bootstrap-v1/public-derived-research.zip`，SHA-256 `86acbf1c6b8b9de91bcb025880d64fbc05ca284845267a042d1b3e21a7df84d6`。`PUBLIC_MANIFEST.json` 列出 17 个文件和精确哈希。独立新目录校验清单后运行 `reproduce_derived.py`、`cost_stress.py`，应分别与保存输出一致。

可恢复范围为自撰研究与派生算术，不能冒充恢复完整原始交易所数据。源数据远端备份未完成。原始 CSV/ZIP/HTML 不在公开包。

## 验收映射与接续

- A01：已完成无复核启动的真实官方数据研究；A02/A04：独立股票会话根已做真实资料核验。
- A03：A-I 唯一机制签名；费用计算属于原后继，不虚报新独立机制。
- A05：已实际计算完整双边费用情景反证，性质为条件会计检验，非真实交易结果。
- A06/A08/F07：自然独立复核、两个自然研究时点及反馈采用尚未发生，`WAITING_NATURAL_OUTCOME`。
- B01：四产品身份、单位、参考/成交/标记/指数与费用分别保存；B02：INTC 仅禁用扩展示例。
- B07/B08：未知费用不填零，取得与事件时间不同，前向封存早于生效。
- E07：原件 LOCAL_ONLY，公开仅自撰材料与派生诊断；E10 只能验公开派生恢复，不能宣称原始证据完整远端恢复。
- F01/F07：本轮是官方应用研究子代理的 manual safe trial，`native_task_id=null`；不冒充原生 Run now 或 scheduled。

唯一下一动作：主代理校验以上 SHA 后正式提交、派独立复核并发布。自然后续由已配置原生任务在窗口真实发生且官方文件可得时继续；不需要用户再说继续。
