# OKX 官方下载来源与固定 adapter 审计

结论：**BLOCKED_FOR_FROZEN_FORWARD_PLAN_FINALIZATION**。已核实资金费率真实文件及官方 UI 字段，尚未找到可证明精确结算 mark、完整 mark 路径、同毫秒首笔成交顺序及事件无遗漏的官方下载材料。因此不能仅靠未来日包发布就自动把两份 BTC 方案升为 FINAL。

本次只读核实 `p-btc-funding-short-20260923@1`、`p-btc-funding-long-control-20260923@1`。目标为 `BTC-USDT-SWAP`，入场窗口 `[2026-09-23T00:05Z,00:06Z)`、出场窗口 `[2026-09-24T00:05Z,00:06Z)`；冻结规则要求首笔合法成交、持仓内所有实际结算费率及其实际结算 mark、源 mark 事件权益路径。没有计算新的收益、成交或交易信号。

## 真实来源与观察

2026-09-22 19:05:58–19:06:10 UTC，通过[OKX 官方历史数据页](https://www.okx.com/zh-hans/historical-data)的资金费率日期选择器重新观察到：

> 每日的文件数据为 00:00 ~ 23:59 (UTC+8) 期间的数据。

同一 UI 声称交易、K 线、资金费率数据两日后开放下载。此为发布规则声明，尚未验收实际准时率或精确发布时间。[官方 K 线 FAQ 第 10 项](https://www.okx.com/help/candlestick-faqs-and-settings)也明确上一日 16:00 UTC 至当日 15:59 UTC 的分区及两日发布延迟。

此新事实解释了旧文件 `allswap-fundingrates-2026-09-21.zip` 内的 BTC 三个时点（9/20 16:00、9/21 00:00、08:00 UTC）为何可能覆盖其本地日。**它仍不覆盖原研究要求的完整 9/21 UTC 日**：后者至少需本地日期 9/21、9/22 的分区联合，且不能由三个点证明没有其他结算事件。本轮只追加审计说明，未改旧研究或计划原件。

## 数据能力与缺口

| 要求 | 已核实证据 | 判定 |
|---|---|---|
| realized funding | 官方 UI 将 `funding_rate` 定义为实际已结算费率；`funding_time` 为结算 Unix 毫秒；真实旧包包含这两列和 `instrument_name` | 可固定字段解析，事件集合完整性仍未知 |
| 目标逐笔成交 | 官方 UI 列出 `instrument_name, trade_id, side, size, price, created_time, source`；创建时间为 Unix 毫秒；`trade_id` 只声明唯一 | 字段契约已见；BTC 原 CSV 解码未验收 |
| 同毫秒首笔排序 | 未见 trade ID 的先后、连续性或文件行序等同撮合顺序的官方承诺 | UNKNOWN；不能自行按 ID/行号确定首笔 |
| 精确结算 mark | funding CSV 没有 mark；交易 price 是成交价；所查下载表单未提供 mark 类型入口 | BLOCKED；未找到符合冻结规则的官方文件 |
| 全部 mark 事件路径 | K 线是 OHLC 聚合，`confirm=1` 只表明单根 K 线结束；不能还原每个 mark 事件 | BLOCKED |
| 完整覆盖 | 导出界面有日期、合约、大小、导出时间、文件数/文件名；旧 ZIP 仅一个 CSV，无应有事件清单/缺段表/序列范围清单 | 日期覆盖和文件校验可做，事件无遗漏不能证明 |

字段及入口均来自上述[官方历史数据页面](https://www.okx.com/historical-data)实际弹窗。本次只检查这些页面和列明的帮助文档；“未找到”不等于断言 OKX 在任何渠道都没有 mark 数据。账户仓位快照、收费源及行情 API 均未使用。

[官方资金费机制](https://www.okx.com/en-sg/help/perps-funding-fee-mechanism)给出的 USDT 合约资金费用依赖 mark；默认 8 小时间隔可能调整为 1/2/4 小时，实际 assessment 可持续到结算分钟内。因此不能以固定 8h 日历替代完整结算事件证据，也不能由名义 `funding_time` 单独推出真实 assessment 的精确 mark 采样时点。[mark 与 last price 说明](https://www.okx.com/help/ii-mark-price-and-last-price)也将二者分开；邻近成交、K 线收盘、插值或自制价格都不满足当前冻结要求。

## 实际样本与下载边界

在隔离 worktree 的 `.local/adapter-audit` 复制并重新解码先前已正式取得的 12,419 字节 funding ZIP；没有重新下载市场数据。SHA-256 为 `34a7e077c89ade3d60e5afe26e615bcf2df10fdfab04930b62d185810e8f698c`。ZIP CRC 通过，唯一 CSV 82,188 字节、2,103 行、482 个合约，合约与结算时间联合键重复数 0；全部记录落在 `[2026-09-20T16:00Z,2026-09-21T16:00Z)`。仅复核格式、身份和分区，没有公开原始费率行。

BTC 2026/09/21 导出详情显示单个 `BTC-USDT-SWAP-trades-2026-09-21.zip`、27.55 MB。超过本次 10 MB 上限，未下载。较早日期的 UI 选择尝试没有形成可核实的旧导出，故本轮不声称完成目标 tick 解码，也不声称旧小包不存在。另下载 5 个公开帮助/入口 HTML 共 388,890 字节，全部只留隔离目录；URL、观察时点及哈希见相邻 JSON。

[官方历史数据条款](https://www.okx.com/help/historicaldata-terms-and-conditions)不保证完整或准确，并将下载使用限定于个人用途。此条款本身不是某一文件缺行的证据；它也不能当作完整性承诺。公开成果仅本审计的自撰分析、schema、摘要与哈希，不公开 ZIP、CSV、HTML、账户信息或下载凭据。

## 可落地的 normalizer / coverage validator 契约

1. **归一化**：原字节先封存 hash 与来源/取得时间；锁定 header 版本。资金费以 Decimal 保存，时间以整数毫秒转换 UTC，保留 `instrument_name` 精确映射及原始字符串。键 `(instrument_name,funding_time)` 相同且值相同可记录去重；相同键不同值必须冲突阻塞，不能覆盖。目标不匹配、非法数字或未知 schema 直接拒收。
2. **成交**：保留 `trade_id` 字符串、毫秒、方向、价格、数量、source、原文件 hash 和行号。官方数量字段目前只说明交易数量，衍生品单位须另有权威绑定，不能把它无条件当 BTC。相同毫秒可用稳定序列化排序保证可复现，必须同时保留 `semantic_order=UNKNOWN`；序列化顺序不等于交易顺序。当前计划的首笔若落入顺序未证实的并列事件，不能任选一个。trade ID 不连续也不能直接认定缺交易，因为无连续性契约。
3. **区间**：按已声明 UTC+8 生成分区，内部统一使用半开区间 `[local midnight,next midnight)`；这是 validator 的边界约定，UI 文案精度只到分钟。未来持仓窗口至少需要本地日期 2026-09-23、2026-09-24；两日发布声明不能作为文件已发布的事实。保存每个分区的文件名、大小、hash、实际取到时间，窗口结束前或文件未到时保持 WAITING/MISSING_DATA。
4. **覆盖分层**：分别输出传输完整性、schema/身份、声明分区并集、源事件完整性、事件排序与精确 mark 对接五层状态。ZIP CRC/本地 SHA 只证明字节自洽；时间最小最大值、无重复、分区连贯不能证明未漏事件。安静时段不能直接当缺段或零交易。没有源 manifest/应有序列与缺段证据时，事件完整性必须 UNKNOWN。
5. **结算与 mark**：事件清单须配合可核验的结算间隔变更记录或明确源覆盖契约。每个持仓内结算要有确切 mark 的身份、时点、语义和来源关联；全 mark 事件路径也需明确覆盖。缺任一项维持 MISSING_DATA/UNKNOWN，不能用 0、最近价或图表值补齐。文件导出无已暴露的事件分页 cursor；UI 导出历史列表不是数据分页、分片清单或终止证明。

这些是基于已见字段的实现建议，**本轮未实现生产 adapter，也未验收完整 replay/evaluator**。足以开展固定 funding parser 的隔离测试；当前来源不足以承诺将原两份计划自动转成完整经济结果。
