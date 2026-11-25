/* global importScripts, firebase, self, clients, caches */
// One display path for data-only stock pushes, in foreground and background.
// Generic notifications are deliberately blocked before Firebase's push listener.
const STOCK_STATE_CACHE = 'cashoutai-stock-push-v1';
const STOCK_STATE_URL = '/__cashoutai_stock_push_state__';
const STOCK_CONTEXT = /^[a-f0-9]{64}$/;
const STOCK_SYMBOL = /^(?:[A-Z0-9_]{2,12}:)?[A-Z0-9][A-Z0-9._-]{0,14}$/;
const STOCK_ALERT_ID = /^[A-Za-z0-9_-]{1,128}$/;
let stockWork = Promise.resolve();

function stockPushAlert(payload, { allowExpired = false } = {}) {
  const data = payload?.data;
  if (!data || data.type !== 'stock_alert' || data.category !== 'stocks') return null;
  const id = typeof data.alert_id === 'string' ? data.alert_id : '';
  const symbol = typeof data.symbol === 'string' ? data.symbol.trim().toUpperCase() : '';
  const context = typeof data.notification_context === 'string' ? data.notification_context : '';
  if (!STOCK_ALERT_ID.test(id) || !STOCK_SYMBOL.test(symbol) || !STOCK_CONTEXT.test(context)) return null;
  const expiresAt = typeof data.expires_at === 'string' ? Date.parse(data.expires_at) : NaN;
  if (!allowExpired && (!Number.isFinite(expiresAt) || expiresAt <= Date.now())) return null;
  const query = new URLSearchParams({ tab: 'stocks', alert: id, symbol });
  return {
    id, symbol, context, expires_at: data.expires_at, url: `/?${query.toString()}`,
    title: typeof data.title === 'string' ? data.title.slice(0, 120) : `${symbol} stock alert`,
    body: typeof data.body === 'string' ? data.body.slice(0, 500) : 'Open Stocks to read the alert.',
  };
}

async function readStockState() {
  const cache = await caches.open(STOCK_STATE_CACHE);
  const value = await cache.match(STOCK_STATE_URL);
  if (!value) return { enabled: false, context: '', seen: [] };
  try {
    const state = await value.json();
    return { enabled: state.enabled === true, context: STOCK_CONTEXT.test(state.context) ? state.context : '', seen: Array.isArray(state.seen) ? state.seen.slice(-128) : [] };
  } catch (_) { return { enabled: false, context: '', seen: [] }; }
}

async function saveStockState(state) {
  const cache = await caches.open(STOCK_STATE_CACHE);
  await cache.put(STOCK_STATE_URL, new Response(JSON.stringify(state), { headers: { 'Content-Type': 'application/json' } }));
}

function queueStockWork(operation) {
  const work = stockWork.then(operation);
  stockWork = work.catch(() => {});
  return work;
}

async function displayStockAlert(payload) {
  const alert = stockPushAlert(payload);
  if (!alert) return { displayed: false };
  const state = await readStockState();
  if (!state.enabled || state.context !== alert.context || state.seen.includes(alert.id)) return { displayed: false };
  await self.registration.showNotification(alert.title, {
    body: alert.body,
    icon: '/icon-192x192.png',
    badge: '/badge-72x72.png',
    tag: `stock-alert-${alert.context.slice(0, 12)}-${alert.id}`,
    renotify: false,
    data: { type: 'stock_alert', category: 'stocks', alert_id: alert.id, symbol: alert.symbol, notification_context: alert.context, expires_at: alert.expires_at },
  });
  state.seen = [...state.seen, alert.id].slice(-128);
  await saveStockState(state);
  return { displayed: true };
}

self.addEventListener('push', event => {
  // Firebase auto-displays notification payloads. Reject them entirely, as well
  // as obsolete chat/admin pushes; our server sends stocks as data-only payloads.
  let payload;
  try { payload = event.data?.json(); } catch (_) { /* malformed push */ }
  if (!stockPushAlert(payload) || payload.notification) event.stopImmediatePropagation();
});

// Register the custom click handler before loading Firebase, per its web guide.
self.addEventListener('notificationclick', event => {
  event.stopImmediatePropagation();
  // An old displayed notification may still open its saved alert; it must never
  // create a fresh alert or require the original push to remain unexpired.
  const alert = stockPushAlert({ data: event.notification.data }, { allowExpired: true });
  if (!alert) { event.notification.close(); return; }
  event.notification.close();
  if (event.action === 'close') return;
  event.waitUntil(queueStockWork(async () => {
    const state = await readStockState();
    if (!state.enabled || state.context !== alert.context) return;
    const list = await clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const client of list) {
      let sameOrigin = false;
      try { sameOrigin = new URL(client.url).origin === self.location.origin; } catch (_) { /* ignore */ }
      if (!sameOrigin || !('focus' in client)) continue;
      client.postMessage({ type: 'OPEN_STOCK_ALERT', url: alert.url });
      await client.focus();
      return;
    }
    if (clients.openWindow) await clients.openWindow(new URL(alert.url, self.location.origin).href);
  }));
});

self.addEventListener('message', event => {
  const data = event.data || {};
  if (!['STOCK_PUSH_SET_CONTEXT', 'STOCK_PUSH_CLEAR_CONTEXT', 'STOCK_PUSH_DISPLAY'].includes(data.type)) return;
  event.waitUntil(queueStockWork(async () => {
    if (data.type === 'STOCK_PUSH_DISPLAY') return displayStockAlert(data.payload);
    if (!STOCK_CONTEXT.test(data.context || '')) throw new Error('Invalid notification context');
    const state = await readStockState();
    if (data.type === 'STOCK_PUSH_SET_CONTEXT') {
      await saveStockState({ enabled: data.enabled === true, context: data.context, seen: state.context === data.context ? state.seen : [] });
    } else if (state.context === data.context) {
      await saveStockState({ ...state, enabled: false });
      const notifications = await self.registration.getNotifications();
      for (const notification of notifications) {
        if (notification.data?.notification_context === data.context) notification.close();
      }
    }
    return {};
  }).then(value => event.ports?.[0]?.postMessage({ ok: true, ...value }), () => event.ports?.[0]?.postMessage({ ok: false })));
});

// Keep the worker compatible with the application's existing token-based SDK.
// This is not a migration to Firebase's newer Installation-ID API.
importScripts('https://www.gstatic.com/firebasejs/12.12.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/12.12.0/firebase-messaging-compat.js');
firebase.initializeApp({
  apiKey: 'AIzaSyDXsZWHiHAhWxZz4TNmonxbG2RD2WNBoqU',
  authDomain: 'cashoutai-notifications.firebaseapp.com',
  projectId: 'cashoutai-notifications',
  storageBucket: 'cashoutai-notifications.firebasestorage.app',
  messagingSenderId: '1077671941650',
  appId: '1:1077671941650:web:a48c3dce4bffa8e897aacb',
});
firebase.messaging().onBackgroundMessage(payload => queueStockWork(() => displayStockAlert(payload)));

self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('install', () => self.skipWaiting());
