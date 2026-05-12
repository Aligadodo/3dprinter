/* ═══════════════════════════════════════════
   utils.js — Shared utility functions
   ═══════════════════════════════════════════ */

import { t, getLang } from './i18n.js';

// ── HTML escaping ──
export function escHtml(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Formatting ──
export function formatTime(ts) {
  if (!ts) return '';
  const lang = getLang();
  return new Date(ts * 1000).toLocaleString(lang === 'zh' ? 'zh-CN' : 'en-US');
}

export function formatBytes(n) {
  if (!n) return '0 B';
  const u = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return n.toFixed(1) + ' ' + u[i];
}

// ── Toast (stacking) ──
let _toastTimer = null;

export function toast(msg, type) {
  const container = document.getElementById('toast');
  const el = document.createElement('div');
  el.className = `toast ${type || ''}`;
  el.textContent = msg;
  container.appendChild(el);
  // Auto-remove after 4s
  const timer = setTimeout(() => {
    el.classList.add('removing');
    setTimeout(() => el.remove(), 200);
  }, 4000);
  // Store timer to allow early removal
  el._timer = timer;
}

// ── File Cache ──
const _fileCache = new Map();
let _fileSeq = 0;
export let modalFileId = null;

export function cacheFile(f) {
  const id = 'f' + (++_fileSeq);
  _fileCache.set(id, f);
  return id;
}

export function getFile(id) {
  return _fileCache.get(id) || null;
}

export function modalFile() {
  return _fileCache.get(modalFileId) || null;
}

// ── Context Menu ──
let ctxTarget = null;

export function showCtxMenu(e, file) {
  e.preventDefault();
  e.stopPropagation();
  ctxTarget = file;
  const menu = document.getElementById('ctx-menu');
  const isLocal = location.hostname === '127.0.0.1' || location.hostname === 'localhost' || location.hostname === '::1';
  const isImg = ['.png','.jpg','.jpeg','.webp','.bmp'].includes((file.file_type||'').toLowerCase());

  const items = [
    { icon: isImg ? '🖼' : '📄', label: t('ctx.open'), action: 'open' },
    { icon: '⬇', label: t('ctx.download'), action: 'download' },
    { icon: '📋', label: t('ctx.copyPath'), action: 'copypath' },
  ];
  if (isLocal) {
    items.push({ sep: true });
    items.push({ icon: '📂', label: t('ctx.openFolder'), action: 'folder' });
    items.push({ icon: '⬛', label: t('ctx.openTerminal'), action: 'terminal' });
  }

  menu.innerHTML = items.map(it => {
    if (it.sep) return '<hr class="ctx-sep">';
    return `<div class="ctx-item" data-action="${it.action}"><span class="ctx-icon">${it.icon}</span>${it.label}</div>`;
  }).join('');

  menu.style.display = 'block';
  menu.style.left = Math.min(e.clientX, window.innerWidth - 200) + 'px';
  menu.style.top = Math.min(e.clientY, window.innerHeight - menu.scrollHeight - 10) + 'px';

  menu.querySelectorAll('.ctx-item').forEach(el => {
    el.addEventListener('click', () => handleCtxAction(el.dataset.action, file));
  });
}

export function hideCtxMenu() {
  document.getElementById('ctx-menu').style.display = 'none';
  ctxTarget = null;
}

export async function handleCtxAction(action, file) {
  hideCtxMenu();
  const fileUrl = file.url || '#';
  const absPath = file.path || '';

  switch (action) {
    case 'open':
      if (['.png','.jpg','.jpeg','.webp','.bmp'].includes((file.file_type||'').toLowerCase())) {
        showFileModal(file);
      } else {
        window.open(fileUrl, '_blank');
      }
      break;
    case 'download': {
      const a = document.createElement('a');
      a.href = fileUrl;
      a.download = file.filename || '';
      a.click();
      break;
    }
    case 'copypath':
      try {
        await navigator.clipboard.writeText(absPath);
        toast(t('ctx.copied'), 'success');
      } catch (_) {
        prompt(t('ctx.copyPath'), absPath);
      }
      break;
    case 'folder':
      await fetch('/api/open-path', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: absPath, action: 'folder' })
      }).catch(e => toast(e.message, 'error'));
      break;
    case 'terminal':
      await fetch('/api/open-path', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: absPath, action: 'terminal' })
      }).catch(e => toast(e.message, 'error'));
      break;
  }
}

