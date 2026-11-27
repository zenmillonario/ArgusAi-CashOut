import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const source = await readFile(new URL('./snapshotAdapter.js', import.meta.url), 'utf8');
const { adaptNativeSnapshot, accountMarks } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const now = 1800000000;
const book = { yes_bid: .19, yes_ask: .2, no_bid: .79, no_ask: .8 };
const emptyQuotes = { yes: { bid: null, ask: null }, no: { bid: null, ask: null } };
const expectedQuotes = { yes: { bid: .19, ask: .2 }, no: { bid: .79, ask: .8 } };
const account = { positions: [{ id: 'practice-1', asset: 'BTC', contractId: 'BTC-1', side: 'YES' }] };
const packet = (positions = []) => ({
  asset: { symbol: 'BTC' }, run: { stopped: false, review: false, fresh: true },
  market: { ticker: 'BTC-1', fresh: true, close_ts: now + 300, time: now, btc: 100000 },
  quote: { ticker: 'BTC-1', source: 'KALSHI_PUBLIC_BOOK', fresh: true, valid_until: now + 2, ...book,
    last_verified: { ticker: 'BTC-1', verified_at: now, ...book } },
  positions,
});

function assertNoDisplay(view) {
  assert.deepEqual(view.displayQuotes, emptyQuotes);
  assert.equal(view.displayQuoteStatus, 'unavailable');
  assert.equal(view.displayQuoteObservedAt, null);
}

function assertNoLiveValuation(view, at) {
  assert.deepEqual(view.quotes, emptyQuotes);
  assert.equal(view.canPractice, false);
  assert.equal(view.practiceMode, 'unavailable');
  if (view.position) assert.equal(view.position.currentBid, null);
  assert.deepEqual(accountMarks(account, { BTC: view }, at), {});
}

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

test('live, delayed, offline and recovered quotes keep display and execution separate', () => {
  const native = packet([{ ticker: 'BTC-1', side: 'YES', qty: 10, entry_ask: .2, mark_valid: true }]);
  const original = structuredClone(native);
  const live = adaptNativeSnapshot(native, 'BTC', { state: 'live', now });
  assert.deepEqual(live.displayQuotes, expectedQuotes);
  assert.equal(live.displayQuoteStatus, 'live');
  assert.equal(live.displayQuoteObservedAt, now);
  assert.deepEqual(accountMarks(account, { BTC: live }, now), { 'practice-1': { bid: .19, fee: 0 } });

  const delayed = adaptNativeSnapshot(native, 'BTC', { state: 'live', now: now + 3 });
  assert.deepEqual(delayed.displayQuotes, expectedQuotes);
  assert.equal(delayed.displayQuoteStatus, 'delayed');
  assert.equal(delayed.displayQuoteObservedAt, now);
  assertNoLiveValuation(delayed, now + 3);
  // A cached live view also loses mark eligibility at its original deadline.
  assert.deepEqual(accountMarks(account, { BTC: live }, now + 3), {});

  const offline = adaptNativeSnapshot(native, 'BTC', {
    state: 'offline', receivedAt: new Date((now + 4) * 1000).toISOString(), now: now + 4,
  });
  assert.deepEqual(offline.displayQuotes, expectedQuotes);
  assert.equal(offline.displayQuoteStatus, 'offline');
  assert.equal(offline.displayQuoteObservedAt, now);
  assertNoLiveValuation(offline, now + 4);
  assert.deepEqual(native, original, 'adapting delayed/offline views must not rewrite the native observation');

  const recovered = structuredClone(native);
  const newerBook = { yes_bid: .25, yes_ask: .26, no_bid: .73, no_ask: .74 };
  recovered.quote = { ...recovered.quote, ...newerBook, valid_until: now + 6,
    last_verified: { ticker: 'BTC-1', verified_at: now + 4, ...newerBook } };
  const fresh = adaptNativeSnapshot(recovered, 'BTC', { state: 'live', now: now + 4 });
  assert.equal(fresh.displayQuoteStatus, 'live');
  assert.equal(fresh.displayQuoteObservedAt, now + 4);
  assert.deepEqual(fresh.displayQuotes, { yes: { bid: .25, ask: .26 }, no: { bid: .73, ask: .74 } });
  assert.equal(fresh.canPractice, true);
  assert.equal(fresh.position.currentBid, .25);
  assert.deepEqual(accountMarks(account, { BTC: fresh }, now + 4), { 'practice-1': { bid: .25, fee: 0 } });
});

