import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { MEMBERSHIP_PLANS, membershipPlan, moneyFromCents, sameBillingCredential, billingHeaders, billingError,
  loadBillingState, createMemberCheckout, safeSquareCheckoutUrl, checkoutAttemptKey, retireFulfilledAttempts,
  manualApprovalRequest, approveManualPurchase, manualApprovalError, welcomeEmailLabel } from './billingModel.mjs';
import './billing.css';
import { eventDeadlineLabel, eventMembershipPresentation } from '../practiceEvent/eventModel.mjs';

const dateLabel = value => { const date = value ? new Date(value) : null; return date && !Number.isNaN(date.valueOf()) ? date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : 'Not set'; };
const credentialId = value => value?.kind === 'member' ? `member:${value.session.id}:${value.session.active_session_id}` : `billing:${value?.user_id || ''}:${value?.billing_token || ''}`;
const statusLabel = value => ({ COMPLETED: 'Completed', completed: 'Completed', verified: 'Verified', sandbox_verified: 'Sandbox test verified', pending: 'Pending', approved: 'Approved', granted: 'Access approved', refunded: 'Refunded', REFUNDED: 'Refunded', failed: 'Failed', FAILED: 'Failed', review_required: 'Needs review', ready: 'Checkout prepared', preparing: 'Preparing checkout' }[value] || String(value || 'Pending').replace(/_/g, ' '));
const environmentLabel = value => value === 'sandbox' ? 'SANDBOX · TEST PAYMENT' : value === 'production' ? 'PRODUCTION' : 'ENVIRONMENT NOT RECORDED';
const manuallyReviewed = payment => payment?.evidence_source === 'admin_review';
const paymentKey = payment => `${payment.evidence_source || payment.environment || 'unknown'}:${payment.payment_id}`;
const paymentDate = payment => manuallyReviewed(payment) ? payment.reviewed_at : payment.verified_at || payment.received_at;
const paymentReference = payment => payment.payment_reference || payment.payment_id;

