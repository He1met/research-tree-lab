import { test, expect } from '../../web/node_modules/@playwright/test/index.mjs';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { fixture, mockData } from './fixtures';

async function scanAll(page: import('../../web/node_modules/@playwright/test/index.mjs').Page) {
  const section = page.getByRole('region', { name: '本轮相关材料' });
  await section.getByRole('button', { name: '查找相关材料', exact: true }).click();
  while (true) {
    await expect(section.getByRole('button', { name: '取消查找' })).toHaveCount(0);
    const next = section.getByRole('button', { name: '继续查找下一批' });
    if (await next.isDisabled()) break;
    await next.click();
  }
  return section;
}

test('genuine snapshot supplemental run evidence and decision open without changing graph or viewport', async ({ page }, info) => {
  const root = process.env.UI_REPLAY_DATA ? pathToFileURL(resolve(process.env.UI_REPLAY_DATA) + '/') : new URL('../../replay-data/', import.meta.url);
  const pointer = JSON.parse(readFileSync(new URL('latest.json', root), 'utf8'));
  expect(pointer.snapshot_id).toBe('f694bd01460d45258c9694856371a7e1ce2f8bfcabbf03f2430925cda1c9ee44');
  const objects = new Set<string>();
  await page.route('**/data/**', route => { const path = new URL(route.request().url()).pathname.split('/data/')[1]; if (path.startsWith('objects/')) objects.add(path); try { return route.fulfill({ contentType: 'application/json', body: readFileSync(new URL(path, root)) }); } catch { return route.fulfill({ status: 404, body: '{}' }); } });
  await page.goto('/');
  await expect(page.locator('.canvas')).toHaveAttribute('data-snapshot', pointer.snapshot_id);
  await page.getByLabel('全历史搜索', { exact: true }).fill('r-maintenance-tier-20260927');
  await page.locator('#search-results button').first().click();
  await page.waitForTimeout(300); // Wait for the deliberate graph navigation animation.
  const graph = await page.locator('.canvas').getAttribute('data-visible-count');
  const viewport = await page.locator('.react-flow__viewport').getAttribute('style');
  await page.locator('[data-round-id="r-maintenance-tier-20260927"] .card-title').click();
  await expect(page.getByRole('region', { name: '本轮相关材料' })).toContainText('已检查 0 /');
  expect(objects.size).toBeLessThanOrEqual(1);
  const section = await scanAll(page);
  for (const ref of ['run-tier-history-probe-20260927@attempt-1', 'e-tier-history-probe-20260927']) {
    await section.getByRole('button', { name: `打开 ${ref}`, exact: true }).click();
    await expect(section.locator(`[data-record-id="${ref}"]`)).toBeVisible();
    await section.locator(`[data-record-id="${ref}"]`).scrollIntoViewIfNeeded();
    await page.screenshot({ path: info.outputPath(`${ref.replace('@', '-')}.png`), fullPage: true });
  }
  await page.getByRole('button', { name: '反馈与下一步', exact: true }).click();
  const feedback = await scanAll(page);
  const decision = 'decision-tier-history-probe-20260927';
  await feedback.getByRole('button', { name: `打开 ${decision}`, exact: true }).click();
  await expect(feedback.locator(`[data-record-id="${decision}"]`)).toBeVisible();
  await feedback.locator(`[data-record-id="${decision}"]`).scrollIntoViewIfNeeded();
  await page.screenshot({ path: info.outputPath('genuine-decision.png'), fullPage: true });
  expect(await page.locator('.canvas').getAttribute('data-visible-count')).toBe(graph);
  expect(await page.locator('.react-flow__viewport').getAttribute('style')).toBe(viewport);
  await expect(page.locator('[data-round-id="r-maintenance-tier-20260927"]')).toHaveClass(/selected/);
});

test('explicit associations only, page limit, failure, cancellation and snapshot reset', async ({ page }) => {
  await page.clock.install();
  const current = fixture(1);
  for (let i = 0; i < 25; i++) current.record(`aaa-${i.toString().padStart(2, '0')}`, { evidence_id: `aaa-${i}`, input_record_refs: i === 1 ? ['round-1'] : ['other'] });
  current.record('run-round-1-guessed', { run_id: 'run-round-1-guessed', round_id: 'other' });
  current.record('decision-real', { decision_id: 'decision-real', source_round_ref: 'round-1' });
  current.seal(); const state = await mockData(page, current);
  state.failures.add(current.catalog.details['aaa-02']);
  await page.goto('/'); await page.locator('[data-round-id="round-1"] .card-title').click();
  const section = page.getByRole('region', { name: '本轮相关材料' });
  await section.getByRole('button', { name: '查找相关材料', exact: true }).click();
  await expect(section).toContainText('已检查 10 /');
  await expect(section).toContainText('读取失败 1 条');
  await expect(section.getByRole('button', { name: '打开 aaa-01', exact: true })).toBeVisible();
  await expect(section.getByRole('button', { name: /guessed/ })).toHaveCount(0);
  await page.route(`**/data/${current.catalog.details['aaa-10']}`, async route => { await new Promise(r => setTimeout(r, 400)); await route.fulfill({ body: current.files[current.catalog.details['aaa-10']] }); });
  await section.getByRole('button', { name: '继续查找下一批' }).click();
  await section.getByRole('button', { name: '取消查找' }).click();
  await expect(section).toContainText('已取消');
  await expect(section).toContainText('已检查 10 /');
  state.current = fixture(1, { snapshotId: 'new-snapshot' });
  await page.clock.fastForward(60_000);
  await expect(section).toContainText('已检查 0 /');
  await expect(section.getByRole('button', { name: '打开 aaa-01', exact: true })).toHaveCount(0);
});

test('loadRecord cached new-to-old time and membership gates, oversized scan and corrupted hashes', async ({ page }) => {
  const current = fixture(1); current.record('future', { evidence_id: 'future' });
  current.record('oversized', { evidence_id: 'oversized', summary: 'a'.repeat(1_000_001) }); current.seal();
  const state = await mockData(page, current); state.overrides[current.catalog.details['plan-2@1']] = '{}';
  await page.goto('/');
  const results = await page.evaluate(async () => {
    // Vite module access is confined to this local engineering test.
    const data = await import(/* @vite-ignore */ '/src/data.ts');
    const snapshot = await data.loadSnapshot(); await data.loadRecord('future', snapshot);
    const old = { ...snapshot, catalog: { ...snapshot.catalog, as_of: '2000-01-01T00:00:00Z' } };
    const missing = { ...snapshot, catalog: { ...snapshot.catalog, details: {} } };
    const errors = [];
    for (const [ref, snap, opts] of [['future', old, {}], ['future', missing, {}], ['oversized', snapshot, { maxBytes: 1_000_000 }], ['plan-2@1', snapshot, {}]]) {
      try { await data.loadRecord(ref, snap, opts); errors.push('UNEXPECTED_PASS'); } catch (error) { errors.push(String(error)); }
    }
    return errors;
  });
  expect(results[0]).toContain('晚于所选历史时点'); expect(results[1]).toContain('没有公开');
  expect(results[2]).toContain('超出读取范围'); expect(results[3]).toContain('完整性校验失败');
});
