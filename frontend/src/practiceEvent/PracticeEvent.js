import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { confirmPracticeEvent, eventDeadlineLabel, eventMembershipPresentation, practiceEventError, requestPracticeEventLink } from './eventModel.mjs';
import './practice-event.css';

export function PracticeEventInvitation({ event, onJoin, onExisting, registering = false }) {
  if (event.phase === 'ended') return <div className="practice-event-invitation is-ended"><strong>The open practice event has ended.</strong><p>Your account and practice history stay saved. Sign in to review your membership options.</p></div>;
  if (event.phase !== 'open') return null;
  return <section className="practice-event-invitation" aria-label="Open practice event">
    <span className="practice-event-kicker">FREE EVENT ACCESS</span>
    <h2>Explore the bots. Start with $100 in virtual funds.</h2>
    <p>Create an account with your username, email and password. Verify your email to explore the Nautilus rooms. No card required.</p>
    <p className="practice-event-deadline">Free access through <strong>{eventDeadlineLabel(event.config.ends_at)}</strong>.</p>
    {!registering && <div className="practice-event-actions"><button type="button" className="practice-event-primary" onClick={onJoin}>Free Event Access</button><button type="button" className="practice-event-text" onClick={onExisting}>Use my existing account</button></div>}
    <small>One shared deadline. Your saved progress stays with your account.</small>
  </section>;
}

export function PracticeEventRequestDialog({ apiBase, event, email: initialEmail = '', message: initialMessage = '', error: initialError = '', onClose, onRecover }) {
  const [email, setEmail] = useState(initialEmail);
  const [message, setMessage] = useState(initialMessage);
  const [error, setError] = useState(initialError);
  const [busy, setBusy] = useState(false);
  const alive = useRef(true);
  const dialog = useRef(null);
  useEffect(() => {
    alive.current = true;
    const previous = document.activeElement;
    dialog.current?.querySelector('input,button')?.focus();
    return () => { alive.current = false; if (previous?.isConnected) previous.focus(); };
  }, []);
  const submit = async action => {
    action.preventDefault();
    if (busy || event.phase !== 'open') return;
    setBusy(true); setError('');
    try {
      const result = await requestPracticeEventLink(axios, apiBase, email, event.config);
      if (alive.current) setMessage(result.message || 'If this account is eligible, a verification link has been sent to its registered email.');
    } catch (requestError) {
      if (alive.current) setError(practiceEventError(requestError));
    } finally { if (alive.current) setBusy(false); }
  };
  const keyboard = action => {
    if (action.key === 'Escape' && !busy) { action.preventDefault(); onClose(); }
    if (action.key !== 'Tab') return;
    const items = [...dialog.current.querySelectorAll('button:not(:disabled),input:not(:disabled),a[href]')];
    const first = items[0], last = items[items.length - 1];
    if (action.shiftKey && document.activeElement === first) { action.preventDefault(); last?.focus(); }
    else if (!action.shiftKey && document.activeElement === last) { action.preventDefault(); first?.focus(); }
  };
  return <div className="practice-event-backdrop"><section className="practice-event-dialog" role="dialog" aria-modal="true" aria-labelledby="event-request-heading" ref={dialog} onKeyDown={keyboard}>
    <span className="practice-event-kicker">KEEP ONE ACCOUNT</span>
    <h2 id="event-request-heading">{message ? 'Check your email' : 'Verify your email for practice access'}</h2>
    <p>Use the email registered to your CashOutAI account. The link verifies email ownership and opens eligible event access on that same account.</p>
    {message && <div className="practice-event-success" role="status">{message}<p>Open the newest link, confirm your email, then sign in with your username and password. Check Spam if you don’t see it.</p></div>}
    {event.config?.ends_at && <p className="practice-event-deadline">Event access ends {eventDeadlineLabel(event.config.ends_at)}.</p>}
    {event.phase !== 'open' ? <p className="practice-event-error" role="status">This event is not accepting new access. Your account stays saved, and membership options remain available.</p> : <form onSubmit={submit}>
      <label htmlFor="event-request-email">Registered email address</label>
      <input id="event-request-email" type="email" autoComplete="email" value={email} onChange={action => setEmail(action.target.value)} required disabled={busy} />
      {error && <p className="practice-event-error" role="alert">{error}</p>}
      <button type="submit" className="practice-event-primary" disabled={busy}>{busy ? 'Requesting verification…' : message ? 'Send a new verification link' : 'Email verification link'}</button>
    </form>}
    <p className="practice-event-footnote">A verification link does not change your password or create a second account. Existing paid access keeps its original terms.</p>
    <div className="practice-event-actions"><button type="button" className="practice-event-text" disabled={busy} onClick={onRecover}>Need to recover your password?</button><button type="button" className="practice-event-secondary" disabled={busy} onClick={onClose}>Back</button></div>
  </section></div>;
}

