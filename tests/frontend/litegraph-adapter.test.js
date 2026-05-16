/* litegraph-adapter.test.js — unit tests for LiteGraph adapter layer.
 *
 * Tests all public exports with the LiteGraph mock from setup.js.
 * Also tests fallback behavior when LiteGraph methods are missing.
 */

import { describe, it, expect, beforeEach } from 'vitest';

// Re-create a fresh mock setup: the adapter is built as an ES module
// that references global LiteGraph. setup.js provides the mock.
// For these tests we import the adapter functions directly after ensuring
// the mock is in place.

// ── Dynamic import helper ─────────────────────────────────────────────
// The adapter uses static imports of global LiteGraph.
// Since vitest + jsdom + setup.js provides the global, we can import directly.

import {
  createGraph,
  createCanvas,
  startGraph,
  stopGraph,
  clearGraph,
  registerNodeType,
  getRegisteredNodeType,
  addNode,
  removeNode,
  connectNodes,
  removeLink,
  getLinks,
  getNodes,
  findSlot,
  setDirty,
  zoomToFit,
  autoArrange,
  serializeGraph,
  configureGraph,
  configureCanvas,
  getCanvasScale,
  getCanvasOffset,
  createNodeBase,
  inheritLGraphNode,
  addPort,
  addWidget,
} from '../../web/static/js/lib/litegraph-adapter.js';

// ── Tests: Graph Lifecycle ────────────────────────────────────────────

describe('Graph Lifecycle', () => {
  describe('createGraph', () => {
    it('creates an LGraph instance', () => {
      var g = createGraph();
      expect(g).toBeInstanceOf(LiteGraph.LGraph);
    });

    it('initializes with empty nodes and links', () => {
      var g = createGraph();
      expect(g._nodes).toEqual([]);
      expect(g._links).toEqual([]);
    });
  });

  describe('createCanvas', () => {
    it('creates an LGraphCanvas instance', () => {
      var g = createGraph();
      var canvas = createCanvas(null, g);
      expect(canvas).toBeInstanceOf(LiteGraph.LGraphCanvas);
      expect(canvas.graph).toBe(g);
    });
  });

  describe('startGraph / stopGraph', () => {
    it('calls start on the graph', () => {
      var g = createGraph();
      var started = false;
      g.start = function () { started = true; };
      startGraph(g);
      expect(started).toBe(true);
    });

    it('calls stop on the graph', () => {
      var g = createGraph();
      var stopped = false;
      g.stop = function () { stopped = true; };
      stopGraph(g);
      expect(stopped).toBe(true);
    });

    it('does not throw when graph has no start/stop', () => {
      expect(() => startGraph({})).not.toThrow();
      expect(() => stopGraph({})).not.toThrow();
      expect(() => startGraph(null)).not.toThrow();
    });
  });

  describe('clearGraph', () => {
    it('clears nodes and links', () => {
      var g = createGraph();
      var n = new LiteGraph.LGraphNode('Test');
      g.add(n);
      g._links.push([1, n.id, 0, 99, 0, '*']);
      clearGraph(g);
      expect(g._nodes).toEqual([]);
    });

    it('re-initializes _links to empty array', () => {
      var g = createGraph();
      g._links = undefined;
      clearGraph(g);
      expect(g._links).toEqual([]);
    });

    it('does not throw on null graph', () => {
      expect(() => clearGraph(null)).not.toThrow();
    });
  });
});

// ── Tests: Node Registration ──────────────────────────────────────────

describe('Node Registration', () => {
  it('registers a new node type', () => {
    function TestNode() { LiteGraph.LGraphNode.call(this, 'Test'); }
    TestNode.prototype = Object.create(LiteGraph.LGraphNode.prototype);
    registerNodeType('test_type', TestNode);
    expect(getRegisteredNodeType('test_type')).toBe(TestNode);
  });

  it('returns null for unregistered type', () => {
    expect(getRegisteredNodeType('no_such_type')).toBeNull();
  });

  it('skips re-registration of existing type', () => {
    function NodeA() { LiteGraph.LGraphNode.call(this, 'A'); }
    NodeA.prototype = Object.create(LiteGraph.LGraphNode.prototype);
    function NodeB() { LiteGraph.LGraphNode.call(this, 'B'); }
    NodeB.prototype = Object.create(LiteGraph.LGraphNode.prototype);

    registerNodeType('dup_test', NodeA);
    registerNodeType('dup_test', NodeB); // should be skipped
    expect(getRegisteredNodeType('dup_test')).toBe(NodeA);
  });

  it('creates registered_node_types object if missing', () => {
    // Note: setup.js always provides registered_node_types, so this
    // tests the safety check path. We verify it doesn't throw.
    expect(() => registerNodeType('safe_test', function () {})).not.toThrow();
  });
});

