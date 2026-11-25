export const BOT_ASSETS = ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE'];
export const ASSET_NAMES = { BTC: 'Bitcoin', ETH: 'Ethereum', SOL: 'Solana', XRP: 'XRP', DOGE: 'Dogecoin' };
const number = value => typeof value === 'number' && Number.isFinite(value) ? value : null;
const iso = seconds => Number.isFinite(seconds) ? new Date(seconds * 1000).toISOString() : null;

/** Present native recorded values unchanged. A stale quote is never a live practice mark. */
export function adaptNativeSnapshot(native, asset, { state = 'offline', mode, receivedAt, now = Date.now() / 1000 } = {}) {
  if (!BOT_ASSETS.includes(asset)) throw new Error('Unsupported bot asset.');
  if (native?.asset?.symbol && native.asset.symbol !== asset) throw new Error('The bot feed asset does not match this tab.');
  const m = native?.market || {}, q = native?.quote || {};
  const current = state === 'live' && native?.run?.stopped === false && native?.run?.review === false
    && native?.run?.fresh === true && m.fresh === true && q.fresh === true
    && number(q.valid_until) !== null && q.valid_until >= now
    && number(m.close_ts) !== null && m.close_ts > now;
  // Only an explicit preview override permits practice against recorded quotes.
  // A stopped/review packet arriving through the member API remains view-only.
  const explicitReplay = mode === 'replay';
  const presentation = mode || (native?.run?.review ? 'replay' : !native || native.run?.stopped || state === 'offline' ? 'offline' : current ? 'live' : 'stale');
  const replay = presentation === 'replay';
  const replayQuote = replay && q.last_verified?.ticker === m.ticker ? q.last_verified : q;
  const quotes = Object.fromEntries(['yes', 'no'].map(side => [side, {
    bid: current || replay ? number((replay ? replayQuote : q)[side + '_bid']) : null,
    ask: current || replay ? number((replay ? replayQuote : q)[side + '_ask']) : null,
  }]));
  const p = native?.positions?.find(position => position.ticker === m.ticker) || native?.positions?.[0];
  const mark = p?.last_verified_mark || {};
  const verifiedPnl = current && p?.mark_valid ? number(p.open_net_pnl) : number(p?.display_net_pnl) ?? number(mark.net_pnl);
  const verifiedRoi = current && p?.mark_valid ? number(p.open_net_roi) : number(p?.display_net_roi) ?? number(mark.net_roi);
  const position = p ? {
    side: p.side, quantity: p.remaining_qty ?? p.qty, entryPrice: number(p.entry_ask),
    currentBid: current && p.ticker === m.ticker ? quotes[p.side?.toLowerCase()]?.bid : null,
    netPnl: verifiedPnl, netReturnPct: verifiedRoi, ticker: p.ticker,
    reason: current && p.mark_valid ? 'Verified PAPER position' : 'Last recorded PAPER position',
  } : null;
  const trades = [...(native?.trades || [])].filter(t => number(t.exit_ts) !== null).slice(-5).map(t => ({
    id: t.key || String(t.trade_id), side: t.side, entryPrice: number(t.entry_ask), exitPrice: number(t.exit_bid),
    netPnl: number(t.net_pnl) ?? number(t.net_profit) ?? number(t.realized_net),
    netReturnPct: number(t.net_roi) ?? number(t.net_return_pct), closedAt: iso(t.exit_ts),
    nativeTrade: t,
  }));
  return {
    asset, symbol: asset, name: ASSET_NAMES[asset], mode: presentation,
    status: replay ? 'RECORDED PAPER' : current ? (position ? 'POSITION OPEN' : 'OBSERVING') : presentation === 'stale' ? 'FEED DELAYED' : 'AWAITING FEED',
    reason: replay ? (explicitReplay ? 'Historical observation · practice uses recorded quotes' : 'Historical observation · practice needs a live quote') : current ? 'Nautilus PAPER feed connected' : presentation === 'stale' ? 'Feed delayed · practice waits for a fresh quote' : 'Connect the PAPER publisher to see this bot here.',
    updatedAt: iso(m.time) || receivedAt || null, price: number(m.btc),
    contract: { id: m.ticker || null, closeTime: iso(m.close_ts), target: number(m.target) },
    quotes, position, trades, native: native || null,
    canPractice: current || explicitReplay,
    practiceMode: explicitReplay ? 'replay' : current ? 'live' : 'unavailable',
    quoteValidUntil: number(q.valid_until), feePolicy: 'Fees excluded',
  };
}

export function accountMarks(account, snapshots, now = Date.now() / 1000) {
  return Object.fromEntries((account?.positions || []).flatMap(position => {
    const snapshot = snapshots[position.asset];
    const bid = snapshot?.quotes?.[position.side.toLowerCase()]?.bid;
    const current = snapshot?.practiceMode === 'replay' || (snapshot?.practiceMode === 'live'
      && Number.isFinite(snapshot.quoteValidUntil) && snapshot.quoteValidUntil >= now
      && Date.parse(snapshot.contract?.closeTime) / 1000 > now);
    return current && snapshot?.contract?.id === position.contractId && Number.isFinite(bid) ? [[position.id, { bid, fee: 0 }]] : [];
  }));
}
