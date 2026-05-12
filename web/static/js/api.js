/* ═══════════════════════════════════════════
   api.js — Fetch wrapper, SSE streaming, provider cache
   ═══════════════════════════════════════════ */

import { t } from './i18n.js';

const API = '/api';

export async function api(method, path, body) {
  const opts = { method };
  if (body) {
    if (body instanceof FormData) {
      opts.body = body;
    } else {
      opts.body = JSON.stringify(body);
      opts.headers = { 'Content-Type': 'application/json' };
    }
  }
  let r;
  try {
    r = await fetch(API + path, opts);
  } catch (e) {
    throw new Error(t('toast.networkError'));
  }
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(err.detail || err.error || r.statusText);
  }
  return r.json();
}

export function apiStream(taskId, onEvent) {
  const url = `${API}/tasks/${taskId}/stream`;
  const es = new EventSource(url);
  const events = ['status', 'log', 'progress', 'preview', 'complete', 'error', 'cancelled', 'ping'];
  events.forEach(evt => {
    es.addEventListener(evt, (e) => {
      try { onEvent(evt, JSON.parse(e.data)); }
      catch (_) { onEvent(evt, e.data); }
    });
  });
  es.onerror = () => {};
  return es;
}

// ── Provider status cache ──
let _providerStatuses = null;  // {volcengine: {available, api_key_set, ...}, ...}

export async function fetchProviderStatuses() {
  if (_providerStatuses) return _providerStatuses;
  try {
    const r = await fetch(API + '/text2img/providers');
    const d = await r.json();
    _providerStatuses = {};
    (d.providers || []).forEach(p => { _providerStatuses[p.id] = p; });
  } catch(e) { _providerStatuses = {}; }
  return _providerStatuses;
}

export function providerChoiceLabel(providerId) {
  const ps = _providerStatuses || {};
  const info = ps[providerId];
  if (!info) return providerId;
  if (info.available) return info.name || providerId;
  return (info.name || providerId) + t('text2img.unavailableSuffix');
}
