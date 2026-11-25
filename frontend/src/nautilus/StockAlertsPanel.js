import React, { useEffect, useRef } from 'react';
import { normalizeAlertSymbol } from '../stockNotifications.mjs';

function formattedTime(value) {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? '' : date.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short' });
}

export function StockPushSettings({ state = {}, onToggle, preview = false }) {
  const busy = state.status === 'loading';
  const enabled = state.enabled === true;
  const connected = enabled && state.status === 'enabled';
  const needsBrowserChange = ['unsupported', 'needs-install', 'permission-denied'].includes(state.status);
  return <section className="sw-panel sw-push-settings" aria-labelledby="stock-push-heading">
    <div className="sw-panel-heading"><h3 id="stock-push-heading">Stock notifications</h3><span className={connected ? 'sw-push-on' : ''}>{connected ? 'ON' : enabled ? 'NEEDS SETUP' : 'OFF'}</span></div>
    <p>Only stock alerts notify you. Chat, reactions, and bot-room updates stay in the app.</p>
    <button type="button" className={connected ? 'is-enabled' : ''} disabled={preview || busy || !onToggle} onClick={() => onToggle(!connected)} aria-pressed={connected}>
      {busy ? 'Updating…' : connected ? 'Turn off stock notifications' : needsBrowserChange ? 'Check this browser again' : enabled ? 'Connect this browser' : 'Enable stock alerts'}
    </button>
    {enabled && !connected && <button type="button" className="sw-push-secondary" disabled={preview || busy || !onToggle} onClick={() => onToggle(false)}>Turn off stock notifications</button>}
    <p className="sw-push-status" role="status">{preview ? 'Push is available in the connected app. This preview does not send notifications.' : state.message || (connected ? 'Enabled for this login and browser.' : enabled ? 'Your account is opted in. Connect this browser to receive alerts here.' : 'Opt in on the device where you want to receive stock alerts.')}</p>
    {!preview && <small>One active login per account. Signing in on another device moves access there.</small>}
  </section>;
}

export default function StockAlertsPanel({ alerts = [], status = 'loading', error = '', onRefresh, onOpenSymbol, selectedAlertId = '', preview = false }) {
  const selected = useRef(null);
  const focusedAlert = useRef('');
  useEffect(() => {
    if (!selectedAlertId) { focusedAlert.current = ''; return; }
    if (!selected.current || focusedAlert.current === selectedAlertId) return;
    focusedAlert.current = selectedAlertId;
    selected.current.focus({ preventScroll: true });
    selected.current.scrollIntoView({ block: 'nearest', behavior: 'auto' });
  }, [selectedAlertId, alerts]);
  return <section className="sw-alert-panel" aria-labelledby="stock-alert-feed-heading" aria-busy={status === 'loading'}>
    <div className="sw-alert-heading"><div><span className="sw-kicker">THINKORSWIM · VIA ZAPIER</span><h3 id="stock-alert-feed-heading">Stock alerts</h3></div><div><span>{alerts.length ? `${alerts.length} recent` : 'App feed'}</span>{onRefresh && !preview && <button type="button" onClick={onRefresh} disabled={status === 'loading'}>{status === 'loading' ? 'Refreshing…' : 'Refresh'}</button>}</div></div>
    {error && <p className="sw-alert-error" role="status">{error}</p>}
    {alerts.length ? <div className="sw-alert-list">{alerts.map(alert => {
      const symbol = normalizeAlertSymbol(alert.symbol);
      const sourceTime = formattedTime(alert.source_timestamp);
      const receivedTime = formattedTime(alert.received_at);
      const isSelected = alert.id === selectedAlertId;
      return <article key={alert.id} ref={isSelected ? selected : undefined} tabIndex={isSelected ? -1 : undefined} className={`sw-alert-card ${isSelected ? 'is-selected' : ''}`} aria-label={isSelected ? `Selected stock alert: ${symbol || 'Stocks'}` : undefined}>
        <div className="sw-alert-card-top"><strong>{symbol || 'STOCK'}</strong><span>Schwab thinkorswim</span>{symbol && <button type="button" onClick={() => onOpenSymbol?.(symbol)} aria-label={`Open ${symbol} stock chart`}>Open chart <span aria-hidden="true">↗</span></button>}</div>
        <h4>{alert.title || `${symbol || 'Stock'} alert`}</h4><p>{alert.body || 'The source message did not include alert details.'}</p>
        <div className="sw-alert-times">{sourceTime && <span>Source time <time dateTime={alert.source_timestamp}>{sourceTime}</time></span>}{receivedTime && <span>Received <time dateTime={alert.received_at}>{receivedTime}</time></span>}</div>
      </article>;
    })}</div> : <div className="sw-alert-empty"><strong>{status === 'loading' ? 'Loading stock alerts…' : preview ? 'Your stock alerts will appear here' : status === 'error' ? 'The stock feed is unavailable' : 'No stock alerts yet'}</strong><p>{preview ? 'The connected app receives alerts from your thinkorswim email through Zapier. No example signals are shown as real alerts.' : status === 'error' ? 'Use Refresh to try again. Your notification preference is kept separately.' : 'Incoming alerts are saved here, even when push notifications are off.'}</p></div>}
    <div className="sw-alert-footnote">Alert times and prices describe the source message. The chart is a separate market data view.</div>
  </section>;
}
