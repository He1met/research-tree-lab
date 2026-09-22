本轮独立复核覆盖已提交的全部 2 个正式方案；截至固定批次时点，两者均未生效，因此没有模拟成交、收益或自然复核。真实资金费原件和费用情景经独立 Decimal 复算，46 项检查通过。审查发现的缺陷已修复；19 个执行标志对抗场景、9 项机制去重组合检查、8 个模拟公开回读场景及 55 项 Python 工程测试通过。网页发布、原生自然接续、真实跨日路径和经济效果仍须各自取证，不能合并成“整套完成”。

# 独立范围与证据身份

工作依据为 `planning/current/PROJECT_SPEC.md`、`RESEARCH_PROGRAM.md`、`AUTOMATIONS.md`、`docs/ACCEPTANCE.md` 与项目 `daily-review` Skill 的完整任务正文。原件从安装配置所指稳定 store/data 读取，没有修改研究原件、共享方法实现、用户浏览器、Git 或原生任务。

固定批次：`batch-manual-safe-review-20260923-v1`，截止 `2026-09-22T18:08:05.186805Z`。当时共 21 条已提交记录，全部 2 个 plan 版本均纳入；后续提交不倒灌到这个清单。

| 原方案 | canonical SHA-256 | 本次处置 |
|---|---|---|
| `p-btc-funding-long-control-20260923@1` | `a8dd9a25bd4a5353bc8ed479ec41056bcf07704fccb285f2d014a9615358d02c` | `NOT_YET_EFFECTIVE` |
| `p-btc-funding-short-20260923@1` | `65ff62c3603d257b82b3274785fd1bfe2c5a784d215786be4775fe7fa076bce4` | `NOT_YET_EFFECTIVE` |

交接 outbox 为 `review/bootstrap-review/review_bundle.json`，SHA-256 为 `16d84a5f3cea83cccd4ab304de475e56a8cb86a2a6b4c4d369fb2ae8cb506acb`，含 1 个 batch、2 个 review、2 个 feedback。独立审查者只准备并验证 outbox，由主执行者通过受控入口提交；正式提交身份以 store manifest 为准。

方法 `independent-forward-status-v1` 绑定 `REVIEW_METHOD.md` 的精确 SHA-256；本方法只判断固定清单、规则、时点与等待状态。它不是已实现并验证的未来价格路径收益评价器。batch complete 表示 2/2 均有处置，经济可评价数及最终数都为 0。

# 真实算术与规则核对

- 独立读取官方下载 ZIP 的真实字节，核对 CRC、12,419 字节和 SHA-256；CSV 为 2,103 行、482 个合约，4 个目标各 3 行。稳定副本清单所列 8 个文件的大小/哈希一致。
- 使用独立 CSV/Decimal 路径复算费率汇总、符号、时间间隔、目标 UTC 窗口覆盖以及全部 48 个费用情景，46 项断言通过。原研究的 UTC 日不完整结论保留；没有改窗口、补零或年化。
- 两个计划封存早于生效，数量均为声明面值口径下的 0.01 BTC；方向分别为 +1/-1。封存信号在予定入场时为 40 小时 5 分钟前，符合原计划 ≤72 小时规则，但不是入场时新获取的当前费率。
- 入场为 `2026-09-23T00:05:00Z` 后 1 分钟内首个合法目标成交，退出为次日同一窗口；终点评价 `2026-09-24T00:06:00Z`。缺成交、实际结算标记或资金费时保留未解决状态；日终不强制退出或重置。
- 费用情景与实际费用分开。实际交易费、滑点及未来资金费路径未齐，真实净收益、持有期、完整权益回撤和基线结果全部为 null。方向相反并不匹配市场 beta，不能相加为账户收益。
- 本地时间和文件回执可以核对内部顺序，不能充当第三方公开事前预测证明；两原计划 `public_visibility_ref=null` 的边界保持不变。

复算脚本及回执：`review/bootstrap-review/independent_audit.py`、`independent_arithmetic.json`。本次为 `OFFICIAL_APP_SUBAGENT_MANUAL_SAFE_TRIAL`，`native_task_ref=null`、`natural_trigger=false`。

