# 本轮补充资料的详情导航缺项

2026-09-27 发布回读发现：snapshot f694bd01460d45258c9694856371a7e1ce2f8bfcabbf03f2430925cda1c9ee44 的 catalog 已包含 decision-tier-history-probe-20260927、e-tier-history-probe-20260927、run-tier-history-probe-20260927@attempt-1，但 r-maintenance-tier-20260927 的现有详情仍仅展示旧 round；反馈页显示无反馈记录。新原件未丢失，公开归档增量 v5 已上传并校验服务器摘要。

源码依据：researchlib/snapshot.py 的 round 详情仅生成 plan/review/feedback refs，decision_refs 仅关联 successor_round_id；web/src/App.tsx 的 drawer 三页签只加载 round+plans / reviews / feedbacks。当前新增 run 通过 round_id 指向旧轮、decision 通过 source_round_ref 指向旧轮，未获得导航入口。

请求独立维护版本设计并审查补充运行、证据与决定导航：保持原件、代际和 P/R/F 语义；不复制研究，不把资料或合成检查变成经济样本。需验证旧快照兼容、公开许可与引用边界、选中和视窗保留。此次发布未改源码、schema、依赖或研究规则。HTTP发布与网页完整可浏览性分开记录。
