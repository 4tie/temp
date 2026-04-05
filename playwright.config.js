// @ts-check
const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/playwright',
  timeout: 45_000,
  expect: {
    timeout: 8_000,
  },
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: '.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 5173',
    url: 'http://127.0.0.1:5173/healthz',
    reuseExistingServer: true,
    timeout: 90_000,
  },
});
