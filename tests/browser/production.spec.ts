import { test, expect } from '../../web/node_modules/@playwright/test/index.mjs';
import { readFileSync, existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const root = fileURLToPath(new URL('../../', import.meta.url));
test('current genuine public projection renders and exposes verified research evidence', async ({ page, browser }, info) => {
  const dataRoot = join(root, 'site/data');
  test.skip(!existsSync(join(dataRoot, 'latest.json')), 'No genuine public projection has been generated in this checkout');
  const pointer = JSON.parse(readFileSync(join(dataRoot, 'latest.json'), 'utf8'));
  const catalog = JSON.parse(readFileSync(join(dataRoot, pointer.catalog_url), 'utf8'));
  test.skip(catalog.nodes.length === 0, 'Genuine production catalog is empty; synthetic tests verify empty state');
  await page.route('**/data/**', route => { const path = new URL(route.request().url()).pathname.split('/data/')[1]; try { return route.fulfill({ contentType: 'application/json', body: readFileSync(join(dataRoot, path)) }); } catch { return route.fulfill({ status: 404, body: '{}' }); } });
  const errors: string[] = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.locator('.canvas')).toHaveAttribute('data-snapshot', pointer.snapshot_id);
  await expect(page.locator('[data-round-id]')).toHaveCount(catalog.nodes.length);
  const first = catalog.nodes.find((n: { id: string; parent_round_id: string | null }) => {
    const detail = JSON.parse(readFileSync(join(dataRoot, catalog.details[n.id]), 'utf8'));
    return !n.parent_round_id && detail.public_attachment_refs?.length;
  }) ?? catalog.nodes.find((n: { parent_round_id: string | null }) => !n.parent_round_id);
  await expect(page.locator(`[data-round-id="${first.id}"] .status`)).not.toContainText('_');
  await page.screenshot({ path: info.outputPath('genuine-research-desktop.png'), fullPage: true });
  await page.locator(`[data-round-id="${first.id}"] .card-title`).click();
  await expect(page.locator(`[data-record-id="${first.id}"]`)).toBeVisible();
  const attachments = page.getByRole('button', { name: /^核验并查看 / });
  if (Object.keys(catalog.evidence ?? {}).length) await expect(attachments.first()).toBeVisible();
  const actualAttachmentChecked = (await attachments.count()) > 0;
  if (actualAttachmentChecked) { await attachments.first().click(); await expect(page.getByText('字节数与 SHA-256 已核验。').first()).toBeVisible(); }
  await page.screenshot({ path: info.outputPath('genuine-evidence-drawer.png'), fullPage: true });
  await page.keyboard.press('Escape'); await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: info.outputPath('genuine-research-mobile.png'), fullPage: true });
  expect(errors).toEqual([]);
  const artifacts = join(root, 'tests/browser/artifacts'); mkdirSync(artifacts, { recursive: true });
  writeFileSync(join(artifacts, `${info.project.name}-genuine-projection.json`), JSON.stringify({ classification: 'GENUINE_LOCAL_PUBLIC_PROJECTION_BROWSER_CHECK_NOT_PAGES_READBACK', snapshot_id: pointer.snapshot_id, as_of: catalog.as_of, round_count: catalog.round_count, browser: info.project.name, browserVersion: browser.version(), actualAttachmentChecked, errors, at: new Date().toISOString() }, null, 2));
});
