/* wf-core.test.js — unit tests for core workflow editor functions:
 *   _findSlot, _isTypeCompatible, createLiteGraphNodeClass
 *
 * These functions are module-scoped in wf-editor.js. They are duplicated here
 * for isolated testing against the LiteGraph mock from setup.js.
 */

import { describe, it, expect } from 'vitest';

// ── Duplicated from wf-editor.js ──────────────────────────────────────

function _findSlot(node, slotName, isInput) {
  if (!node) return -1;
  var slots = isInput ? node.inputs : node.outputs;
  if (!slots) return -1;
  var fn = isInput ? node.findInputSlot : node.findOutputSlot;
  if (fn) { var r = fn.call(node, slotName); return typeof r === 'number' ? r : (r && r.slot != null ? r.slot : -1); }
  for (var i = 0; i < slots.length; i++) { if (slots[i].name === slotName) return i; }
  return -1;
}

function _isTypeCompatible(srcType, tgtType) {
  if (!srcType || !tgtType) return true;
  if (srcType === tgtType) return true;
  if (srcType === '*' || tgtType === '*') return true;
  if (srcType === 'any' || tgtType === 'any') return true;
  if (srcType === 'file' && ['image', 'stl', 'mesh'].includes(tgtType)) return true;
  if (srcType === 'string' && tgtType === 'image') return true;
  if ((srcType === 'stl' && tgtType === 'mesh') || (srcType === 'mesh' && tgtType === 'stl')) return true;
  if (srcType === 'json') return true;
  return false;
}

function createLiteGraphNodeClass(typeId, nodeTypes) {
  const nt = nodeTypes.find(n => n.id === typeId);
  if (!nt) return null;

  function WFNode(title) {
    LiteGraph.LGraphNode.call(this, title || nt.label);
    this._wfTypeId = typeId;

    (nt.inputs||[]).forEach((p, i) => this.addInput(p.label || p.name, p.type || '*'));
    (nt.outputs||[]).forEach((p, i) => this.addOutput(p.label || p.name, p.type || '*'));

    if (nt.color) this.color = nt.color;

    this.addWidget('button', '✕', null, () => { /* noop in test */ });

    this.properties = {};
    Object.entries(nt.params||{}).forEach(([key, spec]) => {
      this.properties[key] = spec.default;
      if (spec.type === 'bool') this.addWidget('toggle', spec.label || key, this.properties[key], v => { this.properties[key] = v; });
      else if (spec.type === 'choice') this.addWidget('combo', spec.label || key, this.properties[key], v => { this.properties[key] = v; }, { values: spec.choices||[] });
      else if (spec.type === 'int') this.addWidget('number', spec.label || key, this.properties[key], v => { this.properties[key] = Math.round(v); }, { min: spec.min||-99999, max: spec.max||99999, step: 1 });
      else if (spec.type === 'float') this.addWidget('number', spec.label || key, this.properties[key], v => { this.properties[key] = v; }, { min: spec.min||-99999, max: spec.max||99999 });
      else this.addWidget('text', spec.label || key, String(this.properties[key]||''), v => { this.properties[key] = v; });
    });
  }

  WFNode.prototype = Object.create(LiteGraph.LGraphNode.prototype);
  WFNode.prototype.constructor = WFNode;

  WFNode.prototype.getTitle = function() {
    return this.title || nt.label;
  };

  WFNode.prototype.connect = function(slot, target_node, target_slot, options) {
    if (!this.outputs[slot] || !target_node.inputs[target_slot]) return false;
    var srcType = this.outputs[slot].type || '';
    var tgtType = target_node.inputs[target_slot].type || '';
    if (!_isTypeCompatible(srcType, tgtType)) return false;

    if (srcType !== tgtType && srcType !== '*' && tgtType !== '*' && srcType !== '' && tgtType !== '') {
      this.outputs[slot].type = '*';
      target_node.inputs[target_slot].type = '*';
      var result = LiteGraph.LGraphNode.prototype.connect.call(this, slot, target_node, target_slot, options);
      this.outputs[slot].type = srcType;
      target_node.inputs[target_slot].type = tgtType;
      return result;
    }
    return LiteGraph.LGraphNode.prototype.connect.call(this, slot, target_node, target_slot, options);
  };

  return WFNode;
}

// ── Fixtures ──────────────────────────────────────────────────────────

