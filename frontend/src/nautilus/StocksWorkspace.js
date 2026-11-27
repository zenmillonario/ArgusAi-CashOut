import React, { useEffect, useRef, useState } from 'react';
import { RoomChatDock } from './BotWorkspace';
import StockAlertsPanel, { StockPushSettings } from './StockAlertsPanel';
import './stocks.css';

const SYMBOLS = {
  AAPL: { symbol: 'NASDAQ:AAPL', name: 'Apple' },
  MSFT: { symbol: 'NASDAQ:MSFT', name: 'Microsoft' },
  NVDA: { symbol: 'NASDAQ:NVDA', name: 'NVIDIA' },
  TSLA: { symbol: 'NASDAQ:TSLA', name: 'Tesla' },
  AMZN: { symbol: 'NASDAQ:AMZN', name: 'Amazon' },
  GOOGL: { symbol: 'NASDAQ:GOOGL', name: 'Alphabet' },
  META: { symbol: 'NASDAQ:META', name: 'Meta Platforms' },
  IBM: { symbol: 'NYSE:IBM', name: 'IBM' },
  SPY: { symbol: 'AMEX:SPY', name: 'SPDR S&P 500 ETF' },
};
const INITIAL_WATCHLIST = ['NASDAQ:AAPL', 'NASDAQ:NVDA', 'NASDAQ:MSFT'];
export function normalizeStockSymbol(value) {
  const clean = String(value || '').trim().toUpperCase().replace(/^\$/, '');
  if (!/^(?:[A-Z0-9_]{2,12}:)?[A-Z0-9][A-Z0-9._-]{0,14}$/.test(clean)) {
    throw new Error('Enter a ticker such as AAPL, or an exchange and ticker such as NYSE:IBM.');
  }
  return clean.includes(':') ? clean : SYMBOLS[clean]?.symbol || clean;
}
const tickerOf = symbol => symbol.split(':').pop();
const stockName = symbol => SYMBOLS[tickerOf(symbol)]?.symbol === symbol ? SYMBOLS[tickerOf(symbol)].name : 'Stock workspace';
const readStored = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch (_) { return fallback; } };
const saveStored = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch (_) { return false; } };

