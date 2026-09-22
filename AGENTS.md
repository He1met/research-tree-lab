# Research Tree Lab

唯一实施规范是 `planning/current/PROJECT_SPEC.md`，细则为同目录的 `RESEARCH_PROGRAM.md`、`AUTOMATIONS.md`、`docs/ACCEPTANCE.md`。根目录同名入口是符号链接，不产生第二套规范。

默认简体中文。先读 `STATE.md` 与 `.local/installation.json`，再只读取相关完整记录。禁止读取凭据正文、其他项目、交易账户；不下单、不付款、不调用独立 Codex CLI、模型 API、自建行情 API 或其他调度器。

使用对应 `.agents/skills/` 工作方法。研究原件保存在稳定 `.local/store/`，数据在 `.local/data/`。研究和复核只通过受控提交新增；旧原件不得改写。公共代码、评价器、schema 和依赖变更需独立检查，不能为了结果改规则。公开发布仅作用于安装配置已核实的本仓库。

`handoff/`、原始 ZIP、`.local/`、私人路径和受限原件不公开。生产禁止读取合成夹具作为后备；UI 新记录由固定发布程序生成。没有记录的新研究不是已执行，没有自然触发证据不是自然验收。

遵守原生任务用户实际频率；不能自动恢复默认。所有者不明不删锁、不重抽。未来窗口保留 WAITING_NATURAL_OUTCOME，普通研究无需用户接续批准。
