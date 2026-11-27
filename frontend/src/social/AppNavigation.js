import React, { useState } from 'react';
import { PRIMARY_NAVIGATION, appSection, primaryDestination } from './socialModel.mjs';
import peacockPoster from '../assets/peacock-poster.webp';
import './social.css';
import './app-shell.css';

function NavIcon({ name }) {
  const paths = {
    trading: <><path d="M3 3v18h18M7 15l4-5 4 3 6-8" /><path d="M17 5h4v4" /></>,
    community: <><path d="M4 4h16v12H9l-5 4V4Z" /><path d="M8 8h8M8 12h5" /></>,
    notifications: <><path d="M5 17h14l-2-3V9a5 5 0 0 0-10 0v5l-2 3ZM10 21h4" /></>,
    achievements: <><path d="M7 3h10v6a5 5 0 0 1-10 0V3ZM7 5H3v3a4 4 0 0 0 4 4M17 5h4v3a4 4 0 0 1-4 4M12 14v7M8 21h8" /></>,
    profile: <><circle cx="12" cy="7" r="4" /><path d="M4 21v-2a8 8 0 0 1 16 0v2" /></>,
  };
  return <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] || paths.profile}</svg>;
}

export default function AppNavigation({ activeTab, onSelect, lastRoom = 'bot-BTC', unread = 0, currentUser, level = 1,
  isDarkTheme = true, onToggleTheme, onLogout, connectionLabel = '' }) {
  const section = activeTab === 'admin' ? 'admin' : appSection(activeTab);
  const name = currentUser?.screen_name || currentUser?.real_name || currentUser?.username || 'Member';
  return <header className={`cashout-app-header ${isDarkTheme ? '' : 'is-light'}`}>
    <div className="cashout-header-frame">
      <button type="button" className="cashout-brand" onClick={() => onSelect(primaryDestination('trading', lastRoom))} aria-label="CashOutAI trading home">
        <span className="cashout-brand-mark"><img src={peacockPoster} alt="" width="52" height="39" draggable="false" /></span>
        <span className="cashout-brand-wordmark"><strong>CashOut<span>AI</span></strong><small>TRADE TOGETHER. LEARN TOGETHER.</small></span>
      </button>
      <nav className="cashout-primary-nav" aria-label="Main navigation">{PRIMARY_NAVIGATION.map(item => <button type="button" key={item.key} className={section === item.key ? 'is-active' : ''} aria-current={section === item.key ? 'page' : undefined} onClick={() => onSelect(primaryDestination(item.key, lastRoom))}>
        <span className="cashout-nav-icon"><NavIcon name={item.key} />{item.key === 'notifications' && unread > 0 && <span className="cashout-unread-badge" aria-label={`${unread} unread notifications`}>{unread > 99 ? '99+' : unread}</span>}</span><span>{item.label}</span>
      </button>)}</nav>
      <div className="cashout-account-actions">{connectionLabel && <span className="cashout-connection"><span className={connectionLabel === 'Disconnected' ? 'is-offline' : ''} aria-hidden="true" />{connectionLabel}</span>}
        {currentUser?.is_admin && <button type="button" className={`cashout-admin-link ${activeTab === 'admin' ? 'is-active' : ''}`} aria-current={activeTab === 'admin' ? 'page' : undefined} onClick={() => onSelect('admin')}>Admin</button>}
        {onToggleTheme && <button type="button" className="cashout-theme-action" onClick={onToggleTheme} aria-label={isDarkTheme ? 'Switch to light theme' : 'Switch to dark theme'}>{isDarkTheme ? '☀' : '☾'}</button>}
        <button type="button" className="cashout-profile-shortcut" onClick={() => onSelect('profile')} aria-label={`Open ${name}'s profile`}><span className="cashout-nav-avatar">{name.charAt(0).toUpperCase()}{currentUser?.avatar_url && <img src={currentUser.avatar_url} alt="" onError={event => { event.currentTarget.style.display = 'none'; }} />}</span><span className="cashout-nav-identity"><strong>{name}</strong><small>Level {level}</small></span></button>
        {onLogout && <button type="button" className="cashout-header-logout" onClick={onLogout}>Log out</button>}
      </div>
    </div>
  </header>;
}

export function TradingTools({ activeTab, onSelect }) {
  return <nav className="cashout-trading-tools" aria-label="Trading tools"><span>Your tools</span>{[['portfolio', 'Portfolio'], ['practice', 'Stock practice'], ['favorites', 'Favorites']].map(([key, label]) => <button type="button" key={key} className={activeTab === key ? 'is-active' : ''} aria-current={activeTab === key ? 'page' : undefined} onClick={() => onSelect(key)}>{label}</button>)}</nav>;
}

export function CommunityNavigation({ activeTab, onSelect, onShareWin }) {
  return <div className="cashout-community-heading"><div><span>THE COMMUNITY</span><h2>Learn together. Share the experience.</h2></div><div className="cashout-community-links"><nav aria-label="Community navigation"><button type="button" className={activeTab === 'chat' ? 'is-active' : ''} aria-current={activeTab === 'chat' ? 'page' : undefined} onClick={() => onSelect('chat')}>Discussion</button><button type="button" className={activeTab === 'members' ? 'is-active' : ''} aria-current={activeTab === 'members' ? 'page' : undefined} onClick={() => onSelect('members')}>Members</button></nav><button type="button" className="cashout-share-win" onClick={onShareWin}>＋ Share a win</button></div></div>;
}

export function MembersDirectory({ members = [], onlineUsers = [], currentUser, onViewProfile }) {
  const [search, setSearch] = useState('');
  const online = new Set(onlineUsers.map(user => user.id));
  const filtered = members.filter(member => `${member.screen_name || ''} ${member.username || ''}`.toLowerCase().includes(search.toLowerCase()));
  return <section className="cashout-members-directory"><div className="cashout-members-intro"><div><h3>Meet the community</h3><p>Open a profile to follow a trader and see their bio, style, and achievements.</p></div><label>Find a member<input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Name or username" /></label></div>
    <div className="cashout-member-grid">{filtered.map(member => <button type="button" key={member.id} className="cashout-member-card" onClick={() => onViewProfile(member.id)}><span className="cashout-member-avatar">{(member.screen_name || member.username || '?').charAt(0).toUpperCase()}{member.avatar_url && <img src={member.avatar_url} alt="" onError={event => { event.currentTarget.style.display = 'none'; }} />}</span><span><strong>{member.screen_name || member.username}{member.id === currentUser?.id ? ' (you)' : ''}</strong><small>@{member.username}</small><em>{online.has(member.id) ? 'Online' : 'Member'}{member.level ? ` · Level ${member.level}` : ''}</em></span><span className="cashout-member-arrow" aria-hidden="true">↗</span></button>)}</div>
    {!filtered.length && <p className="cashout-members-empty">{search ? 'No members match that name.' : 'Member profiles will appear here when the directory loads.'}</p>}
  </section>;
}
