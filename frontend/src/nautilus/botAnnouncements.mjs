const ASSETS = new Set(['BTC', 'ETH', 'SOL', 'XRP', 'DOGE']);
export const BOT_NOTICE_WINDOW_MS = 90_000;

export function normalizeBotAnnouncement(value) {
  if (!value || value.type !== 'bot_session_started' || !ASSETS.has(value.asset)
    || typeof value.id !== 'string' || !/^nautilus-run-[a-f0-9]{64}$/.test(value.id)
    || typeof value.createdAt !== 'string' || !/(Z|[+-]\d{2}:\d{2})$/.test(value.createdAt)) return null;
  const time = Date.parse(value.createdAt);
  if (!Number.isFinite(time) || time <= 0) return null;
  return {
    id: value.id, type: 'bot_session_started', asset: value.asset,
    createdAt: new Date(time).toISOString(), tab: `bot-${value.asset}`,
    title: `${value.asset} PAPER session detected`,
    message: `A fresh ${value.asset} PAPER feed was detected. Open the room to check its current status and practice.`,
  };
}

export function mergeBotAnnouncements(previous, incoming, limit = 50) {
  const items = new Map();
  for (const raw of [...(Array.isArray(previous) ? previous : []), ...(Array.isArray(incoming) ? incoming : [])]) {
    const item = normalizeBotAnnouncement(raw);
    if (item) items.set(item.id, item);
  }
  return [...items.values()].sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt) || a.id.localeCompare(b.id))
    .slice(0, Math.max(1, Math.min(50, limit)));
}

export function recentBotAnnouncements(items, now = Date.now()) {
  const assets = new Set();
  return mergeBotAnnouncements([], items).filter(item => {
    const age = now - Date.parse(item.createdAt);
    if (age < -5000 || age > BOT_NOTICE_WINDOW_MS || assets.has(item.asset)) return false;
    assets.add(item.asset);
    return true;
  });
}
