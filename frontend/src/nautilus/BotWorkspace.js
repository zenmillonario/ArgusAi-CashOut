import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import './nautilus.css';

const ASSETS = {
  BTC: { name: 'Bitcoin', mark: '₿', color: '#f2ae54' },
  ETH: { name: 'Ethereum', mark: 'Ξ', color: '#a99cff' },
  SOL: { name: 'Solana', mark: '◎', color: '#79e6c6' },
  XRP: { name: 'XRP', mark: '×', color: '#80bcf1' },
  DOGE: { name: 'Dogecoin', mark: 'Ð', color: '#e7ce78' },
};
const valid = value => typeof value === 'number' && Number.isFinite(value);
const currency = (value, decimals = 2) => valid(value)
  ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(value)
  : '—';
const signedCash = value => valid(value) ? `${value > 0 ? '+' : value < 0 ? '−' : ''}${currency(Math.abs(value))}` : '—';
const percent = value => valid(value) ? `${value > 0 ? '+' : ''}${value.toFixed(1)}%` : '—';
const cents = value => valid(value) ? `${(value * 100).toLocaleString('en-US', { maximumFractionDigits: 2 })}¢` : '—';
const price = value => currency(value, valid(value) && value < 10 ? 4 : 2);
const timestamp = value => typeof value === 'number' ? (value < 1e12 ? value * 1000 : value) : Date.parse(value);
const clock = value => {
  const ms = timestamp(value);
  return Number.isFinite(ms) ? new Date(ms).toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit' }) : '—';
};

function Icon({ name, size = 18, ...props }) {
  const icons = {
    expand: <><path d="M8 3H3v5M16 3h5v5M21 16v5h-5M3 16v5h5" /></>,
    collapse: <><path d="M3 8h5V3M21 8h-5V3M16 21v-5h5M8 21v-5H3" /></>,
    monitor: <><rect x="3" y="4" width="18" height="13" rx="2" /><path d="M8 21h8M12 17v4" /></>,
    reset: <><path d="M3 10a9 9 0 1 1 2.6 8.4M3 4v6h6" /></>,
    send: <><path d="m21 3-7 18-4-7-7-4L21 3ZM10 14l5-5" /></>,
    arrow: <><path d="M5 12h14m-6-6 6 6-6 6" /></>,
    target: <><circle cx="12" cy="12" r="7" /><circle cx="12" cy="12" r="2" /><path d="M12 2v3m10 7h-3M12 22v-3M2 12h3" /></>,
    chat: <><path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5H4l-2 2V11.5a9.5 9.5 0 0 1 19 0Z" /><path d="M7 11h10M7 15h6" /></>,
    pulse: <><path d="M2 12h4l3-7 5 14 3-7h5" /></>,
    chevron: <path d="m6 9 6 6 6-6" />,
    book: <><path d="M3 4h6a4 4 0 0 1 3 2 4 4 0 0 1 3-2h6v16h-6a4 4 0 0 0-3 2 4 4 0 0 0-3-2H3V4Z" /><path d="M12 6v16" /></>,
    close: <path d="m6 6 12 12M6 18 18 6" />,
    shield: <><path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z" /><path d="m8 12 3 3 5-6" /></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{icons[name] || icons.pulse}</svg>;
}

function FeedBadge({ mode, updatedAt, status }) {
  const labels = { live: 'Live feed', replay: 'Recorded PAPER run', demo: 'Preview · sample data', offline: 'Feed offline', stale: 'Feed delayed' };
  return <span className={`nw-feed-badge nw-feed-${mode || 'offline'}`} title={updatedAt ? `Source updated ${clock(updatedAt)}` : 'Waiting for a source update'}><span className="nw-status-dot" />{labels[mode] || status || 'Feed offline'}</span>;
}

function NautilusCanvas({ native, span, television, asset, onSelectTrade, chartRef }) {
  const canvasRef = useRef(null);
  const tooltipRef = useRef(null);
  const latestData = useRef(native);
  const selectRef = useRef(onSelectTrade);
  const [ready, setReady] = useState(false);
  const [failure, setFailure] = useState('');
  latestData.current = native;
  selectRef.current = onSelectTrade;

  useEffect(() => {
    let disposed = false;
    const mount = () => {
      if (disposed || chartRef.current || !window.NautilusChart || !canvasRef.current || !tooltipRef.current) return;
      try {
        const chart = new window.NautilusChart(canvasRef.current, tooltipRef.current, trade => selectRef.current?.(trade));
        chart.focusVisual = true;
        chart.fontScale = window.innerWidth <= 540 ? 0.88 : 1.1;
        chart.showLookingGlass = true;
        chart.setSpan(span * 900, { persist: false });
        chartRef.current = chart;
        if (latestData.current) chart.setData(latestData.current);
        setReady(true);
      } catch (error) {
        setFailure('The chart could not load. The rest of the room is available.');
      }
    };
    mount();
    window.addEventListener('nautilus:ready', mount);
    return () => {
      disposed = true;
      window.removeEventListener('nautilus:ready', mount);
      const chart = chartRef.current;
      if (chart?.destroy) chart.destroy();
      else if (chart) {
        chart.resizeObserver?.disconnect();
        window.cancelAnimationFrame(chart.raf);
        window.clearTimeout(chart.pulseTimer);
        chart.requestDraw = () => {};
      }
      chartRef.current = null;
    };
    // The native chart persists while asset data changes, preserving zoom and avoiding duplicate listeners.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (chartRef.current) {
      try { chartRef.current.setData(native || { run: { run_id: `offline-${asset}` }, candles: [], emas: [], trades: [], quotes: [], market: {} }); setFailure(''); }
      catch (error) { setFailure('This chart snapshot is incomplete. Waiting for the next update.'); }
    }
  }, [native, asset, chartRef, ready]);

  useEffect(() => {
    if (chartRef.current) {
      chartRef.current.setSpan(span * 900, { persist: false });
      chartRef.current.toLive();
    }
  }, [span, chartRef, ready]);

  useEffect(() => {
    const updateFont = () => {
      if (!chartRef.current) return;
      chartRef.current.fontScale = window.innerWidth <= 540 ? 0.88 : television ? 1.4 : 1.1;
      chartRef.current.requestDraw();
    };
    updateFont();
    window.addEventListener('resize', updateFont);
    return () => window.removeEventListener('resize', updateFont);
  }, [television, chartRef, ready]);

  const hasData = Array.isArray(native?.candles) && native.candles.length > 0;
  return <div className="nw-chart-host">
    <canvas className="nw-native-canvas" ref={canvasRef} tabIndex={0} aria-label={`${asset} Nautilus chart. Arrow keys pan, plus and minus zoom, Home follows the latest data.`} />
    <div className="nw-chart-tooltip hidden" ref={tooltipRef} role="status" />
    {(!ready || !hasData || failure) && <div className="nw-chart-empty"><div className="nw-empty-orbit"><Icon name="pulse" size={30} /></div><strong>{failure || (!ready ? 'Preparing Nautilus' : 'Waiting for the bot feed')}</strong><span>{!failure && (hasData ? 'Opening the recorded chart' : 'The chart will appear when a source snapshot is available.')}</span></div>}
  </div>;
}

