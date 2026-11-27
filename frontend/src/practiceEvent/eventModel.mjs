export const EVENT_REGISTRATION_PLAN = 'Practice event';

export function eventTokenFromLocation(location) {
  return new URLSearchParams(location?.search || '').get('event_token') || '';
}

export function withoutEventToken(href) {
  const url = new URL(href);
  url.searchParams.delete('event_token');
  return `${url.pathname}${url.search}${url.hash}`;
}

export function normalizePracticeEvent(value, receivedAt = Date.now()) {
  const serverNow = Date.parse(value?.server_now);
  const endsAt = Date.parse(value?.ends_at);
  const startsAt = value?.starts_at ? Date.parse(value.starts_at) : null;
  if (!value || typeof value.campaign_id !== 'string' || !value.campaign_id ||
      !['disabled', 'scheduled', 'open', 'ended'].includes(value.status) ||
      !Number.isFinite(serverNow) || !Number.isFinite(endsAt) ||
      (startsAt !== null && !Number.isFinite(startsAt))) return null;
  return { ...value, serverOffset: serverNow - receivedAt, receivedAt, endsAt, startsAt };
}

export function practiceEventPhase(config, now = Date.now()) {
  if (!config) return 'unavailable';
  if (config.status === 'disabled') return 'disabled';
  const serverNow = now + config.serverOffset;
  if (config.status === 'ended' || serverNow >= config.endsAt) return 'ended';
  if (config.status === 'scheduled' || (config.startsAt !== null && serverNow < config.startsAt)) return 'scheduled';
  return config.status === 'open' ? 'open' : 'unavailable';
}

export function eventDeadlineLabel(value) {
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return 'the event deadline';
  // Describe the last eligible minute, avoiding the ambiguity of "Monday midnight".
  const date = new Date(timestamp - 1);
  const day = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' }).format(date);
  const time = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: 'numeric', minute: '2-digit', hour12: true }).format(date);
  return `${day} at ${time} Eastern`;
}

export function practiceEventError(error, fallback = 'The request could not be completed. Please try again.') {
  const detail = error?.response?.data?.detail;
  if (error?.response?.status === 429) return 'Please wait a little before requesting another verification email.';
  if (error?.response?.status === 409 && (!detail || detail?.code === 'practice_event_closed')) return 'This practice event is not accepting new access. Your account stays saved; you can still choose a membership.';
  if (error?.response?.status === 503) return 'Verification email is temporarily unavailable. Keep your account and try again shortly.';
  return typeof detail === 'string' ? detail : typeof detail?.message === 'string' ? detail.message : fallback;
}

export function eventMembershipPresentation(status) {
  const entitlement = status?.entitlement;
  const event = status?.practice_event;
  if (['square', 'manual_payment', 'legacy', 'manual'].includes(entitlement?.source)) return null;
  if (entitlement?.source === 'practice_event') return {
    kind: entitlement.active ? 'active' : 'ended',
    endsAt: entitlement.trial_ends_at || event?.ends_at,
    title: entitlement.active ? 'Practice event access' : 'Your practice event has ended',
    label: entitlement.active ? 'FREE PRACTICE EVENT' : 'EVENT ACCESS ENDED',
  };
  if (!entitlement?.active && event?.state === 'ended') return {
    kind: 'ended', endsAt: event.ends_at,
    title: 'Your practice event has ended', label: 'EVENT ACCESS ENDED',
  };
  return null;
}

export async function requestPracticeEventLink(client, api, email, config) {
  if (practiceEventPhase(config) !== 'open') throw new Error('This practice event is not open.');
  const response = await client.post(`${api}/practice-event/request`, {
    email: String(email || '').trim(), campaign_id: config.campaign_id,
  }, { timeout: 12000 });
  if (response.data?.status !== 'verification_requested') throw new Error('The verification request could not be confirmed. Please try again.');
  return response.data;
}

export async function confirmPracticeEvent(client, api, token) {
  if (!token || typeof token !== 'string') throw new Error('Open the verification link from your email.');
  const response = await client.post(`${api}/practice-event/confirm`, { token }, { timeout: 12000 });
  if (response.data?.status !== 'confirmed' || !['practice_event', 'existing'].includes(response.data.access) || response.data.sign_in_required !== true) {
    throw new Error('The verification result could not be confirmed. Request a new link for your existing account.');
  }
  return response.data;
}
