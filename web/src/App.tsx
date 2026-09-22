import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Background, Controls, Handle, Position, ReactFlow, ReactFlowProvider } from '@xyflow/react';
import type { Edge, Node, NodeChange, NodeProps, ReactFlowInstance, Viewport } from '@xyflow/react';
import { directionLabel, formatTime, label, loadEvidence, loadHistory, loadRecord, loadSnapshot, productName, readinessState, shortText, statusLabel, uniqueProducts } from './data';
import type { Assessment, JsonRecord, Pointer, Round, Snapshot } from './data';

type Tab = 'plan' | 'review' | 'feedback';
type DrawerState = { roundId?: string; tab: Tab; ref?: string; daily?: boolean };
type Preferences = { product: string; direction: string; openRounds: string[]; openBranches: string[]; viewport: Viewport; selected?: string };
const defaultViewport = { x: 38, y: 46, zoom: .88 };
function initialPrefs(): Preferences {
  try { return { product: '', direction: '', openRounds: [], openBranches: [], viewport: defaultViewport, ...JSON.parse(localStorage.getItem('research-observer-v1') ?? '{}') }; }
  catch { return { product: '', direction: '', openRounds: [], openBranches: [], viewport: defaultViewport }; }
}
type RoundData = { round: Round; productLabel: string; expanded: boolean; descendantsOpen: boolean; childrenCount: number; historical: boolean; readyStates: string[]; selected: boolean; open: (id: string, tab: Tab, ref?: string) => void; toggleRound: (id: string) => void; toggleBranch: (id: string) => void } & Record<string, unknown>;
type RoundNode = Node<RoundData, 'round'>;

function Readiness({ assessment, state, historical = false }: { assessment: Assessment; state: string; historical?: boolean }) {
  const ready = state === 'EXECUTION_READY_AS_OF';
  return <div className={`readiness ${ready && !historical ? 'ready' : ''}`} data-readiness={state}>
    <strong>{historical ? '历史记录 · ' : ''}{label(state)}{ready ? ` · 截至 ${formatTime(assessment.as_of)}` : ''}</strong>
    <span>{assessment.plan_ref} · {label(assessment.evidence_stage, '证据阶段未记录')}</span>
    {assessment.valid_until && <span>条件有效截止 {formatTime(assessment.valid_until)}</span>}
  </div>;
}
const ResearchCard = memo(function ResearchCard({ data }: NodeProps<RoundNode>) {
  const r = data.round;
  const planLine = r.selected_plan_ref ? `${r.selected_plan_ref} · ${shortText(r.plan_summary, '已登记')}` : r.plan_refs.length ? `${r.plan_refs.length} 个候选 · 未指定主选` : shortText(r.plan_summary, '尚无正式方案');
  const readyIndices = data.readyStates.flatMap((state, index) => state === 'EXECUTION_READY_AS_OF' ? [index] : []);
  return <article className={`round-card ${data.selected ? 'selected' : ''}`} aria-label={`${r.title}，第 ${r.generation} 代`} data-round-id={r.id} data-generation={r.generation}>
    <Handle type="target" position={Position.Left} isConnectable={false} />
    <header className="card-header"><div className="eyebrow">第 {r.generation} 代 <span>·</span> {data.productLabel || '产品待核实'}</div><span className="status" title={r.status}>{statusLabel(r.status)}</span></header>
    <button className="card-title nodrag" onClick={() => data.open(r.id, 'plan')}>{r.title}</button>
    <dl className="card-summary"><div><dt>方案</dt><dd>{planLine}</dd></div><div><dt>复核</dt><dd>{shortText(r.review_summary, r.review_refs.length ? `${r.review_refs.length} 份独立复核` : '尚无正式复核')}</dd></div><div><dt>下一步</dt><dd>{shortText(r.next_action ?? r.feedback_summary, '等待有信息增量的输入')}</dd></div></dl>
    {readyIndices.map(index => <button key={r.readiness[index].plan_ref} className={`ready-count nodrag ${data.historical ? 'historical' : ''}`} onClick={() => data.open(r.id, 'plan', r.readiness[index].plan_ref)}><strong>{data.historical ? '历史记录 · ' : ''}具备交易执行条件 · 截至 {formatTime(r.readiness[index].as_of)}</strong><span>{r.readiness[index].plan_ref} · {label(r.readiness[index].evidence_stage, '证据阶段未记录')}</span><small>有效截止 {formatTime(r.readiness[index].valid_until)} · 查看依据</small></button>)}
    <div className="card-actions nodrag"><button aria-expanded={data.expanded} onClick={() => data.toggleRound(r.id)}>{data.expanded ? '收起本轮' : '展开本轮'} <span>{data.expanded ? '−' : '+'}</span></button><button aria-expanded={data.descendantsOpen} disabled={!data.childrenCount} onClick={() => data.toggleBranch(r.id)}>{data.descendantsOpen ? '收起后继' : '展开后继'} <span>{data.childrenCount || '—'}</span></button></div>
    {data.expanded && <section className="round-materials nodrag" aria-label="本轮内部材料">
      <button onClick={() => data.open(r.id, 'plan')}><b>P · 研究方案 <em>{r.plan_refs.length}</em></b><span>{r.selected_plan_ref ? `主选 ${r.selected_plan_ref}` : r.plan_refs.length ? r.plan_refs.join('、') : '保留问题、机制与研究证据'}</span></button>
      <button onClick={() => data.open(r.id, 'review')}><b>R · 多日复核 <em>{r.review_refs.length}</em></b><span>{shortText(r.review_summary, '阶段、最终、未触发与修订均保留')}</span></button>
      <button onClick={() => data.open(r.id, 'feedback')}><b>F · 反馈与下一步 <em>{r.feedback_refs.length}</em></b><span>{shortText(r.feedback_summary, '事实、解释与采用决定分开记录')}</span></button>
    </section>}
    <Handle type="source" position={Position.Right} isConnectable={false} />
  </article>;
});
const nodeTypes = { round: ResearchCard };

