# 第二研究公开字段兼容候选

状态：ISOLATED_CANDIDATE_NOT_INSTALLED。此worktree实际基线为3bac79f1fc0a32fa51bf03790a8079a0c958add9，使用第三批已安装源码，尚不含第四批 conditional-review。作者验证不代替后续独立审查、方法身份整合或安装批准。

第二研究的9条新增公开原件中，5条已可完整归档；另外4条的网页投影保留允许字段，但完整归档器因省略字段而拒收。本候选保留原件字节，不修改其封存内容、disclosure、已生成快照或旧归档。

两处语义范围：

1. `public.py` 仅扩展类型专属字段：decision 的 `comparison_set`、`feedback_disposition`、`selected_plan_ref`；method 的 `protocol_refs`；run 的 `method_ref`。`COMMON_FIELDS`、公开许可、synthetic门、扫描器、`export_fields`收窄与附件白名单均不改。当前decision的 `selected_plan_ref` 为null，嵌套review/feedback引用已由既有 `input_record_refs` 覆盖；本候选没有为一般decision新增选择或嵌套引用语义。
2. `contracts.py` 将非空 `run.method_ref` 纳入既有记录关系与归档闭包；缺失目标、信息时点晚于run沿用现有拒收，另明确要求目标类型为method。单独归档run现在会自动纳入对应方法原件。旧run没有该字段或为null的行为保持。私有或未许可方法会使公开闭包拒收，公开快照也会排除依赖不可公开方法的run。

`protocol_refs` 只是已封存bundle内的定位字符串，不作为record ID查找，也不授权附件读取或公开。真实两份protocol附件没有被任何同bundle原件列入 `disclosure.public_attachments`；补字段后其引用可见、附件字节继续排除。与它们相同，method的代码、源数据和PRIVATE状态不因存在引用而自动成为公开恢复材料。完整记录字节恢复不等于完整方法、来源或经济结果复算。

定向合成测试只在临时Store内执行，夹具标注SYNTHETIC；为经过真实公开过滤器，夹具记录的 `synthetic=false` 仅用于临时目录，不进入生产。覆盖精确字段保留、类型作用域、两run单根闭包、同输入确定性、新目录恢复、缺失/未来/错误类型方法、私有/未许可方法、未知字段、递归私人路径/token拒绝，以及未许可protocol、PRIVATE与源行附件不泄漏。

真实验证入口：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/verify_public_fields_v2.py \
  --code-root "$INSTALLED_PROJECT_ROOT" \
  --receipt tests/receipts/public-fields-v2-real.json
```

`INSTALLED_PROJECT_ROOT` 指实际主项目；脚本从该处 `.local/installation.json` 读取稳定根，使用只读适配器，不调用Store的建目录构造器或写入口。归档与恢复仅写自动清理的临时目录。receipt必须为候选checkout内 `tests/receipts` 下的新文件；复跑使用新名称，不能覆盖旧receipt。该命令是代码验收步骤，不是用户日常操作要求。

本次真实验证见 [public-fields-v2-real.json](../tests/receipts/public-fields-v2-real.json)：39条旧公开原件与旧投影逐值不变，9条新增投影均完整等于原件；4条原拒收对象各自成功导出与新目录恢复。两run单根分别包含对应method；9新增联合闭包25条/50文件，48公开原件全集48条/79文件。6个导出案例均重复生成相同字节并恢复逐hash核对。真实Store共49条，266个已提交文件在验证前后hash均不变；安装配置和主仓两源文件不变。临时归档已删除，没有上传、发布、远端恢复或经济复算。

方法身份影响必须单独处理：已批准waiting方法的本地导入闭包会包含 `public.py` 与 `contracts.py`；第四批conditional方法同样固定这些源码，且对public.py的公开SOURCE例外依赖精确hash。本候选会改变二者的源码身份，不能沿用旧批准、静默替换常量或把新方法倒签为历史可得。第四批精确合入后，根任务须在组合源码上重新生成依赖身份、明确旧waiting/conditional状态接续桥接并独立审查，再决定安装。旧METHOD、SOURCE、review和feedback原件继续保留，尚未执行任何桥接或第四批改动。

扫描器继续承担现有模式检查，不能据扫描通过推断所有任意文本均具有再分发许可；本候选不扩大披露范围，也不提供任意原行检测器。公开许可和附件白名单的边界保持独立。
