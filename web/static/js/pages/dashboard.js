/* dashboard.js — Dashboard page with stats + task list + auto-refresh + filters */
import { api, apiStream } from '../api.js';
import { t, getLang } from '../i18n.js';
import { setPollTimer, setActiveSSE } from '../router.js';

let currentFilter = { status: '', pipeline_type: '' };

export default async function renderDashboard(main) {
  main.innerHTML = `<h2>${t('dash.title')}</h2><div id="dash-content">${t('dash.loading')}</div>`;

  let pollTimer = null;

  async function refresh() {
    const dash = main.querySelector('#dash-content');
    if (!dash) return;

    const params = new URLSearchParams();
    params.set('limit', '50');
    if (currentFilter.status) params.set('status', currentFilter.status);
    if (currentFilter.pipeline_type) params.set('pipeline_type', currentFilter.pipeline_type);

    let data;
    try {
      data = await api('GET', `/tasks?${params.toString()}`);
    } catch (e) {
      dash.innerHTML = `<div class="error-box">
        <p>${t('dash.error')}: ${e.message}</p>
        <button class="btn btn-primary" onclick="location.reload()">${t('dash.retry')}</button>
      </div>`;
      return;
    }

    const { tasks, stats } = data;
    const badgeLabels = {
      queued: t('badge.queued'), running: t('badge.running'),
      completed: t('badge.completed'), failed: t('badge.failed'), cancelled: t('badge.cancelled')
    };

    // Collect unique pipeline types for filter dropdown
    const pipelineTypes = [...new Set(tasks.map(t => t.pipeline_type).filter(Boolean))].sort();

    dash.innerHTML = `
      <div class="stats">
        <div class="stat queued"><div class="num">${stats.queued||0}</div><div class="label">${t('dash.queued')}</div></div>
        <div class="stat running"><div class="num">${stats.running||0}</div><div class="label">${t('dash.running')}</div></div>
        <div class="stat completed"><div class="num">${stats.completed||0}</div><div class="label">${t('dash.done')}</div></div>
        <div class="stat failed"><div class="num">${stats.failed||0}</div><div class="label">${t('dash.failed')}</div></div>
      </div>
      <div class="dash-header">
        <h3>${t('dash.recent')}</h3>
        <div class="dash-filters" style="display:flex;gap:8px;align-items:center">
          <select id="filter-status" class="filter-select" style="font-size:12px;padding:4px 8px;border-radius:4px;background:var(--bg2);color:var(--fg);border:1px solid var(--border)">
            <option value="">${t('dash.filterStatus')}</option>
            <option value="queued" ${currentFilter.status==='queued'?'selected':''}>${t('badge.queued')}</option>
            <option value="running" ${currentFilter.status==='running'?'selected':''}>${t('badge.running')}</option>
            <option value="completed" ${currentFilter.status==='completed'?'selected':''}>${t('badge.completed')}</option>
            <option value="failed" ${currentFilter.status==='failed'?'selected':''}>${t('badge.failed')}</option>
            <option value="cancelled" ${currentFilter.status==='cancelled'?'selected':''}>${t('badge.cancelled')}</option>
          </select>
          <select id="filter-pipeline" class="filter-select" style="font-size:12px;padding:4px 8px;border-radius:4px;background:var(--bg2);color:var(--fg);border:1px solid var(--border)">
            <option value="">${t('dash.filterType')}</option>
            ${pipelineTypes.map(pt => `<option value="${pt}" ${currentFilter.pipeline_type===pt?'selected':''}>${pt}</option>`).join('')}
          </select>
          <button class="btn btn-sm" onclick="location.reload()">${t('dash.refresh')}</button>
        </div>
      </div>
      <div class="task-list" id="task-list">
        ${tasks.length === 0 ? `<div class="empty"><div class="icon">&#128640;</div><p>${t('dash.empty')}</p></div>` : ''}
        ${tasks.map(task => {
          const dname = task.display_name || (task.pipeline_type + ' — ' + task.id);
          const isWf = task.is_workflow_task;
          return `<a href="#/task/${task.id}" class="task-card${isWf ? ' workflow-task' : ''}">
            <span class="badge badge-${task.status}">${badgeLabels[task.status] || task.status}</span>
            ${isWf ? `<span class="badge badge-workflow" title="${t('dash.workflowTask')}">🔄 ${t('dash.workflow')}</span>` : ''}
            <span class="badge" style="background:var(--bg3);color:var(--fg2);font-size:10px">${task.pipeline_type}</span>
            <div class="info">
              <div class="title">${dname}</div>
              <div class="meta">ID: ${task.id}</div>
            </div>
            <span class="arrow">→</span>
          </a>`;
        }).join('')}
      </div>
    `;

    // Wire filter change events
    const statusSel = document.getElementById('filter-status');
    const pipelineSel = document.getElementById('filter-pipeline');
    if (statusSel) statusSel.addEventListener('change', () => {
      currentFilter.status = statusSel.value;
      refresh();
    });
    if (pipelineSel) pipelineSel.addEventListener('change', () => {
      currentFilter.pipeline_type = pipelineSel.value;
      refresh();
    });
  }

  await refresh();
  pollTimer = setInterval(refresh, 5000);
  setPollTimer(pollTimer);

  // SSE for active tasks
  try {
    const data = await api('GET', '/tasks?status=running');
    data.tasks.forEach(task => {
      apiStream(task.id, (evt) => {
        if (evt === 'complete' || evt === 'error' || evt === 'cancelled') refresh();
      });
    });
  } catch (_) {}
}
