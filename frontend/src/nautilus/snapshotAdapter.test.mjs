import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const source = await readFile(new URL('./snapshotAdapter.js', import.meta.url), 'utf8');
const { adaptNativeSnapshot } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const now = 1800000000;
const packet = positions => ({
  asset: { symbol: 'BTC' }, run: { stopped: false, review: false, fresh: true },
  market: { ticker: 'BTC-1', fresh: true, close_ts: now + 300, time: now, btc: 100000 },
  quote: { fresh: true, valid_until: now + 2, yes_bid: .19, yes_ask: .2, no_bid: .79, no_ask: .8 },
  positions,
});

test('closed and fully exited records are not shown as a current bot position', () => {
  const native = packet([
    { ticker: 'BTC-1', side: 'YES', qty: 10, closed: true, entry_ask: .1 },
    { ticker: 'BTC-1', side: 'NO', qty: 10, remaining_qty: 0, entry_ask: .1 },
  ]);
  const view = adaptNativeSnapshot(native, 'BTC', { state: 'live', now });
  assert.equal(view.position, null);
  assert.equal(view.status, 'OBSERVING');
});

test('current contract open position wins over an earlier unresolved contract', () => {
  const native = packet([
    { ticker: 'BTC-OLD', side: 'NO', qty: 12, entry_ask: .1 },
    { ticker: 'BTC-1', side: 'YES', qty: 10, remaining_qty: 4, entry_ask: .2 },
  ]);
  const view = adaptNativeSnapshot(native, 'BTC', { state: 'live', now });
  assert.equal(view.position.ticker, 'BTC-1');
  assert.equal(view.position.quantity, 4);
  assert.equal(view.position.currentBid, .19);
  assert.equal(view.canPractice, true);
});

test('expired quotes cannot mark a live position or enable a practice entry', () => {
  const native = packet([{ ticker: 'BTC-1', side: 'YES', qty: 10, entry_ask: .2, mark_valid: true }]);
  const view = adaptNativeSnapshot(native, 'BTC', { state: 'live', now: now + 3 });
  assert.equal(view.mode, 'stale');
  assert.equal(view.canPractice, false);
  assert.equal(view.position.currentBid, null);
  assert.equal(view.quotes.yes.ask, null);
});
