/* task-detail.js — Task detail page (standalone + workflow sub-tasks) */
import { api, apiStream } from '../api.js';
import { t } from '../i18n.js';
import { escHtml, formatTime, formatBytes, cacheFile, showFileModal, showCtxMenu, getFile, toast } from '../utils.js';
import { setActiveSSE } from '../router.js';
import { renderNodeDetailPanel } from '../components/node-detail.js';

export default async function renderTaskDetail(main, hash) {
  const taskId = hash.startsWith('#/task/') ? hash.slice(7) : hash;
  main.innerHTML = `<h2>${t('detail.title')}</h2><div id="detail-content">${t('detail.loading')}</div>`;

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

  function render() {
    const ofiles = task.output_files || [];
    const statusLabel = badgeLabels[task.status] || task.status;

    // ── Workflow sub-task ──
    if (wfCtx) {
      const backHref = wfCtx.instance_id ? `#/workflow/instance/${wfCtx.instance_id}` : '#/dashboard';
      const nodeLabel = wfCtx.node_label || wfCtx.node_type || wfCtx.node_id || '';

      // Build separated inputs / outputs / params for node detail panel
      const inputs = {};
      if (task.input_file) inputs['input'] = task.input_file;

      const outputs = {};
      ofiles.forEach(of => {
        const key = of.file_type || of.category || 'file';
        const fp = of.path || of.url || '';
        if (!outputs[key]) outputs[key] = fp;
      });
      if (task.result) {
        Object.entries(task.result).forEach(([k, v]) => {
          if (typeof v === 'string' && v.length < 500 && !outputs[k]) outputs[k] = v;
        });
      }

      const params = {};
      const mergedProps = { ...(task.params || {}), ...(wfCtx.params || {}) };
      Object.entries(mergedProps).forEach(([k, v]) => {
        params[k] = { value: v, source: wfCtx.params && k in wfCtx.params ? 'editor' : 'runtime' };
      });

      content.innerHTML = `
        <a href="${backHref}" class="wf-breadcrumb">← ${t('detail.backToWorkflow')}: ${escHtml(wfCtx.workflow_name || 'workflow')} / ${escHtml(nodeLabel)}</a>
        <div class="detail-header">
          <span class="badge badge-${task.status}">${statusLabel}</span>
          <span class="badge badge-workflow">🔄 ${t('dash.workflow')}</span>
          <span style="font-size:14px;font-weight:600;flex:1">${task.display_name || (task.pipeline_type + ' — ' + task.id)}</span>
        </div>
        ${renderNodeDetailPanel({
          nid: wfCtx.node_id || taskId,
          node: { type: wfCtx.node_type || task.pipeline_type, title: nodeLabel, properties: wfCtx.params || task.params || {} },
          nr: { status: task.status, task_id: taskId, error: task.result?.error, task, output_files: ofiles },
          nt: { label: wfCtx.node_type || task.pipeline_type },
          inputs, outputs, taskFiles: ofiles, params,
          showTaskLink: false,
        })}
        <div class="btn-group" style="margin-top:12px">
          ${task.status === 'running' ? `<button class="btn btn-danger" id="cancel-btn">${t('detail.cancel')}</button>` : ''}
          ${task.status === 'failed' || task.status === 'cancelled' ? `<button class="btn btn-primary" id="retry-btn">${t('detail.retry')}</button>` : ''}
          <button class="btn btn-danger btn-sm" id="delete-btn">${t('detail.delete')}</button>
        </div>
      `;
      bindTaskActions(taskId, task, render);
      return;
    }

    // ── Standalone task ──
    content.innerHTML = `
      <div class="help-tip">${t('detail.help')}</div>
      <div class="detail-header">
        <a href="#/dashboard" class="back-btn">←</a>
        <span class="badge badge-${task.status}">${statusLabel}</span>
        <span style="font-size:14px;font-weight:600;flex:1">${task.display_name || (task.pipeline_type + ' — ' + task.id)}</span>
      </div>

      <div class="stats" style="margin-bottom:16px">
        <div class="stat"><div class="num">${task.pipeline_type}</div><div class="label">${t('detail.pipeline')}</div></div>
        <div class="stat"><div class="num">${Object.keys(task.params||{}).length}</div><div class="label">${t('detail.params')}</div></div>
        <div class="stat"><div class="num">${ofiles.length}</div><div class="label">${t('detail.outputFiles')}</div></div>
        <div class="stat"><div class="num">${formatTime(task.created_at)}</div><div class="label">${t('detail.created')}</div></div>
      </div>

      ${(task.status === 'running' || task.status === 'queued') ? `
        <div class="progress-bar"><div class="fill" id="progress-fill" style="width:5%"></div></div>
        <div class="progress-text" id="progress-text">${t('detail.waiting')}</div>
        <div id="preview-zone"></div>
        <h4>${t('detail.logTitle')}</h4>
        <div class="log-viewer" id="log-container"></div>
      ` : ''}

      ${task.status === 'completed' ? buildCompletedResult(task, ofiles) : ''}
      ${task.status === 'failed' ? buildFailedResult(task) : ''}
      ${buildOutputFiles(ofiles)}
      <h4>${t('detail.paramsTitle')}</h4>
      <div class="log-viewer" style="max-height:120px">${JSON.stringify(task.params||{}, null, 2)}</div>
      ${task.result?.log ? `<h4>${t('detail.logTitle')}</h4><div class="log-viewer" style="max-height:200px">${(task.result.log||[]).map(l => `<div class="line">${l}</div>`).join('')}</div>` : ''}

      <div class="btn-group">
        ${task.status === 'running' ? `<button class="btn btn-danger" id="cancel-btn">${t('detail.cancel')}</button>` : ''}
        ${task.status === 'failed' || task.status === 'cancelled' ? `<button class="btn btn-primary" id="retry-btn">${t('detail.retry')}</button>` : ''}
        ${task.status === 'completed' ? `<button class="btn btn-primary btn-sm" id="send-wf-btn">🔗 ${t('detail.sendToWorkflow')}</button>` : ''}
        <button class="btn btn-danger btn-sm" id="delete-btn">${t('detail.delete')}</button>
      </div>
    `;

    bindTaskActions(taskId, task, render);
  }

  render();

  // SSE for live updates
  if (task.status === 'running' || task.status === 'queued') {
    setActiveSSE(apiStream(taskId, (evt, data) => {
      handleSSEEvent(evt, data, taskId, task, render);
    }));
  }
}

