# 正式评价候选开发中独立早审

状态：**CHANGES_REQUIRED_UNFROZEN**。这是失败与修复进度记录，不是冻结版本批准，不授权安装、提交正式复核或发布。

## 证据身份与执行范围

候选为 `research-formal-review-v1` 隔离工作树。审查覆盖 Store-only 输入、方法/前驱绑定、旧 7db 迁移、公开祖先、预算，以及最终复用的真实投影/归档。未修改候选源码、生产 Store/data、安装、原生任务或共享索引；没有网络或交易操作。

早先即时探针确已运行并将结果发送作者/root，但当时作者正在持续修改，**未同步捕获准确源码 hash**。本报告不会将后来的 hash 倒填到早先失败。那些结果归为未冻结历史实证，保留具体操作和工具执行片段标识；不能据此声称能还原当时完整源码。

随后新增 `probe_formal_early_20260923.py`：只读取固定候选源码和已跟踪测试/原计划夹具，逐字节复制到临时目录，从临时副本运行。测试 Store 与行情均为一次性合成材料；既有两份计划只作为冻结规则夹具，不产生真实科学结果。脚本只写临时目录，结果输出 stdout。完整机器输出为 `formal-early-captured-probes-20260923.json`。

本次固定捕获副本的关键 hash：

| 文件 | SHA-256 |
|---|---|
| `researchlib/formal_review.py` | `b47b27f6bdf4b29245da981c59ffe64c12ae8edd18225ee682ef8ad9fc4316e6` |
| `researchlib/formal_funding.py` | `920f3348471eda846d2e28fa17398acd6174703749ce6a5455557d0e52aeae66` |
| `scripts/prepare_formal_review.py` | `6e0da7fbd2e06c490f5c6cc3280d149a2842d5554f98f0d409732f5c49b8a9ad` |
| 捕获文件 hash map | `a2b22b051db80d5e5af7412ed2b6d8b5ffd4bf9096d37c055a9362bffbe946be` |

捕获与执行结束之间，所捕获源文件无漂移。此 hash map 仅绑定该诊断副本，不是 `publish.py --source-hash` 的部署身份；作者随后仍可继续修复。不得把本文当当前源码已通过。

## 发现与复跑状态

### EARLY-01 / P1：旧许可漂移通过新 review 间接公开 PRIVATE

在临时库生成正常旧 7db bundle，仅把其中 feedback 的 `disclosure.public_attachments` 追加同 bundle 的 PRIVATE 计算文件；其余 METHOD、SOURCE、kernel 和前驱不变。Store 通用契约接受，最初新 formal 接续仍返回 WAITING_DATA。提交新 review 后，实际 `export_backup(新 review 单根)` 的语义祖先闭包含旧 PRIVATE 成员及合成价格 canary。

这不是“指标仍 null 所以安全”：新公开根引用的祖先已经泄露完整私有输入。通用 Store 的声明许可不是新 evaluator 可默认信任的程序派生权限。

固定副本复跑 `old_private_permission` 已在准备前以 `PUBLIC_ANCESTOR_POLICY_REJECTED` 整批拒绝，说明**原始直接变体的定向修复有效**。但 EARLY-02 仍绕过，P1 尚未关闭。

### EARLY-02 / P1：未知方法标签跳过安全预检，失败产物仍泄露

在同一旧 bundle 的两份 review 上把 `evaluator_version` 都改为 `UNKNOWN_METHOD`，再对一份 feedback 追加上述 PRIVATE 许可。全部改为未知是为了避免另一份受识别 review 触发同 bundle 的安全检查。

最初新增预检按可变 evaluator 字符串选择要检查的 bundle，因此跳过未知方法。新 formal 虽然产生 TECHNICAL_FAILURE，仍沿 `previous_review_ref` 引用危险祖先。固定副本复跑 `old_private_permission_unknown_method` 确认：新失败 review 可提交；**实际 archive 和 snapshot 都含价格 canary，archive 有旧 PRIVATE 成员**。

必须先独立核验语义祖先的公开许可与派生公开内容。无法证明祖先公开安全时，不得生成会引用它的公开失败产物。不能由可篡改的 `evaluator_version`、改名或身份失败决定跳过安全检查；未知普通规则/状态仍可按计划单独失败，但不能代替公开安全的整批阻断。作者已收到该复现，修复尚待冻结后另验。

