/* dashboard.js — Dashboard page with stats + task list + SSE-driven updates */
import { api, apiStream } from '../api.js';
import { t, getLang } from '../i18n.js';
import { setPollTimer } from '../router.js';

let currentFilter = { status: '', pipeline_type: '' };
let taskLimit = 20;
let pipelineTypeCache = {}; // id → {label, label_zh, ...}

const badgeLabels = {};

function _setBadgeLabels() {
  badgeLabels.queued = t('badge.queued');
  badgeLabels.running = t('badge.running');
  badgeLabels.completed = t('badge.completed');
  badgeLabels.failed = t('badge.failed');
  badgeLabels.cancelled = t('badge.cancelled');
}

export default async function renderDashboard(main) {
  main.innerHTML = `<h2>${t('dash.title')}</h2><div id="dash-content">
    <div class="skeleton-row">
      <div class="skeleton skeleton-stat"></div><div class="skeleton skeleton-stat"></div>
      <div class="skeleton skeleton-stat"></div><div class="skeleton skeleton-stat"></div>
    </div>
    <div class="skeleton skeleton-h2"></div>
    <div class="skeleton skeleton-card"></div><div class="skeleton skeleton-card"></div>
    <div class="skeleton skeleton-card"></div><div class="skeleton skeleton-card"></div>
  </div>`;

  _setBadgeLabels();
  const sseControllers = new Map(); // taskId → {close, es}
  let pollTimer = null;

  // ── Targeted DOM helpers (avoid full rebuild) ──

  function updateTaskCard(taskId, status) {
    const card = document.getElementById('task-card-' + taskId);
    if (!card) return;
    const badge = card.querySelector('.badge');
    if (badge) {
      badge.className = 'badge badge-' + status;
      badge.textContent = badgeLabels[status] || status;
    }
  }

  function updateStats(stats) {
    const setNum = (cls, val) => {
      const el = document.querySelector('#dash-content .stat.' + cls + ' .num');
      if (el) el.textContent = val || 0;
    };
    setNum('queued', stats.queued);
    setNum('running', stats.running);
    setNum('completed', stats.completed);
    setNum('failed', stats.failed);
  }

  // ── SSE subscription management ──

  function subscribeSSE(task) {
    if (sseControllers.has(task.id)) return;
    const ctrl = apiStream(task.id, (evt, data) => {
      if (evt === 'status') {
        updateTaskCard(task.id, data.status || task.status);
        // Also update stats with the delta if provided
        if (data.stats) updateStats(data.stats);
      }
      if (evt === 'complete') {
        updateTaskCard(task.id, 'completed');
        refreshStats();
      }
      if (evt === 'error') {
        updateTaskCard(task.id, 'failed');
        refreshStats();
      }
      if (evt === 'cancelled') {
        updateTaskCard(task.id, 'cancelled');
        refreshStats();
      }
    });
    sseControllers.set(task.id, ctrl);
  }

  async function refreshStats() {
    try {
      const data = await api('GET', '/tasks?limit=0');
      if (data.stats) updateStats(data.stats);
    } catch (_) {}
  }

  function syncSSE(tasks) {
    // Subscribe new running/queued tasks
    tasks.forEach(task => {
      if ((task.status === 'running' || task.status === 'queued') && !sseControllers.has(task.id)) {
        subscribeSSE(task);
      }
    });
    // Unsubscribe completed/terminal tasks
    const activeIds = new Set(tasks.filter(t => t.status === 'running' || t.status === 'queued').map(t => t.id));
    sseControllers.forEach((ctrl, id) => {
      if (!activeIds.has(id)) { ctrl.close(); sseControllers.delete(id); }
    });
  }

  // ── Full refresh (initial load + 30s fallback + filter changes) ──

  async function refresh() {
    const dash = main.querySelector('#dash-content');
    if (!dash) return;

    // Fetch pipeline types once for bilingual labels
    if (Object.keys(pipelineTypeCache).length === 0) {
      try {
        const ptData = await api('GET', '/pipeline-types');
        pipelineTypeCache = ptData.types || {};
      } catch (_) {}
    }

    const params = new URLSearchParams();
    params.set('limit', String(taskLimit));
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
    const isZh = getLang() === 'zh';
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
            ${pipelineTypes.map(pt => {
              const ptDef = pipelineTypeCache[pt];
              const ptLabel = isZh ? (ptDef?.label_zh || ptDef?.label || pt) : (ptDef?.label || pt);
              return `<option value="${pt}" ${currentFilter.pipeline_type===pt?'selected':''}>${ptLabel}</option>`;
            }).join('')}
          </select>
          <button class="btn btn-sm" id="dash-refresh-btn">${t('dash.refresh')}</button>
        </div>
      </div>
      <div class="task-list" id="task-list">
        ${tasks.length === 0 ? `<div class="empty"><div class="icon">&#128640;</div><p>${t('dash.empty')}</p></div>` : ''}
        ${tasks.map(task => {
          const dname = task.display_name || (task.pipeline_type + ' — ' + task.id);
          const isWf = task.is_workflow_task;
          return `<a href="#/task/${task.id}" class="task-card${isWf ? ' workflow-task' : ''}" id="task-card-${task.id}">
            <span class="badge badge-${task.status}">${badgeLabels[task.status] || task.status}</span>
            ${isWf ? `<span class="badge badge-workflow" title="${t('dash.workflowTask')}">🔄 ${t('dash.workflow')}</span>` : ''}
            <span class="badge" style="background:var(--bg3);color:var(--fg2);font-size:10px">${(pipelineTypeCache[task.pipeline_type] && (isZh ? pipelineTypeCache[task.pipeline_type].label_zh : pipelineTypeCache[task.pipeline_type].label)) || task.pipeline_type}</span>
            <div class="info">
              <div class="title">${dname}</div>
              <div class="meta">ID: ${task.id}</div>
            </div>
            <span class="arrow">→</span>
          </a>`;
        }).join('')}
      </div>
      ${tasks.length >= taskLimit ? `<div style="text-align:center;margin-top:12px"><button class="btn btn-sm" id="load-more-btn">${getLang()==='zh'?'加载更多':'Load more'} (${tasks.length})</button></div>` : ''}
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

    // Refresh button
    const refreshBtn = document.getElementById('dash-refresh-btn');
    if (refreshBtn) refreshBtn.addEventListener('click', () => refresh());

    // Load More button
    const loadMoreBtn = document.getElementById('load-more-btn');
    if (loadMoreBtn) loadMoreBtn.addEventListener('click', () => {
      taskLimit += 50;
      refresh();
    });

    // Sync SSE subscriptions after render
    syncSSE(tasks);
  }

  // ── Initial load ──
  await refresh();

  // 30s light fallback poll (catch new tasks, fix any drift)
  pollTimer = setInterval(refresh, 30000);
  setPollTimer(pollTimer);

  // Cleanup on page navigation
  window._pageCleanup = () => {
    if (pollTimer) { clearInterval(pollTimer); setPollTimer(null); }
    sseControllers.forEach(ctrl => ctrl.close());
    sseControllers.clear();
  };
}
