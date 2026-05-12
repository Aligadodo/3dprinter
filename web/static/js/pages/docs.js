/* docs.js — Documentation list and viewer */
import { api } from '../api.js';
import { t, getLang } from '../i18n.js';

export default async function renderDocs(main, hash) {
  if (hash === '#/docs') {
    await renderDocList(main);
  } else {
    const docId = hash.slice(7);
    await renderDocViewer(main, docId);
  }
}

async function renderDocList(main) {
  main.innerHTML = `<h2>${t('docs.title')}</h2><div id="doc-list-content">${t('docs.loading')}</div>`;

  let data;
  try { data = await api('GET', '/docs'); }
  catch (e) {
    document.getElementById('doc-list-content').innerHTML = `<div class="error-box"><p>${e.message}</p></div>`;
    return;
  }

  const docs = data.docs || [];
  const content = document.getElementById('doc-list-content');

  if (docs.length === 0) {
    content.innerHTML = `<div class="empty"><p>${t('docs.empty')}</p></div>`;
    return;
  }

  const lang = getLang();
  const isZh = lang === 'zh';
  content.innerHTML = `
    <div style="margin-bottom:8px;font-size:12px;color:var(--fg2)">
      📖 ${isZh ? '以下文档支持中英双语。在文档内可随时切换语言。' : 'All docs support bilingual (ZH/EN). Toggle language within each doc.'}
    </div>
    <div class="doc-list">
      ${docs.map(d => `
        <a href="#/docs/${d.id}" class="doc-item">
          <span class="doc-icon">📄</span>
          <div class="doc-info">
            <div class="doc-title">${isZh ? d.title_zh : d.title_en}</div>
            <div class="doc-desc">${isZh ? d.description_zh : d.description_en}</div>
          </div>
          <span class="arrow">→</span>
        </a>
      `).join('')}
    </div>
  `;
}

async function renderDocViewer(main, docId) {
  main.innerHTML = `<h2>${t('docs.title')}</h2><div id="doc-viewer-content">${t('docs.loading')}</div>`;

  let docLang = getLang();
  let data;
  try { data = await api('GET', `/docs/${docId}?lang=${docLang}`); }
  catch (e) {
    document.getElementById('doc-viewer-content').innerHTML =
      `<div class="error-box"><p>${t('docs.notFound')}: ${e.message}</p><a href="#/docs" class="btn btn-sm">${t('docs.back')}</a></div>`;
    return;
  }

  const content = document.getElementById('doc-viewer-content');
  content.innerHTML = `
    <div class="doc-viewer">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
        <a href="#/docs" class="btn btn-sm">← ${t('docs.back')}</a>
        <div style="display:flex;gap:2px;margin-left:auto">
          <button class="lang-btn ${docLang==='zh'?'lang-active':''}" data-doc-lang="zh">中</button>
          <button class="lang-btn ${docLang==='en'?'lang-active':''}" data-doc-lang="en">EN</button>
        </div>
      </div>
      <div class="markdown-body">${data.content || data.html}</div>
    </div>
  `;

  // Language switcher within doc viewer
  content.querySelectorAll('[data-doc-lang]').forEach(btn => {
    btn.addEventListener('click', async () => {
      docLang = btn.getAttribute('data-doc-lang');
      const newData = await api('GET', `/docs/${docId}?lang=${docLang}`);
      content.querySelector('.markdown-body').innerHTML = newData.content || newData.html;
      content.querySelectorAll('.lang-btn').forEach(b => {
        b.classList.toggle('lang-active', b.getAttribute('data-doc-lang') === docLang);
      });
    });
  });
}