### EARLY-03 / P2：公开 provenance 与派生字段不完整绑定

最初将新 formal review 的 `provenance.method_code_sha256` 改为全零，其余原件不变，受控提交后下一轮仍接受。随后逐字段矩阵还确认 summary/limitations、feedback.supported_facts、batch.coverage/trigger_origin/complete 可漂移；旧 7db 的自然身份也未被新路径完整核对。

固定副本的 15 项定向矩阵中：方法哈希、自然标志、native 身份、触发来源、方法时间、data_complete、metrics、coverage 篡改被隔离为对应计划 TECHNICAL_FAILURE，另一计划继续；summary、limitations、feedback 独立内容/身份和 batch 派生值篡改被整批拒绝。反馈测试先解除 Python 共享对象别名，避免把“改反馈”误测成同时改 review。

这些是**所列变体已修**，不是全字段安全已证明。预检曾在坏 provenance 上 `continue`，可能跳过反馈公开内容；未知方法/未知字段也不能默认信任。最终应在真实原 prepared_at 可见集、精确源码/方法下重构完整期望，或做等价完整字段检查。仅补某一个 hash 不足以结案。

### EARLY-04 / P2：新旧上下文合计缓存预算漏检

最初新 formal 与旧 7db 共用 deadline，visiting 也合并；但联合 `encoded_bytes` 只在旧域返回时检查，之后新域逐层 reserve 可使合计超过共同限额。临时链 7db c1 → formal a/b/c，将**测试内存阈值**降为 180000 后，验证仍接受新域 169933 + 旧域 29926 = 199859。未改变生产阈值或扩大上限。

固定副本再测，基线合计 200141，测试阈值 185178，已以 `COMBINED_HISTORY_RESOURCE_LIMIT_EXCEEDED` 拒绝，定向修复有效。最终仍需覆盖跨域总深度/节点、decode 缓存、一次顶层 deadline，以及坏 latest 拒绝后保留原引用而非归零；本文没有将单个预算探针扩称全部资源边界通过。

### EARLY-05 / P2：FINAL 复用内部正确，公开闭包不完整

使用测试中显式内存替换的合成可信 resolver，产生两份 FINAL，再准备下一批复用。最初没有新 review：原 batch 记 `reused=2, missing=[]`，实际 catalog 却为 `reviewed=0, missing=两计划, review_refs=[]`；批次单根 archive 也未带入两份原 FINAL。

root 随后选择新增明确的承载 review，不改旧 16 个依赖源码。固定副本中该修复已使实际 snapshot 显示 `reviewed=2, missing=[]`，原记录明确 `new_economic_computations=0`。但 `export_backup(复用 batch 单根)` 仍归档 **0/2 原 FINAL**：批次本身没有被通用语义闭包识别的 review 引用，仅有 items 内部字符串。**网页计数修复有效，完整归档问题仍未关闭。**

可在新 batch 使用已有受支持的显式引用字段绑定处置 review，或采取等价兼容方式；不能仅验证新 review 单根或仅看内部 coverage。承载分支还须严格区分当前确认时间与原经济评价时点，保留原 cutoff/result/input/method 身份、两域 opening hash，不将原 kernel 改写为一次新的状态推进，不重复经济计算或交易计数。连续承载、混合批次、晚到显式更正与坏 latest 均需冻结后另验。

## 复跑方法与未完范围

```sh
python3 -B review/continuation-audit/probe_formal_early_20260923.py --candidate-root "$FORMAL_CANDIDATE_ROOT"
```

脚本针对届时实际字节重新抓取 hash；不同输出不是旧失败被覆盖。它不执行 CLI 提交，不导入生产 Store，不授予任何真实来源能力。FINAL 仅通过测试显式替换内部 resolver 构造，不能被当成生产入口可取得 FINAL 的证明。

最终批准须在作者完整冻结后另写新报告/回执，至少包括：未知/改名方法的公开祖先阻断、原 private 改名及直接公开文本组合、所有正式公开派生字段、历史 latest/双时点/双 opening、跨域共同预算、明确承载复用与更正、真实 generic snapshot 和各根 archive、恢复原完整 outbox 字节、旧 16-source/7db 身份不变，以及精确交付列表和整体部署源码 hash。本文所有早期失败与中途修复记录必须保留。