export function PracticeEventVerification({ apiBase, token, onSignIn, onRequest }) {
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const confirm = async () => {
    if (busy || result) return;
    setBusy(true); setError('');
    try {
      const next = await confirmPracticeEvent(axios, apiBase, token);
      if (alive.current) setResult(next);
    } catch (confirmationError) {
      if (alive.current) setError(practiceEventError(confirmationError, 'This verification link is invalid or expired. Request a new link for the same account.'));
    } finally { if (alive.current) setBusy(false); }
  };
  return <main className="practice-event-verification"><section className="practice-event-dialog" aria-labelledby="event-verify-heading">
    <span className="practice-event-brand">CashOutAI</span>
    <span className="practice-event-kicker">EMAIL VERIFICATION</span>
    <h1 id="event-verify-heading">{result ? 'Your email is verified.' : 'Confirm your practice access.'}</h1>
    {result ? <div role="status"><p>{result.access === 'existing' ? 'Your existing membership remains active with its original terms.' : `Your event access is ready through ${eventDeadlineLabel(result.ends_at)}.`}</p><p>Sign in to your existing account{result.username ? ` as ${result.username}` : ''}. Your password, profile, and history stay with that account.</p><button type="button" className="practice-event-primary" onClick={() => onSignIn(result.username)}>Continue to sign in</button></div> : <>
      <p>Use the button below to verify ownership of the email that received this link. This does not sign you in, change your password, or charge a payment.</p>
      {error && <p className="practice-event-error" role="alert">{error}</p>}
      <button type="button" className="practice-event-primary" onClick={confirm} disabled={busy}>{busy ? 'Confirming your email…' : 'Confirm my email'}</button>
      <div className="practice-event-actions"><button type="button" className="practice-event-text" disabled={busy} onClick={onRequest}>Request a new link</button><button type="button" className="practice-event-secondary" disabled={busy} onClick={() => onSignIn('')}>Back to sign in</button></div>
    </>}
    <p className="practice-event-footnote">CashOutAI event practice uses virtual funds. Your account remains saved after the event ends.</p>
  </section></main>;
}

export function PracticeEventMemberBanner({ status, onMembership }) {
  const view = eventMembershipPresentation(status);
  if (!view || view.kind !== 'active') return null;
  return <section className="practice-event-member" aria-label="Your practice event access">
    <div className="practice-event-member-summary"><div><span className="practice-event-kicker">YOUR FREE PRACTICE ACCESS</span><p>Through <strong>{eventDeadlineLabel(view.endsAt)}</strong></p></div><button type="button" className="practice-event-secondary" onClick={onMembership}>Become a member ↗</button></div>
    <details className="practice-event-guide"><summary>First practice? Start here.</summary><ol><li><strong>Read the room.</strong> Choose a bot tab. Check its source and quote time, then inspect a bot entry and the contract’s target and expiry.</li><li><strong>Use virtual funds.</strong> The shared practice account begins at $100. Choose the YES or NO outcome side, review the displayed quote and amount, then place a practice entry.</li><li><strong>Review and learn.</strong> Compare your result with the bot’s entry and save a lesson in the community. Reset the virtual $100 to start a new attempt whenever you want.</li></ol><p>Recorded and unavailable feeds are labeled. Practice results are educational and do not promise a real-money return.</p></details>
  </section>;
}
