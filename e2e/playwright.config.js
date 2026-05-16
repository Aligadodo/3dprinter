/* e2e/playwright.config.js — Playwright configuration for 3D Print Pipeline */

import { defineConfig, devices } from '@playwright/test';

const SERVER_PORT = 8080;
const BASE_URL = `http://127.0.0.1:${SERVER_PORT}`;

export default defineConfig({
  testDir: '.',
  testMatch: '**/*.spec.js',
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  workers: 1,
  timeout: 30000,

  use: {
    baseURL: BASE_URL,
    browserName: 'chromium',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    headless: true,
  },

  // Start the Python dev server before tests, stop after
  webServer: {
    command: `python start-server.py --port ${SERVER_PORT} --no-browser`,
    url: `${BASE_URL}/api/node-types`,
    reuseExistingServer: true,
    timeout: 15000,
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
