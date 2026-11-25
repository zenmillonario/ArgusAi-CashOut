import { sameSession, sessionHeaders } from '../sessionAuth.mjs';

export const BILLING_STORAGE_KEY = 'cashoutai_billing_session_v1';
export const MEMBERSHIP_PLANS = Object.freeze([
  { id: 'monthly', registrationLabel: 'Monthly', label: '1 month', amount_cents: 9900, currency: 'USD', term_months: 1, manual_payment_url: 'https://checkout.square.site/merchant/VMNWS6K9Y9SN5/checkout/SGEVW3GCMZ2X4WSWREYY2RF2' },
  { id: 'six_months', registrationLabel: 'SixMonths', label: '6 months', amount_cents: 49900, currency: 'USD', term_months: 6, manual_payment_url: 'https://checkout.square.site/merchant/VMNWS6K9Y9SN5/checkout/FEYSOTOHEO6HE6N4ONWO4F7C' },
  { id: 'lifetime', registrationLabel: 'Lifetime', label: 'Lifetime', amount_cents: 89900, currency: 'USD', term_months: null, manual_payment_url: 'https://checkout.square.site/merchant/VMNWS6K9Y9SN5/checkout/7YFX27AOC4IUYZ5DXP4W3VBL' },
]);
export const membershipPlan = value => MEMBERSHIP_PLANS.find(plan => plan.id === value || plan.registrationLabel === value) || null;
export function moneyFromCents(value, currency = 'USD') {
  if (!Number.isSafeInteger(value) || value < 0) return 'Not recorded';
  try { return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(value / 100); }
  catch (_) { return 'Not recorded'; }
}

export function signupPlanIntent(search) {
  const value = new URLSearchParams(search || '').get('join');
  return MEMBERSHIP_PLANS.find(plan => plan.id === value)?.id || '';
}
export const billingReturnIntent = search => new URLSearchParams(search || '').get('billing') === '1';

export function normalizeBillingProof(payload, username = '', now = Date.now()) {
  const expires = Date.parse(payload?.expires_at || '');
  if (payload?.scope !== 'billing' || typeof payload.user_id !== 'string' || !payload.user_id ||
      typeof payload.billing_token !== 'string' || payload.billing_token.length < 20 || payload.billing_token.length > 4096 ||
      !Number.isFinite(expires) || expires <= now) return null;
  return { kind: 'billing', user_id: payload.user_id, billing_token: payload.billing_token,
    expires_at: payload.expires_at, scope: 'billing', username: String(username || payload.username || '').slice(0, 100) };
}

export function readBillingProof(storage, now = Date.now()) {
  try {
    const proof = normalizeBillingProof(JSON.parse(storage.getItem(BILLING_STORAGE_KEY)), '', now);
    if (!proof) storage.removeItem(BILLING_STORAGE_KEY);
    return proof;
  } catch (_) { try { storage.removeItem(BILLING_STORAGE_KEY); } catch (_) {} return null; }
}
export function saveBillingProof(storage, proof) {
  const valid = normalizeBillingProof(proof, proof?.username);
  if (!valid) return false;
  try { storage.setItem(BILLING_STORAGE_KEY, JSON.stringify(valid)); return true; } catch (_) { return false; }
}
export function clearBillingProof(storage, expected) {
  try {
    if (expected) {
      const current = JSON.parse(storage.getItem(BILLING_STORAGE_KEY));
      if (!sameBillingCredential(current, expected)) return false;
    }
    storage.removeItem(BILLING_STORAGE_KEY); return true;
  } catch (_) { return false; }
}
export function memberBillingCredential(session) {
  return session?.id && session?.active_session_id ? { kind: 'member', session: { id: session.id, active_session_id: session.active_session_id } } : null;
}
export function sameBillingCredential(left, right) {
  if (!left || !right || left.kind !== right.kind) return false;
  if (left.kind === 'member') return sameSession(left.session, right.session);
  return left.kind === 'billing' && Boolean(left.user_id && left.billing_token) && left.user_id === right.user_id && left.billing_token === right.billing_token;
}
export function billingHeaders(credential) {
  if (credential?.kind === 'member' && memberBillingCredential(credential.session)) return sessionHeaders(credential.session);
  if (normalizeBillingProof(credential, credential?.username)) return { 'X-Billing-Token': credential.billing_token };
  throw new Error('Sign in again to open your membership payment options.');
}
export function responseBelongsToSession(headers, session) {
  if (!session?.id || !session?.active_session_id || !headers) return false;
  const get = name => typeof headers.get === 'function' ? headers.get(name) : Object.entries(headers).find(([key]) => key.toLowerCase() === name.toLowerCase())?.[1];
  return get('X-User-ID') === session.id && get('X-Session-ID') === session.active_session_id;
}
export function billingError(error) {
  if (error?.response?.status === 401) return 'Your payment session has expired. Sign in again to review your membership.';
  if (error?.response?.status === 503) return 'Account-linked checkout is unavailable. Refresh its status before retrying the same attempt.';
  if (error?.response?.status === 403) return 'This account cannot open that payment view. Sign in with the correct account.';
  return 'The payment information could not be loaded. Refresh to check the current status.';
}

