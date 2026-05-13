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

import { escHtml, cacheFile, getFile, showFileModal, showCtxMenu } from '../utils.js';
import { t } from '../i18n.js';

// ── URL construction ──
function fileToUrl(filePath) {
  if (!filePath) return '';
  if (filePath.startsWith('/api/') || filePath.startsWith('http') || filePath.startsWith('blob:')) return filePath;
  const n = filePath.replace(/\\/g, '/');
  // Find output/tasks or tasks segment — all pipeline/workflow files live under PROJECT_ROOT/...
  const markers = ['/output/tasks/', '/tasks/', '/output/'];
  for (const m of markers) {
    const idx = n.indexOf(m);
    if (idx >= 0) return '/api/files/' + n.slice(idx + 1);
  }
  // Fallback: last two segments
  const parts = n.split('/');
  if (parts.length > 1) return '/api/files/' + parts.slice(-2).join('/');
  return '/api/files/' + parts[0];
}

function fileMeta(filePath) {
  if (!filePath || typeof filePath !== 'string') return { filename: '', ext: '', isImage: false, isMesh: false, url: '', path: '', file_type: '' };
  // Detect plain text values (not file paths) — create a blob URL for download
  const looksLikePath = /[\/\\]/.test(filePath) || /^[A-Za-z]:/.test(filePath) || filePath.startsWith('/api/');
  if (!looksLikePath) {
    const blob = new Blob([filePath], {type: 'text/plain;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    return { filename: 'text.txt', ext: 'txt', isImage: false, isMesh: false, url, path: '', file_type: '.txt', isText: true };
  }
  const filename = filePath.replace(/\\/g, '/').split('/').pop() || '';
  const ext = (filename.split('.').pop() || '').toLowerCase();
  const file_type = ext ? '.' + ext : '';
  const isImage = ['png','jpg','jpeg','gif','webp','bmp'].includes(ext);
  const isMesh = ['stl','obj','glb','gltf','3mf','ply'].includes(ext);
  const url = fileToUrl(filePath);
  const path = filePath;
  return { filename, ext, isImage, isMesh, url, path, file_type };
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
  const enrichedTaskFiles = taskFileList.map(tf => {
    if (tf.url && tf.filename) return { ...fileMeta(tf.path || ''), url: tf.url, filename: tf.filename, path: tf.path || '' };
    return fileMeta(tf.path || tf.url || '');
  }).filter(meta => !outputUrls.has(meta.url) && meta.url);

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
  const hasOutputs = Object.keys(outputMap).length > 0 || enrichedTaskFiles.length > 0;
  if (hasOutputs) {
    Object.entries(outputMap).forEach(([portName, file]) => {
      html += renderPortEntry(portName, file);
    });
    enrichedTaskFiles.forEach(meta => {
      html += renderPortEntry(meta.file_type || 'file', meta);
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

// Escape a value for embedding in a JS string literal inside an HTML attribute.
// Must run AFTER escHtml — backslashes first, then quotes.
function escJS(v) {
  return v.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}
const UTILS = '/static/js/utils.js';

// ── Port entry: thumbnail + filename + file actions ──
function renderPortEntry(portName, file) {
  if (!file) return '';
  const f = typeof file === 'string' ? fileMeta(file) : file;
  if (!f.url && !f.path) return '';

  // Cache file for context menu and file modal
  const fileObj = {
    filename: f.filename || '',
    path: f.path || '',
    url: f.url || '',
    file_type: f.file_type || '',
    ext: f.ext || '',
    isImage: f.isImage,
    isMesh: f.isMesh,
    isText: f.isText,
  };
  const fid = cacheFile(fileObj);
  const fileUrl = escJS(f.url || '');
  const fileName = escJS(f.filename || '');
  const filePath = escJS(f.path || '');
  const isLocal = location.hostname === '127.0.0.1' || location.hostname === 'localhost' || location.hostname === '::1';

  let inner = '';

  if (f.isImage && f.url) {
    inner += `<img src="${f.url}" alt="${escHtml(f.filename)}" class="nd-thumb" loading="lazy"
      onclick="event.stopPropagation();import('${UTILS}').then(m=>m.showImageModal('${fileUrl}'))"
      title="${escHtml(f.filename)}">`;
  } else if (f.isText) {
    inner += `<div class="nd-file-icon nd-icon-file">📝</div>`;
  } else if (f.isMesh) {
    inner += `<div class="nd-file-icon nd-icon-mesh">📦</div>`;
  } else {
    inner += `<div class="nd-file-icon nd-icon-file">📄</div>`;
  }

  inner += `<div class="nd-port-label">${escHtml(portName)}</div>`;
  inner += `<div class="nd-filename" title="${escHtml(f.filename)}">${escHtml(f.filename)}</div>`;

  // Action buttons
  const toastCopied = escJS(t('ctx.copied'));
  inner += `<div class="nd-actions">
    <button class="btn btn-xs nd-act-btn" title="${escHtml(t('ctx.open'))}" onclick="event.stopPropagation();import('${UTILS}').then(m=>m.showFileModal('${fid}'))">📄</button>
    ${f.url ? `<a href="${f.url}" download="${escHtml(f.filename||'file')}" class="btn btn-xs nd-act-btn" onclick="event.stopPropagation()" title="${escHtml(t('ctx.download'))}">⬇</a>` : ''}
    ${filePath ? `<button class="btn btn-xs nd-act-btn" title="${escHtml(t('ctx.copyPath'))}" onclick="event.stopPropagation();navigator.clipboard.writeText('${filePath}').then(()=>import('${UTILS}').then(m=>m.toast('${toastCopied}','success')))">📋</button>` : ''}
    ${isLocal && filePath ? `<button class="btn btn-xs nd-act-btn" title="${escHtml(t('ctx.openFolder'))}" onclick="event.stopPropagation();fetch('/api/open-path',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:'${filePath}',action:'folder'})}).catch(e=>import('${UTILS}').then(m=>m.toast(e.message,'error')))">📂</button>` : ''}
  </div>`;

  return `<div class="nd-port-entry" data-fid="${fid}"
    onclick="import('${UTILS}').then(m=>m.showFileModal('${fid}'))"
    oncontextmenu="event.preventDefault();event.stopPropagation();import('${UTILS}').then(m=>m.showCtxMenu(event,m.getFile('${fid}')))">${inner}</div>`;
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
      const ext = val.ext || ((val.filename || '').split('.').pop() || '').toLowerCase();
      map[port] = {
        path: val.path || '',
        filename: val.filename || '',
        file_type: val.file_type || (ext ? '.' + ext : ''),
        url: val.url || fileToUrl(val.path || ''),
        isImage: !!val.isImage,
        isMesh: !!val.isMesh,
        ext: ext,
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
