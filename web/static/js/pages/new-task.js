/* new-task.js — New task creation page (pipeline + file upload + workflow) */
import { api, fetchProviderStatuses, providerChoiceLabel } from '../api.js';
import { t, getLang } from '../i18n.js';
import { formatBytes, toast, escHtml, isTypeCompatible } from '../utils.js';

export default async function renderNewTask(main) {
  selectedWorkflowId = null;
  window._wfInputFile = null; window._wfInputFiles = {};
  let types = {};
  try {
    const data = await api('GET', '/pipeline-types');
    types = data.types;
  } catch (e) {
    main.innerHTML = `<h2>${t('new.title')}</h2><div class="error-box"><p>${t('dash.error')}: ${e.message}</p></div>`;
    return;
  }

  const isZh = getLang() === 'zh';
  const typeEntries = Object.entries(types);
  const rawCats = [...new Set(typeEntries.map(([,pt]) => pt.category || 'other'))];
  const catLabel = (c) => (t('filterCategory.' + c) || c);
  const categories = rawCats; // used in template below

  main.innerHTML = `
    <h2>${t('new.title')}</h2>
    <div class="help-tip">${t('new.help')}</div>

    ${buildText2ImgPanel(isZh)}

    <div class="nt-sections">
      <!-- Pipeline Tasks -->
      <div class="nt-section">
        <div class="nt-section-header">
          <h3>📋 ${t('new.pipelineTasks')}</h3>
          <span class="nt-section-badge" id="nt-type-count">${typeEntries.length}</span>
        </div>
        <div class="nt-toolbar">
          <input class="nt-search" id="nt-search" type="text" placeholder="${t('new.searchPlaceholder')}">
          <div class="nt-filter-pills" id="nt-filters">
            <button class="nt-pill active" data-cat="all">${t('new.filterAll')}</button>
            ${categories.map(c => `<button class="nt-pill" data-cat="${c}">${catLabel(c)}</button>`).join('')}
          </div>
        </div>
        <div class="type-grid" id="type-selector">
          ${typeEntries.map(([key, pt]) => `
            <div class="type-card" data-type="${key}" data-cat="${pt.category||'other'}" data-search="${(pt.label + ' ' + (pt.label_zh||'') + ' ' + key + ' ' + (pt.description||'')).toLowerCase()}">
              <h4>${isZh ? (pt.label_zh || pt.label) : pt.label}</h4>
              <p>${isZh ? (pt.description_zh || pt.description) : (pt.description || '')}</p>
              <span class="gpu-badge gpu-${pt.gpu?'yes':'no'}">${pt.gpu?'GPU':'CPU'}</span>
            </div>
          `).join('')}
        </div>
        <div class="nt-empty" id="nt-empty" style="display:none">${t('new.noMatch')}</div>
      </div>

      <!-- Workflows -->
      <div class="nt-section">
        <div class="nt-section-header">
          <h3>🔗 ${t('new.workflowsSection')}</h3>
          <span class="nt-section-badge" id="nt-wf-count">-</span>
        </div>
        <div class="nt-wf-grid" id="nt-wf-grid">${t('wf.loading')}</div>
      </div>
    </div>

    <!-- Task form (shown after selecting a pipeline type) -->
    <div id="task-params" style="display:none">
      <h4>${t('new.step2')}</h4>
      <div class="drop-zone" id="drop-zone">
        <div class="icon">&#128193;</div>
        <div class="text">${t('new.dropText')}</div>
        <div class="sub" id="accept-types"></div>
        <input type="file" id="file-input">
      </div>
      <div id="file-chosen" style="display:none;font-size:13px;color:var(--green);margin-bottom:16px"></div>

      <h4>${t('new.step3')}</h4>
      <div id="param-fields"></div>
      <div class="btn-group">
        <button class="btn btn-primary" id="submit-btn" disabled>${t('new.submit')}</button>
        <button class="btn" id="back-btn">${t('new.back')}</button>
      </div>
      <div id="submit-status" style="margin-top:8px;font-size:12px"></div>
    </div>

    <!-- Workflow run form (shown after selecting a workflow) -->
    <div id="workflow-form" style="display:none;margin-top:16px">
      <div class="nt-section-header">
        <h3 id="wf-form-title">${t('new.runWorkflow')}</h3>
        <button class="btn btn-sm" id="workflow-back-btn">← ${t('new.back')}</button>
      </div>
      <div id="workflow-inputs"></div>
      <div class="btn-group" style="margin-top:16px">
        <button class="btn btn-primary" id="workflow-submit-btn" disabled>▶ ${t('new.runWorkflow')}</button>
      </div>
      <div id="workflow-submit-status" style="margin-top:8px;font-size:12px"></div>
    </div>
  `;

  let selectedType = null;
  let selectedFile = null;

  // ── Type card selection ──
  main.querySelectorAll('#type-selector .type-card').forEach(card => {
    card.addEventListener('click', () => {
      const cardType = card.dataset.type;
      main.querySelectorAll('#type-selector .type-card').forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
      selectedType = cardType;
      const pt = types[selectedType];

      document.getElementById('workflow-form').style.display = 'none';
      document.getElementById('task-params').style.display = 'block';
      document.getElementById('accept-types').textContent = (pt.accepts||[]).join(', ');

      const fields = document.getElementById('param-fields');
      fields.innerHTML = (pt.params||[]).map(p => {
        const plabel = isZh ? (p.label_zh || p.label) : p.label;
        const pdesc = (isZh ? (p.description_zh || p.description || '') : (p.description || '')).replace(/"/g, '&quot;');
        const reqStar = p.required ? '<span class="required">*</span>' : '';
        const titleAttr = pdesc ? ` title="${pdesc}"` : '';
        if (p.type === 'bool') return `<div class="form-row"><label class="form-label"${titleAttr}>${plabel}${reqStar}</label><span class="form-value"><input type="checkbox" name="${p.name}" ${p.default ? 'checked' : ''}></span><div class="field-error"></div></div>`;
        if (p.type === 'choice') return `<div class="form-row"><label class="form-label"${titleAttr}>${plabel}${reqStar}</label><span class="form-value"><select name="${p.name}">${(p.choices||[]).map(c => `<option value="${c}" ${c===p.default?'selected':''}>${c.toUpperCase()}</option>`).join('')}</select></span><div class="field-error"></div></div>`;
        const min = p.min != null ? `min="${p.min}"` : '';
        const max = p.max != null ? `max="${p.max}"` : '';
        return `<div class="form-row"><label class="form-label"${titleAttr}>${plabel}${reqStar}</label><span class="form-value"><input type="${p.type==='int'?'number':p.type}" name="${p.name}" value="${p.default||''}" ${min} ${max} step="${p.type==='float'?'any':'1'}"></span><div class="field-error" id="err-${p.name}"></div></div>`;
      }).join('');
      // Wire real-time validation
      fields.querySelectorAll('input, select').forEach(el => {
        el.addEventListener('input', () => validateField(el));
        el.addEventListener('change', () => validateField(el));
      });
      updateSubmit();
      // Scroll to form
      document.getElementById('task-params').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });

  // ── Search & Filter ──
  const searchInput = document.getElementById('nt-search');
  const filterPills = document.getElementById('nt-filters');
  let activeFilter = 'all';

  function filterCards() {
    const query = searchInput.value.toLowerCase();
    let visible = 0;
    main.querySelectorAll('#type-selector .type-card').forEach(card => {
      const cat = card.dataset.cat;
      const searchText = card.dataset.search || '';
      const matchCat = activeFilter === 'all' || cat === activeFilter;
      const matchSearch = !query || searchText.includes(query);
      if (matchCat && matchSearch) { card.style.display = ''; visible++; }
      else { card.style.display = 'none'; }
    });
    document.getElementById('nt-empty').style.display = visible === 0 ? 'block' : 'none';
    document.getElementById('nt-type-count').textContent = visible;
  }

  searchInput.addEventListener('input', filterCards);
  filterPills.addEventListener('click', e => {
    if (!e.target.classList.contains('nt-pill')) return;
    filterPills.querySelectorAll('.nt-pill').forEach(p => p.classList.remove('active'));
    e.target.classList.add('active');
    activeFilter = e.target.dataset.cat;
    filterCards();
  });

  // ── File drop zone ──
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  dropZone.addEventListener('click', () => fileInput.click());
  dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
  dropZone.addEventListener('drop', e => { e.preventDefault(); dropZone.classList.remove('dragover'); handleFile(e.dataTransfer.files[0]); });
  fileInput.addEventListener('change', () => { if (fileInput.files.length) handleFile(fileInput.files[0]); });

  function handleFile(file) {
    selectedFile = file;
    document.getElementById('file-chosen').style.display = 'block';
    document.getElementById('file-chosen').textContent = `${t('new.fileSelected')}: ${file.name} (${formatBytes(file.size)})`;
    updateSubmit();
  }

  function updateSubmit() {
    document.getElementById('submit-btn').disabled = !(selectedType && selectedFile);
  }

  function validateField(el) {
    const group = el.closest('.form-row');
    if (!group) return true;
    const p = (types[selectedType]?.params||[]).find(p => p.name === el.name);
    const errEl = group.querySelector('.field-error');
    group.classList.remove('invalid');
    if (errEl) errEl.textContent = '';

    // Required check
    if (p && p.required && !el.value && el.type !== 'checkbox') {
      group.classList.add('invalid');
      if (errEl) errEl.textContent = (getLang()==='zh'?'此项为必填':'This field is required');
      return false;
    }
    // Number range
    if (el.type === 'number' && el.value) {
      const v = parseFloat(el.value);
      if (p && p.min != null && v < p.min) {
        group.classList.add('invalid');
        if (errEl) errEl.textContent = (getLang()==='zh'?`最小值为 ${p.min}`:`Minimum is ${p.min}`);
        return false;
      }
      if (p && p.max != null && v > p.max) {
        group.classList.add('invalid');
        if (errEl) errEl.textContent = (getLang()==='zh'?`最大值为 ${p.max}`:`Maximum is ${p.max}`);
        return false;
      }
    }
    return true;
  }

  function validateAll() {
    let ok = true;
    document.querySelectorAll('#param-fields input, #param-fields select').forEach(el => {
      if (!validateField(el)) ok = false;
    });
    return ok;
  }

  document.getElementById('back-btn').addEventListener('click', () => {
    document.getElementById('task-params').style.display = 'none';
    main.querySelectorAll('#type-selector .type-card').forEach(c => c.classList.remove('selected'));
    selectedType = null; selectedFile = null;
    document.querySelector('.nt-sections').scrollIntoView({ behavior: 'smooth' });
  });

  // ── Text-to-Image ──
  setupText2Img(isZh, handleFile);

  // ── Submit pipeline task ──
  document.getElementById('submit-btn').addEventListener('click', async () => {
    if (!validateAll()) { toast(getLang()==='zh'?'请修正表单错误':'Please fix form errors', 'error'); return; }
    const params = {};
    document.querySelectorAll('#param-fields input, #param-fields select').forEach(el => {
      if (el.type === 'checkbox') { if (el.checked) params[el.name] = true; }
      else if (el.type === 'number') params[el.name] = el.value.includes('.') ? parseFloat(el.value) : parseInt(el.value, 10);
      else params[el.name] = el.value;
    });

    const formData = new FormData();
    formData.append('pipeline_type', selectedType);
    formData.append('params', JSON.stringify(params));
    formData.append('file', selectedFile);

    const status = document.getElementById('submit-status');
    status.textContent = t('new.submitting'); status.style.color = 'var(--accent)';

    try {
      const task = await api('POST', '/tasks', formData);
      status.textContent = `${t('new.submitted')}: ${task.id}`;
      status.style.color = 'var(--green)';
      toast(t('toast.taskCreated'), 'success');
      setTimeout(() => { location.hash = '#/task/' + task.id; }, 600);
    } catch (e) {
      status.textContent = `${t('new.submitError')}: ${e.message}`;
      status.style.color = 'var(--red)';
      toast(e.message, 'error');
    }
  });

  // ── Workflow cards ──
  loadWorkflowCards(isZh);

  // ── Workflow form ──
  document.getElementById('workflow-back-btn').addEventListener('click', () => {
    document.getElementById('workflow-form').style.display = 'none';
    selectedWorkflowId = null; window._wfInputFile = null; window._wfInputFiles = {};
    document.querySelector('.nt-sections').scrollIntoView({ behavior: 'smooth' });
  });

  document.getElementById('workflow-submit-btn').addEventListener('click', async () => {
    if (!selectedWorkflowId) return;
    const inputsDict = {};
    document.querySelectorAll('[id^="wf-text-"]').forEach(el => {
      const nid = el.id.replace('wf-text-', '');
      const val = el.value.trim();
      if (val) inputsDict[nid] = { text: val };
    });

    const nodeParams = {};
    document.querySelectorAll('[id^="wf-param-"]').forEach(el => {
      const nid = String(el.dataset.node);
      const key = el.dataset.param;
      let val;
      if (el.type === 'checkbox') val = el.checked;
      else if (el.dataset.type === 'int') val = parseInt(el.value, 10) || 0;
      else if (el.dataset.type === 'float') val = parseFloat(el.value) || 0;
      else val = el.value;
      if (!nodeParams[nid]) nodeParams[nid] = {};
      nodeParams[nid][key] = val;
    });

    // Runtime edge overrides from dropdowns
    const nodeInputs = {};
    document.querySelectorAll('.rp-input-sel').forEach(sel => {
      if (!sel.value) return;
      const [srcId, srcSlot, srcPort] = sel.value.split(':');
      const tgtNodeId = String(sel.dataset.node);
      const tgtPort = sel.dataset.port;
      if (!nodeInputs[tgtNodeId]) nodeInputs[tgtNodeId] = {};
      nodeInputs[tgtNodeId][tgtPort] = { source_node: srcId, source_port: srcPort };
    });

    const formData = new FormData();
    // Support multiple file_input nodes
    const wfFiles = window._wfInputFiles || {};
    for (const [nid, file] of Object.entries(wfFiles)) {
      formData.append('file', file);
      if (!inputsDict[nid]) inputsDict[nid] = {};
      inputsDict[nid].file = file.name;
    }
    // Backward compat: single file from non-workflow flow
    if (window._wfInputFile && Object.keys(wfFiles).length === 0) {
      formData.append('file', window._wfInputFile);
    }
    formData.append('inputs', JSON.stringify(inputsDict));
    formData.append('node_params', JSON.stringify(nodeParams));
    formData.append('node_inputs', JSON.stringify(nodeInputs));

    const status = document.getElementById('workflow-submit-status');
    status.textContent = t('wf.running'); status.style.color = 'var(--accent)';
    document.getElementById('workflow-submit-btn').disabled = true;

    try {
      const inst = await api('POST', `/workflows/${selectedWorkflowId}/run`, formData);
      status.textContent = t('wf.runStarted') + ': ' + inst.id;
      status.style.color = 'var(--green)';
      toast(t('wf.runStarted'), 'success');
      setTimeout(() => { location.hash = '#/workflow/instance/' + inst.id; }, 600);
    } catch (e) {
      status.textContent = t('new.submitError') + ': ' + e.message;
      status.style.color = 'var(--red)';
      document.getElementById('workflow-submit-btn').disabled = false;
      toast(e.message, 'error');
    }
  });
}

// ── Workflow state ──
let selectedWorkflowId = null;
window._wfInputFile = null; window._wfInputFiles = {};

async function loadWorkflowCards(isZh) {
  const grid = document.getElementById('nt-wf-grid');
  const countEl = document.getElementById('nt-wf-count');
  try {
    const data = await api('GET', '/workflows');
    const wfs = data.workflows || [];
    countEl.textContent = wfs.length;

    if (wfs.length === 0) {
      grid.innerHTML = `<div class="nt-empty">${t('new.noWorkflows')}</div>`;
      return;
    }

    grid.innerHTML = wfs.map(wf => {
      const graph = wf.graph || {};
      const nodeCount = (graph.nodes || []).length;
      const desc = wf.description || '';
      return `<div class="nt-wf-card" data-wf-id="${wf.id}">
        <div class="nt-wf-card-header">
          <span class="nt-wf-icon">🔗</span>
          <span class="nt-wf-name">${escHtml(wf.name)}</span>
        </div>
        <div class="nt-wf-meta">
          <span>📊 ${nodeCount} ${t('new.nodesCount')}</span>
          ${desc ? `<span class="nt-wf-desc">${escHtml(desc)}</span>` : ''}
        </div>
        <div class="nt-wf-arrow">→</div>
      </div>`;
    }).join('');

    // Click handler
    grid.querySelectorAll('.nt-wf-card').forEach(card => {
      card.addEventListener('click', () => {
        const wfId = card.dataset.wfId;
        grid.querySelectorAll('.nt-wf-card').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        selectWorkflow(wfId, wfs.find(w => w.id === wfId), isZh);
      });
    });
  } catch (e) {
    grid.innerHTML = `<div class="nt-empty">${t('new.loadFailed')}: ${e.message}</div>`;
    countEl.textContent = '!';
  }
}

async function selectWorkflow(wfId, wfSummary, isZh) {
  selectedWorkflowId = wfId;
  window._wfInputFile = null; window._wfInputFiles = {};
  document.getElementById('task-params').style.display = 'none';
  document.getElementById('workflow-form').style.display = 'block';
  document.getElementById('wf-form-title').textContent = (wfSummary && wfSummary.name) || wfId;
  document.getElementById('workflow-submit-btn').disabled = true;
  document.getElementById('workflow-inputs').innerHTML = `<p style="color:var(--fg2);text-align:center;padding:20px">${t('wf.loading')}</p>`;
  document.getElementById('workflow-submit-status').textContent = '';

  try {
    const [inputsData, wfData, ntData] = await Promise.all([
      api('GET', `/workflows/${wfId}/inputs`),
      api('GET', `/workflows/${wfId}`),
      api('GET', '/node-types'),
    ]);
    await fetchProviderStatuses();
    const inputs = (inputsData.inputs || []).map(inp => ({ ...inp, node_type: (inp.node_type || '').replace(/^wf_/, '') }));
    const wfGraph = wfData.graph || {};
    const ntDefs = ntData.types || [];

    let html = '';

    if (inputs.length === 0) {
      html += `<p style="color:var(--fg2);font-size:13px">${t('new.noExternalInput')}</p>`;
      html += buildProcessNodeParamsHtml(wfGraph, ntDefs, isZh);
      document.getElementById('workflow-inputs').innerHTML = html;
      document.getElementById('workflow-submit-btn').disabled = false;
      document.getElementById('workflow-form').scrollIntoView({ behavior: 'smooth', block: 'start' });
      return;
    }

    html += inputs.map(inp => {
      if (inp.node_type === 'file_input') {
        const accept = (inp.params.accept || '.png,.jpg,.stl').split(',');
        return `<div class="form-group wf-file-input-group" style="margin-bottom:16px" data-node-id="${inp.node_id}">
          <label style="font-weight:600">${inp.label} <span style="color:var(--fg2);font-weight:400">(${inp.node_type})</span></label>
          <div class="drop-zone wf-drop-zone" style="margin-top:8px" data-node-id="${inp.node_id}">
            <div class="icon">&#128193;</div>
            <div class="text">${t('new.dropHint')}</div>
            <div class="sub">${accept.join(', ')}</div>
            <input type="file" class="wf-file-input" data-node-id="${inp.node_id}" accept="${accept.join(',')}">
          </div>
          <div class="wf-file-chosen" data-node-id="${inp.node_id}" style="display:none;font-size:13px;color:var(--green);margin-top:8px"></div></div>`;
      }
      if (inp.node_type === 'text_input') {
        return `<div class="form-group" style="margin-bottom:16px">
          <label style="font-weight:600">${inp.label} <span style="color:var(--fg2);font-weight:400">(${inp.node_type})</span></label>
          <textarea id="wf-text-${inp.node_id}" rows="3" style="width:100%;padding:8px 12px;border-radius:var(--radius);border:1px solid var(--border);background:var(--bg);color:var(--fg);font-size:13px;font-family:var(--font);resize:vertical;margin-top:8px" placeholder="${inp.params.placeholder || ''}"></textarea></div>`;
      }
      return '';
    }).join('');

    html += buildProcessNodeParamsHtml(wfGraph, ntDefs, isZh);
    document.getElementById('workflow-inputs').innerHTML = html;

    // Wire file drop zones (support multiple file_input nodes via classes)
    window._wfInputFiles = window._wfInputFiles || {};
    document.querySelectorAll('.wf-drop-zone').forEach(wfDrop => {
      const nid = wfDrop.dataset.nodeId;
      const wfFileInput = wfDrop.querySelector('.wf-file-input');
      if (!wfFileInput) return;
      wfDrop.addEventListener('click', () => wfFileInput.click());
      wfDrop.addEventListener('dragover', e => { e.preventDefault(); wfDrop.classList.add('dragover'); });
      wfDrop.addEventListener('dragleave', () => wfDrop.classList.remove('dragover'));
      wfDrop.addEventListener('drop', e => { e.preventDefault(); wfDrop.classList.remove('dragover'); if (e.dataTransfer.files.length) { window._wfInputFiles[nid] = e.dataTransfer.files[0]; updateWFSubmit(); } });
      wfFileInput.addEventListener('change', () => { if (wfFileInput.files.length) { window._wfInputFiles[nid] = wfFileInput.files[0]; updateWFSubmit(); } });
    });
    updateWFSubmit();
  } catch (e) {
    document.getElementById('workflow-inputs').innerHTML = `<p style="color:var(--red)">${t('new.loadFailed')}: ${e.message}</p>`;
  }

  document.getElementById('workflow-form').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function updateWFSubmit() {
  const submitBtn = document.getElementById('workflow-submit-btn');
  // Update each file_chosen indicator
  document.querySelectorAll('.wf-file-chosen').forEach(el => {
    const nid = el.dataset.nodeId;
    const file = window._wfInputFiles && window._wfInputFiles[nid];
    if (file) {
      el.style.display = 'block';
      el.textContent = t('new.fileChosen') + ': ' + file.name + ' (' + formatBytes(file.size) + ')';
    }
  });
  // Enable submit if ALL file_input groups have a file selected
  if (submitBtn) {
    const groups = document.querySelectorAll('.wf-file-input-group');
    const allReady = groups.length === 0 || Array.from(groups).every(g => {
      const nid = g.dataset.nodeId;
      return window._wfInputFiles && window._wfInputFiles[nid];
    });
    submitBtn.disabled = !allReady;
  }
}

function buildProcessNodeParamsHtml(wfGraph, ntDefs, isZh) {
  const ntMap = {}; ntDefs.forEach(nt => { ntMap[nt.id] = nt; });
  const nodeMap = {}; (wfGraph.nodes || []).forEach(n => { nodeMap[n.id] = n; });
  const portEdgeMap = {};
  // Normalize edges
  const rawEdges = wfGraph.links ? wfGraph.links.map(link => {
    if (Array.isArray(link) && link.length >= 5) {
      return { source: link[1], sourcePort: link[2], target: link[3], targetPort: link[4] };
    }
    return null;
  }).filter(Boolean) : (wfGraph.edges || []);
  rawEdges.forEach(e => {
    const srcNode = nodeMap[e.source];
    const srcNT = ntMap[(srcNode && srcNode.type || '').replace(/^wf_/, '')];
    const srcPort = (srcNT && srcNT.outputs && srcNT.outputs[e.sourcePort]) || { name: String(e.sourcePort) };
    const srcPortLabel = srcPort.name || String(e.sourcePort);
    portEdgeMap[e.target] = portEdgeMap[e.target] || {};
    portEdgeMap[e.target][e.targetPort] = { sourceNodeId: e.source, sourceLabel: srcNode ? (srcNode.title || (srcNT && srcNT.label) || srcNode.type) : '', portLabel: srcPortLabel };
    // Also index by port name for dropdown lookups
    if (srcPortLabel) {
      portEdgeMap[e.target][srcPortLabel] = portEdgeMap[e.target][e.targetPort];
    }
  });

  const processNodes = (wfGraph.nodes || []).filter(n => {
    const nt = ntMap[(n.type || '').replace(/^wf_/, '')];
    return nt && nt.category !== 'input' && nt.category !== 'output';
  });
  if (processNodes.length === 0) return '';

  let html = `<h4 style="margin-top:20px">${t('new.nodeParamsOverride')}</h4>`;
  processNodes.forEach(n => {
    const typeId = (n.type || '').replace(/^wf_/, '');
    const nt = ntMap[typeId];
    const props = n.properties || {};
    const label = n.title || (nt ? (nt.label_zh && nt.label_zh !== nt.label ? nt.label_zh + ' ' + nt.label : nt.label) : typeId);
    const colorDot = nt && nt.color ? `<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${nt.color};flex-shrink:0;vertical-align:middle"></span>` : '';

    html += `<div style="background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:10px 14px;margin-bottom:10px">`;
    html += `<div style="font-weight:700;font-size:12px;color:var(--fg);margin-bottom:6px;display:flex;align-items:center;gap:6px">`;
    html += `<span style="display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;background:var(--accent);color:#000;font-size:10px;font-weight:700">#${n.id}</span>`;
    html += `${colorDot}${label} <span style="font-weight:400;font-size:10px;color:var(--fg2)">(${typeId})</span></div>`;

    // Port connectivity — dropdown-based input selection
    const portEntries = (nt && nt.inputs) || [];
    if (portEntries.length > 0) {
      html += `<div style="margin-bottom:8px;font-size:11px">`;
      portEntries.forEach((p, pi) => {
        const portLabel = (p.label_zh && p.label_zh !== p.label) ? (p.label_zh + ' ' + (p.label || p.name)) : (p.label || p.name);
        const portType = p.type || '*';
        html += `<div style="margin-bottom:4px"><label style="display:block;font-size:10px;font-weight:600;color:var(--fg);margin-bottom:2px">${portLabel} <span style="font-weight:400;color:var(--fg2)">[${portType}]</span></label>`;
        html += `<select class="rp-input-sel" data-node="${n.id}" data-slot="${pi}" data-port="${escHtml(p.name)}" style="width:100%;padding:5px 8px;border-radius:4px;border:1px solid var(--border);background:var(--bg);color:var(--fg);font-size:11px;font-family:var(--font)">`;
        html += `<option value="">${t('inspector.notConnected')}</option>`;
        (wfGraph.nodes || []).forEach(other => {
          if (String(other.id) === String(n.id)) return;
          const otherTypeId = (other.type || '').replace(/^wf_/, '');
          const otherNT = ntMap[otherTypeId];
          if (!otherNT) return;
          (otherNT.outputs || []).forEach((op, opIdx) => {
            if (!op.type) return;
            if (isTypeCompatible(op.type, portType)) {
              const srcLabel = other.title || (otherNT ? (otherNT.label_zh && otherNT.label_zh !== otherNT.label ? otherNT.label_zh + ' ' + otherNT.label : otherNT.label) : '') || String(other.id);
              const srcPortLabel = (op.label_zh && op.label_zh !== op.label ? op.label_zh + ' ' : '') + (op.label || op.name);
              const optVal = `${other.id}:${opIdx}:${escHtml(op.name)}`;
              const edgeInfo = portEdgeMap[n.id] || {};
              const curSrc = edgeInfo[pi] || edgeInfo[p.name];
              let sel = '';
              if (curSrc && String(curSrc.sourceNodeId) === String(other.id) && String(curSrc.portLabel) === String(op.name)) {
                sel = ' selected';
              }
              html += `<option value="${optVal}"${sel}>#${other.id} ${srcLabel} → ${srcPortLabel} [${op.type}]</option>`;
            }
          });
        });
        html += `</select></div>`;
      });
      html += `</div>`;
    }

    Object.entries(nt && nt.params || {}).forEach(([key, spec]) => {
      const val = props[key] !== undefined ? props[key] : (spec.default !== undefined ? spec.default : '');
      const fieldId = `wf-param-${n.id}-${key}`;
      const paramLabel = isZh ? (spec.label_zh || spec.label || key) : (spec.label || key);
      const paramDesc = (isZh ? (spec.desc_zh || spec.desc || '') : (spec.desc || '')).replace(/"/g, '&quot;');
      const titleAttr = paramDesc ? ` title="${paramDesc}"` : '';
      html += `<div class="form-row"><label class="form-label"${titleAttr}>${paramLabel}</label><span class="form-value">`;
      if (spec.type === 'bool') html += `<input type="checkbox" id="${fieldId}" data-node="${n.id}" data-param="${key}" data-type="bool" ${val ? 'checked' : ''}>`;
      else if (spec.type === 'choice') {
        html += `<select id="${fieldId}" data-node="${n.id}" data-param="${key}" data-type="choice">${(spec.choices||[]).map(c => { const display = key==='provider'?providerChoiceLabel(c):c; return `<option value="${c}" ${String(c)===String(val)?'selected':''}>${display}</option>`; }).join('')}</select>`;
      } else if (spec.type === 'int') html += `<input type="number" id="${fieldId}" data-node="${n.id}" data-param="${key}" data-type="int" value="${val}" min="${spec.min!=null?spec.min:-99999}" max="${spec.max!=null?spec.max:99999}" step="1">`;
      else if (spec.type === 'float') html += `<input type="number" id="${fieldId}" data-node="${n.id}" data-param="${key}" data-type="float" value="${val}" min="${spec.min!=null?spec.min:-99999}" max="${spec.max!=null?spec.max:99999}" step="any">`;
      else html += `<input type="text" id="${fieldId}" data-node="${n.id}" data-param="${key}" data-type="text" value="${String(val||'')}">`;
      html += `</span></div>`;
    });
    html += `</div>`;
  });
  return html;
}

// ── Text-to-Image panel ──
function buildText2ImgPanel(isZh) {
  return `<div class="nt-text2img-panel" id="text2img-panel">
    <div style="display:flex;align-items:center;justify-content:space-between;cursor:pointer" id="text2img-toggle">
      <span style="font-weight:600;font-size:13px">🎨 ${t('text2img.title')}</span>
      <span style="font-size:11px;color:var(--fg2)" id="text2img-chevron">▶</span>
    </div>
    <div id="text2img-body" style="display:none;margin-top:12px">
      <div class="form-group">
        <label>${t('text2img.prompt')}</label>
        <textarea id="text2img-prompt" rows="2" style="width:100%;padding:8px 12px;border-radius:var(--radius);border:1px solid var(--border);background:var(--bg);color:var(--fg);font-size:13px;font-family:var(--font);resize:vertical" placeholder="${t('text2img.promptHint')}"></textarea>
      </div>
      <div style="display:flex;gap:12px">
        <div class="form-group" style="flex:1">
          <label>${t('text2img.provider')}</label>
          <select id="text2img-provider" style="width:100%;padding:8px 12px;border-radius:var(--radius);border:1px solid var(--border);background:var(--bg);color:var(--fg);font-size:13px;font-family:var(--font)">
            <option value="openai">OpenAI DALL-E 3</option>
            <option value="stability">Stability AI</option>
          </select>
        </div>
        <div class="form-group" style="flex:1">
          <label>${t('text2img.size')}</label>
          <select id="text2img-size" style="width:100%;padding:8px 12px;border-radius:var(--radius);border:1px solid var(--border);background:var(--bg);color:var(--fg);font-size:13px;font-family:var(--font)">
            <option value="1024x1024">1024×1024</option>
            <option value="1792x1024">1792×1024</option>
            <option value="1024x1792">1024×1792</option>
          </select>
        </div>
      </div>
      <button class="btn btn-primary btn-sm" id="text2img-generate">${t('text2img.generate')}</button>
      <span id="text2img-status" style="font-size:12px;color:var(--accent);margin-left:8px;display:none"></span>
      <div id="text2img-result" style="margin-top:8px"></div>
    </div>
  </div>`;
}

function setupText2Img(isZh, handleFile) {
  let t2iOpen = false;
  document.getElementById('text2img-toggle').addEventListener('click', () => {
    t2iOpen = !t2iOpen;
    document.getElementById('text2img-body').style.display = t2iOpen ? 'block' : 'none';
    document.getElementById('text2img-chevron').textContent = t2iOpen ? '▼' : '▶';
  });

  document.getElementById('text2img-generate').addEventListener('click', async () => {
    const prompt = document.getElementById('text2img-prompt').value.trim();
    if (!prompt) { toast('Please enter a prompt', 'error'); return; }
    const provider = document.getElementById('text2img-provider').value;
    const size = document.getElementById('text2img-size').value;
    const statusEl = document.getElementById('text2img-status');
    const btn = document.getElementById('text2img-generate');
    btn.disabled = true; statusEl.style.display = 'inline';
    statusEl.textContent = t('text2img.generating'); statusEl.style.color = 'var(--accent)';

    try {
      const result = await api('POST', '/text2img', { prompt, provider, size });
      statusEl.textContent = t('text2img.done'); statusEl.style.color = 'var(--green)';
      // Build correct relative URL (preserves output/ prefix for file server)
      const t2iParts = result.image_path.replace(/\\/g, '/').split('/');
      const t2iIdx = t2iParts.indexOf('output');
      const t2iRelUrl = t2iIdx >= 0 ? t2iParts.slice(t2iIdx).join('/') : t2iParts.slice(-2).join('/');
      document.getElementById('text2img-result').innerHTML = `
        <div style="display:flex;align-items:center;gap:12px;padding:8px;background:var(--bg);border-radius:var(--radius-sm);margin-top:8px">
          <img src="/api/files/${t2iRelUrl}" style="max-height:80px;border-radius:var(--radius-sm)" onerror="this.style.display='none'">
          <div>
            <div style="font-size:12px;font-weight:600;color:var(--green)">✅ ${t('text2img.done')}</div>
            <div style="font-size:11px;color:var(--fg2);margin-top:2px">${result.width}×${result.height} — ${result.provider}</div>
            <button class="btn btn-sm" style="margin-top:4px" id="t2i-use-btn">📎 ${t('text2img.useAsInput')}</button>
          </div></div>`;

      document.getElementById('t2i-use-btn').addEventListener('click', async () => {
        try {
          const relUrl = '/api/files/' + t2iRelUrl;
          const resp = await fetch(relUrl);
          if (!resp.ok) throw new Error('HTTP ' + resp.status);
          const blob = await resp.blob();
          const fname = result.image_path.replace(/\\/g, '/').split('/').pop() || 'generated.png';
          handleFile(new File([blob], fname, { type: blob.type || 'image/png' }));
          document.getElementById('text2img-body').style.display = 'none';
          document.getElementById('text2img-chevron').textContent = '▶';
          t2iOpen = false;
          toast(t('new.fileSelected') + ': ' + fname, 'success');
        } catch (e) {
          toast(t('text2img.error') + ': ' + e.message, 'error');
        }
      });
    } catch (e) {
      statusEl.textContent = t('text2img.error') + ': ' + e.message;
      statusEl.style.color = 'var(--red)';
    }
    btn.disabled = false;
  });
}
