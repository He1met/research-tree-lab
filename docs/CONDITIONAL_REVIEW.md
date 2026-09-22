# 条件复核接续层 v1

本版本只为两份已封存 BTC funding plan 准备版本化的条件复算、缺项与反馈 outbox。它不是来源覆盖认证器，不提交生产记录，不调模型/行情 API、不调度任务、不发布网页、不产生新经济验收。固定 plan canonical SHA、原窗口和信号/数量/成本情景均不改变。所有正式 `metrics`（含 trade_count）恒为 null；生效后公开库存恒为 unknown；`data_complete=false`、源覆盖 UNKNOWN，不能产生 FINAL、NOT_TRIGGERED 或 readiness。

## 最小接口

```python
from researchlib.conditional_review import prepare_bundle, prepare_outbox
from researchlib.funding_review import readonly_store

store = readonly_store(project_root)  # 只读现有安装；不会创建 Store
bundle = prepare_bundle(store, batch_id, input_manifest, market_event_cutoff)
# bundle 仅在内存中。以下选择另一个新批次准备可恢复的本地 outbox：
path = prepare_outbox(store, another_batch_id, input_manifest,
                      "new-output.json", market_event_cutoff)
```

`prepare_bundle` 取实际 `store.clock()` 作为新方法及此次信息的可得时点，没有可回填的 information-as-of/native 身份参数。CLI 使用只读安装 reader 的实际系统时钟；隔离合成测试可以控制临时 Store 的时钟。行情 cutoff 不晚于当前信息和原终点。freeze 使用同一次已验证 Store 快照，枚举全部当时已提交、已可得的真实 plan 版本；不只枚举两个已支持项。未知计划逐项 RULES_INCOMPLETE，不阻碍可处理项。

`input_manifest` 精确结构如下；缺省某计划时表示没有接受输入，不表示没有市场成交。每项必须显式有 `sources` 和 `correction`：

```json
{
  "schema_version": 1,
  "plans": {
    "p-btc-funding-short-20260923@1": {
      "sources": [{
        "dataset_ref": "d-btc-trades-20260921@1",
        "adapter": "okx-btc-trade-file-v1",
        "filename": "BTC-USDT-SWAP-trades-2026-09-21.zip",
        "declared_partition": {"date": "2026-09-21", "timezone": "UTC+08:00"},
        "window": {"start_inclusive": "2026-09-20T16:00:00Z", "end_exclusive": "2026-09-20T16:00:01Z"}
      }],
      "correction": null
    }
  }
}
```

此处历史文件仅演示请求 schema，不是原计划入场窗口，也不是未来 plan 的经济输入证明。真实历史接入验收只调用 `decode_sources`，不把这份示例变成生产 review。

- 只接收已登记 dataset ref，逐一绑定 canonical dataset hash、实际 commit/available/acquired 时点、`data_ref=sha256:<原bytes>`、size、来源 URL 和精确目标。URL/取得声明来自 dataset，不接受调用者覆盖。synthetic dataset、未提交或未来可见记录、错合约/角色、无 raw ref 均拒绝。
- trade 只接受 `TARGET_TRADE_HISTORY` + `BTC-USDT-SWAP`，使用已审 `okx-btc-trade-file-v1`；window 必填。每个请求完整扫描源文件再选择窗口，不能用筛选跳过坏行；size 保留来源语义，不推定为 BTC 数量。
- funding 只接受 `TARGET_REALIZED_FUNDING` + `BTC-USDT-SWAP`，使用 `okx-allswap-funding-file-v1`，window 必须 null；其 settlement_mark 恒为 null。已有混合 BTC/ETH 的 exposed-development dataset 不满足这个目标登记契约，不改旧原件来迁就接口。
- 不接受直接 events、sequence、mark、complete/verified 或替代 path。没有 mark decoder，没有新覆盖认证。单文件 parser 的原资源上限继续生效；每计划至多 4 请求、合计至多 20,000 个唯一事件，私有计算附件至多 32,000,000 bytes。超过上限失败，不截断为成功。
- 每个文件先按实际 bytes 和其取得声明完整解码，再按行情 cutoff 选取已发生事件。跨文件同 ID 仅完全相同事件 bytes 可合并；新来源/取得时间改变 canonical 事件时拒绝同时混入，调用者必须明确选择输入并走后续更正。

CLI 是官方应用内离线助手：

```sh
python3 scripts/prepare_conditional_review.py \
  --project-root "$RESEARCH_MAIN_ROOT" \
  --batch-id NEW_UNIQUE_BATCH_ID \
  --input-manifest "$PRIVATE_INPUT_MANIFEST" \
  --market-event-cutoff 2026-09-23T12:00:00Z \
  --output NEW_OUTPUT_FILENAME.json
```

该命令只准备本机 `.local/review-outbox`，不提交 Store。当前维护验收不运行上述命令指向生产；应先在隔离 Store 测试。实际执行需合法真实输入且行情截止已经发生。

## 正式前驱与私有复算

