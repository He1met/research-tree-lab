# 第四批条件复核接续层独立复验

结论：`PASS_SCOPED_ENGINEERING_REVIEW`。冻结模块 `c2ad6dd18d99ee48c6d9360307153709071bafe6f4a472b36c563247fb6518b5` 的本批已知阻断均已修复，独立攻击复验未发现未解决的实质缺陷。批准仅绑定本报告的精确七个新增文件、组合 source hash 与 CPython 3.9.6 方法身份，不覆盖另一隔离工作树的第五批 public/contracts 修改。此结论不表示已安装、已生成生产 review、自然运行或取得经济结果。

- 组合 `source_hash`：`553a5cf1dce6f738745e1ea85d701e00c32c8876e57f17ade4ddc35c24b5197d`。
- 完整 16 文件方法身份：`a1f6f384e885176dbc1680ca4b720ec13c96e2361b84b3f4512ff721cd0c88ae`，CPython 3.9.6。
- 精确交付文件、逐件 SHA、完整方法 source/runtime 映射见 [机器收据](conditional-source-receipt.json)。

## 原问题与复验

保留 [初始失败证据](conditional-findings-initial.json)，不把原失败版本改写成通过。修复版独立运行作者 42 项定向测试通过（11.439 秒）；另外运行 [独立攻击脚本](check_conditional_review_independent.py) 的 13 组断言，全部通过，详见 [攻击回执](conditional-probes-independent-receipt.json)。脚本借用作者工厂创建临时计划和合成数据，但攻击改动与断言独立编写。

| 问题或边界 | 独立结果 |
| --- | --- |
| P1：中间前驱丢弃旧事件并从空状态自洽复算 | 后继明确失败，保留坏 latest 引用；另一计划继续处置。不能退回空状态或跳过坏项。 |
| 每一历史跳的实际 latest、同刻多个候选、双 opening hash | 自洽伪造跳祖先仍拒绝；同刻候选拒绝歧义；完整链重放保留公开与私有两个 hash 域。 |
| 有界整链、循环、缓存与限额 | 深度与循环攻击失败关闭；作者定向测试另覆盖节点、缓存字节与协作时间限额。没有截断祖先后返回成功。 |
| P2：恢复 outbox 自行重算 hash 后扩大公开附件 | 对 review、review_batch、feedback 分别追加 PRIVATE，均拒绝；不改保留原件、不另导出。 |
| 恢复 METHOD、SOURCE、完整计划清单漂移 | 即使重新封装 content hash 仍拒绝。已提交原件重试保持原时钟和清单；晚新增计划不进入旧批次，时钟倒退拒绝。 |
| P2：历史 cutoff 把已生效 unknown 重置成 0 | 私有历史 kernel 可为 NOT_YET_EFFECTIVE；公开保持 WAITING_DATA、HISTORICAL_PRE_EFFECTIVE_INPUTS_ONLY、库存 null。 |
| 孤立旧事件伪装已评价至很晚 cutoff | 正式 actually_evaluated_market_cutoff 恒 null；条件计算 cutoff 与观察到的最大事件时间分列。 |
| 显式更正与私有/公开契约 | 合法更正及后继通过；私有更正与真实父项/公开契约不一致拒绝。 |
| 更正后的实际公开边界 | 实际生成 snapshot，并分别从更正 batch、review、feedback 导出归档与 inspect；均有允许 SOURCE，无 PRIVATE、价格 canary、私有原因或受排除源码附件。 |
| 精确 waiting 桥接 | d21 完整身份正例通过；改变 runtime 不能以相同 version 标签获准。旧 legacy 仍仅两件原 canonical hash。 |

来源必须从已提交 dataset 取角色、产品、bytes/hash、acquired/available/commit 时间；每次沿历史链重新核对原始 bytes 与 decoder 结果。不能传任意 events、mark、sequence 或 complete 标志替代。42 项测试覆盖登记错位、来源 bytes 改坏、同 ID 改来源、迟到补数、坏 latest、物理 manifest 损坏、未知计划逐项失败、源文件复验及中断恢复。全链安全限额是保守拒绝上限；180 秒为协作限额，128 MB 为 canonical 缓存预算，均不是进程硬实时或峰值 RSS 承诺。

