import { test, expect } from '../../web/node_modules/@playwright/test/index.mjs';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { fixture, mockData } from './fixtures';

const oldId = 'fc28e27632c4aa5b13d17036924d7ab4cf22352009e9a6913d27c06d8706b3c8';
const latestId = '9c5613454eda3a3bf1e0fa285f79028c329de18b59e0e6f88aafb4f39ac84d8e';
const dataRoot = process.env.UI_REPLAY_DATA ? pathToFileURL(resolve(process.env.UI_REPLAY_DATA) + '/') : new URL('../../replay-data/', import.meta.url);
async function scanAll(page: import('../../web/node_modules/@playwright/test/index.mjs').Page) {
  const section = page.getByRole('region', { name: '独立资料与发现' });
  await section.getByRole('button', { name: '查找资料（每批10条）', exact: true }).click();
  while (true) {
    await expect(section.getByRole('button', { name: '取消资料查找' })).toHaveCount(0);
    const next = section.getByRole('button', { name: '继续查找资料（下一批10条）' });
    if (await next.isDisabled()) break;
    await next.click();
  }
  return section;
}

for (const snapshotId of [oldId, latestId]) test(`real documentary discovery ${snapshotId.slice(0, 8)} stays proposed with verified attachment`, async ({ page }, info) => {
  const catalog = JSON.parse(readFileSync(new URL(`snapshots/${snapshotId}/catalog.json`, dataRoot), 'utf8'));
  const pointer = { schema_version: '1.0', snapshot_id: snapshotId, as_of: catalog.as_of, catalog_url: `snapshots/${snapshotId}/catalog.json`, manifest_url: `snapshots/${snapshotId}/manifest.json` };
  const requests = new Set<string>();
  await page.route('**/data/**', route => {
    const path = new URL(route.request().url()).pathname.split('/data/')[1]; requests.add(path);
    try { return route.fulfill({ body: path === 'latest.json' ? JSON.stringify(pointer) : path === 'history.json' ? JSON.stringify([pointer]) : readFileSync(new URL(path, dataRoot)) }); }
    catch { return route.fulfill({ status: 404, body: '{}' }); }
  });
  await page.goto('/'); await expect(page.locator('.canvas')).toHaveAttribute('data-snapshot', snapshotId);
  const graph = await page.locator('.canvas').getAttribute('data-visible-count');
  const viewport = await page.locator('.react-flow__viewport').getAttribute('style');
  await page.getByRole('button', { name: '资料与发现 ↗', exact: true }).click();
  await expect(page.getByRole('region', { name: '独立资料与发现' })).toContainText('已检查 0 /');
  expect([...requests].filter(path => path.startsWith('objects/'))).toHaveLength(0);
  const section = await scanAll(page); await section.getByLabel('资料搜索', { exact: true }).fill('异步');
  for (const ref of ['discovery-async-covariance-20260928', 'e-async-covariance-20260928']) {
    await section.locator('.batch-row').filter({ hasText: ref }).click();
    const record = section.locator(`[data-record-id="${ref}"]`); await expect(record).toBeVisible();
    if (ref.startsWith('discovery')) await expect(record).toContainText('PROPOSED_NOT_STARTED');
    await record.scrollIntoViewIfNeeded(); await page.screenshot({ path: info.outputPath(`${ref}.png`), fullPage: true });
    await record.getByRole('button', { name: /核验并查看 .*REPORT.md/ }).click();
    await expect(record).toContainText('字节数与 SHA-256 已核验。');
  }
  expect(await page.locator('.canvas').getAttribute('data-visible-count')).toBe(graph);
  expect(await page.locator('.react-flow__viewport').getAttribute('style')).toBe(viewport);
  expect(catalog.nodes.some((n: { id: string }) => n.id === 'discovery-async-covariance-20260928')).toBe(false);
});

test('document scan is bounded, cancellable, failure-aware and reset on snapshot refresh', async ({ page }) => {
  await page.clock.install(); const current = fixture(1);
  for (let i = 0; i < 25; i++) current.record(`aaa-${i.toString().padStart(2, '0')}`, { record_type: 'discovery', discovery_id: `aaa-${i}`, status: 'PROPOSED_NOT_STARTED', title: '合成资料' });
  current.seal(); const state = await mockData(page, current); state.failures.add(current.catalog.details['aaa-02']);
  await page.goto('/'); await page.getByRole('button', { name: '资料与发现 ↗', exact: true }).click();
  const section = page.getByRole('region', { name: '独立资料与发现' });
  await section.getByRole('button', { name: '查找资料（每批10条）', exact: true }).click();
  await expect(section).toContainText('已检查 10 /'); await expect(section).toContainText('读取失败 1 条');
  await page.route(`**/data/${current.catalog.details['aaa-10']}`, async route => { await new Promise(r => setTimeout(r, 400)); await route.fulfill({ body: current.files[current.catalog.details['aaa-10']] }); });
  await section.getByRole('button', { name: '继续查找资料（下一批10条）' }).click();
  await section.getByRole('button', { name: '取消资料查找' }).click(); await expect(section).toContainText('已取消');
  state.current = fixture(1, { snapshotId: 'new-doc-snapshot' }); await page.clock.fastForward(60_000);
  await expect(section).toContainText('已检查 0 /'); await expect(section.locator('.batch-row')).toHaveCount(0);
});
