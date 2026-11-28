import React from 'react';
import { BOT_ASSETS, ASSET_NAMES } from './snapshotAdapter';
import './nautilus.css';
import './shell.css';

const SYMBOLS = { BTC: '₿', ETH: 'Ξ', SOL: '◎', XRP: '✕', DOGE: 'Ð' };
export default function BotTabs({ activeTab, onSelect }) {
  return <nav className="cashout-bot-tabs cashout-bot-tabs-compact" aria-label="Trading bot rooms">
    <div className="cashout-tabs-caption"><span className="cashout-tabs-orbit" />ROOMS</div>
    <div className="cashout-tab-scroll" role="tablist" aria-label="Stocks and bot rooms">
      <button type="button" role="tab" aria-selected={activeTab === 'stocks'} aria-controls="cashout-stock-room" id="tab-stocks" className={`cashout-asset-tab cashout-stocks-tab ${activeTab === 'stocks' ? 'active' : ''}`} onClick={() => onSelect('stocks')}>
        <span className="cashout-asset-symbol asset-stocks"><svg width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M4 3v17h17M7 14l4-5 4 3 5-7M16 5h4v4" /></svg></span><span>Stocks<small>Ticker workspace</small></span>
      </button>
      {BOT_ASSETS.map(asset => <button type="button" key={asset} role="tab" aria-selected={activeTab === `bot-${asset}`} aria-controls="cashout-bot-room" id={`tab-bot-${asset}`} className={`cashout-asset-tab ${activeTab === `bot-${asset}` ? 'active' : ''}`} onClick={() => onSelect(`bot-${asset}`)}>
        <span className={`cashout-asset-symbol asset-${asset.toLowerCase()}`}>{SYMBOLS[asset]}</span><span>{asset}<small>{ASSET_NAMES[asset]}</small></span>
      </button>)}
    </div>
  </nav>;
}
