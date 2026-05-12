/* node-detail.js — Shared node detail panel (used by task detail + wf runner)
 *
 * Layout:
 *   ┌──────────────────────────────────┐
 *   │ ● Node Name          status  ⏱  │
 *   │ ⚠ Error (if failed)             │
 *   ├──────────────┬───────────────────┤
 *   │ 📥 INPUTS    │ 📤 OUTPUTS        │
 *   │ (upstream)   │ (this node)       │
 *   ├──────────────┴───────────────────┤
 *   │ ⚙ PARAMETERS                    │
 *   ├──────────────────────────────────┤
 *   │ 📊 STATS (if completed)         │
 *   └──────────────────────────────────┘
 */

import { escHtml } from '../utils.js';
import { t } from '../i18n.js';

// ── URL construction ──
function fileToUrl(filePath) {
  if (!filePath) return '';
  if (filePath.startsWith('/api/') || filePath.startsWith('http')) return filePath;
  const n = filePath.replace(/\\/g, '/');
  const idx = n.indexOf('/output/');
  if (idx >= 0) return '/api/files/' + n.slice(idx + 1);
  // Try: find a task-id segment and build from there
  const parts = n.split('/').filter(Boolean);
  for (let i = 0; i < parts.length; i++) {
    if (/^[a-f0-9]{12,}$/.test(parts[i])) {
      return '/api/files/' + parts.slice(Math.max(0, i - 1)).join('/');
    }
  }
  // Last resort: filename only
  return '/api/files/' + parts[parts.length - 1];
}

function fileMeta(filePath) {
  if (!filePath || typeof filePath !== 'string') return { filename: '', ext: '', isImage: false, isMesh: false, url: '' };
  const filename = filePath.replace(/\\/g, '/').split('/').pop() || '';
  const ext = (filename.split('.').pop() || '').toLowerCase();
  const isImage = ['png','jpg','jpeg','gif','webp','bmp'].includes(ext);
  const isMesh = ['stl','obj','glb','gltf','3mf','ply'].includes(ext);
  const url = fileToUrl(filePath);
  return { filename, ext, isImage, isMesh, url };
}

