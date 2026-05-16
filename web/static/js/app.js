/* app.js — Application entry point */
import { initI18n, getLang } from './i18n.js';
import { route } from './router.js';

function initTheme() {
  const saved = localStorage.getItem('theme') || 'dark';
  applyTheme(saved);
  document.getElementById('theme-toggle')?.addEventListener('click', () => {
    const next = document.documentElement.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
    applyTheme(next);
    localStorage.setItem('theme', next);
  });
}

function applyTheme(t) {
  document.documentElement.setAttribute('data-theme', t);
  const btn = document.getElementById('theme-toggle');
  if (btn) btn.textContent = t === 'light' ? '☾' : '☀';
}

// Boot sequence
(async () => {
  try {
    await initI18n();
    // Update lang buttons from initial state
    document.querySelectorAll('.lang-btn').forEach(b => {
      const l = b.getAttribute('data-lang');
      b.classList.toggle('lang-active', l === getLang());
    });
    // Wire language switch buttons
    document.querySelectorAll('.lang-btn').forEach(b => {
      b.addEventListener('click', async () => {
        const l = b.getAttribute('data-lang');
        if (!l) return;
        const { setLang } = await import('./i18n.js');
        setLang(l);
      });
    });
    // Init theme
    initTheme();
    // Start router
    route();
  } catch (e) {
    console.error('App init error:', e);
    const main = document.getElementById('main');
    if (main) {
      main.innerHTML = `<div class="error-box">
        <p>App init failed: ${e.message}</p>
        <button class="btn btn-primary" onclick="location.reload()">Retry</button>
      </div>`;
    }
  }
})();