function recordName(r: JsonRecord) { return String(r.record_ref ?? r.review_id ?? r.feedback_id ?? r.assessment_id ?? r.batch_id ?? r.decision_id ?? r.plan_ref ?? (r.plan_id ? `${r.plan_id}@${r.version ?? '?'}` : undefined) ?? r.round_id ?? r.record_id ?? '记录'); }
const fieldLabels: Record<string, string> = {
  research_question: '研究问题', question: '研究问题', hypothesis: '假设', mechanism: '机制', rules: '封存规则',
  counterevidence: '反证', baseline_comparison: '基线比较', metrics: '评价结果', limitations: '边界与缺项',
  evaluation_stage: '复核阶段', simulation_state: '跨日模拟状态', data_cutoff: '数据截止', available_at: '信息可得时间',
  supported_facts: '有证据的事实', interpretation: '原因解释', alternative_explanations: '其他解释', proposed_question: '待检验问题',
  what_changes: '计划改变', comparison: '比较设计', required_data: '需要的数据', scope: '适用范围', status: '状态',
  adoption_decision_refs: '反馈采用决定', adopted_feedback_refs: '已采用反馈', source_review_refs: '来源复核', derived_from_feedback_refs: '派生反馈',
  correction_reason: '修订原因', supersedes: '替代的旧复核', superseded_by: '后续修订', evidence_stage: '证据阶段',
  replay_eligibility: '可回放条件', effective_from: '评估生效时间', entry_valid_until: '新入场截止', evaluation_end: '原定评估终点',
  sealed_at: '本地封存时间', public_visibility_ref: '公开时间证明', selection_rationale: '主选理由', conclusion: '结论',
  next_action: '下一动作', title: '标题', summary: '摘要', trigger_status: '触发状态', checks: '条件逐项证据',
  product_refs: '产品', instrument_ref: '目标合约', additional_source_refs: '额外来源', purpose_kind: '研究类型',
  rules_summary: '规则摘要', reason: '判定原因', decisions: '采用决定', items: '批次处置', disposition: '处置',
};
function Value({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span className="muted">未知 / 未记录</span>;
  if (Array.isArray(value) && !value.length) return <span className="muted">未记录</span>;
  if (typeof value === 'object') return <pre>{JSON.stringify(value, null, 2)}</pre>;
  const text = String(value);
  // React text escaping is the sole renderer. No raw HTML or remote Markdown.
  return <span className="record-text">{fieldLabels[text] ?? label(text)}</span>;
}
function RecordPanel({ record, focus, snapshot }: { record: JsonRecord; focus?: boolean; snapshot: Snapshot }) {
  const [evidence, setEvidence] = useState<{ ref: string; value?: JsonRecord; error?: string }>();
  const [attachment, setAttachment] = useState<{ ref: string; text?: string; downloadUrl?: string; filename?: string; error?: string }>();
  useEffect(() => () => { if (attachment?.downloadUrl) URL.revokeObjectURL(attachment.downloadUrl); }, [attachment?.downloadUrl]);
  const fields = Object.entries(record).filter(([key]) => fieldLabels[key]);
  const refs = Array.from(new Set(Object.entries(record).filter(([key]) => key.endsWith('_refs') || key.endsWith('_ref')).flatMap(([, value]) => Array.isArray(value) ? value : [value]).filter((v): v is string => typeof v === 'string' && Boolean(snapshot.catalog.details[v]))));
  const allStrings: string[] = [];
  const collect = (value: unknown) => { if (typeof value === 'string') allStrings.push(value); else if (Array.isArray(value)) value.forEach(collect); else if (value && typeof value === 'object') Object.values(value).forEach(collect); };
  collect(record);
  const attachmentRefs = Array.from(new Set(allStrings.filter(s => snapshot.catalog.evidence?.[s])));
  const externalLinks = Array.from(new Set(allStrings.filter(s => { try { const u = new URL(s); return ['https:', 'http:'].includes(u.protocol) && !u.username && !u.password; } catch { return false; } })));
  return <article className={`record-panel ${focus ? 'focused-record' : ''}`} data-record-id={recordName(record)}>
    <div className="record-heading"><h3>{recordName(record)}</h3>{record.revision != null && <span className="status">修订 {String(record.revision)}</span>}</div>
    {!!record.supersedes && <p className="notice compact">这是新增修订；旧版 {String(record.supersedes)} 保留。</p>}
    <dl className="record-fields">{fields.map(([key, value]) => <div key={key}><dt>{fieldLabels[key]}</dt><dd><Value value={value} /></dd></div>)}</dl>
    {attachmentRefs.length > 0 && <section className="public-attachments"><b>公开证据附件</b>{attachmentRefs.map(ref => <button key={ref} onClick={async () => { setAttachment({ ref }); try { setAttachment({ ref, ...await loadEvidence(ref, snapshot) }); } catch (error) { setAttachment({ ref, error: String(error) }); } }}>核验并查看 {ref}</button>)}{attachment && <div>{attachment.error ? <p role="alert">{attachment.error}</p> : attachment.downloadUrl ? <><p className="muted">字节数与 SHA-256 已核验。</p>{attachment.text !== undefined && <pre>{attachment.text}</pre>}<a href={attachment.downloadUrl} download={attachment.filename}>下载已核验附件</a></> : <p>读取并核验附件…</p>}</div>}</section>}
    <details><summary>过程、证据与原件字段</summary><pre>{JSON.stringify(record, null, 2)}</pre>
      {externalLinks.length > 0 && <div className="external-links"><b>外部来源（离开本站）</b>{externalLinks.map(url => <a key={url} href={url} target="_blank" rel="noopener noreferrer">{url}</a>)}</div>}
      {refs.length > 0 && <div className="evidence-links">{refs.map(ref => <button key={ref} onClick={async () => { setEvidence({ ref }); try { setEvidence({ ref, value: await loadRecord(ref, snapshot) }); } catch (error) { setEvidence({ ref, error: String(error) }); } }}>查看 {ref}</button>)}</div>}
      {evidence && <section className="evidence-preview"><b>{evidence.ref}</b>{evidence.error ? <p role="alert">{evidence.error}</p> : evidence.value ? <pre>{JSON.stringify(evidence.value, null, 2)}</pre> : <p>读取已校验的公开证据…</p>}</section>}
    </details>
  </article>;
}

function Drawer({ state, snapshot, now, clockOkay, historical, close, open }: { state: DrawerState; snapshot: Snapshot; now: number; clockOkay: boolean; historical: boolean; close: () => void; open: (id: string, tab: Tab, ref?: string) => void }) {
  const drawerRef = useRef<HTMLElement>(null);
  const [tab, setTab] = useState<Tab>(state.tab);
  const [records, setRecords] = useState<{ ref: string; record?: JsonRecord; error?: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [batchProduct, setBatchProduct] = useState('');
  const [batchDate, setBatchDate] = useState('');
  const [activeBatch, setActiveBatch] = useState<JsonRecord>();
  const round = snapshot.catalog.nodes.find(n => n.id === state.roundId);
  useEffect(() => setTab(state.tab), [state.tab, state.roundId]);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    drawerRef.current?.querySelector<HTMLButtonElement>('button')?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); close(); }
      if (event.key === 'Tab') {
        const elements = Array.from(drawerRef.current?.querySelectorAll<HTMLElement>('button:not([disabled]),select,input,summary,a[href],[tabindex="0"]') ?? []).filter(el => el.getClientRects().length);
        if (!elements.length) return;
        const first = elements[0], last = elements[elements.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener('keydown', handler);
    return () => { document.removeEventListener('keydown', handler); previous?.focus(); };
  }, [close]);
  useEffect(() => {
    if (!round) return;
    let cancelled = false;
    const refs = tab === 'plan' ? [round.id, ...round.plan_refs] : tab === 'review' ? round.review_refs : round.feedback_refs;
    setLoading(true); setRecords([]);
    Promise.all(refs.map(async ref => { try { return { ref, record: await loadRecord(ref, snapshot) }; } catch (error) { return { ref, error: String(error) }; } })).then(next => { if (!cancelled) { setRecords(next); setLoading(false); } });
    return () => { cancelled = true; };
  }, [round, tab, snapshot]);
  const batchDay = (b: JsonRecord) => String(b.date ?? b.review_date ?? b.as_of ?? b.created_at ?? b.cutoff ?? '').slice(0, 10);
  const batches = snapshot.catalog.review_batches.filter(b => (!batchDate || batchDay(b) === batchDate) && (!batchProduct || JSON.stringify(b).toLocaleLowerCase().includes(batchProduct.toLocaleLowerCase())));
  async function selectBatch(batch: JsonRecord) {
    const ref = String(batch.batch_id ?? batch.id ?? '');
    if (snapshot.catalog.details[ref]) { try { setActiveBatch(await loadRecord(ref, snapshot)); } catch (error) { setActiveBatch({ batch_id: ref, error: String(error) }); } }
    else setActiveBatch(batch);
  }
  return <div className="drawer-layer"><button className="drawer-scrim" tabIndex={-1} onClick={close} aria-label="关闭详情背景" /><aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title" ref={drawerRef}>
    <header className="drawer-header"><div><div className="eyebrow">{state.daily ? '独立复核' : '研究轮次详情'}</div><h2 id="drawer-title">{state.daily ? '每日复核' : round?.title ?? '此快照没有该轮次'}</h2></div><button className="close-button" onClick={close} aria-label="关闭详情">关闭 <span>×</span></button></header>
    {state.daily ? <div className="drawer-body"><p className="muted">按原方案版本逐项复核。每日复核保留在原轮次内部，不增加研究代际。</p><div className="batch-filters"><label>日期<select value={batchDate} onChange={e => setBatchDate(e.target.value)}><option value="">全部日期</option>{Array.from(new Set(snapshot.catalog.review_batches.map(batchDay))).sort().reverse().map(date => <option key={date}>{date}</option>)}</select></label><label>产品<select value={batchProduct} onChange={e => setBatchProduct(e.target.value)}><option value="">全部产品</option>{uniqueProducts(snapshot.catalog.products).map(p => <option key={p.product_id} value={p.product_id}>{productName(p)}</option>)}</select></label></div>
      {!batches.length && <div className="drawer-empty">所选范围尚无已提交复核批次。</div>}
      {batches.map((batch, i) => <button className="batch-row" key={String(batch.batch_id ?? batch.id ?? i)} onClick={() => void selectBatch(batch)}><b>{batchDay(batch) || '日期未记录'}</b><span>{String(batch.batch_id ?? batch.id ?? '复核批次')}</span><small>{label(batch.status ?? batch.state, '已登记')} · {shortText(batch.summary, '查看逐项处置')}</small></button>)}
      {activeBatch && <section className="batch-detail"><h3>{String(activeBatch.batch_id ?? activeBatch.id ?? '批次')}</h3><pre>{JSON.stringify(activeBatch, null, 2)}</pre>{snapshot.catalog.nodes.flatMap(n => n.review_refs.map(ref => ({ n, ref }))).filter(({ ref }) => JSON.stringify(activeBatch).includes(`"${ref}"`)).map(({ n, ref }) => <button className="batch-review-link" key={ref} onClick={() => open(n.id, 'review', ref)}>定位 {ref} · {n.title}</button>)}</section>}
    </div> : round && <><nav className="drawer-tabs" aria-label="详情页签">{([['plan', '研究方案'], ['review', '复核历史'], ['feedback', '反馈与下一步']] as [Tab, string][]).map(([id, title]) => <button key={id} aria-current={tab === id ? 'page' : undefined} onClick={() => setTab(id)}>{title}</button>)}</nav><div className="drawer-body">
      <p className="detail-context">{round.id} · 第 {round.generation} 代 · {round.product_refs.map(id => productName(snapshot.catalog.products.find(p => p.product_id === id.split('@')[0]) ?? { product_id: id.split('@')[0] })).join(' / ')}<br />所选信息时点 {formatTime(snapshot.catalog.as_of)}</p>
      {tab === 'plan' && <>{!round.selected_plan_ref && round.plan_refs.length > 0 && <p className="notice">本轮未指定主选，以下候选分别展示，不按收益自动选取。</p>}{round.readiness.map((assessment, i) => <Readiness key={String(assessment.assessment_id ?? i)} assessment={assessment} historical={historical} state={readinessState(assessment, round, historical ? Date.parse(snapshot.catalog.as_of) : now, clockOkay, snapshot.catalog.mode, new Set([...Object.keys(snapshot.catalog.details), ...Object.keys(snapshot.catalog.evidence ?? {})]))} />)}<p className="account-note">执行条件仅针对所列方案版本与观察时点。账户适配未评估（NOT_ASSESSED）；不代表盈利、保证成交或交易授权。</p></>}
      {loading ? <p role="status">按需读取已校验记录…</p> : records.length ? records.map(item => item.record ? <RecordPanel key={`${snapshot.pointer.snapshot_id}-${item.ref}`} record={item.record} focus={state.ref === item.ref} snapshot={snapshot} /> : <p className="notice" key={item.ref}>{item.error}</p>) : <div className="drawer-empty">本轮尚无{tab === 'review' ? '正式复核' : tab === 'feedback' ? '反馈记录' : '已公开方案'}。缺项保留为未知。</div>}
    </div></>}
  </aside></div>;
}

