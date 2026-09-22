# 文件事实层与公开投影

本目录是标准库 Python 3.9+ 的生产程序。它不调用模型、行情接口或交易接口，也不创建调度服务。合成工程检查在 `tests/test_storage_contracts.py` 与 `tests/test_replay_ledger.py`，只使用临时目录。

## 写入及恢复接口

```python
from researchlib import Store, publish_snapshot
from researchlib.archive import export_backup, restore_backup

store = Store(project_root)  # 从 .local/installation.json 读取稳定原档/data根
claim = store.claim(request_key, owner_id, "research")
store.commit_bundle(bundle_id, "research", records, attachments,
                    request_key=request_key, claim_token=claim["token"])
result = publish_snapshot(store, public_data_directory)
backup = export_backup(store, archive_file, record_refs=[round_id])
restore = restore_backup(archive_file, new_empty_directory)
```

`records` 是符合现行模板的对象数组，另需明确 `record_type`、实际 `created_at`、`available_at` 和 `synthetic`。保留模板中的字段名；正式对象移除 `template_only`，`record_state` 不可是 `DRAFT_NOT_COMMITTED`。支持 schema `1`、`"1"`、`"1.0"`，未知版本拒收/在读取时明确列异常。

记录引用使用稳定 ID，方案是 `plan_id@version`，产品/数据/方法有版本时是 `id@version`，运行有 attempt 时是 `run_id@attempt_id`。附件引用是 `bundle:BUNDLE_ID/attachments/name.md`。共享原始数据通过 `Store.put_data(bytes, provenance, role)` 内容去重，返回 `sha256:...`；附属事实记录保存身份、来源、时间、许可和目标/参考角色。

`attachments` 是相对文件名到原始 bytes（CLI 输入可为字符串）的字典。所有文件先写到专属 staging，逐个 fsync，再写完整 manifest，原子 rename 至稳定 store 的 `bundles/`。只有完整 manifest 和所有字节验证通过的对象才能进入正式读取。内部 record 相对路径包含类型。未完成 staging 保留，正式结果不会读取它。恢复同 request 不生成新研究；完成的 request 返回原 bundle。相同 ID 异内容拒收。

认领无超时偷取。`transfer_claim` 必须给当前已调查 owner、调查证据引用和理由，增加 generation 并更换 token；旧 owner 提交会被 fencing 拒绝。它是受控程序入口，不能阻止具有同样系统文件权限的进程直接改文件。读取独立重算哈希可以发现原件被改；这些机制不是 OS 硬沙箱。

命令行只是应用内计算助手，不运行 Codex CLI：

```text
python3 scripts/store_cli.py --help
python3 scripts/store_cli.py commit --input research/my-bundle.json
python3 scripts/store_cli.py validate
python3 scripts/store_cli.py review-batch --id review-YYYYMMDD --commit
python3 scripts/store_cli.py snapshot --output site/data
python3 scripts/store_cli.py backup --output .local/archives/research.zip --record-ref ROUND_ID
python3 scripts/store_cli.py restore --archive .local/archives/research.zip --directory .local/recovery/new
```

CLI bundle 格式为 `{bundle_id, role, request_key, records, attachments}`。复核批次枚举全部正式非合成方案，包括旧版、负结果、缺数与规则不全。`freeze_batch` 返回待提交对象；跨日复核绑定 `previous_review_ref` 和此前 `simulation_state` 的规范 JSON SHA-256（规范 JSON 为 UTF-8、排序键、无多余空格、末尾换行）。截止不产生退出成交。只有原终点到达且完整数据路径明确为真才允许 FINAL。最终输入和评价器版本未变可复用。纠错采用新 review ID、增加 revision、`supersedes` 和理由，公开投影会给相关反馈与后继加需复查标记。

`replay.py` 是精确费用/库存事件账本，只处理冻结规则已经产生的事件，不自行猜成交。价格、币种、资金费正负方向和未知费用都有明确语义；未知净值为 null。它不等于四产品的已完成策略回测器。动态模型决策没有当时留档时拒绝回放。

