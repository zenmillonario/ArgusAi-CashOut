import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';
import { retireLegacyServiceWorker } from './legacyWorkerMigration.mjs';

const origin = 'https://cashoutai.app';
const legacy = `${origin}/sw.js`;
const firebase = `${origin}/firebase-messaging-sw.js`;

function registration(scriptURL = legacy, extra = {}) {
  const calls = [];
  return {
    scope: `${origin}/`, active: { scriptURL }, installing: null, waiting: null,
    update: async () => { calls.push('update'); },
    unregister: async () => { calls.push('unregister'); return true; },
    calls, ...extra,
  };
}

async function migrate(registrations, changes = {}) {
  const deleted = [];
  const result = await retireLegacyServiceWorker({ origin,
    serviceWorker: { getRegistrations: async () => registrations },
    cacheStorage: { delete: async name => { deleted.push(name); return true; } },
    ...changes,
  });
  return { result, deleted };
}

test('migration retires only the exact root legacy worker and its cache', async () => {
  const old = registration();
  const push = registration(firebase);
  const { result, deleted } = await migrate([old, push]);
  assert.deepEqual(result, { matched: 1, unregistered: 1 });
  assert.deepEqual(old.calls, ['update', 'unregister']);
  assert.deepEqual(push.calls, []);
  assert.deepEqual(deleted, ['cashoutai-v1']);
});

test('lookalike URLs, other origins/scopes and mixed Firebase updates are untouched', async () => {
  const others = [
    registration('https://other.example/sw.js'),
    registration(`${legacy}?version=old`),
    registration(`${origin}/nested/sw.js`),
    registration(legacy, { scope: `${origin}/nested/` }),
    registration(legacy, { installing: { scriptURL: firebase } }),
    registration(legacy, { waiting: { scriptURL: firebase } }),
    registration(firebase, { installing: { scriptURL: legacy } }),
    registration(legacy, { active: null }),
  ];
  assert.deepEqual(await migrate(others), { result: { matched: 0, unregistered: 0 }, deleted: [] });
  for (const other of others) assert.deepEqual(other.calls, []);
});

test('offline update failure still retires the known old registration', async () => {
  const old = registration(legacy, { update: async () => { throw new Error('offline'); } });
  assert.deepEqual((await migrate([old])).result, { matched: 1, unregistered: 1 });
  assert.deepEqual(old.calls, ['unregister']);
});

test('a Firebase installation that begins during update is preserved', async () => {
  const old = registration();
  old.update = async () => { old.installing = { scriptURL: firebase }; };
  assert.deepEqual(await migrate([old]), { result: { matched: 1, unregistered: 0 }, deleted: [] });
  assert.deepEqual(old.calls, []);
});

test('a Firebase installation that begins during cache deletion is preserved', async () => {
  const old = registration();
  const deleted = [];
  const { result } = await migrate([old], { cacheStorage: { delete: async name => {
    deleted.push(name); old.installing = { scriptURL: firebase }; return true;
  } } });
  assert.deepEqual(result, { matched: 1, unregistered: 0 });
  assert.deepEqual(deleted, ['cashoutai-v1']);
  assert.deepEqual(old.calls, ['update']);
});

test('unavailable browser APIs and storage errors do not interrupt startup', async () => {
  assert.deepEqual(await retireLegacyServiceWorker({ serviceWorker: null, origin }), { matched: 0, unregistered: 0 });
  assert.deepEqual(await retireLegacyServiceWorker({ origin, serviceWorker: {
    getRegistrations: async () => { throw new Error('blocked'); },
  } }), { matched: 0, unregistered: 0 });
  const old = registration();
  assert.equal((await migrate([old], { cacheStorage: { delete: async () => { throw new Error('blocked'); } } })).result.unregistered, 1);
  const failed = registration(legacy, { unregister: async () => { throw new Error('unavailable'); } });
  assert.equal((await migrate([failed])).result.unregistered, 0);
});

async function retirementHarness() {
  const listeners = new Map();
  const deleted = [];
  let skipped = 0, unregistered = 0;
  const own = registration(legacy, { unregister: async () => { unregistered += 1; return true; } });
  const context = vm.createContext({ URL, Promise,
    caches: { delete: async name => { deleted.push(name); return true; } },
    self: { location: { origin, href: legacy }, registration: own,
      skipWaiting: async () => { skipped += 1; },
      addEventListener: (name, handler) => listeners.set(name, handler),
    },
  });
  vm.runInContext(await readFile(new URL('../public/sw.js', import.meta.url), 'utf8'), context);
  const dispatch = async name => {
    let task;
    listeners.get(name)({ waitUntil: value => { task = value; } });
    await task;
  };
  return { listeners, deleted, own, context, dispatch,
    counts: () => ({ skipped, unregistered }),
  };
}

test('retirement worker has no fetch/push handler and removes only its own cache/registration', async () => {
  const worker = await retirementHarness();
  assert.deepEqual([...worker.listeners.keys()], ['install', 'activate']);
  await worker.dispatch('install');
  await worker.dispatch('activate');
  assert.deepEqual(worker.deleted, ['cashoutai-v1']);
  assert.deepEqual(worker.counts(), { skipped: 1, unregistered: 1 });
  // No clients/navigation or browser-storage APIs exist in this harness: the
  // real retirement code would fail here if it tried to use any of them.
});

test('retirement installation cannot replace a Firebase worker on the same scope', async () => {
  const worker = await retirementHarness();
  worker.own.active = { scriptURL: firebase };
  await assert.rejects(worker.dispatch('install'), /does not own this registration/);
  assert.deepEqual(worker.counts(), { skipped: 0, unregistered: 0 });
  assert.deepEqual(worker.deleted, []);
});

test('retirement activation preserves a newly installing Firebase worker', async () => {
  const worker = await retirementHarness();
  await worker.dispatch('install');
  worker.context.caches.delete = async name => {
    worker.deleted.push(name);
    worker.own.installing = { scriptURL: firebase };
    return true;
  };
  await worker.dispatch('activate');
  assert.deepEqual(worker.deleted, ['cashoutai-v1']);
  assert.deepEqual(worker.counts(), { skipped: 1, unregistered: 0 });
});

test('retirement still unregisters itself if cache deletion is unavailable', async () => {
  const worker = await retirementHarness();
  worker.context.caches.delete = async () => { throw new Error('blocked'); };
  await worker.dispatch('activate');
  assert.deepEqual(worker.counts(), { skipped: 0, unregistered: 1 });
});
