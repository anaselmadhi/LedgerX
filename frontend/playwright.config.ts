import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list'], ['json', { outputFile: '../artifacts/frontend-browser-results.json' }]],
  outputDir: '../artifacts/frontend-browser',
  use: { screenshot: 'only-on-failure', trace: 'off' },
  projects: [
    {
      name: 'desktop',
      testMatch: '**/ui.spec.ts',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1000 } },
    },
    {
      name: 'mobile',
      testMatch: '**/ui.spec.ts',
      use: { ...devices['iPhone 13'], defaultBrowserType: 'chromium' },
    },
    ...(process.env.LEDGERX_LIVE_URL
      ? [
          {
            name: 'live-api',
            testMatch: '**/live.spec.ts',
            use: { baseURL: process.env.LEDGERX_LIVE_URL, viewport: { width: 1440, height: 1000 } },
          },
        ]
      : []),
  ],
});
