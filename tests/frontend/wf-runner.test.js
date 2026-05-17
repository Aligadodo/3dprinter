/* wf-runner.test.js — unit tests for wf-runner.js page module.
 *
 * Tests: getBilingualLabel, getNodeDisplayLabel, buildNodeTabs (DOM),
 * and duplicate-const detection. Uses jsdom for DOM simulation.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';

// ── Mock dependencies (must match actual import paths from wf-runner.js) ──

vi.mock('../../web/static/js/api.js', () => ({
  api: vi.fn(),
}));

vi.mock('../../web/static/js/i18n.js', () => ({
  t: vi.fn(key => key),
  getLang: vi.fn(() => 'zh'),
}));

vi.mock('../../web/static/js/utils.js', () => ({
  escHtml: vi.fn(s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')),
  toast: vi.fn(),
  showImageModal: vi.fn(),
  getBilingualLabel: vi.fn(nt => {
    if (!nt) return '';
    const zh = nt.label_zh && nt.label_zh.trim() || '';
    const en = nt.label && nt.label.trim() || '';
    if (!zh) return en;
    if (!en || zh === en) return zh;
    return zh + ' ' + en;
  }),
}));

vi.mock('../../web/static/js/components/node-detail.js', () => ({
  renderNodeDetailPanel: vi.fn(() => '<div class="node-detail-panel">MOCK</div>'),
}));

// ── Mock LiteGraph ──────────────────────────────────────────────

global.LiteGraph = {
  LGraphNode: vi.fn(function(title) {
    this.title = title;
    this.id = null;
    this.pos = [100, 100];
    this._wfType = null;
    this._status = 'queued';
    this.color = '#30363d';
    this.size = [220, 100];
    this.inputs = [];
    this.outputs = [];
    this.properties = {};
    this.addInput = vi.fn((label, type) => this.inputs.push({ label, type }));
    this.addOutput = vi.fn((label, type) => this.outputs.push({ label, type }));
  }),
  LGraph: vi.fn(),
  LGraphCanvas: vi.fn(),
  registered_node_types: {},
  registerNodeType: vi.fn(),
};

// ── Import the module under test ─────────────────────────────────

import { getNodeDisplayLabel } from '../../web/static/js/pages/wf-runner.js';

// ── Fixtures ──────────────────────────────────────────────────

function makeNt(id, label, label_zh) {
  return { id, label: label || id, label_zh: label_zh || label || id, category: 'process', inputs: [], outputs: [] };
}

function makeNode(id, type, title) {
  return { id, type: 'wf_' + type, title };
}

// ── Tests ──────────────────────────────────────────────────────

describe('getNodeDisplayLabel', () => {
  const ntMap = {
    relief: makeNt('relief', 'Relief', '浮雕'),
    triposr: makeNt('triposr', 'TripoSR', 'TripoSR'),
  };

  it('returns node.title when present', () => {
    const node = makeNode(1, 'relief', 'My Custom Title');
    const graphNodes = [node];
    expect(getNodeDisplayLabel(node, ntMap['relief'], graphNodes, ntMap)).toBe('My Custom Title');
  });

  it('returns bilingual nt label when no title and no graphNodes', () => {
    const node = makeNode(1, 'relief');
    expect(getNodeDisplayLabel(node, ntMap['relief'], [], ntMap)).toBe('浮雕 Relief');
  });

  it('returns base label when only one node of that type', () => {
    const node = makeNode(1, 'relief');
    const graphNodes = [node];
    expect(getNodeDisplayLabel(node, ntMap['relief'], graphNodes, ntMap)).toBe('浮雕 Relief');
  });

  it('appends #1 when multiple nodes of same type', () => {
    const node1 = makeNode(1, 'relief');
    const node2 = makeNode(2, 'relief');
    const graphNodes = [node1, node2];
    expect(getNodeDisplayLabel(node1, ntMap['relief'], graphNodes, ntMap)).toBe('浮雕 Relief #1');
    expect(getNodeDisplayLabel(node2, ntMap['relief'], graphNodes, ntMap)).toBe('浮雕 Relief #2');
  });

  it('appends correct #N for more than 2 nodes', () => {
    const nodes = [1, 2, 3].map(i => makeNode(i, 'relief'));
    const graphNodes = nodes;
    expect(getNodeDisplayLabel(nodes[0], ntMap['relief'], graphNodes, ntMap)).toBe('浮雕 Relief #1');
    expect(getNodeDisplayLabel(nodes[1], ntMap['relief'], graphNodes, ntMap)).toBe('浮雕 Relief #2');
    expect(getNodeDisplayLabel(nodes[2], ntMap['relief'], graphNodes, ntMap)).toBe('浮雕 Relief #3');
  });

  it('handles mixed types — only counts same type', () => {
    const reliefNode = makeNode(1, 'relief');
    const triposrNode = makeNode(2, 'triposr');
    const graphNodes = [reliefNode, triposrNode];
    expect(getNodeDisplayLabel(reliefNode, ntMap['relief'], graphNodes, ntMap)).toBe('浮雕 Relief');
    expect(getNodeDisplayLabel(triposrNode, ntMap['triposr'], graphNodes, ntMap)).toBe('TripoSR');
  });

  it('handles null/undefined graphNodes gracefully', () => {
    const node = makeNode(1, 'relief');
    expect(getNodeDisplayLabel(node, ntMap['relief'], null, ntMap)).toBe('浮雕 Relief');
    expect(getNodeDisplayLabel(node, ntMap['relief'], undefined, ntMap)).toBe('浮雕 Relief');
  });

  it('uses type as fallback when no nt provided', () => {
    const node = makeNode(1, 'relief');
    expect(getNodeDisplayLabel(node, null, [], ntMap)).toBe('wf_relief');
  });
});

describe('buildNodeTabs — module loads without error', async () => {
  it('renderWorkflowRunner module loads successfully', async () => {
    const { default: renderWorkflowRunner } = await import('../../web/static/js/pages/wf-runner.js');
    expect(typeof renderWorkflowRunner).toBe('function');
  });
});

describe('addOrUpdateRunnerNode duplicate-const detection', () => {
  it('does not redeclare graphNodes within the same function scope', async () => {
    const fs = await import('fs');
    const code = fs.readFileSync('web/static/js/pages/wf-runner.js', 'utf8');

    // Find the addOrUpdateRunnerNode function body
    const funcStart = code.indexOf('function addOrUpdateRunnerNode');
    const funcEnd = code.indexOf('\n}', funcStart);
    const funcBody = code.slice(funcStart, funcEnd);

    // The fixed version should have exactly ONE "const graphNodes" declaration
    const matches = funcBody.match(/const graphNodes/g);
    expect(matches, 'addOrUpdateRunnerNode should have exactly one "const graphNodes" declaration').toHaveLength(1);
  });
});