// ── Main render ──
export function renderNodeDetailPanel({ nid, node, nr, nt, inputs, outputs, taskFiles, params, showTaskLink }) {
  const status = (nr && nr.status) || 'queued';
  const isCompleted = status === 'completed';
  const isFailed = status === 'failed';
  const isRunning = status === 'running';
  const nodeLabel = (node && (node.title || node.type)) || (nt && nt.label) || 'Node';
  const nodeColor = (nt && nt.color) || '#888';
  const errorMsg = (nr && nr.error) || null;

  const statusIcon = { completed: '✅', running: '⚡', failed: '❌', cancelled: '⏳', queued: '⏳' }[status] || '⏳';
  const statusColor = { completed: 'var(--green)', running: 'var(--accent)', failed: 'var(--red)', cancelled: 'var(--fg2)', queued: 'var(--fg2)' }[status] || 'var(--fg2)';

  // Normalize inputs: { portName: filePath } or { portName: {path, url, ...} }
  const inputMap = normalizePortMap(inputs);
  const outputMap = normalizePortMap(outputs);
  const taskFileList = taskFiles || (nr && nr.output_files) || [];

  // Dedup: remove task files already represented in outputs
  const outputUrls = new Set(Object.values(outputMap).map(f => (f && f.url) || ''));
  const filteredTaskFiles = taskFileList.filter(tf => {
    const meta = fileMeta(tf.path || tf.url || '');
    return !outputUrls.has(meta.url) && meta.url;
  });

  let html = '';

  // ── Header ──
  html += `<div class="nd-header">
    <span class="nd-dot" style="background:${nodeColor}"></span>
    <span class="nd-title">${escHtml(nodeLabel)}</span>
    <span class="nd-status" style="color:${statusColor}">${statusIcon} ${status}</span>
    ${showTaskLink && nr && nr.task_id ? `<a href="#/task/${nr.task_id}" class="nd-task-link">${t('node.viewTask')} →</a>` : ''}
  </div>`;

  // ── Error banner ──
  if (errorMsg) {
    html += `<div class="nd-error">⚠ ${escHtml(typeof errorMsg === 'string' ? errorMsg : JSON.stringify(errorMsg))}</div>`;
  }

  // ── Inputs | Outputs two-column ──
  html += `<div class="nd-io-grid">`;

  // Left: Inputs
  html += `<div class="nd-io-col nd-inputs"><div class="nd-section-title">📥 ${t('node.inputs')}</div>`;
  if (Object.keys(inputMap).length > 0) {
    Object.entries(inputMap).forEach(([portName, file]) => {
      html += renderPortEntry(portName, file);
    });
  } else {
    html += `<div class="nd-empty-hint">${t('node.noInputs')}</div>`;
  }
  html += `</div>`;

  // Right: Outputs
  html += `<div class="nd-io-col nd-outputs"><div class="nd-section-title">📤 ${t('node.outputs')}</div>`;
  const hasOutputs = Object.keys(outputMap).length > 0 || filteredTaskFiles.length > 0;
  if (hasOutputs) {
    Object.entries(outputMap).forEach(([portName, file]) => {
      html += renderPortEntry(portName, file);
    });
    filteredTaskFiles.forEach(tf => {
      const meta = fileMeta(tf.path || tf.url || '');
      html += renderPortEntry(tf.category || tf.file_type || 'file', meta);
    });
  } else {
    html += `<div class="nd-empty-hint">${t('node.noOutputs')}</div>`;
  }
  html += `</div>`;

  html += `</div>`; // close nd-io-grid

  // ── Parameters ──
  html += renderParams(params, node && node.properties, nt && nt.params);

  // ── Stats ──
  const result = (nr && nr.task && nr.task.result) || null;
  if (result && Object.keys(result).length > 0) {
    html += renderStats(result);
  }

  return `<div class="nd-panel">${html}</div>`;
}

