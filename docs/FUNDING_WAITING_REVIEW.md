# 原资金费方案的等待状态复核预备

`scripts/prepare_funding_review.py` 为每日复核准备版本化的 batch、review、feedback 和方法附件。它只读取稳定 Store，把新原件写入 `.local/review-outbox/`；不会提交 Store、调用行情 API、运行经济回放或发布网页。本文描述工具的使用边界，不代表任何生产批次已经准备、提交或自然触发。

当前方法 `funding-review-waiting-v1` 只处理下列两个原封存方案的精确版本与 canonical hash。它补充状态迁移和等待处置，不证明行情完整性，也不完成正式经济评价。

| 原方案 | 固定 canonical SHA-256 |
| --- | --- |
| `p-btc-funding-short-20260923@1` | `65ff62c3603d257b82b3274785fd1bfe2c5a784d215786be4775fe7fa076bce4` |
| `p-btc-funding-long-control-20260923@1` | `a8dd9a25bd4a5353bc8ed479ec41056bcf07704fccb285f2d014a9615358d02c` |

## CLI 与准备结果

在经审查的源码安装到实际项目后，先确认实际安装配置与稳定原档位置，再运行：

```sh
python3 scripts/prepare_funding_review.py --help
```

参数与当前 `--help` 对齐：

| 参数 | 含义 |
| --- | --- |
| `--project-root PROJECT_ROOT` | 实际项目安装根，读取其中的 `.local/installation.json` 来定位稳定 Store。默认是脚本所属项目根，不是当前工作目录。 |
| `--batch-id BATCH_ID` | 必填的新批次标识，受安全 ID 校验，最长 90 字符；一经准备不可用同 ID 重造。 |
| `--market-event-cutoff MARKET_EVENT_CUTOFF` | 可选、带时区的实际已发生行情截止。不可晚于本次准备时间；对于支持的方案也不可超出原评价终点。它不设置方法可得时间或信息截止。 |
| `--output OUTPUT` | 必填、相对 `.local/review-outbox/` 的新 `.json` 路径，不允许覆盖。 |

以下仅为命令模板。将 `YYYYMMDD` 和序号替换为实际独立批次标识；同一批次失败重试应先检查保留原件，不能通过换 ID 绕过重复保护。

```sh
python3 scripts/prepare_funding_review.py \
  --batch-id review-waiting-manual-YYYYMMDD-001 \
  --output manual/review-waiting-manual-YYYYMMDD-001.json
```

若脚本位于隔离工作树，应显式使用 `--project-root` 指向已经确认的实际安装根，不能把临时工作树猜作原档位置。工具要求稳定 Store 已存在，不会为缺失的 Store 创建空目录。实际输出始终位于指定项目根的 outbox。

CLI 不提供 `--information-as-of`、原生任务身份、市场源数据行、收益参数或 `--commit`。不要通过修改系统时钟、源码或生成的原件制造过去的信息截止。成功返回 `OUTBOX_PREPARED_NOT_COMMITTED`，同时明确 `formal_economic_evaluation: false`；拒绝返回 `REJECTED`，退出码为 2。退出成功只代表预备原件已生成。

## 固定批次与逐项状态

工具使用一次严格读取后的 `freeze_batch` 固定信息截止前全部正式方案版本。方案和前次复核都须在该截止前真实可得且已经提交；不能以记录中较早的 `available_at` 纳入迟提交原件。每项保留精确 `plan_ref`、`plan_hash`、`previous_review_ref`、`opening_state_hash`，新 review 递增 revision，旧方案、review 和反馈不改写。

| 条件 | 本次处置 |
| --- | --- |
| 支持的精确方案，前次状态与方法验证通过，实际准备时间早于生效时间 | `NOT_YET_EFFECTIVE`；库存 `"0"` 只描述生效前尚未开始的状态。 |
| 支持的精确方案，验证通过，已经生效但未接纳可验证输入 | `WAITING_DATA`；库存为 `null`，表示生效后持仓未知。 |
| 原窗口已经结束，但必要输入仍未接纳 | 仍为 `WAITING_DATA`，不能生成 `FINAL` 或 `NOT_TRIGGERED`。 |
| 未知方案或同版本原件 hash 不匹配 | 该项 `RULES_INCOMPLETE`，保留在批次清单中。 |
| 前次状态、方法证据或接续时序不能验证 | 该项 `TECHNICAL_FAILURE`，保留旧引用与旧状态 hash；不清空或重置旧仓位。 |

单项未知方案或坏旧状态不会使其他有效项被跳过。Store 原件异常等批次级完整性问题则拒绝准备。批次 `complete` / `coverage_complete` 仅表示冻结清单每项都有处置；`evaluable_results` 与 `final_results` 均为 0，不代表策略通过、数据覆盖完成或经济结果为零。

收益、费用、资金费现金流、净值路径、回撤、持仓时长和 `trade_count` 均为 `null`。没有接纳事件不证明没有市场事件、没有入场或零交易。两个假设方案也不能合并称为实际账户结果。

## 信息时间与行情时间

`prepared_at`、`information_as_of` 和新方法 `available_at` 使用本次真实准备时间。新方法的可得时间不会倒签到旧方案封存时点。原方案生效时间为 `2026-09-23T00:05:00Z`，评价终点为 `2026-09-24T00:06:00Z`；状态阶段依据实际信息时点与原生效时间判断，选择较早行情截止不会把新方法变为当时可用的方法。

