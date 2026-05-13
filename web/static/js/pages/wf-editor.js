/* wf-editor.js — Workflow Editor (LiteGraph DAG editor) */
import { api } from '../api.js';
import { t, getLang } from '../i18n.js';
import { toast, escHtml } from '../utils.js';

let wfGraph = null;
let wfCanvas = null;
let wfId = null;

export default async function renderWorkflowEditor(main, hash) {
  wfId = hash === '#/workflow/new' ? null : hash.slice(11);

  window._pageCleanup = () => {
    if (wfGraph) { wfGraph.stop(); wfGraph = null; }
    if (wfCanvas) { wfCanvas = null; }
    wfId = null;
  };

  main.innerHTML = `
    <div class="wf-toolbar">
      <span class="wf-name" id="wf-name-display">${wfId ? t('wf.loading') : t('wf.untitled')}</span>
      <input id="wf-name-input" placeholder="${t('wf.name')}" style="display:none;flex:1;padding:6px 10px;border-radius:4px;border:1px solid var(--border);background:var(--bg);color:var(--fg);font-size:13px;font-family:var(--font);max-width:300px">
      <button class="btn btn-sm" id="wf-save-btn">💾 ${t('wf.save')}</button>
      <button class="btn btn-sm btn-primary" id="wf-run-btn">▶ ${t('wf.run')}</button>
      <button class="btn btn-sm btn-danger" id="wf-delete-btn" ${!wfId?'style="display:none"':''}>${t('wf.delete')}</button>
    </div>
    <div class="wf-layout">
      <div class="wf-palette" id="wf-palette"></div>
      <div class="wf-canvas-wrap" id="wf-canvas-wrap"></div>
      <div class="wf-inspector" id="wf-inspector"><div class="wf-insp-placeholder">${t('inspector.noSelection')}</div></div>
    </div>
    <div class="wf-log" id="wf-log"></div>
    <div class="wf-node-tooltip" id="wf-tooltip"></div>
  `;

  // Load node types
  let nodeTypes = [];
  try { const d = await api('GET', '/node-types'); nodeTypes = d.types || []; }
  catch (e) { toast(e.message, 'error'); }
  window._wfNodeTypes = nodeTypes;

  // Build palette
  const catOrder = ['input','generate','process','output'];
  const catLabels = { input: t('wf.cat.input'), generate: t('wf.cat.generate'), process: t('wf.cat.process'), output: t('wf.cat.output') };
  const cats = {};
  nodeTypes.forEach(nt => {
    const cat = nt.category || 'other';
    if (!cats[cat]) cats[cat] = [];
    cats[cat].push(nt);
  });

  const palette = document.getElementById('wf-palette');
  palette.innerHTML = `
    <div style="margin-bottom:12px">
      <div style="font-size:10px;color:var(--fg2);text-transform:uppercase;margin-bottom:6px">${getLang()==='zh'?'模板':'Templates'}</div>
      <button class="btn btn-xs" style="width:100%;margin-bottom:4px" onclick="window._wfTemplate && window._wfTemplate('basic')">${t('wf.template.basic')}</button>
      <button class="btn btn-xs" style="width:100%;margin-bottom:4px" onclick="window._wfTemplate && window._wfTemplate('text2img')">${t('wf.template.text2img')}</button>
      <button class="btn btn-xs" style="width:100%;margin-bottom:4px" onclick="window._wfTemplate && window._wfTemplate('advanced')">${t('wf.template.advanced')}</button>
      <button class="btn btn-xs" style="width:100%" onclick="window._wfTemplate && window._wfTemplate('full')">${t('wf.template.full')}</button>
    </div>
    ${catOrder.filter(c => cats[c]).map(c => `
      <div class="cat-title">${catLabels[c] || c}</div>
      ${cats[c].map(nt => `
        <div class="node-item" draggable="true" data-nt='${JSON.stringify(nt).replace(/'/g,"&#39;")}'
             onmouseenter='window._wfShowTooltip && window._wfShowTooltip(event,${JSON.stringify(nt).replace(/'/g,"&#39;")})'
             onmouseleave="window._wfHideTooltip && window._wfHideTooltip()">
          <span class="dot" style="background:${nt.color||'#888'}"></span>${getLang()==='zh'?(nt.label_zh||nt.label):nt.label}
        </div>`).join('')}
    `).join('')}
  `;

  // Template function
  window._wfTemplate = (name) => {
    const templates = {
      basic: { nodes: [{id:1,type:'wf_file_input',title:'File',pos:[100,100]},{id:2,type:'wf_generate_relief',title:'Relief',pos:[400,100]}], edges: [{source:1,target:2,sourcePort:'file',targetPort:'image'}] },
      text2img: { nodes: [{id:1,type:'wf_text_input',title:'Text',pos:[100,100]},{id:2,type:'wf_text2img',title:'Text→Image',pos:[400,100]},{id:3,type:'wf_generate_relief',title:'Relief',pos:[700,100]}], edges: [{source:1,target:2,sourcePort:'text',targetPort:'prompt'},{source:2,target:3,sourcePort:'image',targetPort:'image'}] },
      advanced: { nodes: [{id:1,type:'wf_file_input',title:'File',pos:[100,100]},{id:2,type:'wf_layered_relief',title:'Layered',pos:[400,100]},{id:3,type:'wf_repair',title:'Repair',pos:[700,100]}], edges: [{source:1,target:2,sourcePort:'file',targetPort:'image'},{source:2,target:3,sourcePort:'stl',targetPort:'mesh'}] },
      full: { nodes: [{id:1,type:'wf_file_input',title:'File',pos:[100,100]},{id:2,type:'wf_3dgenerate',title:'3D Gen',pos:[400,100]},{id:3,type:'wf_views',title:'Views',pos:[700,100]}], edges: [{source:1,target:2,sourcePort:'file',targetPort:'image'},{source:2,target:3,sourcePort:'mesh',targetPort:'mesh'}] },
    };
    const tpl = templates[name];
    if (!tpl) return;
    wfGraph.clear();
    tpl.nodes.forEach(n => {
      const cleanType = (n.type || '').replace(/^wf_/, '');
      const LiteGraphNode = createLiteGraphNodeClass(cleanType, nodeTypes);
      if (LiteGraphNode) {
        const node = new LiteGraphNode(n.title);
        node.id = n.id; node.pos = n.pos;
        wfGraph.add(node);
      }
    });
    tpl.edges.forEach(e => {
      const srcNode = wfGraph._nodes.find(n => String(n.id) === String(e.source));
      const tgtNode = wfGraph._nodes.find(n => String(n.id) === String(e.target));
      if (srcNode && tgtNode) {
        const srcOut = srcNode.findOutputSlot(e.sourcePort);
        const tgtIn = tgtNode.findInputSlot(e.targetPort);
        if (srcOut >= 0 && tgtIn >= 0) wfGraph.add({source: srcNode, target: tgtNode, sourcePort: srcOut, targetPort: tgtIn});
      }
    });
    wfGraph.arrange();
    wfCanvas.setDirty(true, true);
    clearInspector();
    wfLog('Template loaded: ' + name);
  };

  // Tooltip
  window._wfShowTooltip = (e, nt) => {
    const tt = document.getElementById('wf-tooltip');
    const isZh = getLang() === 'zh';
    tt.innerHTML = `<div class="tt-header"><span class="tt-dot" style="background:${nt.color||'#888'}"></span>${isZh?(nt.label_zh||nt.label):nt.label}</div>
      <div class="tt-cat">${nt.category || ''}</div>
      ${nt.description ? `<div style="font-size:11px;color:var(--fg2)">${isZh?(nt.description_zh||nt.description):nt.description}</div>` : ''}
      ${(nt.inputs||[]).length>0?`<div class="tt-section"><div class="tt-section-title">Inputs</div>${nt.inputs.map(p=>`<div class="tt-port"><span class="tt-port-dot" style="background:var(--accent)"></span><span class="tt-port-name">${isZh?(p.label_zh||p.label||p.name):(p.label||p.name)}</span><span class="tt-port-type">${p.type||''}</span></div>`).join('')}</div>`:''}
      ${(nt.outputs||[]).length>0?`<div class="tt-section"><div class="tt-section-title">Outputs</div>${nt.outputs.map(p=>`<div class="tt-port"><span class="tt-port-dot" style="background:var(--green)"></span><span class="tt-port-name">${isZh?(p.label_zh||p.label||p.name):(p.label||p.name)}</span><span class="tt-port-type">${p.type||''}</span></div>`).join('')}</div>`:''}`;
    tt.style.display = 'block';
    tt.style.left = Math.min(e.clientX + 12, window.innerWidth - 340) + 'px';
    tt.style.top = Math.min(e.clientY + 12, window.innerHeight - tt.scrollHeight - 10) + 'px';
  };
  window._wfHideTooltip = () => { document.getElementById('wf-tooltip').style.display = 'none'; };

  // Init LiteGraph
  initLiteGraph(nodeTypes);

  // Load workflow if editing
  if (wfId) {
    try {
      const wf = await api('GET', `/workflows/${wfId}`);
      document.getElementById('wf-name-input').value = wf.name || '';
      document.getElementById('wf-name-display').textContent = wf.name || t('wf.untitled');
      document.getElementById('wf-name-input').style.display = 'block';
      document.getElementById('wf-name-display').style.display = 'none';
      loadGraph(wf.graph);
    } catch (e) { toast(e.message, 'error'); }
  }

  // Name edit
  const nameDisplay = document.getElementById('wf-name-display');
  const nameInput = document.getElementById('wf-name-input');
  nameDisplay.addEventListener('click', () => { nameDisplay.style.display='none'; nameInput.style.display='block'; nameInput.focus(); });
  nameInput.addEventListener('blur', () => { nameDisplay.textContent = nameInput.value || t('wf.untitled'); nameDisplay.style.display='block'; nameInput.style.display='none'; });

  // Save
  document.getElementById('wf-save-btn').addEventListener('click', async () => {
    const name = nameInput.value.trim() || t('wf.untitled');
    const graph = wfGraph.serialize();
    // Normalize: convert Float32Array pos to plain arrays (survives JSON round-trip)
    graph.nodes = (graph.nodes||[]).map(n => ({
      ...n,
      type: n.type||'',
      pos: Array.isArray(n.pos) ? [...n.pos] : (n.pos && typeof n.pos === 'object' && '0' in n.pos ? [n.pos[0]||0, n.pos[1]||0] : (n.pos || [100, 100]))
    }));
    try {
      if (wfId) {
        await api('PUT', `/workflows/${wfId}`, { name, graph });
      } else {
        const wf = await api('POST', '/workflows', { name, graph });
        wfId = wf.id;
        document.getElementById('wf-delete-btn').style.display = '';
        location.hash = '#/workflow/' + wfId;
      }
      toast(t('wf.saved'), 'success');
    } catch (e) { toast(t('wf.saveError') + ': ' + e.message, 'error'); }
  });

  // Run
  document.getElementById('wf-run-btn').addEventListener('click', async () => {
    if (!wfId) { toast(t('wf.saveFirst'), 'error'); return; }
    showRunParamsDialog(wfId);
  });

  // Delete
  document.getElementById('wf-delete-btn').addEventListener('click', async () => {
    if (!confirm(t('wf.deleteConfirm'))) return;
    try { await api('DELETE', `/workflows/${wfId}`); location.hash = '#/workflows'; }
    catch (e) { toast(e.message, 'error'); }
  });
}

