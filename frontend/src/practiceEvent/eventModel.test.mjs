import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizePracticeEvent, practiceEventPhase, eventDeadlineLabel, eventMembershipPresentation,
  eventTokenFromLocation, withoutEventToken, requestPracticeEventLink, confirmPracticeEvent, practiceEventError, eventRegistrationPayload } from './eventModel.mjs';

const end = '2026-12-01T05:00:00Z';
const start = '2026-11-25T17:00:00Z';
const config = (changes = {}, receivedAt = Date.parse(start)) => normalizePracticeEvent({
  campaign_id: 'cashoutai-practice-2026', status: 'open', starts_at: start,
  ends_at: end, server_now: start, ...changes,
}, receivedAt);

test('one event deadline applies at the exact boundary, independent of enrollment date', () => {
  const event = config();
  assert.equal(practiceEventPhase(event, Date.parse(start) - 1), 'scheduled');
  assert.equal(practiceEventPhase(event, Date.parse(start)), 'open');
  assert.equal(practiceEventPhase(event, Date.parse(end) - 1), 'open');
  assert.equal(practiceEventPhase(event, Date.parse(end)), 'ended');
  assert.equal(practiceEventPhase(event, Date.parse(end) + 1), 'ended');
});

test('server clock offset controls display and disabled or scheduled responses never open access', () => {
  const local = Date.parse(start) - 86400000;
  const event = config({}, local);
  assert.equal(practiceEventPhase(event, local), 'open');
  assert.equal(practiceEventPhase(event, local + Date.parse(end) - Date.parse(start)), 'ended');
  assert.equal(practiceEventPhase(config({ status: 'disabled' }), Date.parse(start)), 'disabled');
  assert.equal(practiceEventPhase(config({ status: 'scheduled' }), Date.parse(start) + 1), 'scheduled');
  assert.equal(practiceEventPhase(config({ status: 'ended' }), Date.parse(start)), 'ended');
});

test('incomplete or malformed event configuration fails closed', () => {
  for (const changes of [{ campaign_id: '' }, { status: 'unknown' }, { ends_at: 'bad' }, { server_now: null }, { starts_at: 'bad' }]) {
    assert.equal(config(changes), null);
    assert.equal(practiceEventPhase(config(changes)), 'unavailable');
  }
  assert.equal(normalizePracticeEvent(null), null);
});

test('deadline is unambiguous in Eastern regardless of the viewer timezone', () => {
  assert.equal(eventDeadlineLabel(end), 'Monday, November 30, 2026 at 11:59 PM Eastern');
  assert.equal(eventDeadlineLabel('bad'), 'the event deadline');
});

test('paid entitlement takes precedence over an old event record', () => {
  assert.equal(eventMembershipPresentation({ entitlement: { active: true, source: 'manual_payment', lifetime: true }, practice_event: { state: 'ended', ends_at: end } }), null);
  assert.equal(eventMembershipPresentation({ entitlement: { active: true, source: 'legacy' }, practice_event: { state: 'enrolled', ends_at: end } }), null);
  assert.equal(eventMembershipPresentation({ entitlement: { active: false, source: 'manual_payment', paid_through: end }, practice_event: { state: 'ended', ends_at: end } }), null);
  const active = eventMembershipPresentation({ entitlement: { source: 'practice_event', active: true, trial_ends_at: end } });
  assert.equal(active.kind, 'active'); assert.equal(active.endsAt, end);
  const ended = eventMembershipPresentation({ entitlement: { source: 'practice_event', active: false, trial_ends_at: end } });
  assert.equal(ended.kind, 'ended');
});

test('event token is separate from password recovery and removed without losing other deep-link state', () => {
  assert.equal(eventTokenFromLocation({ search: '?event_token=synthetic&reset_token=other' }), 'synthetic');
  assert.equal(eventTokenFromLocation({ search: '?reset_token=other' }), '');
  assert.equal(withoutEventToken('https://app.example.test/?event_token=synthetic&billing=1#membership'), '/?billing=1#membership');
});

test('email request sends only email and the server-provided campaign identifier', async () => {
  const now = new Date().toISOString();
  const event = normalizePracticeEvent({ campaign_id: 'server-campaign', status: 'open', server_now: now,
    starts_at: null, ends_at: new Date(Date.now() + 60000).toISOString() });
  const calls = [];
  const client = { post: async (...args) => { calls.push(args); return { data: { status: 'verification_requested', message: 'Generic response' } }; } };
  await requestPracticeEventLink(client, '/api', ' learner@example.test ', event);
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], '/api/practice-event/request');
  assert.deepEqual(calls[0][1], { email: 'learner@example.test', campaign_id: 'server-campaign' });
  await assert.rejects(() => requestPracticeEventLink(client, '/api', 'learner@example.test', config({ status: 'disabled' })));
  assert.equal(calls.length, 1);
});

test('confirmation requires an explicit token, accepts no implied session, and rejects malformed success', async () => {
  const calls = [];
  const client = { post: async (...args) => { calls.push(args); return { data: { status: 'confirmed', access: 'practice_event', sign_in_required: true, ends_at: end } }; } };
  await assert.rejects(() => confirmPracticeEvent(client, '/api', ''));
  assert.equal(calls.length, 0);
  const response = await confirmPracticeEvent(client, '/api', 'synthetic-token');
  assert.deepEqual(calls[0][1], { token: 'synthetic-token' });
  assert.equal(response.sign_in_required, true);
  assert.equal(response.active_session_id, undefined);
  await assert.rejects(() => confirmPracticeEvent({ post: async () => ({ data: { status: 'ok', active_session_id: 'untrusted' } }) }, '/api', 'synthetic-token'));
});

test('closed, rate-limited, and unavailable email states remain distinguishable', () => {
  assert.match(practiceEventError({ response: { status: 409 } }), /not accepting new access/);
  assert.match(practiceEventError({ response: { status: 429 } }), /wait a little/);
  assert.match(practiceEventError({ response: { status: 503 } }), /temporarily unavailable/);
  assert.equal(practiceEventError({ response: { status: 409, data: { detail: 'Account access changed while confirming. Request a fresh verification link.' } } }), 'Account access changed while confirming. Request a fresh verification link.');
});


test('free event registration uses only the three credentials and server campaign, never a paid plan or real name', () => {
  const live = normalizePracticeEvent({campaign_id: 'cashoutai-practice-2026', status: 'open', starts_at: start, ends_at: end, server_now: start}, Date.now());
  assert.deepEqual(eventRegistrationPayload({username: '  racer  ', password: 'example-password', real_name: 'ignored', membership_plan: 'Lifetime'}, ' racer@example.test ', live), {
    username: 'racer', password: 'example-password', email: 'racer@example.test', real_name: '', membership_plan: 'Practice event', practice_event_id: 'cashoutai-practice-2026',
  });
});

test('the short signup cannot construct event registration when the event is closed or unavailable', () => {
  for (const status of ['disabled', 'scheduled', 'ended']) {
    assert.throws(() => eventRegistrationPayload({username:'racer', password:'example-password'}, 'racer@example.test', config({status})), /not open/);
  }
  assert.throws(() => eventRegistrationPayload({}, '', null), /not open/);
});
