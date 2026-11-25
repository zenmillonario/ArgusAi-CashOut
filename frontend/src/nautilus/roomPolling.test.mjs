import test from 'node:test';
import assert from 'node:assert/strict';
import { preferNewerPracticeLedger, roomAssetsToPoll, startVisiblePolling } from './roomPolling.mjs';

const flush = async () => { await Promise.resolve(); await Promise.resolve(); };
function environment(initial = 'visible') {
  const listeners = new Set();
  const timers = new Map();
  let next = 0;
  const visibility = {
    visibilityState: initial,
    addEventListener: (_, listener) => listeners.add(listener),
    removeEventListener: (_, listener) => listeners.delete(listener),
  };
  return {
    visibility, timers, listeners,
    setTimer: (callback, delay) => { const id = ++next; timers.set(id, { callback, delay }); return id; },
    clearTimer: id => timers.delete(id),
    change(state) { visibility.visibilityState = state; for (const listener of listeners) listener(); },
    tick() { const [id, timer] = timers.entries().next().value; timers.delete(id); timer.callback(); },
  };
}

test('only active and held bot assets need snapshots', () => {
  const supported = ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE'];
  assert.deepEqual(roomAssetsToPoll('BTC', undefined, supported), ['BTC']);
  assert.deepEqual(roomAssetsToPoll('ETH', [
    { asset: 'BTC', quantity: 5 }, { asset: 'ETH', quantity: 10 },
    { asset: 'BTC', quantity: 2 }, { asset: 'DOGE', quantity: 0 },
    { asset: 'UNSUPPORTED', quantity: 5 },
  ], supported), ['ETH', 'BTC']);
});

test('late account polls cannot undo a trade, settlement, or reset', () => {
  const before = { revision: 3, account: { attemptId: 'attempt-1', cashUnits: 75000000 } };
  const settled = { revision: 4, account: { attemptId: 'attempt-1', cashUnits: 125000000 } };
  const reset = { revision: 5, account: { attemptId: 'attempt-2', cashUnits: 100000000 } };
  assert.equal(preferNewerPracticeLedger(null, before), before);
  assert.equal(preferNewerPracticeLedger(before, settled), settled);
  assert.equal(preferNewerPracticeLedger(settled, before), settled);
  assert.equal(preferNewerPracticeLedger(reset, settled), reset);
  assert.equal(preferNewerPracticeLedger(reset, { revision: '6', account: {} }), reset);
});

test('hidden room uses no network polling and resumes immediately when shown', async () => {
  const env = environment('hidden');
  let calls = 0;
  const stop = startVisiblePolling(async () => { calls++; }, 3000, env);
  assert.equal(calls, 0);
  assert.equal(env.timers.size, 0);
  env.change('visible');
  assert.equal(calls, 1);
  await flush();
  assert.equal([...env.timers.values()][0].delay, 3000);
  env.change('hidden');
  assert.equal(env.timers.size, 0);
  env.change('visible');
  assert.equal(calls, 2);
  stop();
  await flush();
  assert.equal(env.timers.size, 0);
  assert.equal(env.listeners.size, 0);
});

test('rapid app switching aborts the old request without overlapping its replacement', async () => {
  const env = environment();
  const signals = [];
  let finish;
  const stop = startVisiblePolling(signal => {
    signals.push(signal);
    return new Promise(resolve => { finish = resolve; });
  }, 3000, env);
  assert.equal(signals.length, 1);
  env.change('hidden');
  assert.equal(signals[0].aborted, true);
  env.change('visible');
  assert.equal(signals.length, 1, 'the aborted operation must settle before its replacement starts');
  finish();
  await flush();
  assert.equal([...env.timers.values()][0].delay, 0);
  env.tick();
  assert.equal(signals.length, 2);
  stop();
  assert.equal(signals[1].aborted, true);
  finish();
  await flush();
  assert.equal(env.timers.size, 0);
});

test('an ordinary network failure retries only on the configured interval', async () => {
  const env = environment();
  const errors = [];
  let calls = 0;
  const stop = startVisiblePolling(async () => { calls++; throw new Error('offline'); }, 5000,
    { ...env, onError: error => errors.push(error.message) });
  await flush();
  assert.equal(calls, 1);
  assert.deepEqual(errors, ['offline']);
  assert.equal([...env.timers.values()][0].delay, 5000);
  env.tick();
  await flush();
  assert.equal(calls, 2);
  stop();
});