function initLiteGraph(nodeTypes) {
  const canvasWrap = document.getElementById('wf-canvas-wrap');
  canvasWrap.innerHTML = '';

  const canvas = document.createElement('canvas');
  canvasWrap.appendChild(canvas);

  // Size canvas to fill container BEFORE passing to LiteGraph
  function updateCanvasSize() {
    const r = canvasWrap.getBoundingClientRect();
    const w = Math.max(r.width, 400);
    const h = Math.max(r.height, 300);
    canvas.width = w;
    canvas.height = h;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
  }
  updateCanvasSize();

  wfGraph = new LiteGraph.LGraph();
  wfCanvas = new LiteGraph.LGraphCanvas(canvas, wfGraph);

  // Enable keyboard shortcuts (Delete/Backspace) by giving canvas focus
  canvas.tabIndex = 0;
  canvas.addEventListener('click', () => canvas.focus());
  canvas.focus();

  // Right-click menu on nodes: add "Delete Node" option
  wfCanvas.getNodeMenuOptions = function(node) {
    return [
      { content: t('inspector.deleteNode'), callback: () => { wfGraph.remove(node); wfCanvas.setDirty(true, true); } },
      null, // separator
      { content: t('inspector.inputs'), disabled: true },
    ];
  };

  // Lock viewport: disable zoom, center at origin
  wfCanvas.allow_dragcanvas = true;
  wfCanvas.allow_interaction = true;
  // Reset transform to default so nodes appear at (0,0) area
  try {
    if (wfCanvas.ds) {
      wfCanvas.ds.scale = 1.0;
      if (!wfCanvas.ds.offset) {
        wfCanvas.ds.offset = [0, 0];
      }
      wfCanvas.ds.offset[0] = 0;
      wfCanvas.ds.offset[1] = 0;
    }
  } catch (_) { /* ds not ready yet */ }

  // Keep canvas sized on window resize
  window.addEventListener('resize', () => {
    updateCanvasSize();
    wfCanvas.setDirty(true, true);
  });

  // Register node types
  nodeTypes.forEach(nt => {
    const cls = createLiteGraphNodeClass(nt.id, nodeTypes);
    if (cls) LiteGraph.registerNodeType('wf_' + nt.id, cls);
  });

  // Drag from palette
  canvasWrap.addEventListener('dragover', e => e.preventDefault());
  canvasWrap.addEventListener('drop', e => {
    e.preventDefault();
    const raw = e.dataTransfer.getData('text/plain');
    if (!raw) return;
    try {
      const nt = JSON.parse(raw);
      const cls = LiteGraph.registered_node_types['wf_' + nt.id];
      if (cls) {
        const node = new cls();
        const rect = canvasWrap.getBoundingClientRect();
        const scale = wfCanvas.ds ? wfCanvas.ds.scale : 1;
        const offset = wfCanvas.ds ? [wfCanvas.ds.offset[0], wfCanvas.ds.offset[1]] : [0, 0];
        node.pos = [(e.clientX - rect.left - offset[0]) / scale, (e.clientY - rect.top - offset[1]) / scale];
        wfGraph.add(node);
        wfCanvas.setDirty(true, true);
        // Auto-select and inspect the newly dropped node
        setTimeout(() => renderInspector(node), 50);
      }
    } catch (_) {}
  });

  // Set drag data on palette items
  document.querySelectorAll('.node-item[draggable]').forEach(el => {
    el.addEventListener('dragstart', e => {
      e.dataTransfer.setData('text/plain', el.getAttribute('data-nt'));
    });
  });

  // Node selection → update inspector
  wfCanvas.onNodeSelected = function(node) {
    if (node && node._wfTypeId) renderInspector(node);
    else clearInspector();
  };

  wfGraph.start();
}

