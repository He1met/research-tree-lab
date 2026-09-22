# OKX funding 文件离线 normalizer v1

`researchlib.okx_funding_file.normalize_funding_file` 只解析已取得的单个 allswap 日文件，不联网、不写 store、不发布、不生成结算日历。目标固定为 `BTC-USDT-SWAP` / `USDT`。输出含原始行定位与数值，整个返回值均为 **LOCAL_ONLY**。

官方字段与分区依据是 `review/continuation-audit/source-adapter-audit.md/json` 的已观察结果；原审计与原方案不修改。本模块只落实可验证的文件层，不补足 tick、精确结算 mark 或事件完整覆盖。

## 输入与约束

签名为 `normalize_funding_file(blob, manifest, *, information_as_of, synthetic, target_instrument='BTC-USDT-SWAP')`。`blob` 必须是实际文件 bytes。`synthetic` 必须显式为布尔值，是调用方声明，hash/官网 URL 不会自动把输入认定为真实。

manifest 恰有以下字段；日期必须与文件名一致。`information_as_of` 单独传入，不能藏在 URL 或文件元数据里。

```json
{
  "schema_version": 1,
  "format": "zip",
  "filename": "allswap-fundingrates-2026-09-21.zip",
  "sha256": "34a7e077c89ade3d60e5afe26e615bcf2df10fdfab04930b62d185810e8f698c",
  "size_bytes": 12419,
  "source_url": "https://www.okx.com/zh-hans/historical-data",
  "obtained_at": "2026-09-22T17:51:24.065702Z",
  "declared_partition": {"date": "2026-09-21", "timezone": "UTC+08:00"}
}
```

支持 `zip` 或直接 `csv`，文件名固定为 `allswap-fundingrates-YYYY-MM-DD` 加匹配后缀。ZIP 只允许一个同名 CSV、无路径/软链、无 extra/data descriptor/ZIP64、flags 0 或 UTF-8 标志、stored/deflate；真实已观察 12 KB 包符合此范围。其他 ZIP 变体需另行审查，不自动兼容。输入最多 10,000,000 字节，解压 CSV 最多 20,000,000 字节、250,000 行；不落盘解压。检查 local/central 声明、实际解压长度与 CRC，防伪造短 size 隐藏解压尾部。

UTF-8 可有首 BOM；header 精确为 `instrument_name,funding_rate,funding_time`，顺序和列数固定。率使用 finite Decimal，编码最多 128 字符、指数绝对值不超过 1000；不受其他分析的 Decimal 精度影响。时间必须是无前导零的非负 ASCII 整数毫秒，不接受浮点、指数或四舍五入。**全文件含非目标行**都验证格式、冲突、UTC+8 半开分区及 `event_at <= obtained_at <= information_as_of <= 当前主机时钟`。主机时钟及取得时间声明并非独立的获取证明。

官网 URL 只接受 HTTPS、白名单 host `okx.com/www.okx.com/static.okx.com`，已审查入口路径或 `.zip/.csv` 文件路径；不接受用户信息、端口、query 或 fragment。白名单只验证声明的 URL 形状，不证明这些 bytes 真从该网站取得。

## 离线调用与内核衔接

在官方应用内终端、项目根执行以下 Python；示例要求已知原样本在本地指定路径，不能把失败改成合成回退。无网络调用。

```python
import json
from pathlib import Path
from researchlib.common import now_iso
from researchlib.okx_funding_file import MAX_SOURCE_BYTES, normalize_funding_file

source = json.loads(Path('research/bootstrap-v1/sources.json').read_text())['archive']
sample = Path('.local/funding-file-audit/allswap-fundingrates-2026-09-21.zip')
with sample.open('rb') as stream:
    blob = stream.read(MAX_SOURCE_BYTES + 1)
manifest = {
    'schema_version': 1, 'format': 'zip', 'filename': source['original_filename'],
    'sha256': source['sha256'], 'size_bytes': source['bytes'],
    'source_url': source['source_url'], 'obtained_at': source['downloaded_at'],
    'declared_partition': {'date': '2026-09-21', 'timezone': 'UTC+08:00'},
}
# False 只对应已有真实获取记录；合成/对抗输入必须传 True。
result = normalize_funding_file(blob, manifest, information_as_of=now_iso(), synthetic=False)
scratch = Path('.local/funding-normalization')
scratch.mkdir(parents=True, exist_ok=True)
for name, value in [('normalizer.json', result), ('kernel-payload.json', result['kernel_payload'])]:
    with (scratch / name).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
```

`result['kernel_payload']` 可作为已审核 `scripts/evaluate_funding.py --input` 的输入。在确已安装、能读到正式计划的项目中，例如：

```sh
python3 scripts/evaluate_funding.py --project-root "$PWD" \
  --plan-ref p-btc-funding-short-20260923@1 \
  --input .local/funding-normalization/kernel-payload.json \
  --market-event-cutoff 2026-09-22T18:30:00Z \
  --output funding-only-example.json
```

此固定旧样本发生在方案生效前，示例只能得到条件内核的未生效结果。对以后样本，市场截止必须取实际已到且不超冻结终点的时点，信息截止另外取真实当前时点。隔离 worktree 不会自动装载生产 store；本次未执行 helper 读取生产项目。

所有事件的 `settlement_mark=null`，没有 trade/mark 事件，`source_coverage=UNKNOWN`、`data_complete=false` 固定。仅有 funding 输入不会形成完整收益、FINAL、NOT_TRIGGERED 或 readiness。分区尚未结束时可接纳已观察行，但不能声称全天已齐；没见目标合约也不是 0 资金费。

事件 ID 为 `okx-funding:<instrument>:<integer_ms>`，不依赖文件 hash/行号；来源另存 archive/member hash 和全部原字符串/行号。同键同 Decimal 值去重并保留每个原行，数值不同拒收。**只验收单文件**；跨文件去重/来源合并未实现。相同 ID 的来源或 available_at 改变可能触发 kernel correction，不能为通过而回填取得时间或丢掉新来源。

## 可重跑证据

合成对抗测试（独立于真实样本）：

```sh
python3 -m unittest discover -s tests -p 'test_okx_funding_file.py' -v
```

真实旧样本只读复跑，写全新脱敏回执，不公开 raw、不运行经济评价：

```sh
python3 tests/replay_okx_funding_sample.py \
  --sample .local/funding-file-audit/allswap-fundingrates-2026-09-21.zip \
  --receipt tests/receipts/okx-funding-real-sample-rerun.json
```

已执行回执为 `tests/receipts/okx-funding-real-sample.json`。其 PASS 仅限字节身份、CRC、schema、声明分区和 2,103 行中的 3 个 BTC 事件解析；不是新获取、全覆盖或经济结果验收。原始 ZIP 与归一化数值始终留本地隔离目录。