export default function BillingPanel({ apiBase, credential, initialPlanId = '', onAccessReady, onAuthExpired, compact = false, practiceEvent, onRequestEvent }) {
  const current = useRef(credential); current.current = credential;
  const key = credentialId(credential);
  const [view, setView] = useState({ owner: null, data: null, error: '', authExpired: false, loading: true });
  const [refreshVersion, refresh] = useState(0);
  const [planId, setPlanId] = useState(membershipPlan(initialPlanId)?.id || 'monthly');
  const [checkout, setCheckout] = useState({ owner: null, busy: false, error: '', result: null });
  const attempts = useRef(new Map());
  const planEdited = useRef(false);
  useEffect(() => { if (membershipPlan(initialPlanId)) setPlanId(membershipPlan(initialPlanId).id); }, [initialPlanId]);
  useEffect(() => {
    const captured = credential;
    current.current = captured;
    attempts.current = new Map();
    planEdited.current = false;
    setPlanId(membershipPlan(initialPlanId)?.id || 'monthly');
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
  const manualMode = plans?.approval_mode !== 'automatic';
  const selected = (plans?.plans || MEMBERSHIP_PLANS).find(plan => plan.id === planId) || MEMBERSHIP_PLANS[0];
  const ownCheckout = sameBillingCredential(checkout.owner, credential) ? checkout : { busy: false, error: '', result: null };
  const sandbox = !manualMode && plans?.environment === 'sandbox';
  const manualUrl = manualMode && selected?.manual_payment_url && safeSquareCheckoutUrl(selected.manual_payment_url, { mode: 'manual', planId: selected.id });
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
    const savedPlan = membershipPlan(data?.status?.selected_plan_id || data?.status?.membership_plan);
    if (!membershipPlan(initialPlanId) && !planEdited.current && savedPlan) setPlanId(savedPlan.id);
  }, [data?.status?.selected_plan_id, data?.status?.membership_plan, initialPlanId, key]);

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
  const eventMembership = eventMembershipPresentation(data?.status);
  const membershipTag = eventMembership?.label || (membership?.active ? 'MEMBERSHIP ACTIVE' : manualMode ? 'AWAITING ADMIN APPROVAL' : 'ACCESS PENDING');
  const membershipTitle = eventMembership?.title || (membership?.lifetime ? 'Lifetime access' : membershipPlan(membership?.plan_id)?.label || (membership?.source === 'legacy' ? 'Existing membership' : 'Your account is saved'));
  const membershipDescription = eventMembership ? eventMembership.kind === 'active'
    ? `Your free practice access runs through ${eventDeadlineLabel(eventMembership.endsAt)}. It does not renew or charge you. Choose a membership below to continue after the event.`
    : 'Your account, profile, and practice history are saved. Choose a one-time membership to continue. If you already paid on Square, wait for the team to review your payment before buying again.'
    : membership?.active ? membership.lifetime ? 'Your account has lifetime membership access.' : membership.paid_through ? `Access through ${dateLabel(membership.paid_through)}. This purchase does not renew automatically.` : 'Your existing access remains active.'
      : manualMode ? 'If you have already paid, wait for the CashOutAI team to match your Square payment and approve access. Keep this account; you do not need to register again.' : 'Access is pending. Refresh to check this account’s current membership status.';
  return <section className={`cashout-billing ${compact ? 'is-compact' : ''}`} aria-labelledby="membership-heading">
    <div className="billing-heading"><div><span className="billing-kicker">YOUR MEMBERSHIP</span><h2 id="membership-heading">Membership &amp; payments</h2></div><button type="button" className="billing-refresh" onClick={() => refresh(value => value + 1)} disabled={loading}>Refresh status</button></div>
    {loading ? <p className="billing-loading" role="status">Loading this account's membership…</p> : view.error ? <div className="billing-error" role="alert"><p>{view.error}</p>{view.authExpired && onAuthExpired && <button type="button" onClick={onAuthExpired}>Sign in again</button>}</div> : <>
      <div className={`billing-membership-status ${membership?.active ? 'is-active' : 'is-pending'}`}><div><span>{membershipTag}</span><h3>{membershipTitle}</h3><p>{membershipDescription}</p></div>{membership?.active && onAccessReady && <button type="button" onClick={() => { if (sameBillingCredential(current.current, credential)) onAccessReady(data.status); }}>{credential?.kind === 'billing' ? 'Sign in to the app' : 'Continue to the app'} ↗</button>}</div>
      {!membership?.active && practiceEvent?.phase === 'open' && onRequestEvent && <div className="practice-event-portal"><h3>Try the open practice event</h3><p>Verify this account’s email for eligible free practice access through {eventDeadlineLabel(practiceEvent.config.ends_at)}. The event uses virtual funds and has one shared deadline.</p><button type="button" className="practice-event-secondary" onClick={() => onRequestEvent(data.status.email || '')}>Verify email for practice access</button></div>}
      {manualMode && <div className="billing-account-summary" aria-label="Payment matching details"><div><span>ACCOUNT EMAIL</span><strong>{data.status.email || 'Contact the CashOutAI team to confirm your account email'}</strong></div><div><span>USERNAME</span><strong>{data.status.username || credential.username || 'Your account'}</strong></div><div className="billing-account-id"><span>ACCOUNT ID</span><code>{data.status.user_id}</code></div><p>Use this account email at Square. If you paid with a different email, tell the CashOutAI team your account email and Square receipt or payment reference so they can match your purchase.</p></div>}
      {membership?.active && membership?.lifetime ? <p className="billing-terms">You already have lifetime access. No renewal is needed.</p> : <>
        <div className="billing-plans" role="radiogroup" aria-label="Membership access term">
          {(plans?.plans || MEMBERSHIP_PLANS).map(plan => <button type="button" role="radio" aria-checked={planId === plan.id} key={plan.id} className={planId === plan.id ? 'is-selected' : ''} onClick={() => { planEdited.current = true; setPlanId(plan.id); }} disabled={ownCheckout.busy}>
            <span>{plan.label}</span><strong>{moneyFromCents(plan.amount_cents)}</strong><small>One-time purchase<br />{plan.term_months === null ? 'Lifetime access' : `${plan.term_months} calendar ${plan.term_months === 1 ? 'month' : 'months'} of access`}</small>
          </button>)}
        </div>
        <p className="billing-terms">Choose an access term. Each purchase is paid once, with no recurring charge or automatic renewal. Enter your payment details on Square.</p>
        {data.plansError ? <p className="billing-error" role="status">{data.plansError}</p>
          : manualMode ? <div className="billing-checkout-box is-manual"><div><h3>One-time payment · Manual approval</h3><p>Selected plan: {selected.label}. Pay once through Square. The CashOutAI team checks the payment, approves your membership, and sends a welcome email. Already paid? Wait for approval before making another purchase.</p></div>{manualUrl && <a href={manualUrl} target="_blank" rel="noopener noreferrer" className="billing-primary-action">Pay {moneyFromCents(selected.amount_cents)} once ↗</a>}</div>
            : plans?.automatic_checkout_available ? <div className="billing-checkout-box">
            <div><h3>{sandbox ? 'Square sandbox checkout' : 'Account-linked Square checkout'}</h3><p>{sandbox ? 'This is a test checkout. Sandbox payments do not activate real membership access.' : plans.automatic_activation_available ? 'Your payment is linked to this account. Membership updates after Square confirms the completed payment to CashOutAI.' : 'Your payment is linked to this account. Automatic activation is not available; the payment needs review before access changes.'}</p></div>
            {blockedRecord ? <p className="billing-inline-note" role="status">{blockedRecord.status === 'review' ? 'This checkout needs an admin review before another payment is started.' : 'This checkout was canceled. Contact an admin before starting another payment.'} Reference: {blockedRecord.checkout_id}.</p>
              : pendingRecord ? <><button type="button" className="billing-primary-action" onClick={() => refresh(value => value + 1)}>Check checkout status</button><p className="billing-inline-note" role="status">Your checkout is still being prepared. Refresh its status to continue with the same attempt.</p></>
                : preparedUrl ? <a href={preparedUrl} target="_blank" rel="noopener noreferrer" className="billing-primary-action">{sandbox ? 'Open Square test checkout' : 'Continue to Square'} ↗</a>
                  : <button type="button" className="billing-primary-action" disabled={ownCheckout.busy} onClick={prepareCheckout}>{ownCheckout.busy ? 'Preparing checkout…' : 'Prepare secure checkout'}</button>}
          </div>
            : sandbox ? <div className="billing-checkout-box"><div><h3>Sandbox checkout is not configured</h3><p>Test payment options are unavailable. No payment has been started, and this sandbox view does not offer a production payment link.</p></div></div>
              : <div className="billing-checkout-box"><div><h3>Payment options need attention</h3><p>Contact the CashOutAI team for help with this account's payment options.</p></div></div>}
        {ownCheckout.error && <p className="billing-error" role="alert">{ownCheckout.error}</p>}
      </>}
      <div className="billing-history-heading"><h3>Payment history</h3><span>Server records for this account</span></div>
      {payments.length ? <div className="billing-payment-list">{payments.map(payment => <article key={paymentKey(payment)}><div><strong>{membershipPlan(payment.plan_id)?.label || 'Membership payment'}</strong><span className={payment.environment === 'sandbox' ? 'billing-environment is-sandbox' : 'billing-environment'}>{manuallyReviewed(payment) ? 'MANUAL · ADMIN REVIEWED' : environmentLabel(payment.environment)}</span><span>{manuallyReviewed(payment) ? `Admin reviewed ${dateLabel(payment.reviewed_at)}` : payment.verified_at ? `Verified ${dateLabel(payment.verified_at)}` : 'Verification pending'}</span><small>Reference {paymentReference(payment)}</small></div><div><strong>{moneyFromCents(payment.amount_cents, payment.currency || 'USD')}</strong><span className={payment.review_required ? 'needs-review' : ''}>{payment.review_required ? 'Needs admin review' : statusLabel(payment.status)}</span></div></article>)}</div> : <p className="billing-history-empty">No payment is recorded for this account yet. After the team reviews and records your Square purchase, it appears here.</p>}
      <p className="billing-footer-note">{manualMode ? 'Refresh status after the team approves your membership. Your payment receipt helps the team match your purchase; access opens when approval is recorded in CashOutAI.' : 'Refresh after paying to see the current status. A checkout return page or receipt alone never grants app access.'}</p>
    </>}
  </section>;
}

export function AdminBillingPanel({ apiBase, credential, members = [], selectedMemberId = '', selectionVersion = 0, onApproved }) {
  const current = useRef(credential); current.current = credential;
  const key = credentialId(credential);
  const [version, refresh] = useState(0);
  const [view, setView] = useState({ owner: null, payments: [], loading: true, error: '', hasMore: false });
  const [draftState, setDraft] = useState({ owner: credential, userId: '', planId: 'monthly', paymentReference: '', paymentReviewed: false });
  const draft = sameBillingCredential(draftState.owner, credential) ? draftState : { userId: '', planId: 'monthly', paymentReference: '', paymentReviewed: false };
  const [approval, setApproval] = useState({ owner: null, busy: false, error: '', result: null, member: null });
  const submitting = useRef(null);
  const memberSelect = useRef(null);
  const availableMembers = [...new Map(members.filter(member => typeof member?.id === 'string' && member.id)
    .map(member => [member.id, member])).values()]
    .sort((left, right) => String(left.username || left.email || left.id).localeCompare(String(right.username || right.email || right.id)));
  const selectedMember = availableMembers.find(member => member.id === draft.userId);
  const selectedPlan = membershipPlan(draft.planId);

  useEffect(() => {
    current.current = credential;
    submitting.current = null;
    setDraft({ owner: credential, userId: '', planId: 'monthly', paymentReference: '', paymentReviewed: false });
    setApproval({ owner: credential, busy: false, error: '', result: null, member: null });
    return () => { if (sameBillingCredential(current.current, credential)) current.current = null; };
  }, [key]);
  useEffect(() => {
    if (!selectedMemberId || submitting.current) return;
    const member = availableMembers.find(item => item.id === selectedMemberId);
    if (!member) return;
    setDraft({ owner: credential, userId: member.id, planId: membershipPlan(member.membership_plan)?.id || 'monthly', paymentReference: '', paymentReviewed: false });
    setApproval({ owner: credential, busy: false, error: '', result: null, member: null });
    memberSelect.current?.focus({ preventScroll: true });
  }, [selectedMemberId, selectionVersion, key]);
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
    return () => { cancelled = true; };
  }, [key, version, apiBase]);
  const visible = sameBillingCredential(view.owner, credential) ? view : { loading: true, payments: [], error: '' };
  const ownApproval = sameBillingCredential(approval.owner, credential) ? approval : { busy: false, error: '', result: null, member: null };
  const approvedPayment = ownApproval.result?.payment;
  const refreshedPayment = approvedPayment && visible.payments.find(payment => paymentKey(payment) === paymentKey(approvedPayment));
  const emailStatus = refreshedPayment?.welcome_email?.status || ownApproval.result?.welcome_email?.status;
  const updateDraft = changes => {
    if (submitting.current) return;
    setDraft(previous => ({ ...previous, owner: credential, ...changes, paymentReviewed: false }));
    setApproval({ owner: credential, busy: false, error: '', result: null, member: null });
  };
  const submitApproval = async event => {
    event.preventDefault();
    if (submitting.current || !selectedMember || !sameBillingCredential(current.current, credential)) return;
    const captured = credential;
    const purchase = { ...draft };
    try { manualApprovalRequest(purchase); }
    catch (error) { setApproval({ owner: captured, busy: false, error: error.message, result: null, member: null }); return; }
    const request = { credential: captured, purchase };
    submitting.current = request;
    setApproval({ owner: captured, busy: true, error: '', result: null, member: selectedMember });
    try {
      const result = await approveManualPurchase({ client: axios, api: apiBase, credential: captured,
        currentCredential: () => current.current, purchase });
      if (result && sameBillingCredential(current.current, captured)) {
        setApproval({ owner: captured, busy: false, error: '', result, member: selectedMember });
        setDraft(previous => ({ ...previous, paymentReviewed: false }));
        refresh(value => value + 1);
        onApproved?.(result);
      }
    } catch (error) {
      if (sameBillingCredential(current.current, captured)) setApproval({ owner: captured, busy: false, error: manualApprovalError(error), result: null, member: selectedMember });
    } finally {
      if (submitting.current === request) submitting.current = null;
    }
  };

  return <section id="admin-paid-approval" className="cashout-billing billing-admin" aria-labelledby="admin-billing-heading">
    <div className="billing-heading"><div><span className="billing-kicker">ADMINISTRATION</span><h2 id="admin-billing-heading">Approve a paid purchase</h2></div><button type="button" className="billing-refresh" onClick={() => refresh(value => value + 1)} disabled={visible.loading || ownApproval.busy}>Refresh payments</button></div>
    <p className="billing-terms">After receiving the Square payment alert, check the payment in Square and match it to the member below. This records your review, grants the purchased term, and requests a welcome email.</p>
    <form className="billing-approval-form" onSubmit={submitApproval}>
      <fieldset disabled={ownApproval.busy}>
        <div className="billing-approval-fields">
          <label className="billing-approval-member">Member account
            <select ref={memberSelect} value={draft.userId} onChange={event => {
              const member = availableMembers.find(item => item.id === event.target.value);
              updateDraft({ userId: event.target.value, planId: membershipPlan(member?.membership_plan)?.id || 'monthly', paymentReference: '' });
            }} required>
              <option value="">Choose a member</option>
              {availableMembers.map(member => <option value={member.id} key={member.id}>{member.username || member.real_name || 'Member'} · {member.email || member.id}</option>)}
            </select>
          </label>
          <label>Actual purchased plan
            <select value={draft.planId} onChange={event => updateDraft({ planId: event.target.value })} required>
              {MEMBERSHIP_PLANS.map(plan => <option key={plan.id} value={plan.id}>{plan.label} · {moneyFromCents(plan.amount_cents)} one time</option>)}
            </select>
          </label>
          <label>Square payment or receipt reference
            <input value={draft.paymentReference} onChange={event => updateDraft({ paymentReference: event.target.value })}
              placeholder="Payment or receipt code" autoComplete="off" spellCheck={false} minLength={3} maxLength={192} required aria-describedby="approval-reference-help" />
          </label>
        </div>
        {selectedMember && <div className="billing-review-member"><strong>{selectedMember.real_name || selectedMember.username}</strong><span>{selectedMember.email || 'No email recorded'} · @{selectedMember.username}</span><small>Account ID: {selectedMember.id}</small></div>}
        {!availableMembers.length && <p className="billing-inline-note">Member accounts are loading or none are available. A member must create an account before you can approve their purchase.</p>}
        <p id="approval-reference-help" className="billing-inline-note">Use the code from Square, not a receipt URL. Retrying the same member, plan, and reference does not add time twice or send a second welcome email.</p>
        <label className="billing-approval-confirm"><input type="checkbox" checked={draft.paymentReviewed} onChange={event => setDraft(previous => ({ ...previous, paymentReviewed: event.target.checked }))} required /><span>I checked this payment in Square and matched the buyer, the {moneyFromCents(selectedPlan?.amount_cents)} amount, and the purchased plan to this member.</span></label>
        <button className="billing-primary-action" type="submit" disabled={!selectedMember || !draft.paymentReviewed || ownApproval.busy || Boolean(ownApproval.result)}>{ownApproval.busy ? 'Recording approval…' : 'Approve access & send welcome email'}</button>
      </fieldset>
    </form>
    {ownApproval.error && <p className="billing-error" role="alert">{ownApproval.error}</p>}
    {ownApproval.result && <div className="billing-approval-result" role="status">
      <h3>{ownApproval.result.duplicate ? 'Purchase already recorded' : 'Purchase approved'}</h3>
      <p>{ownApproval.member?.username || 'Member'} · {membershipPlan(approvedPayment?.plan_id)?.label || 'Membership'} · Reference {paymentReference(approvedPayment)}</p>
      <p>{ownApproval.result.entitlement.active ? ownApproval.result.entitlement.lifetime ? 'Lifetime access is active.' : ownApproval.result.entitlement.paid_through ? `Access is active through ${dateLabel(ownApproval.result.entitlement.paid_through)}.` : 'Membership access is active.' : 'This recorded purchase does not currently provide active access. Review the account’s membership.'}{ownApproval.result.duplicate ? ' This retry did not extend the term or request another welcome email.' : ''}</p>
      <p className="billing-email-outcome"><strong>{welcomeEmailLabel(emailStatus)}.</strong> {['pending', 'sending'].includes(emailStatus) ? 'Refresh payments to see the email result.' : emailStatus === 'sent' ? 'Provider acceptance does not confirm inbox delivery.' : ['failed', 'unavailable', 'unknown'].includes(emailStatus) ? 'The purchase remains recorded; do not approve it again to resend email.' : ''}</p>
      <button type="button" className="billing-refresh" onClick={() => { updateDraft({ userId: '', planId: 'monthly', paymentReference: '' }); memberSelect.current?.focus(); }}>Review another purchase</button>
    </div>}
    <div className="billing-history-heading"><h3>Payment tracking</h3><span>Recorded purchases and email outcomes</span></div>
    {visible.loading ? <p className="billing-loading">Loading payment records…</p> : visible.error ? <p className="billing-error" role="alert">{visible.error}</p> : visible.payments.length ? <div className="billing-admin-table-wrap"><table><thead><tr><th>Member</th><th>Plan / amount</th><th>Review / email</th><th>Recorded</th><th>Payment reference</th></tr></thead><tbody>{visible.payments.map(payment => <tr key={paymentKey(payment)}><td><strong>{payment.username || 'Member'}</strong><small>{payment.user_id}</small><span className={payment.environment === 'sandbox' ? 'billing-environment is-sandbox' : 'billing-environment'}>{manuallyReviewed(payment) ? 'MANUAL · ADMIN REVIEWED' : environmentLabel(payment.environment)}</span></td><td>{membershipPlan(payment.plan_id)?.label || 'Membership'}<small>{moneyFromCents(payment.amount_cents, payment.currency || 'USD')}</small></td><td>{payment.review_required ? 'Needs review' : statusLabel(payment.status)}{payment.reason && <small>{String(payment.reason).replace(/_/g, ' ')}</small>}{manuallyReviewed(payment) && <small>{welcomeEmailLabel(payment.welcome_email?.status)}</small>}</td><td>{dateLabel(paymentDate(payment))}</td><td>{paymentReference(payment)}</td></tr>)}</tbody></table></div> : <p className="billing-history-empty">No purchases have been recorded yet. Approve a matched Square purchase above to add it here.</p>}
    {visible.hasMore && <p className="billing-footer-note">Showing the latest 50 payments.</p>}
  </section>;
}
