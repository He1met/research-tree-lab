# 已封存 BTC 方案的固定计算内核

维护版本 `funding-forward-kernel-v1` 仅处理两份原方案的精确 canonical SHA；任何方向、数量、时间、成本情景或其他字段改变均拒绝，不把新实现倒签为旧方案当时已有的方法。原 plan/review、原 method 标签和原执行资格不修改。

当前交付范围是**条件计算内核**，不是已完成的官方资料评价器。`researchlib/funding_forward.py` 始终输出 `source_coverage=UNVERIFIED_NO_AUDITED_OFFICIAL_ADAPTER`、`data_complete=false`；所有正式实际收益指标仍为 null。调用者即使填 `complete=true` / `verified=true` 也不能产生 FINAL、NOT_TRIGGERED、readiness 或自然运行证明。当前缺失的来源适配、覆盖验证和旧正式 review 状态迁移分别列在 `missing_capabilities`，不能只说未来数据还没有发生。

计算直接绑定封存数量、方向、固定历史信号、合法窗口、所有 12 个预先成本情景和名义本金口径。事件仅支持目标合约的 trade、mark、funding；每项有稳定 ID、源字节哈希、事件时点和实际可得时点。同毫秒成交必须有唯一非负交易所顺序键，否则 PATH_AMBIGUOUS。源哈希仅是身份，不证明官方来源和完整覆盖。资金费只取 `entry <= settlement < exit`，精确结算 mark 缺失时依赖的资金费/净额/权益路径为 null；不会补零、插值或按八小时猜日历。

`conditional_observed_input_metrics` 与 `scenarios` 是**以调用者所给观察为条件的计算**；首笔身份、遗漏成交、资金费全覆盖都未被证明。原价格计算价差，再单独扣一次费用和滑点。轨迹保留观察到的 mark、资金费点和成交点，回撤明确只涵盖观察点；实际用户成本未知。两个相反方向并不构成可相加的账户结果，也不证明资金费预测 alpha。

两个截止必须分开：`information_as_of` 限制真实取得的信息，`market_event_cutoff` 限制行情事件且不越过原终点。后来下载的历史观察可在后来信息截止计算，但不得倒签取得时点或改变原信号。跨日使用完整既有输入前缀复算；前次 state 必须能从其输入复现，所有旧事件 ID/hash 保持一致。删除/改字节、改变已选择成交、给已评价区间补事件都拒绝，需要显式纠错版本；当前内核不自动生成 correction。午夜和每日截止不关闭持仓、不重计资金费。

`scripts/evaluate_funding.py` 是官方应用内的只读计算辅助命令。它从真实 Store 读取原 plan，拒绝尚未提交或 synthetic/未声明真实的输入，不从测试夹具回退；输出 `CONDITIONAL_COMPUTATION_ONLY_NOT_A_FORMAL_REVIEW` 到项目 `.local/review-computation/` 下指定新文件（拒绝路径穿越、符号链接及覆盖已有文件）。它没有网络、任务触发、store 提交或发布副作用。`natural_trigger=false` 仅说明此计算回执不是自然任务身份，不能据此覆盖调用它的独立原生身份记录。

输入示意（值均须来自实际资料；不要将本示意补成生产数据）：

```json
{"instrument":"BTC-USDT-SWAP","currency":"USDT","synthetic":false,"events":[]}
```

每个事件需要 `event_id/kind/instrument/currency/event_at/available_at/source_sha256`，trade/mark 需 `price`，trade 同时点排序需实际 `sequence`，funding 需 `rate/settlement_mark`。decimal 采用字符串，固定 50 位有效精度和 ROUND_HALF_EVEN，不继承其他分析的全局数值上下文；NaN/Infinity、非正价格、混合单位、未来或倒签观察均拒绝。空事件只表达没有输入，不证明没有成交或零资金费。

下一必要实现仍是从许可来源取得的官方原文件固定解码、真实下载范围/缺口/排序校验，以及可复算的独立覆盖证明，再增加版本化正式 review 输出和原生效前状态迁移。来源格式或精确结算 mark 不可得时保留缺项。真实前向路径和自然触发验收另行取证。

工程验证使用 `tests/test_funding_forward.py` 的合成数据，独立检查原公式、正负方向、全部成本情景、中途回撤、重复事件、窗口边界、双截止、缺失输入、状态篡改及跨日一致性。测试数据不进入生产 store、公开业务快照或真实成果计数。
