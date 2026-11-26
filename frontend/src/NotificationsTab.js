import React, { useState } from 'react';
import { notificationPresentation, unreadCount } from './social/socialModel.mjs';

const NotificationsTab = ({ notifications = [], botNotices = [], botNoticesError = '', onRefreshBotNotices, onOpenBotNotice, onMarkAsRead, onMarkAllAsRead, onDeleteNotification, onOpenNotification, onOpenStocks }) => {
  const [pending, setPending] = useState(new Set());
  const [error, setError] = useState('');
  const unread = unreadCount(notifications);
  const run = async (key, action) => {
    if (!action || pending.has(key)) return;
    setPending(previous => new Set([...previous, key])); setError('');
    try {
      const success = await action();
      if (success === false) setError('That change could not be saved. Please try again.');
    } catch (_) { setError('That change could not be saved. Please try again.'); }
    finally { setPending(previous => { const next = new Set(previous); next.delete(key); return next; }); }
  };
  const formatDate = value => {
    const date = value ? new Date(value) : null;
    return date && !Number.isNaN(date.valueOf()) ? date.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '';
  };
  return <section className="cashout-notification-screen" aria-labelledby="cashout-inbox-heading">
    <div className="cashout-inbox-heading"><div><h2 id="cashout-inbox-heading">Notifications</h2><p>{unread ? `${unread} unread · ` : ''}{notifications.length} community {notifications.length === 1 ? 'update' : 'updates'}</p></div>{onMarkAllAsRead && <button type="button" disabled={!unread || pending.has('all')} onClick={() => run('all', onMarkAllAsRead)}>{pending.has('all') ? 'Saving…' : 'Mark all read'}</button>}</div>
    <div className="cashout-inbox-info"><p>Bot sessions, replies, reactions, follows, mentions, and achievements stay in the app. Only stock alerts send device push notifications.</p>{onOpenStocks && <button type="button" onClick={onOpenStocks}>Open stock alerts ↗</button>}</div>
    <section className="cashout-run-history" aria-labelledby="cashout-run-history-heading">
      <h3 id="cashout-run-history-heading">Bot session history</h3>
      <p>These shared notices record when a fresh PAPER feed reached the app. Open a room to check its current live or offline status.</p>
      {botNoticesError && <p role="alert">{botNoticesError} {onRefreshBotNotices && <button type="button" onClick={onRefreshBotNotices}>Retry</button>}</p>}
      {botNotices.length ? <div className="cashout-inbox-list">{botNotices.map(item => <article key={item.id} className="cashout-notification-card">
        <span className="cashout-notification-icon" aria-hidden="true">↗</span>
        <div className="cashout-notification-body"><div className="cashout-notification-top"><h4>{item.title}</h4><time dateTime={item.createdAt}>{formatDate(item.createdAt)}</time></div>
          <p>{item.message}</p>{onOpenBotNotice && <button type="button" onClick={() => onOpenBotNotice(item)}>Open {item.asset} room ↗</button>}
        </div>
      </article>)}</div> : !botNoticesError && <p>New bot sessions will appear here after their first fresh feed is received.</p>}
    </section>
    {error && <p className="cashout-inbox-error" role="alert">{error}</p>}
    {notifications.length ? <div className="cashout-inbox-list">{notifications.map(item => {
      const presentation = notificationPresentation(item);
      return <article key={item.id} className={`cashout-notification-card ${item.read ? '' : 'is-unread'}`}>
        <span className="cashout-notification-icon" aria-hidden="true">{presentation.icon}</span><div className="cashout-notification-body"><div className="cashout-notification-top"><h3>{presentation.title}</h3><time dateTime={item.created_at}>{formatDate(item.created_at)}</time></div><p>{item.message}</p><div className="cashout-notification-actions">
          {onOpenNotification && <button type="button" onClick={() => onOpenNotification(item)}>{presentation.action}</button>}
          {!item.read && onMarkAsRead ? <button type="button" disabled={pending.has(item.id)} onClick={() => run(item.id, () => onMarkAsRead(item.id))}>Mark read</button> : item.read && <small>Read</small>}
          {onDeleteNotification && <button type="button" className="cashout-delete-notification" disabled={pending.has(item.id)} onClick={() => run(item.id, () => onDeleteNotification(item.id))}>Delete</button>}
        </div></div>
      </article>;
    })}</div> : <div className="cashout-inbox-empty"><strong>Your community inbox</strong><p>New follows, replies, mentions, reactions, and achievement updates will appear here.</p></div>}
  </section>;
};
export default NotificationsTab;
