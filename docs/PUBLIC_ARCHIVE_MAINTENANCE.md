# 公开归档字段兼容维护提案

状态：PROPOSED_INDEPENDENT_MAINTENANCE_REQUIRED。发现于2026-09-23发布；本轮没有修改公共schema、导出白名单、评价器或安装批准hash。

固定完整归档器要求公开副本保留原件全部字段。已提交的 `r-feedback-input-completeness-20260923` 使用 `source_review_refs`，当前round公开白名单没有该字段，因而该轮、对应run及两条反馈采用decision的完整归档闭包被拒绝。网页投影省略该字段，但parent_round_id、derived_from_feedback_refs、additional_source_refs、input_record_refs与decision引用均保留，39条公开投影关系验证通过。

拟议维护版本 `public-round-review-reference-compatibility-v1`：先独立审查该字段的契约、引用语义与公开许可；必要时作最小兼容变更，并验证旧snapshot可读、精确原件hash不变、引用闭包及同输入确定性、秘密/私人路径/嵌套包拒绝。通过审查后另更新固定安装批准身份。不得删改原件字段、放松扫描或用摘要冒充完整备份。

归档待补的4条、可归档子集与上传草稿见 [归档回执](archive-increment-20260923.json)。新方法脚本与受限上游未获公开附件授权的边界另保留；兼容修复不自动扩大许可。权限恢复后仅续传已生成归档包，不重做研究。
