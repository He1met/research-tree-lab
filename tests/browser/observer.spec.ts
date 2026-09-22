import { test, expect } from '../../web/node_modules/@playwright/test/index.mjs';
import { fixture, hash, mockData } from './fixtures';
import { writeFileSync, mkdirSync } from 'node:fs';
import { cpus, platform, release, arch, totalmem } from 'node:os';
import { fileURLToPath } from 'node:url';

test('C01-C04: real React Flow, rounds contain P/R/F, independent expansion and candidates', async ({ page }) => {
  await mockData(page, fixture()); await page.goto('/');
  await expect(page.locator('.react-flow')).toBeVisible();
  const first = page.locator('[data-round-id="round-1"]');
  await expect(page.locator('[data-round-id="round-2"]')).toBeVisible();
  await expect(page.locator('[data-round-id="round-2"]')).toHaveAttribute('data-generation', '2');
  await first.getByRole('button', { name: '展开本轮' }).click();
  await expect(first.getByLabel('本轮内部材料')).toBeVisible();
  await first.getByRole('button', { name: '收起后继' }).click();
  await expect(page.locator('[data-round-id="round-2"]')).toHaveCount(0);
  await expect(first.getByLabel('本轮内部材料')).toBeVisible();
  await first.getByRole('button', { name: '展开后继' }).click();
  await first.getByRole('button', { name: '收起本轮' }).click();
  await expect(page.locator('[data-round-id="round-2"]')).toBeVisible();
  await first.getByRole('button', { name: '突破机制的成本边界' }).click();
  await expect(page.getByText('本轮未指定主选，以下候选分别展示，不按收益自动选取。')).toBeVisible();
  await expect(page.locator('[data-record-id="plan-1@1"]')).toBeVisible();
  await expect(page.locator('[data-record-id="plan-2@1"]')).toBeVisible();
  await expect(page.locator('[data-readiness="EXECUTION_READY_AS_OF"]')).toHaveCount(1);
  await page.keyboard.press('Escape'); await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('C06: search unloaded descendant restores ancestor chain without duplicate source nodes', async ({ page }) => {
  await mockData(page, fixture()); await page.goto('/');
  await expect(page.locator('[data-round-id="round-4"]')).toHaveCount(0);
  await page.getByLabel('全历史搜索', { exact: true }).fill('隐藏的深层');
  await page.getByRole('button', { name: /隐藏的深层检验.*round-4/ }).click();
  for (const id of ['round-1', 'round-2', 'round-4']) await expect(page.locator(`[data-round-id="${id}"]`)).toHaveCount(1);
  await expect(page.locator('[data-round-id="round-4"]')).toHaveAttribute('data-generation', '3');
  expect(await page.locator('.react-flow__edge').count()).toBe(3);
});

test('C07/B10: daily drawer locates exact review; multi-day revisions coexist', async ({ page }) => {
  await mockData(page, fixture(6, { correction: true })); await page.goto('/');
  await page.getByRole('button', { name: '每日复核' }).click();
  await page.getByRole('button', { name: /2026-09-22.*batch-1/ }).click();
  await page.getByRole('button', { name: '定位 review-1 · 突破机制的成本边界' }).click();
  for (const id of ['review-1', 'review-2', 'review-2-rev2']) await expect(page.locator(`[data-record-id="${id}"]`)).toBeVisible();
  await expect(page.locator('[data-record-id="review-1"]')).toHaveClass(/focused-record/);
  await expect(page.getByText('这是新增修订；旧版 review-2 保留。')).toBeVisible();
  await expect(page.locator('[data-round-id="round-1"]')).toHaveAttribute('data-generation', '1');
});

test('C08: selecting immutable historical snapshot excludes future products, revisions and adoption', async ({ page }) => {
  const latest = fixture(6, { correction: true }); const old = fixture(1, { old: true });
  old.catalog.nodes[0].feedback_refs = []; old.catalog.nodes[0].review_refs = ['review-1']; old.catalog.nodes[0].feedback_summary = null;
  delete old.catalog.details['feedback-1']; delete old.catalog.details['decision-1']; delete old.catalog.details['review-2']; old.seal();
  const state = await mockData(page, latest);
  Object.assign(state.overrides, old.files); state.overrides['latest.json'] = latest.files['latest.json']; state.overrides['history.json'] = JSON.stringify([latest.pointer, old.pointer]);
  await page.goto('/'); await page.getByLabel('历史快照').selectOption(old.pointer.snapshot_id);
  await expect(page.locator('.canvas')).toHaveAttribute('data-snapshot', old.pointer.snapshot_id);
  await expect(page.getByLabel('产品', { exact: true }).locator('option')).toHaveCount(2);
  await page.locator('[data-round-id="round-1"] .card-title').click();
  await page.getByRole('button', { name: '复核历史', exact: true }).click();
  await expect(page.locator('[data-record-id="review-1"]')).toBeVisible();
  await expect(page.locator('[data-record-id="review-2-rev2"]')).toHaveCount(0);
  await page.getByRole('button', { name: '反馈与下一步', exact: true }).click();
  await expect(page.getByText('本轮尚无反馈记录。缺项保留为未知。')).toBeVisible();
});

test('C09/E08: atomic refresh preserves viewport and selection; interrupted snapshot keeps old data', async ({ page }) => {
  const original = fixture(); const state = await mockData(page, original); await page.goto('/');
  await page.locator('[data-round-id="round-1"] .card-title').click(); await page.keyboard.press('Escape');
  await page.locator('.react-flow__controls-zoomin').click();
  const transform = await page.locator('.react-flow__viewport').getAttribute('style');
  state.current = fixture(7, { snapshotId: 'new-result' }); state.failures.add(state.current.pointer.catalog_url);
  await page.getByRole('button', { name: '刷新记录' }).click();
  await expect(page.getByRole('alert')).toContainText('保留最后完整快照');
  await expect(page.locator('.canvas')).toHaveAttribute('data-snapshot', original.pointer.snapshot_id);
  expect(await page.locator('.react-flow__viewport').getAttribute('style')).toBe(transform);
  state.failures.clear(); await page.getByRole('button', { name: '刷新记录' }).click();
  await expect(page.locator('.canvas')).toHaveAttribute('data-snapshot', 'new-result');
  await expect(page.locator('[data-round-id="round-1"]')).toHaveClass(/selected/);
  expect(await page.locator('.react-flow__viewport').getAttribute('style')).toBe(transform);
  await expect(page.locator('[data-round-id="round-7"]')).toHaveCount(1);
});

test('D03-D05: precise plan badge expires while page stays open; refresh does not renew it', async ({ page }) => {
  await page.clock.install({ time: Date.now() });
  const f = fixture(6, { readyForMs: 3000 }); await mockData(page, f); await page.goto('/');
  await page.locator('[data-round-id="round-1"] .card-title').click();
  await expect(page.locator('[data-readiness="EXECUTION_READY_AS_OF"]')).toHaveCount(1);
  await page.clock.runFor(5000);
  await expect(page.locator('[data-readiness="EXPIRED"]')).toHaveCount(1);
  await expect(page.locator('.ready-count')).toHaveCount(0);
  await page.keyboard.press('Escape'); await page.getByRole('button', { name: '刷新记录' }).click();
  await page.locator('[data-round-id="round-1"] .card-title').click();
  await expect(page.locator('[data-readiness="EXPIRED"]')).toHaveCount(1);
  await expect(page.getByText(/账户适配未评估/)).toBeVisible();
});

for (const scenario of ['synthetic', 'missing-evidence', 'unknown-schema', 'invalidated', 'unbound-plan', 'unavailable-evidence', 'naive-time']) test(`D01/D06: fail-closed readiness ${scenario}`, async ({ page }) => {
  const f = fixture();
  if (scenario === 'synthetic') f.assessment.synthetic = true;
  if (scenario === 'missing-evidence') f.assessment.checks.rules_complete.evidence_refs = [];
  if (scenario === 'unknown-schema') f.assessment.schema_version = '9.0';
  if (scenario === 'invalidated') Object.assign(f.assessment, { invalidated: true });
  if (scenario === 'unbound-plan') f.assessment.plan_ref = 'other-plan@1';
  if (scenario === 'unavailable-evidence') delete f.catalog.details['evidence-1'];
  if (scenario === 'naive-time') f.assessment.as_of = f.assessment.as_of.replace('Z', '');
  f.seal(); await mockData(page, f); await page.goto('/'); await expect(page.locator('[data-round-id="round-1"]')).toBeVisible();
  await expect(page.locator('.ready-count')).toHaveCount(0);
});

test('stale persisted filters are cleared visibly; product versions remain catalog-driven', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('research-observer-v1', JSON.stringify({ product: 'unregistered-product', direction: 'Former long English mechanism', openRounds: [], openBranches: [], viewport: { x: 38, y: 46, zoom: .88 } })));
  const f = fixture(); f.catalog.nodes[0].product_refs = ['btc@observed-v1']; f.seal(); await mockData(page, f); await page.goto('/');
  await expect(page.getByText('已保存的筛选不在当前目录，已重置失效项并显示可用研究。')).toBeVisible();
  await expect(page.getByLabel('产品', { exact: true })).toHaveValue('');
  await expect(page.getByLabel('方向', { exact: true })).toHaveValue('');
  await page.getByLabel('产品', { exact: true }).selectOption('btc');
  await expect(page.locator('[data-round-id="round-1"]')).toBeVisible();
  await expect(page.locator('[data-round-id="round-5"]')).toHaveCount(0);
  const node = page.locator('.react-flow__node[data-id="round-1"]'); const before = await node.evaluate(el => (el as HTMLElement).style.transform);
  await node.focus(); await page.keyboard.press('ArrowRight'); await page.keyboard.press('Delete');
  expect(await node.evaluate(el => (el as HTMLElement).style.transform)).toBe(before);
  await expect(node).toHaveCount(1);
});

