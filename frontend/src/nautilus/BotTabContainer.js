import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import BotWorkspace from './BotWorkspace';
import { adaptNativeSnapshot, accountMarks, BOT_ASSETS } from './snapshotAdapter';
import { calculateAccountSummary, quotePurchase } from './practiceEngine';

let chartScriptPromise;
export function loadNautilusChart() {
  if (window.NautilusChart) return Promise.resolve();
  if (!chartScriptPromise) chartScriptPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = `${process.env.PUBLIC_URL || ''}/nautilus-chart.js`;
    script.onload = () => { window.dispatchEvent(new Event('nautilus:ready')); resolve(); };
    script.onerror = () => { chartScriptPromise = null; script.remove(); reject(new Error('The Nautilus chart could not load.')); };
    document.head.appendChild(script);
  });
  return chartScriptPromise;
}

export default function BotTabContainer({ asset, currentUser, apiBase }) {
  const [feeds, setFeeds] = useState({});
  const [clockTick, setClockTick] = useState(Date.now());
  const [ledger, setLedger] = useState(null);
  const [messages, setMessages] = useState([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const root = useRef(null);
  const activeRoom = useRef(asset);
  const activeUser = useRef(currentUser.id);
  activeRoom.current = asset;
  activeUser.current = currentUser.id;
  const headers = useCallback(() => ({ 'Content-Type': 'application/json', 'X-User-ID': currentUser.id, 'X-Session-ID': currentUser.active_session_id || '' }), [currentUser.id, currentUser.active_session_id]);
  const request = useCallback(async (path, options = {}) => {
    const controller = new AbortController();
    const cancel = () => controller.abort();
    const upstream = options.signal;
    if (upstream?.aborted) controller.abort();
    else upstream?.addEventListener('abort', cancel, { once: true });
    const timeout = setTimeout(cancel, 8000);
    try {
      const response = await fetch(`${apiBase}/nautilus${path}`, { ...options, signal: controller.signal, headers: headers(), cache: 'no-store' });
      const body = await response.json().catch(() => null);
      if (!response.ok) throw new Error(typeof body?.detail === 'string' ? body.detail : `Request failed (${response.status}).`);
      if (!body || typeof body !== 'object' || Array.isArray(body)) throw new Error('The server response was incomplete. Refresh and try again.');
      return body;
    } finally {
      clearTimeout(timeout);
      upstream?.removeEventListener('abort', cancel);
    }
  }, [apiBase, headers]);
  const refreshAccount = useCallback(async () => setLedger(await request('/practice')), [request]);

  useEffect(() => { loadNautilusChart().catch(e => setError(e.message)); }, []);
  useEffect(() => {
    const timer = setInterval(() => setClockTick(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    let disposed = false;
    let timer;
    let controller;
    const update = async () => {
      controller = new AbortController();
      const results = await Promise.allSettled(BOT_ASSETS.map(async symbol => {
        const result = await request(`/bots/${symbol}`, { signal: controller.signal });
        return [symbol, result];
      }));
      if (disposed) return;
      setFeeds(previous => {
        const next = Object.fromEntries(results.filter(r => r.status === 'fulfilled').map(r => r.value));
        for (let i = 0; i < results.length; i++) if (results[i].status === 'rejected') {
          const symbol = BOT_ASSETS[i];
          next[symbol] = { snapshot: previous[symbol]?.snapshot || null, receivedAt: previous[symbol]?.receivedAt, state: 'offline' };
        }
        return next;
      });
      timer = setTimeout(update, 3000);
    };
    update();
    return () => { disposed = true; clearTimeout(timer); controller?.abort(); };
  }, [request]);
  useEffect(() => { refreshAccount().catch(e => setError(e.message)); }, [refreshAccount]);
  useEffect(() => {
    let disposed = false;
    let timer;
    let controller;
    setMessages([]);
    const update = async () => {
      controller = new AbortController();
      try { const result = await request(`/chat/${asset}`, { signal: controller.signal }); if (!disposed) setMessages(result.messages || []); }
      catch (e) { if (!disposed) setError(e.message); }
      if (!disposed) timer = setTimeout(update, 5000);
    };
    update();
    return () => { disposed = true; clearTimeout(timer); controller?.abort(); };
  }, [asset, request]);
  useEffect(() => {
    const changed = () => setFullscreen(document.fullscreenElement === root.current);
    const key = event => { if (event.key === 'Escape') setExpanded(false); };
    document.addEventListener('fullscreenchange', changed); document.addEventListener('keydown', key);
    return () => { document.removeEventListener('fullscreenchange', changed); document.removeEventListener('keydown', key); };
  }, []);
  const toggleFullscreen = async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else if (expanded) setExpanded(false);
      else if (root.current?.requestFullscreen) await root.current.requestFullscreen();
      else setExpanded(true);
    } catch (_) { setExpanded(value => !value); }
  };
  const command = async (path, payload) => {
    if (busy || !ledger?.account) return false;
    setBusy(true); setError('');
    try {
      const result = await request(`/practice/${path}`, { method: 'POST', body: JSON.stringify({ ...payload, attemptId: ledger.account.attemptId, revision: ledger.revision, transactionId: crypto.randomUUID() }) });
      setLedger(result); return true;
    } catch (e) { setError(e.message); await refreshAccount().catch(() => {}); return false; }
    finally { setBusy(false); }
  };
  const snapshots = useMemo(() => Object.fromEntries(BOT_ASSETS.map(symbol => {
    const feed = feeds[symbol] || {};
    try { return [symbol, adaptNativeSnapshot(feed.snapshot, symbol, { state: feed.state || 'offline', receivedAt: feed.receivedAt, now: Date.now() / 1000 })]; }
    catch (_) { return [symbol, adaptNativeSnapshot(null, symbol)]; }
  })), [feeds, clockTick]);
  const account = ledger?.account;
  const summary = account ? calculateAccountSummary(account, accountMarks(account, snapshots)) : {};
  const snapshot = snapshots[asset] || adaptNativeSnapshot(null, asset);
  const practice = { ...summary, ready: Boolean(account), busy, exitFee: 0, feesIncluded: false, feeLabel: 'Fees excluded from this practice model', error,
    positions: (summary.positions || []).map(p => ({ ...p, entryPrice: p.entryPrice, currentBid: p.currentBid })),
    quotePurchase: ({ ask, budget }) => {
      if (!account) return { error: 'Loading your practice balance.' };
      if (!snapshot.canPractice) return { error: 'Practice entries need a current bot quote.' };
      try { const result = quotePurchase({ account, ask, budget, fee: 0 }); return { ...result, fees: result.fee }; }
      catch (e) { return { error: e.message }; }
    },
  };
  return <section id="cashout-bot-room" role="tabpanel" aria-labelledby={`tab-bot-${asset}`} ref={root} className={`cashout-room-shell ${expanded ? 'cashout-room-expanded' : ''}`}>
    {error && <div className="cashout-room-notice" role="status">{error}<button onClick={() => setError('')} aria-label="Dismiss status">×</button></div>}
    <BotWorkspace currentUser={currentUser} chatMode="community" asset={asset} snapshot={snapshot} account={account} practice={practice} chatMessages={messages} fullscreen={fullscreen || expanded}
      onRequestFullscreen={toggleFullscreen}
      onBuyPractice={values => command('buy', values)}
      onClosePractice={positionId => command('close', { positionId })}
      onResetPractice={() => command('reset', {})}
      onSendChat={async text => {
        const room = asset, user = currentUser.id;
        try {
          const result = await request(`/chat/${room}`, { method: 'POST', body: JSON.stringify({ text }) });
          if (activeRoom.current === room && activeUser.current === user) setMessages(old => old.some(message => message.id === result.message.id) ? old : [...old, result.message]);
          return true;
        } catch (e) { if (activeRoom.current === room && activeUser.current === user) setError(e.message); return false; }
      }} />
  </section>;
}
