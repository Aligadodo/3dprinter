/* setup.js — vitest setup: mock LiteGraph global for unit tests */
import { beforeEach } from 'vitest';

// Minimal LiteGraph mock sufficient for testing:
// - LGraphNode (base class with addInput/addOutput/addWidget/connect/serialize)
// - LGraph (graph with add/remove/clear/serialize/configure)
// - LGraphCanvas (canvas stub)
// - registerNodeType / registered_node_types

// Use a fresh mock before each test file
beforeEach(() => {
  globalThis.LiteGraph = createLiteGraphMock();
});

function createLiteGraphMock() {
  let _nextNodeId = 1;
  let _nextLinkId = 1;

  // ── LGraphNode ──
  function LGraphNode(title) {
    this.id = _nextNodeId++;
    this.title = title || '';
    this.pos = [0, 0];
    this.size = [140, 80];
    this.inputs = [];
    this.outputs = [];
    this.properties = {};
    this.widgets = [];
    this.color = '#444';
    this._wfTypeId = null;
  }

  LGraphNode.prototype.addInput = function (name, type) {
    this.inputs.push({ name: name, type: type || '*', link: null });
  };

  LGraphNode.prototype.addOutput = function (name, type) {
    this.outputs.push({ name: name, type: type || '*', links: [] });
  };

  LGraphNode.prototype.addWidget = function (type, name, value, callback, options) {
    this.widgets.push({ type, name, value, callback, options });
    if (type !== 'button') {
      this.properties[name] = value;
    }
  };

  LGraphNode.prototype.connect = function (slot, targetNode, targetSlot) {
    if (!this.outputs[slot]) return false;
    if (!targetNode.inputs[targetSlot]) return false;
    this.outputs[slot].links = this.outputs[slot].links || [];
    this.outputs[slot].links.push({ target_id: targetNode.id, target_slot: targetSlot });
    targetNode.inputs[targetSlot].link = { origin_id: this.id, origin_slot: slot };
    return true;
  };

  LGraphNode.prototype.findInputSlot = function (name) {
    for (var i = 0; i < this.inputs.length; i++) {
      if (this.inputs[i].name === name) return i;
    }
    return -1;
  };

  LGraphNode.prototype.findOutputSlot = function (name) {
    for (var i = 0; i < this.outputs.length; i++) {
      if (this.outputs[i].name === name) return i;
    }
    return -1;
  };

  LGraphNode.prototype.getBounding = function () {
    return [this.pos[0], this.pos[1], this.pos[0] + this.size[0], this.pos[1] + this.size[1]];
  };

  LGraphNode.prototype.serialize = function () {
    var o = {
      id: this.id, type: this._wfTypeId || '', title: this.title,
      pos: this.pos.slice(), size: this.size.slice(),
      inputs: this.inputs.map(function (s) { return { name: s.name, type: s.type, link: s.link }; }),
      outputs: this.outputs.map(function (s) { return { name: s.name, type: s.type, links: s.links }; }),
      properties: Object.assign({}, this.properties),
      widgets_values: this.widgets.map(function (w) { return w.value; }),
    };
    return o;
  };

  // ── LGraph ──
  function LGraph() {
    this._nodes = [];
    this._links = [];
    this._nodes_by_id = {};
  }

  LGraph.prototype.add = function (item) {
    if (item instanceof LGraphNode) {
      this._nodes.push(item);
      this._nodes_by_id[item.id] = item;
    } else if (item && item.origin_id !== undefined) {
      // link object
      var link = { id: _nextLinkId++, origin_id: item.origin_id, origin_slot: item.origin_slot,
                   target_id: item.target_id, target_slot: item.target_slot, type: item.type || '*' };
      this._links.push(link);
      return link;
    }
  };

  LGraph.prototype.remove = function (node) {
    var idx = this._nodes.indexOf(node);
    if (idx >= 0) this._nodes.splice(idx, 1);
    delete this._nodes_by_id[node.id];
    // Remove connected links
    this._links = this._links.filter(function (l) {
      return l.origin_id !== node.id && l.target_id !== node.id;
    });
  };

  LGraph.prototype.removeLink = function (linkId) {
    this._links = this._links.filter(function (l) { return l.id !== linkId; });
  };

  LGraph.prototype.clear = function () {
    this._nodes = [];
    this._links = [];
    this._nodes_by_id = {};
    _nextNodeId = 1;
    _nextLinkId = 1;
  };

  LGraph.prototype.arrange = function () {
    // Simple column layout
    this._nodes.forEach(function (n, i) {
      n.pos[0] = 200 + 300 * (i % 3);
      n.pos[1] = 100 + 200 * Math.floor(i / 3);
    });
  };

  LGraph.prototype.serialize = function () {
    var self = this;
    return {
      nodes: self._nodes.map(function (n) { return n.serialize(); }),
      links: self._links.map(function (l) { return [l.id, l.origin_id, l.origin_slot, l.target_id, l.target_slot, l.type]; }),
    };
  };

  LGraph.prototype.configure = function (data) {
    // simplified: expects nodes already added, just sets properties
  };

  LGraph.prototype.start = function () {};
  LGraph.prototype.stop = function () {};

  // ── LGraphCanvas (stub) ──
  function LGraphCanvas(canvas, graph) {
    this.canvas = canvas;
    this.graph = graph;
    this.ds = { scale: 1, offset: [0, 0] };
    this.allow_dragcanvas = true;
    this.allow_interaction = true;
    this.allow_dragnodes = true;
    this.visible_nodes = [];
  }

  LGraphCanvas.prototype.setDirty = function () {};
  LGraphCanvas.prototype.zoomToFit = function () {};
  LGraphCanvas.prototype.draw = function () {};
  LGraphCanvas.prototype.getNodeMenuOptions = function () { return []; };

  // ── Module-level state ──
  var registered = {};

  return {
    LGraph: LGraph,
    LGraphNode: LGraphNode,
    LGraphCanvas: LGraphCanvas,
    registered_node_types: registered,
    registerNodeType: function (name, cls) {
      if (registered[name]) {
        console.log('replacing node type:', name);
      }
      registered[name] = cls;
    },
  };
}

// Also export a helper to create a minimal mock for adapter tests
export function createMinimalLiteGraphMock() {
  return {
    LGraph: function () {
      this._nodes = [];
      this._links = null;  // Simulate bug: no _links init
      this.clear = function () { this._nodes = []; };
      this.add = function (n) { this._nodes.push(n); };
      this.arrange = function () {};
    },
    LGraphNode: function () {},
    LGraphCanvas: function () {},
    registerNodeType: function () {},
    registered_node_types: {},
  };
}