独立回读的[股票永续说明](https://www.okx.com/help/stock-perpetuals)支持目标市场 24/7、参考会话独立、复合指数与汇率角色，以及利率项为零不等于实际资金费总为零的边界；[资金费机制](https://www.okx.com/en-sg/help/perps-funding-fee-mechanism)支持按持仓数量、面值、乘数和结算标记价计算，以及实际结算频率不能永久写死。动态合约规格表没有在文本回读中返回选中合约字段；本审查不将研究者已有 UI 观察升级为重新独立核验过的最新 tick/最小量。来源回读元数据见 `official_source_readback.json`。

# 发现、修复与独立复验

| 级别 | 初始缺陷和影响 | 修复及复验 |
|---|---|---|
| P1 | `readiness.assess` 可让空规则/INCOMPLETE_DATA 计划、孤立来源、无具体检查范围的证据和缺失 policy 返回执行齐备。 | 固定 policy；重验完整原规则；解析计划方法、目标数据及产品；逐项检查范围与来源链；源字节、时点及循环检查。原复现已降为 UNKNOWN，19 个独立对抗场景全部拒绝错误升格或按期过期。 |
| P1 | `publish.source_hash` 未包含 `web/index.html` 和 `web/public`，实际构建输入变化可绕过审批；shell 缓存也漏静态资源。 | 两个哈希均纳入入口、静态资源和 notices；隔离副本修改这两项均改变审批哈希。发布源码/remote 闸门测试通过。 |
| P2 | `freeze_batch` 的旧 review 只按 available_at 过滤；迟提交而早创建的 FINAL 会进入更早批次并被复用。 | review 同样过滤真实 committed_at；原隔离 Store 复现现在 previous_review_ref=null、REVIEW_REQUIRED。当前真实批次原先没有旧 review，所以未受影响。 |
| P2 | 新增公开回读工具仅比较本地/远端 manifest，未独立校验本地内容寻址身份；只识别 root div 也不能证明当前静态壳。 | HTTP 前执行完整本地 verify_snapshot；严格核对快照路径和时点，逐字节比较 HTML、JS/CSS 及全部对象。8 个完全模拟 HTTP 场景均通过；伪本地身份在 0 次网络请求前被拒绝。 |
| A03 补充 | 自由文本哈希唯一曾被自动视为独立机制，不能证明新机制。 | 现比较结构化规则/方法、参数变体和数据内容身份；改名、参数微调、跨产品、新样本、多来源在单个组合输入中通过 9 项检查。科学独立数保持 null；未知文本不自动认证。 |

原失败记录没有删除：`readiness-repro.json`、`batch-cutoff-repro.json`；修复后为 `readiness-recheck.json`、`readiness-matrix.json`、`publisher-hash-recheck.json`、`batch-cutoff-recheck.json`。追加复验见 `novelty-matrix.json` 和 `publication-readback-matrix.json`。`engineering-tests-final.txt` 保存本次 55 项 Python 测试通过的输出，包含存储不可变性/认领并发/中断/纠错/历史时点/恢复、事件账本、公开扫描、发布闸门和机制去重。

真实追加的独立快照回读见 `actual-append-recheck.json`：21→26 个公开对象，新增 batch/review/feedback 共 5 条，3 轮及其代际保持不变。追加时前端源码未变的原始测量由 `docs/real-append-c05.json` 保存；后续 UI 修复作为独立代码变更验收，不以当前源码哈希覆盖早先证据。

前端专门代理的最终回执有 54 项 Chromium/WebKit 通过、0 失败/跳过/flaky。本独立审查只核对该回执与当前前端/锁文件哈希吻合，没有声称亲自重跑浏览器。组合源码冻结绑定及完整文件哈希见 `review/bootstrap-review/reviewed_source_receipt.json`；后续源代码变化必须重新绑定，不能沿用本次结论。

程序控制与 OS 权限仍分开：同用户 full-access 进程能够绕过受控入口直接写文件；校验可以检测原件被改，不能把它宣称为按角色只读挂载。发布脚本核对当前授权 remote，不代表 GitHub 登录本身仅获本仓权限。前端可保留或降级后端判断，不能替代来源链核验；HTML/静态壳的后续变更仍需新独立检查。

# 尚未由本次证据满足的验收

| 范围 | 准确状态 / 下一步 |
|---|---|
| B03 全量日复核清单 | 本次真实 manual 为 2/2；自然每日批次未发生。 |
| B04/B05/B07 跨日与最终经济路径 | 工程事件账本已测试，真实方案尚未生效，后续行情/结算标记/费用缺口待数据；不能把 pre-effective review 当跨日实绩。 |
| A06/A08/F07 自然反馈闭环 | 两个不同自然研究时点、一轮自然每日复核及真实反馈后继采用均须未来原生运行证据，`WAITING_NATURAL_OUTCOME`。本次反馈已正式准备，尚无本审查核实的后继采用。 |
| B01/D01-D07 当前执行条件 | 本轮无当前可交易标志。规则数据缺项维持 UNKNOWN/INCOMPLETE_DATA，最新动态合约规格和目标行情须单独核验。 |
| C01-C12 浏览器 | 本审查没有控制用户浏览器。React Flow 真组件/规模/移动与键盘/过期等由专门浏览器验收记录承担，不能用本 Python 测试替代。 |
| E09 公开发布 | 本审查未执行 Git/Pages；必须以真实部署 URL 和同一 snapshot 回读为准，不能把 JSON 或构建成功当上线。 |
| E10 恢复 | 主执行者已报告允许公开派生研究的新目录恢复；本审查确认公开边界，未把它称作上游原始文件完整远端备份。受限原件仍 LOCAL_ONLY。 |
| F01/F04/F05/F07 原生任务 | 手动子代理运行不等于原生 Run now；真实 ID、权限、当前频率、下一触发和自然身份应由官方管理回读及后续运行记录承担。 |
| 经济有效性 | 目前只支持真实数据/机制边界与条件算术；没有前向净收益、统计增量、盈利策略或账户适配结论。 |

唯一下一动作：主执行者把已提交复核与最新修复生成同一公开快照，完成真实发布/原生启用回读；后续原生复核仅在窗口与合法数据实际到来时按旧计划接续，并保存独立评价器和输入版本，不要求用户重复发送“继续”。
