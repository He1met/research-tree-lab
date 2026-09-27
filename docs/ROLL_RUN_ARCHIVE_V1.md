# Roll run 精确归档兼容 v1

本次仅在 archive.py 为 run-roll-scale-20260927@attempt-1 的固定原件增加精确归档许可。省略的 verification 是作者检查说明：alternate_formulas_and_pairs 为 PASS、independent_audit 为 false、synthetic_author_checks 为整数 13。它不证明经济结果、独立科学复核或自然验收，维护独审也不会将原件 independent_audit 改成 true。

许可要求固定 record_type/run_id/attempt_id、完整原件 SHA-256、仅 verification 一个额外字段、闭合三键对象与精确值/类型；布尔值不能充当检查次数，0 不能充当 false。公共许可必须为 PUBLIC/OWN_ANALYSIS 且未设置 export_fields。基础投影一致性、递归扫描、旧 numeraire/calendar 固定许可、inspect 重验许可和 canonical 原始字节检查均保留。没有调用者 hash 许可入口，不接受未知 verification。

19 项针对性工程测试通过，包括所有原件标量逐项变异、字段/类型/布尔/值/身份/许可攻击、9 种重算 manifest 与文件 hash 的 ZIP 攻击和重复键。已只读复验 27 个现有归档，字节 hash 不变。将真实 Store 的 bundle 复制到临时目录后执行 export→inspect→restore，闭包 33 条、89 文件，目标原件字节完全一致，verification 保留原值。174 原件及 1320 个生产 bundle 文件、公开投影/图均未变；临时副本及输出已清理。

复验命令（项目根仅作只读输入）：

```sh
python3 -m unittest discover -s tests -p 'test_archive*.py' -v
python3 -m unittest discover -s tests -p 'test_public_round_archive.py' -v
python3 tests/replay_archive_roll_run_readonly.py --project-root "$RESEARCH_PROJECT_ROOT"
```

测试夹具是已审作者原件，只供隔离工程验证，生产不读取。精确交付文件及哈希见候选清单。旧16/formal19、public.py、schema、前端、评价和原件均不改。verification 仍不进入公开投影；本机工程恢复不等于正式补归档或远端备份。生产仍待独审和安装；正式补归档、上传、回读由原生 publisher 执行，不重跑研究。
