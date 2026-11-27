import { initializeApp } from 'firebase/app';
import { getMessaging, getToken, onMessage, isSupported } from 'firebase/messaging';
import { sameSession, sessionHeaders } from './sessionAuth.mjs';
import { normalizeStockAlertPayload, webPushCapability } from './stockNotifications.mjs';

// Firebase client config (public keys — safe to include in client code)
// These must match the config in firebase-messaging-sw.js
const firebaseConfig = {
  apiKey: process.env.REACT_APP_FIREBASE_API_KEY || "AIzaSyDXsZWHiHAhWxZz4TNmonxbG2RD2WNBoqU",
  authDomain: process.env.REACT_APP_FIREBASE_AUTH_DOMAIN || "cashoutai-notifications.firebaseapp.com",
  projectId: process.env.REACT_APP_FIREBASE_PROJECT_ID || "cashoutai-notifications",
  storageBucket: process.env.REACT_APP_FIREBASE_STORAGE_BUCKET || "cashoutai-notifications.firebasestorage.app",
  messagingSenderId: process.env.REACT_APP_FIREBASE_MESSAGING_SENDER_ID || "1077671941650",
  appId: process.env.REACT_APP_FIREBASE_APP_ID || "1:1077671941650:web:a48c3dce4bffa8e897aacb"
};

// VAPID key for push notifications
const VAPID_KEY = process.env.REACT_APP_FIREBASE_VAPID_KEY || "BCFwFhta05moYQ1dkY6Q1YjWCkGoOOCopnT19IwCzMP62X7RTKIPXUSV4ZQvWAq93QNJKUpV_1yjt42htBcfLvg";

const result = (ok, status, message) => ({ ok, status, message });
const stale = () => result(false, 'off', 'This login has changed.');
const API_URL = `${(process.env.REACT_APP_BACKEND_URL || '').replace(/\/$/, '')}/api`;

async function contextForSession(session) {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(`${session.id}\0${session.active_session_id}`));
  return Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, '0')).join('');
}

const waitForActiveWorker = registration => new Promise((resolve, reject) => {
  // After a deployment an older worker may still be active while the stock-only
  // worker installs. Wait for that update before sending its settings protocol.
  const worker = registration.installing || registration.waiting || registration.active;
  if (worker && (worker.state === 'activated' || (!registration.installing && !registration.waiting && registration.active))) { resolve(registration); return; }
  if (!worker) { reject(new Error('No notification worker is available.')); return; }
  const timer = setTimeout(() => { worker.removeEventListener('statechange', changed); reject(new Error('The notification worker did not become ready.')); }, 12000);
  const changed = () => {
    if (worker.state === 'activated') { clearTimeout(timer); worker.removeEventListener('statechange', changed); resolve(registration); }
    else if (worker.state === 'redundant') { clearTimeout(timer); worker.removeEventListener('statechange', changed); reject(new Error('The notification worker could not start.')); }
  };
  worker.addEventListener('statechange', changed);
  changed();
});

// Acknowledgements prevent the UI from claiming push is ready before the worker
// has persisted its stock-only setting. No credentials are sent to the worker.
function messageWorker(registration, message) {
  return new Promise((resolve, reject) => {
    const worker = registration?.active;
    if (!worker) { reject(new Error('The notification worker is not active.')); return; }
    const channel = new MessageChannel();
    const timer = setTimeout(() => { channel.port1.close(); reject(new Error('The notification worker did not respond.')); }, 7000);
    channel.port1.onmessage = event => {
      clearTimeout(timer); channel.port1.close();
      if (event.data?.ok) resolve(event.data);
      else reject(new Error('The notification setting could not be saved on this browser.'));
    };
    worker.postMessage(message, [channel.port2]);
  });
}

export class NotificationService {
  constructor() {
    this.session = null;
    this.context = null;
    this.token = null;
    this.registration = null;
    this.messaging = null;
    this.unsubscribe = null;
    this.stocksEnabled = false;
    this.generation = 0;
  }

  getCapability() {
    if (typeof window === 'undefined' || typeof navigator === 'undefined') return webPushCapability();
    const isIos = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    return webPushCapability({
      secure: window.isSecureContext === true,
      serviceWorker: 'serviceWorker' in navigator,
      pushManager: 'PushManager' in window,
      notification: 'Notification' in window,
      permission: 'Notification' in window ? Notification.permission : 'default',
      isIos,
      standalone: Boolean(navigator.standalone || window.matchMedia?.('(display-mode: standalone)').matches),
    });
  }

  get isSupported() { return this.getCapability().ok; }

