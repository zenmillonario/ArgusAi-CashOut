import React from 'react';
import { normalizeBotAnnouncement } from './botAnnouncements.mjs';
import './botAnnouncements.css';

export default function BotRunBanner({ notices = [], onOpen, onDismiss }) {
  if (!notices.length) return null;
  return <aside className="cashout-run-banner" aria-label="New bot sessions">
    <div role="status"><strong>New PAPER {notices.length === 1 ? 'session' : 'sessions'}</strong><span>Fresh feeds reached the app. Open a room to check its status and practice.</span></div>
    <div className="cashout-run-banner-actions">{notices.map(raw => {
      const item = normalizeBotAnnouncement(raw);
      return item && <button key={item.id} type="button" onClick={() => onOpen(item)}>{item.asset} room ↗</button>;
    })}<button type="button" className="cashout-run-dismiss" onClick={onDismiss} aria-label="Dismiss bot session notice">Dismiss</button></div>
  </aside>;
}
