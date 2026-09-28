import { useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { loadRecord } from './data';
import type { JsonRecord, Snapshot } from './data';

// Catalog membership and verified content determine scope; never guess a round
// from an ID or turn a documentary proposal into a graph node.
export default function DocumentLibrary({ snapshot, renderRecord }: { snapshot: Snapshot; renderRecord: (record: JsonRecord) => ReactNode }) {
  const refs = useMemo(() => Object.keys(snapshot.catalog.details).sort(), [snapshot]);
  const [cursor, setCursor] = useState(0);
  const [query, setQuery] = useState('');
  const [items, setItems] = useState<{ ref: string; title: string; text: string; kind: string }[]>([]);
  const [failures, setFailures] = useState<{ ref: string; error: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [cancelled, setCancelled] = useState(false);
  const [opened, setOpened] = useState<{ ref: string; record?: JsonRecord; error?: string }>();
  const [limit, setLimit] = useState(20);
  const controller = useRef<AbortController | undefined>(undefined);
  const live = useRef(true);
  useEffect(() => { live.current = true; return () => { live.current = false; controller.current?.abort(); }; }, []);
  async function scan() {
    if (controller.current) return;
    const active = new AbortController(); controller.current = active; setBusy(true); setCancelled(false);
    try {
      for (let i = cursor; i < Math.min(cursor + 10, refs.length); i++) {
        const ref = refs[i];
        try {
          const record = await loadRecord(ref, snapshot, { signal: active.signal, maxBytes: 1_000_000 });
          if (!live.current || active.signal.aborted) return;
          const kind = record.record_type;
          if (kind === 'discovery' || kind === 'evidence') {
            setItems(values => [...values, { ref, kind, title: String(record.title ?? record.summary ?? ref), text: `${ref} ${JSON.stringify(record)}`.toLocaleLowerCase() }]);
          }
        } catch (error) {
          if (!live.current || active.signal.aborted) return;
          setFailures(values => [...values, { ref, error: String(error) }]);
        }
        setCursor(i + 1);
      }
    } finally { if (live.current) { setBusy(false); controller.current = undefined; } }
  }
  async function open(ref: string) {
    setOpened({ ref });
    try { const record = await loadRecord(ref, snapshot); if (live.current) setOpened(value => value?.ref === ref ? { ref, record } : value); }
    catch (error) { if (live.current) setOpened(value => value?.ref === ref ? { ref, error: String(error) } : value); }
  }
  const matches = items.filter(item => item.text.includes(query.trim().toLocaleLowerCase()));
  return <section className="document-library" aria-label="独立资料与发现">
    <p>资料与发现按原件展示，不要求关联研究轮次。提案状态保留原文，不代表已执行研究。</p>
    <label>资料搜索<input aria-label="资料搜索" placeholder="搜索已检查资料的标题、内容或标识…" value={query} onChange={e => { setQuery(e.target.value); setLimit(20); }} /></label>
    <p role="status">已检查 {cursor} / {refs.length} 条 · 资料与发现 {items.length} 条 · 当前匹配 {matches.length} 条 · 读取失败 {failures.length} 条{cancelled ? ' · 已取消' : ''}。{cursor < refs.length || failures.length ? '搜索仅覆盖已成功检查部分，未检查或失败记录仍为未知。' : '所选快照查找完成。'}</p>
    <button disabled={busy || cursor >= refs.length} onClick={() => void scan()}>{cursor ? '继续查找资料（下一批10条）' : '查找资料（每批10条）'}</button>
    {busy && <button onClick={() => { controller.current?.abort(); setCancelled(true); }}>取消资料查找</button>}
    <p className="muted">仅读取当前快照许可记录，每条检查上限 1 MB；正文和附件由你按需打开。</p>
    {matches.slice(0, limit).map(item => <button className="batch-row" key={item.ref} onClick={() => void open(item.ref)}><b>{item.title}</b><span>{item.ref}</span><small>{item.kind === 'discovery' ? '研究发现 / 提案原件' : '资料证据原件'}</small></button>)}
    {matches.length > limit && <button onClick={() => setLimit(value => value + 20)}>显示更多匹配资料</button>}
    {!!failures.length && <details><summary>未能检查的资料</summary>{failures.map(item => <p key={item.ref}>{item.ref}：{item.error}</p>)}</details>}
    {opened && <section aria-label="资料原件详情">{opened.record ? renderRecord(opened.record) : <p role={opened.error ? 'alert' : 'status'}>{opened.error ?? `读取 ${opened.ref}…`}</p>}</section>}
  </section>;
}
