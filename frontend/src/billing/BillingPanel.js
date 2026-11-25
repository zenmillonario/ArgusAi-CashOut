import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { MEMBERSHIP_PLANS, membershipPlan, moneyFromCents, sameBillingCredential, billingHeaders, billingError,
  loadBillingState, createMemberCheckout, safeSquareCheckoutUrl, checkoutAttemptKey, retireFulfilledAttempts } from './billingModel.mjs';
import './billing.css';

const dateLabel = value => { const date = value ? new Date(value) : null; return date && !Number.isNaN(date.valueOf()) ? date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : 'Not set'; };
const credentialId = value => value?.kind === 'member' ? `member:${value.session.id}:${value.session.active_session_id}` : `billing:${value?.user_id || ''}:${value?.billing_token || ''}`;
const statusLabel = value => ({ COMPLETED: 'Completed', completed: 'Completed', verified: 'Verified', sandbox_verified: 'Sandbox test verified', pending: 'Pending', approved: 'Approved', refunded: 'Refunded', REFUNDED: 'Refunded', failed: 'Failed', FAILED: 'Failed', review_required: 'Needs review', ready: 'Checkout prepared', preparing: 'Preparing checkout' }[value] || String(value || 'Pending').replace(/_/g, ' '));
const environmentLabel = value => value === 'sandbox' ? 'SANDBOX · TEST PAYMENT' : value === 'production' ? 'PRODUCTION' : 'ENVIRONMENT NOT RECORDED';

