# 正式反事实评价候选 v1

这是隔离工程候选，尚未独立批准、安装或生成生产复核。`formal_funding.py` 实现逐项资格、正式模拟算术与终态；`formal_review.py` 负责 Store 输入、完整历史验证、批次及可恢复 outbox。没有调用网络、账户、行情 API、原生任务或发布程序。

与已部署 7db 的区别是：不是把 `data_complete=false` 换一个诊断名称，而是在同一内部算术上实现可达的分指标及 FINAL 路径；生产固定 resolver 当前没有任何可授予完整性、顺序、mark、费用资格的正式来源 validator。因此真实生产仍不能获得这些未知事实。隔离测试显式替换内部 resolver，用合成事实验证正向路径，不构成来源证书或经济验收。

## 固定计划与分指标算术

只处理两份原 plan，canonical SHA 保持不变：

- `p-btc-funding-short-20260923@1`：`65ff62c3603d257b82b3274785fd1bfe2c5a784d215786be4775fe7fa076bce4`。
- `p-btc-funding-long-control-20260923@1`：`a8dd9a25bd4a5353bc8ed479ec41056bcf07704fccb285f2d014a9615358d02c`。

依据原件 `rules.entry/exit/signal/quantity_or_inventory/termination`、`cost_model`、`evaluation_contract` 与 `replay_missing`：数量为 0.01 BTC，方向 ±1，原入场窗为 2026-09-23 00:05–00:06 UTC，退出窗为次日同一分钟。不得换规则、缩窗、用后来的资金费更新冻结信号。两份固定信号已满足，不存在合法的 NOT_TRIGGERED 分支；空文件、到期或缺数均不能推成“未触发”。

| 正式反事实分项 | 必需事实 | 缺项时行为 |
|---|---|---|
| 入场、退出及模拟库存 | 对该冻结窗口的完整首笔资格与成交顺序 | 当前持仓未知，不凭一个样本价格推定首笔 |
| 已闭仓价格差 | 两笔合法且已证明的 fill | mark/funding 缺失不会抹掉独立已证价格差 |
| 未平仓价格差 | 合法入场与截止估值 mark | 不用未来退出价或日末虚拟强平 |
| 完整资金费总额 | 持仓区间全部结算与精确结算 mark | 不能把已知部分和冒充完整总额 |
| 12 个费用情景 | 固定费用/滑点假设及各指标所需价格/资金费事实 | 全部情景始终列出，未知分项 null；假设不等于实际费用 |
| actual-cost-applied 模拟净值 | 适用腿的实际费用/滑点输入及价格/资金费 | 任一必需费用未知则 actual_net=null，不补零 |
| 完整观察路径及 DD | 上述净值依赖及全部 source mark events | 普通 mark 缺失只阻塞完整路径/DD，不删除已证毛价差或资金费 |

资金费只纳入 `entry_time <= funding_time < exit_time`；费用和滑点按已发生腿只扣一次，开仓期不预扣退出成本。完整路径留 PRIVATE，公开只给逐项汇总、路径点数/hash 和观察 DD；最大绝对回撤与最大比例回撤分别计算。`actual_net` 指原协议实际成本输入作用于反事实模型的净值，**不是账户实际盈亏**。公开 `actual_inventory` 永远 null，模拟库存注明反事实口径。

FINAL 要求原终点到达、合法退出、资金费全集与精确 mark、完整 source mark 路径、verified cost schedule，并且实际适用腿费用输入完整。原 `termination` 的 verified inputs、`replay_missing` 的 verified actual trading-cost schedule，与 `evaluation_contract.actual_net` 的实际成本输入不可合并成一个布尔值。仅 schedule 已证而实际费用仍缺时，本候选保守保留 `cost_terminal_interpretation=UNPROVEN`、不 FINAL；不擅自认定 FINAL 可以 actual_net=null，也不新增账户访问前提。明确成本适用语义/真实来源后须另审 validator。

公开当前阶段以实际信息时点为准；信息已过生效而 market cutoff 仍为历史时，公开 WAITING_DATA、库存未知，私有内核可保存历史 NOT_YET_EFFECTIVE。已证合法退出即使尚未到原一分钟终点，也保留闭仓分项及模拟库存 0，但只 STAGE；终点未到不 FINAL。

## Store-only 输入与尚缺来源

```python
from researchlib.formal_review import prepare_bundle, prepare_outbox, correction_proposal
from researchlib.funding_review import readonly_store

store = readonly_store(project_root)
bundle = prepare_bundle(store, "NEW_BATCH_ID", input_manifest, market_event_cutoff)
# 仅内存；另选唯一 batch 后可准备本机 outbox，仍不提交 Store：
path = prepare_outbox(store, "ANOTHER_NEW_BATCH_ID", input_manifest,
                      "NEW_OUTPUT_FILENAME.json", market_event_cutoff)
```