根代理的 [集成回执](conditional-integration-tests.json) 另记录完整后端 232 项和规范参考 24 项通过；本报告将其标为根代理执行证据，不混为本独立代理重跑全套。

## 真实文件的独立核对

[只读复跑脚本](check_conditional_real_input_independent.py) 用当前冻结模块的 `decode_sources` 解析已登记历史 tick；显式阻止 `evaluate` 被调用。实际完整读取 4,969,733 行、295,527,908 个 CSV bytes，CRC、展开 SHA、同一源 FD 前后 SHA 均通过，窗口保留 112 条，全部 sequence 为 null。12.538 秒。dataset canonical bytes/metadata 及原始对象 inode、size、mtime 均未改变。见 [独立真实回执](conditional-real-input-independent.json)。

该文件是 UTC+8 的历史日分区，不是两份原计划未来入场窗口的经济证据。回执没有保存事件、价格或私人路径。登记的 URL 和 acquired_at 仍是登记声明，不因此升级为独立官方认证。覆盖仍 UNKNOWN，data_complete 仍 false；没有运行计划/kernel 评价，没有生产/outbox/native 写入。

## 方法附件与部署边界

完整 16 件本机源码逐 hash 绑定。公开精确允许 METHOD 与 15 件 SOURCE；唯一排除 `SOURCE/researchlib/public.py`，固定 SHA `514263bb4038d7d1b1548f31ba9d3d00d67c0f0410990456fc9f02e85e9fd063`。它仍保存在同 bundle 本机附件，METHOD 明示扫描器自身路径正则误报的原因、该字节对应的基线 Git URL，以及 `self_contained_method_restore=false`。没有删依赖、编码规避、放宽 scanner 或公开 PRIVATE。七件候选交付文件通过原 public_guard，零拒绝。

可将本批保留为精确工程验收后暂不安装。若首次部署时并入第五批，应先重新审查组合：完整依赖 identity、public.py 唯一排除 hash/公开定位、waiting 精确历史身份验证、实际公开归档与新 source hash 都必须重算并复验。本回执不能直接批准变更后的源码，也不需要为从未部署/未产生记录的第四批虚构生产迁移。

## 尚未关闭的三层能力

| 层次 | 当前能力与下一最小范围 |
| --- | --- |
| 已实现的受限工程层 | 两类文件严格解码；注册原件/bytes/时点绑定；固定两计划的私有条件数学；全前驱链与显式更正；完整批次处置；只新增 outbox、原时钟恢复；公开摘要及附件边界。正式指标全 null、data_complete=false、评价游标 null。 |
| METHOD_IMPLEMENTATION_REQUIRED | 尚无可将来源证据判定为正式 coverage 的验证器和门禁；没有精确结算 mark/完整 mark 路径的接入；没有通过完整证据后输出正式经济指标及 FINAL/NOT_TRIGGERED 的分支。现有 12 个冻结成本情景可在私有 kernel 复算，但正式成本/净收益投影仍未实现，不能从传入布尔值获准。下一步须分别实现对应输入契约、证据判断和正式评价门禁，不能靠等待未来日期修复源码缺口。 |
| INPUT_CAPABILITY_UNVERIFIED | 官方来源/取得时点的独立证明、事件无遗漏边界、同毫秒成交排序、精确 funding mark 和完整 mark 路径、相关成本证据仍未获证。文件完整解码不证明市场事件完整；官方不保证无遗漏也不等于已证明缺行。缺 mark 样本不等于所有渠道都不存在。 |
| WAITING_WINDOW / WAITING_NATURAL_OUTCOME | 审核信息时点为 2026-09-22T21:02Z，两原计划从 2026-09-23T00:05Z 起生效、终点 2026-09-24T00:06Z 尚在未来；真实未来路径与自然 review 需另有实际证据。合成跨日测试和手工解码均不计自然验收。 |

因此 B04 仍为 IMPLEMENTATION_REQUIRED，B05/B07 仍为 ENGINEERING_PARTIAL。原计划当时未解析的方法标签不因后来新增模块而被追溯改成可执行。完整项目验收、正式经济结果和自然触发均未关闭。
