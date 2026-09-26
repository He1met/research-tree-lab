export type JsonRecord = Record<string, unknown>;
export type Assessment = JsonRecord & { plan_ref?: string; state?: string; as_of?: string; valid_until?: string; evidence_stage?: string };
export type Round = {
  id: string; title: string; question?: string; mechanism?: string; purpose_kind?: string;
  product_refs: string[]; parent_round_id: string | null; generation: number;
  plan_refs: string[]; selected_plan_ref: string | null; review_refs: string[]; feedback_refs: string[];
  latest_review_ref?: string; status?: string; next_action?: unknown; plan_summary?: unknown;
  review_summary?: unknown; feedback_summary?: unknown; readiness: Assessment[];
};
export type SearchEntry = { id: string; title: string; text: string; ancestor_ids: string[]; product_refs: string[] };
export type Product = { product_id: string; display_name?: string; name?: string; ticker?: string; reference_underlying?: { ticker?: string } };
export type Catalog = {
  schema_version: string; snapshot_id: string; as_of: string; mode: string; round_count: number;
  nodes: Round[]; edges: { source: string; target: string; relation?: string }[];
  products: Product[]; review_batches: JsonRecord[]; search_index: SearchEntry[];
  details: Record<string, string>; anomalies: unknown[];
  evidence?: Record<string, { url: string; sha256: string; bytes: number }>;
};
export type Pointer = { schema_version?: string; snapshot_id: string; catalog_url: string; manifest_url: string; as_of: string; generated_at?: string; history_url?: string };
export type Snapshot = { pointer: Pointer; catalog: Catalog; receivedAt: number };
const dataBase = new URL(`${import.meta.env.BASE_URL}data/`, window.location.href);
const schema = '1.0';
const timestamp = (value: unknown) => typeof value === 'string' && /(Z|[+-]\d{2}:\d{2})$/.test(value) ? Date.parse(value) : NaN;

// File references are data capabilities, never arbitrary fetch/download URLs.
export function safeDataUrl(path: string): string {
  if (!/^(latest\.json|history\.json|snapshots\/[A-Za-z0-9_-]+\/(manifest|catalog)\.json|objects\/[a-f0-9]{64}\.json|evidence\/[a-f0-9]{64}\.(txt|md|json|csv|tsv|py|js|ts|pdf|png|jpg|jpeg|webp|zip|gz))$/.test(path)) {
    throw new Error('公开文件路径不符合白名单');
  }
  const url = new URL(path, dataBase);
  if (url.origin !== dataBase.origin || !url.pathname.startsWith(dataBase.pathname)) throw new Error('禁止越界文件引用');
  return url.href;
}

