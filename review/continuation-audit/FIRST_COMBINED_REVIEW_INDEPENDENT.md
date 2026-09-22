# 首次条件复核与公开字段组合独立验收

结论：`PASS_SCOPED_FIRST_COMBINED_ENGINEERING_REVIEW`。本批未发现未解决的实质缺陷；初始 helper 路径 P2 已修复并独立复验。批准绑定 [机器收据](first-combined-source-receipt.json) 中精确 23 文件及完整源码 hash，不表示本独立代理已安装、提交生产 review、发布或完成自然/经济验收。

- 总体 `source_hash`：`eca93fe70146b1c6962842cd6b62dc8f66f89a47e8249017387202e1a6985277`。
- 条件模块：`2508392c524c19b4260f6d120d4f17f80bcd0d327b8daa483036130d12b56fd6`。
- CPython 3.9.6 的完整 16 文件方法身份：`7dbdd186fd04ddca07dc3bfa933f9a0fae1ce66e1f1d91447e0bbeff5332d3ce`。

## 方法桥接与第四批安全边界

旧 waiting `d21b004a…` 与新 waiting `7718ec0e…` 分别按完整 11 文件 source map、runtime、固定 METHOD 模板识别，并读取前驱同 bundle 的六件实际源码附件逐件比对。独立复验使用已安装旧源码真实产生的 METHOD/六附件作为对照，确认测试中的旧模板和旧 contracts 字节相等；没有将新 contracts 当作旧原件。其余五个依赖在旧 METHOD 中固定 hash，但未被旧 helper 附入 bundle；旧包仍不称自包含方法恢复包。

[独立桥接脚本](check_combined_waiting_bridge_independent.py) 的八组检查全部通过，包含 24 个源码缺件/改写案例、10 个 runtime/map/template/时间/evaluator 变体。正例在禁止 subprocess/network 的条件下桥接、提交临时 Store、恢复同批次并续接。另从第四批冻结工作树实际生成完整且自洽的 `a1f6f384…` conditional bundle，组合版明确拒绝；不是仅改一个 hash 标签来测试。见 [桥接回执](combined-waiting-bridge-independent.json)。

相对第四批已批准模块，AST 函数比较仅 `method_material` 与 `_previous_node` 有变化。独立运行组合 48 项定向测试通过（14.050 秒），再次运行此前 13 组攻击全部通过，见 [连续性与公开边界回执](combined-regression-independent.json)。中间丢前缀、跳过历史 latest、同刻歧义、循环/限额、普通接续清空状态、未明示更正、恢复披露名单漂移均拒绝；信息截止与行情 cutoff 分开，正式评价游标恒 null。合法更正后的实际 snapshot 与 batch/review/feedback 三根归档仍排除 PRIVATE、价格 canary、私有原因和唯一排除源码附件。

完整 16 件源码本机保留。公开依旧为 METHOD 加 15 件 SOURCE，唯一排除 `SOURCE/researchlib/public.py`，SHA `db4eb97c35a312277798605f76ac334dfd57bbc6fe3b1b6d718cd86f00d20dbd`。该字节与本地固定 Git ref `e65bb32e162ddc21b2513ee4edfd4d90829c5b5b` 相符；METHOD 使用 `git_source_locator`，明确不证明网络可访问。整合方须保留并实际归档该来源历史，不能指向旧字节或把本回执当远端发布证明。

## 类型字段与真实归档

两份字段源的固定提交 e65 已单独检查：只增加 decision 的 comparison_set/feedback_disposition/selected_plan_ref，method 的 protocol_refs，run 的顶层 method_ref。COMMON_FIELDS、scanner、许可、附件名单及 export_fields 收窄机制保持。run 顶层 method_ref 必须存在、可得时间不晚于 run、目标为 method；私有或不许可的方法阻止依赖公开。protocol_refs 只保留定位字符串，不授权附件或自动读取文件。

14 项字段测试独立通过。追加第三研究之前，独立实读当时 49 条原件、48 条公开原件：旧 39 条逐值不变、新 9 条精确，四个原受阻单根及新九条联合/全四十八条共六种归档恢复通过。两 run 单根均包含对应 method；protocol/raw/PRIVATE 未获新附件许可。266 个已提交 bundle 文件 hash 前后相同，见 [初次真实检查](public-fields-v2-real-independent.json)。

