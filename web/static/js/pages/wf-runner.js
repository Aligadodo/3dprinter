/* wf-runner.js — Workflow Runner page (DAG + tabs + node detail + SSE) */
import { api } from '../api.js';
import { t, getLang } from '../i18n.js';
import { escHtml, toast, showImageModal } from '../utils.js';
import { renderNodeDetailPanel } from '../components/node-detail.js';

let wfRunnerGraph = null;
let wfRunnerCanvas = null;
let wfSSE = null;

export default async function renderWorkflowRunner(main, hash) {
  const instId = hash.slice(20);

  window._pageCleanup = () => {
    if (wfSSE) { wfSSE.close(); wfSSE = null; }
    if (wfRunnerGraph) { wfRunnerGraph = null; }
    if (wfRunnerCanvas) { wfRunnerCanvas = null; }
  };

  main.innerHTML = `<h2>${t('wf.runner.title')}</h2><div id="wf-runner-body">${t('wf.runner.loading')}</div>`;

  let inst, wfDef, nodeTypes;
  try {
    [inst, nodeTypes] = await Promise.all([
      api('GET', `/workflows/instances/${instId}`),
      api('GET', '/node-types'),
    ]);
    try { wfDef = await api('GET', `/workflows/${inst.workflow_id}`); }
    catch (_) { wfDef = inst.workflow || {}; }
  } catch (e) {
    document.getElementById('wf-runner-body').innerHTML = `<div class="error-box"><p>${e.message}</p></div>`;
    return;
  }

  const ntMap = {};
  (nodeTypes.types||[]).forEach(nt => { ntMap[nt.id] = nt; });

  const nrMap = {};
  (inst.node_runs||[]).forEach(nr => { nrMap[nr.node_id] = nr; });

  const body = document.getElementById('wf-runner-body');
  const totalNodes = (inst.node_runs||[]).length;
  const doneNodes = (inst.node_runs||[]).filter(nr => nr.status==='completed').length;
  const statusEmoji = inst.status === 'completed' ? '✅' : inst.status === 'failed' ? '❌' : inst.status === 'running' ? '⚡' : '⏳';
  const isRunning = inst.status === 'running' || inst.status === 'queued';

  const roundNum = inst.round || 0;
  body.innerHTML = `
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">
      <span style="font-size:14px;font-weight:700">${statusEmoji} ${escHtml(inst.workflow_name||'')}</span>
      <span class="badge badge-${inst.status==='completed'?'completed':inst.status==='failed'?'failed':'running'}">${inst.status}</span>
      ${roundNum > 0 ? `<span class="badge badge-workflow" title="${t('wf.runner.round')} ${roundNum}">↻ R${roundNum}</span>` : ''}
      <span style="flex:1"></span>
      ${isRunning ? `<button class="btn btn-sm btn-danger" id="wf-cancel-btn">${t('wf.runner.cancel')}</button>` : ''}
      <button class="btn btn-sm" onclick="location.reload()">🔄</button>
      <button class="btn btn-sm" onclick="import('../pages/wf-runner.js').then(m=>m._downloadOutputs('${instId}'))">📥</button>
      <a href="#/workflow/${inst.workflow_id}" class="btn btn-sm">🔧 Edit</a>
    </div>
    <div class="progress-bar"><div class="fill" style="width:${totalNodes?(doneNodes/totalNodes*100):0}%"></div></div>
    <div class="progress-text">${doneNodes}/${totalNodes} ${t('wf.runner.progress')}${roundNum > 0 ? ' — ' + t('wf.runner.round') + ' ' + roundNum : ''}</div>

    <div class="wf-runner-layout">
      <div class="wf-dag-panel" id="wf-dag-panel"></div>
      <div class="wf-results-panel">
        <div class="wf-results-tabs" id="wf-results-tabs"></div>
        <div class="wf-results-content" id="wf-results-content"></div>
      </div>
    </div>
  `;

  // Build DAG
  try { buildRunnerDAG(inst, wfDef, ntMap, nrMap, instId); }
  catch (e) { console.error('buildRunnerDAG error:', e); body.innerHTML += `<div class="error-box"><p>DAG render error: ${e.message}</p></div>`; }
  // Build tabs
  try { buildNodeTabs(inst, nrMap, ntMap); }
  catch (e) { console.error('buildNodeTabs error:', e); body.innerHTML += `<div class="error-box"><p>Tab render error: ${e.message}</p></div>`; }
  // Wire events
  wireRunnerEvents(inst, nrMap, ntMap, instId);

  // SSE for live updates — engine emits: node_start, node_complete, node_error, node_progress, done, cancelled, workflow_complete
  if (isRunning) {
    wfSSE = new EventSource(`/api/workflows/instances/${instId}/stream`);
    wfSSE.addEventListener('node_start', e => {
      try {
        const data = JSON.parse(e.data);
        if (data.node_id) {
          nrMap[data.node_id] = { ...(nrMap[data.node_id]||{}), node_id: data.node_id, status: 'running', node_type: data.node_type };
          addOrUpdateRunnerNode(data.node_id, nrMap[data.node_id], wfDef, ntMap);
        }
      } catch(_) {}
    });
    wfSSE.addEventListener('node_complete', e => {
      try {
        const data = JSON.parse(e.data);
        if (data.node_id) {
          nrMap[data.node_id] = { ...(nrMap[data.node_id]||{}), ...data, status: 'completed' };
          updateRunnerNode(data.node_id, { status: 'completed' });
          refreshNodeTab(data.node_id, nrMap, ntMap);
        }
      } catch(_) {}
    });
    wfSSE.addEventListener('node_error', e => {
      try {
        const data = JSON.parse(e.data);
        if (data.node_id) {
          nrMap[data.node_id] = { ...(nrMap[data.node_id]||{}), error: data.error, status: 'failed' };
          updateRunnerNode(data.node_id, { status: 'failed' });
          refreshNodeTab(data.node_id, nrMap, ntMap);
        }
      } catch(_) {}
    });
    wfSSE.addEventListener('node_progress', e => {
      try {
        const data = JSON.parse(e.data);
        if (data.node_id) {
          updateRunnerNode(data.node_id, { status: 'running' });
        }
      } catch(_) {}
    });
    wfSSE.addEventListener('workflow_complete', () => {
      toast(t('wf.runner.completed'), 'success');
      setTimeout(() => location.reload(), 1000);
    });
    wfSSE.addEventListener('done', () => { wfSSE.close(); });
    wfSSE.addEventListener('cancelled', () => {
      toast(t('wf.runner.cancelled'), 'success');
      setTimeout(() => location.reload(), 500);
    });
    wfSSE.onerror = () => {};
  }
}

