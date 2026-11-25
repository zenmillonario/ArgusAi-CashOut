import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';
import { createHash, webcrypto } from 'node:crypto';
import { normalizeStockAlertPayload, stockAlertLink, readStockAlertLink, webPushCapability } from './stockNotifications.mjs';
import { sameSession, sessionHeaders } from './sessionAuth.mjs';

const contextA = 'a'.repeat(64);
const contextB = 'b'.repeat(64);
const stockPayload = (changes = {}) => ({ data: {
  type: 'stock_alert', category: 'stocks', alert_id: 'alert_123', symbol: 'AAPL',
  title: 'AAPL stock alert', body: 'Price condition met.', source: 'schwab_thinkorswim',
  notification_context: contextA, url: 'https://untrusted.example/redirect',
  expires_at: '2099-01-01T00:00:00Z', ...changes,
} });

async function workerHarness() {
  const listeners = new Map();
  const storage = new Map();
  const shown = [];
  const closed = [];
  const opened = [];
  let background;
  const context = vm.createContext({ URL, URLSearchParams, Response, Promise,
    caches: { open: async () => ({ match: async key => storage.get(key)?.clone(), put: async (key, value) => storage.set(key, value.clone()) }) },
    clients: { matchAll: async () => [], openWindow: async url => opened.push(url) },
    self: {
      location: { origin: 'https://cashoutai.app' },
      registration: {
        showNotification: async (title, options) => shown.push({ title, ...options }),
        getNotifications: async () => shown.map(value => ({ data: value.data, close: () => closed.push(value.data.alert_id) })),
      },
      clients: { claim: async () => {} }, skipWaiting: () => {},
      addEventListener: (name, callback) => listeners.set(name, callback),
    },
    importScripts: () => {},
    firebase: { initializeApp: () => {}, messaging: () => ({ onBackgroundMessage: callback => { background = callback; } }) },
  });
  vm.runInContext(await readFile(new URL('../public/firebase-messaging-sw.js', import.meta.url), 'utf8'), context);
  const send = async data => {
    let task;
    let result;
    listeners.get('message')({ data, ports: [{ postMessage: value => { result = value; } }], waitUntil: value => { task = value; } });
    await task;
    return result;
  };
  return { context, listeners, shown, closed, opened, send, background: payload => background(payload) };
}

test('stock payload policy rejects unrelated, malformed, and unbound pushes', () => {
  const valid = normalizeStockAlertPayload(stockPayload());
  assert.equal(valid.id, 'alert_123');
  assert.equal(valid.url, '/?tab=stocks&alert=alert_123&symbol=AAPL');
  for (const change of [{ type: 'new_message' }, { category: 'chat' }, { notification_context: '' }, { notification_context: 'not-a-session' }, { symbol: 'javascript:alert(1)' }, { alert_id: '../account' }, { expires_at: '2001-01-01T00:00:00Z' }, { expires_at: '' }]) {
    assert.equal(normalizeStockAlertPayload(stockPayload(change)), null);
  }
});

test('stock deep links are constructed locally and parsed with a bounded ticker and alert ID', () => {
  assert.equal(stockAlertLink({ id: 'stock_1', symbol: 'nasdaq:aapl', url: 'https://bad.example' }), '/?tab=stocks&alert=stock_1&symbol=NASDAQ%3AAAPL');
  assert.deepEqual(readStockAlertLink('?tab=stocks&alert=stock_1&symbol=nasdaq%3Aaapl'), { tab: 'stocks', alertId: 'stock_1', symbol: 'NASDAQ:AAPL' });
  assert.equal(readStockAlertLink('?tab=stocks&alert=../../secret'), null);
  assert.equal(readStockAlertLink('?tab=stocks&symbol=%3Cscript%3E'), null);
  assert.equal(readStockAlertLink('?tab=profile'), null);
});

test('mobile push uses actual capabilities and offers installed iOS guidance only where needed', () => {
  const capable = { secure: true, serviceWorker: true, pushManager: true, notification: true, permission: 'granted' };
  assert.equal(webPushCapability({ ...capable, isIos: true }).ok, true);
  assert.equal(webPushCapability({ ...capable, permission: 'denied' }).status, 'permission-denied');
  assert.equal(webPushCapability({ secure: true, isIos: true, standalone: false }).status, 'needs-install');
  assert.equal(webPushCapability({ ...capable, secure: false }).status, 'unsupported');
});