`input_manifest` 沿用已审 conditional 精确 schema：`{"schema_version":1,"plans":{plan_ref:{"sources":[request],"correction":null}}}`。每个 source request 仅含 `dataset_ref/adapter/filename/declared_partition/window`；具体示例见 `docs/CONDITIONAL_REVIEW.md`。缺少某计划配置表示没有输入，不表示无成交。

CLI 在官方应用内运行：

```sh
python3 scripts/prepare_formal_review.py \
  --project-root "$RESEARCH_MAIN_ROOT" \
  --batch-id NEW_UNIQUE_BATCH_ID \
  --input-manifest "$PRIVATE_INPUT_MANIFEST" \
  --market-event-cutoff 2026-09-23T12:00:00Z \
  --output NEW_OUTPUT_FILENAME.json
```

本候选验收不把命令指向生产。实际使用取真实系统时间，不允许回填方法可得时间或自然触发身份；没有提交、发布、调度或账户操作。

生产 resolver 只能按已登记 dataset 取得其 canonical hash、真实 acquired/available/committed 三时点、raw SHA/size、目标合约/角色，再调用已审单文件 parser 全文件解码。原文件坏行不能被窗口筛选绕过。路径/URL/取得声明不能由请求覆盖；synthetic、未提交、未来、错目标或 symlink 原件拒绝。source URL 白名单、SHA、CRC、已解码到 EOF 及 UTC+8 声明分区不证明网络来源、事件无漏或撮合顺序。

当前真实 trade 格式只支持逐行观察、sequence=null、同毫秒歧义；funding 格式只有 realized rate/time，settlement_mark=null。**没有**可用的官方全集/首笔顺序、精确结算 mark、全 source mark events、实际适用费用 validator。生产没有 backend 参数、events 上传、verified/coverage 布尔、证书 JSON schema 或 registry。内部 `_Resolution` 是固定受审代码的计算对象，不是可上传官方证据，也不是操作系统权限边界。只有今后独立审核具体真实来源格式及其语义后，才能改固定 resolver 授予相应资格。

覆盖报告分别列文件校验、声明分区、顺序、资金费/mark/费用依赖；一个旧事件或声明分区不能推进正式 `actually_evaluated_market_cutoff`。该游标只在持仓区间必需价格、资金费及完整 mark 路径均被独立资格支持时存在；费用仍单列。当前生产资格全空，所有正式分项/游标未知，`data_complete=false`。正式 batch complete 仅表示清单处置完成。

## 历史、修订与最终复用

现有 7db 的 16 件源码完全不改。每次准备先验证本地完整 7db source/runtime 身份 `7dbdd186fd04ddca07dc3bfa933f9a0fae1ce66e1f1d91447e0bbeff5332d3ce`，由已审实现验证其精确 legacy/waiting profile 与完整 conditional 链。新的 formal 方法把旧 16 件与新增 3 件运行源一起纳入完整 19 件 METHOD 闭包。只认精确身份，不执行附件代码、调用 Git 或网络；旧 waiting 缺少完整闭包附件的限制仍保留。生产当前固定已批准 CPython 3.9.6，别的 runtime 不能伪装获准身份。

每跳按真实 prepared/available 与 committed 可见集重新确定当时 latest；坏最新节点不能跳过，同一最新时间歧义拒绝。完整同 bundle METHOD、SOURCE、PRIVATE 按 manifest hash/size 回读；旧已登记 source 重新解码，旧 kernel 全输入/状态及每步普通前缀重算。公开 opening hash 绑定上一公开摘要，内核 opening hash 绑定上一私有内核状态。缺件、篡改、倒退、晚到或普通链丢前缀不能重置成空仓。

给旧区间增加/删除/更换事件及同 ID 改 provenance，必须显式 correction。正式层的费用分配或资格事实变化也必须 correction；即使变化合理，不能静默改写旧结果。`correction_proposal` 返回可放入配置的 correction 字典，绑定最新 review、旧新 input hash、事件差异、旧新 fact hash 与差异、私有原因。它不能授权新事实，所有事实仍由固定 resolver 在新实际信息时点重建。新 review 使用 supersedes/revision，公开只给 hash/计数/固定原因，原件不改。普通后继必须完整接纳该更正链。方法改版须另审兼容身份，不能借 correction 换方法规则。

FINAL 复用先重新验证完整 latest 链、实际登记源与相同方法/输入/截止/资格/费用。每个本批复用项生成明确 `disposition=REUSED_FINAL` 的承载 review，actual created/available 为本次验证时间，但 `results.economic_computation_information_as_of`、市场截止、全部原 kernel/result 保留原经济计算时点，`economic_recomputed=false`。PRIVATE 分别绑定直接前驱公开/内核/private hash；复用是独立类型，不能把原 kernel opening hash 改成新前驱来冒充新计算。连续 carrier 仍逐跳验证，后继不跳过坏 carrier。