## 公开与执行条件

公开原件需 `disclosure.visibility=PUBLIC`，且许可在显式允许集合内；来源原文不会因为报告自撰而获得转载许可。导出字段取 schema 白名单与 `export_fields` 的交集。附件需显式列入 `disclosure.public_attachments`（如 `attachments/report.md`）。秘密、私人绝对路径、路径逃逸、symlink、未支持二进制及嵌套压缩包均检查。扫描是工程门禁，内容许可仍由来源核实记录负责。

执行条件固定策略是 `execution-conditions-v1`。只有明确 ELIGIBLE/REPLAYABLE 且完整冻结规则、可解析方法、精确目标数据与产品的方案才能进一步检查。每项证据需 `evidence_status=VERIFIED`、`check_names` 作用域、精确计划版本、`verification_method`、时点与来源链。来源链最终必须指向已保存且 hash 可验证的原始 bytes，附有公开 HTTPS `source_url`。缺失、循环、未来、失效、参考数据或超出原入场窗口一律不能绿色。固定程序验证记录完整性与作用域；它不能代替实际核实来源事实的独立工作。收益正负不是通过条件，账户始终未评估，也不授予交易权限。

已封存为 `INCOMPLETE_DATA` 且未绑定可解析 TARGET 数据/方法的旧版本不会因增加一张 assessment 被升格。补齐时建立引用旧版本的新 plan 版本，保存新的封存/生效/入场窗口；旧版本继续按原规则复核。这里需要的是规则和当前必要输入，不要求未来收益路径已发生。未来评价窗口未到应体现在 review 的阶段/等待状态，不能在规则与当前执行事实已经齐备时仅因未来结果未知而倒填数据。

新颖性采用保守的结构化去重辅助：比较冻结 rules、可解析 method.algorithm 和目标/参考等输入角色，忽略标题、ticker、记录 ID 与创建时间；数字/显式参数从 family 签名抽象，完整取值保留到 variant 签名。数据内容身份、样本角色和区间另有 input 签名。改名不成为新机制，参数改变属于同族变体，换产品或新数据属于复现候选，多来源始终只计算一次轮次。未解析文本与方法/数据缺项会显示比较局限。`mechanism_identity`、`novelty_claim`、`novelty_evidence_refs` 及 `duplicate_of`/`variant_of`/`replication_of` 可保存声明与可追溯引用；它们不能自证科学独立。独有结构签名仍为 `UNKNOWN_NOVELTY` 或 `DECLARED_UNVERIFIED`，`mechanism_family_count` 只数结构族，科学独立机制数保持 null。已有封存原件不改，只重建保守投影。

## 网页契约

`latest.json` 指向不可变 `snapshots/<id>/manifest.json` 与 `catalog.json`，`history.json` 提供旧快照。`catalog` 包含轻量节点/边、全历史摘要搜索、200项节点分片索引、产品、复核批次、异常与按需详情 URL。详情在 `objects/<content_hash>.json`；允许公开的附件在 `evidence/`。原件哈希和真实提交时间保留。新记录只增加投影，不修改 `web/src`。

生成顺序：不可变对象→catalog与manifest→逐项回读hash→history→原子latest。中断保留旧latest；重新发布补投影，不重做研究。相同原档、as_of 与生成器版本产生相同快照。as_of同时过滤信息可得与实际提交时间；未来产品、修订、反馈采用不能进入旧快照。生产空数据就是空页面，合成测试记录不会回退进生产。

归档仅声称已许可的精确原件与显式附件恢复；受限上游数据不包含，不能声称已备份。新目录恢复回读每个hash；`scientific_reproduction=NOT_RUN` 直到另行执行实际研究复算。公开发布也必须由外层工具实际推送并回读后单独确认，生成 JSON 不等于已上线。
