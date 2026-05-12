/* new-task.js — New task creation page (pipeline + file upload + workflow) */
import { api, fetchProviderStatuses, providerChoiceLabel } from '../api.js';
import { t, getLang } from '../i18n.js';
import { formatBytes, toast } from '../utils.js';

export default async function renderNewTask(main) {
  let types = {};
  try {
    const data = await api('GET', '/pipeline-types');
    types = data.types;
  } catch (e) {
    main.innerHTML = `<h2>${t('new.title')}</h2><div class="error-box"><p>${t('dash.error')}: ${e.message}</p></div>`;
    return;
  }

  main.innerHTML = `
    <h2>${t('new.title')}</h2>
    <div class="help-tip">${t('new.help')}</div>
    <div id="text2img-panel" style="background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius);padding:14px 16px;margin-bottom:16px">
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
    </div>
    <div id="new-task-form">
      <h4>${t('new.step1')}</h4>
      <div class="type-grid" id="type-selector">
        ${Object.entries(types).map(([key, pt]) => `
          <div class="type-card" data-type="${key}">
            <h4>${t('type.' + key + '.label', pt.label)}</h4>
            <p>${t('type.' + key + '.desc', pt.description)}</p>
            <span class="gpu-badge gpu-${pt.gpu?'yes':'no'}">${pt.gpu?'GPU':'CPU'}</span>
          </div>
        `).join('')}
        <div class="type-card workflow-card" data-type="__workflow__" style="border-color:var(--accent)">
          <h4>🔗 ${t('new.workflowOption')}</h4>
          <p>${t('new.workflowOptionDesc')}</p>
          <span class="gpu-badge" style="background:var(--accent);color:#000">${t('new.multi')}</span>
        </div>
      </div>

      <div id="workflow-form" style="display:none;margin-top:16px">
        <h4>${t('new.selectWorkflow')}</h4>
        <select id="workflow-select" style="width:100%;padding:8px 12px;border-radius:var(--radius);border:1px solid var(--border);background:var(--bg);color:var(--fg);font-size:13px;font-family:var(--font);margin-bottom:16px">
          <option value="">-- ${t('new.selectWorkflowPlaceholder')} --</option>
        </select>
        <div id="workflow-inputs"></div>
        <div class="btn-group" style="margin-top:16px">
          <button class="btn btn-primary" id="workflow-submit-btn" disabled>▶ ${t('new.runWorkflow')}</button>
          <button class="btn" id="workflow-back-btn">${t('new.back')}</button>
        </div>
        <div id="workflow-submit-status" style="margin-top:8px;font-size:12px"></div>
      </div>

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
    </div>
  `;

  let selectedType = null;
  let selectedFile = null;

  // Type card selection
  main.querySelectorAll('.type-card').forEach(card => {
    card.addEventListener('click', () => {
      const cardType = card.dataset.type;
      if (cardType === '__workflow__') {
        main.querySelectorAll('.type-card').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        selectedType = null; selectedFile = null;
        document.getElementById('task-params').style.display = 'none';
        showWorkflowForm(main);
        return;
      }

      main.querySelectorAll('.type-card').forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
      selectedType = cardType;
      const pt = types[selectedType];

      document.getElementById('workflow-form').style.display = 'none';
      document.getElementById('task-params').style.display = 'block';
      document.getElementById('accept-types').textContent = (pt.accepts||[]).join(', ');

      const fields = document.getElementById('param-fields');
      const isZh = getLang() === 'zh';
      fields.innerHTML = (pt.params||[]).map(p => {
        const plabel = isZh ? (p.label_zh || p.label) : p.label;
        const pdesc = isZh ? (p.description_zh || p.description) : (p.description || '');
        if (p.type === 'bool') return `<div class="form-group"><label><input type="checkbox" name="${p.name}" ${p.default ? 'checked' : ''}> ${plabel}</label><div class="hint">${pdesc}</div></div>`;
        if (p.type === 'choice') return `<div class="form-group"><label>${plabel}</label><select name="${p.name}">${(p.choices||[]).map(c => `<option value="${c}" ${c===p.default?'selected':''}>${c.toUpperCase()}</option>`).join('')}</select><div class="hint">${pdesc}</div></div>`;
        return `<div class="form-group"><label>${plabel}</label><input type="${p.type==='int'?'number':p.type}" name="${p.name}" value="${p.default||''}" ${p.min!=null?`min="${p.min}"`:''} ${p.max!=null?`max="${p.max}"`:''} step="${p.type==='float'?'any':'1'}"><div class="hint">${pdesc}</div></div>`;
      }).join('');
      updateSubmit();
    });
  });

  // File drop zone
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

  document.getElementById('back-btn').addEventListener('click', () => {
    document.getElementById('task-params').style.display = 'none';
    main.querySelectorAll('.type-card').forEach(c => c.classList.remove('selected'));
    selectedType = null; selectedFile = null;
  });

  // Text-to-Image toggle
  let t2iOpen = false;
  document.getElementById('text2img-toggle').addEventListener('click', () => {
    t2iOpen = !t2iOpen;
    document.getElementById('text2img-body').style.display = t2iOpen ? 'block' : 'none';
    document.getElementById('text2img-chevron').textContent = t2iOpen ? '▼' : '▶';
  });

  // Text-to-Image generate
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
      document.getElementById('text2img-result').innerHTML = `
        <div style="display:flex;align-items:center;gap:12px;padding:8px;background:var(--bg);border-radius:var(--radius-sm);margin-top:8px">
          <img src="/api/files/${result.image_path.replace(/\\\\/g,'/').split('/').slice(-2).join('/')}" style="max-height:80px;border-radius:var(--radius-sm)" onerror="this.style.display='none'">
          <div>
            <div style="font-size:12px;font-weight:600;color:var(--green)">✅ ${t('text2img.done')}</div>
            <div style="font-size:11px;color:var(--fg2);margin-top:2px">${result.width}×${result.height} — ${result.provider}</div>
            <button class="btn btn-sm" style="margin-top:4px" id="t2i-use-btn">📎 ${t('text2img.useAsInput')}</button>
          </div></div>`;

      document.getElementById('t2i-use-btn').addEventListener('click', async () => {
        const parts = result.image_path.replace(/\\/g, '/').split('/');
        const idx = parts.indexOf('output');
        const relUrl = idx >= 0 ? '/api/files/' + parts.slice(idx).join('/') : '/api/files/' + parts.slice(-2).join('/');
        const resp = await fetch(relUrl);
        const blob = await resp.blob();
        const fname = result.image_path.replace(/\\/g, '/').split('/').pop() || 'generated.png';
        handleFile(new File([blob], fname, { type: blob.type || 'image/png' }));
        document.getElementById('text2img-body').style.display = 'none';
        document.getElementById('text2img-chevron').textContent = '▶';
        t2iOpen = false;
        toast(t('new.fileSelected') + ': ' + fname, 'success');
      });
    } catch (e) {
      statusEl.textContent = t('text2img.error') + ': ' + e.message;
      statusEl.style.color = 'var(--red)';
    }
    btn.disabled = false;
  });

  // Submit task
  document.getElementById('submit-btn').addEventListener('click', async () => {
    const params = {};
    document.querySelectorAll('#param-fields input, #param-fields select').forEach(el => {
      if (el.type === 'checkbox') { if (el.checked) params[el.name] = true; }
      else if (el.type === 'number') params[el.name] = el.value.includes('.') ? parseFloat(el.value) : parseInt(el.value);
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

  // Workflow form (nested within new-task)
  let selectedWorkflowId = null;
  let workflowInputFile = null;

  async function showWorkflowForm(main) {
    document.getElementById('task-params').style.display = 'none';
    const wfForm = document.getElementById('workflow-form');
    wfForm.style.display = 'block';
    selectedWorkflowId = null; workflowInputFile = null;
    document.getElementById('workflow-submit-btn').disabled = true;
    document.getElementById('workflow-inputs').innerHTML = '';
    document.getElementById('workflow-submit-status').textContent = '';

    const sel = document.getElementById('workflow-select');
    sel.innerHTML = '<option value="">-- ' + t('new.loadingWorkflows') + ' --</option>';
    try {
      const data = await api('GET', '/workflows');
      const wfs = data.workflows || [];
      sel.innerHTML = '<option value="">-- ' + t('new.selectWorkflowPlaceholder') + ' --</option>';
      wfs.forEach(wf => { sel.innerHTML += `<option value="${wf.id}">${wf.name}</option>`; });
    } catch (e) {
      sel.innerHTML = '<option value="">-- ' + t('new.loadWorkflowsFailed') + ' --</option>';
    }
  }

  document.getElementById('workflow-back-btn').addEventListener('click', () => {
    document.getElementById('workflow-form').style.display = 'none';
    main.querySelectorAll('.type-card').forEach(c => c.classList.remove('selected'));
    selectedWorkflowId = null; workflowInputFile = null;
  });

  document.getElementById('workflow-select').addEventListener('change', async function() {
    selectedWorkflowId = this.value; workflowInputFile = null;
    const inputsDiv = document.getElementById('workflow-inputs');
    const submitBtn = document.getElementById('workflow-submit-btn');
    submitBtn.disabled = true;
    if (!selectedWorkflowId) { inputsDiv.innerHTML = ''; return; }

    try {
      const [inputsData, wfData, ntData] = await Promise.all([
        api('GET', `/workflows/${selectedWorkflowId}/inputs`),
        api('GET', `/workflows/${selectedWorkflowId}`),
        api('GET', '/node-types'),
      ]);
      await fetchProviderStatuses();
      const inputs = (inputsData.inputs || []).map(inp => ({ ...inp, node_type: (inp.node_type || '').replace(/^wf_/, '') }));
      const wfGraph = wfData.graph || {};
      const ntDefs = ntData.types || [];

      const isZh = getLang() === 'zh';
      let html = '';

      if (inputs.length === 0) {
        html += '<p style="color:var(--fg2);font-size:13px">' + (isZh?'此工作流无需外部输入，可直接运行':'This workflow needs no external input') + '</p>';
        html += buildProcessNodeParamsHtml(wfGraph, ntDefs);
        inputsDiv.innerHTML = html;
        submitBtn.disabled = false;
        return;
      }

      html += inputs.map(inp => {
        if (inp.node_type === 'file_input') {
          const accept = (inp.params.accept || '.png,.jpg,.stl').split(',');
          return `<div class="form-group" style="margin-bottom:16px">
            <label style="font-weight:600">${inp.label} <span style="color:var(--fg2);font-weight:400">(${inp.node_type})</span></label>
            <div class="drop-zone" id="wf-drop-zone" style="margin-top:8px">
              <div class="icon">&#128193;</div>
              <div class="text">${isZh?'点击或拖拽上传文件':'Click or drag to upload file'}</div>
              <div class="sub">${accept.join(', ')}</div>
              <input type="file" id="wf-file-input" accept="${accept.join(',')}">
            </div>
            <div id="wf-file-chosen" style="display:none;font-size:13px;color:var(--green);margin-top:8px"></div></div>`;
        }
        if (inp.node_type === 'text_input') {
          return `<div class="form-group" style="margin-bottom:16px">
            <label style="font-weight:600">${inp.label} <span style="color:var(--fg2);font-weight:400">(${inp.node_type})</span></label>
            <textarea id="wf-text-${inp.node_id}" rows="3" style="width:100%;padding:8px 12px;border-radius:var(--radius);border:1px solid var(--border);background:var(--bg);color:var(--fg);font-size:13px;font-family:var(--font);resize:vertical;margin-top:8px" placeholder="${inp.params.placeholder || ''}"></textarea></div>`;
        }
        return '';
      }).join('');

      html += buildProcessNodeParamsHtml(wfGraph, ntDefs);
      inputsDiv.innerHTML = html;

      const wfDrop = document.getElementById('wf-drop-zone');
      const wfFileInput = document.getElementById('wf-file-input');
      if (wfDrop && wfFileInput) {
        wfDrop.addEventListener('click', () => wfFileInput.click());
        wfDrop.addEventListener('dragover', e => { e.preventDefault(); wfDrop.classList.add('dragover'); });
        wfDrop.addEventListener('dragleave', () => wfDrop.classList.remove('dragover'));
        wfDrop.addEventListener('drop', e => { e.preventDefault(); wfDrop.classList.remove('dragover'); if (e.dataTransfer.files.length) { window._wfInputFile = e.dataTransfer.files[0]; updateWFSubmit(); } });
        wfFileInput.addEventListener('change', () => { if (wfFileInput.files.length) { window._wfInputFile = wfFileInput.files[0]; updateWFSubmit(); } });
      }
      updateWFSubmit();
    } catch (e) {
      inputsDiv.innerHTML = '<p style="color:var(--red)">' + (getLang()==='zh'?'加载失败: ':'Load failed: ') + e.message + '</p>';
    }
  });

  // Workflow submit button handler
  document.getElementById('workflow-submit-btn').addEventListener('click', async () => {
    if (!selectedWorkflowId) return;

    // Collect text inputs
    const inputsDict = {};
    document.querySelectorAll('[id^="wf-text-"]').forEach(el => {
      const nid = el.id.replace('wf-text-', '');
      const val = el.value.trim();
      if (val) inputsDict[nid] = { text: val };
    });

    // Collect node param overrides
    const nodeParams = {};
    document.querySelectorAll('[id^="wf-param-"]').forEach(el => {
      const nid = String(el.dataset.node);
      const key = el.dataset.param;
      let val;
      if (el.type === 'checkbox') val = el.checked;
      else if (el.dataset.type === 'int') val = parseInt(el.value) || 0;
      else if (el.dataset.type === 'float') val = parseFloat(el.value) || 0;
      else val = el.value;
      if (!nodeParams[nid]) nodeParams[nid] = {};
      nodeParams[nid][key] = val;
    });

    const formData = new FormData();
    if (window._wfInputFile) formData.append('file', window._wfInputFile);
    formData.append('inputs', JSON.stringify(inputsDict));
    formData.append('node_params', JSON.stringify(nodeParams));

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

function updateWFSubmit() {
  const wfFileChosen = document.getElementById('wf-file-chosen');
  const submitBtn = document.getElementById('workflow-submit-btn');
  if (window._wfInputFile && wfFileChosen) {
    wfFileChosen.style.display = 'block';
    wfFileChosen.textContent = (getLang()==='zh'?'已选择文件: ':'File: ') + window._wfInputFile.name + ' (' + formatBytes(window._wfInputFile.size) + ')';
  }
  // Enable submit if there's a file OR the workflow has no file_input nodes
  if (submitBtn) {
    const hasFileInput = document.getElementById('wf-drop-zone') || document.getElementById('wf-file-input');
    submitBtn.disabled = hasFileInput && !window._wfInputFile;
  }
}

function buildProcessNodeParamsHtml(wfGraph, ntDefs) {
  const isZh = getLang() === 'zh';
  const ntMap = {}; ntDefs.forEach(nt => { ntMap[nt.id] = nt; });
  const nodeMap = {}; (wfGraph.nodes || []).forEach(n => { nodeMap[n.id] = n; });
  // Simple port edge map
  const portEdgeMap = {};
  if (ntMap) {
  // Normalize edges from both LiteGraph "links" and legacy "edges" format
  const rawEdges = wfGraph.links ? wfGraph.links.map(link => {
    if (Array.isArray(link) && link.length >= 5) {
      return { source: link[1], sourcePort: link[2], target: link[3], targetPort: link[4] };
    }
    return null;
  }).filter(Boolean) : (wfGraph.edges || []);
  rawEdges.forEach(e => {
      const srcNode = nodeMap[e.source];
      const srcNT = ntMap[(srcNode && srcNode.type || '').replace(/^wf_/, '')];
      const srcPort = (srcNT && srcNT.outputs && srcNT.outputs[e.sourcePort]) || { label: e.sourcePort };
      const tgtNode = nodeMap[e.target];
      portEdgeMap[e.target] = portEdgeMap[e.target] || {};
      portEdgeMap[e.target][e.targetPort] = { sourceNodeId: e.source, sourceLabel: srcNode ? (srcNode.title || srcNT.label || srcNode.type) : '', portLabel: srcPort.label || e.sourcePort };
    });
  }

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
    const label = n.title || (nt && nt.label) || typeId;
    const colorDot = nt && nt.color ? `<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${nt.color};flex-shrink:0;vertical-align:middle"></span>` : '';

    html += `<div style="background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:10px 14px;margin-bottom:10px">`;
    html += `<div style="font-weight:700;font-size:12px;color:var(--fg);margin-bottom:6px;display:flex;align-items:center;gap:6px">`;
    html += `<span style="display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;background:var(--accent);color:#000;font-size:10px;font-weight:700">#${n.id}</span>`;
    html += `${colorDot}${label} <span style="font-weight:400;font-size:10px;color:var(--fg2)">(${typeId})</span></div>`;

    const edgeInfo = portEdgeMap[n.id] || {};
    const portEntries = (nt && nt.inputs) || [];
    if (portEntries.length > 0) {
      html += `<div style="margin-bottom:6px;font-size:10px">`;
      portEntries.forEach(p => {
        const src = edgeInfo[p.name];
        const portLabel = isZh ? (p.label_zh || p.label || p.name) : (p.label || p.name);
        if (src) html += `<div style="color:var(--green);padding:1px 0">${portLabel} ← <span style="color:var(--fg2)">#${src.sourceNodeId} ${src.sourceLabel}</span></div>`;
        else html += `<div style="color:var(--orange);padding:1px 0">${portLabel}: ${t('new.portNotConnected')}</div>`;
      });
      html += `</div>`;
    }

    Object.entries(nt && nt.params || {}).forEach(([key, spec]) => {
      const val = props[key] !== undefined ? props[key] : (spec.default !== undefined ? spec.default : '');
      const fieldId = `wf-param-${n.id}-${key}`;
      const paramLabel = isZh ? (spec.label_zh || spec.label || key) : (spec.label || key);
      html += `<div class="form-group" style="margin-bottom:6px"><label style="font-size:11px">${paramLabel}</label>`;
      if (spec.type === 'bool') html += `<div><input type="checkbox" id="${fieldId}" data-node="${n.id}" data-param="${key}" data-type="bool" ${val ? 'checked' : ''}></div>`;
      else if (spec.type === 'choice') {
        html += `<select id="${fieldId}" data-node="${n.id}" data-param="${key}" data-type="choice" style="width:100%;padding:6px 10px;border-radius:4px;border:1px solid var(--border);background:var(--bg);color:var(--fg);font-size:12px;font-family:var(--font)">${(spec.choices||[]).map(c => { const display = key==='provider'?providerChoiceLabel(c):c; return `<option value="${c}" ${String(c)===String(val)?'selected':''}>${display}</option>`; }).join('')}</select>`;
      } else if (spec.type === 'int') html += `<input type="number" id="${fieldId}" data-node="${n.id}" data-param="${key}" data-type="int" value="${val}" min="${spec.min!=null?spec.min:-99999}" max="${spec.max!=null?spec.max:99999}" step="1" style="width:100%;padding:6px 10px;border-radius:4px;border:1px solid var(--border);background:var(--bg);color:var(--fg);font-size:12px;font-family:var(--font)">`;
      else if (spec.type === 'float') html += `<input type="number" id="${fieldId}" data-node="${n.id}" data-param="${key}" data-type="float" value="${val}" min="${spec.min!=null?spec.min:-99999}" max="${spec.max!=null?spec.max:99999}" step="any" style="width:100%;padding:6px 10px;border-radius:4px;border:1px solid var(--border);background:var(--bg);color:var(--fg);font-size:12px;font-family:var(--font)">`;
      else html += `<input type="text" id="${fieldId}" data-node="${n.id}" data-param="${key}" data-type="text" value="${String(val||'')}" style="width:100%;padding:6px 10px;border-radius:4px;border:1px solid var(--border);background:var(--bg);color:var(--fg);font-size:12px;font-family:var(--font)">`;
      html += `</div>`;
    });
    html += `</div>`;
  });
  return html;
}