export function checkoutAttemptKey(planId, environment) {
  return `${environment || 'unconfigured'}:${planId}`;
}

// Only an exact, confirmed fulfillment retires an attempt. A timeout, review,
// failed read, or a checkout belonging to another attempt cannot rotate its key.
export function retireFulfilledAttempts(attempts, checkouts) {
  for (const [key, attempt] of attempts) {
    if (attempt.checkoutId && checkouts.some(item => item.checkout_id === attempt.checkoutId &&
        item.status === 'fulfilled' && item.environment === attempt.environment)) attempts.delete(key);
  }
}

// URLs from API responses are not trusted until they pass an exact provider
// allowlist. Manual links and account-linked checkout are separate flows.
export function safeSquareCheckoutUrl(value, { mode = 'automatic', planId, environment } = {}) {
  if (typeof value !== 'string' || value !== value.trim() || value.length > 2048) return null;
  let url;
  try { url = new URL(value); } catch (_) { return null; }
  if (url.protocol !== 'https:' || url.username || url.password || url.port || url.hash || url.search) return null;
  if (mode === 'manual') {
    const plan = membershipPlan(planId);
    return plan && url.href === plan.manual_payment_url ? url.href : null;
  }
  const allowedHost = url.hostname === 'square.link' || (environment === 'sandbox' && url.hostname === 'sandbox.square.link');
  return allowedHost && /^\/u\/[A-Za-z0-9_-]{4,128}\/?$/.test(url.pathname) ? url.href : null;
}

export function normalizePlansResponse(payload) {
  if (!payload || !Array.isArray(payload.plans)) throw new Error('Membership plans are unavailable.');
  const plans = payload.plans.map(plan => {
    const expected = membershipPlan(plan.id);
    if (!expected || expected.id !== plan.id || plan.amount_cents !== expected.amount_cents || plan.currency !== 'USD' || plan.term_months !== expected.term_months) throw new Error('Membership pricing needs to be refreshed.');
    const manual = safeSquareCheckoutUrl(plan.manual_payment_url, { mode: 'manual', planId: plan.id });
    return { ...expected, manual_payment_url: manual };
  });
  if (plans.length !== 3 || new Set(plans.map(plan => plan.id)).size !== 3 || payload.recurring !== false) throw new Error('Membership plans are incomplete.');
  const approvalMode = payload.approval_mode === 'automatic' ? 'automatic' : 'manual';
  return { plans, approval_mode: approvalMode, environment: ['sandbox', 'production'].includes(payload.environment) ? payload.environment : null,
    automatic_checkout_available: approvalMode === 'automatic' && payload.automatic_checkout_available === true && ['sandbox', 'production'].includes(payload.environment),
    automatic_activation_available: approvalMode === 'automatic' && payload.automatic_activation_available === true && payload.environment === 'production', recurring: false };
}

export function manualApprovalRequest({ userId, planId, paymentReference, paymentReviewed }) {
  if (typeof userId !== 'string' || !userId.trim() || membershipPlan(planId)?.id !== planId) throw new Error('Choose a member and the plan they purchased.');
  const reference = typeof paymentReference === 'string' ? paymentReference.trim() : '';
  if (!/^[A-Za-z0-9_-]{3,192}$/.test(reference)) throw new Error('Enter the Square payment or receipt code: 3–192 letters, numbers, underscores, or hyphens. Do not paste a full link.');
  if (paymentReviewed !== true) throw new Error('Confirm that you checked the payment in Square and matched it to this member.');
  return { user_id: userId, plan_id: planId, payment_reference: reference, confirm_payment_reviewed: true };
}

