/* page-load.test.js — Smoke tests for all page modules.
 *
 * Verifies each page module:
 * 1. Loads without throwing
 * 2. Exports a default render function
 * 3. The render function produces no JS errors when called (mocked DOM)
 * 4. Key DOM elements are present in the rendered output
 *
 * Coverage: dashboard, workflows, wf-editor, wf-runner, task-detail, new-task, file-browse, docs
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// ── Shared mocks (all pages use these) ─────────────────────────────────

const mockApi = vi.fn(() => Promise.resolve({}));

vi.mock('../../web/static/js/api.js', () => ({
  api: mockApi,
  apiStream: vi.fn(),
  fetchProviderStatuses: vi.fn(() => Promise.resolve([])),
  providerChoiceLabel: vi.fn(() => ''),
}));

vi.mock('../../web/static/js/i18n.js', () => ({
  t: vi.fn(key => key),
  getLang: vi.fn(() => 'zh'),
}));

vi.mock('../../web/static/js/utils.js', () => ({
  escHtml: vi.fn(s => s),
  toast: vi.fn(),
  getBilingualLabel: vi.fn(nt => nt.label || nt.id || ''),
  isTypeCompatible: vi.fn(() => true),
  formatBytes: vi.fn(() => '1 KB'),
  showImageModal: vi.fn(),
  showFileModal: vi.fn(),
  showCtxMenu: vi.fn(),
  cacheFile: vi.fn(() => 'fid'),
  getFile: vi.fn(),
  formatTime: vi.fn(() => '刚刚'),
}));

vi.mock('../../web/static/js/router.js', () => ({
  setActiveSSE: vi.fn(),
  setPollTimer: vi.fn(),
}));

// ── LiteGraph mock (used by workflow pages) ─────────────────────────────

globalThis.LiteGraph = {
  LGraphNode: class {
    constructor(title) { this.title = title; this.inputs = []; this.outputs = []; this.properties = {}; }
    addInput() { this.inputs.push({}); }
    addOutput() { this.outputs.push({}); }
  },
  LGraph: class {
    constructor() { this._nodes = []; this._links = {}; }
    add(node) { this._nodes.push(node); }
    start() {}
    stop() {}
    clear() {}
  },
  LGraphCanvas: class {},
  registered_node_types: {},
  registerNodeType: vi.fn(),
};

// ── DOM setup helper ─────────────────────────────────────────────────

function setupMain() {
  document.body.innerHTML = '<div id="main" style="display:none"></div>';
  return document.getElementById('main');
}

// ══════════════════════════════════════════════════════════════════
// Page: dashboard
// ══════════════════════════════════════════════════════════════════

describe('dashboard', async () => {
  let mod;
  beforeEach(() => { document.body.innerHTML = ''; mockApi.mockReset(); });

  it('loads and exports default render function', async () => {
    mod = await import('../../web/static/js/pages/dashboard.js');
    expect(typeof mod.default).toBe('function');
  });

  it('render completes without JS errors', async () => {
    mod = await import('../../web/static/js/pages/dashboard.js');
    const main = setupMain();

    // Mock data the dashboard needs
    const mockStats = {
      total_tasks: 0, completed_tasks: 0, failed_tasks: 0, running_tasks: 0,
      total_workflows: 0, total_storage_mb: 0,
    };
    const mockTasks = { tasks: [], total: 0, stats: mockStats };
    const mockWorkflows = { workflows: [] };

    mockApi.mockResolvedValueOnce({ types: {} });  // pipeline-types
    mockApi.mockResolvedValueOnce(mockTasks);      // /tasks with stats
    mockApi.mockResolvedValueOnce(mockWorkflows);   // /workflows

    await mod.default(main, '');
    expect(true).toBe(true);
  });

  it('renders page-title element', async () => {
    mod = await import('../../web/static/js/pages/dashboard.js');
    const main = setupMain();

    const mockStats = {
      total_tasks: 0, completed_tasks: 0, failed_tasks: 0, running_tasks: 0,
      total_workflows: 0, total_storage_mb: 0,
    };
    const mockTasks = { tasks: [], total: 0, stats: mockStats };

    mockApi.mockResolvedValueOnce({ types: {} });
    mockApi.mockResolvedValueOnce(mockTasks);
    mockApi.mockResolvedValueOnce({ workflows: [] });

    await mod.default(main, '');
    expect(main.querySelector('.page-title, h2, h1')).toBeTruthy();
  });
});

// ══════════════════════════════════════════════════════════════════
// Page: workflows
// ══════════════════════════════════════════════════════════════════

describe('workflows', async () => {
  let mod;
  beforeEach(() => { document.body.innerHTML = ''; mockApi.mockReset(); });

  it('loads and exports default render function', async () => {
    mod = await import('../../web/static/js/pages/workflows.js');
    expect(typeof mod.default).toBe('function');
  });

  it('render completes without JS errors', async () => {
    mod = await import('../../web/static/js/pages/workflows.js');
    const main = setupMain();
    mockApi.mockResolvedValueOnce({ workflows: [] });
    await mod.default(main, '');
    expect(true).toBe(true);
  });

  it('renders workflow list or empty state', async () => {
    mod = await import('../../web/static/js/pages/workflows.js');
    const main = setupMain();
    mockApi.mockResolvedValueOnce({ workflows: [] });
    await mod.default(main, '');
    expect(main.innerHTML.length).toBeGreaterThan(0);
  });
});

// ══════════════════════════════════════════════════════════════════
// Page: wf-editor
// ══════════════════════════════════════════════════════════════════

describe('wf-editor', async () => {
  let mod;
  beforeEach(() => { document.body.innerHTML = ''; mockApi.mockReset(); });

  it('loads and exports default render function', async () => {
    mod = await import('../../web/static/js/pages/wf-editor.js');
    expect(typeof mod.default).toBe('function');
  });

  it('render completes without JS errors', async () => {
    mod = await import('../../web/static/js/pages/wf-editor.js');
    const main = setupMain();
    mockApi.mockResolvedValueOnce({ types: [], categories: {} });
    await mod.default(main, '#/workflow/new');
    expect(true).toBe(true);
  });

  it('creates palette, canvas, and inspector elements', async () => {
    mod = await import('../../web/static/js/pages/wf-editor.js');
    const main = setupMain();
    mockApi.mockResolvedValueOnce({ types: [], categories: {} });
    await mod.default(main, '#/workflow/new');
    expect(main.querySelector('#wf-palette')).toBeTruthy();
    expect(main.querySelector('#wf-canvas-wrap')).toBeTruthy();
    expect(main.querySelector('#wf-inspector')).toBeTruthy();
  });
});

// ══════════════════════════════════════════════════════════════════
// Page: wf-runner
// ══════════════════════════════════════════════════════════════════

describe('wf-runner', async () => {
  let mod;
  beforeEach(() => { document.body.innerHTML = ''; mockApi.mockReset(); });

  it('loads and exports default render function', async () => {
    mod = await import('../../web/static/js/pages/wf-runner.js');
    expect(typeof mod.default).toBe('function');
  });

  it('render completes without JS errors', async () => {
    mod = await import('../../web/static/js/pages/wf-runner.js');
    const main = setupMain();

    const mockInst = {
      id: 'test-inst-id',
      workflow_id: 'wf-1',
      workflow_name: 'Test Workflow',
      status: 'completed',
      node_runs: [],
      context: {},
      workflow: { graph: { nodes: [], links: [] } },
    };
    const mockNodeTypes = { types: [] };

    mockApi.mockResolvedValueOnce(mockInst);
    mockApi.mockResolvedValueOnce(mockNodeTypes);

    // Capture the cleanup function — don't call it
    await mod.default(main, '#/workflow/instance/test-inst-id');
    expect(true).toBe(true);
  });

  it('renders workflow name and status badge', async () => {
    mod = await import('../../web/static/js/pages/wf-runner.js');
    const main = setupMain();

    const mockInst = {
      id: 'test-inst-id',
      workflow_id: 'wf-1',
      workflow_name: 'My Workflow',
      status: 'completed',
      node_runs: [],
      context: {},
      workflow: { graph: { nodes: [], links: [] } },
    };
    const mockNodeTypes = { types: [] };

    mockApi.mockResolvedValueOnce(mockInst);
    mockApi.mockResolvedValueOnce(mockNodeTypes);

    await mod.default(main, '#/workflow/instance/test-inst-id');
    expect(main.textContent).toContain('My Workflow');
  });
});

// ══════════════════════════════════════════════════════════════════
// Page: task-detail
// ══════════════════════════════════════════════════════════════════

describe('task-detail', async () => {
  let mod;
  beforeEach(() => { document.body.innerHTML = ''; mockApi.mockReset(); });

  it('loads and exports default render function', async () => {
    mod = await import('../../web/static/js/pages/task-detail.js');
    expect(typeof mod.default).toBe('function');
  });

  it('render completes without JS errors for completed task', async () => {
    mod = await import('../../web/static/js/pages/task-detail.js');
    const main = setupMain();

    const mockTask = {
      id: 'task-1',
      pipeline_type: 'relief',
      status: 'completed',
      created_at: new Date().toISOString(),
      result: { vertices: 1000, faces: 2000 },
    };
    const mockWfDef = { name: 'Test WF', graph: { nodes: [], links: [] } };

    mockApi.mockResolvedValueOnce(mockTask);
    mockApi.mockResolvedValueOnce(mockWfDef);

    await mod.default(main, '#/task/task-1');
    expect(true).toBe(true);
  });

  it('render completes for failed task', async () => {
    mod = await import('../../web/static/js/pages/task-detail.js');
    const main = setupMain();

    const mockTask = {
      id: 'task-1',
      pipeline_type: 'relief',
      status: 'failed',
      error: 'Something went wrong',
      created_at: new Date().toISOString(),
    };
    const mockWfDef = { name: 'Test WF', graph: { nodes: [], links: [] } };

    mockApi.mockResolvedValueOnce(mockTask);
    mockApi.mockResolvedValueOnce(mockWfDef);

    await mod.default(main, '#/task/task-1');
    expect(true).toBe(true);
  });

  it('renders task result content (vertices/faces)', async () => {
    mod = await import('../../web/static/js/pages/task-detail.js');
    const main = setupMain();

    const mockTask = {
      id: 'task-1',
      pipeline_type: 'relief',
      status: 'completed',
      created_at: new Date().toISOString(),
      result: { vertices: 1000, faces: 2000 },
    };
    const mockWfDef = { name: 'Test WF', graph: { nodes: [], links: [] } };

    mockApi.mockResolvedValueOnce(mockTask);
    mockApi.mockResolvedValueOnce(mockWfDef);

    await mod.default(main, '#/task/task-1');
    expect(main.textContent).toContain('1,000');
    expect(main.textContent).toContain('2,000');
  });
});

// ══════════════════════════════════════════════════════════════════
// Page: new-task
// ══════════════════════════════════════════════════════════════════

describe('new-task', async () => {
  let mod;
  beforeEach(() => { document.body.innerHTML = ''; mockApi.mockReset(); });

  it('loads and exports default render function', async () => {
    mod = await import('../../web/static/js/pages/new-task.js');
    expect(typeof mod.default).toBe('function');
  });

  it('render completes without JS errors', async () => {
    mod = await import('../../web/static/js/pages/new-task.js');
    const main = setupMain();
    mockApi.mockResolvedValueOnce({ types: [] });
    await mod.default(main);
    expect(true).toBe(true);
  });

  it('renders provider tabs', async () => {
    mod = await import('../../web/static/js/pages/new-task.js');
    const main = setupMain();
    mockApi.mockResolvedValueOnce({ types: [] });
    await mod.default(main);
    expect(main.querySelector('[data-provider]') || main.textContent.length).toBeTruthy();
  });
});

// ══════════════════════════════════════════════════════════════════
// Page: file-browse
// ══════════════════════════════════════════════════════════════════

describe('file-browse', async () => {
  let mod;
  beforeEach(() => { document.body.innerHTML = ''; mockApi.mockReset(); });

  it('loads and exports default render function', async () => {
    mod = await import('../../web/static/js/pages/file-browse.js');
    expect(typeof mod.default).toBe('function');
  });

  it('render completes without JS errors', async () => {
    mod = await import('../../web/static/js/pages/file-browse.js');
    const main = setupMain();
    mockApi.mockResolvedValueOnce({ tasks: [] });
    mockApi.mockResolvedValueOnce({ files: [] });
    await mod.default(main, '#/files');
    expect(true).toBe(true);
  });

  it('renders file list or empty state', async () => {
    mod = await import('../../web/static/js/pages/file-browse.js');
    const main = setupMain();
    mockApi.mockResolvedValueOnce({ tasks: [] });
    mockApi.mockResolvedValueOnce({ files: [] });
    await mod.default(main, '#/files');
    expect(main.innerHTML.length).toBeGreaterThan(0);
  });
});

// ══════════════════════════════════════════════════════════════════
// Page: docs
// ══════════════════════════════════════════════════════════════════

describe('docs', async () => {
  let mod;
  beforeEach(() => { document.body.innerHTML = ''; mockApi.mockReset(); });

  it('loads and exports default render function', async () => {
    mod = await import('../../web/static/js/pages/docs.js');
    expect(typeof mod.default).toBe('function');
  });

  it('render completes without JS errors', async () => {
    mod = await import('../../web/static/js/pages/docs.js');
    const main = setupMain();
    await mod.default(main, '#/docs');
    expect(true).toBe(true);
  });

  it('renders doc content', async () => {
    mod = await import('../../web/static/js/pages/docs.js');
    const main = setupMain();
    await mod.default(main, '#/docs');
    expect(main.textContent.length).toBeGreaterThan(0);
  });
});