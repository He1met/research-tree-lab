import { defineConfig, devices } from '@playwright/test';
export default defineConfig({
  testDir: '../tests/browser',
  outputDir: '../tests/browser/artifacts/results',
  timeout: 40_000,
  expect: { timeout: 8000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['json', { outputFile: '../tests/browser/artifacts/playwright-results.json' }]],
  use: { baseURL: 'http://127.0.0.1:5173', viewport: { width: 1440, height: 1000 }, trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }, { name: 'webkit', use: { ...devices['Desktop Safari'] } }],
  webServer: { command: 'npm run dev -- --port 5173 --strictPort', port: 5173, reuseExistingServer: true },
});