// ── DAG ──
function buildRunnerDAG(inst, wfDef, ntMap, nrMap, instId) {
  const panel = document.getElementById('wf-dag-panel');
  const graphData = wfDef.graph || inst.workflow_graph || {};
  if (!graphData.nodes || graphData.nodes.length === 0) {
    panel.innerHTML = '<div style="padding:40px;text-align:center;color:var(--fg2)">No nodes</div>';
    return;
  }

  // LiteGraph requires a <canvas> element, not a div
  panel.innerHTML = '';
  const canvas = document.createElement('canvas');
  panel.appendChild(canvas);

  // Size canvas to fill panel before passing to LiteGraph
  function updateRunnerCanvasSize() {
    const r = panel.getBoundingClientRect();
    const w = Math.max(r.width, 400);
    const h = Math.max(r.height, 280);
    canvas.width = w;
    canvas.height = h;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
  }
  updateRunnerCanvasSize();

  wfRunnerGraph = new LiteGraph.LGraph();
  wfRunnerCanvas = new LiteGraph.LGraphCanvas(canvas, wfRunnerGraph);

  // Read-only DAG viewer — disable drag/pan but keep clicks for tab navigation
  if (wfRunnerCanvas) {
    wfRunnerCanvas.allow_dragcanvas = false;
    wfRunnerCanvas.allow_dragnodes = false;
    wfRunnerCanvas.allow_searchbox = false;
  }

  // Lock viewport at default zoom — guard against uninitialized ds.offset
  try {
    if (wfRunnerCanvas && wfRunnerCanvas.ds) {
      wfRunnerCanvas.ds.scale = 1.0;
      if (!wfRunnerCanvas.ds.offset) {
        wfRunnerCanvas.ds.offset = [0, 0];
      }
      wfRunnerCanvas.ds.offset[0] = 0;
      wfRunnerCanvas.ds.offset[1] = 0;
    }
  } catch (_) { /* ds not initialized yet, skip */ }

  const nodeLookup = {};
  graphData.nodes.forEach(n => {
    const nr = nrMap[n.id] || {};
    const nt = ntMap[(n.type||'').replace(/^wf_/, '')] || {};
    const node = new LiteGraph.LGraphNode(n.title || nt.label || n.type);
    node.id = n.id;
    // Ensure pos is a valid array-like (LiteGraph pos setter requires .length >= 2)
    const rawPos = n.pos;
    node.pos = (Array.isArray(rawPos) && rawPos.length >= 2) ? rawPos : [100, 100];
    node._wfType = n.type;
    node._status = nr.status || 'queued';

    const statusColors = { completed: '#3fb950', running: '#58a6ff', failed: '#f85149', cancelled: '#8b949e', queued: '#30363d' };
    node.color = statusColors[node._status] || '#30363d';

    (nt.inputs||[]).forEach((p, i) => node.addInput(p.label || p.name, p.type || '*'));
    (nt.outputs||[]).forEach((p, i) => node.addOutput(p.label || p.name, p.type || '*'));
    node.size = [220, Math.max(100, 60 + Math.max(nt.inputs?.length||0, nt.outputs?.length||0) * 14)];

    wfRunnerGraph.add(node);
    nodeLookup[n.id] = node;
  });

  // Handle both LiteGraph "links" format and legacy "edges" format
  const rawEdges = graphData.links ? graphData.links.map(link => {
    if (Array.isArray(link) && link.length >= 5) {
      return { source: link[1], sourcePort: link[2], target: link[3], targetPort: link[4] };
    }
    return null;
  }).filter(Boolean) : (graphData.edges || []);
  rawEdges.forEach(e => {
    const srcNode = nodeLookup[e.source];
    const tgtNode = nodeLookup[e.target];
    if (srcNode && tgtNode) {
      const srcOut = e.sourcePort != null ? (typeof e.sourcePort==='number'?e.sourcePort:srcNode.findOutputSlot(e.sourcePort)) : 0;
      const tgtIn = e.targetPort != null ? (typeof e.targetPort==='number'?e.targetPort:tgtNode.findInputSlot(e.targetPort)) : 0;
      if (srcOut >= 0 && tgtIn >= 0) wfRunnerGraph.add({source:srcNode, target:tgtNode, sourcePort:srcOut, targetPort:tgtIn});
    }
  });

  // Click node → select tab
  wfRunnerCanvas.onNodeSelected = (node) => {
    if (node && node.id != null) {
      const tab = document.querySelector(`.wf-results-tabs button[data-tab="${node.id}"]`);
      if (tab) tab.click();
    }
  };

  // Double-click node → open task
  wfRunnerCanvas.onNodeDblClicked = (node) => {
    const nr = nrMap[node.id];
    if (nr && nr.task_id) location.hash = '#/task/' + nr.task_id;
  };

  // Single draw (no animation loop needed for static DAG viewer)
  wfRunnerGraph.arrange();
  try {
    wfRunnerCanvas.setDirty(true, true);
    wfRunnerCanvas.draw(true, true);
  } catch (e) {
    console.error('DAG draw error:', e);
    body.innerHTML += `<div class="error-box"><p>DAG draw error: ${e.message}</p></div>`;
  }
}

