import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeBotAnnouncement, mergeBotAnnouncements, recentBotAnnouncements } from './botAnnouncements.mjs';

const now = Date.parse('2026-11-25T13:00:00Z');
const notice = (n = 1, asset = 'BTC', age = 0) => ({
  id: `nautilus-run-${n.toString(16).padStart(64, '0')}`, type: 'bot_session_started', asset,
  createdAt: new Date(now - age).toISOString(), tab: `bot-${asset}`,
});

test('bot notice routing uses a fixed asset tab and strips untrusted fields', () => {
  const normalized = normalizeBotAnnouncement({ ...notice(), tab: 'https://example.test/', title: 'bad', sourceRunId: 'private' });
  assert.equal(normalized.tab, 'bot-BTC');
  assert.equal(normalized.title, 'BTC PAPER session detected');
  assert.equal('sourceRunId' in normalized, false);
  assert.equal(normalizeBotAnnouncement(notice(2, 'STOCKS')), null);
  assert.equal(normalizeBotAnnouncement({ ...notice(), type: 'notification' }), null);
  assert.equal(normalizeBotAnnouncement({ ...notice(), id: '../BTC' }), null);
  assert.equal(normalizeBotAnnouncement({ ...notice(), createdAt: '2026-11-25T13:00:00' }), null);
});

test('socket and history overlap merge once without dropping a newer socket notice', () => {
  const first = notice(1, 'BTC', 4000), next = notice(2, 'ETH');
  const rows = mergeBotAnnouncements([next, first], [first]);
  assert.deepEqual(rows.map(item => item.id), [next.id, first.id]);
  assert.equal(mergeBotAnnouncements([], Array.from({ length: 75 }, (_, i) => notice(i + 1))).length, 50);
});

test('banner groups by asset and never re-labels stale or future history as a new run', () => {
  const items = [notice(1, 'BTC'), notice(2, 'ETH', 1000), notice(3, 'BTC', 2000),
    notice(4, 'SOL', 91_000), notice(5, 'DOGE', -6000)];
  assert.deepEqual(recentBotAnnouncements(items, now).map(item => item.asset), ['BTC', 'ETH']);
  assert.equal(recentBotAnnouncements(items, now + 100_000).length, 0);
});
