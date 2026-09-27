# 每日独立策略复核 · 2026-09-27

本批完整处置全部2个登记版本，均为 PATH_AMBIGUOUS，经济可评价0、最终0、复用0、技术失败0。取得4份官方原窗口文件，通过固定评价器完整解码，追加2份复核和2份反馈。原方案、旧复核及已冻结115条原件hash不变。毛/净结果、费用、持仓、资金费现金流、持有期和完整权益回撤均未知。覆盖完成不代表经济评价完成；自然触发 UNKNOWN，网页发布尚由发布任务处理。

## 真实覆盖与阶段

| 方案版本 | 方向与数量 | 阶段 | 实际可评价市场截止 | 经济结果 |
|---|---|---|---|---|
| p-btc-funding-short-20260923@1 | -0.01 BTC | PATH_AMBIGUOUS | null | 全部正式指标null |
| p-btc-funding-long-control-20260923@1 | +0.01 BTC | PATH_AMBIGUOUS | null | 全部正式指标null |

初始清单冻结于 2026-09-27T00:18:21.072312Z；固定程序封存时再次核对清单、plan hash及前驱完全一致，未混入晚登记方案。窗口仍是原定2026-09-23 00:05–00:06 UTC入场、2026-09-24同一分钟退出；请求截止为原终点00:06 UTC。信号由原冻结观察决定，不能改为未触发，也没有制造0收益交易。两方向是同一窗口的对照，不能相加为账户收益或算作独立市场样本。

## 数据与路径问题

官方历史下载页面实际选择永续BTC-USDT及9月23–24日，资金费率为原官方allswap文件；UTC+8分区。页面下载按钮给出下列精确静态文件地址，HTTP 200取得原字节，后经受控put_data及review角色dataset提交。完整下载原件保持本机受限，不公开原行。取得时间不是数据首次发布时间；published_at仍null，不把9月27取得资料倒签。

| 原文件 | 字节 | SHA-256 | 实际取得UTC |
|---|---:|---|---|
| BTC-USDT-SWAP-trades-2026-09-23.zip | 19459479 | c17b52f17ae7762aff2d2ef72720df08f1f0ce534331054dc11d30cff8e195aa | 2026-09-27T00:21:40.699570Z |
| BTC-USDT-SWAP-trades-2026-09-24.zip | 19578282 | 531d1397caa0fb0bdb3158b4b0fd8acb618f7a0c7b46b17600762985993e574d | 2026-09-27T00:21:37.685663Z |
| allswap-fundingrates-2026-09-23.zip | 12808 | ccb7a177d16a56889a56e878402852302d57a6c8443aadf8e99814195bb6a2e8 | 2026-09-27T00:23:18.689661Z |
| allswap-fundingrates-2026-09-24.zip | 13250 | f3c2de4291bf963c8da05dc01a602d5ed06ea552df491e3b47954b41f98519a7 | 2026-09-27T00:23:17.849533Z |

两份trade完整校验6,815,192行，原入/退出一分钟分别选出2,616/1,359条观察；两份funding完整校验4,219行、各观察到3条BTC事件，按原截止筛选后每方案共有3,980条输入观察。未按行号或trade ID伪造同毫秒顺序。文件声明分区覆盖所请求区间，不等于源事件全集、首笔顺序或连续路径证明；交易价不充当mark。

首笔入场/退出资格、持仓、价格损益、完整资金费现金流、mark路径、适用费用表、实际费用及成本终态语义均未获资格。全部12个事前费用/滑点情景仍逐项保存在原评价输出，依赖缺项保持null；不能择优挑选。跨日状态链接各自原review及opening_state_hash，未重置为空仓、未强制平仓。公示时间原字段null，维持本地封存前向记录边界，不追加未经核实的公开事前证明。

## 反馈：事实、解释、待检验变化

事实：原窗口文件已取得并完整解码，但正式所需来源资格缺失。解释：未知指标来自原规则证据要求未满足，不能解释成策略亏损、无效或没有交易。

下一项可检验变化是取得并独立审查能证明原窗口首笔顺序、覆盖和精确mark的官方证据格式，随后按明确修订链重算；不是修改原策略参数。对照保留同期同绝对数量的多/空方案和全部成本情景。反例是新增资料仍只有交易价或没有顺序/结算mark：此时应继续未知，不能升级最终。若在已曝光行情上另改规则，只能登记新开发假设，不能充当前向证明。

## 身份、工程与自然证据

固定release_ref c7ec6ba8b0c6ab00def8c9878ea4b65fe906a82b；方法SHA-256 34e0bcfce6515c0ccb5e2f742ab1936b440b6d06cf4b3670049c7993efa63be4。已逐件核对源码与安装批准及Git固定ref，CPython 3.9.6；本轮没有更换评价器或运行合成测试。固定解析/计算程序实际运行和Store追加回读是工程事实，不是经济有效性证明。

官方automation view仅返回界面卡片，没有可靠本次触发来源。调用层记UNKNOWN、natural_trigger=null；评价器自身固定OFFICIAL_APP_HELPER_NOT_NATIVE_ATTESTATION和false只表示helper不提供原生触发认证，不据此把会话判为manual。F07仍等待自然来源证据。

## 完整证据索引

- 批次：batch-daily-review-20260927-v1
- 复核：review-batch-daily-review-20260927-v1-4809fda65a42055d, review-batch-daily-review-20260927-v1-bf1f5e787c973f51
- 前驱：review-btc-funding-long-control-manual-20260923-v1, review-btc-funding-short-manual-20260923-v1
- 正式bundle：bundle-batch-daily-review-20260927-v1（METHOD、19件源码、2份PRIVATE计算状态均以manifest绑定；PRIVATE及受限raw不公开）
- 数据bundle：review-inputs-20260927-v1（4个dataset）；原始SHA见上表。
- 本报告配套EVIDENCE.json保存身份、覆盖、源文件和解码计数。正式review保存全部情景、状态hash及缺项。
- 本机incoming完整HTTP回执、input-manifest、冻结清单、outbox和commit回执均保留；公共索引与页面未由本任务改写。