test('browser clock jump removes current-ready badges', async ({ page }) => {
  await page.clock.install({ time: Date.now() }); await mockData(page, fixture(6, { readyForMs: 24 * 3600_000 })); await page.goto('/');
  await expect(page.locator('.ready-count')).toHaveCount(1);
  await page.clock.setSystemTime(Date.now() + 4 * 3600_000); await page.clock.runFor(1100);
  await expect(page.getByRole('alert')).toContainText('浏览器时钟异常');
  await expect(page.locator('.ready-count')).toHaveCount(0);
});

test('C10: 390px drawer, keyboard controls and Escape', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 }); await mockData(page, fixture()); await page.goto('/');
  await expect(page.getByRole('button', { name: '每日复核' })).toBeVisible();
  await page.getByRole('button', { name: '每日复核' }).focus(); await page.keyboard.press('Enter');
  await expect(page.getByRole('dialog')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.keyboard.press('Tab'); expect(await page.evaluate(() => Boolean(document.activeElement?.closest('[role="dialog"]')))).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('mobile-390.png'), fullPage: true });
  await page.keyboard.press('Escape'); await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('button', { name: '每日复核' })).toBeFocused();
});

test('C12: text escaping, path escape refusal, safe attachments and external links', async ({ page }) => {
  const f = fixture(); const attack = '<img src=x onerror="window.__xss=1"><script>window.__xss=1</script>';
  f.catalog.nodes[0].title = attack;
  const publicText = 'SYNTHETIC TEST ONLY\n<img src=x onerror="window.__xss=1">'; const sha = hash(publicText); const evidenceUrl = `evidence/${sha}.txt`;
  Object.assign(f.catalog, { evidence: { 'bundle:test/evidence.txt': { url: evidenceUrl, sha256: sha, bytes: Buffer.byteLength(publicText) } } });
  f.record('plan-1@1', { plan_ref: 'plan-1@1', research_question: attack, dataset_refs: ['bundle:test/evidence.txt'], source_url: 'https://example.org/source', malicious_url: 'javascript:window.__xss=1' });
  f.files[evidenceUrl] = publicText;
  f.catalog.details['plan-2@1'] = '../../private.json';
  f.seal();
  await mockData(page, f); await page.goto('/'); await page.locator('[data-round-id="round-1"] .card-title').click();
  await expect(page.locator('[data-record-id="plan-1@1"]')).toBeVisible();
  await expect(page.getByText(/公开文件路径不符合白名单/)).toBeVisible();
  await page.getByRole('button', { name: '核验并查看 bundle:test/evidence.txt' }).click();
  await expect(page.getByText('字节数与 SHA-256 已核验。')).toBeVisible();
  expect(await page.evaluate(() => (window as unknown as Record<string, unknown>).__xss)).toBeUndefined();
  await expect(page.locator('.drawer img,.drawer script')).toHaveCount(0);
  await page.locator('[data-record-id="plan-1@1"] summary').click();
  await expect(page.locator('a[href="https://example.org/source"]')).toHaveAttribute('rel', 'noopener noreferrer');
  await expect(page.locator('a[href^="javascript:"]')).toHaveCount(0);
});