// ── Port entry: thumbnail + filename + download ──
function renderPortEntry(portName, file) {
  if (!file) return '';
  const f = typeof file === 'string' ? fileMeta(file) : file;
  if (!f.url && !f.path) return '';

  let inner = '';

  if (f.isImage && f.url) {
    inner += `<img src="${f.url}" alt="${escHtml(f.filename)}" class="nd-thumb" loading="lazy"
      onclick="import('../utils.js').then(m=>m.showImageModal('${f.url.replace(/'/g, "\\\'")}'))"
      title="${escHtml(f.filename)}">`;
  } else if (f.isMesh) {
    inner += `<div class="nd-file-icon nd-icon-mesh">📦</div>`;
  } else {
    inner += `<div class="nd-file-icon nd-icon-file">📄</div>`;
  }

  inner += `<div class="nd-port-label">${escHtml(portName)}</div>`;
  inner += `<div class="nd-filename" title="${escHtml(f.filename)}">${escHtml(f.filename)}</div>`;

  if (f.url) {
    inner += `<div class="nd-actions">
      ${f.isImage ? `<button class="btn btn-xs" onclick="event.stopPropagation();import('../utils.js').then(m=>m.showImageModal('${f.url.replace(/'/g, "\\\'")}'))">🔍</button>` : ''}
      <a href="${f.url}" download class="btn btn-xs" onclick="event.stopPropagation()">⬇ ${t('node.download')}</a>
    </div>`;
  }

  return `<div class="nd-port-entry">${inner}</div>`;
}

// ── Parameters table ──
function renderParams(runtimeParams, nodeProps, typeParams) {
  // Merge: type params (specs + defaults) → node properties → runtime params
  const merged = {};
  if (typeParams && typeof typeParams === 'object') {
    Object.entries(typeParams).forEach(([key, spec]) => {
      const val = typeof spec === 'object' && spec !== null ? spec : { value: spec };
      merged[key] = { value: val.default !== undefined ? val.default : val.value, source: 'default', label: val.label || key, type: val.type };
    });
  }
  if (nodeProps && typeof nodeProps === 'object') {
    Object.entries(nodeProps).forEach(([key, val]) => {
      merged[key] = { ...(merged[key] || {}), value: val, source: 'editor' };
    });
  }
  if (runtimeParams && typeof runtimeParams === 'object') {
    Object.entries(runtimeParams).forEach(([key, val]) => {
      const v = typeof val === 'object' && val !== null ? val.value : val;
      const s = (typeof val === 'object' && val.source) ? val.source : 'runtime';
      merged[key] = { ...(merged[key] || {}), value: v, source: s };
    });
  }

  const entries = Object.entries(merged);
  if (entries.length === 0) {
    return `<div class="nd-params"><div class="nd-section-title">⚙ ${t('node.params')}</div><div class="nd-empty-hint">${t('node.noParams')}</div></div>`;
  }

  let html = `<div class="nd-params"><div class="nd-section-title">⚙ ${t('node.params')}</div>
    <table class="nd-param-table">
    <thead><tr><th>${t('detail.params')}</th><th>Value</th><th>Source</th></tr></thead><tbody>`;

  entries.forEach(([key, p]) => {
    let display = p.value;
    if (typeof display === 'boolean') display = display ? '✓ true' : '✗ false';
    if (display == null || display === '') display = '-';
    const srcLabel = { editor: 'editor', runtime: 'runtime', default: 'default' }[p.source] || p.source;
    const srcCls = 'nd-src-' + (p.source || 'default');
    html += `<tr>
      <td class="nd-param-key">${escHtml(p.label || key)}</td>
      <td class="nd-param-val">${escHtml(String(display))}</td>
      <td><span class="nd-src-tag ${srcCls}">${srcLabel}</span></td>
    </tr>`;
  });

  html += `</tbody></table></div>`;
  return html;
}

// ── Stats section ──
function renderStats(result) {
  const items = [];
  if (result.decimated_vertices) items.push(['Vertices', result.decimated_vertices.toLocaleString()]);
  else if (result.vertices) items.push(['Vertices', result.vertices.toLocaleString()]);
  if (result.decimated_faces) items.push(['Faces', result.decimated_faces.toLocaleString()]);
  else if (result.faces) items.push(['Faces', result.faces.toLocaleString()]);
  if (result.width_mm || result.height_mm) items.push(['Size (mm)', `${result.width_mm || '?'} × ${result.height_mm || '?'}`]);
  if (result.thickness_mm) items.push(['Thickness', `${result.thickness_mm} mm`]);
  if (result.file_size) items.push(['File Size', result.file_size]);

  if (items.length === 0) return '';

  return `<div class="nd-stats">
    <div class="nd-section-title">📊 ${t('node.stats')}</div>
    <div class="nd-stats-grid">
      ${items.map(([label, val]) => `<div class="nd-stat-item"><span class="nd-stat-val">${val}</span><span class="nd-stat-lbl">${label}</span></div>`).join('')}
    </div>
  </div>`;
}

// ── Normalize port map ──
function normalizePortMap(raw) {
  if (!raw || typeof raw !== 'object') return {};
  const map = {};
  Object.entries(raw).forEach(([port, val]) => {
    if (!val) return;
    if (typeof val === 'string') {
      map[port] = fileMeta(val);
    } else if (typeof val === 'object') {
      map[port] = {
        path: val.path || '',
        filename: val.filename || '',
        url: val.url || fileToUrl(val.path || ''),
        isImage: !!val.isImage,
        isMesh: !!val.isMesh,
        ext: val.ext || '',
      };
    }
  });
  return map;
}

// Legacy wrapper — kept for any external callers
export function buildNodeDetailHTML(nid, node, nrMap, ntMap, ctxOutputs) {
  const nr = nrMap[nid];
  const nt = ntMap[node.type] || {};
  return renderNodeDetailPanel({
    nid, node, nr, nt,
    inputs: ctxOutputs || {},
    outputs: nr && nr.outputs ? nr.outputs : {},
    taskFiles: nr && nr.output_files ? nr.output_files : [],
    params: node.properties || {},
    showTaskLink: true,
  });
}