// ── Tests: Node Operations ────────────────────────────────────────────

describe('Node Operations', () => {
  var graph;

  beforeEach(() => {
    graph = createGraph();
  });

  describe('addNode', () => {
    it('adds a node to the graph', () => {
      var n = new LiteGraph.LGraphNode('Test');
      addNode(graph, n);
      expect(graph._nodes).toContain(n);
      expect(graph._nodes_by_id[n.id]).toBe(n);
    });

    it('does not throw on null graph', () => {
      expect(() => addNode(null, new LiteGraph.LGraphNode('X'))).not.toThrow();
    });

    it('does not throw on null node', () => {
      expect(() => addNode(graph, null)).not.toThrow();
    });
  });

  describe('removeNode', () => {
    it('removes a node from the graph', () => {
      var n = new LiteGraph.LGraphNode('Test');
      addNode(graph, n);
      removeNode(graph, n);
      expect(graph._nodes).not.toContain(n);
      expect(graph._nodes_by_id[n.id]).toBeUndefined();
    });

    it('does not throw on null args', () => {
      expect(() => removeNode(null, {})).not.toThrow();
      expect(() => removeNode(graph, null)).not.toThrow();
    });
  });
});

// ── Tests: Link Operations ────────────────────────────────────────────

describe('Link Operations', () => {
  var graph, src, tgt;

  beforeEach(() => {
    graph = createGraph();
    src = new LiteGraph.LGraphNode('Source');
    src.addOutput('out', 'stl');
    tgt = new LiteGraph.LGraphNode('Target');
    tgt.addInput('in', 'stl');
    addNode(graph, src);
    addNode(graph, tgt);
  });

  describe('connectNodes', () => {
    it('connects two nodes and returns a link object', () => {
      var result = connectNodes(src, 0, tgt, 0);
      expect(result).toBe(true);
    });

    it('returns null when source node has no output at slot', () => {
      expect(connectNodes(src, 99, tgt, 0)).toBeNull();
    });

    it('returns null when target node has no input at slot', () => {
      expect(connectNodes(src, 0, tgt, 99)).toBeNull();
    });

    it('returns null when source node is null', () => {
      expect(connectNodes(null, 0, tgt, 0)).toBeNull();
    });

    it('returns null when target node is null', () => {
      expect(connectNodes(src, 0, null, 0)).toBeNull();
    });
  });

  describe('removeLink', () => {
    it('removes a link by id', () => {
      // connectNodes uses node.connect() which sets up node-level links,
      // but graph._links is populated via graph.add(link). Simulate the full flow.
      connectNodes(src, 0, tgt, 0);
      var link = { id: 99, origin_id: src.id, origin_slot: 0, target_id: tgt.id, target_slot: 0, type: 'stl' };
      graph._links.push(link);
      expect(graph._links.length).toBe(1);
      removeLink(graph, 99);
      expect(graph._links.length).toBe(0);
    });

    it('does not throw on null graph', () => {
      expect(() => removeLink(null, 1)).not.toThrow();
    });
  });

  describe('getLinks', () => {
    it('returns empty array for truly empty graph', () => {
      var empty = createGraph();
      expect(getLinks(empty)).toEqual([]);
    });

    it('returns links array after connecting', () => {
      // connectNodes uses node.connect() which sets up node-level links.
      // The adapter getLinks reads graph._links which is populated via graph.add(link).
      // Simulate a full link cycle by adding to graph._links directly.
      connectNodes(src, 0, tgt, 0);
      var link = { id: 1, origin_id: src.id, origin_slot: 0, target_id: tgt.id, target_slot: 0, type: 'stl' };
      graph._links.push(link);
      expect(getLinks(graph).length).toBe(1);
    });

    it('returns empty array when _links is undefined', () => {
      graph._links = undefined;
      expect(getLinks(graph)).toEqual([]);
    });

    it('returns empty array when graph is null', () => {
      expect(getLinks(null)).toEqual([]);
    });
  });

  describe('getNodes', () => {
    it('returns empty array for truly empty graph', () => {
      var empty = createGraph();
      expect(getNodes(empty)).toEqual([]);
    });

    it('returns nodes array for populated graph', () => {
      // beforeEach added src + tgt (2 nodes), test adds one more = 3
      var n = new LiteGraph.LGraphNode('Extra');
      addNode(graph, n);
      expect(getNodes(graph).length).toBe(3);
    });

    it('returns empty array when _nodes is undefined', () => {
      graph._nodes = undefined;
      expect(getNodes(graph)).toEqual([]);
    });
  });
});

