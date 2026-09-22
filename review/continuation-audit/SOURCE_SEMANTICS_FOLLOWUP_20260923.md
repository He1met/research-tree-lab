# OKX 来源语义追加核查（2026-09-23）

结论：**PARTITION_DOCUMENTATION_CORROBORATED / FORMAL_SOURCE_GAPS_REMAIN**。官方技术文档补充佐证了交易、资金费等下载的 UTC+8 日期规则；仍未证明历史 CSV 的撮合顺序、事件全集、精确 funding 结算 mark 或完整源 mark 路径。本次没有调用行情 API、访问账户、取得新行情、运行经济评价或变更已安装实现。

## 观察归属与范围

- 本报告作者先读 [原来源审计](source-adapter-audit.md)、[独立来源复审](source-capability-independent.md)及[后续实施边界](FORMAL_REVIEW_NEXT_BOUNDARY.md)，再用 web 工具核查三个官方文档入口：API 主文档、更新日志、funding FAQ。期间记录的工具时钟为 `2026-09-22T21:43:34Z`。API 主文档读取因超过工具约 4 MB 限制失败，锚点重试也未成功；作者未因此把主文档记作已读。
- **root 的独立浏览器观察**：root 随后通过 Chrome DOM 成功读取同一 API 主文档的下列四个锚点，并在本轮协作中报告字段及说明。以下该文档事实归属 root 的直接观察，作者据其回传写入；不是作者再次浏览、原始截图归档或独立第二次字段复验。root 未提供秒级观察时点，本文不补造。
- 全程仍是最多三个官方文档入口；页面中描述某接口或字段，不表示本次调用过接口、下载过输出或验证过实际准时率。旧报告与原始回执保留各自历史时点，不改写。

## 新增可核语义及其限度

| 问题 | 已观察到的官方说明 | 仍未证明 |
|---|---|---|
| 下载分区与可得性（root） | 历史下载 modules 1/2/3/11 将时间戳按 UTC+8 转日期；通常 T+2；补录进行中，可用性依模块、合约及时间而异。日期首尾包含、结果逆时间，超过限额取靠 end 的数据 | 日期并集不是事件全集；T+2 不是特定文件已发布或准时取得的证据；受限返回不等于全范围已取完 |
| 交易身份与顺序（root） | module 1 称逐笔数据；trades history 的 `tradeId` 是交易 ID，可请求较早/较新分页 | 未将分页或 ID 与下载 CSV 的撮合先后、同毫秒首笔、连续编号或无遗漏保证绑定 |
| funding 历史（root） | 区分预测 `fundingRate` 和实际 `realizedRate`，有 `fundingTime`、`method` 等；周期可变，字段中没有 mark | 名义结算时间不能单独定位实际采用的 mark；不能固定八小时补造事件 |
| mark 历史（root） | 历史 K 线为 `[ts,o,h,l,c,confirm]`；`ts` 是 bar 起点，最小列示周期 1m，`confirm` 表示 bar 完成 | 完成 bar 不能还原精确结算 tick，也不证明冻结计划的 `all source mark events` 全路径 |

上述四项的精确官方入口依次为：[历史市场下载](https://www.okx.com/docs-v5/en/#public-data-rest-api-get-historical-market-data)、[历史成交](https://www.okx.com/docs-v5/en/#order-book-trading-market-data-get-trades-history)、[历史资金费率](https://www.okx.com/docs-v5/en/#public-data-rest-api-get-funding-rate-history)、[历史 mark K 线](https://www.okx.com/docs-v5/en/#public-data-rest-api-get-mark-price-candlesticks-history)。本次文档复读补充了旧独立审计仅以 K 线 FAQ 佐证日期规则的范围，**不是重新验收旧交易/资金费弹窗截图**。

作者直接读取的[官方更新日志](https://www.okx.com/docs-v5/log_en/)还有以下限定：2025-07-08 的 WS `seqId` 为消息序号，同一时刻不同更新可能共用；2025-11-26 说明 trades channel 按 taker、成交价、`source` 聚合；2026-07-28 将 GET trades 的 `source=1` 说明从 ELP 更名为 RPI。root 读取的 trades history 页面仍写 ELP。应保留该范围/文案差异，不能猜测下载 CSV 的映射，更不能据此赋予 `source` 排序含义。

作者直接读取的[官方 funding FAQ](https://www.okx.com/en-sg/help/funding-fees-for-perpetual-contracts-faq)说明实际结算在一分钟内完成、单合约为毫秒级；未给出采用哪个 mark 事件的采样规则或可据以复原的公开历史输出。更新日志另记录账户账单 `px` 在 funding 收支类型 173/174 下表示 mark；这是账户账单字段，不能替代本项目允许的公开市场来源。本次未访问账户，也不建议以账户读取绕过来源边界。

## 对后续实施的影响

可以按官方声明检查下载日期参数、声明分区及返回范围；必须另存实际取得事实，不把日期规则提升为齐全证明。已有 parser 的真实解码能力不因本报告失效，但 `sequence=null`、`coverage=UNKNOWN`、`settlement_mark=null` 仍应保留。

下一步只有取得**明确绑定历史 CSV 的顺序/覆盖语义，以及公开历史 mark 的采样与范围依据**，才有理由审查相应正式通过分支。现有 K 线、预测费率、相邻成交、ID/行序或 caller 自填 `verified` 均不能补足这些证据。本轮未找到解除原两份冻结计划上述缺口的新证明；也不将有限入口的未发现外推成所有官方渠道均不存在。本文不新增 FINAL、NOT_TRIGGERED、readiness 或经济验收结论。
