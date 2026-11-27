import React, { useEffect, useState } from 'react';
import { sessionHeaders } from '../sessionAuth.mjs';
import './traffic.css';

const display = value => Number.isFinite(value) ? value.toLocaleString('en-US') : '—';

export default function AdminTrafficPanel({ apiBase, currentUser, isDarkTheme }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => setRefresh(value => value + 1), 60000);
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => {
    if (!currentUser?.is_admin) return undefined;
    const controller = new AbortController();
    setError(false);
    fetch(apiBase + '/admin/traffic', {
      headers: sessionHeaders(currentUser), cache: 'no-store',
      referrerPolicy: 'no-referrer', signal: controller.signal,
    }).then(response => {
      if (!response.ok) throw Error('Traffic unavailable');
      return response.json();
    }).then(value => {
      if (!controller.signal.aborted) setData(value);
    }).catch(() => {
      if (!controller.signal.aborted) setError(true);
    });
    return () => controller.abort();
  }, [apiBase, currentUser, refresh]);

  const metrics = [
    ['App opens today', data?.page_opens_today],
    ['App opens · 7 days', data?.page_opens_7_days],
    ['Members seen · 15 min', data?.recent_member_activity],
    ['Registrations today', data?.registrations_today],
    ['Registered accounts', data?.registered_accounts],
    ['Verified event accounts', data?.verified_event_accounts],
  ];
  const peak = Math.max(1, ...(data?.days || []).map(day => day.page_opens || 0));
  return <section className={`admin-traffic ${isDarkTheme ? '' : 'admin-traffic-light'}`} aria-label="App traffic">
    <div className="admin-traffic-heading"><div><span>ADMIN · ACTIVITY</span><h2>App traffic</h2></div>
      <button type="button" onClick={() => setRefresh(value => value + 1)}>Refresh</button></div>
    <p className="admin-traffic-note">Eastern time · Updated every minute while this panel is open.</p>
    {error && <p role="status" className="admin-traffic-note">Traffic data is temporarily unavailable. Select Refresh to try again.</p>}
    {!data && !error && <p role="status">Loading traffic data…</p>}
    <div className="admin-traffic-grid">{metrics.map(([label, value]) => <div className="admin-traffic-metric" key={label}>
      <span>{label}</span><strong>{display(value)}</strong>
    </div>)}</div>
    {data && <div className="admin-traffic-history">
      <h3>Last seven days</h3>
      <div className="admin-traffic-table"><div className="admin-traffic-row admin-traffic-label"><span>Date (ET)</span><span>App opens</span><span>Signups</span></div>
      {data.days.map(day => <div className="admin-traffic-row" key={day.date}>
        <span>{day.date.slice(5)}</span><div className="admin-traffic-bar"><i aria-hidden="true" style={{width: ((day.page_opens || 0) / peak * 100) + '%'}}/><b>{display(day.page_opens)}</b></div>
        <span>{display(day.registrations)}</span>
      </div>)}</div>
    </div>}
    <p className="admin-traffic-note">App opens are measured from the new counter's launch, including anonymous browser opens and refreshes; they are not unique visitors. A dash means no count recorded. Recent member activity uses the account's last-seen timestamp, not a live headcount. Verified event accounts are cumulative. Sensitive verification and recovery pages are excluded from the new counter.</p>
  </section>;
}
