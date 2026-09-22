# 正式有事件评价：下一实施边界

状态：`DESIGN_ONLY_DURING_FIRST_COMBINED_CANDIDATE_REVIEW`。本文写于首次组合候选独立审查阶段；组合尚未安装，本文不构成实现、安装、自然运行或经济验收。没有新抓取数据、执行计划、写入生产 Store 或改变 native。第四批及组合冻结文件不变，原 [FORWARD_EVALUATOR_AUDIT.md](FORWARD_EVALUATOR_AUDIT.md) 保留其历史时点。

组合候选的完整 16 文件方法身份为 `7dbdd186fd04ddca07dc3bfa933f9a0fae1ce66e1f1d91447e0bbeff5332d3ce`，conditional 模块 SHA 为 `2508392c524c19b4260f6d120d4f17f80bcd0d327b8daa483036130d12b56fd6`。下文 conditional 源码行号以此候选为准，不声称 main 当时已经装有该模块。候选清单为根相对路径 `tests/receipts/first-combined-candidate-freeze.json`。

## 结论与验收对象

下一项有价值的工程工作是**逐指标的证据需求、可计算性及受限情景结果输出**，而不是再加一个固定 `data_complete=false` 的外层状态器。当前没有已审核的真实官方格式可支持“源事件全集、同毫秒撮合顺序、精确结算 mark、完整 mark 事件路径”这些正式通过分支。不能自行设计一份由 caller 勾选 `verified` 的证明协议来填补缺口。

| 验收 | 已有工程基础 | 正式有事件评价仍缺什么 |
|---|---|---|
| B04 | 条件内核、跨日状态、完整历史前驱校验、普通前缀与更正链 | 由真实来源证实的原窗口首笔成交及后续结算/估值输入；不能把条件持仓说成已证实模拟成交 |
| B05 | 批次全集处置、信息/行情截止分离、等待/歧义/技术失败 | 逐项导出数据齐备与终态资格；到原终点仍缺资料必须保留缺项，不能由时间流逝或 Boolean 升级 |
| B07 | Decimal 会计、12 个冻结费用情景、条件库存与观测轨迹 | 全部应有结算、精确 mark、完整源轨迹及适用费用证据；实际成本未知不能填零。这两份单次持仓 BTC 计划不是网格，不覆盖全部网格验收 |

