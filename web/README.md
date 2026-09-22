# 策略研究观察页

真实 React + TypeScript + Vite + `@xyflow/react` 静态页面，数据来自本项目的受控文件发布器。没有内置演示回退，没有行情、模型、账户或交易接口。

安装与构建（从 `web` 目录）：

```sh
npm ci
npm run build
npm run dev -- --port 5173
npm run test:browser
```

首次测试需要 `npx playwright install chromium webkit`。测试仅启动独立浏览器实例，不操作用户现有浏览器。构建结果是 `dist/`；项目发布器负责复制静态壳与公开 JSON 至发布目录。

页面读取相对路径 `data/latest.json`，校验 snapshot manifest 和 catalog 的 SHA-256/字节数后原子切换。`history.json` 提供不可变历史时点；详情通过 `catalog.details` 的内容寻址 JSON 按需读取。`catalog.evidence` 与记录内完整 `public_attachment_refs` 提供安全附件入口。文本按纯文本显示，附件通过白名单与哈希检查后才可预览/下载。

新增研究、独立复核、反馈和后继应追加原档并运行发布器；无需更改 `src/` 或重新构建静态壳。`tests/browser/` 的合成输入不能复制到生产数据根。完整验收记录见 `docs/FRONTEND_VERIFICATION.md`。