const MOCK_NODE_TYPES = [
  {
    id: 'triposr',
    label: 'TripoSR',
    category: 'process',
    color: '#336699',
    inputs: [{ name: 'image', type: 'image', label: 'Image' }],
    outputs: [
      { name: 'mesh', type: 'stl', label: 'Mesh' },
      { name: 'preview', type: 'image', label: 'Preview' }
    ],
    params: {
      resolution: { type: 'int', default: 384, min: 64, max: 384, label: 'Resolution' },
      format: { type: 'choice', default: 'glb', choices: ['glb', 'obj', 'stl'], label: 'Format' }
    }
  },
  {
    id: 'repair',
    label: 'Repair',
    category: 'process',
    color: '#994422',
    inputs: [{ name: 'mesh', type: 'stl', label: 'Mesh' }],
    outputs: [{ name: 'repaired_mesh', type: 'stl', label: 'Repaired' }],
    params: {
      scale: { type: 'float', default: 1.0, min: 0.1, max: 10.0, label: 'Scale' },
      verbose: { type: 'bool', default: false, label: 'Verbose' }
    }
  },
  {
    id: 'file_input',
    label: 'File Input',
    category: 'input',
    color: '#226622',
    inputs: [],
    outputs: [{ name: 'file', type: 'file', label: 'File' }],
    params: {}
  },
  {
    id: 'text_input',
    label: 'Text Input',
    category: 'input',
    color: '#226622',
    inputs: [],
    outputs: [{ name: 'text', type: 'string', label: 'Text' }],
    params: {
      text: { type: 'text', default: '', label: 'Text' }
    }
  },
  {
    id: 'output_file',
    label: 'Output File',
    category: 'output',
    color: '#662222',
    inputs: [{ name: 'file', type: 'file', label: 'File' }],
    outputs: [],
    params: { filename: { type: 'text', default: 'output.stl', label: 'Filename' } }
  }
];

// ── Tests: _findSlot ──────────────────────────────────────────────────

describe('_findSlot', () => {
  it('finds an output slot by name', () => {
    var n = new LiteGraph.LGraphNode('Test');
    n.addOutput('mesh', 'stl');
    n.addOutput('preview', 'image');
    expect(_findSlot(n, 'mesh', false)).toBe(0);
    expect(_findSlot(n, 'preview', false)).toBe(1);
  });

  it('finds an input slot by name', () => {
    var n = new LiteGraph.LGraphNode('Test');
    n.addInput('image', 'image');
    n.addInput('mesh', 'stl');
    expect(_findSlot(n, 'image', true)).toBe(0);
    expect(_findSlot(n, 'mesh', true)).toBe(1);
  });

  it('returns -1 for nonexistent slot name', () => {
    var n = new LiteGraph.LGraphNode('Test');
    n.addOutput('mesh', 'stl');
    expect(_findSlot(n, 'nonexistent', false)).toBe(-1);
  });

  it('returns -1 when node has no inputs', () => {
    var n = new LiteGraph.LGraphNode('Test');
    expect(_findSlot(n, 'image', true)).toBe(-1);
  });

  it('returns -1 when node has no outputs', () => {
    var n = new LiteGraph.LGraphNode('Test');
    expect(_findSlot(n, 'mesh', false)).toBe(-1);
  });

  it('returns -1 for null/undefined node', () => {
    expect(_findSlot(null, 'mesh', false)).toBe(-1);
    expect(_findSlot(undefined, 'mesh', false)).toBe(-1);
  });

  it('falls back to linear scan when findOutputSlot is missing', () => {
    var n = new LiteGraph.LGraphNode('Test');
    n.addOutput('mesh', 'stl');
    delete n.findOutputSlot; // remove LiteGraph API
    n.findInputSlot = null;
    expect(_findSlot(n, 'mesh', false)).toBe(0);
  });
});

// ── Tests: _isTypeCompatible ──────────────────────────────────────────

