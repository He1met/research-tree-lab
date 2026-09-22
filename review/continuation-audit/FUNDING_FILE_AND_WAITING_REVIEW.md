独立结论：**PASS_SCOPED_FUNDING_FILE_AND_WAITING_REVIEW_OUTBOX**。批准范围仅为单个已提供资金费文件的严格离线解码，以及两份固定旧计划从原生效前状态到版本化等待状态的正式 bundle 准备。组合源码 hash 为 `0b6047c816779f4d2d48cc9435768e5cde7a34a55af9e7ecc7b52298f41841ae`，通过隔离工作树 `python3 scripts/publish.py --source-hash` 两次实算一致。

这不是完整经济评价器、来源完整性验收或自然复核证据。生产 wrapper 只写隔离 outbox，不提交 store；本审查甚至没有写生产 outbox，只在临时工程库测试提交/接续，并对生产原件做只读内存准备。原方案及其原方法引用没有修改，未把新实现倒签到原封存时点。

## 单文件解析

`okx_funding_file.py` 对输入真实 bytes 校验 hash/大小、受限 ZIP 结构及 CRC、精确 CSV schema、全文件每行数值/整数毫秒/UTC+8 半开分区。非目标行也验证；同键同 Decimal 值保留全部原始行再去重，冲突拒绝。URL 和取得时间只是受到格式/时序约束的声明，不自动证明实际获取。

独立直接读旧原包 `34a7e077…10e8f698c`，重新用标准 CSV 解码逐一比较 BTC 费率：2,103 行、3 个 BTC 事件、2,100 条排除，全部相符。没有下载新行情、没有输出原费率行。`coverage=UNKNOWN`、`settlement_mark=null`、`data_complete=false` 和 LOCAL_ONLY 边界保持；目标未见不会变成零资金费。另复跑 27 项作者测试，以及 7 组独立攻击检查，全部通过。

解析器仅接纳单文件；跨文件来源合并、完整事件集合、真实同毫秒成交顺序、精确 settlement mark、完整 mark 路径均未由其实现或证明。

## 等待状态与正式 outbox

固定批次从一次完整 Store 读取冻结所有当时已 available 且真实 committed 的正式 plan。两个原计划使用精确 canonical SHA；其他计划逐项 RULES_INCOMPLETE，未知/不合法旧状态逐项 TECHNICAL_FAILURE，不能跳过后误称经济评价齐全。批次 complete 只指逐项处置齐全，经济可评价数与 FINAL 数均明确为 0。

旧桥接只接受实际生产中已审核的两条 review ID/canonical hash，并再次检查其空状态；仅复制旧 method 名称和零库存不能伪造桥接。新等待状态在生效后 inventory 为 null，收益/费用/次数全为 null；后续接续保留 previous_review_ref 和 opening_state_hash，不把缺事件当零交易、不重置已有持仓。超过原终点仍为 WAITING_DATA。未知 kernel/非空旧状态必须显式另行迁移，当前助手不自动处理。

新方法记录真实准备时间，信息 cutoff 无 CLI 回填参数。方法 hash 包括递归本地 Python import 闭包（含 `__init__` 的间接导入）及 Python runtime；前次新方法必须解析到同一已提交 review bundle 的 METHOD.json，核对实际原件、完整身份和 availability。批次 outbox 内另有按 batch ID 唯一的完整准备原件，原子、只增不覆盖；换输出文件名、并发或导出中断均不能重抽同批。符号链接/目录穿越拒绝，未知本机自然身份不能通过自由参数填入。

复跑 28 项作者测试和 8 组独立临时库检查，全部通过。真实生产只读检查确认两条原 review hash 与受控 Store、已跟踪 bootstrap bundle 相同；内存准备时两计划均 NOT_YET_EFFECTIVE、所有指标 null。检查前后所读 store/data 的 161 个文件 hash 集相同。该次输入快照之后其他任务产生的记录不在本回执范围内。

## 已修复并独立复验的问题

| 级别 | 原复现 | 当前结果 |
|---|---|---|
| P2 | 同一未提交 batch ID 在 20:00/20:01 换 output 名能生成不同 frozen_at 的两份准备原件。 | 独立 batch 身份文件原子建立；第二次明确拒绝，原件不变。 |
| P2 | 方法 hash 只含 6 文件，漏 package initializer 及间接导入。 | 实际本地静态 import 闭包 11 文件与 runtime 入 hash；公开附件仍只含安全自有源码，其他依赖以 hash 绑定。 |
| P2 | 前次 review_method_ref 悬空，但 evaluator 字符串/状态照抄时可被接续。 | 必须解析已提交方法证据；悬空方法逐项 TECHNICAL_FAILURE。legacy 还必须匹配两份原 review 全字节哈希。 |

当前受限范围无未解决的已复现 P1/P2。公开记录与方法附件扫描通过，无私人路径或原行情行；审计目录的既有 20 个文本材料也已扫描通过。原 raw ZIP/归一化输出保留本地，不纳入公开附件。

仍待完成：官方来源与真实取得回执的可信绑定、完整路径/顺序/精确 mark 的独立验证、接受市场事件的正式经济 review 与其状态迁移、真实费用范围，以及自然日复核身份和经济结果。其他任务的自然研究资料/记录由根代理单独审查，本报告不替其出具自然运行结论。

组合机器回执见 `funding-review-source-receipt.json`，细项见 `funding-file-independent-receipt.json`、`waiting-review-independent-receipt.json` 与 `waiting-production-memory-receipt.json`。
