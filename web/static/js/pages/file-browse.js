/* file-browse.js — Browse completed task output files */
import { api } from '../api.js';
import { t, getLang } from '../i18n.js';
import { formatTime, toast, getFile, cacheFile } from '../utils.js';
import { showFileModal, showCtxMenu } from '../utils.js';

export default async function renderBrowse(main) {
  main.innerHTML = `<h2>${t('browse.title')}</h2><div id="browse-content">
    <div class="browse-grid">
      <div class="skeleton" style="height:190px"></div><div class="skeleton" style="height:190px"></div>
      <div class="skeleton" style="height:190px"></div><div class="skeleton" style="height:190px"></div>
      <div class="skeleton" style="height:190px"></div><div class="skeleton" style="height:190px"></div>
    </div>
  </div>`;

  let data;
  try {
    data = await api('GET', '/tasks?status=completed&limit=50');
  } catch (e) {
    document.getElementById('browse-content').innerHTML =
      `<div class="error-box"><p>${t('browse.error')}: ${e.message}</p><button class="btn btn-primary" onclick="location.reload()">${t('dash.retry')}</button></div>`;
    return;
  }

  const files = [];
  data.tasks.forEach(task => {
    (task.output_files||[]).forEach(f => {
      files.push({ ...f, taskId: task.id, pipelineType: task.pipeline_type, taskTime: task.created_at });
    });
  });

  const content = document.getElementById('browse-content');
  if (files.length === 0) {
    content.innerHTML = `<div class="empty"><div class="icon">&#128444;</div><p>${t('browse.empty')}</p></div>`;
    return;
  }

  const isZh = getLang() === 'zh';
  let selected = new Set();

  function updateBatchBar() {
    const bar = document.getElementById('batch-bar');
    const count = document.getElementById('batch-count');
    if (bar) bar.style.display = selected.size > 0 ? 'flex' : 'none';
    if (count) count.textContent = selected.size;
  }

  window._bfToggleSelect = (fid, checked) => {
    if (checked) selected.add(fid); else selected.delete(fid);
    updateBatchBar();
  };

  window._bfSelectAll = (checked) => {
    document.querySelectorAll('.bf-checkbox').forEach(cb => {
      cb.checked = checked;
      if (checked) selected.add(cb.value); else selected.delete(cb.value);
    });
    updateBatchBar();
  };

  window._bfClearSelection = () => {
    selected.clear();
    updateBatchBar();
    document.querySelectorAll('.bf-checkbox').forEach(cb => { cb.checked = false; });
  };

  window._bfDownloadSelected = () => {
    files.forEach(f => {
      if (selected.has(f._fid) && f.url) {
        const a = document.createElement('a');
        a.href = f.url;
        a.download = f.filename || '';
        a.click();
      }
    });
    toast(isZh ? `已触发 ${selected.size} 个文件下载` : `Downloading ${selected.size} files`, 'success');
  };

  window._bfCopyPaths = () => {
    const paths = files.filter(f => selected.has(f._fid)).map(f => f.path || '').filter(Boolean).join('\n');
    navigator.clipboard.writeText(paths).then(() => {
      toast(isZh ? `已复制 ${selected.size} 个路径` : `Copied ${selected.size} paths`, 'success');
    }).catch(() => toast('Copy failed', 'error'));
  };

  content.innerHTML = `
    <div class="batch-bar" id="batch-bar" style="display:none">
      <span>${isZh?'已选':'Selected'} <strong id="batch-count">0</strong> ${isZh?'个文件':'files'}</span>
      <span style="flex:1"></span>
      <button class="btn btn-sm" onclick="window._bfDownloadSelected()">${isZh?'下载选中':'Download'}</button>
      <button class="btn btn-sm" onclick="window._bfCopyPaths()">${isZh?'复制路径':'Copy paths'}</button>
      <button class="btn btn-sm" onclick="window._bfClearSelection()">${isZh?'取消选择':'Clear'}</button>
    </div>
    <div class="browse-grid">
      ${files.map(f => {
        const ext = (f.file_type||'').toLowerCase();
        const isImg = ['.png','.jpg','.jpeg','.webp','.bmp'].includes(ext);
        const fileUrl = f.url || '#';
        const fileName = f.filename || (f.path || '').split(/[\\/]/).pop();
        const fid = cacheFile(f);
        f._fid = fid;
        return `<div class="browse-card file-card" data-fid="${fid}" style="position:relative">
            <input type="checkbox" class="bf-checkbox" value="${fid}" onclick="event.stopPropagation()" onchange="window._bfToggleSelect('${fid}',this.checked)" title="${isZh?'选择':'Select'}">
            <div onclick="import('/static/js/utils.js').then(m=>m.showFileModal('${fid}'))" oncontextmenu="import('/static/js/utils.js').then(m=>m.showCtxMenu(event,m.getFile('${fid}')))">
              ${isImg ? `<img src="${fileUrl}" alt="${fileName}" loading="lazy">`
                : `<div style="height:140px;display:flex;align-items:center;justify-content:center;font-size:40px;color:var(--fg2)">&#128736;</div>`}
              <div class="file-info">
                <div class="file-name" title="${fileName}">${fileName}</div>
                <div class="file-size">${f.pipelineType} — ${formatTime(f.taskTime)}</div>
              </div>
            </div></div>`;
      }).join('')}
    </div>`;
}