  // Call directly in the button handler, before any network await. iOS requires
  // the permission request itself to happen during the user's click gesture.
  requestPermissionForStocks() {
    const capability = this.getCapability();
    if (!capability.ok) return Promise.resolve(capability);
    if (Notification.permission === 'granted') return Promise.resolve(result(true, 'ready', 'Stock notification permission is allowed.'));
    try {
      const permission = Notification.requestPermission();
      return Promise.resolve(permission).then(value => value === 'granted'
        ? result(true, 'ready', 'Stock notification permission is allowed.')
        : result(false, value === 'denied' ? 'permission-denied' : 'off', value === 'denied' ? 'Notifications are blocked in this browser. You can change this in browser settings.' : 'Stock notifications remain off.'));
    } catch (_) { return Promise.resolve(result(false, 'error', 'The browser could not request notification permission.')); }
  }

  async initializeForUser(userId, sessionId, { stocksEnabled = false } = {}) {
    const session = { id: userId, active_session_id: sessionId };
    if (!userId || !sessionId) return stale();
    if (this.session && !sameSession(this.session, session)) this.clearSession(this.session);
    this.session = session;
    const generation = ++this.generation;
    const current = () => generation === this.generation && sameSession(this.session, session);
    this.unsubscribe?.(); this.unsubscribe = null;
    this.stocksEnabled = stocksEnabled === true;
    if (!this.stocksEnabled) {
      await this.disableStockNotifications(session);
      return result(true, 'off', 'Stock push notifications are off.');
    }
    const capability = this.getCapability();
    if (!capability.ok) return capability;
    // A saved preference never opens a browser permission prompt automatically.
    if (Notification.permission !== 'granted') return result(false, 'permission-needed', 'Choose Enable stock alerts to allow notifications on this browser.');
    try {
      if (!await isSupported()) return result(false, 'unsupported', 'Firebase messaging is unavailable in this browser. The stock feed still works.');
      if (!current()) return stale();
      if (!this.messaging) this.messaging = getMessaging(initializeApp(firebaseConfig));
      const registration = await waitForActiveWorker(await navigator.serviceWorker.register('/firebase-messaging-sw.js'));
      if (!current()) return stale();
      this.registration = registration;
      const context = await contextForSession(session);
      if (!current()) return stale();
      this.context = context;
      const token = await getToken(this.messaging, { vapidKey: VAPID_KEY, serviceWorkerRegistration: registration });
      if (!current()) return stale();
      if (!token) throw new Error('No notification token is available.');
      const response = await fetch(`${API_URL}/fcm/register-token`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...sessionHeaders(session) },
        body: JSON.stringify({ token, user_id: userId }),
      });
      if (!current()) return stale();
      if (!response.ok) throw new Error('Notification registration was rejected.');
      await messageWorker(registration, { type: 'STOCK_PUSH_SET_CONTEXT', context, enabled: true });
      if (!current()) {
        // A later login has a different context; the worker clears only this one.
        await messageWorker(registration, { type: 'STOCK_PUSH_CLEAR_CONTEXT', context }).catch(() => {});
        return stale();
      }
      this.token = token;
      this.unsubscribe = onMessage(this.messaging, payload => {
        if (!current() || !this.stocksEnabled) return;
        const alert = normalizeStockAlertPayload(payload);
        if (!alert || alert.notification_context !== this.context) return;
        window.dispatchEvent(new CustomEvent('cashoutai:stock-alert', { detail: alert }));
        // The same worker handles foreground and background dedup, including when
        // several tabs share this permitted login.
        messageWorker(registration, { type: 'STOCK_PUSH_DISPLAY', payload }).catch(() => {});
      });
      return result(true, 'enabled', 'Stock alerts are enabled for this login and browser.');
    } catch (_) {
      if (!current()) return stale();
      this.stocksEnabled = false;
      this.unsubscribe?.(); this.unsubscribe = null;
      const context = this.context;
      if (context && this.registration) await messageWorker(this.registration, { type: 'STOCK_PUSH_CLEAR_CONTEXT', context }).catch(() => {});
      return result(false, 'error', 'Stock notifications could not be connected. You can still read alerts here and try again.');
    }
  }

  async disableStockNotifications(session = this.session) {
    if (session && this.session && !sameSession(this.session, session)) return stale();
    ++this.generation;
    this.stocksEnabled = false;
    this.unsubscribe?.(); this.unsubscribe = null;
    try {
      const context = this.context || (session?.id && session?.active_session_id && typeof crypto !== 'undefined' && crypto.subtle ? await contextForSession(session) : null);
      const registration = this.registration || (typeof navigator !== 'undefined' && 'serviceWorker' in navigator ? await navigator.serviceWorker.getRegistration('/firebase-messaging-sw.js') : null);
      if (context && registration?.active) await messageWorker(registration, { type: 'STOCK_PUSH_CLEAR_CONTEXT', context });
    } catch (_) { return result(false, 'error', 'The account setting is off. Reload this browser to finish clearing its notification setting.'); }
    return result(true, 'off', 'Stock push notifications are off.');
  }

  clearSession(session) {
    if (this.session && !sameSession(this.session, session)) return;
    this.disableStockNotifications(session).catch(() => {});
    this.session = null; this.context = null; this.token = null;
  }
}

const notificationService = new NotificationService();
export default notificationService;

