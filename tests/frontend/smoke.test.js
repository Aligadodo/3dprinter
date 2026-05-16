/* smoke.test.js — verify test environment works */
import { describe, it, expect } from 'vitest';

describe('Test environment', () => {
  it('has LiteGraph mock', () => {
    expect(globalThis.LiteGraph).toBeDefined();
    expect(globalThis.LiteGraph.LGraph).toBeDefined();
    expect(globalThis.LiteGraph.LGraphNode).toBeDefined();
  });

  it('creates a graph', () => {
    var g = new LiteGraph.LGraph();
    expect(g._nodes).toEqual([]);
    expect(g._links).toEqual([]);
  });

  it('creates a node with ports', () => {
    var n = new LiteGraph.LGraphNode('Test');
    n.addInput('image', 'image');
    n.addOutput('stl', 'stl');
    expect(n.inputs.length).toBe(1);
    expect(n.outputs.length).toBe(1);
    expect(n.findInputSlot('image')).toBe(0);
    expect(n.findOutputSlot('stl')).toBe(0);
  });

  it('finds slot by name', () => {
    var n = new LiteGraph.LGraphNode('Test');
    n.addOutput('mesh', 'stl');
    n.addOutput('preview', 'image');
    expect(n.findOutputSlot('mesh')).toBe(0);
    expect(n.findOutputSlot('preview')).toBe(1);
    expect(n.findOutputSlot('nonexistent')).toBe(-1);
  });

  it('connects two nodes', () => {
    var g = new LiteGraph.LGraph();
    var a = new LiteGraph.LGraphNode('A');
    a.addOutput('image', 'image');
    var b = new LiteGraph.LGraphNode('B');
    b.addInput('image', 'image');
    g.add(a);
    g.add(b);
    var ok = a.connect(0, b, 0);
    expect(ok).toBe(true);
  });
});
