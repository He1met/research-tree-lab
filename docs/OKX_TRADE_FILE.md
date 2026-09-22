# OKX BTC 单日成交文件离线扫描器

`researchlib.okx_trade_file.scan_trade_file` 在官方应用内调用标准库 Python 即可运行。它只读取调用者已取得的本地 ZIP/CSV，不联网、不下载、不解压落盘、不登记原件、不运行经济复核。完整输出含选中原行，只能 `LOCAL_ONLY` 保存；公开回执只能选取计数、校验摘要和限制说明。

## 已审核范围与输入

当前实现支持已实际解码的 BTC 文件布局：文件名 `BTC-USDT-SWAP-trades-YYYY-MM-DD.zip`，恰好一个同名 `.csv`；或直接输入该 CSV。精确列序为：

```text
instrument_name,trade_id,side,price,size,created_time,source
```

这是实际文件的 `price,size` 列序。字段为未加引号的 ASCII，行尾支持 CRLF、LF 或最后一行无行尾；BOM、引号、嵌入换行、空白行、多余列均拒收。只接受 `BTC-USDT-SWAP` / `USDT`，`side` 为 `buy` / `sell`，当前观察到的 `source` 编码 `0` / `1` 原样保留，不给编码添加未经核实的市场含义。价格和数量必须为有限、严格正值 Decimal，原字符串与物理行号保留在选中事件的定位中。

ZIP 仅支持单成员、非加密、flags=0、无 extra/comment/data descriptor/ZIP64，stored 或 raw-deflate，local/central 声明一致且没有夹带或尾部数据。读取固定大小尾部目录后才读取唯一成员元数据，不构建任意数量的目录项。实际 deflate EOF、展开长度、CRC 都检查，不依赖 `ZipExtFile` 按被伪造的小尺寸截断。

精确 manifest 字段如下；拒收多余字段，包括人为填写的 `coverage=COMPLETE`：

```python
manifest = {
    "schema_version": 1,
    "format": "zip",  # 或 csv；与 filename 后缀一致
    "filename": "BTC-USDT-SWAP-trades-2026-09-21.zip",
    "sha256": "efab589d1d2171e7bd589e334653bea29daa414b4c87239ad75c4f6c23886f69",
    "size_bytes": 28884745,
    "source_url": "https://www.okx.com/zh-hans/historical-data",
    "obtained_at": "2026-09-22T19:13:41.105816+00:00",
    "declared_partition": {"date": "2026-09-21", "timezone": "UTC+08:00"},
}
```

`obtained_at` 必须来自真实取得记录，不能用本次解析时间替代。上例是已封存 `d-btc-trades-20260921@1` 的 `acquired_at`；该值仍属于取得时间声明，解析器只能检查约束，不独立认证下载过程。SHA/size 验证实际读取 bytes；官方 host 白名单只校验声明 URL，不能证明网络来源。源 URL、取得声明、调用者单独提供的 `information_as_of` 和实际文件身份分别报告。

## 实际调用

先在当前终端把 `RESEARCH_MAIN_ROOT` 设置为实际主安装目录（绝对路径），再从仓库根目录，在官方应用内执行下面的离线 Python；`source` 是主安装稳定对象的已有路径，可只读指向它，不应复制安装到开发 worktree。示例不保存完整输出：

```python
from datetime import datetime, timezone
from pathlib import Path
import json
import os
from researchlib.okx_trade_file import scan_trade_file

main = Path(os.environ["RESEARCH_MAIN_ROOT"])
dataset_path = main / ".local/store/bundles/research-feedback-input-completeness-20260923-v1/records/dataset/d-btc-trades-20260921@1.json"
dataset = json.loads(dataset_path.read_text())
source = main / ".local/data/objects" / dataset["sha256"]
manifest = {
    "schema_version": 1, "format": "zip",
    "filename": "BTC-USDT-SWAP-trades-2026-09-21.zip",
    "sha256": dataset["sha256"], "size_bytes": dataset["bytes"],
    "source_url": dataset["source_url"], "obtained_at": dataset["acquired_at"],
    "declared_partition": {"date": "2026-09-21", "timezone": "UTC+08:00"},
}
result = scan_trade_file(
    source, manifest,
    information_as_of=datetime.now(timezone.utc).isoformat(),
    synthetic=False,  # 调用者声明；不能凭文件名/hash 自动推断
    window={"start_inclusive": "2026-09-20T16:00:00Z",
            "end_exclusive": "2026-09-20T16:00:01Z"},
)
assert result["audit"]["status"] == "FILE_DECODE_COMPLETE"
print(result["audit"]["rows_read"], len(result["kernel_payload"]["events"]))
# result 整体及 kernel_payload 含来源原行，仅限本地，不传到公开发布器。
```

