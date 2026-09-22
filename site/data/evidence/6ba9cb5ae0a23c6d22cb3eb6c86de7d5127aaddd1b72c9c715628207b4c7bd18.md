# 公开范围与恢复含义

本目录允许公开的最小包由 `PUBLIC_MANIFEST.json` 明确列举。自撰报告、协议、派生诊断表与元数据可按 CC-BY-4.0 使用；自撰 Python 代码可按 MIT 使用（亦可按本项目许可合并分发）。第三方源数据、网页、名称和来源链接不因本说明被重新许可。

不公开：OKX ZIP/CSV 原件、网页 HTML、行级摘录、浏览器会话/登录资料。官方源 ZIP 的 SHA-256、大小、取得时间和网址保留在公开元数据中。条款审核见 `sources.json`；未找到明确的原件再分发授权。

公开包能恢复自撰研究和派生事实上的算术结果，可执行 `python3 reproduce_derived.py` 与 `python3 cost_stress.py`，分别与保存的 JSON 比较。它不能独立重建/认证上游 CSV 的所有行；本机 `audit_funding.py` 仍需已下载且哈希匹配的原 ZIP。恢复派生计算不等于完整原始市场证据远端备份，后者为 LOCAL_ONLY/未完成。

本次 manual safe trial 由官方 Codex 应用中的研究子代理完成。它不是原生任务 Run now，也不是 scheduled 触发；两个自然研究时点、自然日复核与自然反馈采用仍待未来事实。
