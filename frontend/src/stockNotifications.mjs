// Stock push policy shared by the signed-in UI and notification registration.
// The classic service worker mirrors these validators; tests run the same cases
// against both entry points to keep their policy aligned.
const SYMBOL = /^(?:[A-Z0-9_]{2,12}:)?[A-Z0-9][A-Z0-9._-]{0,14}$/;
const ALERT_ID = /^[A-Za-z0-9_-]{1,128}$/;
const CONTEXT = /^[a-f0-9]{64}$/;

export function normalizeAlertSymbol(value) {
  const symbol = typeof value === 'string' ? value.trim().toUpperCase() : '';
  return SYMBOL.test(symbol) ? symbol : '';
}

export function stockAlertLink(alert = {}) {
  const id = String(alert.alert_id || alert.id || '');
  const symbol = normalizeAlertSymbol(alert.symbol);
  const query = new URLSearchParams({ tab: 'stocks' });
  if (ALERT_ID.test(id)) query.set('alert', id);
  if (symbol) query.set('symbol', symbol);
  return `/?${query.toString()}`;
}

export function readStockAlertLink(search) {
  const params = new URLSearchParams(search || '');
  if (params.get('tab') !== 'stocks') return null;
  const rawId = params.get('alert') || '';
  const rawSymbol = params.get('symbol') || '';
  if (rawId && !ALERT_ID.test(rawId)) return null;
  const symbol = normalizeAlertSymbol(rawSymbol);
  if (rawSymbol && !symbol) return null;
  return { tab: 'stocks', alertId: rawId, symbol };
}

export function normalizeStockAlertPayload(payload, now = Date.now()) {
  const data = payload?.data;
  if (!data || data.type !== 'stock_alert' || data.category !== 'stocks') return null;
  const id = typeof data.alert_id === 'string' ? data.alert_id : '';
  const symbol = normalizeAlertSymbol(data.symbol);
  const context = typeof data.notification_context === 'string' ? data.notification_context : '';
  if (!ALERT_ID.test(id) || !symbol || !CONTEXT.test(context)) return null;
  const expiresAt = typeof data.expires_at === 'string' ? Date.parse(data.expires_at) : NaN;
  if (!Number.isFinite(expiresAt) || expiresAt <= now) return null;
  return {
    id, symbol, notification_context: context,
    expires_at: data.expires_at,
    title: typeof data.title === 'string' ? data.title.slice(0, 120) : `${symbol} stock alert`,
    body: typeof data.body === 'string' ? data.body.slice(0, 500) : 'Open Stocks to read the alert.',
    source: data.source === 'schwab_thinkorswim' ? data.source : 'stock_alert',
    source_timestamp: typeof data.source_timestamp === 'string' ? data.source_timestamp : null,
    received_at: typeof data.received_at === 'string' ? data.received_at : null,
    url: stockAlertLink({ id, symbol }),
  };
}

export function webPushCapability({ secure = false, serviceWorker = false, pushManager = false,
  notification = false, permission = 'default', isIos = false, standalone = false } = {}) {
  if (!secure) return { ok: false, status: 'unsupported', message: 'Open the secure HTTPS app to enable stock notifications.' };
  if (!(serviceWorker && pushManager && notification)) {
    if (isIos && !standalone) return { ok: false, status: 'needs-install', message: 'On iPhone or iPad, add CashOutAI to your Home Screen, open it there, then enable stock alerts. Web push needs iOS or iPadOS 16.4 or later.' };
    return { ok: false, status: 'unsupported', message: 'This browser does not support web push. You can still read every stock alert here.' };
  }
  if (permission === 'denied') return { ok: false, status: 'permission-denied', message: 'Notifications are blocked in your browser settings. Allow them for CashOutAI, then try again.' };
  return { ok: true, status: permission === 'granted' ? 'ready' : 'permission-needed', message: permission === 'granted' ? 'This browser is ready for stock notifications.' : 'Enable stock alerts to choose whether this browser may notify you.' };
}