默认行情截止为本次准备时间与原评价终点中的较早者。显式未来截止导致整次拒绝；支持方案的截止超出原终点或倒退到前次复核游标之前，会记录逐项技术失败。`actually_evaluated_market_cutoff` 始终为 `null`，因为本工具没有执行行情回放。

等待原因分别说明：正式来源适配器尚未绑定到本状态方法、来源覆盖未验证、实际成本未知、尚无已接纳行情输入，以及原窗口事件尚未发生或窗口已结束但输入仍缺失。其他模块存在文件解码能力，不等于本方法已经接入该模块或获得完整性证明。

## 方法证据与旧状态验证

每个新 bundle 包含 `METHOD.json` 和相关方法源码附件。`METHOD.json` 冻结从该模块与 CLI 入口递归分析得到的本地 import 源码 hash，包含 `researchlib/__init__.py` 及其可达依赖，并记录 Python 实现、版本和无第三方运行依赖。方法身份绑定这些源码 hash 与运行时说明。

当前静态依赖清单为 `researchlib/{__init__,common,contracts,funding_review,novelty,public,readiness,review,snapshot,store}.py` 及 `scripts/prepare_funding_review.py`。这是本地静态 import 闭包和 Python 版本约束，不是整个操作系统环境的二进制封存。附件保存六个直接相关源码文件及 `METHOD.json`；其余依赖通过清单中的 hash 绑定经审查的发布源码，不能声称每个依赖源码都已随 bundle 附送。

首次桥接只接受两份已核对的原始 bootstrap review 的固定 ID 和 canonical hash，而非任意声明 `independent-forward-status-v1` 的记录。随后逐字段检查旧状态：严格有限十进制零库存、空事件列表、无 entry/exit fill、无 last event、费用与现金流为空，并且处于生效前。未知字段、残余成本、已处理事件或未知状态均不能静默丢弃。

后续接续要求前次 review 属于同一受支持等待方法，其 `review_method_ref` 必须指向该 review 实际已提交 bundle 中的 `METHOD.json`。工具核验附件字节 hash、完整方法清单、方法可得时间和实际提交时间，再验证等待状态。悬空方法引用、照抄 evaluator 标签、复制旧 review 换 ID、未知 kernel 仓位状态均不能通过。源码或 Python 版本变化导致方法身份变化时，不会自动假定旧状态仍可接续。

## 同批次重试与原件保留

用户输出路径与批次唯一身份相互独立。工具先在 `.local/review-outbox/.prepared-batches/<sha256(batch_id)>.json` 原子保存完整 bundle 原件，再向 `--output` 指定的新路径保存相同内容。内部文件是可核验的完整预备原件，不是正式 Store research claim。

同一 batch ID 再次准备一律拒绝，包括相同内容、不同输出文件名或不同准备时间；错误为 `BATCH_ALREADY_PREPARED`。已正式提交的 batch ID 也不能重造。用户输出已存在、路径穿越、绝对路径、符号链接路径及保留目录均拒绝。

若进程在内部原件完成后、用户输出完成前中断，内部完整原件仍保留。当前 CLI 没有自动恢复导出选项：先核对该原件及实际提交状态，按既有复核流程使用保留原件，不删除身份文件、不覆盖旧文件，也不重新计算相同批次。若没有完整原件，按实际失败证据处理，不把残留临时文件当作成功记录。

## 身份与正常提交流程

本工具固定写入 `MANUAL_PREPARATION_NOT_NATURAL`、`natural_trigger: false`、`native_task_ref: null`，并注明原生身份未由此工具认证。即便由某个已启用任务调用，也不能单凭自由填写 header、进程环境或任务 ACTIVE 状态将其升级为自然运行。未来自然身份须有独立的实际任务与运行证据；本 CLI 没有这样的认证入口。

日常操作继续遵守 [daily-review skill](../.agents/skills/daily-review/SKILL.md) 和 [每日复核任务说明](../planning/current/prompts/03_DAILY_REVIEW.txt)：确认实际项目与稳定原档，核对固定清单、前次状态、方法附件、等待原因、全部指标为空以及输入可得/提交时间。共享代码先经独立审查与既有维护流程安装；准备原件仍须由 daily-review 角色正常审查，不能把工具成功退出作为提交依据。

完成上述核对后，由既有 Store CLI 受控追加已审查原件。例如从实际项目根提交对应输出文件：

```sh
python3 scripts/store_cli.py commit \
  --input .local/review-outbox/manual/review-waiting-manual-YYYYMMDD-001.json
```

这是后续独立写入步骤，本文及预备 CLI 都不执行它。需要显式项目根时，`store_cli.py` 的 `--project-root` 位于 `commit` 子命令之前；若当前正式 claim 流程要求 token，应沿用实际合法 owner/token，不编造或绕过。追加后的共享索引、公开快照和网页由发布职责处理。

等待处置记录本身可以成为真实、可追溯的正式研究原件，但仍不证明策略收益、完整来源覆盖、自然调度或正式经济计算已完成。后续经济复核仍需独立验证输入契约、原窗口覆盖、可得时点、真实成本范围和适用的版本化评价方法，参见 [原规则评价 kernel 边界](FUNDING_FORWARD_KERNEL.md)。
