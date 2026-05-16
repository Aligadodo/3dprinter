import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // jsdom for DOM API (canvas, events, etc.)
    environment: 'jsdom',
    // Look for tests in tests/frontend/
    include: ['tests/frontend/**/*.test.js'],
    // Setup file: mock LiteGraph global
    setupFiles: ['tests/frontend/setup.js'],
  },
});
