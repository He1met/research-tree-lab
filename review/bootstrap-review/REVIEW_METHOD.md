# Independent forward status review v1

方法身份：`independent-forward-status-v1`。本方法只认定合法生效、完整清单、冻结规则、输入完整性与等待状态；不作为价格路径回放、收益评价或原生自然运行评价器。

批次开始从稳定 store 冻结所有当时已经完整提交的真实 plan 版本，保存原件 canonical SHA-256、已有 review 链、批次时点；不是只取主选或赢家。

1. 每项只读原方案，检查 seal/effective/entry-end/evaluation-end 时间顺序、版本/哈希、quantity 单位、signal、entry、exit、reentry、cost、terminal 和跨日约定；本地封存与公开第三方证明分开。
2. 如果批次 cutoff 早于 effective_from，结果必须为 NOT_YET_EFFECTIVE；路径、费用、毛净收益、持有期、回撤和基线结果为 null。模拟状态仅表示尚未合法开始，不创造零收益交易。
3. 到生效后但未有覆盖所需的实际输入，不得用这份 pre-effective 方法评价经济结果；生成 WAITING_DATA 新 review，保存未解决状态。后续正式回放需冻结独立实现版本、完整目标成交/标记/资金费输入和原成本情景。不能追认本次旧 review。
4. 把既有历史研究输入作为已曝光开发信息，不作为随后验证路径。没有动态 LLM 决策规则，不在事后补问。没有前一 review 时 opening_state_hash=null；有前一 review 时严格绑定状态哈希与原 cursor，不重置持仓。
5. 完整覆盖与可评价结果分开。batch complete 只意味着固定清单逐项都有处置，并不意味着方案最终、输入完整或通过经济验收。
6. 事实、解释、可检验后继问题分开保存；同一窗口的方向相反对照不是独立样本，不相加成账户收益。

独立计算实现见 `independent_audit.py`；与研究实现不同的 CSV/Decimal 汇总和费用算式检查保存于 `independent_arithmetic.json`。本次是官方应用子代理的手动安全试跑，native_task_ref=null，natural_trigger=false。未来原生触发不得引用本次记录作为自然身份。