export async function approveManualPurchase({ client, api, credential, currentCredential, purchase }) {
  if (credential?.kind !== 'member') throw new Error('An active administrator session is required.');
  const body = manualApprovalRequest(purchase);
  if (!sameBillingCredential(credential, currentCredential())) return null;
  const response = await client.post(`${api}/billing/admin/approve`, body, { headers: billingHeaders(credential) });
  if (!sameBillingCredential(credential, currentCredential())) return null;
  const result = response.data;
  if (result?.user_id !== body.user_id || result?.payment?.plan_id !== body.plan_id ||
      result?.payment?.evidence_source !== 'admin_review' || typeof result?.entitlement?.active !== 'boolean' ||
      typeof result?.payment?.payment_id !== 'string' || result.payment.payment_id.toLowerCase() !== body.payment_reference.toLowerCase() ||
      typeof result?.duplicate !== 'boolean') throw new Error('The approval response could not be matched. Refresh payments and retry with the same reference.');
  return result;
}

export function manualApprovalError(error) {
  if ([401, 403].includes(error?.response?.status)) return 'Your administrator session could not be verified. Sign in again before approving this purchase.';
  if (error?.response?.status === 409) return 'This approval needs review. Refresh payments, check the member’s status and purchased plan, and reuse this same Square reference if you retry.';
  if (error?.response?.status === 404) return 'This member account could not be found. Refresh the member list before continuing.';
  if ([400, 422].includes(error?.response?.status)) return 'The approval details were not accepted. Check the member, purchased plan, and Square payment or receipt code.';
  return 'Approval could not be confirmed. Refresh payments and retry with the same reference. A retry will not add the same purchase twice or send another welcome email.';
}

export const welcomeEmailLabel = status => ({
  pending: 'Welcome email queued', sending: 'Welcome email is being submitted', sent: 'Email provider accepted',
  failed: 'Welcome email failed — follow up manually', unavailable: 'Email service unavailable — send the welcome email manually',
  unknown: 'Email outcome unknown — check before sending again',
}[status] || 'Email status not recorded');

export async function loadBillingState({ client, api, credential, currentCredential }) {
  if (!sameBillingCredential(credential, currentCredential())) return null;
  const headers = billingHeaders(credential);
  const outcomes = await Promise.allSettled([
    client.get(`${api}/billing/plans`),
    client.get(`${api}/billing/status`, { headers }),
  ]);
  if (!sameBillingCredential(credential, currentCredential())) return null;
  const status = outcomes[1];
  if (status.status !== 'fulfilled') throw status.reason;
  const expectedUser = credential.kind === 'member' ? credential.session.id : credential.user_id;
  if (status.value.data?.user_id !== expectedUser) throw new Error('The payment account did not match this login.');
  let plans = null; let plansError = '';
  if (outcomes[0].status === 'fulfilled') {
    try { plans = normalizePlansResponse(outcomes[0].value.data); } catch (_) { plansError = 'Membership pricing could not be verified. Refresh before continuing.'; }
  } else plansError = 'Payment options are unavailable. Refresh to try again.';
  return { status: status.value.data, plans, plansError };
}

export async function createMemberCheckout({ client, api, credential, currentCredential, planId, idempotencyKey, environment }) {
  if (membershipPlan(planId)?.id !== planId || !/^[A-Za-z0-9_-]{16,100}$/.test(idempotencyKey || '')) throw new Error('Choose a membership plan before opening checkout.');
  if (!sameBillingCredential(credential, currentCredential())) return null;
  const response = await client.post(`${api}/billing/checkout`, { plan_id: planId, idempotency_key: idempotencyKey }, { headers: billingHeaders(credential) });
  if (!sameBillingCredential(credential, currentCredential())) return null;
  const checkout = response.data;
  if (checkout?.plan_id !== planId || !['ready', 'preparing'].includes(checkout.status) || typeof checkout.checkout_id !== 'string') throw new Error('Checkout could not be verified.');
  if (checkout.status === 'preparing') return { ...checkout, checkout_url: null };
  const url = safeSquareCheckoutUrl(checkout.checkout_url, { environment });
  if (!url) throw new Error('Square returned an unsupported checkout address.');
  return { ...checkout, checkout_url: url };
}