// ── Lenient type compatibility ──
// Allows 'file' → 'image'/'stl'/'mesh', 'string' → 'image', stl↔mesh, etc.
// The backend already handles type mismatches; this removes the artificial frontend block.
function _isTypeCompatible(srcType, tgtType) {
  if (!srcType || !tgtType) return true;
  if (srcType === tgtType) return true;
  if (srcType === '*' || tgtType === '*') return true;
  if (srcType === 'any' || tgtType === 'any') return true;
  // file → image/stl/mesh (files can contain images or meshes)
  if (srcType === 'file' && ['image', 'stl', 'mesh'].includes(tgtType)) return true;
  // string → image (text prompts → image generation)
  if (srcType === 'string' && tgtType === 'image') return true;
  // stl ↔ mesh interchange
  if ((srcType === 'stl' && tgtType === 'mesh') || (srcType === 'mesh' && tgtType === 'stl')) return true;
  // json → any (metadata can feed into any node)
  if (srcType === 'json') return true;
  return false;
}

function createLiteGraphNodeClass(typeId, nodeTypes) {
  const nt = nodeTypes.find(n => n.id === typeId);
  if (!nt) return null;

  function WFNode(title) {
    LiteGraph.LGraphNode.call(this, title || nt.label);
    this._wfTypeId = typeId;

    (nt.inputs||[]).forEach((p, i) => this.addInput(p.label || p.name, p.type || '*'));
    (nt.outputs||[]).forEach((p, i) => this.addOutput(p.label || p.name, p.type || '*'));

    if (nt.color) this.color = nt.color;

    // ✕ delete button
    this.addWidget('button', '✕', null, () => {
      if (wfGraph) { wfGraph.remove(this); wfCanvas.setDirty(true, true); }
    });

    this.properties = {};
    Object.entries(nt.params||{}).forEach(([key, spec]) => {
      this.properties[key] = spec.default;
      if (spec.type === 'bool') this.addWidget('toggle', spec.label || key, this.properties[key], v => { this.properties[key] = v; });
      else if (spec.type === 'choice') this.addWidget('combo', spec.label || key, this.properties[key], v => { this.properties[key] = v; }, { values: spec.choices||[] });
      else if (spec.type === 'int') this.addWidget('number', spec.label || key, this.properties[key], v => { this.properties[key] = Math.round(v); }, { min: spec.min||-99999, max: spec.max||99999, step: 1 });
      else if (spec.type === 'float') this.addWidget('number', spec.label || key, this.properties[key], v => { this.properties[key] = v; }, { min: spec.min||-99999, max: spec.max||99999 });
      else this.addWidget('text', spec.label || key, String(this.properties[key]||''), v => { this.properties[key] = v; });
    });
  }

  WFNode.prototype = Object.create(LiteGraph.LGraphNode.prototype);
  WFNode.prototype.constructor = WFNode;

  // Ensure title shows in node header
  WFNode.prototype.getTitle = function() {
    return this.title || nt.label;
  };

  // Lenient connect — overrides LiteGraph's strict type check
  WFNode.prototype.connect = function(slot, target_node, target_slot, options) {
    if (!this.outputs[slot] || !target_node.inputs[target_slot]) return false;
    var srcType = this.outputs[slot].type || '';
    var tgtType = target_node.inputs[target_slot].type || '';
    if (!_isTypeCompatible(srcType, tgtType)) return false;

    // If lenient but would fail LiteGraph's strict check, temporarily adjust types
    if (srcType !== tgtType && srcType !== '*' && tgtType !== '*' && srcType !== '' && tgtType !== '') {
      this.outputs[slot].type = '*';
      target_node.inputs[target_slot].type = '*';
      var result = LiteGraph.LGraphNode.prototype.connect.call(this, slot, target_node, target_slot, options);
      this.outputs[slot].type = srcType;
      target_node.inputs[target_slot].type = tgtType;
      return result;
    }
    return LiteGraph.LGraphNode.prototype.connect.call(this, slot, target_node, target_slot, options);
  };

  return WFNode;
}

