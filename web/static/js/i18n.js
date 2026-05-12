/* ═══════════════════════════════════════════
   i18n.js — Locale loader, t() function, language switch
   ═══════════════════════════════════════════ */

let lang = localStorage.getItem('lang') || 'zh';
let messages = {};

export function getLang() { return lang; }

export async function initI18n() {
  await loadLocale(lang);
  updateStaticTexts();
  updateLangButtons();
}

export async function loadLocale(l) {
  if (messages[l]) return;
  try {
    const resp = await fetch(`/static/locales/${l}.json`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    messages[l] = await resp.json();
  } catch (e) {
    console.error(`Failed to load locale "${l}":`, e);
    // Fallback: use empty object, t() will return keys
    messages[l] = {};
  }
  // Always ensure zh is loaded as ultimate fallback
  if (l !== 'zh' && !messages['zh']) {
    try {
      const resp = await fetch('/static/locales/zh.json');
      messages['zh'] = await resp.json();
    } catch (_) { messages['zh'] = {}; }
  }
}

/**
 * Look up a translation by dotted key path.
 * Fallback order: current lang → zh (default) → key itself
 */
export function t(key, fallback) {
  const parts = key.split('.');
  // Try current language
  let val = _resolve(messages[lang], parts);
  // Fallback to zh
  if (val == null && lang !== 'zh') {
    val = _resolve(messages['zh'], parts);
  }
  return val ?? fallback ?? key;
}

function _resolve(obj, parts) {
  let cur = obj;
  for (const p of parts) {
    if (cur == null || typeof cur !== 'object') return null;
    cur = cur[p];
  }
  return cur;
}

export async function setLang(l) {
  if (l === lang && messages[l]) return;
  lang = l;
  localStorage.setItem('lang', l);
  await loadLocale(l);
  updateStaticTexts();
  updateLangButtons();
  // Re-render current page
  const { route } = await import('./router.js');
  route();
}

function updateStaticTexts() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    el.textContent = t(el.getAttribute('data-i18n'));
  });
}

function updateLangButtons() {
  document.querySelectorAll('.lang-btn').forEach(b => {
    const btnLang = b.getAttribute('data-lang') || b.textContent.trim();
    b.classList.toggle('lang-active', btnLang === lang || (btnLang === '中' && lang === 'zh') || (btnLang === 'EN' && lang === 'en'));
  });
}
