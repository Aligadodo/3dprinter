/* task-detail.test.js — unit tests for task-detail.js page module.
 *
 * Tests: renderTaskDetail (standalone + workflow branches), helper functions,
 * and bindTaskActions. Uses jsdom to simulate DOM rendering.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';

// ── Mock dependencies ──────────────────────────────────────────────

const mockApi = vi.fn();
const mockApiStream = vi.fn();
const mockT = vi.fn((key, vars) => {
  const map = {
    'detail.title': 'Task Detail',
    'detail.notFound': 'Task not found',
    'detail.waiting': 'Waiting...',
    'detail.help': 'Hover for help',
    'detail.backToWorkflow': 'Back to workflow',
    'detail.logTitle': 'Log',
    'badge.queued': 'Queued',
    'badge.running': 'Running',
    'badge.completed': 'Completed',
    'badge.failed': 'Failed',
    'badge.cancelled': 'Cancelled',
    'nav.dashboard': 'Dashboard',
    'detail.currentNode': 'Current',
    'node.viewTask': 'View task',
    'detail.expandAll': 'Expand all',
    'detail.collapseAll': 'Collapse all',
    'dash.workflow': 'Workflow',
    'detail.allNodes': 'All nodes ({n})',
    'detail.delete': 'Delete',
    'detail.deleteConfirm': 'Are you sure?',
    'detail.cancel': 'Cancel',
    'toast.taskCancelled': 'Task cancelled',
    'toast.taskDeleted': 'Task deleted',
    'toast.taskCompleted': 'Task completed',
  };
  return map[key] || key;
});
const mockGetLang = vi.fn(() => 'zh');
const mockEscHtml = vi.fn(s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'));
const mockFormatTime = vi.fn(() => '刚刚');
const mockFormatBytes = vi.fn(() => '1 KB');
const mockShowConfirm = vi.fn(() => Promise.resolve(true));
const mockSetActiveSSE = vi.fn();
const mockToast = vi.fn();
const mockRenderNodeDetailPanel = vi.fn(() => '<div class="node-detail-panel">MOCK</div>');

// ── Module under test ─────────────────────────────────────────────

vi.mock('../../web/static/js/api.js', () => ({ api: mockApi, apiStream: mockApiStream }));
vi.mock('../../web/static/js/i18n.js', () => ({ t: mockT, getLang: mockGetLang }));
vi.mock('../../web/static/js/utils.js', () => ({
  escHtml: mockEscHtml,
  formatTime: mockFormatTime,
  formatBytes: mockFormatBytes,
  cacheFile: vi.fn(() => 'fid-1'),
  showFileModal: vi.fn(),
  showCtxMenu: vi.fn(),
  getFile: vi.fn(),
  toast: mockToast,
}));
vi.mock('../../web/static/js/components/confirm.js', () => ({ showConfirm: mockShowConfirm }));
vi.mock('../../web/static/js/router.js', () => ({ setActiveSSE: mockSetActiveSSE }));
vi.mock('../../web/static/js/components/node-detail.js', () => ({ renderNodeDetailPanel: mockRenderNodeDetailPanel }));

// We need to import the module AFTER mocks are set up
const mod = await import('../../web/static/js/pages/task-detail.js');
const { default: renderTaskDetail, buildCompletedResult, buildFailedResult, buildOutputFiles, getPipelineTypeLabel } = mod;

// ── DOM setup ─────────────────────────────────────────────────────

function setupDOM() {
  document.body.innerHTML = '<div id="main"></div>';
  const main = document.getElementById('main');
  return { main };
}

// ── Mock LiteGraph (for node-detail panel) ─────────────────────────
beforeEach(() => {
  globalThis.LiteGraph = {
    LGraphNode: class {},
    LGraph: class {},
  };
});

// ══════════════════════════════════════════════════════════════════
// Tests: getPipelineTypeLabel
// ══════════════════════════════════════════════════════════════════

describe('getPipelineTypeLabel', () => {
  it('returns label_zh when lang is zh', () => {
    const cache = { triposr: { label: 'TripoSR', label_zh: 'TripoSR中文' } };
    expect(getPipelineTypeLabel(cache, 'triposr', true)).toBe('TripoSR中文');
  });

  it('returns label when lang is en', () => {
    const cache = { triposr: { label: 'TripoSR', label_zh: 'TripoSR中文' } };
    expect(getPipelineTypeLabel(cache, 'triposr', false)).toBe('TripoSR');
  });

  it('falls back to pipeline_type when not in cache', () => {
    const cache = {};
    expect(getPipelineTypeLabel(cache, 'hunyuan3d', true)).toBe('hunyuan3d');
  });
});

// ══════════════════════════════════════════════════════════════════
// Tests: buildCompletedResult helper
// ══════════════════════════════════════════════════════════════════

describe('buildCompletedResult', () => {
  it('renders vertices and faces', () => {
    const task = {
      result: { vertices: 12345, faces: 67890 },
    };
    const html = buildCompletedResult(task, []);
    expect(html).toContain('12,345');
    expect(html).toContain('67,890');
  });

  it('renders decimated stats', () => {
    const task = {
      result: { decimated_vertices: 5000, decimated_faces: 8000 },
    };
    const html = buildCompletedResult(task, []);
    expect(html).toContain('5,000');
    expect(html).toContain('8,000');
  });

  it('renders size when width_mm present', () => {
    const task = { result: { width_mm: 100, height_mm: 80 } };
    const html = buildCompletedResult(task, []);
    expect(html).toContain('100×80');
  });

  it('renders color bands', () => {
    const task = {
      result: {
        bands: [
          { z_start_mm: 0, z_end_mm: 5, color_hex: '#FF0000' },
          { z_start_mm: 5, z_end_mm: 10, color_hex: '#00FF00' },
        ],
      },
    };
    const html = buildCompletedResult(task, []);
    expect(html).toContain('#FF0000');
    expect(html).toContain('5 – 10');
  });
});

// ══════════════════════════════════════════════════════════════════
// Tests: buildFailedResult helper
// ══════════════════════════════════════════════════════════════════

describe('buildFailedResult', () => {
  it('renders error message', () => {
    const task = { result: { error: 'GPU out of memory' } };
    const html = buildFailedResult(task);
    expect(html).toContain('GPU out of memory');
  });

  it('renders unknown error when none', () => {
    const task = { result: {} };
    const html = buildFailedResult(task);
    // t('detail.unknownError') is called for missing error
    expect(html).toContain('detail.unknownError');
  });
});

// ══════════════════════════════════════════════════════════════════
// Tests: buildOutputFiles helper
// ══════════════════════════════════════════════════════════════════

describe('buildOutputFiles', () => {
  it('returns empty string for no files', () => {
    const html = buildOutputFiles([]);
    expect(html).toBe('');
  });

  it('categorizes preview files', () => {
    const files = [
      { category: 'preview', file_type: '.png', filename: 'thumb.png', url: '/api/files/thumb.png', path: '/output/thumb.png' },
    ];
    const html = buildOutputFiles(files);
    expect(html).toContain('preview');
    expect(html).toContain('thumb.png');
  });

  it('categorizes result files', () => {
    const files = [
      { category: 'result', file_type: '.stl', filename: 'model.stl', url: '/api/files/model.stl', path: '/output/model.stl' },
    ];
    const html = buildOutputFiles(files);
    expect(html).toContain('detail.catResult'); // t('detail.catResult') returns key itself in mock
    expect(html).toContain('model.stl');
  });
});

// ══════════════════════════════════════════════════════════════════
// Tests: renderTaskDetail — standalone task (no wfCtx)
// ══════════════════════════════════════════════════════════════════

describe('renderTaskDetail — standalone task (no workflow context)', () => {
  it('renders standalone task successfully', async () => {
    setupDOM();
    const main = document.getElementById('main');

    const taskId = 'standalone-task-123';
    mockApi.mockResolvedValueOnce({
      id: taskId,
      pipeline_type: 'triposr',
      display_name: 'My TripoSR Task',
      status: 'completed',
      output_files: [],
      params: {},
      result: { vertices: 5000 },
    });
    mockApi.mockResolvedValueOnce({
      types: { triposr: { id: 'triposr', label: 'TripoSR', label_zh: 'TripoSR', color: '#58a6ff' } },
    });

    await renderTaskDetail(main, `#/task/${taskId}`);

    const content = document.getElementById('detail-content');
    expect(content).not.toBeNull();
    expect(content.innerHTML).not.toContain('undefined'); // no undefined values
    expect(content.innerHTML).not.toContain('ptLabel');   // ptLabel must be defined before use
  });

  it('throws ReferenceError if ptLabel is used before definition (regression test)', async () => {
    setupDOM();
    const main = document.getElementById('main');

    const taskId = 'no-ptlabel-task-456';
    mockApi.mockResolvedValueOnce({
      id: taskId,
      pipeline_type: 'mesh_repair',
      display_name: null,   // triggers ptLabel fallback path
      status: 'failed',
      output_files: [],
      params: {},
      result: { error: 'repair failed' },
    });
    mockApi.mockResolvedValueOnce({ types: {} });

    // Should not throw — this test verifies the fix
    await expect(renderTaskDetail(main, `#/task/${taskId}`)).resolves.not.toThrow();
  });

  it('renders failed standalone task with retry/delete buttons', async () => {
    setupDOM();
    const main = document.getElementById('main');

    const taskId = 'failed-task-789';
    mockApi.mockResolvedValueOnce({
      id: taskId,
      pipeline_type: 'hunyuan3d',
      status: 'failed',
      output_files: [],
      params: {},
      result: { error: 'out of memory' },
    });
    mockApi.mockResolvedValueOnce({ types: {} });

    await renderTaskDetail(main, `#/task/${taskId}`);
    const content = document.getElementById('detail-content');
    // Failed task shows retry and delete buttons
    expect(content.innerHTML).toContain('retry-btn');
    expect(content.innerHTML).toContain('delete-btn');
  });
});

// ══════════════════════════════════════════════════════════════════
// Tests: renderTaskDetail — workflow sub-task (wfCtx present)
// ══════════════════════════════════════════════════════════════════

describe('renderTaskDetail — workflow sub-task (has workflow context)', () => {
  it('renders workflow sub-task with node cards', async () => {
    setupDOM();
    const main = document.getElementById('main');

    const taskId = 'wf-task-001';
    // 1. GET /tasks/{id}
    mockApi.mockResolvedValueOnce({
      id: taskId,
      pipeline_type: 'image_to_3d',
      display_name: null,
      status: 'running',
      is_workflow_task: true,
      output_files: [],
      params: {},
    });
    // 2. GET /tasks/{id}/workflow (workflow sub-task)
    mockApi.mockResolvedValueOnce({
      instance_id: 'inst-abc',
      workflow_name: 'My Pipeline',
      node_id: '2',
    });
    // 3. GET /pipeline-types
    mockApi.mockResolvedValueOnce({ types: { image_to_3d: { label: 'Image→3D', label_zh: '图→3D' } } });
    // 4. Promise.all: GET /workflows/instances/{id}
    mockApi.mockResolvedValueOnce({
      id: 'inst-abc',
      node_runs: [
        { node_id: '1', status: 'completed', task_id: 't1', output_files: [] },
        { node_id: '2', status: 'running', task_id: taskId, output_files: [] },
      ],
      workflow_graph: {
        nodes: [
          { id: '1', type: 'file_input', title: 'Input' },
          { id: '2', type: 'triposr', title: 'TripoSR' },
        ],
        links: [],
      },
      context: {
        '1': { file: '/input.jpg' },
        '2': { image: '/output.glb' },
      },
    });
    // 5. Promise.all: GET /node-types
    mockApi.mockResolvedValueOnce({
      types: [
        { id: 'file_input', label: 'File Input', label_zh: '文件输入', color: '#888' },
        { id: 'triposr', label: 'TripoSR', label_zh: 'TripoSR', color: '#58a6ff' },
      ],
    });

    await renderTaskDetail(main, `#/task/${taskId}`);

    const content = document.getElementById('detail-content');
    expect(content.innerHTML).not.toContain('undefined');
    expect(content.innerHTML).not.toContain('ptLabel');
    expect(content.innerHTML).toContain('My Pipeline');
  });

  it('workflow branch uses ptLabel from correct scope', async () => {
    setupDOM();
    const main = document.getElementById('main');

    const taskId = 'wf-task-002';
    mockApi.mockResolvedValueOnce({
      id: taskId,
      pipeline_type: 'mesh_repair',
      display_name: null,
      status: 'queued',
      is_workflow_task: true,
      output_files: [],
      params: {},
    });
    mockApi.mockResolvedValueOnce({ instance_id: 'inst-def', workflow_name: 'Repair Flow', node_id: '1' });
    mockApi.mockResolvedValueOnce({ types: { mesh_repair: { label: 'Mesh Repair', label_zh: 'Mesh修复' } } });
    mockApi.mockResolvedValueOnce({
      id: 'inst-def',
      node_runs: [{ node_id: '1', status: 'queued', output_files: [] }],
      workflow_graph: { nodes: [{ id: '1', type: 'repair', title: 'Repair' }], links: [] },
      context: { '1': {} },
    });
    mockApi.mockResolvedValueOnce({ types: [{ id: 'repair', label: 'Mesh Repair', label_zh: 'Mesh修复', color: '#ff9900' }] });

    await renderTaskDetail(main, `#/task/${taskId}`);

    const content = document.getElementById('detail-content');
    expect(content.innerHTML).not.toContain('ReferenceError');
    expect(content.innerHTML).not.toContain('ptLabel');
  });
});

// ══════════════════════════════════════════════════════════════════
// Tests: bindTaskActions (called after render, tests interactions)
// ══════════════════════════════════════════════════════════════════

describe('bindTaskActions', () => {
  it('cancel button calls API and re-renders', async () => {
    setupDOM();
    const main = document.getElementById('main');

    const taskId = 'action-task-001';
    mockApi.mockResolvedValueOnce({
      id: taskId,
      pipeline_type: 'triposr',
      status: 'running',
      output_files: [],
      params: {},
    });
    mockApi.mockResolvedValueOnce({ types: {} });
    mockApi.mockResolvedValueOnce({ id: taskId, pipeline_type: 'triposr', status: 'completed', output_files: [], params: {} });

    await renderTaskDetail(main, `#/task/${taskId}`);

    const cancelBtn = document.getElementById('cancel-btn');
    expect(cancelBtn).not.toBeNull();

    mockApi.mockResolvedValueOnce({}); // cancel API
    mockApi.mockResolvedValueOnce({ id: taskId, pipeline_type: 'triposr', status: 'cancelled', output_files: [], params: {} });

    // Fire cancel — will re-render
    cancelBtn.click();
    await new Promise(r => setTimeout(r, 50));

    expect(mockApi).toHaveBeenCalledWith('POST', `/tasks/${taskId}/cancel`);
  });
});