依据：[ACCEPTANCE.md 第 28/29/31 行](../../planning/current/docs/ACCEPTANCE.md#L28)、[PROJECT_SPEC.md 第 172–181 行](../../planning/current/PROJECT_SPEC.md#L172)及[RESEARCH_PROGRAM.md 第 129 行](../../planning/current/RESEARCH_PROGRAM.md#L129)。旧 FORWARD 审计第 22–25 行的“没有解释器/不能迁移”已被后续内核及条件接续候选部分解决，不能继续把整份旧发现当作未变现状；其来源、实际成本与终态边界仍成立。

## 原计划及 actual cost / FINAL 的精确边界

两原件位于 [research_bundle.json](../../research/bootstrap-v1/research_bundle.json) 的 `records[]`：

- `p-btc-funding-short-20260923@1`，canonical SHA `65ff62c3603d257b82b3274785fd1bfe2c5a784d215786be4775fe7fa076bce4`。
- `p-btc-funding-long-control-20260923@1`，canonical SHA `a8dd9a25bd4a5353bc8ed479ec41056bcf07704fccb285f2d014a9615358d02c`。

应以以下原字段区分结论，不用一个“成本未知”标签替代阅读原协议：

| 字段位置 | 原文含义与约束 |
|---|---|
| `rules.termination`，第 514/693 行 | FINAL 明确要求两笔合法成交、持仓中每次资金费结算、精确结算 mark、完整持仓/权益路径及 verified inputs；缺信息在终点后仍为 MISSING_DATA |
| `replay_missing`，第 473/652 行 | 原件仍列 `verified actual trading-cost schedule`，不能在维护中静默删除或视为已满足 |
| `evaluation_contract.actual_net`，第 445/624 行 | `null until actual cost inputs are verified; scenario values are not actual fills`：实际净收益有明确成本验证前提 |
| `cost_model`，第 352/531 行起 | actual entry/exit fee 与 actual slippage 均为 null；费用 `[0,2,5,10]` × 滑点 `[0,1,3]` 共 12 情景，全部报告；零成本是摩擦下界，不是实际值 |
| `evaluation_contract.equity/drawdown`，第 449–450/628–629 行 | 保留所有源 mark 事件的权益轨迹；观测路径回撤须说明采样限制，不是连续风险保证 |

**实际费用验证是 actual net 的明确门槛；原 termination 没有逐字单列“用户账户实际费率/实际滑点已知”作为独立 FINAL 条件。** 但它要求 verified inputs，且 `replay_missing` 明列成本表缺项，因此也不能反向推出“实际成本未知时旧计划当然可 FINAL”。当前精确 mark 和全路径已独立缺失，已经足以阻止 FINAL，无需为得到当前结论擅自解释掉成本缺项。

固定情景可作为正式登记、有方法/输入身份的**假设结果**独立呈现，actual fees/actual net 继续 null；“正式登记”不等于实际成交，也不等于原计划整体 FINAL。公开费率表可以支持其明确适用范围，不能证明用户费率等级、订单实际滑点或实际成本。项目不因该缺项接账户或下单。[旧审计第 36–40 行](FORWARD_EVALUATOR_AUDIT.md#L36)已明确这一边界。

若以后全部市场输入已证实、只剩成本层，须针对上述原字段给出可审核的终态解释；不能在代码里默认跳过。若目的改为“仅情景完成即整体终态”，应登记明确的新协议/方案版本与实际可得时点，不追认旧成绩。允许费用未知/明确情景的项目规范，也不能被解释为“所有有意义的分项计算都必须等账户数据”。

## 已存在的真实格式与仍缺的官方证明

| 能力 | 当前真实证据与程序位置 | 不足及所需额外证据 |
|---|---|---|
| funding 解码 | [funding 独立回执](funding-file-independent-receipt.json)实际核对旧 ZIP；CSV 为 `instrument_name,funding_rate,funding_time`；[okx_funding_file.py 第 245–265 行](../../researchlib/okx_funding_file.py#L245) | 可解析实际结算费率与整数毫秒，但文件没有 mark、完整事件清单或应有事件数；`settlement_mark=null`、coverage UNKNOWN |
| tick 解码 | [trade 真实独立回执](trade-file-real-safe-output-independent-receipt.json)完成 4,969,733 行扫描；CSV 为 `instrument_name,trade_id,side,price,size,created_time,source`；[okx_trade_file.py 第 374–426 行](../../researchlib/okx_trade_file.py#L374) | ID 保留身份，严格递增只限定已支持布局；`sequence=null`。文件行号、ID 大小、最早观察到的毫秒均未证明官方首笔或事件全集 |
| 原始来源与时间 | parser 核对实际 bytes/hash/size，注册 dataset 提供 acquired/available/commit；source audit 有官方网页取得记录 | URL 白名单和填写的 obtained_at 不是独立来源/时间证明。未来正式适配应将可核验取得记录与确切下载文件关联，不能只接受 source_url 字符串 |
| UTC+8 分区 | [来源审计第 9–15、43–45 行](source-adapter-audit.md#L9)及[独立来源复审](source-capability-independent.md) | 日期并集只是声明分区。官方 FAQ 的独立复核只覆盖 K 线；资金费/交易弹窗保留原作者第一手观察，不能外推成再次独立证实。发布延迟声明不证明实际文件已发布或及时取得 |
| 全集/终止证明 | 已查导出界面有文件名、大小、日期等；[来源审计第 26、45–46 行](source-adapter-audit.md#L26) | 未取得对应的官方完整性/分片终止/应有事件范围/缺段契约。CRC、无重复、时间首尾相符、分区连续、ID 连续或不连续都不能替代它 |
| 精确结算 mark 与全 mark 路径 | [来源审计第 24–30 行](source-adapter-audit.md#L24)，[独立复审](source-capability-independent.md) | 已审查官方下载来源没有满足要求的真实格式；不是断言所有官方渠道都不存在。结算名义时间不自证真实 assessment mark 的采样时点；成交价、最近价、K 线 close、插值均不是替代品 |

来源审计最初尚未解码目标 tick；上述后续独立回执补齐的是实际文件解码，未补齐顺序或全集证明。本文没有重新浏览官方网页或取得新数据，官方事实严格沿用这些带观察范围的已有证据。

正式首笔必须有原半开入场/退出窗口的完整覆盖及必要顺序依据；同毫秒并列不得按价格择优，即使价格相同也不能冒称唯一首笔。没有记录不等于没有交易。原 `rules.entry/exit.missing_data_outcome` 已要求缺资料时 MISSING_DATA，不补替代时刻；不得把缺入场行情改称 NOT_TRIGGERED。冻结信号只能在原计划的予定入场时点判断年龄，不能用后来资金费替换。

## 可执行的最小下一实施范围

在组合安装并核验身份后，另开隔离版本，仅处理这两个精确 plan hash：

1. 从原字段导出逐指标需求表，区分来源身份、bytes/schema、声明分区、源全集、顺序、结算 mark、源 mark 路径、公开费用适用范围、实际成本。每项输出所用登记 ref/hash、实际信息时点、满足或缺失原因。拒绝直接传入 events、mark、sequence 或 `verified/complete`；不提供通用“证明 JSON”上传即通过入口。
2. 只复用已审文件解码及登记引用解析，建立指标依赖关系：首笔→数量/持有状态；结算全集+对应 mark→资金费；完整源 mark 路径+现金流→情景权益与观测回撤；实际成本→实际净额。分开 requested cutoff、条件计算 cutoff、观察到的最晚事件、确有证据支持的评价范围。没有正式来源依据的维度保持 UNKNOWN，并列出具体缺项，而非只有统一硬编码 false。
3. 允许输出严格白名单的派生情景摘要，完整 12 个既定情景并列；原始事件、价格/权益数组和私有更正原因仍只留受控 private 附件。部分依赖缺失的指标为 null，不把部分和称全额；正式 actual metrics、整体 FINAL 和 readiness 不随情景可计算性升级。实际 snapshot 与 review/batch/feedback archive 都须验证无私有泄漏。
4. 未来取得真实官方格式及其适用语义后，再为该具体格式增加固定 validator、真实小样本和独立审查；不是现在发明全集/顺序证书。没有新证据就停止该通过分支，只交付上述需求、诊断及隔离工程验证。

现有 [funding_forward.py 第 81–107、118–262 行](../../researchlib/funding_forward.py#L81)已有条件首笔选择、跨日状态、费用情景和观测回撤；其中第 178 行静态 missing-capability 文案不是现时能力台账，不能据此把后来已实现的 parser/接续层再报成全部不存在。候选 [conditional_review.py 第 491–512 行](../../researchlib/conditional_review.py#L491)已把正式评价 cutoff 保留 null，与条件 cutoff/观察时点分开；下一版本应细化证据依赖，不回退为 caller 的真假标志。

完整 mark 路径还可能超出候选每计划 4 来源、20,000 事件、32,000,000 bytes 私有附件上限（同文件第 100–102 行）。须待真实格式/规模明确后另审有界流式全路径处理和可复算状态；不能截断为齐全、抽样后称完整权益轨迹，或先扩建通用大数据平台。

## 独立反例与停止条件

- 缺中间分片，但首尾时间、CRC、文件数看似合理：全集仍 UNKNOWN，正式评价游标不得推进。
- 非官方模板、自签 `verified=true`、后来提交/取得的资料倒填时点：拒绝或未知；不得进入原事前信号。
- 同毫秒改 ID/行序，或两笔同价：不能变成已证首笔；稳定序列化不产生市场顺序。
- 结算 mark 错合约、错语义、偏移毫秒，或使用成交价/close；名义结算时间相同但 assessment 关联未证：资金费依赖指标仍缺失。
- 漏一笔结算、固定八小时补造日历、缺费率/mark 填零：不得得到完整现金流。
- 开平两点相同但中间权益下探被删，或路径超过资源限额：不得沿用完整回撤/完整路径结论。
- 零成本情景冒充实际成本、只选最优情景、先调整成交价又重复扣同一滑点、把多空结果相加为账户收益：拒绝对应声明。
- 跨日丢前缀、重入/重计、迟到换来源不更正、跳过坏 latest、恢复时新增公开 PRIVATE 许可：完整继承已审链/恢复/公开导出攻击测试。

没有真实官方完整性/顺序/mark 证据时，合成正例只能验工程契约，不能让生产 validator 输出“官方已证”。原窗口发生、实际发布/取得、自然任务运行和经济效果是另外的真实证据，代码测试不能代替。

## 首次安装之后的升级约束

这次不兼容第四批 `a1f6f384…` conditional 的理由仅是生产盘点确认其未安装、无正式 conditional review/outbox。**组合 `7dbdd186…` 一旦真实使用，此理由失效。** 下一源码升级必须重新盘点生产实际身份与在途 outbox，核对真实完整 SOURCE/METHOD/private、所有祖先、更正链及新旧语义，提供精确前驱兼容或明确版本迁移；不能换方法 hash 后永久阻断已有链，也不能归零重开。不得执行 record 附件代码、只认 version 名或把新方法倒签。当前只是记录这一未来升级条件，不提前新增未经需要和审查的兼容白名单。