test('worker shares context policy with foreground and never auto-displays a notification payload', async () => {
  const worker = await workerHarness();
  for (const changes of [{}, { type: 'new_message' }, { category: 'chat' }, { notification_context: '' }, { symbol: 'AAPL/evil' }, { alert_id: 'a?b' }, { expires_at: '2001-01-01T00:00:00Z' }, { expires_at: '' }]) {
    assert.equal(Boolean(worker.context.stockPushAlert(stockPayload(changes))), Boolean(normalizeStockAlertPayload(stockPayload(changes))));
  }
  let stopped = 0;
  worker.listeners.get('push')({ data: { json: () => ({ ...stockPayload(), notification: { title: 'Old generic payload' } }) }, stopImmediatePropagation: () => { stopped++; } });
  worker.listeners.get('push')({ data: { json: () => stockPayload({ type: 'new_message' }) }, stopImmediatePropagation: () => { stopped++; } });
  worker.listeners.get('push')({ data: { json: () => stockPayload() }, stopImmediatePropagation: () => { stopped++; } });
  assert.equal(stopped, 2);
});

test('worker opt-in, dedup, logout, and a queued old login push are enforced together', async () => {
  const worker = await workerHarness();
  await worker.background(stockPayload());
  assert.equal(worker.shown.length, 0);
  await worker.send({ type: 'STOCK_PUSH_SET_CONTEXT', context: contextA, enabled: true });
  await Promise.all([worker.background(stockPayload()), worker.send({ type: 'STOCK_PUSH_DISPLAY', payload: stockPayload() })]);
  assert.equal(worker.shown.length, 1);
  await worker.send({ type: 'STOCK_PUSH_SET_CONTEXT', context: contextB, enabled: true });
  await worker.send({ type: 'STOCK_PUSH_CLEAR_CONTEXT', context: contextA });
  await worker.background(stockPayload({ alert_id: 'old_login' }));
  assert.equal(worker.shown.length, 1);
  await worker.background(stockPayload({ alert_id: 'new_login', notification_context: contextB }));
  assert.equal(worker.shown.length, 2);
  await worker.send({ type: 'STOCK_PUSH_CLEAR_CONTEXT', context: contextB });
  await worker.background(stockPayload({ alert_id: 'after_logout', notification_context: contextB }));
  assert.equal(worker.shown.length, 2);
  assert.ok(worker.closed.includes('new_login'));
});

test('worker click opens the generated stock destination and rejects a stale-context click', async () => {
  const worker = await workerHarness();
  await worker.send({ type: 'STOCK_PUSH_SET_CONTEXT', context: contextA, enabled: true });
  let task;
  const click = data => {
    worker.listeners.get('notificationclick')({ notification: { data, close: () => {} }, action: '', stopImmediatePropagation: () => {}, waitUntil: value => { task = value; } });
    return task;
  };
  await click(stockPayload({ expires_at: '2001-01-01T00:00:00Z' }).data);
  assert.equal(worker.opened[0], 'https://cashoutai.app/?tab=stocks&alert=alert_123&symbol=AAPL');
  await worker.send({ type: 'STOCK_PUSH_CLEAR_CONTEXT', context: contextA });
  await click(stockPayload().data);
  assert.equal(worker.opened.length, 1);
});