function StockIcon({ type = 'chart', size = 18 }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{type === 'expand' ? <path d="M8 3H3v5m13-5h5v5m0 8v5h-5M3 16v5h5" /> : type === 'star' ? <path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9L12 3Z" /> : type === 'search' ? <><circle cx="10" cy="10" r="6" /><path d="m15 15 6 6" /></> : type === 'book' ? <><path d="M4 4h6l2 2 2-2h6v16h-6l-2 2-2-2H4V4Z" /><path d="M12 6v16" /></> : <><path d="M4 3v17h17M7 14l4-5 4 3 5-7" /><path d="M16 5h4v4" /></>}</svg>;
}

/** Public hosted market widget. Quotes remain inside the provider frame;
 * no credentials, member data or simulated execution are sent to it.
 * Official embed reference: https://www.tradingview.com/widget-docs/widgets/charts/legacy-advanced-chart/
 */
function StockMarketChart({ symbol, interval }) {
  const host = useRef(null);
  const [status, setStatus] = useState('loading');
  useEffect(() => {
    const element = host.current;
    let disposed = false;
    let frame;
    setStatus('loading');
    const loaded = () => { if (!disposed) setStatus('loaded'); };
    const observe = new MutationObserver(() => {
      const next = element.querySelector('iframe');
      if (next && next !== frame) {
        frame?.removeEventListener('load', loaded);
        frame = next;
        frame.title = `${symbol} stock market chart by TradingView`;
        frame.addEventListener('load', loaded);
      }
    });
    observe.observe(element, { childList: true, subtree: true });
    const mount = document.createElement('div');
    mount.className = 'tradingview-widget-container__widget';
    mount.style.height = '100%';
    mount.style.width = '100%';
    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
    script.type = 'text/javascript';
    script.async = true;
    script.onerror = () => { if (!disposed) setStatus('error'); };
    script.textContent = JSON.stringify({
      autosize: true, symbol, interval, timezone: 'America/New_York',
      theme: 'dark', style: '1', locale: 'en', backgroundColor: '#0b151e',
      gridColor: 'rgba(73, 105, 123, 0.12)', allow_symbol_change: false,
      hide_side_toolbar: true, hide_top_toolbar: false, hide_legend: false,
      hide_volume: false, withdateranges: true, save_image: false,
      calendar: false, details: false, hotlist: false,
      support_host: 'https://www.tradingview.com',
    });
    element.append(mount, script);
    const timeout = window.setTimeout(() => { if (!disposed) setStatus(previous => previous === 'loading' ? 'slow' : previous); }, 12000);
    return () => {
      disposed = true; window.clearTimeout(timeout); observe.disconnect();
      frame?.removeEventListener('load', loaded); script.onerror = null;
      element.replaceChildren();
    };
  }, [symbol, interval]);
  const url = `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(symbol)}`;
  return <div className="sw-chart-stage">
    <div ref={host} className="tradingview-widget-container sw-provider-chart" />
    {status === 'loading' && <div className="sw-chart-loading" role="status"><StockIcon size={30} /><strong>Opening {tickerOf(symbol)}</strong><span>Loading the market chart</span></div>}
    {(status === 'error' || status === 'slow') && <div className="sw-chart-loading sw-chart-unavailable" role="status"><StockIcon size={30} /><strong>{status === 'error' ? 'The chart is unavailable here' : 'The chart is taking longer to load'}</strong><span>Your selected ticker and notes are saved. You can also open the chart directly.</span><a href={url} target="_blank" rel="noopener noreferrer">Open {tickerOf(symbol)} chart <span aria-hidden="true">↗</span></a></div>}
  </div>;
}

export default function StocksWorkspace({ currentUser, onOpenCommunity, preview = false, messages = {}, onSendChat,
  stockAlerts = [], stockAlertsStatus = 'loading', stockAlertsError = '', onRefreshStockAlerts,
  stockNotifications = {}, onToggleStockNotifications, initialStockSymbol = '', selectedStockAlertId = '' }) {
  const owner = currentUser?.id || 'private-preview';
  const storage = `cashoutai-stocks-v1-${owner}`;
  const [symbol, setSymbol] = useState(() => { try { return normalizeStockSymbol(initialStockSymbol || readStored(`${storage}-symbol`, 'NASDAQ:AAPL')); } catch (_) { return 'NASDAQ:AAPL'; } });
  const [input, setInput] = useState(tickerOf(symbol));
  const [interval, setInterval] = useState('D');
  const [watchlist, setWatchlist] = useState(() => {
    const list = readStored(`${storage}-watchlist`, INITIAL_WATCHLIST);
    return Array.isArray(list) ? [...new Set(list.filter(s => typeof s === 'string' && /^(?:[A-Z0-9_]{2,12}:)?[A-Z0-9][A-Z0-9._-]{0,14}$/.test(s)))].slice(0,10) : INITIAL_WATCHLIST;
  });
  const [note, setNote] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [full, setFull] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [television, setTelevision] = useState(false);
  const root = useRef(null);
  const currentNote = useRef({ storage, symbol, note });
  currentNote.current = { storage, symbol, note };
  const ticker = tickerOf(symbol);
  useEffect(() => {
    const saved = readStored(`${storage}-note-${symbol}`, '');
    setNote(typeof saved === 'string' ? saved : ''); setNotice('');
  }, [storage, symbol]);
  useEffect(() => { saveStored(`${storage}-symbol`, symbol); }, [storage, symbol]);
  useEffect(() => { saveStored(`${storage}-watchlist`, watchlist); }, [storage, watchlist]);
  useEffect(() => {
    const changed = () => setFull(document.fullscreenElement === root.current);
    const escape = event => { if (event.key === 'Escape') setExpanded(false); };
    document.addEventListener('fullscreenchange', changed); window.addEventListener('keydown', escape);
    return () => { document.removeEventListener('fullscreenchange', changed); window.removeEventListener('keydown', escape); };
  }, []);
  useEffect(() => {
    if (!expanded) return undefined;
    const old = document.body.style.overflow; document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = old; };
  }, [expanded]);
  useEffect(() => {
    if (!initialStockSymbol) return;
    try {
      const next = normalizeStockSymbol(initialStockSymbol);
      const previous = currentNote.current;
      if (next !== previous.symbol) saveStored(`${previous.storage}-note-${previous.symbol}`, previous.note);
      setSymbol(next); setInput(tickerOf(next)); setError('');
    } catch (_) { /* Ignore an invalid deep link; normal ticker entry still works. */ }
  }, [initialStockSymbol, selectedStockAlertId]);
  const loadSymbol = value => {
    try {
      const next = normalizeStockSymbol(value);
      // Preserve an unfinished observation before switching symbols.
      saveStored(`${storage}-note-${symbol}`, note);
      setSymbol(next); setInput(tickerOf(next)); setError(''); setNotice('');
    } catch (e) { setError(e.message); }
  };
  const toggleFullscreen = async () => {
    if (document.fullscreenElement === root.current) { await document.exitFullscreen?.(); return; }
    if (expanded) { setExpanded(false); return; }
    try { if (root.current.requestFullscreen) await root.current.requestFullscreen(); else setExpanded(true); }
    catch (_) { setExpanded(true); }
  };
  const starred = watchlist.includes(symbol);
  const toggleWatch = () => {
    if (starred) setWatchlist(previous => previous.filter(s => s !== symbol));
    else if (watchlist.length < 10) setWatchlist(previous => [...previous, symbol]);
    else setNotice('Your watchlist holds 10 symbols. Remove one to add another.');
  };
  return <section ref={root} id="cashout-stock-room" role="tabpanel" aria-labelledby="tab-stocks" className={`nw-workspace sw-workspace ${television ? 'sw-tv' : ''} ${expanded ? 'sw-expanded' : ''}`}>
    <div className="sw-titlebar"><div className="sw-title"><span className="sw-title-icon"><StockIcon size={25} /></span><div><h2>Stocks</h2><p>CHOOSE A TICKER. STUDY THE MOVE.</p></div></div><div className="sw-toolbar"><span className="sw-foundation">Research workspace</span><button type="button" onClick={() => setTelevision(!television)} aria-pressed={television}>TV mode</button><button type="button" onClick={toggleFullscreen} aria-label={full || expanded ? 'Exit stocks full screen' : 'Open stocks full screen'}><StockIcon type="expand" size={16} />{full || expanded ? 'Exit full screen' : 'Full screen'}</button></div></div>
    <div className="sw-layout"><div className="sw-main">
      <div className="sw-search-panel"><form onSubmit={event => { event.preventDefault(); loadSymbol(input); }}><label htmlFor="stock-ticker">Stock ticker</label><div className="sw-search"><StockIcon type="search" /><input id="stock-ticker" value={input} onChange={event => setInput(event.target.value)} placeholder="AAPL or NYSE:IBM" autoComplete="off" autoCapitalize="characters" spellCheck={false} maxLength={28} /><button type="submit">Load stock <span aria-hidden="true">→</span></button></div></form><div className="sw-quick"><span>Quick open</span>{['AAPL','NVDA','MSFT','TSLA'].map(s => <button key={s} type="button" className={ticker === s ? 'is-active' : ''} onClick={() => loadSymbol(s)}>{s}</button>)}</div>{error && <p className="sw-error" role="alert">{error}</p>}</div>
      <section className="sw-chart-panel" aria-label={`${ticker} stock chart`}><div className="sw-chart-heading"><div><span className="sw-stock-symbol">{ticker}</span><span className="sw-stock-name">{stockName(symbol)}</span><small>{symbol.includes(':') ? symbol.split(':')[0] : 'Provider symbol search'}</small></div><div className="sw-chart-actions"><div role="group" aria-label="Stock chart candle interval">{[['15','15m'],['60','1h'],['D','1D']].map(([value,label]) => <button type="button" key={value} aria-pressed={interval === value} className={interval === value ? 'is-active' : ''} onClick={() => setInterval(value)}>{label}</button>)}</div><button type="button" aria-label={starred ? `Remove ${ticker} from watchlist` : `Save ${ticker} to watchlist`} aria-pressed={starred} onClick={toggleWatch} className={starred ? 'is-starred' : ''}><StockIcon type="star" size={18} /></button></div></div>
        <StockMarketChart symbol={symbol} interval={interval} />
        <div className="sw-attribution"><span>Market data may be delayed. Availability varies by exchange.</span><a href={`https://www.tradingview.com/chart/?symbol=${encodeURIComponent(symbol)}`} target="_blank" rel="noopener noreferrer">{ticker} chart by TradingView <span aria-hidden="true">↗</span></a></div>
      </section>
      <RoomChatDock key={symbol} asset={ticker} messages={messages[symbol] || []} chatMode={preview ? 'preview' : 'community'} chatStatus={preview ? 'Stock discussion · this browser' : 'Join the community discussion'} currentUser={currentUser} onSendChat={preview && onSendChat ? text => onSendChat(symbol, text) : undefined} onOpenRoom={!preview ? onOpenCommunity : undefined} />
      <StockAlertsPanel alerts={stockAlerts} status={preview ? 'preview' : stockAlertsStatus} error={stockAlertsError} onRefresh={onRefreshStockAlerts} onOpenSymbol={loadSymbol} selectedAlertId={selectedStockAlertId} preview={preview} />
    </div><aside className="sw-sidebar" aria-label="Stock watchlist and study notes">
      <StockPushSettings state={stockNotifications} onToggle={onToggleStockNotifications} preview={preview} />
      <section className="sw-panel"><div className="sw-panel-heading"><h3><StockIcon type="star" size={15} />Your watchlist</h3><span>{watchlist.length}/10</span></div><p className="sw-small-note">Saved on this browser</p><div className="sw-watchlist">{watchlist.length ? watchlist.map(s => <div className={s === symbol ? 'is-active' : ''} key={s}><button type="button" onClick={() => loadSymbol(s)}><strong>{tickerOf(s)}</strong><span>{stockName(s)}</span></button><button type="button" aria-label={`Remove ${tickerOf(s)} from watchlist`} onClick={() => setWatchlist(previous => previous.filter(item => item !== s))}>×</button></div>) : <p>Use the star above the chart to save a ticker.</p>}</div></section>
      <section className="sw-panel sw-study"><div className="sw-panel-heading"><h3><StockIcon type="book" size={16} />Study notes</h3><span>{ticker}</span></div><p>What do you see? Write your idea before the next move.</p><label htmlFor="stock-study-note">Your observation</label><textarea id="stock-study-note" value={note} onChange={event => { setNote(event.target.value); setNotice(''); }} placeholder="Trend, key level, and what would change my view…" maxLength={2000} /><div className="sw-note-controls"><small>{note.length}/2000</small><button type="button" onClick={() => setNotice(saveStored(`${storage}-note-${symbol}`, note) ? `${ticker} observation saved on this browser.` : 'Browser storage is unavailable. Copy your note before leaving.')}>Save note</button></div><div className="sw-notice" role="status">{notice}</div></section>
      <section className="sw-next"><span className="sw-next-orbit"><StockIcon size={23} /></span><span className="sw-kicker">NEXT CHAPTER</span><h3>Nautilus for stocks.</h3><p>A dedicated stock Nautilus is planned for this space. For now, explore price history, build a watchlist, and keep your observations.</p><span className="sw-coming">Stock bot guides are not active yet</span></section>
    </aside></div>
  </section>;
}