export default function BillingPanel({ apiBase, credential, initialPlanId = '', onAccessReady, onAuthExpired, compact = false }) {
  const current = useRef(credential); current.current = credential;
  const key = credentialId(credential);
  const [view, setView] = useState({ owner: null, data: null, error: '', authExpired: false, loading: true });
  const [refreshVersion, refresh] = useState(0);
  const [planId, setPlanId] = useState(membershipPlan(initialPlanId)?.id || 'monthly');
  const [checkout, setCheckout] = useState({ owner: null, busy: false, error: '', result: null });
  const attempts = useRef(new Map());
  useEffect(() => { if (membershipPlan(initialPlanId)) setPlanId(membershipPlan(initialPlanId).id); }, [initialPlanId]);
  useEffect(() => {
    const captured = credential;
    current.current = captured;
    attempts.current = new Map();
    return () => { if (sameBillingCredential(current.current, captured)) current.current = null; };
  }, [key]);
  useEffect(() => {
    const captured = credential;
    current.current = captured;
    let cancelled = false;
    setView({ owner: captured, data: null, error: '', authExpired: false, loading: true });
    loadBillingState({ client: axios, api: apiBase, credential: captured, currentCredential: () => current.current }).then(data => {
      if (!cancelled && data && sameBillingCredential(current.current, captured)) setView({ owner: captured, data, error: '', authExpired: false, loading: false });
    }).catch(error => {
      if (!cancelled && sameBillingCredential(current.current, captured)) setView({ owner: captured, data: null, error: billingError(error), authExpired: error.response?.status === 401, loading: false });
    });
    return () => { cancelled = true; };
  }, [key, refreshVersion, apiBase]);
  useEffect(() => {
    const onFocus = () => refresh(value => value + 1);
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, []);
  const ownView = sameBillingCredential(view.owner, credential);
  const data = ownView ? view.data : null;
  const loading = !ownView || view.loading;
  const plans = data?.plans;
  const membership = data?.status?.entitlement;
  const selected = (plans?.plans || MEMBERSHIP_PLANS).find(plan => plan.id === planId) || MEMBERSHIP_PLANS[0];
  const ownCheckout = sameBillingCredential(checkout.owner, credential) ? checkout : { busy: false, error: '', result: null };
  const sandbox = plans?.environment === 'sandbox';
  const manualUrl = !sandbox && selected?.manual_payment_url && safeSquareCheckoutUrl(selected.manual_payment_url, { mode: 'manual', planId: selected.id });
  const checkouts = Array.isArray(data?.status?.checkouts) ? data.status.checkouts : [];
  const ownRecord = ownCheckout.result && checkouts.find(item => item.checkout_id === ownCheckout.result.checkout_id);
  const selectedRecord = checkouts.find(item => item.plan_id === planId && item.environment === plans?.environment);
  const blockedRecord = [ownRecord, selectedRecord].find(item => item?.plan_id === planId && ['review', 'canceled'].includes(item?.status));
  const pendingRecord = [ownRecord, selectedRecord, ownRecord ? null : ownCheckout.result].find(item => item?.plan_id === planId && item.environment === plans?.environment && ['preparing', 'retry'].includes(item.status));
  const readyResponse = ownCheckout.result?.plan_id === planId && ownCheckout.result?.status === 'ready' &&
    ownCheckout.result?.environment === plans?.environment && (!ownRecord || ownRecord.status === 'ready') ? ownCheckout.result : null;
  const prepared = !blockedRecord && (readyResponse || checkouts.find(item => item.plan_id === planId && item.environment === plans?.environment && item.status === 'ready' && item.checkout_url));
  const preparedUrl = prepared && safeSquareCheckoutUrl(prepared.checkout_url, { environment: plans?.environment });

  useEffect(() => {
    if (!data) return;
    const recorded = Array.isArray(data.status?.checkouts) ? data.status.checkouts : [];
    retireFulfilledAttempts(attempts.current, recorded);
    setCheckout(previous => {
      if (!sameBillingCredential(previous.owner, credential) || !previous.result) return previous;
      return recorded.some(item => item.checkout_id === previous.result.checkout_id && item.status === 'fulfilled' && item.environment === previous.result.environment)
        ? { owner: credential, busy: false, error: '', result: null } : previous;
    });
  }, [data, key]);

  const prepareCheckout = async () => {
    if (ownCheckout.busy || !plans?.automatic_checkout_available || !data?.status || blockedRecord || pendingRecord) return;
    const captured = credential;
    const selectedId = planId;
    const attemptKey = checkoutAttemptKey(selectedId, plans.environment);
    const attempt = attempts.current.get(attemptKey) || { key: crypto.randomUUID(), checkoutId: null, environment: plans.environment };
    attempts.current.set(attemptKey, attempt);
    setCheckout({ owner: captured, busy: true, error: '', result: null });
    try {
      const result = await createMemberCheckout({ client: axios, api: apiBase, credential: captured,
        currentCredential: () => current.current, planId: selectedId, idempotencyKey: attempt.key, environment: plans.environment });
      if (result && sameBillingCredential(current.current, captured)) {
        attempts.current.set(attemptKey, { ...attempt, checkoutId: result.checkout_id });
        setCheckout({ owner: captured, busy: false, error: '', result: { ...result, environment: plans.environment } });
      }
    } catch (error) {
      if (sameBillingCredential(current.current, captured)) setCheckout({ owner: captured, busy: false, error: billingError(error), result: null });
    }
  };
  const payments = Array.isArray(data?.status?.payments) ? data.status.payments : [];
  return <section className={`cashout-billing ${compact ? 'is-compact' : ''}`} aria-labelledby="membership-heading">
    <div className="billing-heading"><div><span className="billing-kicker">YOUR MEMBERSHIP</span><h2 id="membership-heading">Membership &amp; payments</h2></div><button type="button" className="billing-refresh" onClick={() => refresh(value => value + 1)} disabled={loading}>Refresh status</button></div>
    {loading ? <p className="billing-loading" role="status">Loading this account's membership…</p> : view.error ? <div className="billing-error" role="alert"><p>{view.error}</p>{view.authExpired && onAuthExpired && <button type="button" onClick={onAuthExpired}>Sign in again</button>}</div> : <>
      <div className={`billing-membership-status ${membership?.active ? 'is-active' : 'is-pending'}`}><div><span>{membership?.active ? 'MEMBERSHIP ACTIVE' : 'ACCESS PENDING'}</span><h3>{membership?.lifetime ? 'Lifetime access' : membershipPlan(membership?.plan_id)?.label || (membership?.source === 'legacy' ? 'Existing membership' : 'Choose your membership')}</h3><p>{membership?.active ? membership.lifetime ? 'Your account has lifetime membership access.' : membership.paid_through ? `Access through ${dateLabel(membership.paid_through)}.` : 'Your existing access remains active.' : 'A payment or an admin review may still be needed. This status updates only after the server verifies your account.'}</p></div>{membership?.active && onAccessReady && <button type="button" onClick={() => { if (sameBillingCredential(current.current, credential)) onAccessReady(data.status); }}>{credential?.kind === 'billing' ? 'Sign in to the app' : 'Continue to the app'} ↗</button>}</div>
      {membership?.active && membership?.lifetime ? <p className="billing-terms">You already have lifetime access. No renewal is needed.</p> : <>
        <div className="billing-plans" role="radiogroup" aria-label="Membership access term">
          {(plans?.plans || MEMBERSHIP_PLANS).map(plan => <button type="button" role="radio" aria-checked={planId === plan.id} key={plan.id} className={planId === plan.id ? 'is-selected' : ''} onClick={() => setPlanId(plan.id)} disabled={ownCheckout.busy}>
            <span>{plan.label}</span><strong>{moneyFromCents(plan.amount_cents)}</strong><small>{plan.term_months === null ? 'Lifetime access' : `${plan.term_months} calendar ${plan.term_months === 1 ? 'month' : 'months'} of access`}</small>
          </button>)}
        </div>
        <p className="billing-terms">Choose an access term. Review the final price and payment terms on Square before paying. Card details are entered on Square's checkout page.</p>
        {data.plansError ? <p className="billing-error" role="status">{data.plansError}</p>
          : plans?.automatic_checkout_available ? <div className="billing-checkout-box">
            <div><h3>{sandbox ? 'Square sandbox checkout' : 'Account-linked Square checkout'}</h3><p>{sandbox ? 'This is a test checkout. Sandbox payments do not activate real membership access.' : plans.automatic_activation_available ? 'Your payment is linked to this account. Membership updates after Square confirms the completed payment to CashOutAI.' : 'Your payment is linked to this account. Automatic activation is not available; the payment needs review before access changes.'}</p></div>
            {blockedRecord ? <p className="billing-inline-note" role="status">{blockedRecord.status === 'review' ? 'This checkout needs an admin review before another payment is started.' : 'This checkout was canceled. Contact an admin before starting another payment.'} Reference: {blockedRecord.checkout_id}.</p>
              : pendingRecord ? <><button type="button" className="billing-primary-action" onClick={() => refresh(value => value + 1)}>Check checkout status</button><p className="billing-inline-note" role="status">Your checkout is still being prepared. Refresh its status to continue with the same attempt.</p></>
                : preparedUrl ? <a href={preparedUrl} target="_blank" rel="noopener noreferrer" className="billing-primary-action">{sandbox ? 'Open Square test checkout' : 'Continue to Square'} ↗</a>
                  : <button type="button" className="billing-primary-action" disabled={ownCheckout.busy} onClick={prepareCheckout}>{ownCheckout.busy ? 'Preparing checkout…' : 'Prepare secure checkout'}</button>}
          </div>
            : sandbox ? <div className="billing-checkout-box"><div><h3>Sandbox checkout is not configured</h3><p>Test payment options are unavailable. No payment has been started, and this sandbox view does not offer a production payment link.</p></div></div>
              : <div className="billing-checkout-box is-manual"><div><h3>Manual payment review</h3><p>Account-linked checkout is not configured. This existing Square payment link requires an admin to match your payment to this account and approve access. Paying or returning to the app does not activate membership automatically.</p></div>{manualUrl && <a href={manualUrl} target="_blank" rel="noopener noreferrer" className="billing-primary-action">Pay {moneyFromCents(selected.amount_cents)} on Square ↗</a>}</div>}
        {ownCheckout.error && <p className="billing-error" role="alert">{ownCheckout.error}</p>}
      </>}
      <div className="billing-history-heading"><h3>Payment history</h3><span>Server records for this account</span></div>
      {payments.length ? <div className="billing-payment-list">{payments.map(payment => <article key={`${payment.environment || 'unknown'}:${payment.payment_id}`}><div><strong>{membershipPlan(payment.plan_id)?.label || 'Membership payment'}</strong><span className={payment.environment === 'sandbox' ? 'billing-environment is-sandbox' : 'billing-environment'}>{environmentLabel(payment.environment)}</span><span>{payment.verified_at ? `Verified ${dateLabel(payment.verified_at)}` : 'Verification pending'}</span><small>Reference {payment.payment_id}</small></div><div><strong>{moneyFromCents(payment.amount_cents, payment.currency || 'USD')}</strong><span className={payment.review_required ? 'needs-review' : ''}>{payment.review_required ? 'Needs admin review' : statusLabel(payment.status)}</span></div></article>)}</div> : <p className="billing-history-empty">No payment records are available for this account yet. A payment made through an existing link may appear after an admin reviews it.</p>}
      <p className="billing-footer-note">Refresh after paying to see the verified status. A checkout return page or receipt alone never grants app access.</p>
    </>}
  </section>;
}

export function AdminBillingPanel({ apiBase, credential }) {
  const current = useRef(credential); current.current = credential;
  const key = credentialId(credential);
  const [version, refresh] = useState(0);
  const [view, setView] = useState({ owner: null, payments: [], loading: true, error: '', hasMore: false });
  useEffect(() => {
    const captured = credential;
    current.current = captured;
    let cancelled = false;
    setView({ owner: captured, payments: [], loading: true, error: '', hasMore: false });
    axios.get(`${apiBase}/billing/admin/payments`, { params: { limit: 50 }, headers: billingHeaders(captured) }).then(response => {
      if (!cancelled && sameBillingCredential(current.current, captured)) setView({ owner: captured, payments: Array.isArray(response.data?.payments) ? response.data.payments : [], loading: false, error: '', hasMore: response.data?.has_more === true });
    }).catch(error => {
      if (!cancelled && sameBillingCredential(current.current, captured)) setView({ owner: captured, payments: [], loading: false, error: billingError(error), hasMore: false });
    });
    return () => { cancelled = true; if (sameBillingCredential(current.current, captured)) current.current = null; };
  }, [key, version, apiBase]);
  const visible = sameBillingCredential(view.owner, credential) ? view : { loading: true, payments: [], error: '' };
  return <section className="cashout-billing billing-admin"><div className="billing-heading"><div><span className="billing-kicker">ADMINISTRATION</span><h2>Payment tracking</h2></div><button type="button" className="billing-refresh" onClick={() => refresh(value => value + 1)} disabled={visible.loading}>Refresh payments</button></div><p className="billing-terms">Review recorded Square payments and accounts needing attention. This view does not mark a payment complete or grant access.</p>{visible.loading ? <p className="billing-loading">Loading payment records…</p> : visible.error ? <p className="billing-error" role="alert">{visible.error}</p> : visible.payments.length ? <div className="billing-admin-table-wrap"><table><thead><tr><th>Member</th><th>Plan / amount</th><th>Status</th><th>Recorded</th><th>Payment reference</th></tr></thead><tbody>{visible.payments.map(payment => <tr key={`${payment.environment || 'unknown'}:${payment.payment_id}`}><td><strong>{payment.username || 'Member'}</strong><small>{payment.user_id}</small><span className={payment.environment === 'sandbox' ? 'billing-environment is-sandbox' : 'billing-environment'}>{environmentLabel(payment.environment)}</span></td><td>{membershipPlan(payment.plan_id)?.label || 'Membership'}<small>{moneyFromCents(payment.amount_cents, payment.currency || 'USD')}</small></td><td>{payment.review_required ? 'Needs review' : statusLabel(payment.status)}{payment.reason && <small>{String(payment.reason).replace(/_/g, ' ')}</small>}</td><td>{dateLabel(payment.verified_at || payment.received_at)}</td><td>{payment.payment_id}</td></tr>)}</tbody></table></div> : <p className="billing-history-empty">No payment records have been received.</p>}{visible.hasMore && <p className="billing-footer-note">Showing the latest 50 payments.</p>}</section>;
}
