本次新增维护代码的独立结论是 **`PASS_SCOPED_MAINTENANCE`**，仅限固定条件内核、主机时区观察与 F09 快照时点文案，绑定下述文件及组合源码哈希。固定计算内核可对给定标准化观察按两份原方案做可重复的条件算术；它没有证明资料真实或完整，也未完成正式每日经济复核闭环。`FORWARD_EVALUATOR_AUDIT.md` 记录的是本次维护开始前的生产能力审计；本维护解决其中一部分固定计算缺口，不能把整个审计改写成“前向评价已完成”。

本次在隔离维护工作树读代码并执行合成测试，仅向本审计目录写报告和临时探针文件。没有修改原计划/正式 review、没有新造真实行情、没有生产 store 写入、没有运行真实 native task、没有变更原生任务配置，也没有发布。

## 已独立复验的范围

- 原 plan canonical SHA 白名单、方向/数量/窗口/信号与全部 12 个费用情景绑定；修改原规则拒绝。
- 两方向的价格损益、正负资金费、双边费用和单次滑点；每一情景最终权益与初始名义本金加条件净额一致。
- 首笔同时间顺序歧义、分钟终点严格排除、退出时点资金费排除、缺 entry/exit/精确 funding mark 的未知处理、重复事件和迟到历史证据纠错边界。
- 完整前缀与分日接续结果一致；删除/修改任何既有事件或向旧区间补事件均要求显式 correction；已算持仓不因每日截止重置。
- 信息截止与市场事件截止分开；后来实际取得历史观察只能进入后来信息截止。旧正式 review 状态迁移仍未实现，代码不把其当已有 kernel state。
- 外部 Decimal precision/rounding 不改变输出；计算固定 50 位有效精度、ROUND_HALF_EVEN。
- `complete/verified/provenance_verified/coverage` 等 caller 字段不能升 `FINAL` 或 `NOT_TRIGGERED`；正式实际 metrics 保持 null，来源覆盖固定未验证，并逐项列出当前实现缺口。
- helper 只在 `.local/review-computation/` 建立新报告；独立验证已有文件、目录穿越、绝对路径、父目录或文件 symlink 均不覆盖或逃逸。没有正式 review 提交接口。
- 主机时区来自真实 OS localtime TZif；忽略进程 `TZ`，只观察当前偏移/可核对名称。未知/offset-only/名称与偏移矛盾均保留未知；来源时区只是安装历史声明，原生任务时区、下一触发和调度影响仍未知。

工程测试重新运行 `test_funding_forward.py` 的 26 项和 `test_native_receipts_timezone.py` 的 7 项，均通过。另有不导入作者测试工厂的 21 组独立内核/输出安全检查和 11 组独立时区检查，均通过。后者包含只读实际主机 TZif 观察；没有读取真实 native task 配置文件或运行 `native_receipts.main()`。

随后只读对比 `web/src/App.tsx`、`web/src/styles.css`、`tests/browser/observer.spec.ts` 的维护差异。页面新增明确文案：“截至时间仅表示记录快照时点；发布任务当前运行状态未知。最新快照超过 36 小时显示陈旧。”现有过期判断确为最新快照年龄严格大于 36 小时；本维护没有从一次静态 HTTP 成功推断后台发布任务活跃。390px 样式仅调整文案内边距与字号。独立重新执行 Chromium/WebKit 的 F09、时钟跳变、390px 抽屉三项共 6 项，全部通过；刷新同一旧快照不续期。该测试证明静态数据老化/运行状态文案，不证明整机关闭后的实际行为或原生发布器自然运行。

## 发现与修复确认

