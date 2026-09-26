# 日历原件精确归档兼容 v1

现有公开投影省略两条已封存日历原件的 round_id，以及决定中的 feedback_dispositions，导致归档不能声称原件完整备份。本维护只在 archive.py 增加两条源码内固定身份许可，不改变投影、方法、原件或导航。

完整原件已审阅：round_id 指向已有股票时段轮次，且重复已公开 input_record_refs 的相同引用；两条 feedback_dispositions 记述既有多/空反馈用于资料角色、时间与未知成本边界，明确等待经济输入。它们不是经济复核或新后继执行证明。固定的 feedback_ref/source_review_ref 也在公开 input_record_refs 中；真实临时闭包验证已覆盖这些目标及 existing_successor_round_id。

许可同时要求 PUBLIC / OWN_ANALYSIS、没有显式 export_fields、基础投影字段值一致、精确额外字段集合、固定类型和身份、闭合的反馈数组与对象结构、固定值，以及完整 canonical 原件 SHA-256。所有内容仍经过递归公开扫描。调用者不能提供许可 hash，字节或内容改变不能借此放行。inspect 重新执行同一许可检查，并要求受审例外的实际存档原件字节等于 canonical 字节，拒绝攻击者重算文件、原件和 manifest 摘要后的空白/重复键变异。旧 numeraire 许可不变，15 个现存归档均通过只读 inspect。

作者验证：9 项 archive 测试及 6 项既有公开轮次归档测试通过。新测试逐个变异两原件的全部标量叶，另含闭合结构、显式导出字段、调用者 hash、16 种伪造存档检验。真实原件临时 export→inspect→restore 的闭包为 20 条记录、43 个文件；两个原件逐字节一致。105 原件、770 bundle 文件、当前投影和图均未改变。临时输出已清理；不是正式补归档、远端上传或自然运行验收。

复验（在候选根目录；项目根只作只读输入）：

```sh
python3 -m unittest discover -s tests -p 'test_archive*.py' -v
python3 -m unittest discover -s tests -p 'test_public_round_archive.py' -v
python3 tests/replay_archive_calendar_readonly.py --project-root "$RESEARCH_PROJECT_ROOT"
```

投影仍省略上述字段，feedback_dispositions 不新增结构化导航。运行/证据的既有 input_record_refs 导航规则保持，不能据此宣称决定或反馈的完整导航语义已扩展。改变投影涉及旧方法源，应另案审批；本维护不顺带处理。

精确安装文件在候选 manifest 的 delivery_files。测试夹具是固定已审作者原件，只供隔离工程验证；生产不读取它们。归档所含范围仍为公开原件和明确许可附件；不包含受限上游原文、本机操作文件或完整行情数据。正式归档、上传和回读仍由原生发布任务执行。