修复 helper 后，当前生产已增至 54 条、52 条可公开。固定历史诊断按原 48-public 范围拒绝，未生成成功回执；[该范围拒绝](combined-current-scope-refusal.json) 如实保留。随后按首次观察时点的实际 committed_at 选取旧 49 条，原样复制 266 个 bundle 文件，文件映射 SHA `1072220a990e088ef7e6a48b2e76da4740159bb76dd7bae75892f76890f3c1b8` 与初次检查精确相等，所有 canonical 记录和 metadata 与生产旧原件相等。修复 CLI 在该临时冻结副本上实际完成六种归档/恢复，见 [CLI 复验](combined-public-archive-cli-independent.json)。没有删新记录、改生产安装或把历史 49 当成当前总数。

批准范围限原九新增/四受阻原件和顶层 `run.method_ref`。第三研究若只把 method_ref 放在 `results` 中，本实现不会自动将其升级为语义引用闭包；本报告不外推第三研究单根归档能力。一般 decision 的选择语义与任意嵌套引用同样不在本次新增范围内。

## Helper P2 修复

[初始问题](public-fields-v2-findings-initial.json) 在原版本可复现：receipt 目录与允许根一起 resolve，会跟随目录 symlink 向外新增文件。修复版固定候选根、逐层目录 FD/NOFOLLOW、验证前 O_EXCL 预留并持有输出 FD。失败只清空自持 inode，不按可替换路径删除；既有文件、hardlink 和 symlink target 不被覆盖。

独立运行 15 项 helper 安全测试通过（0.027 秒），另 [独立 CLI 攻击](check_public_fields_helper_independent.py) 十案全部通过，包括原根目录 symlink、嵌套父 symlink、叶链接、已有文件/hardlink、traversal、验证中父/叶替换及验证失败，见 [回执](public-fields-helper-independent.json)。正常案例成功，非法入口均在读取证据前拒绝。可能留下空的新预留文件，但不会留下成功回执；这是明确诊断，不是 OS 级隔离承诺。

## 真实解码、剩余能力与整合

组合版另独立调用 registered `decode_sources`：完整 4,969,733 行、295,527,908 CSV bytes，CRC/展开 SHA/同 FD 前后 SHA 相符，112 条选择事件全部 sequence=null，12.677 秒。测试显式禁止调用 evaluate，未生成生产 review。见 [组合真实解码](combined-real-input-independent.json)。该历史 UTC+8 文件不是原计划未来路径；coverage UNKNOWN、data_complete=false，来源与取得时间仍是登记声明。

| 层次 | 本次达到的范围和未完成项 |
| --- | --- |
| 已实现受限工程 | 登记文件解码；固定两计划私有条件复算；精确旧/新 waiting 桥接；整链/更正/原时钟恢复；完整批次处置；安全新增 outbox；类型字段及允许附件归档。正式 actual 指标全 null，正式评价游标 null。 |
| METHOD_IMPLEMENTATION_REQUIRED | 独立来源/coverage 判断及正式门禁、精确结算 mark 和完整 mark 路径接入、证据完备时的正式经济指标与 FINAL/NOT_TRIGGERED 分支仍无实现。12 个冻结成本情景已有私有数学，不等于正式实际成本结果。 |
| INPUT_CAPABILITY_UNVERIFIED | 官方来源/取得时点独立证明、事件无遗漏边界、同毫秒顺序、精确 mark/全路径及相关成本证据仍未获证。文件解码完成不推导 source completeness。 |
| WAITING_WINDOW / WAITING_NATURAL_OUTCOME | 本次审核仍早于原 2026-09-23T00:05Z 生效和 2026-09-24T00:06Z 终点；未来路径及自然复核须另有实际证据。实施缺口不能归类为只需等日期。 |

B04 保留 IMPLEMENTATION_REQUIRED；B05/B07 保留 ENGINEERING_PARTIAL。原计划的历史 unresolved method 标签不被追溯改写。根代理的 [267 后端/24 参考集成回执](combined-integration-tests.json) 已核对并绑定，属于根执行证据，不冒称独立重跑全套。

整合仅复制机器收据列出的精确 23 文件，复核总体 source hash、完整方法/runtime 与逐文件 hash；保存第四候选和原失败/开发回执；确保 e65 来源历史可归档。当前生产没有用过 a1 conditional/outbox，无需制造其迁移。安装、真实业务提交、远端发布/恢复及自然验收由各自实际证据另行确认。本独立审查未改生产、native、安装或四份共享状态索引。
