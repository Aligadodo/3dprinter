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

export function apiStream(taskId, onEvent, onStatusChange) {
  const url = `${API}/tasks/${taskId}/stream`;
  const events = ['status', 'log', 'progress', 'preview', 'complete', 'error', 'cancelled', 'ping'];

  let es = null;
  let connected = false;
  let reconnectAttempts = 0;
  let reconnectTimer = null;
  let closed = false;

  function bindEvents() {
    es.addEventListener('open', () => {
      connected = true;
      reconnectAttempts = 0;
      if (onStatusChange) onStatusChange('connected');
    });

    events.forEach(evt => {
      es.addEventListener(evt, (e) => {
        try { onEvent(evt, JSON.parse(e.data)); }
        catch (_) { onEvent(evt, e.data); }
      });
    });

    es.onerror = () => {
      if (connected) {
        connected = false;
        if (onStatusChange) onStatusChange('disconnected');
        scheduleReconnect();
      }
      // If never connected (e.g. server down), onerror fires without open first.
      // Don't schedule reconnect here — the initial connect attempt is still pending.
      // Only schedule reconnect when we had a connection and lost it.
    };
  }

  function scheduleReconnect() {
    if (closed) return;
    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
    reconnectAttempts++;
    if (onStatusChange) onStatusChange('reconnecting', { attempt: reconnectAttempts, delay: delay });
    reconnectTimer = setTimeout(connect, delay);
  }

  function connect() {
    es = new EventSource(url);
    bindEvents();
  }

  function close() {
    closed = true;
    if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
    if (es) { es.close(); es = null; }
  }

  if (onStatusChange) onStatusChange('connecting');
  connect();
  return { close, get es() { return es; } };
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
  } catch(e) { /* Don't cache failures — allow retry next call */ }
  return _providerStatuses || {};
}

export function providerChoiceLabel(providerId) {
  const ps = _providerStatuses || {};
  const info = ps[providerId];
  if (!info) return providerId;
  if (info.available) return info.name || providerId;
  return (info.name || providerId) + t('text2img.unavailableSuffix');
}