// ── Node Tabs ──
function buildNodeTabs(inst, nrMap, ntMap) {
  const tabs = document.getElementById('wf-results-tabs');
  const content = document.getElementById('wf-results-content');
  const graphData = inst.workflow_graph || inst.workflow || {};

  const nodeRuns = inst.node_runs || [];
  const graphNodes = graphData.nodes || [];
  const graphEdges = graphData.links
    ? graphData.links.map(link => {
        if (Array.isArray(link) && link.length >= 5) {
          return { source: link[1], sourcePort: link[2], target: link[3], targetPort: link[4] };
        }
        return null;
      }).filter(Boolean)
    : (graphData.edges || []);

  // Build lookup: node ID → graph node
  const graphNodeMap = {};
  graphNodes.forEach(n => { graphNodeMap[String(n.id)] = n; });

  // Build upstream edge lookup: target node ID → [{sourceId, sourcePort, targetPort}]
  const upstreamEdges = {};
  graphEdges.forEach(e => {
    const tgtId = String(e.target);
    if (!upstreamEdges[tgtId]) upstreamEdges[tgtId] = [];
    upstreamEdges[tgtId].push({ sourceId: String(e.source), sourcePort: e.sourcePort, targetPort: e.targetPort });
  });

  // Tabs
  let tabsHTML = `<button class="active" data-tab="overview">${t('wf.runner.overview')}</button>`;
  nodeRuns.forEach(nr => {
    const node = graphNodeMap[String(nr.node_id)] || {};
    const nt = ntMap[(node.type||'').replace(/^wf_/, '')] || {};
    const label = node.title || nt.label || nr.node_id;
    tabsHTML += `<button data-tab="${nr.node_id}">${escHtml(label)}</button>`;
  });
  tabs.innerHTML = tabsHTML;

  // Overview content
  let overviewHTML = `<div id="wf-tab-overview"><div class="wf-overview-grid">`;
  nodeRuns.forEach(nr => {
    const node = graphNodeMap[String(nr.node_id)] || {};
    const nt = ntMap[(node.type||'').replace(/^wf_/, '')] || {};
    const statusEmoji = nr.status === 'completed' ? '✅' : nr.status === 'running' ? '⚡' : nr.status === 'failed' ? '❌' : '⏳';
    const statusCls = nr.status === 'completed' ? 'green' : nr.status === 'running' ? 'accent' : nr.status === 'failed' ? 'red' : 'fg2';

    // Count inputs/outputs for summary
    const edgesIn = upstreamEdges[String(nr.node_id)] || [];
    const inputCount = edgesIn.length;
    const ctxOutputsForCount = (inst.context && inst.context[String(nr.node_id)]) || {};
    const nrOutputKeys = Object.keys(nr.outputs || {});
    const ctxOutputKeys = Object.keys(ctxOutputsForCount).filter(k => !k.startsWith('_') && typeof ctxOutputsForCount[k] === 'string');
    const outputCount = Math.max(nrOutputKeys.length, ctxOutputKeys.length) + (nr.output_files || []).length;

    overviewHTML += `<div class="wf-overview-card" data-node="${nr.node_id}" onclick="document.querySelector('.wf-results-tabs button[data-tab=\\'${nr.node_id}\\']').click()">
      <div class="ovc-header">
        <span class="ovc-dot" style="background:var(--${statusCls})"></span>
        <span class="ovc-title">${statusEmoji} ${escHtml(node.title || nt.label || nr.node_id)}</span>
      </div>
      <div class="ovc-meta">
        <span>📥 ${inputCount} input${inputCount!==1?'s':''}</span>
        <span>📤 ${outputCount} output${outputCount!==1?'s':''}</span>
        ${nr.task_id ? `<a href="#/task/${nr.task_id}" class="ovc-task-link" onclick="event.stopPropagation()">🔗 ${t('node.viewTask')}</a>` : ''}
      </div>
      ${nr.error ? `<div class="ovc-error">⚠ ${escHtml(nr.error)}</div>` : ''}
    </div>`;
  });
  overviewHTML += `</div></div>`;
  content.innerHTML = overviewHTML;

  // Individual node tab content
  nodeRuns.forEach(nr => {
    const nid = String(nr.node_id);
    const node = graphNodeMap[nid] || {};
    const nt = ntMap[(node.type||'').replace(/^wf_/, '')] || {};

    // Compute inputs: upstream node outputs connected to this node's input ports
    const inputs = {};
    const edgesIn = upstreamEdges[nid] || [];
    edgesIn.forEach(e => {
      const srcNr = nrMap[e.sourceId];
      // Try node_run outputs first, then fallback to workflow context
      const srcOutputs = (srcNr && srcNr.outputs) || (inst.context && inst.context[String(e.sourceId)]) || {};
      if (srcOutputs[e.sourcePort]) {
        inputs[e.targetPort || e.sourcePort] = srcOutputs[e.sourcePort];
      }
    });

    // Compute outputs: node_run outputs > context > empty
    const ctxOutputs = (inst.context && inst.context[nid]) || {};
    // Filter out internal keys (_inputs, _params, _upstream)
    const cleanCtxOutputs = {};
    if (ctxOutputs && typeof ctxOutputs === 'object') {
      Object.entries(ctxOutputs).forEach(([k, v]) => {
        if (!k.startsWith('_') && typeof v === 'string') cleanCtxOutputs[k] = v;
      });
    }
    const outputs = (nr.outputs && Object.keys(nr.outputs).length) ? { ...nr.outputs }
      : (Object.keys(cleanCtxOutputs).length ? cleanCtxOutputs : {});

    // Compute params from node properties
    const params = {};
    if (node.properties && typeof node.properties === 'object') {
      Object.entries(node.properties).forEach(([k, v]) => {
        params[k] = { value: v, source: 'editor' };
      });
    }

    const detailHTML = `<div id="wf-tab-${nr.node_id}" style="display:none">
      ${renderNodeDetailPanel({ nid, node, nr, nt, inputs, outputs, taskFiles: nr.output_files || (nr.task && nr.task.output_files) || [], params, showTaskLink: true })}
      ${nr.status === 'completed' && nr.node_id ? `<div class="nd-replay-bar">
        <button class="btn btn-sm btn-primary" onclick="import('../pages/wf-runner.js').then(m=>m._replayFrom('${instId}','${nr.node_id}'))">↻ ${t('wf.runner.replay')}</button>
      </div>` : ''}
    </div>`;
    content.insertAdjacentHTML('beforeend', detailHTML);
  });
}