function CurrentPosition({ snapshot }) {
  const position = snapshot?.position;
  const pnl = position?.netPnl;
  return <section className="nw-panel nw-position-panel" aria-label="Bot current position">
    <div className="nw-panel-heading"><h3>Current position</h3><span className="nw-mini-label">BOT · PAPER</span></div>
    {position ? <>
      <div className="nw-position-main"><span className={`nw-side-pill nw-side-${String(position.side).toLowerCase()}`}>{String(position.side).toUpperCase()}</span><span className={`nw-position-pnl ${valid(pnl) && pnl < 0 ? 'nw-negative' : 'nw-positive'}`}>{signedCash(pnl)}<small>{percent(position.netReturnPct)}</small></span></div>
      <dl className="nw-position-details"><div><dt>Entry</dt><dd>{cents(position.entryPrice)}</dd></div><div><dt>Current bid</dt><dd>{cents(position.currentBid)}</dd></div><div><dt>Contracts</dt><dd>{valid(position.quantity) ? position.quantity.toLocaleString() : '—'}</dd></div></dl>
      {(position.reason || snapshot.reason) && <p className="nw-position-reason"><span className="nw-status-dot" />{position.reason || snapshot.reason}</p>}
    </> : <div className="nw-waiting-position"><Icon name="target" size={25} /><div><strong>{snapshot?.status || 'Waiting for a setup'}</strong><p>{snapshot?.reason || 'No open bot position in this snapshot.'}</p></div></div>}
  </section>;
}

function BotTrades({ trades = [], onInspectTrade, selectedTrade }) {
  const recent = (Array.isArray(trades) ? [...trades] : []).slice(-4).reverse();
  return <section className="nw-panel nw-trades-panel" aria-label="Past bot trades">
    <div className="nw-panel-heading"><h3>Past trades</h3><span className="nw-mini-label">BOT · NET</span></div>
    <div className="nw-trade-table"><div className="nw-trade-table-head"><span>Side / entry</span><span>Exit</span><span>Return</span></div>
      {recent.length ? recent.map((trade, index) => <button type="button" key={trade.id || index} className={`nw-trade-row ${selectedTrade?.id === trade.id && trade.id ? 'is-selected' : ''}`} onClick={() => onInspectTrade?.(trade)} disabled={!onInspectTrade} aria-label={`Inspect ${trade.side} trade, return ${percent(trade.netReturnPct)}`}><span><b className={`nw-trade-side nw-${String(trade.side).toLowerCase()}`}>{String(trade.side).toUpperCase()}</b><small>{cents(trade.entryPrice)}</small></span><span>{cents(trade.exitPrice)}<small>{clock(trade.closedAt)}</small></span><span className={trade.netPnl < 0 ? 'nw-negative' : 'nw-positive'}><b>{percent(trade.netReturnPct)}</b><small>{signedCash(trade.netPnl)}</small></span></button>) : <div className="nw-empty-trades">Completed trades will appear here.</div>}
    </div>
  </section>;
}