批次 `input_record_refs` 显式链接本批所有 review，carrier 再链接前驱，兼容既有 snapshot 的 batch_ref 计数与单根 archive 语义闭包。全复用与部分复用均可定位原 FINAL，不重计交易/费用、不延长经济有效期。

## 公开与恢复边界

公开只许可 METHOD 与 18 件通过原扫描器的 SOURCE。完整本地 19 件仍绑定，唯一排除 `SOURCE/researchlib/public.py`，保持原精确 SHA 和 e65bb32 Git locator；不缩小闭包、不编码绕扫描、不许可 PRIVATE/raw。因此公开包不是完整自包含方法或受限经济复算恢复包。

在生成新 bundle 前，先检查所引用语义祖先及同 bundle 所有记录的公开附件许可、固定派生文本、反馈与冻结批次清单。此检查独立于 evaluator 标签与 provenance 是否正确；UNKNOWN 方法不能掩盖 PRIVATE 许可。**公开祖先许可/派生文本异常整批拒绝**，不生成一个仍引用危险祖先、可把私人附件带入 archive 的“失败 review”。这是公开安全特例；一般规则/数据/状态错误仍逐项 TECHNICAL_FAILURE，保留原 opening 与前驱，不阻碍另一计划。Store 物理完整性损坏保持原整库门禁。

同 batch 重试复用原 prepared_at 和已冻结清单，在原双时点可见集上重建完整预期 bundle，比较全部 records、SOURCE/METHOD/PRIVATE/公开许可；自重算 content hash 不能授权修改。后加计划/晚提交不进入旧清单。已提交的 outbox 还必须与实际 Store 原文件集合/hash/size 一致；不重复 commit。旧 7db outbox 只能用未改的旧 helper 恢复，新 helper 不把旧同 ID 内容重解释成新方法。

资源边界沿用单文件 parser 上限、每计划最多 4 请求/20,000 事件、PRIVATE 32,000,000 bytes、链深 64、不同 review 节点 128。formal 与 7db 验证共享协作截止，并对二者缓存并集累计限制 128,000,000 bytes；不是各自一份额度，也不是 RSS 保证。历史与解码最多 180 秒协作限额，初始 Store 读取、源码读取及最终同步序列化不是硬实时中断。公开祖先语义闭包最多 4096 节点；无法完成公开安全预检时不准备 bundle，其后普通计划验证资源不足逐项失败，不截断为成功。

## 工程验证与剩余缺项

```sh
python3 -m unittest discover -s tests -p 'test_formal*.py' -v
```

隔离测试包括同一算术两方向全部 12 情景、资金费半开区间、一次/分日一致、不重入、单次滑点、开仓不预扣退出费、独立分项缺数、实际逐腿成本路径/DD、FINAL 与禁用 NOT_TRIGGERED；真实临时 Store 验证 legacy/waiting/7db 到 formal、坏最新/中间重置、联合资源限额、显式事件与费用/资格更正、复用载体、全批次及恢复、真实 snapshot/archive 无 PRIVATE/canary。测试中的来源资格全部是明确合成替身；没有用历史样本计算未来 plan 经济结果。

跨版本 CI 的桥接正例显式固定受审 3.9.6 runtime fixture；另测试不同 runtime 拒绝。这不授予生产 3.12 新方法身份。测试结果/冻结 SHA 见同目录候选回执。独立算术 oracle 来自主库已封存审计，未将其合成正例当真实来源证明。

剩余是真实来源能力：没有官方格式/证据支持的覆盖、同毫秒首笔、精确结算 mark、完整 mark 路径和实际适用费用不能由本模块凭空提供。之后修改 resolver 或升级方法必须维护部署盘点、完整旧方法/祖先及私有状态兼容，不能换一个 hash 就永久阻断已使用的 7db/formal 链；也不能执行附件 Python 来规避迁移工作。

真实既有单文件接入可用以下独立脚本重跑（输出必须是新文件）：

```sh
python3 tests/replay_formal_registered_sample.py \
  --project-root "$RESEARCH_MAIN_ROOT" \
  --receipt "$NEW_RECEIPT_PATH"
```

它从真实 Store 读取旧 2026-09-21 BTC dataset 与 content-addressed 原文件，只调用生产固定 resolver、禁止 `_compute`；不拷贝 raw、不提交 review。输出仅含计数/hash/真实 acquired 绑定与未授予资格说明。首次开发接入回执与冻结版回执分别保存，不覆盖旧哈希。