function Observer() {
  const [prefs, setPrefs] = useState(initialPrefs);
  const [snapshot, setSnapshot] = useState<Snapshot>();
  const [history, setHistory] = useState<Pointer[]>([]);
  const [historyId, setHistoryId] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [onlyReady, setOnlyReady] = useState(false);
  const [drawer, setDrawer] = useState<DrawerState>();
  const [visibleLimit, setVisibleLimit] = useState(50);
  const [now, setNow] = useState(Date.now());
  const [clockOkay, setClockOkay] = useState(true);
  const [filterNotice, setFilterNotice] = useState('');
  const [measurements, setMeasurements] = useState<Record<string, { width: number; height: number }>>({});
  const [flow, setFlow] = useState<ReactFlowInstance<RoundNode>>();
  const loading = useRef(false);
  const clockAnchor = useRef({ wall: Date.now(), monotonic: performance.now() });
  const firstSnapshot = useRef(true);
  const focusTarget = useRef<string | undefined>(undefined);
  const currentSnapshotId = useRef('');
  const refresh = useCallback(async (pointer?: Pointer, navigation = false) => {
    if (loading.current) return;
    loading.current = true; setBusy(true);
    try {
      const next = await loadSnapshot(pointer);
      if (next.pointer.snapshot_id !== currentSnapshotId.current) { setSnapshot(next); currentSnapshotId.current = next.pointer.snapshot_id; }
      setHistoryId(pointer?.snapshot_id ?? '');
      if (navigation) { setDrawer(undefined); setPrefs(p => ({ ...p, product: '', direction: '', selected: undefined })); }
      setError('');
      if (firstSnapshot.current) {
        firstSnapshot.current = false;
        setPrefs(p => p.openBranches.length ? p : { ...p, openBranches: next.catalog.nodes.filter(n => !n.parent_round_id).slice(0, 12).map(n => n.id) });
      }
      try { setHistory(await loadHistory()); } catch { /* Latest remains valid if optional history index is absent. */ }
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { loading.current = false; setBusy(false); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => { if (historyId) return; const timer = setInterval(() => void refresh(), 60_000); return () => clearInterval(timer); }, [historyId, refresh]);
  useEffect(() => { const timer = setInterval(() => {
    const current = Date.now(); const elapsed = performance.now() - clockAnchor.current.monotonic;
    if (Math.abs(current - clockAnchor.current.wall - elapsed) > 120_000) setClockOkay(false);
    setNow(current);
  }, 1000); return () => clearInterval(timer); }, []);
  useEffect(() => {
    const deadlines = snapshot?.catalog.nodes.flatMap(n => n.readiness.map(a => Date.parse(a.valid_until ?? ''))).filter(t => Number.isFinite(t) && t > Date.now()) ?? [];
    if (!deadlines.length) return;
    const timer = setTimeout(() => setNow(Date.now()), Math.min(Math.min(...deadlines) - Date.now() + 1, 2_147_483_647));
    return () => clearTimeout(timer);
  }, [snapshot, now]);
  useEffect(() => { try { localStorage.setItem('research-observer-v1', JSON.stringify(prefs)); } catch { /* Browsing works without storage. */ } }, [prefs]);
  const catalog = snapshot?.catalog;
  const roundMap = useMemo(() => new Map(catalog?.nodes.map(n => [n.id, n]) ?? []), [catalog]);
  const childMap = useMemo(() => { const m = new Map<string, string[]>(); for (const n of catalog?.nodes ?? []) if (n.parent_round_id) m.set(n.parent_round_id, [...m.get(n.parent_round_id) ?? [], n.id]); return m; }, [catalog]);
  const clockIsValid = clockOkay && (!catalog || Date.parse(catalog.as_of) <= now + 120_000);
  const evaluationTime = historyId && catalog ? Date.parse(catalog.as_of) : now;
  const publicRefs = useMemo(() => new Set([...Object.keys(catalog?.details ?? {}), ...Object.keys(catalog?.evidence ?? {})]), [catalog]);
  const readinessSignature = (catalog?.nodes ?? []).flatMap(n => n.readiness.map(a => readinessState(a, n, evaluationTime, clockIsValid, catalog?.mode ?? '', publicRefs))).join('|');
  const readyMap = useMemo(() => new Map((catalog?.nodes ?? []).map(n => [n.id, n.readiness.map(a => readinessState(a, n, evaluationTime, clockIsValid, catalog?.mode ?? '', publicRefs))])), [catalog, readinessSignature]);
  const open = useCallback((id: string, tab: Tab, ref?: string) => { setPrefs(p => ({ ...p, selected: id })); setDrawer({ roundId: id, tab, ref }); }, []);
  const close = useCallback(() => setDrawer(undefined), []);
  const toggleRound = useCallback((id: string) => setPrefs(p => ({ ...p, openRounds: p.openRounds.includes(id) ? p.openRounds.filter(v => v !== id) : [...p.openRounds, id] })), []);
  const toggleBranch = useCallback((id: string) => setPrefs(p => ({ ...p, openBranches: p.openBranches.includes(id) ? p.openBranches.filter(v => v !== id) : [...p.openBranches, id] })), []);
  const onNodesChange = useCallback((changes: NodeChange<RoundNode>[]) => {
    // Preserve measured geometry when a fresh immutable snapshot recreates nodes.
    // Without this controlled-state bridge, a rapid snapshot switch can reset a
    // node to hidden while WebKit is still delivering its first ResizeObserver.
    setMeasurements(previous => {
      let next = previous;
      for (const change of changes) if (change.type === 'dimensions' && change.dimensions) {
        const known = previous[change.id];
        if (!known || known.width !== change.dimensions.width || known.height !== change.dimensions.height) {
          if (next === previous) next = { ...previous };
          next[change.id] = change.dimensions;
        }
      }
      return next;
    });
  }, []);
  const search = useMemo(() => {
    if (!catalog || !query.trim()) return [];
    const needle = query.toLocaleLowerCase();
    return catalog.search_index.filter(item => `${item.title} ${item.text} ${item.id}`.toLocaleLowerCase().includes(needle)).slice(0, 60);
  }, [catalog, query]);
  const productNames = useMemo(() => new Map(catalog?.products.map(p => [p.product_id, productName(p)]) ?? []), [catalog]);
  const directions = useMemo(() => Array.from(new Set(catalog?.nodes.map(directionLabel) ?? [])).sort(), [catalog]);
  useEffect(() => {
    if (!catalog) return;
    const invalidProduct = Boolean(prefs.product && !catalog.products.some(p => p.product_id === prefs.product));
    const invalidDirection = Boolean(prefs.direction && !directions.includes(prefs.direction));
    if (!invalidProduct && !invalidDirection) return;
    setPrefs(p => ({ ...p, product: invalidProduct ? '' : p.product, direction: invalidDirection ? '' : p.direction, selected: undefined }));
    setFilterNotice('已保存的筛选不在当前目录，已重置失效项并显示可用研究。');
  }, [catalog, directions, prefs.product, prefs.direction]);
  const visible = useMemo(() => {
    if (!catalog) return { nodes: [] as Round[], total: 0 };
    const included = new Set<string>();
    const filtering = Boolean(prefs.product || prefs.direction || onlyReady);
    for (const node of catalog.nodes) {
      if (prefs.product && !node.product_refs.some(ref => ref.split('@')[0] === prefs.product)) continue;
      if (prefs.direction && directionLabel(node) !== prefs.direction) continue;
      if (onlyReady && !readyMap.get(node.id)?.includes('EXECUTION_READY_AS_OF')) continue;
      included.add(node.id);
      let parent = node.parent_round_id;
      while (parent) { included.add(parent); parent = roundMap.get(parent)?.parent_round_id ?? null; }
    }
    const roots = catalog.nodes.filter(n => !n.parent_round_id);
    const walk: Round[] = []; const stack = [...roots].reverse(); const expanded = new Set(prefs.openBranches);
    while (stack.length) {
      const node = stack.pop()!; if (!included.has(node.id)) continue; walk.push(node);
      if (expanded.has(node.id) || filtering) for (const id of [...childMap.get(node.id) ?? []].reverse()) { const child = roundMap.get(id); if (child) stack.push(child); }
    }
    // Search is a deliberate navigation action: all ancestors remain visible even beyond a page boundary.
    const out = walk.slice(0, visibleLimit); const have = new Set(out.map(n => n.id));
    if (prefs.selected && roundMap.has(prefs.selected)) {
      let selected: Round | undefined = roundMap.get(prefs.selected);
      while (selected) { if (!have.has(selected.id)) { out.push(selected); have.add(selected.id); } selected = selected.parent_round_id ? roundMap.get(selected.parent_round_id) : undefined; }
    }
    return { nodes: out, total: walk.length };
  }, [catalog, prefs.product, prefs.direction, prefs.openBranches, prefs.selected, onlyReady, readyMap, roundMap, childMap, visibleLimit]);
  const graph = useMemo(() => {
    const shown = new Set(visible.nodes.map(n => n.id));
    const nodes: RoundNode[] = [];
    const openRounds = new Set(prefs.openRounds); const branches = new Set(prefs.openBranches);
    // Stable row order and explicit generation columns; a daily review cannot create a node.
    const rows = new Map<number, number>();
    for (const round of visible.nodes) {
      const row = rows.get(round.generation) ?? 0;
      const extra = openRounds.has(round.id) ? 235 : 0;
      nodes.push({ id: round.id, type: 'round', measured: measurements[round.id] ?? { width: 350, height: 260 + extra + ((readyMap.get(round.id)?.filter(s => s === 'EXECUTION_READY_AS_OF').length ?? 0) * 100) }, position: { x: (round.generation - 1) * 416, y: row }, draggable: false, connectable: false,
        selected: round.id === prefs.selected, ariaLabel: `${round.title} 第${round.generation}代`, data: { round, productLabel: round.product_refs.map(id => productNames.get(id.split('@')[0]) ?? id.split('@')[0].toUpperCase()).join(' / '), expanded: openRounds.has(round.id), descendantsOpen: branches.has(round.id), childrenCount: childMap.get(round.id)?.length ?? 0, historical: Boolean(historyId), readyStates: readyMap.get(round.id) ?? [], selected: round.id === prefs.selected, open, toggleRound, toggleBranch } });
      rows.set(round.generation, row + (measurements[round.id]?.height ?? (260 + extra + ((readyMap.get(round.id)?.filter(s => s === 'EXECUTION_READY_AS_OF').length ?? 0) * 100))) + 35);
    }
    const edges: Edge[] = visible.nodes.filter(n => n.parent_round_id && shown.has(n.parent_round_id)).map(n => ({ id: `${n.parent_round_id}:${n.id}`, source: n.parent_round_id!, target: n.id, type: 'smoothstep', animated: false, selectable: false, focusable: false, style: { stroke: '#91a59b', strokeWidth: 1.4 } }));
    return { nodes, edges };
  }, [visible.nodes, prefs.openRounds, prefs.openBranches, prefs.selected, childMap, historyId, readyMap, open, toggleRound, toggleBranch, productNames, measurements]);
  useEffect(() => {
    if (!focusTarget.current || !flow) return;
    const node = graph.nodes.find(n => n.id === focusTarget.current);
    if (node) { void flow.setCenter(node.position.x + 174, node.position.y + 125, { zoom: .95, duration: 220 }); focusTarget.current = undefined; }
  }, [flow, graph.nodes]);
  const locate = useCallback((id: string, tab?: Tab, ref?: string) => {
    const path: string[] = []; let node = roundMap.get(id);
    while (node?.parent_round_id) { path.push(node.parent_round_id); node = roundMap.get(node.parent_round_id); }
    focusTarget.current = id;
    setPrefs(p => ({ ...p, product: '', direction: '', selected: id, openBranches: Array.from(new Set([...p.openBranches, ...path])) }));
    setSearchOpen(false); setOnlyReady(false);
    if (tab) open(id, tab, ref);
  }, [roundMap, open]);
  const snapshotAge = catalog ? now - Date.parse(catalog.as_of) : 0;
  const stale = Boolean(error) || (!historyId && snapshotAge > 36 * 3600_000);
  return <div className="app-shell">
    <header className="masthead"><div className="brand-mark" aria-hidden="true"><span /><span /><span /></div><div><div className="eyebrow">PERSONAL RESEARCH / 个人研究</div><h1>策略研究树</h1></div><div className="masthead-note">让每个结论，都有来路。<span>研究 · 独立复核 · 持续演进</span></div></header>
    <main><section className="toolbar" aria-label="研究筛选"><label>产品<select aria-label="产品" value={prefs.product} onChange={e => { setPrefs(p => ({ ...p, product: e.target.value, selected: undefined })); setVisibleLimit(50); }}><option value="">全部产品</option>{uniqueProducts(catalog?.products ?? []).map(p => <option key={p.product_id} value={p.product_id}>{productName(p)}</option>)}</select></label><label>方向<select aria-label="方向" value={prefs.direction} onChange={e => { setPrefs(p => ({ ...p, direction: e.target.value, selected: undefined })); setVisibleLimit(50); }}><option value="">全部方向</option>{directions.map(d => <option key={d}>{d}</option>)}</select></label>
      <div className="search-box"><label htmlFor="history-search">全历史搜索</label><input id="history-search" value={query} placeholder="搜索问题、机制、轮次…" autoComplete="off" onFocus={() => setSearchOpen(true)} onChange={e => { setQuery(e.target.value); setSearchOpen(true); }} onKeyDown={e => { if (e.key === 'Escape') setSearchOpen(false); if (e.key === 'Enter' && search.length) locate(search[0].id); }} aria-expanded={searchOpen && Boolean(query)} aria-controls="search-results" />{searchOpen && query && <div className="search-results" id="search-results" role="region" aria-label="全历史搜索结果">{search.length ? search.map(result => <button key={result.id} onClick={() => locate(result.id)}><b>{result.title}</b><span>{result.id} · {result.ancestor_ids?.length ?? 0} 级祖先</span></button>) : <p>此快照内没有匹配记录。</p>}<small>覆盖折叠与未加载记录；选择结果会恢复祖先路径。</small></div>}</div>
      <label className="ready-filter"><input type="checkbox" checked={onlyReady} onChange={e => { setOnlyReady(e.target.checked); setPrefs(p => ({ ...p, selected: undefined })); }} />仅看条件齐备</label><button className="daily-button" onClick={() => setDrawer({ daily: true, tab: 'review' })}>每日复核 <span>↗</span></button>
    </section>
    <section className={`snapshot-bar ${stale ? 'stale' : ''}`} aria-label="数据新鲜度"><div><i className="freshness-dot" />{catalog ? `${historyId ? '历史时点' : stale ? '最后记录 · 陈旧' : '记录快照截至'} ${formatTime(catalog.as_of)}` : busy ? '读取完整快照…' : '尚未取得生产快照'}{catalog && <span className="snapshot-id">快照 {catalog.snapshot_id.slice(0, 12)}</span>}</div><div className="snapshot-actions"><select aria-label="历史快照" value={historyId} onChange={e => { const id = e.target.value; void refresh(history.find(h => h.snapshot_id === id), true); }}><option value="">最新公开记录</option>{history.map(h => <option key={h.snapshot_id} value={h.snapshot_id}>{formatTime(h.as_of)}</option>)}</select><button onClick={() => void refresh(history.find(h => h.snapshot_id === historyId))} disabled={busy}>{busy ? '读取中' : '刷新记录'}</button></div></section>
    <p className="snapshot-context">截至时间仅表示记录快照时点；发布任务当前运行状态未知。最新快照超过 36 小时显示陈旧。</p>
    {error && <div role="alert" className="notice">{error}。{snapshot ? '保留最后完整快照，尚未切换到新记录。' : '生产记录为空时不会加载示例。'}</div>}
    {filterNotice && <div className="filter-notice" role="status">{filterNotice}<button onClick={() => setFilterNotice('')}>知道了</button></div>}
    {!clockIsValid && <div role="alert" className="notice">浏览器时钟异常，无法确认当前时效；执行条件标志已降级。</div>}
    {catalog?.mode === 'SYNTHETIC_UI_ONLY' && <div className="notice">合成测试快照 · 仅用于界面验证，不是真实研究或执行条件证据。</div>}
    {!!catalog?.anomalies.length && <div className="notice">{catalog.anomalies.length} 项原档异常已显式隔离。<details><summary>查看遗漏与原因</summary><pre>{JSON.stringify(catalog.anomalies, null, 2)}</pre></details></div>}
    <section className="canvas" aria-label="研究轮次树" data-snapshot={catalog?.snapshot_id ?? ''} data-visible-count={graph.nodes.length}>
      <ReactFlow<RoundNode> nodes={graph.nodes} edges={graph.edges} nodeTypes={nodeTypes} onNodesChange={onNodesChange} onInit={setFlow} defaultViewport={prefs.viewport} onMoveEnd={(_, viewport) => setPrefs(p => ({ ...p, viewport }))} onNodeClick={(_, node) => setPrefs(p => ({ ...p, selected: node.id }))} onNodeDoubleClick={(_, node) => open(node.id, 'plan')} nodesDraggable={false} nodesConnectable={false} edgesReconnectable={false} deleteKeyCode={null} minZoom={.2} maxZoom={1.5} selectionOnDrag={false} selectNodesOnDrag={false} onlyRenderVisibleElements={false} attributionPosition="bottom-right"><Background gap={24} size={1} color="#d6dfd8" /><Controls showInteractive={false} fitViewOptions={{ padding: .2 }} /></ReactFlow>
      {!graph.nodes.length && <div className="empty-state"><div className="empty-icon" aria-hidden="true">⌘</div><h2>{catalog?.round_count ? '此范围暂无研究轮次' : '研究从一个好问题开始'}</h2><p>{catalog?.round_count ? '调整筛选可查看其他记录。历史与负结果仍保留。' : '尚无已完整提交的生产研究。新记录通过发布校验后，会自动出现在这里。'}</p><span>方案在本轮内部，后继走向下一代。</span></div>}
      <div className="canvas-caption"><span>{catalog ? `全历史 ${catalog.round_count.toLocaleString()} 轮 · 当前 ${graph.nodes.length} 轮` : '生产记录待读取'}<b>左 → 右 / 研究代际</b></span>{visible.total > visible.nodes.length && <button onClick={() => setVisibleLimit(v => v + 50)}>加载更多轮次 ({visible.total - visible.nodes.length})</button>}</div>
    </section>
    <footer className="page-footer"><span>一轮一卡 · P / R / F 属于本轮 · 多日复核保留在原轮次</span><span>研究观察页 · 不提供账户接入或交易操作 · <a href="./third-party-notices.txt">开源许可</a></span></footer>
    </main>
    {drawer && snapshot && <Drawer state={drawer} snapshot={snapshot} now={now} clockOkay={clockIsValid} historical={Boolean(historyId)} close={close} open={locate} />}
  </div>;
}
export default function App() { return <ReactFlowProvider><Observer /></ReactFlowProvider>; }