test('a quiet native price feed and an expired native book retain only explicitly verified display values', () => {
  for (const cause of ['market', 'book']) {
    const native = packet();
    if (cause === 'market') {
      native.run.fresh = false;
      native.market.fresh = false;
    } else {
      native.quote.fresh = false;
      for (const key of Object.keys(book)) native.quote[key] = null;
    }
    const view = adaptNativeSnapshot(native, 'BTC', { state: 'live', now: now + 1 });
    assert.deepEqual(view.displayQuotes, expectedQuotes, cause);
    assert.equal(view.displayQuoteStatus, 'delayed', cause);
    assertNoLiveValuation(view, now + 1);
  }
});

test('display prices and observation time come from one record on both sides of expiry', () => {
  for (const recordedBid of [.79, undefined]) {
    const native = packet();
    native.quote.no_bid = .75;
    native.quote.last_verified.no_bid = recordedBid;
    const live = adaptNativeSnapshot(native, 'BTC', { state: 'live', now });
    const delayed = adaptNativeSnapshot(native, 'BTC', { state: 'live', now: now + 3 });
    assert.equal(live.quotes.no.bid, .75, 'the existing executable quote source is unchanged');
    assert.equal(live.displayQuotes.no.bid, recordedBid ?? null);
    assert.deepEqual(live.displayQuotes, delayed.displayQuotes, 'expiry cannot swap in a different book');
    assert.equal(live.displayQuoteObservedAt, now);
    assert.equal(delayed.displayQuoteObservedAt, now);
    assertNoLiveValuation(delayed, now + 3);
  }
});

test('retained display requires explicit matching market, quote and verified-book identities', () => {
  const invalid = [
    ['missing verified book', native => { delete native.quote.last_verified; }],
    ['missing market ticker', native => { delete native.market.ticker; }],
    ['blank market ticker', native => { native.market.ticker = ' '; }],
    ['wrong quote ticker', native => { native.quote.ticker = 'BTC-OLD'; }],
    ['missing quote ticker', native => { delete native.quote.ticker; }],
    ['wrong verified ticker', native => { native.quote.last_verified.ticker = 'BTC-OLD'; }],
    ['missing verified ticker', native => { delete native.quote.last_verified.ticker; }],
    ['unverified source', native => { native.quote.source = 'OTHER_SOURCE'; }],
  ];
  for (const [reason, alter] of invalid) {
    const native = packet(); alter(native);
    const view = adaptNativeSnapshot(native, 'BTC', { state: 'stale', now: now + 3 });
    assertNoDisplay(view);
    assertNoLiveValuation(view, now + 3);
    assert.equal(view.native, native, reason);
  }
  assertNoDisplay(adaptNativeSnapshot(null, 'BTC', { now }));
  assert.throws(() => adaptNativeSnapshot(packet(), 'ETH', { state: 'live', now }), /asset does not match/);
});

test('rollover clears the old book until a verified observation for the new contract arrives', () => {
  const native = packet();
  native.market.ticker = 'BTC-2';
  native.market.close_ts = now + 600;
  native.quote.ticker = 'BTC-2';
  // Native current fields can still be populated: they are not a delayed fallback.
  assertNoDisplay(adaptNativeSnapshot(native, 'BTC', { state: 'stale', now: now + 3 }));
  native.quote.last_verified = { ...native.quote.last_verified, ticker: 'BTC-2', verified_at: now + 3 };
  const view = adaptNativeSnapshot(native, 'BTC', { state: 'stale', now: now + 3 });
  assert.deepEqual(view.displayQuotes, expectedQuotes);
  assert.equal(view.displayQuoteStatus, 'delayed');
  assertNoLiveValuation(view, now + 3);
});

test('ordinary display clears exactly at contract close and stays cleared offline', () => {
  const native = packet();
  for (const state of ['live', 'stale', 'offline']) {
    const before = adaptNativeSnapshot(native, 'BTC', { state, now: now + 299.999 });
    assert.deepEqual(before.displayQuotes, expectedQuotes);
    for (const at of [now + 300, now + 301]) {
      const expired = adaptNativeSnapshot(native, 'BTC', { state, now: at });
      assertNoDisplay(expired);
      assertNoLiveValuation(expired, at);
    }
  }
});

