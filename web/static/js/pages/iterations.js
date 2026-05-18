/* iterations.js — Iteration records & project docs unified view */
import { api } from '../api.js';
import { t } from '../i18n.js';
import { escHtml } from '../utils.js';

const TAG_COLORS = {
  frontend: '#6c9bd2',
  backend: '#4a9b5c',
  workflow: '#b07cd8',
  bugfix: '#e05577',
  test: '#e5a040',
  config: '#7f8c8d',
  design: '#569cd6',
  postmortem: '#d48a5c',
  evaluation: '#5cb0b8',
  architecture: '#c080d0',
  guide: '#7fb87f',
};

let currentFilter = 'all';

export default async function renderIterations(main, hash) {
  if (hash === '#/iterations') {
    await renderIterationList(main);
  } else {
    const iterId = hash.slice(13);
    await renderIterationViewer(main, iterId);
  }
}

async function renderIterationList(main) {
  main.innerHTML = `<h2 data-i18n="iterations.title">${t('iterations.title')}</h2><div id="iterations-content">${t('iterations.loading')}</div>`;

  let data;
  try { data = await api('GET', '/iterations'); }
  catch (e) {
    document.getElementById('iterations-content').innerHTML = `<div class="error-box"><p>${e.message}</p></div>`;
    return;
  }

  const items = data.iterations || [];
  window._iterItems = items;
  window._iterFilter = currentFilter;
  renderList(items, currentFilter);
}

function renderList(items, filter) {
  const filtered = filter === 'all' ? items : items.filter(x => x.source === filter);
  const content = document.getElementById('iterations-content');

  const iterCount = items.filter(x => x.source === 'iteration').length;
  const docCount = items.filter(x => x.source === 'doc').length;

  const filterBar = `
    <div class="iter-filter-bar">
      <button class="iter-filter-btn ${filter === 'all' ? 'active' : ''}" data-filter="all">
        ${t('iterations.all')} <span class="iter-filter-count">${items.length}</span>
      </button>
      <button class="iter-filter-btn ${filter === 'iteration' ? 'active' : ''}" data-filter="iteration">
        📊 ${t('iterations.iterations')} <span class="iter-filter-count">${iterCount}</span>
      </button>
      <button class="iter-filter-btn ${filter === 'doc' ? 'active' : ''}" data-filter="doc">
        📄 ${t('iterations.docs')} <span class="iter-filter-count">${docCount}</span>
      </button>
    </div>`;

  if (filtered.length === 0) {
    content.innerHTML = `${filterBar}<div class="empty"><p>${t('iterations.emptyFilter')}</p></div>`;
    return;
  }

  content.innerHTML = filterBar + `<div class="iterations-list">${filtered.map(item => renderIterationCard(item)).join('')}</div>`;

  // Wire filter buttons
  content.querySelectorAll('.iter-filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      currentFilter = btn.dataset.filter;
      renderList(items, currentFilter);
    });
  });
}

function renderIterationCard(item) {
  const isDoc = item.source === 'doc';
  const sourceBadge = isDoc
    ? `<span class="iter-source-badge doc">${t('iterations.docBadge')}</span>`
    : `<span class="iter-source-badge iteration">${t('iterations.iterationBadge')}</span>`;

  const tagsHtml = (item.tags || []).slice(0, 5).map(tag =>
    `<span class="iter-tag" style="--tag-color:${TAG_COLORS[tag] || '#888'}">${escHtml(tag)}</span>`
  ).join('');

  const metaParts = [];
  if (item.changedFiles) {
    metaParts.push(`<span class="iter-stat">📄 ${item.changedFiles} files</span>`);
  }
  if (item.branch && item.branch !== 'N/A') {
    metaParts.push(`<span class="iter-stat">⎇ ${escHtml(item.branch)}</span>`);
  }
  if (item.planName) {
    metaParts.push(`<span class="iter-stat">📋 ${escHtml(item.planName)}</span>`);
  }

  const summaryHtml = item.summary
    ? `<div class="iter-summary">${escHtml(item.summary)}</div>`
    : '';

  const metaHtml = metaParts.length
    ? `<div class="iter-stats">${metaParts.join(' · ')}</div>`
    : '';

  const icon = isDoc ? '📄' : (item.changedFiles ? '📊' : '📋');

  return `
    <a href="#/iterations/${encodeURIComponent(item.id)}" class="iteration-item">
      <span class="iter-icon">${icon}</span>
      <div class="iter-info">
        <div class="iter-title-row">
          <span class="iter-title">${escHtml(item.title)}</span>
          ${sourceBadge}
        </div>
        ${summaryHtml}
        <div class="iter-meta">
          <span class="iter-datetime">${escHtml(item.datetime || item.date)}</span>
          ${tagsHtml ? `<span class="iter-tags">${tagsHtml}</span>` : ''}
        </div>
        ${metaHtml}
      </div>
      <span class="arrow">→</span>
    </a>`;
}

async function renderIterationViewer(main, iterId) {
  main.innerHTML = `<h2 data-i18n="iterations.title">${t('iterations.title')}</h2><div id="iteration-viewer-content">${t('iterations.loading')}</div>`;

  let data;
  try { data = await api('GET', `/iterations/${iterId}`); }
  catch (e) {
    document.getElementById('iteration-viewer-content').innerHTML =
      `<div class="error-box"><p>${t('iterations.notFound')}: ${e.message}</p><a href="#/iterations" class="btn btn-sm">${t('iterations.back')}</a></div>`;
    return;
  }

  const isDoc = data.source === 'doc';
  const sourceLabel = isDoc ? t('iterations.docBadge') : t('iterations.iterationBadge');

  const content = document.getElementById('iteration-viewer-content');
  content.innerHTML = `
    <div class="iteration-viewer">
      <div class="breadcrumb">
        <a href="#/iterations">${t('iterations.title')}</a><span class="breadcrumb-sep">/</span>
        <span class="breadcrumb-current">${escHtml(data.title)}</span>
        <span class="iter-source-badge ${isDoc ? 'doc' : 'iteration'}" style="margin-left:8px">${sourceLabel}</span>
      </div>
      <div class="markdown-body">${data.content}</div>
    </div>
  `;
}