describe('_isTypeCompatible', () => {
  it('returns true when types are identical', () => {
    expect(_isTypeCompatible('image', 'image')).toBe(true);
    expect(_isTypeCompatible('stl', 'stl')).toBe(true);
    expect(_isTypeCompatible('mesh', 'mesh')).toBe(true);
  });

  it('returns true when either type is empty/null/undefined', () => {
    expect(_isTypeCompatible('', 'image')).toBe(true);
    expect(_isTypeCompatible('image', '')).toBe(true);
    expect(_isTypeCompatible(null, 'image')).toBe(true);
    expect(_isTypeCompatible('image', undefined)).toBe(true);
  });

  it('returns true when either type is wildcard *', () => {
    expect(_isTypeCompatible('*', 'image')).toBe(true);
    expect(_isTypeCompatible('stl', '*')).toBe(true);
    expect(_isTypeCompatible('*', '*')).toBe(true);
  });

  it('returns true when either type is "any"', () => {
    expect(_isTypeCompatible('any', 'image')).toBe(true);
    expect(_isTypeCompatible('stl', 'any')).toBe(true);
  });

  it('allows file → image, stl, mesh', () => {
    expect(_isTypeCompatible('file', 'image')).toBe(true);
    expect(_isTypeCompatible('file', 'stl')).toBe(true);
    expect(_isTypeCompatible('file', 'mesh')).toBe(true);
  });

  it('does NOT allow file → string', () => {
    expect(_isTypeCompatible('file', 'string')).toBe(false);
  });

  it('allows string → image (text prompts)', () => {
    expect(_isTypeCompatible('string', 'image')).toBe(true);
  });

  it('does NOT allow string → stl', () => {
    expect(_isTypeCompatible('string', 'stl')).toBe(false);
  });

  it('allows stl ↔ mesh interchange both ways', () => {
    expect(_isTypeCompatible('stl', 'mesh')).toBe(true);
    expect(_isTypeCompatible('mesh', 'stl')).toBe(true);
  });

  it('allows json → anything', () => {
    expect(_isTypeCompatible('json', 'image')).toBe(true);
    expect(_isTypeCompatible('json', 'stl')).toBe(true);
    expect(_isTypeCompatible('json', 'file')).toBe(true);
  });

  it('rejects incompatible types', () => {
    expect(_isTypeCompatible('image', 'stl')).toBe(false);
    expect(_isTypeCompatible('stl', 'image')).toBe(false);
    expect(_isTypeCompatible('preview', 'mesh')).toBe(false);
  });
});

// ── Tests: createLiteGraphNodeClass ───────────────────────────────────