test('C12/E11: corrupt and unsupported snapshots never replace current complete state', async ({ page }) => {
  const f = fixture(); const state = await mockData(page, f); await page.goto('/');
  await expect(page.locator('[data-round-id="round-1"]')).toBeVisible();
  state.overrides[f.pointer.catalog_url] = '{}'; await page.getByRole('button', { name: '刷新记录' }).click();
  await expect(page.getByRole('alert')).toContainText('完整性校验失败');
  await expect(page.locator('[data-round-id="round-1"]')).toBeVisible();
  state.overrides['latest.json'] = JSON.stringify({ ...f.pointer, schema_version: '9.0' }); await page.getByRole('button', { name: '刷新记录' }).click();
  await expect(page.getByRole('alert')).toContainText('暂不支持 schema 9.0');
});

test('C01: empty production remains empty without synthetic fallback', async ({ page }, testInfo) => {
  const f = fixture(0); f.catalog.review_batches = []; f.catalog.products = []; f.seal(); await mockData(page, f); await page.goto('/');
  await expect(page.getByRole('heading', { name: '研究从一个好问题开始' })).toBeVisible();
  await expect(page.locator('[data-round-id]')).toHaveCount(0);
  await expect(page.locator('.canvas')).toHaveAttribute('data-visible-count', '0');
  await page.screenshot({ path: testInfo.outputPath('production-empty.png'), fullPage: true });
});

