// @ts-check
const { defineConfig, devices } = require('@playwright/test');

process.env.TMPDIR ??= '/tmp';
process.env.TEMP ??= '/tmp';
process.env.TMP ??= '/tmp';

module.exports = defineConfig({
  testDir: './tests/playwright',
  timeout: 45_000,
  expect: {
    timeout: 8_000,
  },
  use: {
    baseURL: 'http://127.0.0.1:5417',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: '4t\\Scripts\\python.exe run.py start --foreground --no-reload --port 5417',
    url: 'http://127.0.0.1:5417/healthz',
    reuseExistingServer: true,
    timeout: 90_000,
  },
});
