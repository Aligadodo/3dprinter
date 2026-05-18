/* task-detail.js — Task detail page (standalone + workflow sub-tasks) */
import { api, apiStream } from '../api.js';
import { t, getLang } from '../i18n.js';
import { escHtml, formatTime, formatBytes, cacheFile, showFileModal, showCtxMenu, getFile, toast, getBilingualLabel } from '../utils.js';
import { showConfirm } from '../components/confirm.js';
import { setActiveSSE } from '../router.js';
import { renderNodeDetailPanel } from '../components/node-detail.js';

let _renderGen = 0;

/** Compute ptLabel from pipeline type cache + task */
export function getPipelineTypeLabel(pipelineTypeCache, pipelineType, isZh) {
  return (pipelineTypeCache[pipelineType] &&
    (isZh ? pipelineTypeCache[pipelineType].label_zh : pipelineTypeCache[pipelineType].label)) || pipelineType;
}

/** Generate display label with type counter */
function getNodeDisplayLabel(node, nt, graphNodes) {
  if (node && node.title) return node.title;
  const base = nt ? getBilingualLabel(nt) : (node && node.type) || '';
  let count = 0, targetIdx = -1;
  (graphNodes || []).forEach((n, i) => {
    const tid = (n.type || '').replace(/^wf_/, '');
    const nodeTid = (node && node.type || '').replace(/^wf_/, '');
    if (tid === nodeTid) {
      count++;
      if (String(n.id) === String(node && node.id)) targetIdx = count;
    }
  });
  if (count <= 1) return base;
  return base + ' #' + (targetIdx > 0 ? targetIdx : 1);
}

