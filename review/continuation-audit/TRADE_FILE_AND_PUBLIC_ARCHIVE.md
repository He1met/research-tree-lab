# 成交文件解析与公开字段兼容维护独立审查

结论：**PASS_SCOPED_INDEPENDENT_REVIEW**。限已观察 BTC 单日成交文件的完整离线流式解码，以及 round.source_review_refs 的公开归档兼容修复；本次范围内无未解决实质问题。

组合源码 SHA-256：`c1aa9e50635b4591514dc17e2d5123f3742a6b4a7b6b90c9403f6f84bd043592`。由候选目录实际运行 `python3 scripts/publish.py --source-hash` 得到并再次回读一致。精确 **10 个交付文件及各自 hash**、集成步骤见 [trade-public-source-receipt.json](trade-public-source-receipt.json)。waiting review 的递归本地依赖 hash 更新为 `d21b004a0efe4295f391a3f82ccba05f6a967b9205d370eabd807a8692f91f65`；不得沿用旧批准身份或倒签方法可用时点。

独立复跑 **81 项定向测试**：成交解析33、回执输出安全8、公开归档及扫描12、waiting review 回归28。另有自写10组成交攻击检查、6项CLI输出攻击；同行对压缩流补充63种裁尾、4种追加、9种块大小检查，均符合拒绝或精确解码预期。1万与5万行 audit-only 合成扫描峰值内存未随总行数增长。这里的合成检查是工程证据。

真实旧包独立全量扫描：28,884,745-byte ZIP、295,527,908-byte CSV、4,969,733行；完整EOF、CRC、成员SHA及同FD前后源SHA通过。修复后脚本本次约12.235秒、峰值RSS18,743,296 bytes，仅是本机小输出窗口的观测。首秒112条事件全部保留，sequence恒为null；源及窗口覆盖恒UNKNOWN。取得时点来自原dataset声明，UTC+8声明分区未转换成“完整UTC日”，也未据此证明官方来源、无漏或真实撮合顺序。回执不含原行情行或价格，见 [真实回读](trade-file-real-safe-output-independent-receipt.json)。

发现并修复的P2：旧复跑脚本允许把 `--receipt` 指向 `--source`，即使COMPARISON_FAILED仍覆盖源ZIP。已用临时文件复现。当前版本在扫描前通过目录FD和NOFOLLOW逐层打开，末级O_EXCL独占创建并持续持有输出FD，拒绝已有文件、硬链接及符号链接；竞争创建和预留后的路径替换不会重定向写入。失败可能留下空的新占位，它不是成功回执。独立CLI复验输入均未改变，见 [输出安全复验](trade-helper-output-independent-receipt.json)。

公开字段修复仅允许round已有source_review_refs字段进入投影，未知字段、限制性disclosure、引用时点和私有内容拒绝均保留。4个真实受阻对象独立生成临时归档，闭包分别为13/34、13/34、12/33、13/34个records/files；逐记录原字节和附件hash回读通过，39条生产原件hash前后相同。这只验证本机公开范围归档能力，未进行远端恢复，受限上游仍LOCAL_ONLY。详见 [公开归档独立回执](public-round-independent-receipt.json)。

未关闭：独立来源/取得认证、市场全覆盖、同毫秒交易排序、精确结算mark及路径、完整funding/实际费用、非空跨日经济状态接续、正式经济评价和自然调度验收。资源时限仍为协作式；本次没有新增OS隔离保证。历史格式样本不在两份plan的前向结果窗口内。

集成时仅复制JSON列明10文件，逐文件验hash；在main重算组合source hash必须一致，并执行适用集成检查与公开扫描，再由根任务处理安装和发布。本审查没有修改生产安装、Store、旧方案、原始数据或原生任务，没有生成经济review或自然触发身份。
