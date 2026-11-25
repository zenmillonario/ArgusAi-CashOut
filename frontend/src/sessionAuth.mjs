// Session identity is captured at the start of an asynchronous operation.
// A callback from an earlier login must never clear a later login.
export function sameSession(left, right) {
  return Boolean(left?.id && left?.active_session_id && right?.id && right?.active_session_id &&
    left.id === right.id && left.active_session_id === right.active_session_id);
}

export function sessionHeaders(session) {
  if (!session?.id || !session?.active_session_id) return {};
  return { 'X-User-ID': session.id, 'X-Session-ID': session.active_session_id };
}

export function removeStoredSession(storage, session) {
  try {
    const saved = JSON.parse(storage.getItem('cashoutai_user'));
    if (!sameSession(saved, session)) return false;
    storage.removeItem('cashoutai_user');
    return true;
  } catch (_) { return false; }
}

export function closeSessionTransport(transport, clearTimer = clearInterval) {
  if (!transport) return;
  if (transport.type === 'polling') {
    clearTimer(transport.sessionInterval);
    clearTimer(transport.messageInterval);
    return;
  }
  transport.onopen = null;
  transport.onmessage = null;
  transport.onerror = null;
  transport.onclose = null;
  transport.close?.();
}
