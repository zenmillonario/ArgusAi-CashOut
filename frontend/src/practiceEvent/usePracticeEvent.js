import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { sameSession, sessionHeaders } from '../sessionAuth.mjs';
import { normalizePracticeEvent, practiceEventPhase } from './eventModel.mjs';

export default function usePracticeEvent(apiBase, currentUser, onMembershipRequired) {
  const [config, setConfig] = useState(null);
  const [clock, setClock] = useState(Date.now());
  const [member, setMember] = useState({ owner: null, data: null });
  const current = useRef(currentUser); current.current = currentUser;
  const gate = useRef(onMembershipRequired); gate.current = onMembershipRequired;
  const publicRequest = useRef(null);
  const memberRequest = useRef(null);
  const memberVersion = useRef(0);
  const refreshPublic = useCallback(async () => {
    publicRequest.current?.abort();
    const controller = new AbortController(); publicRequest.current = controller;
    try {
      const response = await axios.get(`${apiBase}/practice-event`, { signal: controller.signal, timeout: 8000 });
      if (!controller.signal.aborted) { setConfig(normalizePracticeEvent(response.data)); setClock(Date.now()); }
    } catch (_) {
      if (!controller.signal.aborted) setConfig(null);
    }
  }, [apiBase]);
  const refreshMember = useCallback(async () => {
    const session = current.current;
    if (!session?.id || !session.active_session_id) return;
    memberRequest.current?.abort();
    const controller = new AbortController(); memberRequest.current = controller;
    const version = ++memberVersion.current;
    try {
      const response = await axios.get(`${apiBase}/billing/status`, { headers: sessionHeaders(session), signal: controller.signal, timeout: 8000 });
      if (controller.signal.aborted || version !== memberVersion.current || !sameSession(current.current, session) || response.data?.user_id !== session.id) return;
      setMember({ owner: session, data: response.data });
      // Ask the server at the boundary. A paid approval may have replaced event
      // access since the last login, so a client timer alone must never lock it.
      if (response.data?.entitlement?.active === false) gate.current?.(session);
    } catch (_) { /* Existing session handling remains authoritative on errors. */ }
  }, [apiBase]);
  useEffect(() => {
    refreshPublic();
    const onFocus = () => { if (!document.hidden) { refreshPublic(); refreshMember(); } };
    window.addEventListener('focus', onFocus);
    document.addEventListener('visibilitychange', onFocus);
    const timer = setInterval(() => { if (!document.hidden) refreshPublic(); }, 300000);
    const clockTimer = setInterval(() => setClock(Date.now()), 15000);
    return () => {
      window.removeEventListener('focus', onFocus); document.removeEventListener('visibilitychange', onFocus);
      clearInterval(timer); clearInterval(clockTimer); publicRequest.current?.abort(); memberRequest.current?.abort();
    };
  }, [refreshPublic, refreshMember]);
  const userKey = `${currentUser?.id || ''}:${currentUser?.active_session_id || ''}`;
  useEffect(() => {
    memberVersion.current += 1;
    memberRequest.current?.abort();
    setMember({ owner: null, data: null });
    if (currentUser?.id && currentUser.active_session_id) refreshMember();
    return () => { memberVersion.current += 1; memberRequest.current?.abort(); };
  }, [userKey, refreshMember]);
  const status = sameSession(member.owner, currentUser) ? member.data : null;
  const eventEnd = status?.entitlement?.source === 'practice_event' ? Date.parse(status.entitlement.trial_ends_at || status.practice_event?.ends_at) : NaN;
  useEffect(() => {
    if (!Number.isFinite(eventEnd) || !status?.entitlement?.active) return undefined;
    const delay = Math.max(0, eventEnd - Date.now() - (config?.serverOffset || 0) + 50);
    // The interval also catches a missed timeout after a device has slept.
    const interval = setInterval(() => { if (!document.hidden) refreshMember(); }, 60000);
    const timeout = setTimeout(refreshMember, Math.min(delay, 2147483647));
    return () => { clearInterval(interval); clearTimeout(timeout); };
  }, [eventEnd, status?.entitlement?.active, config?.serverOffset, refreshMember, userKey]);
  return { config, phase: practiceEventPhase(config, clock), status, refreshMember, refreshPublic };
}
