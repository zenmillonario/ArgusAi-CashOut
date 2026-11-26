import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { sameSession, sessionHeaders } from '../sessionAuth.mjs';
import { mergeBotAnnouncements, normalizeBotAnnouncement, recentBotAnnouncements } from './botAnnouncements.mjs';

const ownerKey = user => user?.id && user?.active_session_id ? `${user.id}:${user.active_session_id}` : '';
const empty = owner => ({ owner, items: [], banners: [], error: '' });

/** Shared run history stays separate from the member's personal read/delete inbox. */
export default function useBotAnnouncements({ currentUser, activeUserRef, activeTab, apiBase }) {
  const [state, setState] = useState(() => empty(''));
  const revision = useRef(0);
  const observed = useRef({ owner: '', initialized: false, ids: new Set() });

  const receive = useCallback(raw => {
    const session = activeUserRef.current, owner = ownerKey(session);
    const item = normalizeBotAnnouncement(raw);
    if (!owner || !item) return;
    if (observed.current.owner !== owner) observed.current = { owner, initialized: false, ids: new Set() };
    const fresh = !observed.current.ids.has(item.id);
    observed.current.ids.add(item.id);
    observed.current.ids = new Set([...observed.current.ids].slice(-50));
    setState(previous => {
      if (!sameSession(activeUserRef.current, session)) return previous;
      const prior = previous.owner === owner ? previous : empty(owner);
      return { ...prior, items: mergeBotAnnouncements(prior.items, [item]),
        banners: fresh ? recentBotAnnouncements([...prior.banners, item]) : prior.banners };
    });
  }, [activeUserRef]);

  const refresh = useCallback(async () => {
    const session = activeUserRef.current, owner = ownerKey(session);
    if (!owner) return;
    const attempt = ++revision.current;
    const valid = () => attempt === revision.current && sameSession(activeUserRef.current, session);
    try {
      const response = await axios.get(`${apiBase}/nautilus/announcements?limit=20`, { headers: sessionHeaders(session) });
      if (!valid()) return;
      if (!Array.isArray(response.data?.announcements)) throw new Error('Invalid run history');
      const incoming = mergeBotAnnouncements([], response.data.announcements);
      const priorSeen = observed.current.owner === owner ? observed.current : { owner, initialized: false, ids: new Set() };
      const arrived = priorSeen.initialized ? incoming.filter(item => !priorSeen.ids.has(item.id)) : [];
      observed.current = { owner, initialized: true, ids: new Set([...priorSeen.ids, ...incoming.map(item => item.id)].slice(-50)) };
      setState(previous => {
        if (!valid()) return previous;
        const prior = previous.owner === owner ? previous : empty(owner);
        return { ...prior, items: mergeBotAnnouncements(prior.items, incoming), error: '',
          banners: recentBotAnnouncements([...prior.banners, ...arrived]) };
      });
    } catch (_) {
      if (valid()) setState(previous => ({ ...(previous.owner === owner ? previous : empty(owner)),
        error: 'Bot session history could not refresh. Try again.' }));
    }
  }, [activeUserRef, apiBase]);

  useEffect(() => {
    ++revision.current;
    const owner = ownerKey(currentUser);
    observed.current = { owner, initialized: false, ids: new Set() };
    setState(empty(owner));
    if (!owner) return undefined;
    refresh();
    const visibleRefresh = () => { if (!document.hidden) refresh(); };
    // Reconnect/multi-worker fallback, bounded to one shared read per visible minute.
    const timer = window.setInterval(visibleRefresh, 60_000);
    document.addEventListener('visibilitychange', visibleRefresh);
    return () => { ++revision.current; window.clearInterval(timer); document.removeEventListener('visibilitychange', visibleRefresh); };
  }, [currentUser?.id, currentUser?.active_session_id, refresh]);

  useEffect(() => { if (activeTab === 'notifications') refresh(); }, [activeTab, refresh]);

  useEffect(() => {
    if (!state.banners.length) return undefined;
    const timer = window.setInterval(() => setState(previous => ({ ...previous, banners: recentBotAnnouncements(previous.banners) })), 10_000);
    return () => window.clearInterval(timer);
  }, [state.banners.length]);

  const dismiss = useCallback(() => setState(previous => ({ ...previous, banners: [] })), []);
  const visible = state.owner === ownerKey(currentUser) ? state : empty('');
  return { notices: visible.items, banners: visible.banners, error: visible.error, receive, refresh, dismiss };
}