| 级别 | 原复现 | 当前处理与复验 |
|---|---|---|
| P2 | short entry100、同刻 mark110/funding mark105 时，zero 情景 net=-.0395，轨迹末值减本金却为-.0895。 | 同一精确 settlement 时间的矛盾 mark 拒绝；同价允许，open/closed 各情景末值与净额一致。 |
| P2 | 同刻 trade 的 sequence 分别为 1 与 null，排序抛 TypeError，未到 PATH_AMBIGUOUS。 | null 作为缺序处理；独立复验输出 PATH_AMBIGUOUS，无条件情景结果。 |
| P2 | 全局 Decimal prec=6 与默认精度对完全相同输入产生不同资金费与净额。 | 独立 Context 固定精度/舍入，外部 prec=6/ROUND_UP 下全报告 canonical bytes 相等。 |
| P2 | helper 接受任意 output 路径并原子覆盖，可误覆盖输入、旧报告或研究原件。 | 限定 scratch 下新相对路径并 exclusive create；独立路径与原字节保留检查通过。 |

本次受限维护范围内没有未解决的已复现 P1/P2。完整经济评价范围仍有下列真实阻断，不能因内核测试通过撤销。

## 仍未完成的验收

1. **当前实现缺口**：许可官方原文件的固定解码、source byte/行定位复算、可信覆盖/分页终止/交易顺序验证、独立来源完整性回执。输入 source hash 目前只验证字符串格式，不能证明来源、真实取得时间或事件无遗漏；因此条件结果不可晋升为正式经济结果。
2. **当前实现缺口**：从两条原生效前 review 到新 ledger 的版本化状态迁移、review/feedback bundle 构建与受控提交、正式 source identity 解析。原计划尚未解析的方法 refs 仍保持原历史事实，不能补登记新方法后宣称它在原封存时已存在。
3. **未来路径与必要输入**：入场/退出窗口的真实首笔、持有期所有结算及精确 mark、完整可核查权益路径。窗口到达不意味着资料齐全；实际用户成本仍未知，12 情景不能变成实际收益或放宽原 FINAL 条件。
4. **独立自然验收**：原生触发身份、真实槽位、跨日长期运行、原生调度时区/下一触发实际观察。本次只读 host 观察或合成算法不证明这些事项。
5. **经济效果**：当前未作真实前向评分或资金费预测有效性结论；两个方向也不能加成账户收益。

此结论允许合入受限内核、主机观察和 F09 文案维护；不授权任何交易、原方案重写、回填自然触发、将合成资料当生产后备或将覆盖字段调绿。真实闭环仍须按照 `INPUT_CONTRACT_RECOMMENDATION.md` 完成相应能力并独立复验。

## 源码绑定

| 文件 | SHA-256 |
|---|---|
| `researchlib/funding_forward.py` | `79f9aa7dc3c2e1dc47b1cd2eb307cf3eaf685874f722dab21710601bdfefeb66` |
| `scripts/evaluate_funding.py` | `ca954e78216509917c7055532e40d2f5acb3b7c32a3d77dc73e2cf52890c817d` |
| `docs/FUNDING_FORWARD_KERNEL.md` | `a58a2a493b790d6bcf74b74c10137ecb74209993baa3af2571dd9d9b458b99fd` |
| `tests/test_funding_forward.py` | `699d7b6625cb22143e83d193b5ee6d44cff469bd4827ffb43c5ab9860ac87b44` |
| `scripts/native_receipts.py` | `7c0e6adc0e0a351b097dcab547728fbd190b83bcb7d49ff709dbfb6d2fb59c4d` |
| `tests/test_native_receipts_timezone.py` | `f97a8064ab80b6be3a3e5f5994591bcd2f7dd91f82063c9d68a42b70f33ca329` |

机器回执为 `kernel-independent-receipt.json` 与 `timezone-independent-receipt.json`；复验程序为同目录 `check_kernel_independent.py` 与 `check_timezone_independent.py`。它们明确标注 synthetic/只读观察，不能导入生产记录或公开业务成果计数。

维护组合源码由隔离工作树 `python3 scripts/publish.py --source-hash` 实际复算，两次结果一致：`2add8c42b4ab1ffc541e40870c0b0f1d14fd4b871da4dd89c1af15af392d6c0c`。该组合身份及新增前端三个文件哈希详见 `maintenance-source-receipt.json`；后续源码如变化须重新绑定。本审查结束时未执行部署或声称线上 readback 完成。