for (const total of [1000, 10000]) for (const visible of [50, 100, 200]) test(`C11: synthetic history ${total}, rendered ${visible}`, async ({ page, browser }, testInfo) => {
  test.setTimeout(90_000);
  const f = fixture(total, { roots: true }); await mockData(page, f);
  const started = performance.now(); await page.goto('/'); await expect(page.locator('.canvas')).toHaveAttribute('data-visible-count', '50');
  for (let loaded = 50; loaded < visible; loaded += 50) await page.getByRole('button', { name: /加载更多轮次/ }).click();
  await expect(page.locator('.react-flow__node')).toHaveCount(visible);
  const renderedMs = performance.now() - started;
  const searchStarted = performance.now(); await page.getByLabel('全历史搜索', { exact: true }).fill(`独立机制研究 ${total}`);
  await expect(page.getByRole('button', { name: new RegExp(`独立机制研究 ${total}.*round-${total}`) })).toBeVisible();
  const searchMs = performance.now() - searchStarted;
  const panStarted = performance.now(); await page.keyboard.press('Escape'); await page.locator('.react-flow__controls-zoomin').click();
  const panMs = performance.now() - panStarted;
  const receipt = { classification: 'SYNTHETIC_BROWSER_PERFORMANCE_ONLY', browser: testInfo.project.name, version: browser.version(), platform: platform(), release: release(), architecture: arch(), cpu: cpus()[0]?.model, cpuCores: cpus().length, memoryGB: +(totalmem() / 1024 ** 3).toFixed(1), viewport: page.viewportSize(), totalHistory: total, renderedNodes: visible, firstRenderAndExpansionMs: +renderedMs.toFixed(1), searchToResultMs: +searchMs.toFixed(1), zoomClickMs: +panMs.toFixed(1), catalogBytes: Buffer.byteLength(f.files[f.pointer.catalog_url]), actualDomNodes: await page.locator('.react-flow__node').count(), at: new Date().toISOString() };
  const dir = fileURLToPath(new URL('./artifacts/scale/', import.meta.url)); mkdirSync(dir, { recursive: true }); writeFileSync(`${dir}${testInfo.project.name}-${total}-${visible}.json`, JSON.stringify(receipt, null, 2));
  if (total === 1000 && visible === 50) await page.screenshot({ path: testInfo.outputPath('scale-1000-visible-50.png'), fullPage: true });
});
