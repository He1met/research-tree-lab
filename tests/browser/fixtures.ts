import { createHash } from 'node:crypto';
import type { Page } from '../../web/node_modules/@playwright/test/index.mjs';

// All content in this module is synthetic test input. Never publish these files.
// Production-shaped fields exercise fail-closed branches; they are not evidence.
export const hash = (text: string) => createHash('sha256').update(text).digest('hex');
export function fixture(count = 6, options: { roots?: boolean; readyForMs?: number; snapshotId?: string; correction?: boolean; old?: boolean } = {}) {
  const now = Date.now(); const at = new Date(now - 60_000).toISOString(); const valid = new Date(now + (options.readyForMs ?? 600_000)).toISOString();
  const snapshotId = options.snapshotId ?? `fixture-${count}${options.old ? '-old' : ''}${options.correction ? '-revision' : ''}`;
  const objects: Record<string, string> = {}; const details: Record<string, string> = {};
  const record = (ref: string, value: Record<string, unknown>) => { const raw = JSON.stringify({ schema_version: '1.0', available_at: at, ...value }); const url = `objects/${hash(raw)}.json`; objects[url] = raw; details[ref] = url; };
  const refs = ['target_contract_verified', 'rules_complete', 'execution_model_supported', 'quantity_cost_model_explicit', 'target_data_current', 'technical_validation_complete', 'references_intact'];
  const assessment = { schema_version: '1.0', synthetic: false, assessment_id: 'assessment-1', plan_ref: 'plan-1@1', state: 'EXECUTION_READY_AS_OF', policy_ref: 'execution-conditions-v1', as_of: at, valid_until: valid, effective_from: at, replay_eligible: true, account_eligibility: 'NOT_ASSESSED', automatic_trade_authorized: false, evidence_stage: 'HISTORICAL_VALIDATION', trigger_status: 'MET', trigger_evidence_refs: ['evidence-1'], checks: Object.fromEntries(refs.map(name => [name, { status: 'PASS', evidence_refs: ['evidence-1'], observed_at: at, valid_until: valid }])) };
  const nodes = Array.from({ length: count }, (_, i) => {
    const id = `round-${i + 1}`; const parent = !options.roots && i > 0 && i < 4 ? (i === 3 ? 'round-2' : 'round-1') : null;
    const generation = parent === 'round-2' ? 3 : parent ? 2 : 1;
    const node = { id, title: i === 0 ? '突破机制的成本边界' : i === 1 ? '反馈后继：检验成交滑点' : i === 2 ? '独立反证：少数事件依赖' : i === 3 ? '隐藏的深层检验' : `独立机制研究 ${i + 1}`, question: `研究问题 ${i + 1}`, mechanism: i % 2 ? '费用与成交' : '市场结构', product_refs: [i === 4 ? 'intc' : 'btc'], parent_round_id: parent, generation, plan_refs: i === 0 ? ['plan-1@1', 'plan-2@1'] : [], selected_plan_ref: null, review_refs: i === 0 ? ['review-1', 'review-2', ...(options.correction ? ['review-2-rev2'] : [])] : [], feedback_refs: i === 0 ? ['feedback-1'] : [], latest_review_ref: i === 0 ? 'review-2' : null, status: i === 2 ? 'FAILED' : 'COMPLETED', next_action: i === 0 ? '以更细路径检验成交歧义' : '等待新输入', plan_summary: '不将盈利作为规则完整的前提', review_summary: i === 0 ? options.correction ? '费用纠错 · 旧结果保留' : '2 日独立复核 · 阶段结果' : null, feedback_summary: i === 0 ? '反馈已采用；后继显式引用' : null, readiness: i === 0 ? [assessment] : [] };
    record(id, { round_id: id, title: node.title, question: node.question, mechanism: node.mechanism, additional_source_refs: i === 1 ? ['round-1', 'review-1'] : [], next_action: node.next_action });
    return node;
  });
  record('plan-1@1', { plan_ref: 'plan-1@1', plan_id: 'plan-1', version: 1, round_id: 'round-1', research_question: '突破是否对费用稳健', hypothesis: '净优势可能被成交摩擦消耗', evidence_stage: 'HISTORICAL_VALIDATION', rules: { signal: 'SYNTHETIC_TEST_ONLY', entry: '事先定义', exit: '按原规则', termination: '固定测试窗口' }, dataset_refs: ['evidence-1'], effective_from: at, entry_valid_until: valid, metrics: null });
  record('plan-2@1', { plan_ref: 'plan-2@1', round_id: 'round-1', research_question: '独立候选', evidence_stage: 'DEVELOPMENT', replay_eligibility: 'UNKNOWN', limitations: ['仅有参考数据，执行事实缺失'] });
  record('review-1', { review_id: 'review-1', plan_ref: 'plan-1@1', revision: 1, evaluation_stage: 'INTERIM', data_cutoff: at, metrics: [{ name: 'net_return_fraction', value: -.01 }], simulation_state: { inventory: 1, cash: 999, cumulative_fees: 1 }, limitations: ['这是合成界面测试'] });
  record('review-2', { review_id: 'review-2', plan_ref: 'plan-1@1', revision: 1, evaluation_stage: 'INTERIM', data_cutoff: at, metrics: [{ name: 'net_return_fraction', value: -.02 }], simulation_state: { inventory: 1, cash: 998, cumulative_fees: 2 } });
  if (options.correction) record('review-2-rev2', { review_id: 'review-2-rev2', plan_ref: 'plan-1@1', revision: 2, supersedes: 'review-2', correction_reason: '合成测试：补计资金费', evaluation_stage: 'INTERIM' });
  record('feedback-1', { feedback_id: 'feedback-1', review_ref: 'review-1', supported_facts: ['成本压力使净结果转负'], interpretation: '需要拆分信号与成交成本', proposed_question: '更细成交路径能否改变结论', status: 'ADOPTED', adoption_decision_refs: ['decision-1'] });
  record('decision-1', { decision_id: 'decision-1', status: 'ADOPTED', next_action: '由 round-2 检验', source_review_refs: ['review-1'] });
  record('evidence-1', { evidence_id: 'evidence-1', title: '合成测试证据', summary: 'SYNTHETIC — 不是真实行情或策略证据' });
  record('assessment-1', assessment);
  const batch = { batch_id: 'batch-1', date: '2026-09-22', product_refs: ['btc'], status: 'COMPLETED', items: [{ plan_ref: 'plan-1@1', review_ref: 'review-1', round_id: 'round-1', disposition: 'INTERIM' }, { plan_ref: 'plan-2@1', review_ref: 'review-2', round_id: 'round-1', disposition: 'DATA_MISSING' }] };
  record('batch-1', batch);
  const catalog = { schema_version: '1.0', snapshot_id: snapshotId, as_of: at, mode: 'PRODUCTION_NO_DEMO_FALLBACK', round_count: count, nodes, edges: nodes.filter(n => n.parent_round_id).map(n => ({ source: n.parent_round_id, target: n.id, relation: 'DERIVED_FROM' })), products: [{ product_id: 'btc', ticker: 'BTC', display_name: 'Bitcoin' }, ...(options.old ? [] : [{ product_id: 'intc', ticker: 'INTC', display_name: 'Intel' }])], review_batches: [batch], details, search_index: nodes.map(n => ({ id: n.id, title: n.title, text: `${n.question} ${n.mechanism} ${n.title}`, product_refs: n.product_refs, ancestor_ids: n.generation === 3 ? ['round-1', 'round-2'] : n.parent_round_id ? [n.parent_round_id] : [] })), shards: [], anomalies: [] };
  const pointer = { schema_version: '1.0', snapshot_id: snapshotId, as_of: at, generated_at: at, manifest_url: `snapshots/${snapshotId}/manifest.json`, catalog_url: `snapshots/${snapshotId}/catalog.json`, history_url: 'history.json' };
  const files: Record<string, string> = { ...objects };
  const seal = () => {
    Object.assign(files, objects);
    const raw = JSON.stringify(catalog);
    files[pointer.catalog_url] = raw;
    files[pointer.manifest_url] = JSON.stringify({ schema_version: '1.0', snapshot_id: snapshotId, as_of: at, files: [{ path: 'catalog.json', bytes: Buffer.byteLength(raw), sha256: hash(raw) }] });
    files['latest.json'] = JSON.stringify(pointer); files['history.json'] = JSON.stringify([pointer]);
    return files;
  };
  seal();
  return { catalog, pointer, files, seal, record, assessment };
}
export async function mockData(page: Page, current: ReturnType<typeof fixture>) {
  const state = { current, failures: new Set<string>(), overrides: {} as Record<string, string> };
  await page.route('**/data/**', async route => {
    const path = new URL(route.request().url()).pathname.split('/data/')[1];
    if (state.failures.has(path)) return route.fulfill({ status: 503, body: 'simulated publishing interruption' });
    const text = state.overrides[path] ?? state.current.files[path];
    await route.fulfill({ status: text === undefined ? 404 : 200, contentType: 'application/json', body: text ?? '{}' });
  });
  return state;
}
