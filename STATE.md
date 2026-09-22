# 当前检查点

状态：SCOPED_PUBLIC_DELIVERY_VERIFIED / FORWARD_EVALUATOR_IMPLEMENTATION_REQUIRED / WAITING_NATURAL_OUTCOME。正式项目唯一规范为 planning/current/，目标仍在接续，未宣称全表完成。

- 公开网页：https://he1met.github.io/research-tree-lab/ 。当前已实测 snapshot 为 429c7ab2a4f89a7512eb3357908352f4f65ad15ab4a881145fe52e02faaea7aa；56 个远端 HTTP 资源及浏览器实际页面核对通过，见 `docs/current-publication.json`。
- 稳定根见 `.local/installation.json`；原件在 `.local/store`，共享资料在 `.local/data`。已提交 27 条真实记录：3 轮研究、2 个封存方案、2 份独立复核、2 份反馈，以及首次公开证明等。首轮和公开回读均为官方应用手动安全试跑，非原生 Run now，非自然运行。
- 代码固定版本与审批 hash 在安装配置。浏览器 54 项、Python 工程 55 项、参考契约 24 项通过，上述测试对应首版范围；续接独立审计新增固定评价器实现缺口，详见 `review/continuation-audit/FORWARD_EVALUATOR_AUDIT.md`，维护已通过独立受限审查并合入当前源码；条件内核26测试、宿主时区7测试和全部后端88测试通过。官方适配/覆盖/正式旧状态迁移仍待实现，详见 `docs/FUNDING_FORWARD_KERNEL.md`。不能将通用账本或生效前状态器当成完整原规则评价器。
- 四业务原生任务已 ACTIVE 并回读。上海时区：发现 07:30/19:30，研究每小时 :05，日复核 08:15，发布每小时 :35。保留实际用户后续设置，不恢复默认。管理工具没有暴露调度器实际下一触发时间，仍为 UNKNOWN。
- 本任务每两小时有官方 heartbeat 继续剩余验收；它不替代四业务任务、不补跑旧时点。无变化保持安静，有实质变化再报告。
- GitHub Release `research-bootstrap-v1` 的 26 条当时记录、46 个公开文件已从远端下载到新目录恢复并实际复算，见 `docs/remote-restore.json`。第 27 条是后续新增发布证明，已经公开 Git/Pages；受限上游原始行情仍 LOCAL_ONLY，不冒充完整远端备份。
- 本轮维护回执为 `review/continuation-audit/maintenance-source-receipt.json`，组合源码 hash 绑定在安装配置。F09 已在两浏览器核对持续200快照跨36小时陈旧及刷新不续期，并补显示发布任务运行状态未知。宿主实测 Asia/Shanghai +08:00；原生任务自身时区未由管理工具暴露，不用宿主读数代证。
- 当前权限为弱隔离：角色约定与程序准入不等于 OS 只读挂载，发布核验唯一 remote 也不等于凭据本身只限本仓库。

下一动作：先补当前可完成的官方来源/覆盖验证、固定评价计算与正式旧状态迁移，经独立检查后版本化交付；同时收集至少两个不同官方自然研究时点、一轮自然日复核与真实反馈后继采用。两个旧 BTC 计划的当前必要数据未齐；原生效为 2026-09-23 00:05 UTC，原终点评价为 2026-09-24 00:06 UTC。日复核按原封存规则继续，窗口未到或路径/实际成本缺失保持等待，不填零、不重置跨日状态、不提前给最终收益。必要当前事实补齐后若需升级执行资格，按研究库约束另建版本，旧方案原件不改。

本文件仅是接续索引。完整 manifest、准确自然运行身份、独立复核版本及真实发布回执才是证据。逐项状态见 `docs/acceptance.json` 与 `docs/ACCEPTANCE_STATUS.md`。普通研究无需用户重复批准或发送“继续”。