当前仅允许三类前驱：两份精确旧 legacy review 原件；已独立批准的 waiting-v1 完整 METHOD 身份 `d21b004a0efe4295f391a3f82ccba05f6a967b9205d370eabd807a8692f91f65`（包括 CPython 3.9.6/runtime/源码闭包）；同版本、同完整源码/runtime 身份的条件 review。只认方法名称或伪造 version 标签不能迁移。没有无条件放行其他等待方法 hash。

每个新 review 的正式 `opening_state_hash` 仍为上一正式 public-state 的精确 hash。legacy/waiting 迁移不会修改旧原件；等待状态的 `actually_evaluated_market_cutoff=None` 不当成已回放市场区间，生效后的 unknown inventory 不被初始化为实际 0。

公开当前阶段由真实 information-as-of 判断。若信息时点已经生效，但调用者的 market cutoff 仍早于生效点，私有 kernel 可保留历史 `NOT_YET_EFFECTIVE`；公开则为 `WAITING_DATA`、`HISTORICAL_PRE_EFFECTIVE_INPUTS_ONLY`、`inventory=null` 和 `ACTUAL_INVENTORY_UNKNOWN`，并标明 `historical_pre_effective_cutoff=true`。不会用历史截止点把已生效后的未知状态倒退成尚未开始或实际零库存。

完整 kernel input/result、原字符串/行定位、每个 dataset/decoder 的审计、source 绑定和私有更正理由放在同一 bundle 的 `attachments/PRIVATE/<review_id>.json`。公开 simulation_state 仅存固定状态摘要、观察条数、actual inventory 未知和 opaque private hash；不含 entry price、事件字典、轨迹数组、条件库存或任意调用者文本。完整条件情景只留私有。后继只能按真实前驱 metadata 所属 bundle 的固定路径读取，核验 manifest entry hash/size、private hash、METHOD/ref/runtime/可得时间、完整源码逐件 hash，再从已登记原文件重解码、重算旧 kernel，不能借其他 bundle 的同名文件或在缺件时退回空 state。

普通接续必须保留全旧事件 ID/hash，重现前驱 whole input/state，并保持信息和行情截止不倒退。午夜不自动退出、不重新进入、不重计事件。给已评价区间补数、删除/修订旧事件、同 ID 换来源导致 canonical 改变时，输出 `EXPLICIT_CORRECTION_REQUIRED`。

验证从最新前驱一直追到获准原件，而非只重算立即前驱。每一跳都按该历史 review 的真实 prepared/available 时点及实际 commit 可见集重新选取当时最新正式前驱；不能跳过当时已经提交的好或坏 review。同一最新 available 时点出现多份候选时拒绝歧义，不用字典顺序或 revision 猜选。每跳分别校验两种域：公开 opening hash 绑定上一公开 summary；kernel opening hash 绑定上一私有 simulation_state。普通接续必须带正确私有前驱复算，更正才允许在明确旧新差异与公开 supersedes 一致时从头重算。

链深最多 64 个 review（包含批准的起始原件），一次批次最多访问 128 个不同历史 review；去环并缓存已验证节点。超过限额逐项 TECHNICAL_FAILURE，不截断祖先。相同请求、信息截止与行情截止的解码结果在该冻结快照内共享；每个所属 bundle 的完整 Store manifest 门禁只重复核验一次，随后附件逐件核验真实 bytes/hash，避免逐附件重新扫描全 Store。缓存的 canonical 编码累计预算为 128,000,000 bytes（不是进程 RSS 承诺；重复引用保守重复计数）。链与源验证阶段另有 180 秒协作式总限额，传给成交扫描器取消检查；源码、Store 初始读取和最终序列化仍是本地同步操作，不承诺硬实时中断。资源耗尽只产生明确失败，不产生部分成功、空前驱或经济结论。

需要更正时，可先只读生成精确差异提案：

```python
from researchlib.conditional_review import correction_proposal
proposal = correction_proposal(store, plan_ref, new_source_requests,
                               market_event_cutoff, "真实更正原因，仅保留在私有审计")
input_manifest["plans"][plan_ref] = {
    "sources": new_source_requests,
    "correction": proposal["correction"],
}
```

提案不是提交或自动授权。更正必须同时绑定最新正式前驱 ref、旧/新 input fingerprint、实际计算的 added/removed/changed ID 列表及私有原因，不能用布尔 allow_correction 跳过前缀。新 review 增 revision、写 supersedes，保留旧 opening hash、旧原件和新实际可得时点；公开只给固定原因代码、diff hash 与计数。若生成提案后前驱/输入变了，原提案拒绝。

完整 manifest 但缺少该方法约定的 PRIVATE/源码附件、私有 hash/状态不符、坏来源等是该计划 TECHNICAL_FAILURE；不能跳过最新坏前驱找更早的好结果。公开错误仅为固定代码，不包含异常正文、路径或原行。**物理损坏已声明 manifest、Store 完整性异常仍阻止整个批次准备**；本版本不绕过已有 Store 门禁，不制造“全覆盖成功”。

