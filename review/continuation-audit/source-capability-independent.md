独立结论：**PASS_SOURCE_CAPABILITY_BOUNDARIES_NOT_ADAPTER_ACCEPTANCE**。原来源审计对“当前无法完成两份冻结方案最终评价”的结论成立；没有理由据此放宽规则、补写旧方法或宣称数据渠道全部不存在。本次只读旧计划、旧原包和来源审计，重新打开官方帮助页；未下载新行情、未运行新 normalizer/outbox，也未修改旧审计或生产原件。

- 旧 ZIP 独立重新解码：SHA-256 `34a7e077c89ade3d60e5afe26e615bcf2df10fdfab04930b62d185810e8f698c`、12,419 字节；CSV 2,103 行、482 合约，CRC/成员 hash/全行有限十进制/整数毫秒/联合键无重复等 11 项相符。全部时点落于 `[2026-09-20T16:00Z,2026-09-21T16:00Z)`，与标称 9/21 的 UTC+8 日相容。BTC 三时点为 9/20 16:00、9/21 00:00、08:00 UTC。该相容性不证明文件无漏事件，也不满足完整 9/21 UTC 日的覆盖证明；原研究对其目标 UTC 窗口不足的记录仍成立，不能反推源文件本身损坏或缺行。
- 官方 FAQ 第 10 项独立确认 **K 线下载**的本地日换算与两日后可下载声明；它不是资金费/交易弹窗的独立证明。原审计作者在这些弹窗观察到 UTC+8/两日及字段说明，保留为其第一手记录；本次未重新操纵用户浏览器，也不把其手工转录算作第二次独立抓取。两日声明不证明实际准时率、精确发布时间或未来包已经可得。[官方 FAQ](https://www.okx.com/help/candlestick-faqs-and-settings)
- `trade_id` 的唯一性只能用于身份区分。没有另外的官方时序/连续性契约，就不能依其大小或文件行号裁定同毫秒首笔，也不能依不连续 ID 推断缺成交。原审计对此保留 UNKNOWN 正确；本次未取得目标 tick CSV，未验收其解码或排序。
- 所查入口没有找到精确 settlement mark 或完整 mark 路径，结论限于**已审查来源没有满足原要求的证据**。不能外推成所有官方/其他渠道都没有 mark。官方机制确认资金费用依赖 mark，结算周期可变、assessment 时间有其语义，最近成交价/OHLC/固定八小时表不能代替原方案所需的实际输入。[资金费机制](https://www.okx.com/en-sg/help/perps-funding-fee-mechanism)
- 官方不保证完整和准确的条款不是具体文件缺行的证明；SHA、CRC、日期一致及无重复也不是事件全集证明。完整性必须继续为 UNKNOWN，不能从免责声明直接认定“有缺行”，也不能从 ZIP 完整直接认定“全事件齐备”。[历史数据条款](https://www.okx.com/help/historicaldata-terms-and-conditions)

原两份计划的 canonical SHA 与前次独立审计一致；原入退场窗口、精确资金费 mark、完整轨迹和实际成本未知边界均保持。允许下一步实现严格 funding 离线归一化，其输出仍应 `coverage=UNKNOWN`、`settlement_mark=null`；方法只能证明给定字节按固定 schema 解码，不能自证官方取得、时间真实性、全事件覆盖或经济结果。正式 WAITING_DATA outbox 另行审查，不能由此提前验收。

对应可复算字段、原审计哈希与本次来源边界见 `source-capability-independent.json`。此报告不新增收益、模拟成交、自然触发或方案执行资格。
