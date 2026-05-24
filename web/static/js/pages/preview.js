/** Multi-color preview page — Beer-Lambert real-time 3D preview.
 *
 * Route: #/preview
 * Flow: Upload image → Worker computes → Three.js renders → Tune params → Submit
 */

import { api } from '../api.js';
import { t, getLang } from '../i18n.js';
import { toast, formatBytes } from '../utils.js';
import { initPreview, updateMesh, setViewMode, cleanup, resize, getCanvas } from '../preview/renderer.js';

let worker = null;
let currentImageData = null;
let lastResult = null;
let currentPipelineType = 'multi_color_relief';
let debounceTimer = null;

export default async function renderPreview(main, hash) {
    // Parse hash for pipeline type: #/preview/multi_color_relief
    const parts = hash.split('/');
    if (parts.length > 2) currentPipelineType = parts[2];

    const isZh = getLang() === 'zh';

    main.innerHTML = `
    <div class="preview-layout">
      <div class="preview-sidebar">
        <div style="display:flex;align-items:center;gap:8px">
          <button class="btn btn-sm" id="pv-back">← ${t('new.back')}</button>
          <h3 style="margin:0;font-size:14px">${isZh ? '多色预览' : 'Multi-Color Preview'}</h3>
        </div>

        <div class="pv-card">
          <h4>${isZh ? '图片' : 'Image'}</h4>
          <div style="display:flex;gap:8px">
            <button class="btn btn-sm" id="pv-upload-btn" style="flex:1">${isZh ? '选择图片' : 'Choose Image'}</button>
            <input type="file" id="pv-file-input" accept=".jpg,.jpeg,.png,.webp,.bmp" style="display:none">
          </div>
          <div id="pv-img-info" style="font-size:11px;color:var(--muted);margin-top:4px"></div>
        </div>

        <div class="pv-card">
          <h4>${isZh ? '参数' : 'Parameters'}</h4>
          <div class="pv-field">
            <label>${isZh ? '颜色数量' : 'Colors'} <span class="val" id="pv-num-colors-val">4</span></label>
            <input type="range" id="pv-num-colors" min="2" max="8" value="4" step="1">
          </div>
          <div class="pv-field">
            <label>${isZh ? '层高 (mm)' : 'Layer Height'} <span class="val" id="pv-layer-height-val">0.08</span></label>
            <input type="range" id="pv-layer-height" min="0.04" max="0.4" value="0.08" step="0.04">
          </div>
          <div class="pv-field">
            <label>${isZh ? '最大深度 (mm)' : 'Max Depth'} <span class="val" id="pv-max-depth-val">3.0</span></label>
            <input type="range" id="pv-max-depth" min="0.5" max="10.0" value="3.0" step="0.1">
          </div>
          <div class="pv-field">
            <label>${isZh ? '底厚 (mm)' : 'Base Thickness'} <span class="val" id="pv-base-thick-val">0.6</span></label>
            <input type="range" id="pv-base-thick" min="0.2" max="5.0" value="0.6" step="0.1">
          </div>
          <div class="pv-field">
            <label>${isZh ? '抖动强度' : 'Dither'} <span class="val" id="pv-dither-val">0.8</span></label>
            <input type="range" id="pv-dither" min="0" max="1.0" value="0.8" step="0.05">
          </div>
          <div class="pv-field">
            <label>${isZh ? '宽度 (mm)' : 'Width'} <span class="val" id="pv-width-val">160</span></label>
            <input type="range" id="pv-width" min="20" max="500" value="160" step="5">
          </div>
          <div class="pv-field">
            <label>${isZh ? '高度 (mm)' : 'Height'} <span class="val" id="pv-height-val">120</span></label>
            <input type="range" id="pv-height" min="20" max="500" value="120" step="5">
          </div>
          <div class="pv-field">
            <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
              <input type="checkbox" id="pv-lithophane">
              ${isZh ? '夜灯模式 (背光)' : 'Lithophane (backlit)'}
            </label>
          </div>
        </div>

        <div class="pv-card" id="pv-filaments-card" style="display:none">
          <h4>${isZh ? '识别到的耗材' : 'Detected Filaments'}</h4>
          <div id="pv-filaments-list"></div>
        </div>

        <div class="pv-card" id="pv-swaps-card" style="display:none">
          <h4>${isZh ? '换色时序' : 'Swap Timeline'}</h4>
          <div id="pv-swaps-list" class="pv-swaps"></div>
        </div>

        <div class="pv-actions">
          <button class="btn btn-primary" id="pv-submit" disabled>${isZh ? '提交任务' : 'Submit Task'}</button>
          <div class="pv-view-toggle">
            <button class="active" data-view="front">${isZh ? '正面' : 'Front'}</button>
            <button data-view="back">${isZh ? '背面' : 'Back'}</button>
          </div>
        </div>
        <div class="pv-status" id="pv-status"></div>
      </div>

      <div class="preview-canvas-wrap" id="pv-canvas-wrap">
        <div class="pv-empty" id="pv-empty">
          <div class="icon">🖼️</div>
          <p>${isZh ? '拖拽图片到此处或点击选择' : 'Drop an image here or click to choose'}</p>
          <button class="btn btn-primary upload-btn" id="pv-empty-upload">${isZh ? '选择图片' : 'Choose Image'}</button>
        </div>
        <input type="file" id="pv-empty-file" accept=".jpg,.jpeg,.png,.webp,.bmp" style="display:none">
      </div>
    </div>`;

    // ── Wire up UI ──
    const canvasWrap = document.getElementById('pv-canvas-wrap');
    const emptyOverlay = document.getElementById('pv-empty');

    // File input triggers
    document.getElementById('pv-upload-btn').onclick = () => document.getElementById('pv-file-input').click();
    document.getElementById('pv-empty-upload').onclick = () => document.getElementById('pv-empty-file').click();
    document.getElementById('pv-file-input').onchange = (e) => handleFile(e.target.files[0]);
    document.getElementById('pv-empty-file').onchange = (e) => handleFile(e.target.files[0]);

    // Drag & drop
    canvasWrap.addEventListener('dragover', (e) => { e.preventDefault(); canvasWrap.classList.add('drag-over'); });
    canvasWrap.addEventListener('dragleave', () => canvasWrap.classList.remove('drag-over'));
    canvasWrap.addEventListener('drop', (e) => {
        e.preventDefault();
        canvasWrap.classList.remove('drag-over');
        const file = e.dataTransfer.files[0];
        if (file) handleFile(file);
    });

    // Back button
    document.getElementById('pv-back').onclick = () => { location.hash = '#/new'; };

    // View toggle
    document.querySelectorAll('.pv-view-toggle button').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.pv-view-toggle button').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            setViewMode(btn.dataset.view);
        };
    });

    // Submit
    document.getElementById('pv-submit').onclick = submitTask;

    // Parameter sliders → debounced recompute
    const paramIds = ['pv-num-colors','pv-layer-height','pv-max-depth','pv-base-thick','pv-dither','pv-width','pv-height'];
    paramIds.forEach(id => {
        const el = document.getElementById(id);
        el.oninput = () => {
            // Update value label
            const valEl = document.getElementById(id + '-val');
            if (valEl) valEl.textContent = el.value;
            scheduleRecompute();
        };
    });
    document.getElementById('pv-lithophane').onchange = () => scheduleRecompute();

    // ── Init Three.js ──
    const rect = canvasWrap.getBoundingClientRect();
    const cw = rect.width || 600;
    const ch = rect.height || 400;
    initPreview(canvasWrap, cw, ch);

    // Resize observer
    if (window.ResizeObserver) {
        new ResizeObserver(() => {
            const r = canvasWrap.getBoundingClientRect();
            resize(r.width, r.height);
        }).observe(canvasWrap);
    }

    // Cleanup on navigation
    window._pageCleanup = () => {
        if (worker) { worker.terminate(); worker = null; }
        cleanup();
        if (debounceTimer) clearTimeout(debounceTimer);
    };
}