## 覆盖、批次幂等与恢复

覆盖报告分开文件 bytes/schema 完整性、声明分区并集是否覆盖请求区间、源事件完整性 UNKNOWN、同毫秒顺序 UNKNOWN、精确结算 mark MISSING、完整 mark 路径 MISSING、实际费用 UNKNOWN。正式 `actually_evaluated_market_cutoff` 恒为 null；另列 `conditional_computation_market_cutoff` 与 `observed_event_max_at`，两者不表示完整已评价区间。一个很早的事件不会把正式评价游标推进到很晚的请求时点。声明 UTC+8 分区连贯不是事件无遗漏证明；没有文件不能被当成区间已覆盖。正式 batch complete 仅表示全部登记项有处置，`evaluable_results=0`、`final_results=0`。

每个 batch ID 第一次生成的实际 prepared_at、方法闭包、请求 fingerprint、全部 records/本地 attachments 作为完整 canonical outbox 一起封存。沿用现有独占创建和原子保留机制：中断若发生在导出前，可从 `.prepared-batches` 原件恢复；同 ID 重试返回同一原件，不生成新时间、不另写新导出。请求/方法变化必须新 batch。

恢复不能把可自行重算的 content hash 当作许可。它在原 prepared_at 的已提交且可见记录集合上，使用同一准备器重新构建完整预期 bundle，并精确比较全部记录、冻结计划清单、METHOD、每件 SOURCE、每件 PRIVATE 和所有 record 的精确公开许可名单。后来新增 plan、晚 commit 或后来的 review 不进入原清单；普通链/更正链、source 请求与真实 bytes、公开状态使用同一校验。若该 outbox 已正式提交，还必须与实际 committed bundle 的角色、request key、完整文件集合/hash/size 一致；任何冲突拒绝，不重复 commit。失败不更新封存件、不导出被篡改资料。该 helper 不修复 Store 损坏，不以系统时钟倒退伪造新 review chronology；原 prepared_at 只是恢复既有封存内容。

## 公开归档的明确限制

完整 16 文件方法闭包（包含 package initializer 及其真实传递依赖）都随本机附件保留、逐 hash 绑定。公开许可精确列出 `METHOD.json` 与通过原扫描器的 15 个 `SOURCE/*`；它们在加入任何 PRIVATE 之前形成白名单，不使用最终附件的通配导出。

唯一排除的是 `SOURCE/researchlib/public.py`：原扫描器会在这个源码自身的路径检测正则上报 `PRIVATE_LOCAL_PATH`。没有缩小依赖闭包、重编码逃避扫描、改扫描政策或把 raw 加公开许可。METHOD 明示排除原因、精确 hash，以及同字节已公开 [Git 源码](https://github.com/He1met/research-tree-lab/blob/9a5259b7c72c1b3d40ad4b11ae2e28210252d9a0/researchlib/public.py)。本公开包因此**不是自包含完整方法恢复包**；更没有覆盖受限 raw/私有 kernel 原件的科学复算恢复承诺。需要完整复算时仍须合法保有本机绑定的完整源码和原始证据。

## 验证范围

```sh
python3 -m unittest discover -s tests -p test_conditional_review.py -v
```

获准 waiting 迁移的正例测试显式使用隔离的 CPython 3.9.6 runtime fixture，因此可在 Python 3.12 CI 重跑；另有不同 runtime 被拒绝的负例。生产允许的完整 waiting method hash 未放宽。

这些是临时 Store 中的合成工程样本，使用真实原 plan/legacy 形状与合成 CSV；不写生产、不算真实收益。测试实际走 decoder、kernel、Store commit、`publish_snapshot`、`export_backup`，覆盖单次/分日一致、重入/重计、未知库存、中间链丢前缀/跳过当时 latest/双 hash 域、循环/限额/缓存、迟到更正及公开 supersedes、历史行情截止与当前信息时间、幂等/已提交复用/完整 outbox 语义重建、中断恢复、逐项失败、物理 Store 损坏、SOURCE 在公开包、PRIVATE/数字原行/私有原因不在公开包。仅模式秘密扫描不能检出普通行情数字，所以泄漏验证逐文件搜索专用数字 canary，分别检查普通与更正 review、batch、feedback 的真实归档闭包。

`tests/receipts/conditional-real-input-only.json` 是真实既有历史 tick 的只读登记/解码接入回执：4,969,733 行完整校验后首秒选择 112 条。它没有调用 plan/kernel evaluate、没有生成 review、没有保存价格/原行。其 module SHA 对应当时解码测试的开发状态；冻结版接入复验另存 `conditional-real-input-final.json`，不改写旧回执。

独立审查指出整链、恢复公开许可及历史截止状态缺口后，修复版追加回执为 `conditional-real-input-repaired.json`；前两份保留各自实际运行时源码身份，不把旧回执改写成新版本通过。

这些工程能力不消除真实来源无漏/顺序/精确 mark 证据缺口；原计划未来窗口、自然运行和经济效果仍分别等待自己的证据。