// ── Inspector Panel ──
let _inspSelectedNode = null;

function clearInspector() {
  _inspSelectedNode = null;
  const panel = document.getElementById('wf-inspector');
  if (panel) panel.innerHTML = `<div class="wf-insp-placeholder">${t('inspector.noSelection')}</div>`;
}

function renderInspector(node) {
  if (!node || !node._wfTypeId) return;
  _inspSelectedNode = node;
  const panel = document.getElementById('wf-inspector');
  if (!panel) return;
  const isZh = getLang() === 'zh';

  // Find node type def
  const nt = (window._wfNodeTypes || []).find(n => n.id === node._wfTypeId);
  if (!nt) return;

  const nodeId = String(node.id);
  const title = node.title || nt.label || node._wfTypeId;

  // Build upstream output options for each input port
  function buildUpstreamOptions(tgtPortType, currentTgtSlot) {
    let opts = `<option value="">${t('inspector.notConnected')}</option>`;
    if (!wfGraph) return opts;
    wfGraph._nodes.forEach(other => {
      if (String(other.id) === nodeId) return;
      const otherNT = (window._wfNodeTypes || []).find(n => n.id === (other._wfTypeId || ''));
      if (!otherNT) return;
      (otherNT.outputs || []).forEach((op, opIdx) => {
        if (!op.type) return;
        if (_isTypeCompatible(op.type, tgtPortType)) {
          const srcLabel = other.title || otherNT.label || String(other.id);
          const portLabel = isZh ? (op.label_zh || op.label || op.name) : (op.label || op.name);
          const val = `${other.id}:${opIdx}`;
          // Check if this is the currently connected source
          let selected = '';
          if (wfGraph) {
            wfGraph._links.forEach(link => {
              if (String(link.target_id) === nodeId && link.target_slot === currentTgtSlot &&
                  String(link.origin_id) === String(other.id) && link.origin_slot === opIdx) {
                selected = ' selected';
              }
            });
          }
          opts += `<option value="${val}"${selected}>#${other.id} ${srcLabel} → ${portLabel} [${op.type}]</option>`;
        }
      });
    });
    return opts;
  }

  // Build output connection list
  function buildOutputConnections(srcSlot) {
    if (!wfGraph) return '';
    let html = '';
    wfGraph._links.forEach(link => {
      if (String(link.origin_id) === nodeId && link.origin_slot === srcSlot) {
        const tgtNode = wfGraph._nodes.find(n => String(n.id) === String(link.target_id));
        if (tgtNode) {
          const tgtNT = (window._wfNodeTypes || []).find(n => n.id === (tgtNode._wfTypeId || ''));
          const tgtLabel = tgtNode.title || (tgtNT && tgtNT.label) || String(tgtNode.id);
          const portName = (tgtNT && tgtNT.inputs && tgtNT.inputs[link.target_slot])
            ? (isZh ? (tgtNT.inputs[link.target_slot].label_zh || tgtNT.inputs[link.target_slot].label) : tgtNT.inputs[link.target_slot].label)
            : String(link.target_slot);
          html += `<div class="wf-insp-out-link">→ <strong>#${tgtNode.id} ${tgtLabel}</strong> <span style="color:var(--fg2)">: ${portName}</span></div>`;
        }
      }
    });
    return html || `<div class="wf-insp-out-none">${t('inspector.notConnected')}</div>`;
  }

  let html = `<div class="wf-insp-header">
    <span class="wf-insp-dot" style="background:${nt.color||'#888'}"></span>
    <span class="wf-insp-title">${escHtml(title)}</span>
    <span class="badge" style="font-size:9px;background:var(--bg3);color:var(--fg2)">${nt.id}</span>
    <button class="btn btn-xs btn-danger wf-insp-del-btn" title="${t('inspector.deleteNode')}" onclick="(function(){if(window._wfRemoveNode){window._wfRemoveNode(${nodeId})}})()">✕</button>
  </div>`;

  // Input ports
  if ((nt.inputs || []).length > 0) {
    html += `<div class="wf-insp-section"><div class="wf-insp-section-title">📥 ${t('inspector.inputs')}</div>`;
    (nt.inputs || []).forEach((p, i) => {
      const portLabel = isZh ? (p.label_zh || p.label || p.name) : (p.label || p.name);
      html += `<div class="wf-insp-field">
        <label class="wf-insp-label">${portLabel} <span class="wf-insp-type">[${p.type || '*'}]</span></label>
        <select class="wf-insp-select" data-node="${nodeId}" data-slot="${i}" onchange="window._wfInspChange && window._wfInspChange(this)">
          ${buildUpstreamOptions(p.type || '', i)}
        </select>
      </div>`;
    });
    html += `</div>`;
  }

  // Output ports
  if ((nt.outputs || []).length > 0) {
    html += `<div class="wf-insp-section"><div class="wf-insp-section-title">📤 ${t('inspector.outputs')}</div>`;
    (nt.outputs || []).forEach((p, i) => {
      const portLabel = isZh ? (p.label_zh || p.label || p.name) : (p.label || p.name);
      html += `<div class="wf-insp-field"><label class="wf-insp-label">${portLabel} <span class="wf-insp-type">[${p.type || '*'}]</span></label>
        ${buildOutputConnections(i)}
      </div>`;
    });
    html += `</div>`;
  }

  // Parameters
  if (Object.keys(nt.params || {}).length > 0) {
    html += `<div class="wf-insp-section"><div class="wf-insp-section-title">⚙ ${t('node.params')}</div>`;
    Object.entries(nt.params || {}).forEach(([key, spec]) => {
      const val = node.properties[key] !== undefined ? node.properties[key] : (spec.default !== undefined ? spec.default : '');
      const fieldId = `wf-insp-param-${nodeId}-${key}`;
      const paramLabel = isZh ? (spec.label_zh || spec.label || key) : (spec.label || key);
      html += `<div class="wf-insp-field"><label class="wf-insp-label" for="${fieldId}">${paramLabel}</label>`;
      if (spec.type === 'bool') {
        html += `<div><input type="checkbox" id="${fieldId}" ${val ? 'checked' : ''} onchange="var n=window._wfInspGetNode&&window._wfInspGetNode(${nodeId});if(n){n.properties['${key}']=this.checked;wfCanvas.setDirty(true,true)}"></div>`;
      } else if (spec.type === 'choice') {
        html += `<select id="${fieldId}" class="wf-insp-select" onchange="var n=window._wfInspGetNode&&window._wfInspGetNode(${nodeId});if(n){n.properties['${key}']=this.value;wfCanvas.setDirty(true,true)}">${(spec.choices||[]).map(c => `<option value="${c}" ${String(c)===String(val)?'selected':''}>${c.toUpperCase()}</option>`).join('')}</select>`;
      } else if (spec.type === 'int') {
        html += `<input type="number" id="${fieldId}" class="wf-insp-input" value="${val}" step="1" onchange="var n=window._wfInspGetNode&&window._wfInspGetNode(${nodeId});if(n){n.properties['${key}']=parseInt(this.value)||0;wfCanvas.setDirty(true,true)}">`;
      } else if (spec.type === 'float') {
        html += `<input type="number" id="${fieldId}" class="wf-insp-input" value="${val}" step="any" onchange="var n=window._wfInspGetNode&&window._wfInspGetNode(${nodeId});if(n){n.properties['${key}']=parseFloat(this.value)||0;wfCanvas.setDirty(true,true)}">`;
      } else {
        html += `<input type="text" id="${fieldId}" class="wf-insp-input" value="${String(val||'')}" onchange="var n=window._wfInspGetNode&&window._wfInspGetNode(${nodeId});if(n){n.properties['${key}']=this.value;wfCanvas.setDirty(true,true)}">`;
      }
      html += `</div>`;
    });
    html += `</div>`;
  }

  // Delete button
  html += `<div style="margin-top:12px"><button class="btn btn-sm btn-danger" style="width:100%" onclick="window._wfRemoveNode && window._wfRemoveNode(${nodeId})">🗑 ${t('inspector.deleteNode')}</button></div>`;

  panel.innerHTML = html;
}

