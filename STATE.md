# 当前检查点

状态：SCOPED_PUBLIC_DELIVERY_VERIFIED / FORWARD_EVALUATOR_IMPLEMENTATION_REQUIRED / WAITING_NATURAL_OUTCOME。正式项目唯一规范为 planning/current/，目标仍在接续，未宣称全表完成。

- 公开网页：https://he1met.github.io/research-tree-lab/ 。当前维护快照为 87a7725123ed070e2d489087b2edb1901eaccce338acb50beed2fe107be7acf7，39记录、5轮、72个远端HTTP资源hash核验通过；源码9a5259b的CI与发布96639b1的Pages成功。当前视觉回读为PENDING_MAC_LOCKED；最近实际视觉核对仍是27c878快照，不能混为同一次。见 `docs/current-publication.json` 与 `docs/publication-maintenance-trade-20260923.json`。
- 稳定根见 `.local/installation.json`；原件在 `.local/store`，共享资料在 `.local/data`。第三维护发布87a772快照所用冻结记录为39条：5轮研究、2个封存方案、2份独立复核、2份反馈，以及首次公开证明等。该数字仅对应发布回执时点，不是Store实时总数；第二任务后续追加须另作未发布增量核对。首轮和首次公开回读均为官方应用手动安全试跑，非原生 Run now，非自然运行。
- 代码固定版本与审批 hash 在安装配置。浏览器 54 项、Python 工程 55 项、参考契约 24 项通过，上述测试对应首版范围；续接独立审计新增固定评价器实现缺口，详见 `review/continuation-audit/FORWARD_EVALUATOR_AUDIT.md`，维护已通过独立受限审查并合入当前源码；条件内核26测试、宿主时区7测试和全部后端88测试通过。后续已独立批准单资金费文件解析和原空状态到等待处置outbox，143后端/24参考通过；实际来源完整性及有事件经济状态迁移仍待实现。详见 `docs/FUNDING_FORWARD_KERNEL.md`。不能将通用账本或生效前状态器当成完整原规则评价器。
- 四业务原生任务已 ACTIVE 并回读。上海时区：发现 07:30/19:30，研究每小时 :05，日复核 08:15，发布每小时 :35。保留实际用户后续设置，不恢复默认。管理工具没有暴露调度器实际下一触发时间，仍为 UNKNOWN。
- 本任务每两小时有官方 heartbeat 继续剩余验收；它不替代四业务任务、不补跑旧时点。无变化保持安静，有实质变化再报告。
- GitHub Release `research-bootstrap-v1` 的 26 条当时记录、46 个公开文件已从远端下载到新目录恢复并实际复算，见 `docs/remote-restore.json`。第 27 条是后续新增发布证明，已经公开 Git/Pages；受限上游原始行情仍 LOCAL_ONLY，不冒充完整远端备份。
- 首批维护回执为 `review/continuation-audit/maintenance-source-receipt.json`；当前维护源码hash为 c1aa9e50635b4591514dc17e2d5123f3742a6b4a7b6b90c9403f6f84bd043592，以安装配置与第三批独立审查回执为准。F09 已在两浏览器核对持续200快照跨36小时陈旧及刷新不续期，并补显示发布任务运行状态未知。宿主实测 Asia/Shanghai +08:00；原生任务自身时区未由管理工具暴露，不用宿主读数代证。
- 首次自动化研究任务已完成并追加12条，原27条哈希均未变；两份feedback合为一个实际后继。官方任务头/完成状态可见，但scheduler-event身份仍未知，原natural_trigger=null不改，严格自然计数仍0。见 `docs/first-native-research-completion.json`。新增12条在27c878快照中通过HTTP与实际浏览器回读，该次发布调度事件身份仍UNKNOWN。第二个研究任务于2026-09-22T20:06:16Z启动，观察时仍active；完成观察仍1、严格自然计数0，见 `docs/second-native-research-observation.json`。
- 第二批维护见 `review/continuation-audit/funding-review-source-receipt.json`，限单资金费文件解码和状态等待outbox。使用说明为 `docs/OKX_FUNDING_FILE.md` 与 `docs/FUNDING_WAITING_REVIEW.md`。
- 第三批维护已独立批准安装：单BTC成交文件流式解码与round.source_review_refs公开归档兼容；190后端/24参考检查通过，字段兼容工程缺项已关闭。见 `review/continuation-audit/trade-public-source-receipt.json` 与 `review/continuation-audit/trade-public-integration-tests.json`。来源完整性、有事件正式经济复核仍缺实现；conditional-review层仅在隔离开发中，不属于已交付能力。
- 当前权限为弱隔离：角色约定与程序准入不等于 OS 只读挂载，发布核验唯一 remote 也不等于凭据本身只限本仓库。

下一动作：待用户解锁Mac后，通过原生文件选择器上传已核验补充包并实际回读当前网页；新增包远端下载恢复保持未验，不能绕过Browser策略。继续补官方来源/覆盖验证和有事件的正式经济状态迁移，经独立检查后版本化交付；同时收集至少两个不同官方自然研究时点、一轮自然日复核；反馈真实后继已经核实。两个旧 BTC 计划的当前必要数据未齐；原生效为 2026-09-23 00:05 UTC，原终点评价为 2026-09-24 00:06 UTC。日复核按原封存规则继续，窗口未到或路径/实际成本缺失保持等待，不填零、不重置跨日状态、不提前给最终收益。必要当前事实补齐后若需升级执行资格，按研究库约束另建版本，旧方案原件不改。

本文件仅是接续索引。完整 manifest、准确自然运行身份、独立复核版本及真实发布回执才是证据。逐项状态见 `docs/acceptance.json` 与 `docs/ACCEPTANCE_STATUS.md`。普通研究无需用户重复批准或发送“继续”。

- 增量归档：Release `research-increment-20260923-v1` 已发布9条新增/14条引用闭包/35文件，服务器digest与本地附件一致；实际下载恢复未验，Chrome拦截及Browser策略拒绝均如实记录且未绕过，见 `docs/archive-upload-recovery-20260923.json`。另4条的补充包15条闭包/36文件已在本机新目录恢复通过，三包本机并集覆盖冻结39条；Mac锁定，补充包尚未上传，见 `docs/archive-supplement-20260923.json`。原native失败回执 `docs/publication-run-20260923-v1.json`、`docs/archive-increment-20260923.json` 保留历史，不改写为成功。
