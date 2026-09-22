import { test, expect } from '../../web/node_modules/@playwright/test/index.mjs';
import { execFileSync } from 'node:child_process';
import { readdirSync, readFileSync, mkdirSync, mkdtempSync, writeFileSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

const root = fileURLToPath(new URL('../../', import.meta.url));
function sourceHashes() { return Object.fromEntries(readdirSync(join(root, 'web/src')).sort().map(name => [name, createHash('sha256').update(readFileSync(join(root, 'web/src', name))).digest('hex')])); }
test('C05: complete-manifest append → actual projector → browser refresh, web/src unchanged', async ({ page }, info) => {
  const base = join(root, 'tests/browser/artifacts/integration'); mkdirSync(base, { recursive: true });
  const work = mkdtempSync(join(base, `${info.project.name}-`)); const before = sourceHashes();
  const run = (phase: string) => JSON.parse(execFileSync('python3', [join(root, 'tests/browser/commit_fixture.py'), phase, work], { cwd: root, encoding: 'utf8' }));
  const first = run('initial');
  await page.route('**/data/**', route => { const path = new URL(route.request().url()).pathname.split('/data/')[1]; try { return route.fulfill({ contentType: 'application/json', body: readFileSync(resolve(work, 'data', path)) }); } catch { return route.fulfill({ status: 404, body: '{}' }); } });
  await page.goto('/'); await expect(page.locator('[data-round-id="C05-root"]')).toBeVisible();
  await expect(page.locator('[data-round-id]')).toHaveCount(1);
  const second = run('append');
  await page.getByRole('button', { name: '刷新记录' }).click();
  await expect(page.locator('[data-round-id]')).toHaveCount(3);
  await expect(page.locator('[data-round-id="C05-root"]')).toHaveAttribute('data-generation', '1');
  await expect(page.locator('[data-round-id="C05-child"]')).toHaveAttribute('data-generation', '2');
  await expect(page.locator('[data-round-id="C05-independent"]')).toHaveAttribute('data-generation', '1');
  await page.locator('[data-round-id="C05-root"] .card-title').click();
  await page.getByRole('button', { name: '复核历史', exact: true }).click();
  await expect(page.locator('[data-record-id="C05-review"]')).toBeVisible();
  await page.getByRole('button', { name: '反馈与下一步', exact: true }).click();
  await expect(page.locator('[data-record-id="C05-feedback"]')).toBeVisible();
  const after = sourceHashes(); expect(after).toEqual(before);
  writeFileSync(join(base, `${info.project.name}-receipt.json`), JSON.stringify({ classification: 'SYNTHETIC_FILE_PIPELINE_TEST', first, second, sourceHashesBefore: before, sourceHashesAfter: after, equal: true, checkedAt: new Date().toISOString() }, null, 2));
});
