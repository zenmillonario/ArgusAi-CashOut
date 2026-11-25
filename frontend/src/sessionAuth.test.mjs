import test from 'node:test';
import assert from 'node:assert/strict';
import {
  sameSession,
  sessionHeaders,
  removeStoredSession,
  closeSessionTransport,
} from './sessionAuth.mjs';

const firstLogin = Object.freeze({ id: 'member-1', active_session_id: 'session-1' });
const laterLogin = Object.freeze({ id: 'member-1', active_session_id: 'session-2' });

function memoryStorage(initialValue) {
  let value = initialValue;
  const removed = [];
  return {
    getItem(key) {
      assert.equal(key, 'cashoutai_user');
      return value;
    },
    setItem(key, nextValue) {
      assert.equal(key, 'cashoutai_user');
      value = nextValue;
    },
    removeItem(key) {
      assert.equal(key, 'cashoutai_user');
      removed.push(key);
      value = null;
    },
    get removed() { return removed; },
  };
}

test('session equality requires both the account and the exact login token', () => {
  assert.equal(sameSession(firstLogin, { ...firstLogin, screen_name: 'Updated profile' }), true);
  assert.equal(sameSession(firstLogin, laterLogin), false);
  assert.equal(sameSession(firstLogin, { id: 'member-2', active_session_id: 'session-1' }), false);
  for (const incomplete of [undefined, null, {}, { id: 'member-1' }, { active_session_id: 'session-1' }, { id: 'member-1', active_session_id: '' }]) {
    assert.equal(sameSession(incomplete, incomplete), false);
    assert.equal(sameSession(firstLogin, incomplete), false);
  }
});

test('request headers contain the captured credentials and no profile or password fields', () => {
  const session = Object.freeze({ ...firstLogin, password: 'unused-example', is_admin: true });
  const headers = sessionHeaders(session);
  assert.deepEqual(headers, { 'X-User-ID': 'member-1', 'X-Session-ID': 'session-1' });
  headers['X-Session-ID'] = 'changed-locally';
  assert.equal(session.active_session_id, 'session-1');
  assert.deepEqual(sessionHeaders(laterLogin), { 'X-User-ID': 'member-1', 'X-Session-ID': 'session-2' });
  assert.deepEqual(sessionHeaders(null), {});
  assert.deepEqual(sessionHeaders({ id: 'member-1' }), {});
});

test('matching-session cleanup removes only the saved login and is safe to repeat', () => {
  const storage = memoryStorage(JSON.stringify({ ...firstLogin, rememberMe: true }));
  assert.equal(removeStoredSession(storage, firstLogin), true);
  assert.equal(storage.getItem('cashoutai_user'), null);
  assert.equal(removeStoredSession(storage, firstLogin), false);
  assert.deepEqual(storage.removed, ['cashoutai_user']);
});

test('a delayed cleanup from the preceding login preserves the newer same-account login', async () => {
  const storage = memoryStorage(JSON.stringify(firstLogin));
  let finishOldRequest;
  const oldRequest = new Promise(resolve => { finishOldRequest = resolve; });
  const completion = oldRequest.then(() => removeStoredSession(storage, firstLogin));
  storage.setItem('cashoutai_user', JSON.stringify(laterLogin));
  finishOldRequest();
  assert.equal(await completion, false);
  assert.deepEqual(JSON.parse(storage.getItem('cashoutai_user')), laterLogin);
  assert.deepEqual(storage.removed, []);
});

test('cleanup cannot remove another account even when its token string is identical', () => {
  const saved = { id: 'member-2', active_session_id: 'session-1' };
  const storage = memoryStorage(JSON.stringify(saved));
  assert.equal(removeStoredSession(storage, firstLogin), false);
  assert.deepEqual(JSON.parse(storage.getItem('cashoutai_user')), saved);
  assert.deepEqual(storage.removed, []);
});

test('unreadable or blocked storage does not turn cleanup into a broad deletion', () => {
  for (const saved of [null, '', '{invalid-json', 'null', '{}']) {
    const storage = memoryStorage(saved);
    assert.equal(removeStoredSession(storage, firstLogin), false);
    assert.deepEqual(storage.removed, []);
  }
  assert.equal(removeStoredSession({ getItem() { throw new Error('Storage unavailable'); } }, firstLogin), false);
  assert.equal(removeStoredSession({
    getItem() { return JSON.stringify(firstLogin); },
    removeItem() { throw new Error('Storage is blocked'); },
  }, firstLogin), false);
});

test('socket callbacks are detached before close can synchronously emit an old event', () => {
  let oldCallbackCalls = 0;
  let closed = 0;
  const oldCallback = () => { oldCallbackCalls += 1; };
  const socket = {
    onopen: oldCallback,
    onmessage: oldCallback,
    onerror: oldCallback,
    onclose: oldCallback,
    close() {
      closed += 1;
      this.onclose?.({ code: 1000 });
      assert.equal(this.onopen, null);
      assert.equal(this.onmessage, null);
      assert.equal(this.onerror, null);
    },
  };
  closeSessionTransport(socket);
  assert.equal(closed, 1);
  assert.equal(oldCallbackCalls, 0);
  assert.equal(socket.onclose, null);
});

test('polling cleanup clears its own two timers, including a valid zero timer ID', () => {
  const timers = [];
  const otherTransport = { type: 'polling', sessionInterval: 4, messageInterval: 5 };
  closeSessionTransport({ type: 'polling', sessionInterval: 0, messageInterval: 3 }, timer => timers.push(timer));
  assert.deepEqual(timers, [0, 3]);
  assert.deepEqual(otherTransport, { type: 'polling', sessionInterval: 4, messageInterval: 5 });
  assert.doesNotThrow(() => closeSessionTransport(null));
  assert.doesNotThrow(() => closeSessionTransport(undefined));
});