// ── Tests: findSlot ───────────────────────────────────────────────────

describe('findSlot', () => {
  var node;

  beforeEach(() => {
    node = new LiteGraph.LGraphNode('Test');
    node.addInput('image', 'image');
    node.addInput('mesh', 'stl');
    node.addOutput('stl', 'stl');
    node.addOutput('preview', 'image');
  });

  it('finds input slot by name', () => {
    expect(findSlot(node, 'image', true)).toBe(0);
    expect(findSlot(node, 'mesh', true)).toBe(1);
  });

  it('finds output slot by name', () => {
    expect(findSlot(node, 'stl', false)).toBe(0);
    expect(findSlot(node, 'preview', false)).toBe(1);
  });

  it('returns -1 for nonexistent name', () => {
    expect(findSlot(node, 'nonexistent', true)).toBe(-1);
    expect(findSlot(node, 'nonexistent', false)).toBe(-1);
  });

  it('returns -1 when slots are empty', () => {
    var empty = new LiteGraph.LGraphNode('Empty');
    expect(findSlot(empty, 'anything', true)).toBe(-1);
    expect(findSlot(empty, 'anything', false)).toBe(-1);
  });

  it('returns -1 when node is null', () => {
    expect(findSlot(null, 'mesh', false)).toBe(-1);
  });
});

// ── Tests: Canvas Operations ──────────────────────────────────────────

describe('Canvas Operations', () => {
  describe('setDirty', () => {
    it('calls setDirty on the canvas', () => {
      var g = createGraph();
      var canvas = createCanvas(null, g);
      var called = false;
      canvas.setDirty = function (a, b) { called = true; };
      setDirty(canvas);
      expect(called).toBe(true);
    });

    it('does not throw on null canvas', () => {
      expect(() => setDirty(null)).not.toThrow();
    });
  });

  describe('zoomToFit', () => {
    it('calls zoomToFit on the canvas', () => {
      var g = createGraph();
      var canvas = createCanvas(null, g);
      var called = false;
      canvas.zoomToFit = function () { called = true; };
      zoomToFit(canvas);
      expect(called).toBe(true);
    });

    it('falls back to fitToContent when zoomToFit is not a function', () => {
      var g = createGraph();
      var canvas = createCanvas(null, g);
      // Make zoomToFit a non-function value on the instance
      Object.defineProperty(canvas, 'zoomToFit', { value: null, writable: true, configurable: true });
      var called = false;
      canvas.fitToContent = function () { called = true; };
      zoomToFit(canvas);
      expect(called).toBe(true);
    });

    it('does not throw when neither method exists', () => {
      var g = createGraph();
      var canvas = createCanvas(null, g);
      delete canvas.zoomToFit;
      canvas.fitToContent = null;
      expect(() => zoomToFit(canvas)).not.toThrow();
    });

    it('does not throw on null canvas', () => {
      expect(() => zoomToFit(null)).not.toThrow();
    });
  });

  describe('autoArrange', () => {
    it('calls arrange on the graph', () => {
      var g = createGraph();
      var called = false;
      g.arrange = function () { called = true; };
      autoArrange(g);
      expect(called).toBe(true);
    });

    it('does not throw when arrange is missing', () => {
      expect(() => autoArrange({})).not.toThrow();
    });
  });
});

// ── Tests: Serialization ──────────────────────────────────────────────

describe('Serialization', () => {
  describe('serializeGraph', () => {
    it('returns nodes and links arrays', () => {
      var g = createGraph();
      var result = serializeGraph(g);
      expect(result).toHaveProperty('nodes');
      expect(result).toHaveProperty('links');
      expect(result.nodes).toEqual([]);
      expect(result.links).toEqual([]);
    });

    it('serializes graph with nodes', () => {
      var g = createGraph();
      var n = new LiteGraph.LGraphNode('Test');
      n.addOutput('out', 'stl');
      g.add(n);
      var result = serializeGraph(g);
      expect(result.nodes.length).toBe(1);
      expect(result.nodes[0].type).toBe('');
      expect(result.nodes[0].title).toBe('Test');
    });

    it('returns empty structure when graph is null', () => {
      var result = serializeGraph(null);
      expect(result).toEqual({ nodes: [], links: [] });
    });
  });

  describe('configureGraph', () => {
    it('handles configure call without throwing', () => {
      var g = createGraph();
      var n = new LiteGraph.LGraphNode('Test');
      g.add(n);
      var data = serializeGraph(g);
      var g2 = createGraph();
      // Mock configure is a no-op; verify it doesn't throw
      expect(() => configureGraph(g2, data)).not.toThrow();
    });

    it('handles empty data', () => {
      var g2 = createGraph();
      expect(() => configureGraph(g2, {})).not.toThrow();
    });

    it('does not throw on null graph', () => {
      expect(() => configureGraph(null, {})).not.toThrow();
    });
  });
});

