import test from 'node:test';
import assert from 'node:assert/strict';
import { deriveContractClock } from './contractClock.mjs';

const now = Date.parse('2026-11-27T08:00:00Z');
const room = (mode = 'live') => ({
  mode,
  contract: { id: 'BTC-0800', closeTime: new Date(now + 300000).toISOString() },
  native: { run: { stopped: false, review: false } },
});

test('quote freshness changes do not replace the running contract countdown', () => {
  for (const mode of ['live', 'stale', 'offline', 'live']) {
    const clock = deriveContractClock(room(mode), now + 11000);
    assert.equal(clock.kind, 'countdown');
    assert.equal(clock.remainingSeconds, 289);
    assert.equal(clock.ended, false);
  }
});

test('a delayed snapshot keeps counting without receiving a new packet', () => {
  const snapshot = room('stale');
  assert.equal(deriveContractClock(snapshot, now + 1000).remainingSeconds, 299);
  assert.equal(deriveContractClock(snapshot, now + 31000).remainingSeconds, 269);
});

test('expiry stops at zero and never starts an inferred next contract', () => {
  for (const elapsed of [300000, 300001, 1200000]) {
    const clock = deriveContractClock(room('offline'), now + elapsed);
    assert.equal(clock.remainingSeconds, 0);
    assert.equal(clock.ended, true);
    assert.equal(clock.closeTime, now + 300000);
  }
});

test('only an explicitly received replacement contract starts another countdown', () => {
  const previous = room('stale');
  const next = { ...room(), contract: { id: 'BTC-0815', closeTime: new Date(now + 1200000).toISOString() } };
  assert.equal(deriveContractClock(previous, now + 301000).remainingSeconds, 0);
  assert.equal(deriveContractClock(next, now + 301000).remainingSeconds, 899);
});

test('replay, demo, stopped and review snapshots retain recorded time', () => {
  const cases = [room('replay'), room('demo'), room(), room()];
  cases[2].native.run.stopped = true;
  cases[3].native.run.review = true;
  for (const snapshot of cases) {
    snapshot.contract.remainingSeconds = 42;
    const first = deriveContractClock(snapshot, now);
    const later = deriveContractClock(snapshot, now + 700000);
    assert.equal(first.kind, 'recorded');
    assert.equal(first.remainingSeconds, 42);
    assert.deepEqual(first, later);
    assert.equal(later.ended, false);
  }
});

test('recorded packets without a saved countdown retain their closing time', () => {
  const clock = deriveContractClock(room('replay'), now + 700000);
  assert.equal(clock.kind, 'recorded');
  assert.equal(clock.remainingSeconds, null);
  assert.equal(clock.closeTime, now + 300000);
});

test('missing or ambiguous timestamps do not produce a fabricated countdown', () => {
  for (const value of [null, undefined, '', ' ', 'tomorrow', '2026-11-27', '2026-11-27T08:05:00', 0, -1, Infinity, NaN]) {
    const snapshot = room();
    snapshot.contract.closeTime = value;
    const clock = deriveContractClock(snapshot, now);
    assert.equal(clock.kind, 'unavailable', String(value));
    assert.equal(clock.remainingSeconds, null);
  }
  const snapshot = room();
  snapshot.contract.id = null;
  assert.equal(deriveContractClock(snapshot, now).kind, 'unavailable');
});

test('explicit ISO offsets and numeric seconds/milliseconds identify the same close', () => {
  for (const closeTime of ['2026-11-27T03:05:00-05:00', (now + 300000) / 1000, now + 300000]) {
    const snapshot = room();
    snapshot.contract.closeTime = closeTime;
    assert.equal(deriveContractClock(snapshot, now + 1000).remainingSeconds, 299);
  }
});

test('unknown run state cannot imply a live countdown', () => {
  const snapshot = room();
  snapshot.native = null;
  assert.equal(deriveContractClock(snapshot, now).kind, 'recorded');
  assert.equal(deriveContractClock(snapshot, now).remainingSeconds, null);
});