// ── File handling ──

function handleFile(file) {
    if (!file || !file.type.startsWith('image/')) {
        toast(t('new.invalidFile') || 'Invalid file type');
        return;
    }

    document.getElementById('pv-img-info').textContent =
        `${file.name} (${formatBytes(file.size)})`;

    const reader = new FileReader();
    reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
            // Downscale for preview (max 256px on longest side)
            const maxDim = 256;
            let w = img.width, h = img.height;
            if (Math.max(w, h) > maxDim) {
                const scale = maxDim / Math.max(w, h);
                w = Math.round(w * scale);
                h = Math.round(h * scale);
            }

            const canvas = document.createElement('canvas');
            canvas.width = w;
            canvas.height = h;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0, w, h);
            currentImageData = ctx.getImageData(0, 0, w, h);

            // Hide empty overlay
            document.getElementById('pv-empty').style.display = 'none';

            // Start compute
            recompute();
        };
        img.src = e.target.result;
    };
    reader.readAsDataURL(file);
}

// ── Worker computation ──

function scheduleRecompute() {
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(recompute, 300);
}

function recompute() {
    if (!currentImageData) return;

    setStatus('computing', true);

    if (worker) { worker.terminate(); }
    worker = new Worker('/static/js/preview/worker.js');

    worker.onmessage = (e) => {
        const data = e.data;

        // Reconstruct typed arrays from transferred buffers
        const heightMap = new Float32Array(data.heightMap);
        const colorMap = new Uint8Array(data.colorMap);

        lastResult = {
            heightMap, colorMap,
            width: data.width, height: data.height,
            filaments: data.filaments,
            swaps: data.swaps,
            totalHeightMm: data.totalHeightMm,
            log: data.log,
        };

        // Update 3D view
        const physW = parseFloat(document.getElementById('pv-width').value);
        const physH = parseFloat(document.getElementById('pv-height').value);
        const baseT = parseFloat(document.getElementById('pv-base-thick').value);
        updateMesh(heightMap, colorMap, data.width, data.height, physW, physH, baseT);

        // Update filament list
        updateFilamentList(data.filaments);

        // Update swap timeline
        updateSwapList(data.swaps);

        // Enable submit
        document.getElementById('pv-submit').disabled = false;

        setStatus(data.log.join(' · '), false);
        worker = null;
    };

    worker.onerror = (err) => {
        setStatus('Worker error: ' + err.message, false);
        worker = null;
    };

    const params = {
        imageData: currentImageData,
        numColors: parseInt(document.getElementById('pv-num-colors').value),
        layerHeight: parseFloat(document.getElementById('pv-layer-height').value),
        maxDepth: parseFloat(document.getElementById('pv-max-depth').value),
        baseThickness: parseFloat(document.getElementById('pv-base-thick').value),
        ditherStrength: parseFloat(document.getElementById('pv-dither').value),
        lithophane: document.getElementById('pv-lithophane').checked,
    };

    worker.postMessage(params);
}