function PracticeBox({ asset, snapshot, practice = {}, selection, onBuyPractice, onClosePractice, onResetPractice }) {
  const [side, setSide] = useState('YES');
  const [budget, setBudget] = useState('25');
  const [exitPrice, setExitPrice] = useState('');
  const [resetOpen, setResetOpen] = useState(false);
  const [calculatorOpen, setCalculatorOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [actionError, setActionError] = useState('');
  const [notice, setNotice] = useState('');
  const panelRef = useRef(null);
  const quotes = snapshot?.quotes || {};
  const quote = quotes[side.toLowerCase()] || {};
  const positions = (practice.positions || []).filter(position => position.asset === asset && position.quantity > 0);
  const needsSettlement = position => snapshot?.practiceMode !== 'replay' && Boolean(snapshot?.contract?.id)
    && (position.contractId !== snapshot.contract.id || (Number.isFinite(timestamp(snapshot.contract.closeTime)) && timestamp(snapshot.contract.closeTime) <= Date.now()));
  const amount = Number(budget);
  const purchase = useMemo(() => {
    if (!valid(quote.ask)) return { error: 'Waiting for an available ask quote.' };
    if (!Number.isFinite(amount) || amount <= 0) return { error: 'Enter a budget greater than zero.' };
    if (!practice.quotePurchase) return { error: 'Practice pricing is not connected yet.' };
    try { return practice.quotePurchase({ asset, contractId: snapshot?.contract?.id, side, budget: amount, ask: quote.ask }) || {}; }
    catch (error) { return { error: error.message || 'This practice trade is unavailable.' }; }
  }, [quote.ask, amount, practice, asset, snapshot?.contract?.id, side]);
  const fee = purchase.fees ?? purchase.fee;
  const hypotheticalExit = exitPrice === '' ? quote.bid : Number(exitPrice) / 100;
  let estimatedExitFee = valid(practice.exitFee) ? practice.exitFee : null;
  if (practice.estimateExitFee && valid(purchase.quantity) && valid(hypotheticalExit)) {
    try { estimatedExitFee = Number(practice.estimateExitFee({ quantity: purchase.quantity, price: hypotheticalExit })); }
    catch (error) { estimatedExitFee = null; }
  }
  const projectedPnl = valid(hypotheticalExit) && hypotheticalExit >= 0 && hypotheticalExit <= 1 && valid(purchase.quantity) && valid(purchase.totalCost) && valid(estimatedExitFee) ? purchase.quantity * hypotheticalExit - estimatedExitFee - purchase.totalCost : null;
  const projectedReturn = valid(projectedPnl) && purchase.totalCost > 0 ? projectedPnl / purchase.totalCost * 100 : null;
  const disabledReason = practice.disabledReason || (practice.ready === false ? 'Loading your practice account…' : null) || purchase.error || (!snapshot?.contract?.id ? 'Waiting for a contract.' : null);
  const busy = pending || practice.busy;
  const canBuy = !busy && !disabledReason && onBuyPractice && purchase.quantity > 0 && purchase.canAfford !== false;
  const budgetAssumption = practice.budgetLabel || (practice.feesIncluded === false || /excluded|not included/i.test(practice.feeLabel || '') ? 'fees excluded' : 'fees included');
  const runAction = async (action, success) => {
    setPending(true); setActionError(''); setNotice('');
    try {
      const result = await action();
      if (result === false) { setActionError(practice.error || 'The practice update was not accepted. Please try again.'); return false; }
      setNotice(success);
      return true;
    }
    catch (error) { setActionError(error.message || 'The practice action could not be completed.'); }
    finally { setPending(false); }
  };
  useEffect(() => { setActionError(''); setNotice(''); setExitPrice(''); setResetOpen(false); }, [asset]);
  useEffect(() => {
    if (!selection || selection.asset !== asset || !['YES', 'NO'].includes(selection.side)) return;
    setSide(selection.side);
    setActionError('');
    setNotice(`${selection.side} selected. Review the quote and budget, then choose whether to practice.`);
    panelRef.current?.scrollIntoView({ block: 'nearest', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
    panelRef.current?.querySelector('input')?.focus({ preventScroll: true });
  }, [selection, asset]);

  return <section ref={panelRef} className="nw-panel nw-practice-panel" aria-label="Your practice calculator">
    <div className="nw-panel-heading"><h3><Icon name="book" size={16} />Your practice</h3><button className="nw-icon-button nw-reset-button" type="button" onClick={() => setResetOpen(!resetOpen)} aria-label="Reset practice balance to one hundred dollars" aria-expanded={resetOpen} title="Start again with $100"><Icon name="reset" size={15} /><span>Reset $100</span></button></div>
    {resetOpen && <div className="nw-reset-confirm" role="group" aria-label="Confirm practice reset"><strong>Start again with $100?</strong><p>This starts a fresh attempt and clears your practice positions and history across all five bots.</p><div><button type="button" className="nw-button nw-button-subtle" onClick={() => setResetOpen(false)}>Keep practicing</button><button type="button" className="nw-button nw-button-primary" disabled={busy || practice.ready === false || !onResetPractice} onClick={() => runAction(async () => { const result = await onResetPractice(); if (result !== false) setResetOpen(false); return result; }, 'New $100 practice attempt started.')}>Reset</button></div></div>}
    <div className="nw-practice-balance"><div><span className="nw-eyebrow">Practice equity</span><strong>{currency(practice.equity)}</strong></div><span className={`nw-balance-return ${valid(practice.equity) && practice.equity < 100 ? 'nw-negative' : 'nw-positive'}`}>{valid(practice.equity) ? signedCash(practice.equity - 100) : 'Unpriced'}</span></div>
    <div className="nw-practice-cash"><span>Available cash <b>{currency(practice.cash)}</b></span><span>Realized <b className={practice.realizedPnl < 0 ? 'nw-negative' : ''}>{signedCash(practice.realizedPnl)}</b></span></div>
    <div className="nw-side-selector" role="group" aria-label="Choose practice side">
      {['YES', 'NO'].map(value => <button type="button" key={value} className={`nw-side-option nw-side-option-${value.toLowerCase()} ${side === value ? 'is-active' : ''}`} aria-pressed={side === value} onClick={() => { setSide(value); setActionError(''); }}><span>{value}</span><strong>{cents(quotes[value.toLowerCase()]?.ask)}</strong><small>ask</small></button>)}
    </div>
    <label className="nw-field-label" htmlFor={`practice-budget-${asset}`}>Practice budget <span>{budgetAssumption}</span></label>
    <div className="nw-budget-row"><div className="nw-money-field"><span>$</span><input id={`practice-budget-${asset}`} aria-label="Practice budget in dollars" type="number" min="0.01" step="0.01" inputMode="decimal" value={budget} onChange={event => { setBudget(event.target.value); setActionError(''); }} /></div><div className="nw-contract-count"><strong>{valid(purchase.quantity) ? purchase.quantity.toLocaleString() : '—'}</strong><span>contracts</span></div></div>
    <div className="nw-practice-cost"><span>Total <b>{currency(purchase.totalCost)}</b></span><span>Fee <b>{currency(fee)}</b></span><span>Exit bid <b>{cents(quote.bid)}</b></span></div>
    <button type="button" className={`nw-practice-buy nw-buy-${side.toLowerCase()}`} disabled={!canBuy} onClick={() => runAction(() => onBuyPractice({ asset, contractId: snapshot.contract.id, side, budget: amount }), `${side} practice position opened.`)}><span>{busy ? 'Updating practice…' : `Practice ${side}`}</span><Icon name="arrow" size={18} /></button>
    {disabledReason && <p className="nw-practice-hint">{disabledReason}</p>}
    <p className="nw-fee-note">{practice.feeLabel || 'Practice fees are configured separately.'}</p>
    <button type="button" className="nw-calculator-toggle" onClick={() => setCalculatorOpen(!calculatorOpen)} aria-expanded={calculatorOpen}><span>What if I exit at…</span><Icon name="chevron" size={14} style={{ transform: calculatorOpen ? 'rotate(180deg)' : 'none' }} /></button>
    {calculatorOpen && <div className="nw-exit-calculator"><label htmlFor={`practice-exit-${asset}`}>Hypothetical exit price</label><div><div className="nw-money-field"><input id={`practice-exit-${asset}`} type="number" min="0" max="100" step="0.1" inputMode="decimal" placeholder={valid(quote.bid) ? String(Math.round(quote.bid * 1000) / 10) : '0'} value={exitPrice} onChange={event => setExitPrice(event.target.value)} /><span>¢</span></div><strong className={projectedPnl < 0 ? 'nw-negative' : 'nw-positive'}>{signedCash(projectedPnl)}<small>{percent(projectedReturn)}</small></strong></div><p>{valid(estimatedExitFee) ? `Includes ${currency(estimatedExitFee)} estimated exit fee.` : 'An exit-fee estimate is needed to calculate net profit.'}</p></div>}
    {positions.length > 0 && <div className="nw-your-positions"><span className="nw-eyebrow">Your {asset} practice positions</span>{positions.map(position => <div className="nw-practice-position" key={position.id}><div><b className={`nw-${String(position.side).toLowerCase()}`}>{position.side}</b><span>{position.quantity} × {cents(position.entryPrice)}</span><small className={position.unrealizedPnl < 0 ? 'nw-negative' : 'nw-positive'}>{signedCash(position.unrealizedPnl)}</small></div>{needsSettlement(position) ? <span className="nw-practice-hint" style={{ padding: 0, fontSize: 9, maxWidth: 100 }}>Awaiting verified settlement</span> : <button type="button" disabled={busy || practice.ready === false || !valid(position.currentBid) || !onClosePractice} onClick={() => runAction(() => onClosePractice(position.id), 'Practice position closed.')} title={valid(position.currentBid) ? `Sell at the quoted bid of ${cents(position.currentBid)}` : 'A current bid is needed to close this practice position'}>Close <span>{cents(position.currentBid)}</span></button>}</div>)}{positions.some(needsSettlement) && <p className="nw-fee-note">These funds stay reserved. Automatic settlement is not connected in this draft.</p>}</div>}
    <div className="nw-practice-message" aria-live="polite">{actionError ? <span className="nw-negative" role="alert">{actionError}</span> : notice ? <span className="nw-positive">{notice}</span> : null}</div>
    <div className="nw-practice-foot"><Icon name="shield" size={12} /><span>Simulated money · one balance across five bots</span></div>
  </section>;
}

function sourceEntry(snapshot, selectedTrade) {
  const completeEntry = entry => entry && ['YES', 'NO'].includes(entry.side) && valid(entry.entry_ts) && valid(entry.entry_ask);
  const selected = selectedTrade?.nativeTrade || selectedTrade?.native || selectedTrade;
  const positions = (snapshot.native?.positions || []).filter(entry => completeEntry(entry) && entry.closed !== true && (entry.remaining_qty ?? entry.qty ?? 0) > 0);
  const trades = (snapshot.native?.trades || snapshot.trades?.map(trade => trade.nativeTrade || trade.native).filter(Boolean) || []).filter(completeEntry);
  const position = [...positions].sort((a, b) => b.entry_ts - a.entry_ts)[0];
  const entry = completeEntry(selected) ? selected : position || [...trades].sort((a, b) => b.entry_ts - a.entry_ts)[0];
  if (!entry) return null;
  const current = snapshot.mode === 'live' && positions.some(p => p === entry || (p.entry_ts === entry.entry_ts && p.ticker === entry.ticker && p.side === entry.side)) && entry.ticker === snapshot.contract?.id;
  return { native: entry, side: entry.side, ask: entry.entry_ask, quantity: entry.original_qty ?? entry.qty, enteredAt: entry.entry_ts, current, selected: completeEntry(selected), reason: entry.entry_context?.reason || entry.mission?.reason || entry.entry_reason || null };
}

function EntryGuide({ asset, snapshot, selectedTrade, onInspect, onPracticeSide }) {
  const entry = sourceEntry(snapshot, selectedTrade);
  return <section className="nw-panel nw-entry-guide" aria-label={`${asset} bot entry study guide`}>
    <div className="nw-guide-heading"><div><Icon name="book" size={15} /><h3>Learn from the entry</h3></div><span>{entry ? entry.current ? 'CURRENT BOT ENTRY' : entry.selected ? 'SELECTED RECORDING' : 'LATEST RECORDED ENTRY' : 'AWAITING AN ENTRY'}</span></div>
    {entry ? <>
      <div className="nw-guide-content"><div className="nw-guide-facts"><span className={`nw-guide-side nw-side-${entry.side.toLowerCase()}`}>{entry.side}</span><div><span>Entry ask</span><strong>{cents(entry.ask)}</strong></div><div><span>Contracts</span><strong>{valid(entry.quantity) ? entry.quantity.toLocaleString() : '—'}</strong></div><div><span>Entered · ET</span><strong>{clock(entry.enteredAt)}</strong></div></div><div className="nw-guide-actions"><button type="button" className="nw-button" onClick={() => onInspect(entry.native)}><Icon name="target" size={14} />Inspect entry</button><button type="button" className="nw-button nw-guide-practice" title={`Select ${entry.side} in your practice calculator`} onClick={() => onPracticeSide(entry.side)}>Choose {entry.side}<Icon name="arrow" size={14} /></button></div></div>
      <p className="nw-guide-reason">Compare the entry with the trend and the contract spread.</p>
      <div className="nw-guide-foot"><span>Recorded entry for study · practice uses the calculator’s quote.</span><span><b>Observe</b><i>→</i><b>Choose</b><i>→</i><b>Review</b></span></div>
    </> : <div className="nw-guide-empty"><span>The bot’s next recorded entry will appear here, ready to inspect on Nautilus.</span><span>Observe the chart. Choose a side. Review your practice.</span></div>}
  </section>;
}

function ChatRoomDialog({ asset, onClose, ...chatProps }) {
  const dialogRef = useRef(null);
  useEffect(() => {
    const previousFocus = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const target = dialogRef.current?.querySelector('input:not([disabled])') || dialogRef.current?.querySelector('button');
    target?.focus({ preventScroll: true });
    return () => {
      document.body.style.overflow = previousOverflow;
      if (previousFocus?.isConnected) previousFocus.focus?.({ preventScroll: true });
    };
  }, []);
  const keyDown = event => {
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); onClose(); return; }
    if (event.key !== 'Tab') return;
    const items = [...(dialogRef.current?.querySelectorAll('button:not([disabled]), input:not([disabled]), [tabindex="0"]') || [])];
    const first = items[0], last = items[items.length - 1];
    if (!first) { event.preventDefault(); return; }
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  };
  return <div className="nw-chat-modal-scrim" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
    <div ref={dialogRef} className="nw-chat-modal" role="dialog" aria-modal="true" aria-labelledby={`chat-title-${asset}`} aria-describedby={`chat-description-${asset}`} onKeyDown={keyDown} tabIndex={-1}>
      <div className="nw-chat-modal-heading"><div><span className="nw-eyebrow">CASHOUTAI COMMUNITY</span><h2 id={`chat-title-${asset}`}><Icon name="chat" size={23} />{asset} room</h2><p id={`chat-description-${asset}`}>Watch the bot. Share the setup. Learn together.</p></div><button type="button" className="nw-chat-modal-close" onClick={onClose} aria-label={`Close ${asset} chat room`}><Icon name="close" size={20} /></button></div>
      <BotChat asset={asset} {...chatProps} />
      <div className="nw-chat-modal-foot"><span>{chatProps.chatStatus || (chatProps.chatMode === 'preview' ? 'Preview chat · saved in this browser' : 'Community messages')}</span><span>Esc to return to Nautilus</span></div>
    </div>
  </div>;
}

export function RoomChatDock({ asset, messages = [], onOpenRoom, ...chatProps }) {
  const [open, setOpen] = useState(false);
  const [distance, setDistance] = useState(0);
  const viewportRef = useRef(null);
  const groupRef = useRef(null);
  const recent = messages.slice(-4);
  const signature = recent.map(message => `${message.id || ''}:${message.content || message.body || message.text || ''}`).join('|');
  useEffect(() => {
    const measure = () => {
      const width = groupRef.current?.scrollWidth || 0;
      const visible = viewportRef.current?.clientWidth || 0;
      setDistance(messages.length > 0 && width > visible + 4 ? width : 0);
    };
    measure();
    const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(measure) : null;
    if (viewportRef.current) observer?.observe(viewportRef.current);
    if (groupRef.current) observer?.observe(groupRef.current);
    window.addEventListener('resize', measure);
    return () => { observer?.disconnect(); window.removeEventListener('resize', measure); };
  }, [signature, messages.length]);
  const renderMessages = () => recent.map((message, index) => <span className="nw-strip-message" key={message.id || index}><b>{message.isSelf ? 'You' : message.username || message.author || 'Member'}</b><span>{String(message.content || message.body || message.text || '').slice(0, 180)}{String(message.content || message.body || message.text || '').length > 180 ? '…' : ''}</span></span>);
  return <>
    <button type="button" className={`nw-chat-strip ${distance > 0 ? 'nw-strip-moving' : ''} ${open ? 'is-open' : ''}`} onClick={() => onOpenRoom ? onOpenRoom(asset) : setOpen(true)} aria-label={`Open ${asset} chat room${messages.length ? `, ${messages.length} recent messages` : ', no messages yet'}`} aria-haspopup={onOpenRoom ? undefined : 'dialog'} aria-expanded={onOpenRoom ? undefined : open}>
      <span className="nw-strip-label"><Icon name="chat" size={15} /><strong>{asset} room</strong><span className="nw-room-dot" /></span>
      <span className="nw-strip-viewport" ref={viewportRef}><span className="nw-strip-track" style={{ '--strip-distance': `${distance}px`, '--strip-duration': `${Math.max(36, distance / 16)}s` }}><span className="nw-strip-group" ref={groupRef}>{recent.length ? renderMessages() : <span className="nw-strip-empty">No messages yet. Open the room and start a conversation.</span>}</span>{distance > 0 && <span className="nw-strip-group nw-strip-copy" aria-hidden="true">{renderMessages()}</span>}</span></span>
      <span className="nw-strip-open">Open chat<Icon name="arrow" size={14} /></span>
    </button>
    {open && <ChatRoomDialog asset={asset} messages={messages} onClose={() => setOpen(false)} {...chatProps} />}
  </>;
}

function BotChat({ asset, messages = [], onSendChat, chatMode = 'community', chatStatus, currentUser }) {
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const scrollRef = useRef(null);
  const latest = useRef(messages.length);
  useEffect(() => { setDraft(''); setError(''); }, [asset]);
  useEffect(() => {
    const el = scrollRef.current;
    if (el && (messages.length !== latest.current || el.scrollHeight - el.scrollTop - el.clientHeight < 100)) el.scrollTop = el.scrollHeight;
    latest.current = messages.length;
  }, [messages, asset]);
  const submit = async event => {
    event.preventDefault();
    const text = draft.trim();
    if (!text || sending || !onSendChat) return;
    setSending(true); setError('');
    try { const result = await onSendChat(text); if (result === false) { setError('Your message was not sent. Please try again.'); return; } setDraft(''); }
    catch (err) { setError(err.message || 'Your message could not be sent.'); }
    finally { setSending(false); }
  };
  return <section className="nw-panel nw-chat-panel" aria-label={`${asset} chat room`}>
    <div className="nw-panel-heading"><h3><Icon name="chat" size={16} />{asset} room<span className="nw-room-dot" /></h3><span className="nw-chat-status">{chatStatus || (chatMode === 'preview' ? 'Preview chat · this browser' : 'Community chat')}</span></div>
    <div className="nw-chat-messages" ref={scrollRef} role="log" aria-live="polite" aria-relevant="additions text">{messages.length ? messages.map((message, index) => {
      const author = message.username || message.author || 'Member';
      const isSelf = message.isSelf || (currentUser?.id && message.user_id === currentUser.id);
      return <div key={message.id || index} className={`nw-chat-message ${message.system ? 'nw-system-message' : ''}`}><div className={`nw-chat-avatar ${isSelf ? 'nw-chat-avatar-self' : ''}`}>{message.system ? <Icon name="pulse" size={13} /> : author.slice(0, 1).toUpperCase()}</div><div className="nw-chat-message-body"><div><strong>{isSelf ? 'You' : author}</strong><time>{clock(message.timestamp || message.createdAt)}</time></div><p>{message.content || message.body || message.text}</p></div></div>;
    }) : <div className="nw-chat-empty"><Icon name="chat" size={24} /><p>Watch the move. Share what you see.</p><span>Start a conversation in the {asset} room.</span></div>}</div>
    <form className="nw-chat-composer" onSubmit={submit}><label className="nw-sr-only" htmlFor={`room-message-${asset}`}>Message the {asset} room</label><input id={`room-message-${asset}`} placeholder={`Message the ${asset} room…`} value={draft} onChange={event => setDraft(event.target.value)} maxLength={1000} autoComplete="off" disabled={!onSendChat} /><button type="submit" disabled={!draft.trim() || sending || !onSendChat} aria-label={sending ? 'Sending message' : `Send message to ${asset} room`}><Icon name="send" size={17} /></button></form>
    {error && <p className="nw-chat-error" role="alert">{error}</p>}
  </section>;
}

/**
 * A single bot's room. native data is passed unchanged into the shipped Nautilus renderer.
 * Practice values are a dollar-based view model; account persistence and execution belong to the caller.
 */
export default function BotWorkspace({
  asset = 'BTC', snapshot = {}, practice = {}, account, chatMessages = [], chatMode = 'community', chatStatus,
  currentUser, onSendChat, onBuyPractice, onClosePractice, onResetPractice, onRequestFullscreen,
  onInspectTrade, fullscreen = false,
}) {
  const info = ASSETS[asset] || { name: asset, mark: asset.slice(0, 1), color: '#80cfce' };
  const workspaceRef = useRef(null);
  const chartRef = useRef(null);
  const [span, setSpan] = useState(3);
  const [television, setTelevision] = useState(false);
  const [nativeFullscreen, setNativeFullscreen] = useState(false);
  const [focusMode, setFocusMode] = useState(false);
  const [selectedTrade, setSelectedTrade] = useState(null);
  const [practiceSelection, setPracticeSelection] = useState(null);
  const [now, setNow] = useState(Date.now());
  const isFull = fullscreen || nativeFullscreen || focusMode;
  const mode = snapshot.mode || 'offline';
  const normalizedPractice = Object.keys(practice).length ? practice : (account || {});

  useEffect(() => {
    const update = () => setNativeFullscreen(document.fullscreenElement === workspaceRef.current);
    document.addEventListener('fullscreenchange', update);
    const escape = event => { if (event.key === 'Escape') setFocusMode(false); };
    window.addEventListener('keydown', escape);
    return () => { document.removeEventListener('fullscreenchange', update); window.removeEventListener('keydown', escape); };
  }, []);
  useEffect(() => {
    if (mode !== 'live') return undefined;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [mode]);
  useEffect(() => { setSelectedTrade(null); setPracticeSelection(null); chartRef.current?.toLive(); }, [asset]);
  useEffect(() => {
    if (!focusMode) return undefined;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = previous; };
  }, [focusMode]);

  const requestFullscreen = async () => {
    if (focusMode) { setFocusMode(false); return; }
    if (document.fullscreenElement === workspaceRef.current) { await document.exitFullscreen?.(); return; }
    if (onRequestFullscreen) { try { await onRequestFullscreen(workspaceRef.current); } catch (error) { setFocusMode(true); } return; }
    if (workspaceRef.current?.requestFullscreen) {
      try { await workspaceRef.current.requestFullscreen(); }
      catch (error) { setFocusMode(true); }
    } else setFocusMode(true);
  };
  const inspectTrade = useCallback(trade => {
    setSelectedTrade(trade);
    if (trade.native || trade.nativeTrade || valid(trade.entry_ts)) chartRef.current?.inspect(trade.native || trade.nativeTrade || trade);
    onInspectTrade?.(trade);
  }, [onInspectTrade]);
  const inspectEntry = nativeEntry => {
    inspectTrade(nativeEntry);
    if (chartRef.current && valid(nativeEntry.entry_ts)) {
      chartRef.current.end = nativeEntry.entry_ts + chartRef.current.viewSpan() / 2;
      chartRef.current.requestDraw();
      chartRef.current.canvas?.focus({ preventScroll: true });
      chartRef.current.canvas?.scrollIntoView({ block: 'nearest', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
    }
  };
  const end = timestamp(snapshot.contract?.closeTime);
  const remaining = mode === 'live' && Number.isFinite(end) ? Math.max(0, Math.floor((end - now) / 1000)) : snapshot.contract?.remainingSeconds;
  const timeLeft = valid(remaining) ? `${String(Math.floor(remaining / 60)).padStart(2, '0')}:${String(Math.floor(remaining % 60)).padStart(2, '0')}` : clock(snapshot.contract?.closeTime);
  const timeLabel = valid(remaining) ? 'Time remaining' : 'Contract close · ET';
  const native = snapshot.native;
  const latestPrice = snapshot.price ?? native?.market?.btc;

  return <div ref={workspaceRef} className={`nw-workspace ${television ? 'nw-tv' : ''} ${isFull ? 'nw-is-fullscreen' : ''} ${focusMode ? 'nw-focus-mode' : ''}`} style={{ '--asset-color': info.color }} data-asset={asset}>
    <div className="nw-workspace-toolbar">
      <div className="nw-room-title"><span className="nw-asset-mark">{info.mark}</span><div><div className="nw-title-line"><h2>{info.name}</h2><span>{asset} / USD</span></div><p>TACHYOS <span> / </span> NAUTILUS</p></div></div>
      <div className="nw-toolbar-actions"><FeedBadge mode={mode} updatedAt={snapshot.updatedAt} /><button className={`nw-button nw-tv-button ${television ? 'is-active' : ''}`} type="button" onClick={() => setTelevision(!television)} aria-pressed={television} title="Larger type for viewing across the room"><Icon name="monitor" /><span>TV mode</span></button><button className="nw-button nw-fullscreen-button" type="button" onClick={requestFullscreen} aria-label={isFull ? 'Exit full screen' : `Open ${asset} full screen`}><Icon name={isFull ? 'collapse' : 'expand'} /><span>{isFull ? 'Exit full screen' : 'Full screen'}</span></button></div>
    </div>
    <div className="nw-layout">
      <section className="nw-panel nw-chart-panel" aria-label={`${asset} Nautilus`}>
        <div className="nw-chart-topline"><div><span className="nw-eyebrow">{mode === 'live' ? 'Market price' : mode === 'offline' ? 'Market price' : 'Snapshot price'}</span><div className="nw-market-price">{price(latestPrice)}<span className="nw-market-pair">{asset}</span></div></div><div className="nw-chart-contract"><div><span className="nw-eyebrow">Contract target</span><strong>{price(snapshot.contract?.target ?? native?.market?.target)}</strong></div><div className="nw-countdown"><span className="nw-eyebrow">{timeLabel}</span><strong>{timeLeft}</strong></div></div></div>
        <div className="nw-chart-controls"><div className="nw-chart-legend"><span><i className="nw-legend-ema9" />NAEVYR <b>9</b></span><span><i className="nw-legend-ema30" />THAERYON <b>30</b></span><span className="nw-route-legend"><i className="nw-legend-route" />Looking Glass</span></div><div className="nw-range-controls" role="group" aria-label="Chart history range">{[1, 2, 3].map(count => <button type="button" key={count} onClick={() => setSpan(count)} className={span === count ? 'is-active' : ''} aria-pressed={span === count} title={`${count} contract${count > 1 ? 's' : ''} · ${count * 15} minutes`}>{count}<span>{count === 1 ? ' contract' : ' contracts'}</span></button>)}</div></div>
        <NautilusCanvas native={native} span={span} television={television} asset={asset} onSelectTrade={inspectTrade} chartRef={chartRef} />
        <div className="nw-chart-footer"><span><span className="nw-status-dot" />{snapshot.status || (mode === 'offline' ? 'Waiting for source data' : 'PAPER observation')}</span><div><button type="button" onClick={() => { chartRef.current?.fitPriceScale(); }} title="Fit the chart to observed prices">Fit chart</button><button type="button" onClick={() => { chartRef.current?.toLive(); setSelectedTrade(null); }} title="Follow the newest source snapshot"><Icon name="target" size={12} />Follow</button></div></div>
      </section>
      <aside className="nw-sidebar" aria-label="Bot activity and your practice"><CurrentPosition snapshot={snapshot} /><BotTrades trades={snapshot.trades} selectedTrade={selectedTrade} onInspectTrade={inspectTrade} /><PracticeBox asset={asset} snapshot={snapshot} practice={normalizedPractice} selection={practiceSelection} onBuyPractice={onBuyPractice} onClosePractice={onClosePractice} onResetPractice={onResetPractice} /></aside>
      <RoomChatDock key={asset} asset={asset} messages={chatMessages} onSendChat={onSendChat} chatMode={chatMode} chatStatus={chatStatus} currentUser={currentUser} />
      <EntryGuide asset={asset} snapshot={snapshot} selectedTrade={selectedTrade} onInspect={inspectEntry} onPracticeSide={side => setPracticeSelection({ asset, side, key: Date.now() })} />
    </div>
    <div className="nw-workspace-foot"><span><Icon name="shield" size={12} />PAPER trading · simulated funds</span><span>{mode === 'demo' ? 'Design preview — sample prices and positions' : mode === 'replay' ? 'Recorded source data — not a live feed' : snapshot.updatedAt ? `Source update ${clock(snapshot.updatedAt)}` : 'No source connected'}{isFull && <span className="nw-escape-hint"> · Esc to exit</span>}</span></div>
  </div>;
}
