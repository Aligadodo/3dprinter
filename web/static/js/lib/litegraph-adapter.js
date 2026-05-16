/* litegraph-adapter.js — Safe abstraction over LiteGraph 0.7.14 CDN API.
 *
 * Every direct LiteGraph API call flows through this module so that:
 * 1. Version differences (0.7.14 vs ComfyUI fork) are isolated here.
 * 2. Missing methods get graceful fallbacks instead of crashes.
 * 3. Internal property access (._links, ._nodes) is null-safe.
 * 4. Tests can mock this module instead of the full LiteGraph global.
 */

// ── Graph Lifecycle ──

export function createGraph() {
  if (typeof LiteGraph === 'undefined' || !LiteGraph.LGraph) {
    throw new Error('LiteGraph not loaded — is the CDN script tag present?');
  }
  return new LiteGraph.LGraph();
}

export function createCanvas(canvasElement, graph) {
  return new LiteGraph.LGraphCanvas(canvasElement, graph);
}

export function startGraph(graph) {
  if (graph && graph.start) graph.start();
}

export function stopGraph(graph) {
  if (graph && graph.stop) graph.stop();
}

export function clearGraph(graph) {
  if (!graph || !graph.clear) return;
  graph.clear();
  // LiteGraph 0.7.14 clear() may not re-init _links — ensure it exists
  if (!graph._links) graph._links = [];
}

// ── Node Registration ──

export function registerNodeType(name, cls) {
  if (!LiteGraph.registered_node_types) {
    LiteGraph.registered_node_types = {};
  }
  if (LiteGraph.registered_node_types[name]) {
    console.debug('litegraph-adapter: skipping re-registration of', name);
    return;
  }
  LiteGraph.registerNodeType(name, cls);
}

export function getRegisteredNodeType(name) {
  return (LiteGraph.registered_node_types || {})[name] || null;
}

// ── Node Operations ──

export function addNode(graph, node) {
  if (!graph || !node) return;
  graph.add(node);
}

export function removeNode(graph, node) {
  if (!graph || !node) return;
  graph.remove(node);
}

// ── Link Operations ──

/**
 * Create a connection between two nodes.
 * Uses the standard LiteGraph API: node.connect(slot, targetNode, targetSlot).
 */
export function connectNodes(srcNode, srcSlot, tgtNode, tgtSlot) {
  if (!srcNode || !tgtNode) return null;
  if (!srcNode.outputs || !srcNode.outputs[srcSlot]) return null;
  if (!tgtNode.inputs || !tgtNode.inputs[tgtSlot]) return null;
  return srcNode.connect(srcSlot, tgtNode, tgtSlot);
}

export function removeLink(graph, linkId) {
  if (!graph || !graph.removeLink) return;
  graph.removeLink(linkId);
}

/** Safe access to graph links — always returns an array. */
export function getLinks(graph) {
  return (graph && graph._links) ? graph._links : [];
}

/** Safe access to graph nodes — always returns an array. */
export function getNodes(graph) {
  return (graph && graph._nodes) ? graph._nodes : [];
}

// ── Slot Lookup ──

/**
 * Find a slot index by name. Works across LiteGraph versions.
 * @param {object} node - LGraphNode instance
 * @param {string} slotName
 * @param {boolean} isInput
 * @returns {number} slot index, or -1 if not found
 */
export function findSlot(node, slotName, isInput) {
  if (!node) return -1;
  var slots = isInput ? node.inputs : node.outputs;
  if (!slots || !slots.length) return -1;

  // Try LiteGraph built-in methods (0.7+)
  var fn = isInput ? node.findInputSlot : node.findOutputSlot;
  if (typeof fn === 'function') {
    var r = fn.call(node, slotName);
    if (typeof r === 'number') return r;
    if (r && r.slot != null) return r.slot;  // ComfyUI fork returns {slot: N}
    return -1;
  }

  // Fallback: linear scan by slot name
  for (var i = 0; i < slots.length; i++) {
    if (slots[i].name === slotName) return i;
  }
  return -1;
}

// ── Canvas ──

export function setDirty(canvas) {
  if (canvas && canvas.setDirty) {
    canvas.setDirty(true, true);
  }
}

export function zoomToFit(canvas) {
  if (!canvas) return;
  // LiteGraph 0.7.14: zoomToFit, ComfyUI fork adds fitToContent
  if (typeof canvas.zoomToFit === 'function') {
    canvas.zoomToFit();
  } else if (typeof canvas.fitToContent === 'function') {
    canvas.fitToContent();
  }
}

export function autoArrange(graph) {
  if (graph && typeof graph.arrange === 'function') {
    graph.arrange();
  }
}

// ── Serialization ──

export function serializeGraph(graph) {
  if (!graph || !graph.serialize) return { nodes: [], links: [] };
  return graph.serialize();
}

export function configureGraph(graph, data) {
  if (!graph || !graph.configure) return;
  clearGraph(graph);
  if (data && data.nodes && data.nodes.length > 0) {
    graph.configure(data);
  }
}

// ── Canvas Config ──

export function configureCanvas(canvas, opts) {
  if (!canvas) return;
  if (opts.allow_dragcanvas !== undefined) canvas.allow_dragcanvas = opts.allow_dragcanvas;
  if (opts.allow_interaction !== undefined) canvas.allow_interaction = opts.allow_interaction;
  if (opts.allow_dragnodes !== undefined) canvas.allow_dragnodes = opts.allow_dragnodes;
  if (opts.getNodeMenuOptions) canvas.getNodeMenuOptions = opts.getNodeMenuOptions;
  if (opts.onNodeSelected) canvas.onNodeSelected = opts.onNodeSelected;
}

// ── Canvas Coordinate Helpers ──

export function getCanvasScale(canvas) {
  return (canvas && canvas.ds) ? (canvas.ds.scale || 1) : 1;
}

export function getCanvasOffset(canvas) {
  return (canvas && canvas.ds && canvas.ds.offset) ? canvas.ds.offset : [0, 0];
}

// ── Node Construction Helpers ──

export function createNodeBase(WFNodeClass, title) {
  // Call LiteGraph.LGraphNode constructor
  LiteGraph.LGraphNode.call(WFNodeClass, title);
}

export function inheritLGraphNode(WFNodeClass) {
  WFNodeClass.prototype = Object.create(LiteGraph.LGraphNode.prototype);
  WFNodeClass.prototype.constructor = WFNodeClass;
}

export function addPort(node, name, type, isInput) {
  if (isInput) {
    node.addInput(name, type || '*');
  } else {
    node.addOutput(name, type || '*');
  }
}

export function addWidget(node, type, name, value, callback, options) {
  node.addWidget(type, name, value, callback, options || {});
}
