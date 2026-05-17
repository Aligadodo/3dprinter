/* workflows.js — Workflow list page */
import { api } from '../api.js';
import { t } from '../i18n.js';
import { showConfirm } from '../components/confirm.js';
import { escHtml } from '../utils.js';

export default async function renderWorkflowList(main) {
  main.innerHTML = `<h2>${t('wf.title')}</h2><div id="wf-list-content">
    <div class="skeleton skeleton-text"></div>
    <div class="skeleton skeleton-card"></div><div class="skeleton skeleton-card"></div>
    <div class="skeleton skeleton-card"></div>
  </div>`;

  let data;
  try { data = await api('GET', '/workflows'); }
  catch (e) {
    document.getElementById('wf-list-content').innerHTML =
      `<div class="error-box"><p>${e.message}</p></div>`;
    return;
  }

  const wfs = data.workflows || [];
  const content = document.getElementById('wf-list-content');

  content.innerHTML = `
    <div class="wf-list-header">
      <button class="btn btn-primary" onclick="location.hash='#/workflow/new'">+ ${t('wf.new')}</button>
    </div>
    ${wfs.length === 0 ? `<div class="empty"><div class="icon">&#128736;</div><p>${t('wf.empty')}</p></div>` : ''}
    <div class="wf-instance-list">
      ${wfs.map(wf => `
        <div class="wf-instance-card" style="cursor:pointer" onclick="location.hash='#/workflow/${wf.id}'">
          <span style="font-size:20px">🔧</span>
          <div style="flex:1;min-width:0">
            <div style="font-weight:600;font-size:13px">${escHtml(wf.name) || t('wf.untitled')}</div>
            <div style="font-size:11px;color:var(--fg2);margin-top:2px">${escHtml(wf.description) || ''} — ${(wf.graph?.nodes||[]).length} nodes</div>
          </div>
          <button class="btn btn-sm btn-danger wf-delete-btn" data-wf-id="${wf.id}" data-wf-name="${escHtml(wf.name || '')}">${t('wf.delete')}</button>
        </div>
      `).join('')}
    </div>
  `;

  // Delete handler via event delegation — avoids XSS via onclick injection
  content.addEventListener('click', async (e) => {
    const btn = e.target.closest('.wf-delete-btn');
    if (!btn) return;
    e.stopPropagation();
    const id = btn.dataset.wfId;
    const name = btn.dataset.wfName;
    if (!await showConfirm(t('wf.delete'), t('wf.deleteConfirm') + '\n\n' + name, t('wf.delete'), t('wf.runner.cancel'))) return;
    try {
      await api('DELETE', `/workflows/${id}`);
      location.reload();
    } catch (e) { alert(e.message); }
  });
}