// Global helpers for onclick handlers
window._wfNodeTypes = [];
window._wfInspChange = function(selectEl) {
  if (!wfGraph) return;
  const nodeId = String(selectEl.dataset.node);
  const slot = parseInt(selectEl.dataset.slot);
  const tgtNode = wfGraph._nodes.find(n => String(n.id) === nodeId);
  if (!tgtNode) return;

  // Remove existing links to this input slot
  const linksToRemove = [];
  wfGraph._links.forEach(link => {
    if (String(link.target_id) === nodeId && link.target_slot === slot) {
      linksToRemove.push(link);
    }
  });
  linksToRemove.forEach(link => wfGraph.removeLink(link.id));

  // Create new link if selected
  const val = selectEl.value;
  if (val) {
    const [srcId, srcSlot] = val.split(':');
    const srcNode = wfGraph._nodes.find(n => String(n.id) === srcId);
    if (srcNode && srcNode.outputs[parseInt(srcSlot)]) {
      wfGraph.add({ source: srcNode, target: tgtNode, sourcePort: parseInt(srcSlot), targetPort: slot });
    }
  }

  wfCanvas.setDirty(true, true);
  // Refresh inspector
  if (_inspSelectedNode) renderInspector(_inspSelectedNode);
};

window._wfInspGetNode = function(nodeId) {
  return wfGraph && wfGraph._nodes.find(n => String(n.id) === String(nodeId));
};

