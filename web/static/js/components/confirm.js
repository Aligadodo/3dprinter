/* confirm.js — Custom confirmation dialog */
import { t } from '../i18n.js';

function escHtml(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

export function showConfirm(title, message, yesLabel, noLabel) {
  return new Promise((resolve) => {
    const yesText = yesLabel || 'OK';
    const noText = noLabel || 'Cancel';
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay confirm-overlay';
    overlay.style.display = 'flex';
    overlay.innerHTML = `
      <div class="modal confirm-modal" style="max-width:400px;width:90%">
        <div class="modal-header">
          <h3>${escHtml(title)}</h3>
        </div>
        <div class="modal-body" style="text-align:center;font-size:14px;line-height:1.6">
          <p style="white-space:pre-wrap">${escHtml(message)}</p>
        </div>
        <div class="modal-footer" style="justify-content:center">
          <button class="btn btn-danger confirm-yes">${yesText}</button>
          <button class="btn confirm-no">${noText}</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);

    const cleanup = (val) => {
      overlay.remove();
      document.removeEventListener('keydown', onKey);
      resolve(val);
    };

    const onKey = (e) => {
      if (e.key === 'Escape') cleanup(false);
      if (e.key === 'Enter') cleanup(true);
    };
    document.addEventListener('keydown', onKey);

    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) cleanup(false);
    });
    overlay.querySelector('.confirm-yes').addEventListener('click', () => cleanup(true));
    overlay.querySelector('.confirm-no').addEventListener('click', () => cleanup(false));
    overlay.querySelector('.confirm-yes').focus();
  });
}
