# 首版交付与剩余验收

公开研究树已实际打开，存储与网页等范围的工程、真实资料研究、公开发布及限定范围远端恢复已有证据。续接审计发现正式经济复核执行链仍有实现缺口；完整目标继续，不将这些缺口仅归为等待自然窗口。

- 网站：https://he1met.github.io/research-tree-lab/
- 源码：https://github.com/He1met/research-tree-lab
- 首批已实证远端恢复包：https://github.com/He1met/research-tree-lab/releases/tag/research-bootstrap-v1
- 增量已发布包（下载恢复未验）：https://github.com/He1met/research-tree-lab/releases/tag/research-increment-20260923-v1

| 维度 | 已有真实证据 | 尚不能据此声称 |
|---|---|---|
| 工程 | 首版54双浏览器检查；前两批维护88/143后端与24参考检查保留。第三维护已独立批准安装单BTC成交流式解码和公开字段兼容，190后端/24参考通过，源码c1aa9e50635b。 | 正式经济链仍有实现缺口；conditional-review层仅在隔离开发中，来源完整性与有事件经济状态迁移未交付。 |
| 真实研究 | 官方资金费文件核验、独立会话机制调查和成本反证；另实际完成成交/K线核验和双腿资金费成本诊断；87a772维护发布所用冻结范围为5轮、39记录、2封存计划，原手动复核2/2；后续任务追加不计入此快照。 | 数据覆盖不完整，费率汇总不是净收益，两个计划尚无未来经济结果。 |
| 公开发布 | 最新87a7725123ed快照：39记录、5轮、72个HTTP资源hash通过；CI源码9a5259b和Pages发布96639b1成功。此前27c878快照已有实际浏览器核对。 | 最新视觉回读PENDING_MAC_LOCKED，不能沿用前一快照视觉证据；本次复用39条原件与前端壳，新增研究0条，为手动维护发布。 |
| 归档与恢复 | 首批26记录/46文件远端下载、新目录恢复与派生复算通过。增量9新增/14闭包/35文件已发布，服务器digest一致；补充4新增/15闭包/36文件本机新目录恢复通过。三包本机并集覆盖冻结39条。 | 增量下载受Chrome及Browser策略阻塞，远端恢复未验；Mac锁定，补充包未上传。上游受限原始行情和未许可脚本仍LOCAL_ONLY，本机并集不等于全量远端恢复。 |
| 原生任务 | 四项ACTIVE；首个带自动化任务头的研究任务已完成并新增12记录。第二任务于2026-09-22 20:06:16 UTC启动，观察时仍active；启动观察2、完成观察1。 | 第二次启动不算第二次完成；调度事件身份仍UNKNOWN，严格自然计数0。实际下一触发和原生时区未暴露，宿主读数不能代证。 |
| 自然与经济验收 | 四业务任务负责接续，本任务另设两小时heartbeat核验。 | feedback真实后继采用已核实；两个严格自然研究时点、自然日复核及合法未来路径仍WAITING_NATURAL_OUTCOME。 |

当前权限是明确弱隔离：程序可拒绝越权角色和检测原档变化，但同用户full-access进程能够绕过入口。未改全局权限，不接账户、不下单。

原方案的未来评价终点是2026-09-24 00:06 UTC（上海08:06）；只有原窗口已经到达且合法数据/成本完整才允许最终评价。其他有意义方向继续，不把单方向等待变成全局锁。自然运行身份、窗口和许可缺口均不能用手动数据补造。

逐项清单：`ACCEPTANCE_STATUS.md` / `acceptance.json`。关键证据：`INDEPENDENT_REVIEW.md`、`FRONTEND_VERIFICATION.md`、`current-publication.json`、`publication-maintenance-trade-20260923.json`、`archive-upload-recovery-20260923.json`、`archive-supplement-20260923.json`、`remote-restore.json`、`second-native-research-observation.json`、`real-append-c05.json`、`stable-root-worktree-check.json`、`frequency-preservation.json`。第三维护见 `../review/continuation-audit/trade-public-source-receipt.json` 与 `../review/continuation-audit/trade-public-integration-tests.json`；原native上传失败回执保留历史。原件与完整本机回执保存在安装配置指向的稳定根。

当前需要用户解锁Mac，之后才能用原生文件选择器上传补充包并进行新快照视觉回读；Browser下载限制不绕过。普通研究的下一动作由现有官方原生任务和本任务接续承担，无需用户发送“继续”。只有实质变化、完成、失败或必要用户动作才通知。
