import test from 'node:test';
import assert from 'node:assert/strict';
import {
  BILLING_STORAGE_KEY, MEMBERSHIP_PLANS, membershipPlan, moneyFromCents,
  signupPlanIntent, billingReturnIntent, normalizeBillingProof, readBillingProof,
  saveBillingProof, clearBillingProof, memberBillingCredential, sameBillingCredential,
  billingHeaders, responseBelongsToSession, safeSquareCheckoutUrl, normalizePlansResponse,
  loadBillingState, createMemberCheckout, checkoutAttemptKey, retireFulfilledAttempts,
} from './billingModel.mjs';

const memberA = memberBillingCredential({ id: 'member-a', active_session_id: 'session-a' });
const memberB = memberBillingCredential({ id: 'member-b', active_session_id: 'session-b' });
const proof = (id = 'pending-a', token = 'token-aaaaaaaaaaaaaaaaaaaa') => normalizeBillingProof({ user_id: id, billing_token: token, expires_at: '2100-01-01T00:00:00Z', scope: 'billing' }, id);
const publicPlans = (extra = {}) => ({ plans: MEMBERSHIP_PLANS.map(plan => ({ ...plan })), recurring: false,
  environment: 'production', automatic_checkout_available: true, automatic_activation_available: true, ...extra });