省略 `window` 的默认行为为整文件审计，返回空 events，标为 `AUDIT_ONLY_NO_EVENTS_REQUESTED`，不表示没有成交。窗口严格半开、毫秒对齐、落在声明分区内。即使只输出一秒，也扫描校验所有行；窗口外的坏行或未来事件会使整个调用失败。空窗口结果是 `NOT_OBSERVED_NOT_PROVEN_ABSENT`。窗口选取不是分页，不代表该窗口完整，也不会借过滤跳过时点约束。

`created_time` 必须为不经浮点转换的非负整数毫秒字符串。每行满足 UTC+8 声明分区 `[start,end)` 和 `event_at <= obtained_at <= information_as_of <= 当前 UTC 时间`，禁止 naive 时间或未来信息截止。声明分区尚未结束时，合法已观察行可以接受；源和窗口覆盖仍恒为 `UNKNOWN`，`data_complete=False`，没有预期总成交数或日历补齐。

## 完成、资源与顺序语义

接口同步完成，不返回可被中途消费的 generator。只有完整 CSV EOF、实际展开长度/CRC、同一文件描述符扫描前后 SHA、文件 stat 未变都通过，才返回 `FILE_DECODE_COMPLETE` / `validation_complete=True`。尾行坏、资源超限、取消、异常不会返回部分 payload，也没有“部分成功”回执。`TradeFileError` 标为 `FILE_DECODE_NOT_COMPLETE`，不包含部分事件或源路径。`KeyboardInterrupt` 等外部中断也没有返回值；调用者不得将自行累计的进度写成完整验收。

资源上限是十进制 bytes，不是 MiB：

| 项目 | 上限 |
|---|---:|
| ZIP 原 bytes | 64,000,000 |
| CSV 原/实际展开 bytes | 512,000,000 |
| 数据行（不含 header） | 8,000,000 |
| 单物理行（含行尾） | 1,024 bytes |
| 单个压缩/展开块 | 262,144 bytes |
| 选中事件 | 默认 20,000；调用者可降低或提高，硬上限 50,000 |
| 协作式运行时间 | 默认及硬上限 180 秒；可降低 |

全表扫描状态使用常数空间；只有选中事件按显式上限保留。超过选中事件上限整次失败，绝不截断为成功。`timeout_seconds` 覆盖前后 hash、解压和 CSV 扫描；也可传零参 `cancel=lambda: ...`，返回真时取消。检查发生在有限块/每 1,024 行及返回前。它是协作式检查，不保证中断内核阻塞 I/O，也不是进程内存硬隔离。

实际读取对象是**已打开的同一 FD**。前后字节哈希及设备/inode/size/mtime/ctime 检查帮助拒绝并发修改；路径后来被替换不能把原 FD 的结果当成新路径内容认证。不会回写、重新打开替换文件后沿用旧校验、导出本地路径。

为避免存储数百万 ID 去重集合，版本 v1 只支持当前真实样本的布局：时间戳非递减，数字 trade ID 严格递增。ID 保留原字符串，允许 ID 间隔，**不以 ID 连续性证明无漏，也不把数字大小当官方撮合顺序**。相同/冲突 ID、远距离重复、ID 逆序、时间戳倒退全部按不支持布局拒收，不静默去重或重排；其他官方文件布局需要单独评审的新能力。