// ── UI updates ──

function updateFilamentList(filaments) {
    const card = document.getElementById('pv-filaments-card');
    const list = document.getElementById('pv-filaments-list');
    card.style.display = 'block';

    list.innerHTML = filaments.map((f, i) => `
      <div class="pv-filament">
        <div class="swatch" style="background:${f.color}"></div>
        <div class="info">
          <div class="name">${i + 1}. ${f.name}</div>
          <div class="td">TD = ${f.td} mm</div>
        </div>
      </div>
    `).join('');
}

function updateSwapList(swaps) {
    const card = document.getElementById('pv-swaps-card');
    const list = document.getElementById('pv-swaps-list');
    card.style.display = 'block';

    list.innerHTML = swaps.map(s => `
      <div class="pv-swap-row">
        <span class="z">Z=${s.z_mm.toFixed(2)}</span>
        <span class="arrow">→</span>
        <span class="fil-name">${s.filament_name}</span>
      </div>
    `).join('');
}

function setStatus(msg, spinning) {
    const el = document.getElementById('pv-status');
    el.innerHTML = (spinning ? '<span class="spinner"></span> ' : '') + msg;
}

// ── Submit to backend ──

async function submitTask() {
    if (!currentImageData) return;

    const btn = document.getElementById('pv-submit');
    btn.disabled = true;
    btn.textContent = (getLang() === 'zh') ? '提交中...' : 'Submitting...';

    try {
        // Convert ImageData back to a Blob
        const canvas = document.createElement('canvas');
        canvas.width = currentImageData.width;
        canvas.height = currentImageData.height;
        canvas.getContext('2d').putImageData(currentImageData, 0, 0);

        const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
        const formData = new FormData();
        formData.append('file', blob, 'preview.png');
        formData.append('pipeline_type', currentPipelineType);

        const params = {
            width: parseFloat(document.getElementById('pv-width').value),
            height: parseFloat(document.getElementById('pv-height').value),
            max_depth: parseFloat(document.getElementById('pv-max-depth').value),
            base_thickness: parseFloat(document.getElementById('pv-base-thick').value),
            layer_height: parseFloat(document.getElementById('pv-layer-height').value),
            dither_strength: parseFloat(document.getElementById('pv-dither').value),
            num_colors: parseInt(document.getElementById('pv-num-colors').value),
            multi_color: 'true',
            lithophane: document.getElementById('pv-lithophane').checked ? 'true' : '',
        };
        formData.append('params', JSON.stringify(params));

        const result = await api('POST', '/tasks', formData);
        toast(getLang() === 'zh' ? '任务已提交！' : 'Task submitted!');
        location.hash = '#/task/' + result.task_id;
    } catch (e) {
        toast('Submit error: ' + e.message);
        btn.disabled = false;
        btn.textContent = (getLang() === 'zh') ? '提交任务' : 'Submit Task';
    }
}
