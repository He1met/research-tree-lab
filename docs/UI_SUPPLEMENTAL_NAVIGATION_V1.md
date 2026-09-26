# 本轮相关材料导航维护 v1

既有轮次的后续运行、证据和决定已经公开，但三页签缺少访问入口。本维护只改变浏览器导航：研究方案内可查找运行与证据，反馈与下一步内可查找决定。研究代际、评价方法、公开投影与原件不变。

用户每次点击只检查当前已核验 catalog.details 的下一批 10 条记录，顺序读取，每条最多 1,000,000 字节；可取消。记录必须通过现有内容哈希、schema、所选信息时点检查，再由 round_id、source_round_ref 或 input_record_refs 的精确引用确定“本轮相关材料”。ID 前缀不参与判断；引用不意味着派生或采用。未扫描或读取失败明确保留未知，失败明细可展开。正文仅在点击结果时展开。页签、轮次或快照变化会卸载相关查找并取消读取；新快照保留图选中、视窗和折叠状态，但清空旧详情状态。

loadRecord 缓存命中也重新检查当前 catalog 许可与信息时点。流式读取限制单对象大小，详情缓存最多 128 条。没有常规抽屉自动全库查找，也没有创建新的图节点。

## 验证与交付边界

`replay-data/` 是从本项目 `site/data/` 复制的公开 snapshot f694bd01460d45258c9694856371a7e1ce2f8bfcabbf03f2430925cda1c9ee44 的隔离验证输入；不是生产目录、恢复操作或部署输出。清单记录其逐文件 SHA-256，真实三原件在 Chromium 与 WebKit 中实际打开并截图。本机浏览器回放不等于正式 Pages 发布回读。

独立复验在候选的 `web/` 目录运行：

```sh
npm run build
UI_REPLAY_DATA="$(pwd)/../replay-data" ./node_modules/.bin/playwright test --config playwright.ui.config.ts related.spec.ts observer.spec.ts
```

安装后的复验可把 UI_REPLAY_DATA 显式指向本次封存的公开回放目录；不得隐含指向生产原件或合成替代数据。专用服务器端口 5187，reuseExistingServer=false，不接管未知服务。截图、结果 JSON 和输入文件地图列在冻结清单中。只有 `delivery_files` 列出的前端源码和工程测试/说明进入安装审查；`replay-data`、浏览器产物、node_modules 链接和 dist 不属于生产安装清单。

边界：查找只支持上述三种显式字段与 run/evidence/decision 身份。每页有资源限额；超限材料显示失败而非无关联。按需打开使用原有 30 MB 正文上限。未改变原件、方法、收益规则、调度、权限或发布程序；旧 16 源与正式评价 19 源需由冻结清单逐项比对。