export default async function renderTaskDetail(main, hash) {
  const taskId = hash.startsWith('#/task/') ? hash.slice(7) : hash;
  main.innerHTML = `<h2>${t('detail.title')}</h2><div id="detail-content">
    <div class="skeleton skeleton-text"></div>
    <div class="skeleton" style="height:120px;margin-bottom:12px"></div>
    <div class="skeleton" style="height:200px;margin-bottom:12px"></div>
  </div>`;

  let task;
  try {
    task = await api('GET', `/tasks/${taskId}`);
  } catch (e) {
    main.querySelector('#detail-content').innerHTML =
      `<div class="empty"><p>${t('detail.notFound')}: ${taskId}</p><p style="font-size:12px;margin-top:4px">${e.message}</p></div>`;
    return;
  }

  const content = document.getElementById('detail-content');
  const badgeLabels = {
    queued: t('badge.queued'), running: t('badge.running'),
    completed: t('badge.completed'), failed: t('badge.failed'), cancelled: t('badge.cancelled')
  };

  // Fetch workflow context if this is a workflow sub-task
  let wfCtx = null;
  if (task.is_workflow_task) {
    try { wfCtx = await api('GET', `/tasks/${taskId}/workflow`); }
    catch (_) {}
  }

  async function render() {
    const ofiles = task.output_files || [];
    const statusLabel = badgeLabels[task.status] || task.status;

    // Fetch pipeline types for bilingual labels
    let pipelineTypeCache = {};
    try {
      const ptData = await api('GET', '/pipeline-types');
      pipelineTypeCache = ptData.types || {};
    } catch (_) {}
    const isZh = getLang() === 'zh';

    // ── Workflow sub-task: per-node breakdown ──
    if (wfCtx) {
      // Fetch full instance + node types for per-node context
      let inst = null, nodeTypes = null;
      try {
        [inst, nodeTypes] = await Promise.all([
          api('GET', `/workflows/instances/${wfCtx.instance_id}`),
          api('GET', '/node-types'),
        ]);
      } catch (_) {}

      const ntMap = {};
      if (nodeTypes && nodeTypes.types) {
        nodeTypes.types.forEach(nt => { ntMap[nt.id] = nt; });
      }

      const nrMap = {};
      if (inst && inst.node_runs) {
        inst.node_runs.forEach(nr => { nrMap[String(nr.node_id)] = nr; });
      }

      // Build graph node lookup + upstream edges
      const graphData = (inst && inst.workflow_graph) || {};
      const graphNodes = graphData.nodes || [];
      const rawEdges = graphData.links
        ? graphData.links.map(link => {
            if (Array.isArray(link) && link.length >= 5) {
              return { source: String(link[1]), sourcePort: link[2], target: String(link[3]), targetPort: link[4] };
            }
            return null;
          }).filter(Boolean)
        : (graphData.edges || []);

      const graphNodeMap = {};
      graphNodes.forEach(n => { graphNodeMap[String(n.id)] = n; });

      const upstreamEdges = {};
      rawEdges.forEach(e => {
        const tgtId = String(e.target);
        if (!upstreamEdges[tgtId]) upstreamEdges[tgtId] = [];
        upstreamEdges[tgtId].push({ sourceId: String(e.source), sourcePort: e.sourcePort, targetPort: e.targetPort });
      });

      const backHref = wfCtx.instance_id ? `#/workflow/instance/${wfCtx.instance_id}` : '#/dashboard';
      const currentNodeId = String(wfCtx.node_id || '');
      const ptLabel = getPipelineTypeLabel(pipelineTypeCache, task.pipeline_type, isZh);

      let html = `<a href="${backHref}" class="wf-breadcrumb">← ${t('detail.backToWorkflow')}: ${escHtml(wfCtx.workflow_name || 'workflow')}</a>
        <div class="detail-header">
          <span class="badge badge-${task.status}">${statusLabel}</span>
          <span class="badge badge-workflow">🔄 ${t('dash.workflow')}</span>
          <span style="font-size:14px;font-weight:600;flex:1">${task.display_name || (ptLabel + ' — ' + task.id)}</span>
        </div>`;

      // Workflow Context — per-node cards
      // (Task result/output-files are shown inside the "current node" card already)
      const nodeRuns = inst ? (inst.node_runs || []) : [];
      if (nodeRuns.length > 0) {
        html += `<div class="wf-ctx-section">
          <div class="wf-ctx-section-header">
            <h3>📊 ${t('detail.workflowContext')} <span style="font-weight:400;color:var(--fg2);font-size:12px">(${t('detail.allNodes').replace('{n}', nodeRuns.length)})</span></h3>
            <div class="wf-ctx-section-actions">
              <button class="btn btn-xs" onclick="this.closest('.wf-ctx-section').querySelectorAll('.wf-ctx-card-body').forEach(b=>b.style.display='block')">${t('detail.expandAll')}</button>
              <button class="btn btn-xs" onclick="this.closest('.wf-ctx-section').querySelectorAll('.wf-ctx-card-body').forEach(b=>b.style.display='none')">${t('detail.collapseAll')}</button>
            </div>
          </div>`;

        nodeRuns.forEach((nr, i) => {
          const nid = String(nr.node_id);
          const node = graphNodeMap[nid] || {};
          const nt = ntMap[(node.type || '').replace(/^wf_/, '')] || {};
          const isCurrentNode = nid === currentNodeId;
          const nodeLabel = getNodeDisplayLabel(node, nt, graphNodes);
          const statusEmoji = nr.status === 'completed' ? '✅' : nr.status === 'running' ? '⚡' : nr.status === 'failed' ? '❌' : '⏳';
          const nodeColor = (nt && nt.color) || '#888';

          // Per-node inputs from upstream edges (translate slot indices to port names)
          const inputs = {};
          const upstreamInfo = [];
          const edgesIn = upstreamEdges[nid] || [];
          edgesIn.forEach(e => {
            const srcNr = nrMap[e.sourceId];
            const srcNode = graphNodeMap[e.sourceId] || {};
            const srcTypeId = (srcNode.type || '').replace(/^wf_/, '');
            const srcNT = ntMap[srcTypeId] || {};
            // Translate numeric slot index → port name using node type def
            const srcPortName = (srcNT.outputs && srcNT.outputs[e.sourcePort]) ? srcNT.outputs[e.sourcePort].name : e.sourcePort;
            const srcPortLabel = (srcNT.outputs && srcNT.outputs[e.sourcePort])
              ? ((srcNT.outputs[e.sourcePort].label_zh && srcNT.outputs[e.sourcePort].label_zh !== srcNT.outputs[e.sourcePort].label)
                ? srcNT.outputs[e.sourcePort].label_zh + ' ' + srcNT.outputs[e.sourcePort].label
                : srcNT.outputs[e.sourcePort].label || srcPortName)
              : srcPortName;
            // Translate target slot index → port name
            const tgtPortName = (nt.inputs && nt.inputs[e.targetPort]) ? nt.inputs[e.targetPort].name : String(e.targetPort);
            const srcOutputs = (inst && inst.context && inst.context[String(e.sourceId)]) || {};
            const srcLabel = srcNode.title || (srcNT ? getBilingualLabel(srcNT) : '') || String(e.sourceId);
            const portVal = srcOutputs[srcPortName];
            if (portVal) {
              inputs[tgtPortName] = portVal;
              upstreamInfo.push({ targetPort: tgtPortName, sourceLabel: srcLabel, sourcePort: srcPortLabel, resolved: true });
            } else {
              upstreamInfo.push({ targetPort: tgtPortName, sourceLabel: srcLabel, sourcePort: srcPortLabel, resolved: false });
            }
          });

          // Per-node outputs (from context only; node_runs don't have an outputs column)
          const ctxOutputs = (inst && inst.context && inst.context[nid]) || {};
          const outputs = {};
          if (ctxOutputs && typeof ctxOutputs === 'object') {
            Object.entries(ctxOutputs).forEach(([k, v]) => {
              if (!k.startsWith('_') && typeof v === 'string') outputs[k] = v;
            });
          }

          // Per-node params from node properties
          const params = {};
          if (node.properties && typeof node.properties === 'object') {
            Object.entries(node.properties).forEach(([k, v]) => {
              params[k] = { value: v, source: 'editor' };
            });
          }

          html += `<div class="wf-ctx-card${isCurrentNode ? ' current' : ''}">
            <div class="wf-ctx-card-header" onclick="
              const body=this.nextElementSibling;
              const toggle=this.querySelector('.wf-ctx-toggle');
              if(body.style.display==='none'){body.style.display='block';toggle.textContent='▾'}
              else{body.style.display='none';toggle.textContent='▸'}
            ">
              <span class="wf-ctx-dot" style="background:${nodeColor}"></span>
              <span class="wf-ctx-node-index">#${i + 1}</span>
              <span class="wf-ctx-node-title">${statusEmoji} ${escHtml(nodeLabel)}</span>
              <span class="badge badge-${nr.status || 'queued'}" style="font-size:10px">${nr.status || 'queued'}</span>
              ${isCurrentNode ? `<span class="badge wf-ctx-current-badge">${t('detail.currentNode')}</span>` : ''}
              ${nr.task_id ? `<a href="#/task/${nr.task_id}" class="btn btn-xs wf-ctx-task-link" onclick="event.stopPropagation()">🔗 ${t('node.viewTask')}</a>` : ''}
              <span class="wf-ctx-toggle">${isCurrentNode ? '▾' : '▸'}</span>
            </div>
            <div class="wf-ctx-card-body" style="display:${isCurrentNode ? 'block' : 'none'}">
              ${renderNodeDetailPanel({ nid, node, nr, nt, inputs, outputs, upstreamEdges: upstreamInfo, taskFiles: nr.output_files || [], params, showTaskLink: false })}
            </div>
          </div>`;
        });

        html += `</div>`; // close wf-ctx-section
      }

      // Action buttons
      html += `<div class="btn-group" style="margin-top:12px">
        ${task.status === 'running' ? `<button class="btn btn-danger" id="cancel-btn">${t('detail.cancel')}</button>` : ''}
        ${task.status === 'failed' || task.status === 'cancelled' ? `<button class="btn btn-primary" id="retry-btn">${t('detail.retry')}</button>` : ''}
        <button class="btn btn-danger btn-sm" id="delete-btn">${t('detail.delete')}</button>
      </div>`;

      content.innerHTML = html;
      bindTaskActions(taskId, task, render);
      return;
    }

    // ── Standalone task (rendered as single-node "workflow") ──
    const ptLabel = getPipelineTypeLabel(pipelineTypeCache, task.pipeline_type, isZh);
    let html = `<div class="breadcrumb">
      <a href="#/dashboard">${t('nav.dashboard')}</a><span class="breadcrumb-sep">/</span>
      <span class="breadcrumb-current">${escHtml(task.display_name || (ptLabel + ' — ' + task.id))}</span>
    </div>
    <div class="help-tip">${t('detail.help')}</div>`;

    // Progress bar for running/queued
    if (task.status === 'running' || task.status === 'queued') {
      html += `<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">
        <div class="sse-indicator sse-connecting" id="sse-indicator"><span class="sse-dot"></span> Live</div>
      </div>
      <div class="progress-bar"><div class="fill" id="progress-fill" style="width:5%"></div></div>
        <div class="progress-text" id="progress-text">${t('detail.waiting')}</div>
        <div id="preview-zone"></div>`;
    }

    // Build node-detail-panel arguments from task data
    const displayNode = { title: task.display_name || ptLabel, type: task.pipeline_type, properties: {} };
    const displayNr = { status: task.status, task_id: task.id, error: task.result?.error || null, output_files: ofiles, task: task };
    const displayNt = { id: task.pipeline_type, label: ptLabel, color: '#58a6ff', inputs: [], outputs: [], params: {} };
    const displayInputs = task.input_file ? { file: task.input_file } : {};
    const displayParams = {};
    Object.entries(task.params || {}).forEach(([k, v]) => { displayParams[k] = { value: v, source: 'runtime' }; });

    // Extract output file paths from result (some pipelines don't populate output_files table)
    const displayOutputs = {};
    if (task.result && typeof task.result === 'object') {
      // Known file keys in pipeline results
      const fileKeys = ['output', 'stl', 'preview', 'result', 'mesh', 'views', 'height_preview', 'texture'];
      const nonFileKeys = new Set([
        'log', 'error', 'engine', 'format', 'vertices', 'faces', 'watertight',
        'decimated_vertices', 'decimated_faces', 'width_mm', 'height_mm',
        'thickness_mm', 'min_thickness_mm', 'max_thickness_mm', 'lithophane',
        'file_size', 'dimensions_mm', 'foreground_ratio', 'resolution'
      ]);
      Object.entries(task.result).forEach(([k, v]) => {
        if (typeof v === 'string' && v.length > 4 && !nonFileKeys.has(k)) {
          // Heuristic: string value that is a file path (has extension or path separator)
          if (/[\/\\]/.test(v) || /\.[a-z0-9]{2,4}$/i.test(v)) {
            displayOutputs[k] = v;
          }
        }
      });
      // Also check known file keys even if they don't match heuristic
      fileKeys.forEach(k => {
        if (task.result[k] && typeof task.result[k] === 'string' && !displayOutputs[k]) {
          displayOutputs[k] = task.result[k];
        }
      });
    }

    // Only pass non-input output_files to the outputs column
    const nonInputFiles = ofiles.filter(f => f.category !== 'input');

    html += renderNodeDetailPanel({
      nid: task.id, node: displayNode, nr: displayNr, nt: displayNt,
      inputs: displayInputs, outputs: displayOutputs, taskFiles: nonInputFiles, params: displayParams, showTaskLink: false,
    });

    // Render categorized output files section
    html += buildOutputFiles(nonInputFiles);

    // Log for running/queued
    if (task.status === 'running' || task.status === 'queued') {
      html += `<h4 style="margin-top:16px">${t('detail.logTitle')}</h4><div class="log-viewer" id="log-container"></div>`;
    }
    // Log for completed tasks
    if (task.result?.log) {
      html += `<h4 style="margin-top:16px">${t('detail.logTitle')}</h4><div class="log-viewer" style="max-height:200px">${(task.result.log||[]).map(l => `<div class="line">${l}</div>`).join('')}</div>`;
    }

    // Actions
    html += `<div class="btn-group" style="margin-top:16px">
      ${task.status === 'running' ? `<button class="btn btn-danger" id="cancel-btn">${t('detail.cancel')}</button>` : ''}
      ${task.status === 'failed' || task.status === 'cancelled' ? `<button class="btn btn-primary" id="retry-btn">${t('detail.retry')}</button>` : ''}
      ${task.status === 'completed' ? `<button class="btn btn-primary btn-sm" id="send-wf-btn">🔗 ${t('detail.sendToWorkflow')}</button>` : ''}
      <button class="btn btn-danger btn-sm" id="delete-btn">${t('detail.delete')}</button>
    </div>`;

    content.innerHTML = html;
    bindTaskActions(taskId, task, render);
  }

  await render();

  // SSE for live updates (all non-terminal states so 'complete' can trigger re-render)
  if (task.status !== 'failed' && task.status !== 'cancelled') {
    setActiveSSE(apiStream(taskId, (evt, data) => {
      handleSSEEvent(evt, data, taskId, task, render);
    }, (connState) => {
      const el = document.getElementById('sse-indicator');
      if (el) { el.className = 'sse-indicator sse-' + connState; }
    }));
  }
}