test('missing, nonnumeric, impossible or excessive future observation times are not displayed', () => {
  for (const observed of [undefined, null, String(now), NaN, Infinity, -Infinity, 0, -1, 1e100, now + 2.001]) {
    const native = packet();
    native.quote.last_verified.verified_at = observed;
    const view = adaptNativeSnapshot(native, 'BTC', { state: 'stale', now });
    assertNoDisplay(view);
    assertNoLiveValuation(view, now);
  }
  const skewed = packet();
  skewed.quote.last_verified.verified_at = now + 2;
  const allowed = adaptNativeSnapshot(skewed, 'BTC', { state: 'stale', now });
  assert.deepEqual(allowed.displayQuotes, expectedQuotes);
  assert.equal(allowed.displayQuoteObservedAt, now + 2);
  assertNoLiveValuation(allowed, now);
});

test('retained quotes reject invalid prices and crossed books as one observation', () => {
  const invalid = [
    { yes_bid: -.01 }, { yes_ask: 1.01 }, { no_bid: '0.79' }, { no_ask: false },
    { yes_bid: NaN }, { yes_ask: Infinity }, { no_bid: -Infinity },
    { yes_bid: .21, yes_ask: .2 }, { no_bid: .81, no_ask: .8 },
  ];
  for (const values of invalid) {
    const native = packet();
    Object.assign(native.quote.last_verified, values);
    const view = adaptNativeSnapshot(native, 'BTC', { state: 'offline', now: now + 3 });
    assertNoDisplay(view);
    assertNoLiveValuation(view, now + 3);
  }
});

test('partial verified books preserve zero and one without inventing missing prices', () => {
  const native = packet();
  native.quote.last_verified = { ticker: 'BTC-1', verified_at: now, yes_bid: 0, no_ask: 1 };
  const view = adaptNativeSnapshot(native, 'BTC', { state: 'stale', now: now + 3 });
  assert.deepEqual(view.displayQuotes, { yes: { bid: 0, ask: null }, no: { bid: null, ask: 1 } });
  assert.equal(view.displayQuoteStatus, 'delayed');
  assertNoLiveValuation(view, now + 3);
  native.quote.last_verified = { ticker: 'BTC-1', verified_at: now, yes_bid: null, no_ask: null };
  assertNoDisplay(adaptNativeSnapshot(native, 'BTC', { state: 'stale', now: now + 3 }));
});

test('review can display a closed recorded book but only explicit replay keeps replay practice behavior', () => {
  const native = packet();
  native.run.review = true;
  const review = adaptNativeSnapshot(native, 'BTC', { state: 'offline', now: now + 600 });
  assert.equal(review.mode, 'replay');
  assert.equal(review.displayQuoteStatus, 'recorded');
  assert.equal(review.displayQuoteObservedAt, now);
  assert.deepEqual(review.displayQuotes, expectedQuotes);
  assert.equal(review.canPractice, false);
  assert.equal(review.practiceMode, 'unavailable');
  assert.deepEqual(accountMarks(account, { BTC: review }, now + 600), {});

  native.run.review = false;
  const replay = adaptNativeSnapshot(native, 'BTC', { mode: 'replay', now: now + 600 });
  assert.equal(replay.displayQuoteStatus, 'recorded');
  assert.deepEqual(replay.displayQuotes, expectedQuotes);
  assert.equal(replay.canPractice, true);
  assert.equal(replay.practiceMode, 'replay');
  assert.deepEqual(accountMarks(account, { BTC: replay }, now + 600), { 'practice-1': { bid: .19, fee: 0 } });

  for (const observed of [now + 300, now + 301]) {
    native.quote.last_verified.verified_at = observed;
    assertNoDisplay(adaptNativeSnapshot(native, 'BTC', { mode: 'replay', now: now + 600 }));
  }
});

test('stopped feeds keep same-contract display offline without enabling practice', () => {
  const native = packet();
  native.run.stopped = true;
  const view = adaptNativeSnapshot(native, 'BTC', { state: 'live', now });
  assert.equal(view.mode, 'offline');
  assert.equal(view.displayQuoteStatus, 'offline');
  assert.deepEqual(view.displayQuotes, expectedQuotes);
  assertNoLiveValuation(view, now);
});
