import { sameSession, sessionHeaders } from '../sessionAuth.mjs';

export const PRIMARY_NAVIGATION = [
  { key: 'trading', label: 'Trading' }, { key: 'community', label: 'Community' },
  { key: 'notifications', label: 'Notifications' }, { key: 'achievements', label: 'Achievements' },
  { key: 'profile', label: 'Profile' },
];
export const REACTION_EMOJI = { thumbs_up: '👍', heart: '❤️', money: '💰', rocket: '🚀' };

export function appSection(tab) {
  if (String(tab).startsWith('bot-') || ['stocks', 'portfolio', 'practice', 'favorites'].includes(tab)) return 'trading';
  if (['chat', 'members'].includes(tab)) return 'community';
  if (['notifications', 'achievements'].includes(tab)) return tab;
  return 'profile';
}
export function primaryDestination(section, lastRoom = 'bot-BTC') {
  if (section === 'trading') return lastRoom === 'stocks' || /^bot-(BTC|ETH|SOL|XRP|DOGE)$/.test(lastRoom) ? lastRoom : 'bot-BTC';
  return section === 'community' ? 'chat' : section;
}
export function unreadCount(notifications) {
  return (notifications || []).filter(item => item?.id && item.read !== true).length;
}
export function reactionType(value) {
  return Object.hasOwn(REACTION_EMOJI, value) ? value : Object.keys(REACTION_EMOJI).find(key => REACTION_EMOJI[key] === value) || null;
}
export function reactionSummary(raw, userId) {
  const usersByType = {};
  for (const [rawType, users] of Object.entries(raw || {})) {
    const type = reactionType(rawType);
    if (!type || !Array.isArray(users)) continue;
    usersByType[type] ||= new Set();
    for (const user of users) if (user?.user_id) usersByType[type].add(user.user_id);
  }
  return {
    counts: Object.fromEntries(Object.entries(usersByType).map(([type, users]) => [REACTION_EMOJI[type], users.size])),
    mine: Object.entries(usersByType).filter(([, users]) => users.has(userId)).map(([type]) => type),
  };
}
export function winDraft(existing = '') {
  return existing.trim() ? existing : '🏆 A win or lesson\nTicker or bot: \nPractice or live (self-reported): \nWhat happened: \nWhat I learned: ';
}
export function notificationPresentation(item = {}) {
  const data = item.data || {};
  const name = item.from || data.replier_name || data.reactor_name || data.follower_name || data.mentioner_name || 'A member';
  const labels = {
    reply: { icon: '↩', title: `${name} replied to your message`, action: 'Open community' },
    reaction: { icon: REACTION_EMOJI[reactionType(data.reaction_type)] || '❤️', title: `${name} reacted to your message`, action: 'Open community' },
    follow: { icon: '◎', title: `${name} started following you`, action: data.follower_id ? 'View profile' : 'Open community' },
    mention: { icon: '@', title: `${name} mentioned you`, action: 'Open community' },
    achievement: { icon: data.achievement_icon || '🏆', title: item.title || 'Achievement unlocked', action: 'View achievements' },
  };
  return labels[item.type] || { icon: '♧', title: item.title || 'Community update', action: 'Open community' };
}

// Mutation headers are captured before the first await. Completion from an old
// account must never update the current account's reaction state.
export async function persistReaction({ client, api, session, currentSession, messageId, reaction, remove = false }) {
  const type = reactionType(reaction);
  if (!type || !messageId || !session?.id || !session?.active_session_id) throw new Error('A valid login and reaction are required.');
  if (!sameSession(currentSession(), session)) return null;
  const route = `${api}/messages/${encodeURIComponent(messageId)}`;
  const headers = sessionHeaders(session);
  try {
    if (remove) await client.delete(`${route}/react`, { headers, params: { user_id: session.id, reaction_type: type } });
    else await client.post(`${route}/react`, { user_id: session.id, reaction_type: type }, { headers });
  } catch (error) {
    // Another tab may have already recorded this exact reaction. Reload truth
    // from the server; don't invent another count or notification.
    if (!(error.response?.status === 400 && /already reacted/i.test(String(error.response?.data?.detail || '')))) throw error;
  }
  if (!sameSession(currentSession(), session)) return null;
  const response = await client.get(`${route}/reactions`, { headers });
  return sameSession(currentSession(), session) ? reactionSummary(response.data, session.id) : null;
}