// ── Helpers ──

function buildCompletedResult(task, ofiles) {
  const r = task.result || {};
  let html = `<h4>${t('detail.result')}</h4><div class="detail-result-grid">`;
  if (r.decimated_vertices) html += `<div class="detail-result-item"><div class="val">${r.decimated_vertices.toLocaleString()}</div><div class="lbl">${t('detail.vertices')}</div></div>`;
  if (r.decimated_faces) html += `<div class="detail-result-item"><div class="val">${r.decimated_faces.toLocaleString()}</div><div class="lbl">${t('detail.faces')}</div></div>`;
  if (r.vertices && !r.decimated_vertices) html += `<div class="detail-result-item"><div class="val">${r.vertices.toLocaleString()}</div><div class="lbl">${t('detail.vertices')}</div></div>`;
  if (r.faces && !r.decimated_faces) html += `<div class="detail-result-item"><div class="val">${r.faces.toLocaleString()}</div><div class="lbl">${t('detail.faces')}</div></div>`;
  if (r.width_mm) html += `<div class="detail-result-item"><div class="val">${r.width_mm}×${r.height_mm}</div><div class="lbl">${t('detail.size')}</div></div>`;
  if (r.thickness_mm) html += `<div class="detail-result-item"><div class="val">${r.thickness_mm}</div><div class="lbl">${t('detail.thickness')}</div></div>`;
  html += `</div>`;
  if (r.bands) {
    html += `<h4>${t('detail.colorBands')}</h4><div style="margin-bottom:16px">`;
    r.bands.forEach(b => {
      const sw = b.color_rgb ? `rgb(${b.color_rgb.join(',')})` : b.color_hex;
      html += `<div style="display:flex;align-items:center;gap:8px;padding:4px 0;font-size:13px">
        <span style="display:inline-block;width:18px;height:18px;border-radius:3px;background:${sw};border:1px solid var(--border)"></span>
        <span style="color:var(--fg2);min-width:80px">Z ${b.z_start_mm} – ${b.z_end_mm} mm</span>
        <span style="color:var(--fg)">${b.color_hex}</span></div>`;
    });
    html += `</div>`;
  }
  return html;
}

function buildFailedResult(task) {
  return `<div style="background:var(--red-dim);border:1px solid var(--red);border-radius:var(--radius);padding:12px;margin-bottom:16px">
    <strong style="color:var(--red)">${t('detail.error')}</strong>
    <pre style="font-size:12px;margin-top:8px;white-space:pre-wrap;color:var(--fg2)">${task.result?.error || t('detail.unknownError')}</pre>
  </div>`;
}

function buildOutputFiles(ofiles) {
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
        const fileName = f.filename || f.path.split(/[\\/]/).pop();
        const fid = cacheFile(f);
        html += `<div class="preview-card file-card" data-fid="${fid}" onclick="import('../utils.js').then(m=>m.showFileModal('${fid}'))" oncontextmenu="import('../utils.js').then(m=>m.showCtxMenu(event,m.getFile('${fid}')))">
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
      nodes: [{ id: 1, type: 'output_file', title: task.pipeline_type + ' → ' + (stlFile ? stlFile.filename : task.id.slice(0,8)), pos: [50, 150] }],
      edges: [],
    };
    api('POST', '/workflows', { name: 'From: ' + defaultName, description: 'Auto-created from task ' + task.id, graph })
      .then(wf => { toast('Workflow created: ' + wf.name, 'success'); location.hash = '#/workflow/' + wf.id; })
      .catch(e => toast(e.message, 'error'));
  });

  const deleteBtn = document.getElementById('delete-btn');
  if (deleteBtn) deleteBtn.addEventListener('click', async () => {
    if (!confirm(t('detail.deleteConfirm'))) return;
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
    setTimeout(async () => { task = await api('GET', `/tasks/${taskId}`); render(); }, 500);
  }
  if (evt === 'error') {
    toast(data.error || t('toast.taskFailed'), 'error');
    setTimeout(async () => { task = await api('GET', `/tasks/${taskId}`); render(); }, 500);
  }
  if (evt === 'cancelled') {
    toast(t('toast.taskCancelled'), 'error');
    setTimeout(async () => { task = await api('GET', `/tasks/${taskId}`); render(); }, 500);
  }
}
