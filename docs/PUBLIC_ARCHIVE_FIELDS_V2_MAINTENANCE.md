# 新增研究字段的精确公开归档兼容提案

状态：PROPOSED_INDEPENDENT_MAINTENANCE_REQUIRED。发现于2026-09-23第二次原生发布观察。本次未修改公共schema、公开白名单、评价器、源码或安装批准hash。

固定公开投影已生成48条记录，导出字段的值与原件相同。固定完整归档器要求保留原件全部字段，因下列字段未列入类型白名单而拒绝4条原件：

| 原件 | 未列白名单字段 |
|---|---|
| decision-entry-confirmation-boundary-20260923 | comparison_set、feedback_disposition、selected_plan_ref |
| m-btc-entry-confirmation-component-20260923@1 | protocol_refs |
| run-btc-entry-confirmation-20260923@attempt-1 | method_ref |
| run-boundary-sensitivity-20260923@attempt-1 | method_ref |

其余5条新增记录已通过固定归档程序，连同引用闭包共21条、46文件，并在全新本机目录恢复验证。4条拒收原件继续保留，网页中的允许字段投影不等于完整备份。准确范围见 [本次归档回执](archive-increment-20260923-v2.json)。

拟议维护版本 `public-research-reference-fields-compatibility-v2` 需独立检查上述字段的引用语义、schema验证及公开许可，特别是 `protocol_refs` 是否只可引用本机附件。检查通过后才考虑最小兼容变更及安装批准身份更新。需验证精确原件hash不变、旧快照兼容、引用闭包、同输入确定性，以及秘密、私人路径、未许可附件和嵌套包继续拒绝。

不得删除原件字段、把公开摘要称为完整原件，或以本维护提案授权额外附件。已有 `round.source_review_refs` 维护属于此前已安装版本，不重复提议或回滚。上传和远端下载仍分别依赖受支持能力；本机恢复不算远端恢复或自然调度。