async function serviceHarness(permission = 'default', { updatingWorker = false } = {}) {
  let promptCalls = 0;
  let listener;
  const messages = [];
  const requests = [];
  const events = [];
  const activeWorker = { state: 'activated', postMessage: (message, ports) => { messages.push(message); ports[0].postMessage({ ok: true }); } };
  const registration = { active: activeWorker };
  let changed;
  let waitStarted;
  const waitingForUpdate = new Promise(resolve => { waitStarted = resolve; });
  const installingWorker = { state: 'installing', addEventListener: (_, callback) => { changed = callback; waitStarted(); }, removeEventListener: () => {} };
  if (updatingWorker) {
    registration.active = { state: 'activated', postMessage: () => { throw new Error('Old worker used'); } };
    registration.installing = installingWorker;
  }
  const activateUpdate = () => { installingWorker.state = 'activated'; registration.installing = null; registration.active = activeWorker; changed(); };
  class Channel {
    constructor() {
      this.port1 = { onmessage: null, close: () => {} };
      this.port2 = { postMessage: data => queueMicrotask(() => this.port1.onmessage?.({ data })) };
    }
  }
  const Notification = { permission, requestPermission: () => { promptCalls++; return Promise.resolve('granted'); } };
  const context = vm.createContext({
    process: { env: {} }, sameSession, sessionHeaders, normalizeStockAlertPayload, webPushCapability,
    initializeApp: () => ({}), getMessaging: () => ({}), isSupported: async () => true, getToken: async () => 'fake-token-for-test',
    onMessage: (_, callback) => { listener = callback; return () => {}; },
    navigator: { userAgent: 'test', platform: 'test', serviceWorker: { register: async () => registration, getRegistration: async () => registration } },
    window: { isSecureContext: true, PushManager: {}, Notification, matchMedia: () => ({ matches: false }), dispatchEvent: event => events.push(event) },
    Notification, crypto: webcrypto, TextEncoder, Uint8Array, MessageChannel: Channel, URLSearchParams,
    CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options.detail; } },
    fetch: async (url, options) => { requests.push({ url, options }); return { ok: true }; },
    setTimeout, clearTimeout, Promise,
  });
  const source = (await readFile(new URL('./firebase-config.js', import.meta.url), 'utf8'))
    .replace(/^import .*;\n/gm, '')
    .replace('export class NotificationService', 'class NotificationService')
    .replace('export default notificationService;', 'globalThis.notificationService = notificationService;');
  vm.runInContext(source, context);
  return { service: context.notificationService, promptCalls: () => promptCalls, messages, requests, events, foreground: payload => listener?.(payload), Notification, waitingForUpdate, activateUpdate };
}

test('saved opt-in never prompts automatically; only the direct click method requests permission', async () => {
  const harness = await serviceHarness();
  assert.equal((await harness.service.initializeForUser('user', 'session', { stocksEnabled: false })).status, 'off');
  assert.equal((await harness.service.initializeForUser('user', 'session', { stocksEnabled: true })).status, 'permission-needed');
  assert.equal(harness.promptCalls(), 0);
  const promise = harness.service.requestPermissionForStocks();
  assert.equal(harness.promptCalls(), 1, 'permission request starts before the click handler yields');
  assert.equal((await promise).ok, true);
});

test('foreground filters queued old-login pushes and registration carries the captured active session', async () => {
  const harness = await serviceHarness('granted');
  const ready = await harness.service.initializeForUser('user', 'session', { stocksEnabled: true });
  assert.equal(ready.status, 'enabled');
  const expected = createHash('sha256').update('user\0session').digest('hex');
  assert.equal(harness.messages[0].context, expected);
  assert.equal(harness.requests[0].options.headers['X-Session-ID'], 'session');
  harness.foreground(stockPayload());
  assert.equal(harness.events.length, 0);
  harness.foreground(stockPayload({ notification_context: expected }));
  assert.equal(harness.events.length, 1);
  assert.equal(harness.events[0].type, 'cashoutai:stock-alert');
  harness.service.clearSession({ id: 'user', active_session_id: 'session' });
  harness.foreground(stockPayload({ notification_context: expected, alert_id: 'after_logout' }));
  assert.equal(harness.events.length, 1);
});

test('registration waits for the new stock worker instead of messaging an older active worker', async () => {
  const harness = await serviceHarness('granted', { updatingWorker: true });
  const initialized = harness.service.initializeForUser('user', 'session', { stocksEnabled: true });
  await harness.waitingForUpdate;
  assert.equal(harness.messages.length, 0);
  assert.equal(harness.requests.length, 0);
  harness.activateUpdate();
  assert.equal((await initialized).status, 'enabled');
  assert.equal(harness.messages[0].type, 'STOCK_PUSH_SET_CONTEXT');
});