// ── File Modal ──
export function showFileModal(fileOrId) {
  const file = typeof fileOrId === 'string' ? getFile(fileOrId) : fileOrId;
  if (!file) return;
  modalFileId = typeof fileOrId === 'string' ? fileOrId : cacheFile(file);

  const isImg = ['.png','.jpg','.jpeg','.webp','.bmp'].includes((file.file_type||'').toLowerCase());
  const fileUrl = file.url || '#';
  const fileName = file.filename || '';
  const absPath = file.path || '';
  const isLocal = location.hostname === '127.0.0.1' || location.hostname === 'localhost' || location.hostname === '::1';

  const overlay = document.getElementById('file-modal');
  overlay.innerHTML = `
    <div class="modal">
      <div class="modal-header">
        <h3>${fileName}</h3>
        <button class="close-btn" onclick="document.getElementById('file-modal').style.display='none'">×</button>
      </div>
      <div class="modal-body">
        ${isImg ? `<img src="${fileUrl}" alt="${fileName}">` : `<div style="text-align:center;font-size:64px;padding:40px;color:var(--fg2)">&#128736;</div>`}
        <table class="file-meta">
          <tr><td>${t('ctx.colFileType')}</td><td>${file.file_type || '-'}</td></tr>
          <tr><td>${t('ctx.colFileName')}</td><td style="word-break:break-all">${fileName}</td></tr>
          <tr><td>${t('ctx.colFilePath')}</td><td style="word-break:break-all;font:11px monospace">${absPath}</td></tr>
          ${file.category ? `<tr><td>${t('ctx.colCategory')}</td><td>${file.category}</td></tr>` : ''}
        </table>
      </div>
      <div class="modal-footer">
        <button class="btn btn-primary" onclick="import('./utils.js').then(m=>{m.handleCtxAction('open',m.modalFile());document.getElementById('file-modal').style.display='none'})">${t('ctx.open')}</button>
        <button class="btn" onclick="import('./utils.js').then(m=>{m.handleCtxAction('download',m.modalFile());document.getElementById('file-modal').style.display='none'})">${t('ctx.download')}</button>
        <button class="btn" onclick="import('./utils.js').then(m=>{m.handleCtxAction('copypath',m.modalFile());document.getElementById('file-modal').style.display='none'})">${t('ctx.copyPath')}</button>
        ${isLocal ? `
          <button class="btn" onclick="import('./utils.js').then(m=>{m.handleCtxAction('folder',m.modalFile());document.getElementById('file-modal').style.display='none'})">${t('ctx.openFolder')}</button>
          <button class="btn" onclick="import('./utils.js').then(m=>{m.handleCtxAction('terminal',m.modalFile());document.getElementById('file-modal').style.display='none'})">${t('ctx.openTerminal')}</button>
        ` : ''}
      </div>
    </div>
  `;
  overlay.style.display = 'flex';
}

export function closeFileModal() {
  document.getElementById('file-modal').style.display = 'none';
}

// ── Image Preview Modal ──
export function showImageModal(url) {
  const existing = document.querySelector('.wf-img-modal');
  if (existing) existing.remove();
  const modal = document.createElement('div');
  modal.className = 'wf-img-modal';
  modal.innerHTML = `<span class="wf-img-close">&times;</span><img src="${url}" alt="preview">`;
  modal.addEventListener('click', () => modal.remove());
  document.body.appendChild(modal);
}

// ── Global event listeners ──
document.addEventListener('click', (e) => {
  if (!e.target.closest('.ctx-menu')) hideCtxMenu();
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') { hideCtxMenu(); closeFileModal(); }
});
