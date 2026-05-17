/* workflow-validator.js — Frontend workflow validation rules */

/**
 * Validate a workflow graph before saving.
 * @param {Object} graph - Serialized graph with { nodes, edges } or { nodes, links }
 * @param {Array} nodeTypes - Array of node type definitions
 * @returns {{ valid: boolean, errors: Array<{nodeId, message}>, warnings: Array<{nodeId, message}> }}
 */
export function validateWorkflow(graph, nodeTypes) {
  const errors = [];
  const warnings = [];

  const nodes = graph.nodes || [];
  const ntMap = {};
  nodeTypes.forEach(nt => { ntMap[nt.id] = nt; });

  // Normalize edges: handle both LiteGraph "links" format and legacy "edges" format
  let edges = [];
  if (graph.links && Array.isArray(graph.links)) {
    edges = graph.links.map(link => {
      if (Array.isArray(link) && link.length >= 5) {
        return { source: String(link[1]), sourcePort: link[2], target: String(link[3]), targetPort: link[4] };
      }
      return null;
    }).filter(Boolean);
  } else if (graph.edges) {
    edges = graph.edges.map(e => ({
      source: String(e.source), sourcePort: e.sourcePort, target: String(e.target), targetPort: e.targetPort
    }));
  }

  // ── Rule 1: No nodes (ERROR) ──
  if (nodes.length === 0) {
    errors.push({ nodeId: null, message: 'Workflow has no nodes' });
    return { valid: false, errors, warnings };
  }

  // ── Rule 2: Duplicate node IDs (ERROR) ──
  const seenIds = new Set();
  nodes.forEach(n => {
    const id = String(n.id);
    if (seenIds.has(id)) {
      errors.push({ nodeId: id, message: `Duplicate node ID: ${id}` });
    }
    seenIds.add(id);
  });

  if (errors.length > 0) {
    return { valid: false, errors, warnings };
  }

  // ── Build connectivity sets ──
  const downstreamOf = {}; // nodeId -> Set of downstream nodeIds
  const upstreamOf = {};   // nodeId -> Set of upstream nodeIds
  const nodeInputEdges = {};  // nodeId -> [{sourceId, targetPort}]

  nodes.forEach(n => {
    const id = String(n.id);
    downstreamOf[id] = new Set();
    upstreamOf[id] = new Set();
    nodeInputEdges[id] = [];
  });

  edges.forEach(e => {
    const src = String(e.source);
    const tgt = String(e.target);
    if (downstreamOf[src]) downstreamOf[src].add(tgt);
    if (upstreamOf[tgt]) upstreamOf[tgt].add(src);
    if (nodeInputEdges[tgt]) {
      nodeInputEdges[tgt].push({ sourceId: src, targetPort: e.targetPort });
    }
  });

  // ── Rule 3: Input node with no consumers (WARNING) ──
  nodes.forEach(n => {
    const typeId = (n.type || '').replace(/^wf_/, '');
    const nt = ntMap[typeId];
    if (nt && nt.category === 'input') {
      if (downstreamOf[String(n.id)].size === 0) {
        warnings.push({
          nodeId: String(n.id),
          message: `Input node "${n.title || nt.label || n.id}" has no downstream consumer`
        });
      }
    }
  });

  // ── Rule 4: Process node with unconnected required input (WARNING) ──
  nodes.forEach(n => {
    const typeId = (n.type || '').replace(/^wf_/, '');
    const nt = ntMap[typeId];
    if (!nt || nt.category === 'input' || nt.category === 'output') return;

    const connectedPorts = new Set();
    (nodeInputEdges[String(n.id)] || []).forEach(e => {
      // targetPort may be numeric (slot index) or string (port name)
      if (typeof e.targetPort === 'number' && nt.inputs && nt.inputs[e.targetPort]) {
        connectedPorts.add(nt.inputs[e.targetPort].name);
      } else {
        connectedPorts.add(String(e.targetPort));
      }
    });

    (nt.inputs || []).forEach(p => {
      if (p.required && !connectedPorts.has(p.name)) {
        warnings.push({
          nodeId: String(n.id),
          message: `Required port "${p.label || p.name}" on "${n.title || nt.label || n.id}" is not connected`
        });
      }
    });
  });

  // ── Rule 5: Output node with no input (WARNING) ──
  nodes.forEach(n => {
    const typeId = (n.type || '').replace(/^wf_/, '');
    const nt = ntMap[typeId];
    if (nt && nt.category === 'output') {
      if (upstreamOf[String(n.id)].size === 0) {
        warnings.push({
          nodeId: String(n.id),
          message: `Output node "${n.title || nt.label || n.id}" has no input`
        });
      }
    }
  });

  // ── Rule 6: Isolated node (WARNING, skip if only 1 node) ──
  if (nodes.length > 1) {
    nodes.forEach(n => {
      const id = String(n.id);
      if (downstreamOf[id].size === 0 && upstreamOf[id].size === 0) {
        const typeId = (n.type || '').replace(/^wf_/, '');
        const nt = ntMap[typeId];
        warnings.push({
          nodeId: id,
          message: `Node "${n.title || (nt && nt.label) || n.id}" is isolated (no connections)`
        });
      }
    });
  }

  return { valid: true, errors, warnings };
}
