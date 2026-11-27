import test from 'node:test';
import assert from 'node:assert/strict';
import { recordAppOpen } from './trafficModel.mjs';

test('only normal top-level app opens send a privacy-limited request', async () => {
  const calls = [];
  const send = async (...args) => { calls.push(args); return {ok: true}; };
  const window = { __CASHOUTAI_PRIVATE_LANDING__: false };
  window.self = window.top = window;
  assert.equal(await recordAppOpen(window, send, 'https://backend.example.test/'), true);
  assert.deepEqual(calls[0], ['https://backend.example.test/api/traffic/open', {
    method:'POST', credentials:'omit', referrerPolicy:'no-referrer', keepalive:true,
  }]);
  window.__CASHOUTAI_PRIVATE_LANDING__ = true;
  assert.equal(await recordAppOpen(window, send), false);
  delete window.__CASHOUTAI_PRIVATE_LANDING__;
  assert.equal(await recordAppOpen(window, send), false);
  window.__CASHOUTAI_PRIVATE_LANDING__ = false; window.top = {};
  assert.equal(await recordAppOpen(window, send), false);
  assert.equal(calls.length, 1);
});

test('network failure is nonblocking', async () => {
  const window = { __CASHOUTAI_PRIVATE_LANDING__: false };
  window.self = window.top = window;
  assert.equal(await recordAppOpen(window, async () => { throw Error('offline'); }), false);
});
