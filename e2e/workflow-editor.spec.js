/* e2e/workflow-editor.spec.js — Playwright E2E tests for workflow editor */

import { test, expect } from '@playwright/test';

const EDITOR_URL = '/#/workflows/editor/new';

test.describe('Workflow Editor', () => {

  test.beforeEach(async ({ page }) => {
    // Go to editor page
    await page.goto(EDITOR_URL);

    // Wait for the editor canvas to appear
    await page.waitForSelector('#wf-canvas', { timeout: 10000 });
    // Wait for LiteGraph to load from CDN and templates to be ready
    await page.waitForFunction(() => {
      return typeof window.LiteGraph !== 'undefined'
        && window.LiteGraph.LGraph
        && document.querySelector('#wf-canvas');
    }, { timeout: 15000 });
  });

  // ── Template Loading ────────────────────────────────────────────────

  test('clicking "Basic" template loads 2 nodes into the canvas', async ({ page }) => {
    // Click the "Basic" template button
    await page.click('button:has-text("Basic")');

    // Check that canvas contains nodes
    // LiteGraph renders into a canvas element, nodes are in memory not DOM
    const nodeCount = await page.evaluate(() => {
      if (!window.wfGraph || !window.wfGraph._nodes) return 0;
      return window.wfGraph._nodes.length;
    });

    expect(nodeCount).toBeGreaterThanOrEqual(2);
  });

  test('clicking "Text→Image" template loads 3 nodes', async ({ page }) => {
    await page.click('button:has-text("Text→Image")');

    const nodeCount = await page.evaluate(() => {
      if (!window.wfGraph || !window.wfGraph._nodes) return 0;
      return window.wfGraph._nodes.length;
    });

    expect(nodeCount).toBeGreaterThanOrEqual(3);
  });

  test('clicking "Print Ready" template loads 3 nodes', async ({ page }) => {
    await page.click('button:has-text("Print Ready")');

    const nodeCount = await page.evaluate(() => {
      if (!window.wfGraph || !window.wfGraph._nodes) return 0;
      return window.wfGraph._nodes.length;
    });

    expect(nodeCount).toBeGreaterThanOrEqual(3);
  });

  test('clicking "Full Pipeline" template loads 4 nodes', async ({ page }) => {
    await page.click('button:has-text("Full Pipeline")');

    const nodeCount = await page.evaluate(() => {
      if (!window.wfGraph || !window.wfGraph._nodes) return 0;
      return window.wfGraph._nodes.length;
    });

    expect(nodeCount).toBeGreaterThanOrEqual(4);
  });

  // ── Drag & Drop from Palette ────────────────────────────────────────

  test('palette items are visible', async ({ page }) => {
    // Palette items should be in the sidebar
    const paletteItems = await page.$$('.wf-palette-item');
    expect(paletteItems.length).toBeGreaterThan(0);
  });

  // ── Inspector Panel ─────────────────────────────────────────────────

  test('inspector panel shows info when a node is selected', async ({ page }) => {
    // First load a template so we have nodes
    await page.click('button:has-text("Basic")');

    // Click a node on the canvas — LiteGraph handles this via canvas events
    // Use evaluate to simulate node selection
    await page.evaluate(() => {
      if (!window.wfGraph || !window.wfGraph._nodes || !window.wfGraph._nodes.length) return;
      var node = window.wfGraph._nodes[0];
      if (window.wfCanvas && window.wfCanvas.onNodeSelected) {
        window.wfCanvas.onNodeSelected(node);
      }
    });

    // Inspector should now be visible (not display:none)
    const inspectorVisible = await page.evaluate(() => {
      var panel = document.getElementById('wf-inspector');
      return panel && panel.style.display !== 'none';
    });
    expect(inspectorVisible).toBe(true);
  });

  // ── Fit Button ──────────────────────────────────────────────────────

  test('fit button does not throw errors', async ({ page }) => {
    // Load a template first
    await page.click('button:has-text("Full Pipeline")');

    // Collect any console errors after clicking Fit
    const errors = [];
    page.on('pageerror', err => errors.push(err));

    // Click the Fit button
    await page.click('button:has-text("Fit")');

    // Wait a bit for any potential errors
    await page.waitForTimeout(500);

    expect(errors).toHaveLength(0);
  });

  // ── Clear Button ────────────────────────────────────────────────────

  test('clear button removes all nodes', async ({ page }) => {
    await page.click('button:has-text("Basic")');

    // Verify nodes exist
    let nodeCount = await page.evaluate(() => {
      return window.wfGraph && window.wfGraph._nodes ? window.wfGraph._nodes.length : 0;
    });
    expect(nodeCount).toBeGreaterThan(0);

    // Click Clear
    await page.click('button:has-text("Clear")');

    nodeCount = await page.evaluate(() => {
      return window.wfGraph && window.wfGraph._nodes ? window.wfGraph._nodes.length : 0;
    });
    expect(nodeCount).toBe(0);
  });

  // ── No Console Errors on Load ───────────────────────────────────────

  test('editor loads without JavaScript errors', async ({ page }) => {
    // Track errors during page navigation
    const errors = [];
    page.on('pageerror', err => errors.push(err));

    // Reload to capture errors from fresh load
    await page.goto(EDITOR_URL);
    await page.waitForSelector('#wf-canvas', { timeout: 10000 });
    await page.waitForTimeout(1000);

    // Load a template
    await page.click('button:has-text("Basic")');
    await page.waitForTimeout(500);

    expect(errors).toHaveLength(0);
  });
});
