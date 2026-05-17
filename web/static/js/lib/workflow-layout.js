/* workflow-layout.js — Hierarchical auto-layout for workflow DAG */

/**
 * Auto-arrange nodes in a layered left-to-right layout.
 * Handles single pipeline, multi-input, multi-output, and branching.
 *
 * @param {LiteGraph.LGraph} graph - The LiteGraph graph instance
 * @param {Array} nodeTypes - Array of node type definitions (for category info)
 */
export function autoFormatLayout(graph, nodeTypes) {
  if (!graph || !graph._nodes || graph._nodes.length === 0) return;

  const nodes = graph._nodes;
  const ntMap = {};
  nodeTypes.forEach(nt => { ntMap[nt.id] = nt; });

  // Normalize edges from LiteGraph links
  const edges = [];
  if (graph._links) {
    graph._links.forEach(link => {
      edges.push({
        source: String(link.origin_id),
        target: String(link.target_id)
      });
    });
  }

  // Build node lookup
  const nodeMap = {};
  nodes.forEach(n => { nodeMap[String(n.id)] = n; });

  // ── Layer assignment (topological) ──
  const inDegree = {};
  const adj = {}; // nodeId -> [downstream nodeIds]

  nodes.forEach(n => {
    const id = String(n.id);
    inDegree[id] = 0;
    adj[id] = [];
  });

  edges.forEach(e => {
    const src = String(e.source);
    const tgt = String(e.target);
    if (adj[src] && !adj[src].includes(tgt)) {
      adj[src].push(tgt);
    }
    if (inDegree[tgt] !== undefined) {
      inDegree[tgt]++;
    }
  });

  // BFS to assign layers
  const layers = {}; // nodeId -> layer (0-based)
  const queue = [];

  // Root nodes = inDegree 0
  nodes.forEach(n => {
    const id = String(n.id);
    if (inDegree[id] === 0) {
      layers[id] = 0;
      queue.push(id);
    }
  });

  // If no root nodes (all have inDegree > 0, e.g., cycle), assign all to layer 0
  if (queue.length === 0) {
    nodes.forEach(n => { layers[String(n.id)] = 0; });
    return;
  }

  while (queue.length > 0) {
    const cur = queue.shift();
    const curLayer = layers[cur] || 0;
    (adj[cur] || []).forEach(down => {
      const newLayer = curLayer + 1;
      if (layers[down] === undefined || layers[down] < newLayer) {
        layers[down] = newLayer;
      }
      inDegree[down]--;
      if (inDegree[down] === 0) {
        queue.push(down);
      }
    });
  }

  // Handle disconnected nodes (assigned layer 0)
  nodes.forEach(n => {
    const id = String(n.id);
    if (layers[id] === undefined) {
      layers[id] = 0;
    }
  });

  // ── Group nodes by layer ──
  const layerGroups = {}; // layer -> [nodeIds]
  nodes.forEach(n => {
    const id = String(n.id);
    const l = layers[id] || 0;
    if (!layerGroups[l]) layerGroups[l] = [];
    layerGroups[l].push(id);
  });

  // Sort within each layer: input nodes first, then generate, process, output
  const categoryOrder = { input: 0, generate: 1, process: 2, output: 3 };
  const maxLayers = Math.max(...Object.keys(layerGroups).map(Number), 0);

  Object.keys(layerGroups).forEach(l => {
    layerGroups[l].sort((a, b) => {
      const nodeA = nodeMap[a];
      const nodeB = nodeMap[b];
      const typeIdA = (nodeA._wfTypeId || (nodeA.type || '').replace(/^wf_/, ''));
      const typeIdB = (nodeB._wfTypeId || (nodeB.type || '').replace(/^wf_/, ''));
      const ntA = ntMap[typeIdA];
      const ntB = ntMap[typeIdB];
      const catA = ntA ? (categoryOrder[ntA.category] || 99) : 99;
      const catB = ntB ? (categoryOrder[ntB.category] || 99) : 99;
      if (catA !== catB) return catA - catB;
      return parseInt(a) - parseInt(b);
    });
  });

  // ── Positioning ──
  const H_SPACING = 280;
  const V_SPACING = 130;
  const START_X = 80;
  const START_Y = 60;

  // Find max nodes in any layer to compute centering
  let maxNodesInLayer = 0;
  Object.values(layerGroups).forEach(g => {
    if (g.length > maxNodesInLayer) maxNodesInLayer = g.length;
  });

  const maxLayerHeight = maxNodesInLayer * V_SPACING;

  for (let l = 0; l <= maxLayers; l++) {
    const ids = layerGroups[l] || [];
    const x = START_X + l * H_SPACING;
    const layerHeight = ids.length * V_SPACING;
    const yOffset = START_Y + (maxLayerHeight - layerHeight) / 2;

    ids.forEach((nid, i) => {
      const node = nodeMap[nid];
      if (!node) return;
      const y = yOffset + i * V_SPACING;
      node.pos = [x, y];
    });
  }

  // Redraw
  graph.setDirtyCanvas(true, true);
}