async function fetchText(path: string, signal?: AbortSignal, maxBytes = 30_000_000) {
  const response = await fetch(safeDataUrl(path), { cache: 'no-store', signal, credentials: 'omit', redirect: 'error' });
  if (!response.ok) throw new Error(`公开快照读取失败（HTTP ${response.status}）`);
  const reader = response.body?.getReader();
  if (!reader) throw new Error('公开文件没有可读正文');
  const chunks: Uint8Array[] = []; let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read(); if (done) break;
      size += value.byteLength;
      if (size > maxBytes) throw new Error('单个公开文件超出读取范围');
      chunks.push(value);
    }
  } finally { await reader.cancel(); }
  const bytes = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  return new TextDecoder().decode(bytes);
}
async function digest(text: string) {
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return Array.from(new Uint8Array(bytes), b => b.toString(16).padStart(2, '0')).join('');
}
function assertSchema(value: JsonRecord) {
  if (![1, '1', schema].includes(value.schema_version as string)) throw new Error(`暂不支持 schema ${String(value.schema_version ?? '未标明')}；保留最后记录`);
}
export async function loadSnapshot(pointer?: Pointer, signal?: AbortSignal): Promise<Snapshot> {
  const next: Pointer = pointer ?? JSON.parse(await fetchText('latest.json', signal));
  assertSchema(next as JsonRecord);
  if (!next.snapshot_id || !next.manifest_url || !next.catalog_url) throw new Error('快照指针不完整');
  const manifest = JSON.parse(await fetchText(next.manifest_url, signal));
  assertSchema(manifest);
  if (manifest.snapshot_id !== next.snapshot_id) throw new Error('快照 manifest 身份不匹配');
  const entry = manifest.files?.find((f: JsonRecord) => f.path === 'catalog.json');
  if (!entry?.sha256 || !Number.isInteger(entry.bytes)) throw new Error('快照缺少完整目录校验');
  const raw = await fetchText(next.catalog_url, signal);
  if (new TextEncoder().encode(raw).length !== entry.bytes || await digest(raw) !== entry.sha256) throw new Error('快照目录完整性校验失败');
  const catalog: Catalog = JSON.parse(raw);
  assertSchema(catalog as unknown as JsonRecord);
  if (catalog.snapshot_id !== next.snapshot_id || catalog.as_of !== next.as_of || !Number.isFinite(timestamp(catalog.as_of)) || !Array.isArray(catalog.nodes)) throw new Error('快照目录身份或时点不匹配');
  if (!['PRODUCTION_NO_DEMO_FALLBACK', 'SYNTHETIC_UI_ONLY'].includes(catalog.mode)) throw new Error('未支持的快照模式');
  const ids = new Set<string>();
  for (const node of catalog.nodes) {
    if (!node.id || ids.has(node.id)) throw new Error('轮次标识缺失或重复');
    ids.add(node.id);
    node.product_refs ??= []; node.plan_refs ??= []; node.review_refs ??= []; node.feedback_refs ??= []; node.readiness ??= [];
  }
  for (const node of catalog.nodes) if (node.parent_round_id && !ids.has(node.parent_round_id)) throw new Error('快照缺少派生祖先，不能显示为独立根');
  const parentMap = new Map(catalog.nodes.map(n => [n.id, n.parent_round_id]));
  const checked = new Set<string>();
  for (const node of catalog.nodes) {
    const chain = new Set<string>(); let current: string | null | undefined = node.id;
    while (current && !checked.has(current)) { if (chain.has(current)) throw new Error('轮次关系包含循环'); chain.add(current); current = parentMap.get(current); }
    for (const id of chain) checked.add(id);
  }
  catalog.products ??= []; catalog.review_batches ??= []; catalog.search_index ??= []; catalog.details ??= {}; catalog.anomalies ??= [];
  return { pointer: next, catalog, receivedAt: Date.now() };
}
export async function loadHistory(): Promise<Pointer[]> {
  const value = JSON.parse(await fetchText('history.json'));
  const entries = Array.isArray(value) ? value : value.snapshots;
  if (!Array.isArray(entries)) throw new Error('历史快照目录不可读');
  return entries.map((p: Pointer) => ({ ...p, schema_version: p.schema_version ?? schema })).sort((a, b) => b.as_of.localeCompare(a.as_of));
}
const detailCache = new Map<string, { value: JsonRecord; bytes: number }>();
export async function loadRecord(ref: string, snapshot: Snapshot, options: { signal?: AbortSignal; maxBytes?: number } = {}): Promise<JsonRecord> {
  const path = snapshot.catalog.details[ref];
  if (!path) throw new Error(`此快照没有公开该记录：${ref}`);
  options.signal?.throwIfAborted();
  let entry = detailCache.get(path);
  if (!entry) {
    const text = await fetchText(path, options.signal, options.maxBytes);
    const expected = path.match(/^objects\/([a-f0-9]{64})\.json$/)?.[1];
    if (!expected || await digest(text) !== expected) throw new Error('详情记录完整性校验失败');
    const value: JsonRecord = JSON.parse(text); assertSchema(value);
    entry = { value, bytes: new TextEncoder().encode(text).byteLength };
  }
  options.signal?.throwIfAborted();
  if (entry.bytes > (options.maxBytes ?? 30_000_000)) throw new Error('单个公开文件超出读取范围');
  const { value } = entry;
  const available = value.available_at ?? value.created_at;
  if (available != null && !Number.isFinite(timestamp(available))) throw new Error('记录信息时点无法核实');
  if (typeof available === 'string' && timestamp(available) > timestamp(snapshot.catalog.as_of)) throw new Error('记录晚于所选历史时点');
  // Recheck the selected time even on a content-addressed cache hit.
  if (!detailCache.has(path)) { if (detailCache.size >= 128) detailCache.delete(detailCache.keys().next().value!); detailCache.set(path, entry); }
  return value;
}
export async function loadEvidence(ref: string, snapshot: Snapshot): Promise<{ text?: string; downloadUrl: string; filename: string }> {
  const entry = snapshot.catalog.evidence?.[ref];
  if (!entry || !entry.url.includes(entry.sha256) || !/^[a-f0-9]{64}$/.test(entry.sha256)) throw new Error('附件没有当前快照允许公开的完整引用');
  const response = await fetch(safeDataUrl(entry.url), { cache: 'no-store', credentials: 'omit', redirect: 'error' });
  if (!response.ok) throw new Error(`附件读取失败（HTTP ${response.status}）`);
  const bytes = await response.arrayBuffer();
  const digestBytes = await crypto.subtle.digest('SHA-256', bytes);
  const actual = Array.from(new Uint8Array(digestBytes), b => b.toString(16).padStart(2, '0')).join('');
  if (actual !== entry.sha256 || bytes.byteLength !== entry.bytes) throw new Error('附件完整性校验失败');
  const text = /\.(txt|md|json|csv|tsv|py|js|ts)$/.test(entry.url) ? new TextDecoder().decode(bytes) : undefined;
  return { text, downloadUrl: URL.createObjectURL(new Blob([bytes], { type: 'application/octet-stream' })), filename: entry.url.split('/').at(-1)! };
}
export function shortText(value: unknown, fallback = '尚未记录'): string {
  if (value === null || value === undefined || value === '') return fallback;
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.length ? value.map(v => shortText(v, '')).join(' · ') : fallback;
  if (typeof value === 'object') {
    const obj = value as JsonRecord;
    return shortText(obj.summary ?? obj.title ?? obj.status ?? obj.description ?? obj.action ?? obj.text ?? obj.next_action, fallback);
  }
  return String(value);
}
export function formatTime(value: unknown) {
  if (typeof value !== 'string' || !Number.isFinite(Date.parse(value))) return '未记录';
  return new Intl.DateTimeFormat('zh-CN', { timeZoneName: 'short', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value));
}
export const stateLabels: Record<string, string> = {
  EXECUTION_READY_AS_OF: '具备交易执行条件', RULES_READY_WAITING_TRIGGER: '规则齐备 · 待触发',
  REPLAYABLE_ONLY: '可回放 · 执行待核实', RESEARCH_ONLY: '仅供研究 / 条件不完整',
  EXPIRED: '已过期', INVALIDATED: '已失效', UNKNOWN: '执行条件待核实', NOT_YET_EFFECTIVE: '尚未生效', DEMO_ONLY: '合成示例',
  COMPLETED: '已完成', COMMITTED: '已封存', RUNNING: '研究中', FAILED: '执行失败', WAITING_NEW_DATA: '等待新数据',
  WAITING_NATURAL_OUTCOME: '等待自然观察', DORMANT: '休眠', PROPOSED: '待执行', NOT_TRIGGERED: '未触发',
  FINAL: '最终复核', INTERIM: '阶段复核', PARTIAL: '阶段复核', DATA_MISSING: '缺少数据', NOT_EVALUATED: '待复核',
  DEVELOPMENT: '开发证据', HISTORICAL_VALIDATION: '历史验证', FORWARD_SIMULATION: '前向模拟',
};
export function label(value: unknown, fallback = '待记录') { const text = shortText(value, fallback); return stateLabels[text] ?? text; }
export function productName(product: Product) {
  const name = product.ticker ?? product.reference_underlying?.ticker ?? product.display_name ?? product.name ?? product.product_id;
  return /^[a-z0-9.]{1,8}$/.test(name) ? name.toUpperCase() : name;
}
export function uniqueProducts(products: Product[]) { return Array.from(new Map(products.map(p => [p.product_id, p])).values()); }
export function statusLabel(status: unknown) {
  const raw = shortText(status, '');
  if (stateLabels[raw]) return stateLabels[raw];
  if (raw.includes('CORRECTION') || raw.includes('RECHECK')) return '修订后待复查';
  if (raw.includes('FAILED') || raw.includes('ERROR')) return '执行失败';
  if (raw.includes('INCOMPLETE') || raw.includes('MISSING')) return '已封存 · 数据待补';
  if (raw.includes('WAITING') || raw.startsWith('WAIT')) return '等待新数据';
  if (raw.includes('COMPLETED')) return raw.includes('BOUNDARY') ? '已完成 · 明确数据边界' : '已完成';
  if (raw.includes('SEALED')) return '已封存';
  if (raw.includes('RUNNING') || raw.includes('PROGRESS')) return '研究中';
  if (raw.includes('DORMANT') || raw.includes('PAUSED')) return '休眠';
  return /^[\u3400-\u9fff\s·，、]{1,20}$/.test(raw) ? raw : '研究记录';
}
export function directionLabel(round: Round) {
  const kind = round.purpose_kind ?? '';
  if (/COUNTEREVIDENCE|FALSIFICATION|BOUNDARY/.test(kind)) return '反证与边界';
  if (/COST|EXPOSURE/.test(kind)) return '费用与暴露';
  if (/DATA|METHOD|FEASIBILITY/.test(kind)) return '数据与方法';
  if (/INDEPENDENT|DISCOVERY|NEW_MECHANISM/.test(kind)) return '独立新机制';
  if (/REPLICATION|REPRODUC/.test(kind)) return '独立复现';
  if (/COMPAR|CANDIDATE/.test(kind)) return '候选比较';
  if (/DEEP|FOLLOW|SUCCESSOR/.test(kind)) return '后继深化';
  if (/REPAIR|CORRECT/.test(kind)) return '纠错检验';
  if (/^[\u3400-\u9fff\s·，、]{1,14}$/.test(kind)) return kind;
  const mechanism = round.mechanism ?? '';
  return /^[\u3400-\u9fff\s·，、]{1,14}$/.test(mechanism) ? mechanism : '机制研究';
}
const requiredChecks = ['target_contract_verified', 'rules_complete', 'execution_model_supported', 'quantity_cost_model_explicit', 'target_data_current', 'technical_validation_complete', 'references_intact'];
export function readinessState(a: Assessment, round: Round, now: number, clockOkay: boolean, mode: string, publicRefs?: Set<string>) {
  // The browser may only preserve or downgrade a verified publisher decision.
  if (mode !== 'PRODUCTION_NO_DEMO_FALLBACK' || a.synthetic !== false) return 'DEMO_ONLY';
  if (![1, '1', schema].includes(a.schema_version as string) || !a.plan_ref || !round.plan_refs.includes(a.plan_ref) || !a.plan_ref.includes('@')) return 'UNKNOWN';
  if (a.invalidated === true || a.state === 'INVALIDATED') return 'INVALIDATED';
  const valid = timestamp(a.valid_until); const asOf = timestamp(a.as_of);
  if (!clockOkay || !Number.isFinite(valid) || !Number.isFinite(asOf) || valid <= asOf || asOf > now + 60_000) return 'UNKNOWN';
  if (now >= valid) return 'EXPIRED';
  if (a.state !== 'EXECUTION_READY_AS_OF') return a.state ?? 'UNKNOWN';
  const checks = a.checks as Record<string, JsonRecord> | undefined;
  if (a.policy_ref !== 'execution-conditions-v1' || a.account_eligibility !== 'NOT_ASSESSED' || a.automatic_trade_authorized !== false || a.trigger_status !== 'MET' || !Array.isArray(a.trigger_evidence_refs) || !a.trigger_evidence_refs.length) return 'UNKNOWN';
  if (publicRefs && !a.trigger_evidence_refs.every(ref => publicRefs.has(String(ref)))) return 'UNKNOWN';
  const effective = timestamp(a.effective_from);
  if (!Number.isFinite(effective) || effective > now) return 'NOT_YET_EFFECTIVE';
  for (const name of requiredChecks) {
    const check = checks?.[name];
    if (!check || check.status !== 'PASS' || !Array.isArray(check.evidence_refs) || !check.evidence_refs.length) return 'UNKNOWN';
    if (publicRefs && !check.evidence_refs.every(ref => publicRefs.has(String(ref)))) return 'UNKNOWN';
    const observed = timestamp(check.observed_at); const end = timestamp(check.valid_until);
    if (!Number.isFinite(observed) || !Number.isFinite(end) || observed > asOf || end < valid) return 'UNKNOWN';
  }
  return 'EXECUTION_READY_AS_OF';
}