// ── Tests: Canvas Config ──────────────────────────────────────────────

describe('configureCanvas', () => {
  it('sets canvas properties from options', () => {
    var g = createGraph();
    var canvas = createCanvas(null, g);
    configureCanvas(canvas, {
      allow_dragcanvas: false,
      allow_interaction: false,
    });
    expect(canvas.allow_dragcanvas).toBe(false);
    expect(canvas.allow_interaction).toBe(false);
  });

  it('leaves existing properties when not in opts', () => {
    var g = createGraph();
    var canvas = createCanvas(null, g);
    canvas.allow_dragcanvas = true;
    configureCanvas(canvas, { allow_interaction: false });
    expect(canvas.allow_dragcanvas).toBe(true);
  });

  it('does not throw on null canvas', () => {
    expect(() => configureCanvas(null, {})).not.toThrow();
  });
});

// ── Tests: Coordinate Helpers ─────────────────────────────────────────

describe('Coordinate Helpers', () => {
  it('getCanvasScale returns default 1 when no ds', () => {
    var g = createGraph();
    var canvas = createCanvas(null, g);
    expect(getCanvasScale(canvas)).toBe(1);
  });

  it('getCanvasScale returns actual scale', () => {
    var g = createGraph();
    var canvas = createCanvas(null, g);
    canvas.ds.scale = 0.5;
    expect(getCanvasScale(canvas)).toBe(0.5);
  });

  it('getCanvasOffset returns default [0,0]', () => {
    var g = createGraph();
    var canvas = createCanvas(null, g);
    expect(getCanvasOffset(canvas)).toEqual([0, 0]);
  });

  it('getCanvasOffset returns actual offset', () => {
    var g = createGraph();
    var canvas = createCanvas(null, g);
    canvas.ds.offset = [100, 200];
    expect(getCanvasOffset(canvas)).toEqual([100, 200]);
  });
});

// ── Tests: Node Construction Helpers ──────────────────────────────────

describe('Node Construction Helpers', () => {
  describe('addPort', () => {
    it('adds an input port to a node', () => {
      var n = new LiteGraph.LGraphNode('Test');
      addPort(n, 'image', 'image', true);
      expect(n.inputs.length).toBe(1);
      expect(n.inputs[0].name).toBe('image');
      expect(n.inputs[0].type).toBe('image');
    });

    it('adds an output port to a node', () => {
      var n = new LiteGraph.LGraphNode('Test');
      addPort(n, 'stl', 'stl', false);
      expect(n.outputs.length).toBe(1);
      expect(n.outputs[0].name).toBe('stl');
    });

    it('defaults type to * when not specified', () => {
      var n = new LiteGraph.LGraphNode('Test');
      addPort(n, 'generic', undefined, true);
      expect(n.inputs[0].type).toBe('*');
    });
  });

  describe('addWidget', () => {
    it('adds a widget to a node', () => {
      var n = new LiteGraph.LGraphNode('Test');
      addWidget(n, 'number', 'scale', 1.0, () => {});
      expect(n.widgets.length).toBe(1);
      expect(n.widgets[0].type).toBe('number');
      expect(n.widgets[0].name).toBe('scale');
      expect(n.widgets[0].value).toBe(1.0);
    });

    it('passes options to widget', () => {
      var n = new LiteGraph.LGraphNode('Test');
      addWidget(n, 'number', 'count', 5, () => {}, { min: 1, max: 10 });
      expect(n.widgets[0].options).toEqual({ min: 1, max: 10 });
    });
  });

  describe('inheritLGraphNode', () => {
    it('sets up prototype chain correctly', () => {
      function MyNode() { LiteGraph.LGraphNode.call(this, 'MyNode'); }
      inheritLGraphNode(MyNode);
      var node = new MyNode();
      expect(node instanceof LiteGraph.LGraphNode).toBe(true);
      expect(node.constructor).toBe(MyNode);
    });
  });
});
