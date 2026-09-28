# 异步资料交付维护 v1

本维护包含两个独立交付点：固定异步资格决策原件的精确归档许可，以及不依附研究轮次的公开资料/发现导航。没有重跑研究、日复核或发布业务。

archive.py 只新增 decision-async-qualification-20260928、SHA-256 26361666a255e0e96e2e72e39d6b1f64b8c4fe0e3404c18a6a8aad87c9ab09ac 的许可。唯一额外字段 actual_net 必须严格为 None；0、False、字符串、数组、对象均不接受。PUBLIC/OWN_ANALYSIS、无显式 export_fields、基础投影值一致、完整原件hash、递归扫描和恢复 canonical 字节检查均保留。其他三类精确许可不变。日复核证据本身不扩展许可，因相同决策的语义依赖闭包而自然恢复可归档性。

前端增加“资料与发现”独立入口，使用当前已校验 catalog.details 与 loadRecord，每次用户点击顺序检查10条、每条上限1 MB；可取消、显示失败和未检查范围。只把原件 record_type 为 discovery/evidence 的记录加入当前面板搜索，结果分页20条，正文和许可附件按需打开。既有 P/R/F、轮次图与全历史轮次搜索保持。资料无需绑定 round，提案不生成图节点，原文 PROPOSED_NOT_STARTED 不根据后续轮次存在与否改写。快照切换清空旧资料状态，晚返回结果不能进入新快照；保留图选中、视窗和折叠。

工程验证：16项archive测试、6项公开轮次归档测试通过；新增19种值/类型/ID/披露变异及22种重哈希ZIP/空白/重复键攻击均拒绝。30个既有归档hash与inspect通过。真实Store复制至临时目录，两个缺口原件的51条闭包、173文件经export→inspect→restore逐字节通过，actual_net仍null；186原件、1380个bundle文件和公开投影/图不变。临时副本与输出已清理。

Chromium/WebKit共58项通过，包括fc28旧快照与9c561当前快照的原始发现、证据、搜索和许可REPORT核验；两个快照中提案均保持PROPOSED_NOT_STARTED。官方CUA Chrome另外实际操作本地构建：两快照搜索结果、原件状态和REPORT字节/SHA核验通过。IAB工具当时不可用；未修改权限。官方截图在工具记录中，独立工程浏览器截图逐文件列入回执。此验收是本地真实公开快照回放，不是Pages部署或正式补归档。

复验命令：

```sh
python3 -m unittest discover -s tests -p 'test_archive*.py' -v
python3 -m unittest discover -s tests -p 'test_public_round_archive.py' -v
python3 tests/replay_archive_async_readonly.py --project-root "$RESEARCH_PROJECT_ROOT"
cd web
npm run build
UI_REPLAY_DATA="$(pwd)/../replay-data" ./node_modules/.bin/playwright test --config playwright.async.config.ts documents.spec.ts observer.spec.ts
```

replay-data 是本项目 site/data 两份固定公开快照的隔离副本，文件hash在manifest中；只作验证输入，不安装或发布。浏览器测试端口5188禁止复用已有服务；官方本地验证使用本案新建28761服务，结束已关闭。生产安装仅限delivery_files，测试夹具不被生产读取。public.py、snapshot.py、schema、old16/formal19、依赖、评价、原件和任务均未改变。