const memoryStorage = () => {
  const values = new Map();
  return { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
};
const deferred = () => { let resolve; let reject; const promise = new Promise((res, rej) => { resolve = res; reject = rej; }); return { promise, resolve, reject }; };

test('new catalog keeps exact supplied fixed terms without reinterpreting legacy plans', () => {
  assert.deepEqual(MEMBERSHIP_PLANS.map(({ id, registrationLabel, amount_cents, term_months }) => ({ id, registrationLabel, amount_cents, term_months })), [
    { id: 'monthly', registrationLabel: 'Monthly', amount_cents: 9900, term_months: 1 },
    { id: 'six_months', registrationLabel: 'SixMonths', amount_cents: 49900, term_months: 6 },
    { id: 'lifetime', registrationLabel: 'Lifetime', amount_cents: 89900, term_months: null },
  ]);
  assert.equal(membershipPlan('Yearly'), null);
  assert.equal(membershipPlan('Trial'), null);
  assert.equal(moneyFromCents(49900), '$499.00');
  assert.equal(moneyFromCents(-10), 'Not recorded');
  assert.equal(moneyFromCents(10, 'not a currency'), 'Not recorded');
  assert.throws(() => normalizePlansResponse(publicPlans({ plans: MEMBERSHIP_PLANS.map(plan => ({ ...plan, amount_cents: 1 })) })));
  assert.throws(() => normalizePlansResponse(publicPlans({ recurring: true })));
  assert.equal(normalizePlansResponse(publicPlans({ environment: 'sandbox' })).automatic_activation_available, false);
  assert.equal(normalizePlansResponse(publicPlans({ environment: null })).automatic_checkout_available, false);
});

test('marketing and return queries only choose navigation, accepting known plan IDs', () => {
  assert.equal(signupPlanIntent('?join=six_months'), 'six_months');
  for (const search of ['?join=Yearly', '?join=trial', '?join=https://evil.test', '?paid=true']) assert.equal(signupPlanIntent(search), '');
  assert.equal(billingReturnIntent('?billing=1&status=success'), true);
  assert.equal(billingReturnIntent('?paid=1'), false);
  assert.equal(billingReturnIntent('?billing=true'), false);
});

test('billing-only proofs expire and never become member-session headers', () => {
  const value = proof();
  assert.deepEqual(billingHeaders(value), { 'X-Billing-Token': value.billing_token });
  assert.equal(memberBillingCredential(value), null);
  assert.equal(sameBillingCredential(value, memberA), false);
  assert.equal(normalizeBillingProof({ ...value, scope: 'member' }), null);
  assert.equal(normalizeBillingProof({ ...value, expires_at: '2000-01-01T00:00:00Z' }), null);
  assert.throws(() => billingHeaders({ ...value, expires_at: '2000-01-01T00:00:00Z' }));
  assert.throws(() => billingHeaders({ kind: 'member', session: {} }));
  assert.deepEqual(billingHeaders(memberA), { 'X-User-ID': 'member-a', 'X-Session-ID': 'session-a' });
});

test('proof storage clears expired data, and an old account cannot clear a new proof', () => {
  const storage = memoryStorage();
  const first = proof();
  const next = proof('pending-b', 'token-bbbbbbbbbbbbbbbbbbbb');
  assert.equal(saveBillingProof(storage, first), true);
  assert.equal(readBillingProof(storage).user_id, 'pending-a');
  saveBillingProof(storage, next);
  assert.equal(clearBillingProof(storage, first), false);
  assert.equal(readBillingProof(storage).user_id, 'pending-b');
  assert.equal(clearBillingProof(storage, next), true);
  storage.setItem(BILLING_STORAGE_KEY, JSON.stringify({ ...first, expires_at: '2000-01-01T00:00:00Z' }));
  assert.equal(readBillingProof(storage), null);
  assert.equal(storage.getItem(BILLING_STORAGE_KEY), null);
});

test('hosted checkout URLs reject redirects, lookalike hosts, mixed manual flows, and production sandbox URLs', () => {
  assert.equal(safeSquareCheckoutUrl('https://square.link/u/EXAMPLE', { environment: 'production' }), 'https://square.link/u/EXAMPLE');
  assert.equal(safeSquareCheckoutUrl('https://sandbox.square.link/u/EXAMPLE', { environment: 'sandbox' }), 'https://sandbox.square.link/u/EXAMPLE');
  for (const url of ['http://square.link/u/EXAMPLE', 'javascript:alert(1)', 'https://square.link.evil.test/u/EXAMPLE', 'https://square.link@evil.test/u/EXAMPLE',
    'https://evil.test@square.link/u/EXAMPLE', 'https://square.link/u/EXAMPLE?redirect=https://evil.test', 'https://square.link/u/EXAMPLE#next',
    'https://square.link:444/u/EXAMPLE', 'https://square.link/u/%2FEXAMPLE', ' https://square.link/u/EXAMPLE', 'https://sandbox.square.link/u/EXAMPLE',
    MEMBERSHIP_PLANS[0].manual_payment_url]) assert.equal(safeSquareCheckoutUrl(url, { environment: 'production' }), null, url);
  assert.equal(safeSquareCheckoutUrl(MEMBERSHIP_PLANS[0].manual_payment_url, { mode: 'manual', planId: 'monthly' }), MEMBERSHIP_PLANS[0].manual_payment_url);
  assert.equal(safeSquareCheckoutUrl(MEMBERSHIP_PLANS[0].manual_payment_url, { mode: 'manual', planId: 'six_months' }), null);
});

test('membership history rejects a server response for another account', async () => {
  const client = { get: async url => ({ data: url.endsWith('/plans') ? publicPlans() : { user_id: 'member-b', entitlement: { active: true } } }) };
  await assert.rejects(loadBillingState({ client, api: '/api', credential: memberA, currentCredential: () => memberA }), /did not match/);
});

test('a late history response cannot populate a replacement account or an unmounted panel', async () => {
  for (const replacement of [memberB, null]) {
    const pending = deferred();
    let current = memberA;
    const client = { get: url => url.endsWith('/plans') ? Promise.resolve({ data: publicPlans() }) : pending.promise };
    const loading = loadBillingState({ client, api: '/api', credential: memberA, currentCredential: () => current });
    current = replacement;
    pending.resolve({ data: { user_id: 'member-a', payments: [{ payment_id: 'old-private-record' }] } });
    assert.equal(await loading, null);
  }
});

test('billing state keeps authoritative inactive entitlement even with completed-looking payment records', async () => {
  const captured = [];
  const pendingProof = proof();
  const client = { get: async (url, config) => {
    captured.push([url, config]);
    return { data: url.endsWith('/plans') ? publicPlans({ environment: 'sandbox' }) : {
      user_id: pendingProof.user_id, entitlement: { active: false, source: 'none' }, payments: [{ status: 'sandbox_verified', environment: 'sandbox' }], checkouts: []
    } };
  } };
  const value = await loadBillingState({ client, api: '/api', credential: pendingProof, currentCredential: () => pendingProof });
  assert.equal(value.status.entitlement.active, false);
  assert.equal(value.plans.automatic_activation_available, false);
  assert.deepEqual(captured[1][1].headers, { 'X-Billing-Token': pendingProof.billing_token });
});

test('checkout creation sends only a canonical plan and reusable attempt key with captured auth', async () => {
  const sent = [];
  const credential = proof();
  const client = { post: async (...args) => { sent.push(args); return { data: { checkout_id: 'checkout-a', plan_id: 'six_months', status: 'ready', checkout_url: 'https://square.link/u/EXAMPLE' } }; } };
  const args = { client, api: '/api', credential, currentCredential: () => credential, planId: 'six_months', idempotencyKey: 'test-attempt-12345678', environment: 'production' };
  assert.equal((await createMemberCheckout(args)).checkout_id, 'checkout-a');
  await createMemberCheckout(args);
  assert.deepEqual(sent[0][1], { plan_id: 'six_months', idempotency_key: 'test-attempt-12345678' });
  assert.deepEqual(sent[0][1], sent[1][1]);
  assert.deepEqual(sent[0][2].headers, { 'X-Billing-Token': credential.billing_token });
  await assert.rejects(createMemberCheckout({ ...args, planId: 'Yearly' }));
  await assert.rejects(createMemberCheckout({ ...args, planId: 'SixMonths' }));
});

test('checkout responses are discarded after logout/account change and unsafe URLs never open', async () => {
  const pending = deferred();
  let current = memberA;
  const args = { client: { post: () => pending.promise }, api: '/api', credential: memberA, currentCredential: () => current, planId: 'monthly', idempotencyKey: 'attempt-aaaaaaaaaaaa', environment: 'production' };
  const running = createMemberCheckout(args);
  current = memberB;
  pending.resolve({ data: { plan_id: 'monthly', checkout_id: 'old-private-checkout', status: 'ready', checkout_url: 'https://square.link/u/EXAMPLE' } });
  assert.equal(await running, null);
  assert.equal(await createMemberCheckout(args), null);
  current = memberA;
  await assert.rejects(createMemberCheckout({ ...args, client: { post: async () => ({ data: { plan_id: 'monthly', checkout_id: 'x', status: 'ready', checkout_url: 'https://evil.test/u/EXAMPLE' } }) } }), /unsupported/);
});

test('only matching fulfilled attempts retire; uncertainty and a different environment preserve retries', () => {
  const attempts = new Map([
    [checkoutAttemptKey('monthly', 'production'), { key: 'key-a', checkoutId: 'checkout-a', environment: 'production' }],
    [checkoutAttemptKey('six_months', 'production'), { key: 'key-b', checkoutId: 'checkout-b', environment: 'production' }],
    [checkoutAttemptKey('lifetime', 'sandbox'), { key: 'key-c', checkoutId: 'checkout-c', environment: 'sandbox' }],
  ]);
  retireFulfilledAttempts(attempts, [
    { checkout_id: 'checkout-a', environment: 'production', status: 'fulfilled' },
    { checkout_id: 'checkout-b', environment: 'production', status: 'review' },
    { checkout_id: 'checkout-c', environment: 'production', status: 'fulfilled' },
  ]);
  assert.equal(attempts.has('production:monthly'), false);
  assert.equal(attempts.get('production:six_months').key, 'key-b');
  assert.equal(attempts.get('sandbox:lifetime').key, 'key-c');
});

test('membership gate errors must carry the currently captured member session', () => {
  assert.equal(responseBelongsToSession({ 'x-user-id': 'member-a', 'x-session-id': 'session-a' }, memberA.session), true);
  assert.equal(responseBelongsToSession({ get: name => ({ 'X-User-ID': 'member-a', 'X-Session-ID': 'session-a' }[name]) }, memberA.session), true);
  assert.equal(responseBelongsToSession(billingHeaders(memberA), memberB.session), false);
  assert.equal(responseBelongsToSession({ 'X-Billing-Token': 'private-proof' }, memberA.session), false);
  assert.equal(responseBelongsToSession(billingHeaders(memberA), { id: 'member-a', active_session_id: 'replacement-session' }), false);
});