describe('createLiteGraphNodeClass', () => {
  it('returns null for unknown typeId', () => {
    var cls = createLiteGraphNodeClass('nonexistent', MOCK_NODE_TYPES);
    expect(cls).toBeNull();
  });

  it('returns a constructor function for valid typeId', () => {
    var cls = createLiteGraphNodeClass('triposr', MOCK_NODE_TYPES);
    expect(cls).toBeInstanceOf(Function);
    expect(cls.name).toBe('WFNode');
  });

  it('created node has _wfTypeId set', () => {
    var WFNode = createLiteGraphNodeClass('triposr', MOCK_NODE_TYPES);
    var node = new WFNode();
    expect(node._wfTypeId).toBe('triposr');
  });

  it('created node inherits from LGraphNode', () => {
    var WFNode = createLiteGraphNodeClass('triposr', MOCK_NODE_TYPES);
    var node = new WFNode();
    expect(node instanceof LiteGraph.LGraphNode).toBe(true);
  });

  it('creates correct number of inputs and outputs', () => {
    var WFNode = createLiteGraphNodeClass('triposr', MOCK_NODE_TYPES);
    var node = new WFNode();
    expect(node.inputs.length).toBe(1);  // image
    expect(node.outputs.length).toBe(2); // mesh, preview
  });

  it('sets input port names and types correctly', () => {
    var WFNode = createLiteGraphNodeClass('triposr', MOCK_NODE_TYPES);
    var node = new WFNode();
    expect(node.inputs[0].name).toBe('Image');
    expect(node.inputs[0].type).toBe('image');
  });

  it('sets output port names and types correctly', () => {
    var WFNode = createLiteGraphNodeClass('triposr', MOCK_NODE_TYPES);
    var node = new WFNode();
    expect(node.outputs[0].name).toBe('Mesh');
    expect(node.outputs[0].type).toBe('stl');
    expect(node.outputs[1].name).toBe('Preview');
    expect(node.outputs[1].type).toBe('image');
  });

  it('applies color from node type definition', () => {
    var WFNode = createLiteGraphNodeClass('triposr', MOCK_NODE_TYPES);
    var node = new WFNode();
    expect(node.color).toBe('#336699');
  });

  it('uses default title from node type label', () => {
    var WFNode = createLiteGraphNodeClass('triposr', MOCK_NODE_TYPES);
    var node = new WFNode();
    expect(node.title).toBe('TripoSR');
  });

  it('allows custom title override', () => {
    var WFNode = createLiteGraphNodeClass('triposr', MOCK_NODE_TYPES);
    var node = new WFNode('Custom Title');
    expect(node.title).toBe('Custom Title');
  });

  it('getTitle returns title or label', () => {
    var WFNode = createLiteGraphNodeClass('triposr', MOCK_NODE_TYPES);
    var node = new WFNode();
    expect(node.getTitle()).toBe('TripoSR');
    node.title = 'Custom';
    expect(node.getTitle()).toBe('Custom');
  });

  it('creates params as properties with defaults', () => {
    var WFNode = createLiteGraphNodeClass('triposr', MOCK_NODE_TYPES);
    var node = new WFNode();
    expect(node.properties.resolution).toBe(384);
    expect(node.properties.format).toBe('glb');
  });

  it('creates widgets for all param types', () => {
    var WFNode = createLiteGraphNodeClass('repair', MOCK_NODE_TYPES);
    var node = new WFNode();
    // repair has: float (scale), bool (verbose) → 2 param widgets + 1 delete button
    expect(node.widgets.length).toBe(3);
    expect(node.widgets[0].type).toBe('button'); // delete button
    expect(node.widgets[1].type).toBe('number'); // scale
    expect(node.widgets[2].type).toBe('toggle'); // verbose
  });

  it('handles node type with no params', () => {
    var WFNode = createLiteGraphNodeClass('file_input', MOCK_NODE_TYPES);
    var node = new WFNode();
    expect(node.properties).toEqual({});
    // only delete button widget
    expect(node.widgets.length).toBe(1);
  });

  it('handles node type with text param', () => {
    var WFNode = createLiteGraphNodeClass('text_input', MOCK_NODE_TYPES);
    var node = new WFNode();
    expect(node.properties.text).toBe('');
    var textWidget = node.widgets.find(w => w.name === 'Text');
    expect(textWidget).toBeDefined();
    expect(textWidget.type).toBe('text');
  });

  describe('WFNode.connect — lenient type checking', () => {
    function makeNode(typeId) {
      var WFNode = createLiteGraphNodeClass(typeId, MOCK_NODE_TYPES);
      return new WFNode();
    }

    it('connects two nodes with matching types', () => {
      var src = makeNode('triposr');    // output[0] = mesh (stl)
      var tgt = makeNode('repair');     // input[0] = mesh (stl)
      expect(src.connect(0, tgt, 0)).toBe(true);
    });

    it('connects stl → mesh via lenient compatibility', () => {
      // triposr output[0] is 'mesh' with type 'stl'
      // Let's make a custom node type that explicitly tests stl→mesh
      var nodeTypes = [
        {
          id: 'stl_out', label: 'STL Out', category: 'process',
          inputs: [],
          outputs: [{ name: 'out', type: 'stl', label: 'Out' }],
          params: {}
        },
        {
          id: 'mesh_in', label: 'Mesh In', category: 'process',
          inputs: [{ name: 'in', type: 'mesh', label: 'In' }],
          outputs: [],
          params: {}
        }
      ];
      var src = createLiteGraphNodeClass('stl_out', nodeTypes);
      var tgt = createLiteGraphNodeClass('mesh_in', nodeTypes);
      expect(new src().connect(0, new tgt(), 0)).toBe(true);
    });

    it('rejects incompatible types', () => {
      var nodeTypes = [
        {
          id: 'img_out', label: 'Img Out', category: 'process',
          inputs: [],
          outputs: [{ name: 'out', type: 'image', label: 'Out' }],
          params: {}
        },
        {
          id: 'stl_in', label: 'STL In', category: 'process',
          inputs: [{ name: 'in', type: 'stl', label: 'In' }],
          outputs: [],
          params: {}
        }
      ];
      var src = createLiteGraphNodeClass('img_out', nodeTypes);
      var tgt = createLiteGraphNodeClass('stl_in', nodeTypes);
      expect(new src().connect(0, new tgt(), 0)).toBe(false);
    });

    it('returns false when output slot does not exist', () => {
      var src = makeNode('triposr');
      var tgt = makeNode('repair');
      expect(src.connect(99, tgt, 0)).toBe(false);
    });

    it('returns false when input slot does not exist', () => {
      var src = makeNode('triposr');
      var tgt = makeNode('repair');
      expect(src.connect(0, tgt, 99)).toBe(false);
    });

    it('restores original types after lenient connection', () => {
      var nodeTypes = [
        {
          id: 'file_out', label: 'File Out', category: 'input',
          inputs: [],
          outputs: [{ name: 'file', type: 'file', label: 'File' }],
          params: {}
        },
        {
          id: 'img_in', label: 'Img In', category: 'process',
          inputs: [{ name: 'image', type: 'image', label: 'Image' }],
          outputs: [],
          params: {}
        }
      ];
      var WFSource = createLiteGraphNodeClass('file_out', nodeTypes);
      var WFTarget = createLiteGraphNodeClass('img_in', nodeTypes);
      var src = new WFSource();
      var tgt = new WFTarget();
      var result = src.connect(0, tgt, 0);
      expect(result).toBe(true);
      // Types should be restored after lenient connect
      expect(src.outputs[0].type).toBe('file');
      expect(tgt.inputs[0].type).toBe('image');
    });
  });
});