window._wfRemoveNode = function(nodeId) {
  if (!wfGraph) return;
  const node = wfGraph._nodes.find(n => String(n.id) === String(nodeId));
  if (node) {
    wfGraph.remove(node);
    wfCanvas.setDirty(true, true);
    clearInspector();
  }
};

function loadGraph(graphData) {
  wfGraph.clear();
  if (graphData && graphData.nodes && graphData.nodes.length > 0) {
    wfGraph.configure(graphData);
  }
  wfCanvas.setDirty(true, true);
}

function wfLog(msg) {
  const el = document.getElementById('wf-log');
  if (el) el.innerHTML += `<div>${msg}</div>`;
}

async function showRunParamsDialog(wfId) {
  const isZh = getLang() === 'zh';

  // Build overlay with loading state
  const overlay = document.createElement('div');
  overlay.className = 'run-params-overlay';
  overlay.innerHTML = `
    <div class="rp-modal" style="max-width:640px;max-height:85vh;overflow-y:auto">
      <div class="rp-header"><h3>${t('wf.run')}</h3><button class="rp-close">×</button></div>
      <div class="rp-body" id="rp-body"><p style="color:var(--fg2);text-align:center;padding:20px">${t('wf.loading')}</p></div>
      <div class="rp-footer" style="display:none" id="rp-footer">
        <button class="btn btn-primary" id="rp-confirm">▶ ${t('wf.run')}</button>
        <button class="btn" id="rp-cancel">${isZh?'取消':'Cancel'}</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);

  const close = () => overlay.remove();
  overlay.querySelector('.rp-close').addEventListener('click', close);
  overlay.querySelector('#rp-cancel').addEventListener('click', close);
  overlay.addEventListener('click', e => { if (e.target === overlay) close(); });

  // Fetch data
  let wfData, inputsData, nodeTypes;
  try {
    [wfData, inputsData, nodeTypes] = await Promise.all([
      api('GET', `/workflows/${wfId}`),
      api('GET', `/workflows/${wfId}/inputs`),
      api('GET', '/node-types'),
    ]);
  } catch (e) {
    document.getElementById('rp-body').innerHTML = `<div class="error-box"><p>${e.message}</p></div>`;
    return;
  }

  const ntMap = {};
  (nodeTypes.types||[]).forEach(nt => { ntMap[nt.id] = nt; });

  const graph = wfData.graph || {};
  const inputs = (inputsData.inputs || []).map(inp => ({ ...inp, node_type: (inp.node_type || '').replace(/^wf_/, '') }));

  let wfInputFile = null;

  // Build port edge map for showing connectivity
  const nodeMap = {}; (graph.nodes||[]).forEach(n => { nodeMap[n.id] = n; });
  const portEdgeMap = {};
  (graph.edges||[]).forEach(e => {
    const srcNode = nodeMap[e.source];
    const srcNT = ntMap[(srcNode && srcNode.type || '').replace(/^wf_/, '')];
    const srcPort = (srcNT && srcNT.outputs && srcNT.outputs[e.sourcePort]) || { label: e.sourcePort };
    portEdgeMap[e.target] = portEdgeMap[e.target] || {};
    portEdgeMap[e.target][e.targetPort] = {
      sourceNodeId: e.source,
      sourceLabel: srcNode ? (srcNode.title || (srcNT && srcNT.label) || srcNode.type) : '',
      portLabel: srcPort.label || e.sourcePort
    };
  });

  let bodyHTML = '';

  // Input nodes section
  if (inputs.length > 0) {
    bodyHTML += `<div style="margin-bottom:16px"><h4 style="margin-bottom:8px">${isZh?'输入节点':'Input Nodes'}</h4>`;
    inputs.forEach(inp => {
      if (inp.node_type === 'file_input') {
        const accept = (inp.params.accept || '.png,.jpg,.stl').split(',');
        bodyHTML += `<div class="form-group" style="margin-bottom:12px">
          <label style="font-weight:600">${inp.label} <span style="color:var(--fg2);font-weight:400">(${inp.node_type})</span></label>
          <div class="drop-zone" id="rp-drop-zone" style="margin-top:6px">
            <div class="icon">&#128193;</div>
            <div class="text">${isZh?'点击或拖拽上传文件':'Click or drag to upload file'}</div>
            <div class="sub">${accept.join(', ')}</div>
            <input type="file" id="rp-file-input" accept="${accept.join(',')}">
          </div>
          <div id="rp-file-chosen" style="display:none;font-size:13px;color:var(--green);margin-top:6px"></div></div>`;
      } else if (inp.node_type === 'text_input') {
        bodyHTML += `<div class="form-group" style="margin-bottom:12px">
          <label style="font-weight:600">${inp.label} <span style="color:var(--fg2);font-weight:400">(${inp.node_type})</span></label>
          <textarea id="rp-text-${inp.node_id}" rows="3" style="width:100%;padding:8px 12px;border-radius:var(--radius);border:1px solid var(--border);background:var(--bg);color:var(--fg);font-size:13px;font-family:var(--font);resize:vertical;margin-top:6px" placeholder="${(inp.params && inp.params.placeholder) || ''}"></textarea></div>`;
      }
    });
    bodyHTML += `</div>`;
  } else {
    bodyHTML += `<p style="color:var(--fg2);font-size:13px;margin-bottom:16px">${isZh?'此工作流无需外部输入，可直接运行':'This workflow needs no external input'}</p>`;
  }

  // Process node param overrides
  const processNodes = (graph.nodes||[]).filter(n => {
    const nt = ntMap[(n.type || '').replace(/^wf_/, '')];
    return nt && nt.category !== 'input' && nt.category !== 'output';
  });
  if (processNodes.length > 0) {
    bodyHTML += `<h4 style="margin-bottom:8px">${t('new.nodeParamsOverride')}</h4>`;
    processNodes.forEach(n => {
      const typeId = (n.type || '').replace(/^wf_/, '');
      const nt = ntMap[typeId];
      const props = n.properties || {};
      const label = n.title || (nt && nt.label) || typeId;
      const colorDot = nt && nt.color ? `<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${nt.color};flex-shrink:0;vertical-align:middle"></span>` : '';

      bodyHTML += `<div style="background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:10px 14px;margin-bottom:10px">`;
      bodyHTML += `<div style="font-weight:700;font-size:12px;color:var(--fg);margin-bottom:6px;display:flex;align-items:center;gap:6px">`;
      bodyHTML += `<span style="display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;background:var(--accent);color:#000;font-size:10px;font-weight:700">#${n.id}</span>`;
      bodyHTML += `${colorDot}${label} <span style="font-weight:400;font-size:10px;color:var(--fg2)">(${typeId})</span></div>`;

      // Port connectivity — dropdown-based input selection
      const portEntries = (nt && nt.inputs) || [];
      if (portEntries.length > 0) {
        bodyHTML += `<div style="margin-bottom:8px;font-size:11px">`;
        portEntries.forEach((p, pi) => {
          const portLabel = isZh ? (p.label_zh || p.label || p.name) : (p.label || p.name);
          const portType = p.type || '*';
          bodyHTML += `<div style="margin-bottom:4px"><label style="display:block;font-size:10px;font-weight:600;color:var(--fg);margin-bottom:2px">${portLabel} <span style="font-weight:400;color:var(--fg2)">[${portType}]</span></label>`;
          bodyHTML += `<select class="rp-input-sel" data-node="${n.id}" data-slot="${pi}" data-port="${escHtml(p.name)}" style="width:100%;padding:5px 8px;border-radius:4px;border:1px solid var(--border);background:var(--bg);color:var(--fg);font-size:11px;font-family:var(--font)">`;
          bodyHTML += `<option value="">${t('inspector.notConnected')}</option>`;
          // Build upstream options from all nodes in the graph
          (graph.nodes || []).forEach(other => {
            if (String(other.id) === String(n.id)) return;
            const otherTypeId = (other.type || '').replace(/^wf_/, '');
            const otherNT = ntMap[otherTypeId];
            if (!otherNT) return;
            (otherNT.outputs || []).forEach((op, opIdx) => {
              if (!op.type) return;
              if (_isTypeCompatible(op.type, portType)) {
                const srcLabel = other.title || (otherNT && otherNT.label) || String(other.id);
                const srcPortLabel = isZh ? (op.label_zh || op.label || op.name) : (op.label || op.name);
                const optVal = `${other.id}:${opIdx}:${escHtml(op.name)}`;
                // Check if currently connected via saved edge
                const edgeInfo = portEdgeMap[n.id] || {};
                const curSrc = edgeInfo[p.name];
                let sel = '';
                if (curSrc && String(curSrc.sourceNodeId) === String(other.id) && String(curSrc.portLabel) === String(op.name)) {
                  sel = ' selected';
                }
                bodyHTML += `<option value="${optVal}"${sel}>#${other.id} ${srcLabel} → ${srcPortLabel} [${op.type}]</option>`;
              }
            });
          });
          bodyHTML += `</select></div>`;
        });
        bodyHTML += `</div>`;
      }

      // Param fields
      Object.entries(nt && nt.params || {}).forEach(([key, spec]) => {
        const val = props[key] !== undefined ? props[key] : (spec.default !== undefined ? spec.default : '');
        const fieldId = `rp-param-${n.id}-${key}`;
        const paramLabel = isZh ? (spec.label_zh || spec.label || key) : (spec.label || key);
        bodyHTML += `<div class="form-group" style="margin-bottom:6px"><label style="font-size:11px">${paramLabel}</label>`;
        if (spec.type === 'bool') bodyHTML += `<div><input type="checkbox" id="${fieldId}" data-node="${n.id}" data-param="${key}" data-type="bool" ${val ? 'checked' : ''}></div>`;
        else if (spec.type === 'choice') {
          bodyHTML += `<select id="${fieldId}" data-node="${n.id}" data-param="${key}" data-type="choice" style="width:100%;padding:6px 10px;border-radius:4px;border:1px solid var(--border);background:var(--bg);color:var(--fg);font-size:12px;font-family:var(--font)">${(spec.choices||[]).map(c => `<option value="${c}" ${String(c)===String(val)?'selected':''}>${c.toUpperCase()}</option>`).join('')}</select>`;
        } else if (spec.type === 'int') bodyHTML += `<input type="number" id="${fieldId}" data-node="${n.id}" data-param="${key}" data-type="int" value="${val}" min="${spec.min!=null?spec.min:-99999}" max="${spec.max!=null?spec.max:99999}" step="1" style="width:100%;padding:6px 10px;border-radius:4px;border:1px solid var(--border);background:var(--bg);color:var(--fg);font-size:12px;font-family:var(--font)">`;
        else if (spec.type === 'float') bodyHTML += `<input type="number" id="${fieldId}" data-node="${n.id}" data-param="${key}" data-type="float" value="${val}" min="${spec.min!=null?spec.min:-99999}" max="${spec.max!=null?spec.max:99999}" step="any" style="width:100%;padding:6px 10px;border-radius:4px;border:1px solid var(--border);background:var(--bg);color:var(--fg);font-size:12px;font-family:var(--font)">`;
        else bodyHTML += `<input type="text" id="${fieldId}" data-node="${n.id}" data-param="${key}" data-type="text" value="${String(val||'')}" style="width:100%;padding:6px 10px;border-radius:4px;border:1px solid var(--border);background:var(--bg);color:var(--fg);font-size:12px;font-family:var(--font)">`;
        bodyHTML += `</div>`;
      });
      bodyHTML += `</div>`;
    });
  }

  document.getElementById('rp-body').innerHTML = bodyHTML;
  document.getElementById('rp-footer').style.display = '';

  // Wire file drop zone
  const rpDrop = document.getElementById('rp-drop-zone');
  const rpFileInput = document.getElementById('rp-file-input');
  if (rpDrop && rpFileInput) {
    rpDrop.addEventListener('click', () => rpFileInput.click());
    rpDrop.addEventListener('dragover', e => { e.preventDefault(); rpDrop.classList.add('dragover'); });
    rpDrop.addEventListener('dragleave', () => rpDrop.classList.remove('dragover'));
    rpDrop.addEventListener('drop', e => { e.preventDefault(); rpDrop.classList.remove('dragover'); if (e.dataTransfer.files.length) { wfInputFile = e.dataTransfer.files[0]; updateRPFile(); } });
    rpFileInput.addEventListener('change', () => { if (rpFileInput.files.length) { wfInputFile = rpFileInput.files[0]; updateRPFile(); } });
  }

  function updateRPFile() {
    const el = document.getElementById('rp-file-chosen');
    if (el && wfInputFile) {
      el.style.display = 'block';
      el.textContent = `${isZh?'已选择':'File'}: ${wfInputFile.name}`;
    }
  }

  // Submit
  overlay.querySelector('#rp-confirm').addEventListener('click', async () => {
    // Collect text inputs
    const inputsDict = {};
    document.querySelectorAll('[id^="rp-text-"]').forEach(el => {
      const nid = el.id.replace('rp-text-', '');
      const val = el.value.trim();
      if (val) inputsDict[nid] = { text: val };
    });

    // Collect node param overrides
    const nodeParams = {};
    document.querySelectorAll('[id^="rp-param-"]').forEach(el => {
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

    // Collect runtime edge overrides from input port dropdowns
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
    if (wfInputFile) formData.append('file', wfInputFile);
    formData.append('inputs', JSON.stringify(inputsDict));
    formData.append('node_params', JSON.stringify(nodeParams));
    formData.append('node_inputs', JSON.stringify(nodeInputs));

    overlay.remove();
    toast(t('wf.running'), 'success');
    try {
      const inst = await api('POST', `/workflows/${wfId}/run`, formData);
      toast(t('wf.runStarted') + ': ' + inst.id, 'success');
      setTimeout(() => { location.hash = '#/workflow/instance/' + inst.id; }, 600);
    } catch (e) { toast(e.message, 'error'); }
  });
}

// Cleanup
export function cleanupWfEditor() {
  if (wfGraph) { wfGraph.stop(); wfGraph = null; }
  if (wfCanvas) { wfCanvas = null; }
  wfId = null;
}
