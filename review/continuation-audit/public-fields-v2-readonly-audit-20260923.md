# 第二研究新增字段的只读归档诊断

状态：READ_ONLY_DIAGNOSIS_NO_COMPATIBILITY_APPROVAL。只比较当前固定程序与真实已封存原件，未修改白名单、源码、共享索引、原件或已有归档，未导出或发布新包。

严格只读加载49条记录，无异常；9条新增公开原件均与第二研究完成回执hash相同，已有关系契约通过。5条投影与原件完整dict相同；以下4条仅省略未列白名单字段，所有实际投影值保持原值。9条原件全量公开扫描通过，不等于对任意附件的许可或完备性认证。机器证据见同名JSON。

| 原件 | 被省略字段及当前含义 | 隐私与关系边界 |
|---|---|---|
| decision-entry-confirmation-boundary-20260923 | comparison_set：immediate、confirmed、delayed_unconditional、wait四候选；feedback_disposition：采用一般缺数/暴露边界及原review/feedback引用；selected_plan_ref：null | 无新方案被选中；嵌套引用均已在input_record_refs。内容是作者说明，无原行情行或账户数据。未来非null选中方案和新增嵌套引用尚无专门关系检查。 |
| m-btc-entry-confirmation-component-20260923@1 | protocol_refs：固定方案protocol.json与分析前修订protocol_amendment_before_analysis.json的两个bundle引用 | 引用本身不是私人绝对路径；两附件存在、manifest字节吻合、扫描通过，但没有任何同bundle原件将其列入public_attachments。只能保留引用，不能顺带导出附件。 |
| run-boundary-sensitivity-20260923@attempt-1 | method_ref：m-minute-boundary-conditional-envelope-20260923@1 | 实际目标method存在、PUBLIC、可得与提交时点不晚于run；当前semantic_refs不追踪method_ref，自动归档闭包不含目标method。 |
| run-btc-entry-confirmation-20260923@attempt-1 | method_ref：m-btc-entry-confirmation-component-20260923@1 | 同上。补字段可以恢复run原件全部字节，但不能单独证明完整方法依赖恢复。 |

最小兼容候选是仅向decision加入上述3字段、method加入protocol_refs、run加入method_ref；不得扩大COMMON_FIELDS、放开未知字段、改变许可门、扫描器或public_attachments。候选尚未实施或批准。对这些已封存4原件可先验证精确字节兼容；如果要宣称通用方法闭包完整，run.method_ref等关系语义需单独明确并审查，不能把自由文本引用当作已验证依赖。当前缺失protocol/code附件的公开恢复边界继续保留，不能改写旧disclosure补授权。

必要验证：9原件字段值和hash；4受影响项及显式所需引用闭包的隔离export/inspect/新目录restore；未知字段与export_fields收窄；新增嵌套字段中的私人路径/token；方法缺失、错误类型、未来时点；protocol引用与附件白名单分离；旧快照/原件/归档不变。上述修复验证未在本审计执行，不记作通过。

当前已安装public.py SHA256为514263bb4038d7d1b1548f31ba9d3d00d67c0f0410990456fc9f02e85e9fd063，审计前后相同。此文件已被隔离conditional方法身份固定；后续若改动，必须重新绑定组合源码/方法身份并经独立审查后安装，不能在本轮私自更换。

本审计读取的最新发布回执是f7feb8b441e6361d6dc1d31535b9787dbe0703dd43a553b1711c075fc6adc53c：48条公开记录、7轮、85资源HTTP核验和实际浏览器回读。这是引用publisher回执，审计没有自行进行远端回读。既有26条远端恢复、其余增量归档的本机/上传/远端下载状态各自保持，不因本文升级。