function wireRunnerEvents(inst, nrMap, ntMap, instId) {
  const tabs = document.querySelectorAll('.wf-results-tabs button');
  tabs.forEach(btn => {
    btn.addEventListener('click', () => {
      tabs.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tabId = btn.dataset.tab;
      document.querySelectorAll('#wf-results-content > div').forEach(d => d.style.display = 'none');
      const target = document.getElementById('wf-tab-' + tabId);
      if (target) target.style.display = 'block';
    });
  });

  // Cancel button
  const cancelBtn = document.getElementById('wf-cancel-btn');
  if (cancelBtn) cancelBtn.addEventListener('click', async () => {
    try { await api('POST', `/workflows/instances/${instId}/cancel`); }
    catch (e) { toast(e.message, 'error'); }
    toast(t('wf.runner.cancelled'), 'success');
    setTimeout(() => location.reload(), 500);
  });
}

function refreshNodeTab(nodeId, nrMap, ntMap) {
  // Re-render the tab content for this node
  const nr = nrMap[nodeId];
  if (!nr) return;
  const tabContent = document.getElementById('wf-tab-' + nodeId);
  if (!tabContent) return;
  // Simple status update in overview
  const overviewCard = document.querySelector(`#wf-tab-overview .wf-node-card:nth-child(${Object.keys(nrMap).indexOf(String(nodeId))+1})`);
  // For now, just update the DAG node
}

