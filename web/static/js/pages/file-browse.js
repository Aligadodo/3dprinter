/* file-browse.js — Browse completed task output files */
import { api } from '../api.js';
import { t } from '../i18n.js';
import { formatTime } from '../utils.js';
import { showFileModal, showCtxMenu, getFile, cacheFile } from '../utils.js';

export default async function renderBrowse(main) {
  main.innerHTML = `<h2>${t('browse.title')}</h2><div id="browse-content">${t('browse.loading')}</div>`;

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

  content.innerHTML = `<div class="browse-grid">
    ${files.map(f => {
      const ext = (f.file_type||'').toLowerCase();
      const isImg = ['.png','.jpg','.jpeg','.webp','.bmp'].includes(ext);
      const fileUrl = f.url || '#';
      const fileName = f.filename || f.path.split(/[\\/]/).pop();
      const fid = cacheFile(f);
      return `<div class="browse-card file-card" data-fid="${fid}" onclick="import('/static/js/utils.js').then(m=>m.showFileModal('${fid}'))" oncontextmenu="import('/static/js/utils.js').then(m=>m.showCtxMenu(event,m.getFile('${fid}')))">
          ${isImg ? `<img src="${fileUrl}" alt="${fileName}" loading="lazy">`
            : `<div style="height:140px;display:flex;align-items:center;justify-content:center;font-size:40px;color:var(--fg2)">&#128736;</div>`}
          <div class="file-info">
            <div class="file-name" title="${fileName}">${fileName}</div>
            <div class="file-size">${f.pipelineType} — ${formatTime(f.taskTime)}</div>
          </div></div>`;
    }).join('')}
  </div>`;
}
