/* ═══════════════════════════════════════════
   router.js — Hash-based SPA router with dynamic imports
   ═══════════════════════════════════════════ */

import { t } from './i18n.js';

let pollTimer = null;
let activeSSE = null;

// Expose for external cleanup (workflow uses these too)
export { pollTimer, activeSSE };
export function setPollTimer(t) { pollTimer = t; }
export function setActiveSSE(s) { activeSSE = s; }

// ── Route table ──
const routes = {
  '#/dashboard':  () => import('./pages/dashboard.js'),
  '#/new':        () => import('./pages/new-task.js'),
  '#/browse':     () => import('./pages/file-browse.js'),
  '#/docs':       () => import('./pages/docs.js'),
  '#/iterations': () => import('./pages/iterations.js'),
  '#/workflows':  () => import('./pages/workflows.js'),
  '#/workflow/new': () => import('./pages/wf-editor.js'),
};

function resolveRoute(hash) {
  // Direct matches
  if (routes[hash]) return routes[hash];
  // Pattern matches
  if (hash.startsWith('#/task/')) {
    return () => import('./pages/task-detail.js');
  }
  if (hash.startsWith('#/docs/')) {
    return () => import('./pages/docs.js');
  }
  if (hash.startsWith('#/iterations/')) {
    return () => import('./pages/iterations.js');
  }
  if (hash.startsWith('#/workflow/instance/')) {
    return () => import('./pages/wf-runner.js');
  }
  if (hash.startsWith('#/workflow/')) {
    return () => import('./pages/wf-editor.js');
  }
  return null;
}

// ── Main route function ──
let _routing = false;
export async function route() {
  if (_routing) return;
  let hash = location.hash;
  if (!hash) {
    _routing = true;
    location.replace('#/dashboard');
    _routing = false;
    return;
  }
  const main = document.getElementById('main');
  if (!main) return;

  // Update sidebar active state
  const links = document.querySelectorAll('nav a[data-route]');
  links.forEach(a => {
    const isActive = a.getAttribute('href') === hash;
    a.classList.toggle('active', isActive);
    if (isActive) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  });

  // Cleanup previous page resources
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  if (activeSSE) { activeSSE.close(); activeSSE = null; }
  if (typeof window._pageCleanup === 'function') {
    try { window._pageCleanup(); } catch(_) {}
    window._pageCleanup = null;
  }

  const loader = resolveRoute(hash);

  if (loader) {
    try {
      const mod = await loader();
      if (typeof mod.default === 'function') {
        await mod.default(main, hash);
      }
    } catch (e) {
      console.error('Route error:', e);
      main.innerHTML = `<div class="error-box">
        <p>${t('dash.error')}: ${e.message}</p>
        <button class="btn btn-primary" onclick="location.reload()">${t('dash.retry')}</button>
      </div>`;
    }
  } else {
    // Fallback: render dashboard and update hash
    location.hash = '#/dashboard';
    return;
  }
}

// ── Event listeners ──
window.addEventListener('hashchange', route);