// ── Runner graph updates ──
function addOrUpdateRunnerNode(nodeId, nr, wfDef, ntMap) {
  if (!wfRunnerGraph) return;
  // Check if node already exists
  const existing = wfRunnerGraph._nodes.find(n => String(n.id) === String(nodeId));
  if (existing) {
    updateRunnerNode(nodeId, { status: nr.status || 'running' });
    return;
  }
  // Find node definition from workflow graph
  const graphData = wfDef.graph || {};
  const graphNodes = graphData.nodes || [];
  const nodeDef = graphNodes.find(n => String(n.id) === String(nodeId));
  if (!nodeDef) return; // Node not in graph definition
  const nt = ntMap[(nodeDef.type||'').replace(/^wf_/, '')] || {};
  const node = new LiteGraph.LGraphNode(nodeDef.title || nt.label || nodeDef.type);
  node.id = nodeDef.id;
  const rawPos = nodeDef.pos;
  node.pos = (Array.isArray(rawPos) && rawPos.length >= 2) ? rawPos : [100, 100];
  node._wfType = nodeDef.type;
  node._status = 'running';
  node.color = '#58a6ff';
  (nt.inputs||[]).forEach((p, i) => node.addInput(p.label || p.name, p.type || '*'));
  (nt.outputs||[]).forEach((p, i) => node.addOutput(p.label || p.name, p.type || '*'));
  node.size = [220, Math.max(100, 60 + Math.max(nt.inputs?.length||0, nt.outputs?.length||0) * 14)];
  wfRunnerGraph.add(node);
  // Redraw
  try { wfRunnerCanvas.setDirty(true, true); wfRunnerCanvas.draw(true, true); } catch(_) {}
}

function updateRunnerNode(nodeId, updates) {
  if (!wfRunnerGraph) return;
  wfRunnerGraph._nodes.forEach(node => {
    if (String(node.id) === String(nodeId)) {
      const statusColors = { completed: '#3fb950', running: '#58a6ff', failed: '#f85149', cancelled: '#8b949e', queued: '#30363d' };
      if (updates.status) {
        node.color = statusColors[updates.status] || node.color;
        node._status = updates.status;
      }
      Object.entries(updates).forEach(([k, v]) => {
        if (k === 'color') node.color = v;
      });
    }
  });
  try { wfRunnerCanvas.setDirty(true, true); wfRunnerCanvas.draw(true, true); } catch(_) {}
}

// ── Exports for onclick handlers ──
export function _downloadOutputs(instId) {
  window.open(`/api/workflows/instances/${instId}/download`, '_blank');
}

export async function _replayFrom(instId, nodeId) {
  try {
    const result = await api('POST', `/workflows/instances/${instId}/replay`, { from_node: nodeId });
    toast(t('wf.runner.replaying'), 'success');
    location.hash = '#/workflow/instance/' + instId;
  } catch (e) { toast(e.message, 'error'); }
}

// ── Cleanup ──
export function cleanupWfRunner() {
  if (wfSSE) { wfSSE.close(); wfSSE = null; }
  if (wfRunnerGraph) { wfRunnerGraph = null; }
  if (wfRunnerCanvas) { wfRunnerCanvas = null; }
}
