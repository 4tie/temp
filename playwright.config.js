const { defineConfig, devices } = require('@playwright/test');
const path = require('path');

const pythonPath = path.resolve(__dirname, '4t', 'Scripts', 'python.exe');

module.exports = defineConfig({
  testDir: './tests/playwright',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? 'html' : 'line',
  use: {
    baseURL: 'http://127.0.0.1:8000',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: `"${pythonPath}" run.py start --foreground --no-reload --port 8000`,
    url: 'http://127.0.0.1:8000/healthz',
    reuseExistingServer: true,
    timeout: 120000,
  },
});
