# 维护接续协议

此协议由现有验收 heartbeat 执行。`review/continuation-audit/maintenance_flow.py` 只持久化决策，不调用代理、模型、调度器、安装器或研究业务，也不证明自然运行。既有维护与四业务任务沿用各自当前实际模型配置；用户明确为具体新任务或其子代理指定模型时，以该授权为准，不据此更改其他任务。2026-10-02新增经济闭环实施任务及其新子代理使用用户指定gpt-6.1-sol / ultra；四业务仍gpt-6-astra / medium，现有频率、权限与静默通知规则保持。

## 唯一 owner 与现有状态导入

稳定维护控制目录为安装项目下的 `.local/operations/maintenance/`，真实状态由本实施任务唯一写入。先读 `current.json`、已有派工意图和对应绑定回执，查询绑定的真实官方任务/代理句柄。目录和文件时间不代表阶段或活跃状态。不得删除未知锁、重新领取业务或覆盖旧回执。

首次采用助手时，先确认现有 schema 1 的 `owner_thread_id` 与本任务匹配，再执行：

```sh
python3 review/continuation-audit/maintenance_flow.py --state-dir .local/operations/maintenance --owner ACTUAL_OWNER_THREAD_ID
```

`ACTUAL_OWNER_THREAD_ID` 必须替换为已核实身份，不能编造。已有 `current.json` 被完整导入首个 journal 条目，保留 consumed review hashes、候选 hash、真实 worker handle 和 dispatch intent 等字段。已有独立派工/绑定 JSON 不改写。已有 `REPAIR_RUNNING` 可直接消费同句柄的完成回执，不再次 reserve。首个 journal 后，journal 是恢复依据，current 是物化视图；不同步时在锁内由 journal 恢复。

## 每次 heartbeat 的有限工作

1. 先核验当前安装身份、角色锁和实际源码，再读取控制状态。对未消费的独审或完成回执逐件验证真实内容、来源、候选 hash 和完成状态。不是依据作者自报或文件出现就认定通过。
2. 审查 `CHANGES_REQUIRED` 写 `REVIEW_RESULT`，记录回执文件实际 SHA-256 和候选 manifest SHA-256，进入 `REPAIR_READY`。同回执 hash 即使被不同通知包装，也不重复消费。
3. 写 `RESERVE`（role 为 `REPAIR` 或 `REVIEW`），获得持久化 dispatch intent 后，才通过现有官方代理工具实际派工一次。成功后以工具返回的真实句柄写 `BIND`。工具异常、进程中断或超时留下 `DISPATCH_UNKNOWN`，先查询派工记录和目标句柄；绝不因等待而再次派工。
4. 已绑定工作只查询该句柄。BUSY、UNKNOWN、TIMEOUT、FAILED、MISSING 写 `OBSERVATION`，保存下一检查条件和错误分类，不自动重发。确认缺失或失败后的替代工作必须由 owner 核对未执行/已终止证据、追加单独恢复决定；当前助手刻意不提供自动重置入口。
5. 修复真实完成后，逐文件核对新的冻结 manifest、原始审查问题及交付证据，再写同句柄的 `REPAIR_COMPLETE`，进入 `REVIEW_READY`。新 manifest 必须不同。随后 reserve 一次独立审查，不能让作者自审批准。
6. 独立审查 APPROVED 必须精确匹配当前候选，方进入 `INSTALL_READY`。此阶段仍不是已安装。owner 核验安装空闲边界、批准源码映射与回执后实际安装，读回安装身份并写 `INSTALL_VERIFIED`，绑定批准回执 hash、新 source hash 和安装证据，才进入 `REAL_FLOW_WAIT`。
7. 正式研究/复核/发布由原有业务任务完成。接续核验真实合格输入、原规则成本评价、feedback 和网页回读全部证据后，才写 `FLOW_GATE_VERIFIED`；它只进入 `TRIAL_GATE_READY`，不启动计时。试行还需两路线真实首次启动记录，按现行并行政策取较晚者加168小时。

事件 JSON 经 operator 核验后通过同一入口消费：

```sh
python3 review/continuation-audit/maintenance_flow.py --state-dir .local/operations/maintenance --owner ACTUAL_OWNER_THREAD_ID --event VERIFIED_CALLBACK_JSON
```

回调最小示例结构见 `test_maintenance_flow.py`。`evidence` 包含 `reference` 和文件实际 `sha256`；审批含 `candidate_manifest_sha256`、`verdict`；修复完成另含原 `worker_handle`；安装含 `approval_receipt_sha256` 和 `installed_source_sha256`。这些字段的真实来源和语义由调用者验证，助手只验证状态与 hash 格式/绑定关系，不能把任意 JSON 自称的 APPROVED 当作独审。所有实际 callback 留在私有 operations，不公开私人路径或任务身份。

## 数据等待与恢复边界

`DATA_WAIT` 指明方向、逐项 missing 和 next_check，仅更新该方向等待表，不更改维护主阶段或阻止其他合法方向。旧 BTC 窗口已结束，不写未来窗口等待。缺少可靠计时就写 UNKNOWN。真实输入与原规则允许的完整成本情景可满足流程准入；actual_net 不明保持 null，不能升级经济 FINAL。

助手使用非阻塞 `flock`，锁繁忙立即失败且不删锁。每个 journal 条目先写临时文件、fsync、原子发布，再更新 current；中间崩溃下次从 journal 恢复，重复事件不派工。文件锁是同用户协作锁，不是权限隔离。人工恶意改写控制文件不在 hash 链的防护承诺内；异常链、foreign owner 或未知状态均停止修改并记录调查需要。

隔离工程验证命令：

```sh
python3 -m unittest discover -s review/continuation-audit -p test_maintenance_flow.py -v
```

工程测试覆盖失败→修复→独审→安装待执行、分方向数据等待、重入去重、journal/current 崩溃窗口、错误候选、foreign owner、忙锁与篡改检测。测试不创建生产研究、不安装评价器、不贡献自然运行证据。每次接续只有实质进展、失败或需要用户动作才通知；没有新证据则保留控制状态，由原有 heartbeat 再检查。