// ── Helpers ──

export function buildFailedResult(task) {
  return `<div style="background:var(--red-dim);border:1px solid var(--red);border-radius:var(--radius);padding:12px;margin-bottom:16px">
    <strong style="color:var(--red)">${t('detail.error')}</strong>
    <pre style="font-size:12px;margin-top:8px;white-space:pre-wrap;color:var(--fg2)">${task.result?.error || t('detail.unknownError')}</pre>
  </div>`;
}

export function buildOutputFiles(ofiles) {
  if (ofiles.length === 0) return '';
  const cats = {preview:[], result:[], input:[], intermediate:[], other:[]};
  ofiles.forEach(f => { cats[f.category||'result'] ? cats[f.category||'result'].push(f) : cats.other.push(f); });
  const catLabels = {preview: t('detail.catPreview'), result: t('detail.catResult'), input: t('detail.catInput'), intermediate: t('detail.catIntermediate'), other: t('detail.catOther')};
  return ['preview','result','intermediate','input','other']
    .filter(c => cats[c] && cats[c].length)
    .map(c => {
      let html = `<h4 style="font-size:12px;color:var(--fg2);margin:12px 0 6px">${catLabels[c]} (${cats[c].length})</h4><div class="preview-grid">`;
      cats[c].forEach(f => {
        const ext = (f.file_type||'').toLowerCase();
        const isImg = ['.png','.jpg','.jpeg','.webp','.bmp'].includes(ext);
        const fileUrl = f.url || '#';
        const fileName = f.filename || (f.path || '').split(/[\\/]/).pop();
        const fid = cacheFile(f);
        html += `<div class="preview-card file-card" data-fid="${fid}" onclick="import('/static/js/utils.js').then(m=>m.showFileModal('${fid}'))" oncontextmenu="import('/static/js/utils.js').then(m=>m.showCtxMenu(event,m.getFile('${fid}')))">
          ${isImg ? `<img src="${fileUrl}" alt="${fileName}" loading="lazy">` : `<div style="height:160px;display:flex;align-items:center;justify-content:center;font-size:32px;color:var(--fg2)">&#128736;</div>`}
          <div class="caption">${f.file_type} — ${fileName}</div></div>`;
      });
      html += `</div>`;
      return html;
    }).join('');
}

function bindTaskActions(taskId, task, renderFn) {
  const cancelBtn = document.getElementById('cancel-btn');
  if (cancelBtn) cancelBtn.addEventListener('click', async () => {
    try { await api('POST', `/tasks/${taskId}/cancel`); }
    catch (e) { toast(e.message, 'error'); return; }
    toast(t('toast.taskCancelled'), 'success');
    const updated = await api('GET', `/tasks/${taskId}`);
    Object.assign(task, updated);
    renderFn();
  });

  const retryBtn = document.getElementById('retry-btn');
  if (retryBtn) retryBtn.addEventListener('click', async () => {
    try {
      const newTask = await api('POST', `/tasks/${taskId}/retry`);
      location.hash = '#/task/' + newTask.id;
    } catch (e) { toast(e.message, 'error'); }
  });

  const sendWfBtn = document.getElementById('send-wf-btn');
  if (sendWfBtn) sendWfBtn.addEventListener('click', () => {
    const outputFiles = task.output_files || [];
    const stlFile = outputFiles.find(f => ['.stl', '.obj', '.glb'].includes(f.file_type || ''));
    const defaultName = task.display_name || task.pipeline_type;
    const graph = {
      nodes: [{ id: 1, type: 'wf_output_file', title: task.pipeline_type + ' → ' + (stlFile ? stlFile.filename : task.id.slice(0,8)), pos: [50, 150] }],
      edges: [],
    };
    api('POST', '/workflows', { name: 'From: ' + defaultName, description: 'Auto-created from task ' + task.id, graph })
      .then(wf => { toast('Workflow created: ' + wf.name, 'success'); location.hash = '#/workflow/' + wf.id; })
      .catch(e => toast(e.message, 'error'));
  });

  const deleteBtn = document.getElementById('delete-btn');
  if (deleteBtn) deleteBtn.addEventListener('click', async () => {
    if (!await showConfirm(t('detail.delete'), t('detail.deleteConfirm'), t('detail.delete'), t('detail.cancel'))) return;
    try { await api('DELETE', `/tasks/${taskId}`); }
    catch (e) { toast(e.message, 'error'); return; }
    toast(t('toast.taskDeleted'), 'success');
    location.hash = '#/dashboard';
  });
}

function handleSSEEvent(evt, data, taskId, task, render) {
  if (evt === 'log') {
    const lc = document.getElementById('log-container');
    if (lc) { const line = document.createElement('div'); line.textContent = data.line || data; lc.appendChild(line); lc.scrollTop = lc.scrollHeight; }
  }
  if (evt === 'status') {
    const el = document.getElementById('progress-text');
    if (el) el.textContent = data.message || data.status;
  }
  if (evt === 'progress') {
    const el = document.getElementById('progress-fill');
    if (el) el.style.width = (data.percent || 5) + '%';
    const pt = document.getElementById('progress-text');
    if (pt && data.message) pt.textContent = data.message;
  }
  if (evt === 'preview') {
    const pz = document.getElementById('preview-zone');
    if (pz && data.path) {
      const parts = data.path.replace(/\\/g, '/').split('/');
      const idx = parts.indexOf('output');
      const relUrl = idx >= 0 ? '/api/files/' + parts.slice(idx).join('/') : '/api/files/' + data.filename;
      pz.innerHTML = `<div class="preview-grid"><div class="preview-card"><img src="${relUrl}" alt="Preview" loading="lazy" style="max-height:240px"><div class="caption">${t('detail.preview')}</div></div></div>`;
    }
  }
  if (evt === 'complete') {
    toast(t('toast.taskCompleted'), 'success');
    const badge = document.querySelector('#detail-content .badge');
    if (badge) { badge.className = 'badge badge-completed'; badge.textContent = t('badge.completed'); }
    const fill = document.getElementById('progress-fill');
    if (fill) { fill.style.width = '100%'; fill.style.background = 'var(--green)'; }
    const pt = document.getElementById('progress-text');
    if (pt) pt.textContent = t('detail.completed');
    const ind = document.getElementById('sse-indicator');
    if (ind) ind.style.display = 'none';
    const gen = ++_renderGen;
    api('GET', `/tasks/${taskId}`).then(fresh => {
      if (gen !== _renderGen) return;
      Object.assign(task, fresh);
      render();
    });
  }
  if (evt === 'error') {
    toast(data.error || t('toast.taskFailed'), 'error');
    const badge = document.querySelector('#detail-content .badge');
    if (badge) { badge.className = 'badge badge-failed'; badge.textContent = t('badge.failed'); }
    const fill = document.getElementById('progress-fill');
    if (fill) { fill.style.width = '100%'; fill.style.background = 'var(--red)'; }
    const pt = document.getElementById('progress-text');
    if (pt) pt.textContent = data.error || t('detail.failedToast');
    const ind = document.getElementById('sse-indicator');
    if (ind) ind.style.display = 'none';
    const gen = ++_renderGen;
    api('GET', `/tasks/${taskId}`).then(fresh => {
      if (gen !== _renderGen) return;
      Object.assign(task, fresh);
      render();
    });
  }
  if (evt === 'cancelled') {
    toast(t('toast.taskCancelled'), 'error');
    const badge = document.querySelector('#detail-content .badge');
    if (badge) { badge.className = 'badge badge-cancelled'; badge.textContent = t('badge.cancelled'); }
    const ind = document.getElementById('sse-indicator');
    if (ind) ind.style.display = 'none';
    const gen = ++_renderGen;
    api('GET', `/tasks/${taskId}`).then(fresh => {
      if (gen !== _renderGen) return;
      Object.assign(task, fresh);
      render();
    });
  }
}