稳定业务身份为 `okx-trade:BTC-USDT-SWAP:<trade_id>`；源 SHA、成员 SHA、物理行号另存为 provenance，同一成交出现在另一个文件不会得到新的业务 ID。本函数只读单文件，不做跨文件合并；如相同 ID 的 availability/provenance 改变，应走已有显式修订边界，不能回填旧可见时点。

所有选中事件 `sequence=null`，状态为 `PROVISIONAL_SOURCE_COVERAGE_UNKNOWN`。同毫秒多个不同 ID 均保留；同价也不合并。整文件 same-ms 计数仅描述已观察分组，使用该组首个数值价格加一个“已见不同价格”布尔量，不保存无界价格集合，也不选首笔。

## 与条件内核的连接边界

`result["kernel_payload"]` 的 trade 事件形状可供已有条件内核单独检查，但本模块不调用 `evaluate_funding`，不生成经济 review。它没有 funding/精确 settlement mark/实际费用/覆盖证明；即使价格 rows 解码完，也不会据此形成合法收益或 `NO_TRADE`。相同毫秒最早候选有多条且无 sequence 时，已有内核仍应保持 `PATH_AMBIGUOUS`；不应把 `trade_id` 或行号补到 `sequence`。

本次选择的 2026-09-21 声明本地日是历史格式样本，不在两份前向 plan 的未来窗口。没有扩大原计划有效窗口、改写旧数据记录或将研究脚本的结果升为生产来源保证。

## 作者证据与可复跑命令

合成对抗测试（没有下载数据、没有经济结论）：

```sh
python3 -m unittest discover -s tests -p test_okx_trade_file.py -v
```

单独的真实样本回执来自只读稳定原件；需要本机已有文件，不能用合成 fixture 顶替。将 `NEW_RECEIPT_PATH` 设为一个尚不存在的新文件路径，其父目录必须已存在且路径各层均不是符号链接。不要填写本仓库已保存的作者回执路径；重复复跑须选择另一个新路径：

```sh
python3 tests/replay_okx_trade_sample.py \
  --source "$RESEARCH_MAIN_ROOT/.local/data/objects/efab589d1d2171e7bd589e334653bea29daa414b4c87239ad75c4f6c23886f69" \
  --dataset "$RESEARCH_MAIN_ROOT/.local/store/bundles/research-feedback-input-completeness-20260923-v1/records/dataset/d-btc-trades-20260921@1.json" \
  --receipt "$NEW_RECEIPT_PATH"
```

已记录的作者复跑：Python 3.9.6，28,884,745-byte ZIP → 295,527,908-byte CSV → 4,969,733 数据行；CRC 与前后 hash 一致；首秒选中 112 条，全部 sequence 为 null。352,819 个同毫秒多行组、157,283 个多价格组，与既有诊断报告吻合。一次观察耗时 12.46 秒、进程峰值 RSS 18,759,680 bytes；这是本机该次小输出窗口的观测，不是所有环境/最大输出窗口的性能保证。详见 `tests/receipts/okx-trade-real-sample.json`。完整结果未落盘，脱敏回执不含原行、价格或源路径。

复跑 helper 在扫描前用逐层 `O_NOFOLLOW` 目录 FD 和 `O_EXCL` 独占创建 mode 0600 的新输出，拒绝原件同路径、任何已有文件（含 hardlink）、leaf/parent symlink；全过程保留该输出 FD，竞态路径替换不会把写入导向原件。扫描失败可能留下空的新建占位文件，不是成功回执；helper 不按可能已变化的路径删除它。

输出保护回归另见 `tests/test_okx_trade_replay.py`，覆盖同路径、已有/hardlink、符号链接、抢先创建、FD 保留及父目录替换竞态。可运行 `python3 -m unittest discover -s tests -p 'test_okx_trade*.py' -v` 同时验证两组。

作者合成测试和真实文件解码与后续独立审查分开报告。来源全覆盖、相同毫秒真实顺序、精确结算 mark、未来有效窗口与实际费用事实仍是独立缺口。
