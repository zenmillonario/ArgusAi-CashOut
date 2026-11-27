import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import notificationService from './firebase-config';
import { sameSession, sessionHeaders } from './sessionAuth.mjs';
import { readStockAlertLink } from './stockNotifications.mjs';

/** The alert feed is independent of device push. Every request belongs to the
 * login that started it; a replaced login cannot repopulate this user's view. */
export default function useStockAlerts({ currentUser, activeUserRef, activeTab, setActiveTab, apiBase }) {
  const [destination, setDestination] = useState(() => readStockAlertLink(window.location.search));
  const [stockAlerts, setStockAlerts] = useState([]);
  const [stockAlertsStatus, setStockAlertsStatus] = useState('loading');
  const [stockAlertsError, setStockAlertsError] = useState('');
  const [stockNotifications, setStockNotifications] = useState({ enabled: false, status: 'loading', message: '' });
  const feedRevision = useRef(0);
  const preferenceRevision = useRef(0);
  const changingPreference = useRef(null);

  const loadStockAlerts = useCallback(async () => {
    const session = activeUserRef.current;
    if (!session?.active_session_id) return;
    const revision = ++feedRevision.current;
    const valid = () => revision === feedRevision.current && sameSession(activeUserRef.current, session);
    try {
      const config = { headers: sessionHeaders(session) };
      const response = await axios.get(`${apiBase}/stocks/alerts?limit=50`, config);
      let alerts = Array.isArray(response.data?.alerts) ? response.data.alerts : [];
      let errorMessage = '';
      if (destination?.alertId && !alerts.some(alert => alert.id === destination.alertId)) {
        try {
          const exact = await axios.get(`${apiBase}/stocks/alerts/${encodeURIComponent(destination.alertId)}`, config);
          const alert = exact.data?.alert || exact.data;
          if (alert?.id === destination.alertId) alerts = [alert, ...alerts];
        } catch (error) {
          if (!valid()) return;
          if (error.response?.status !== 404) throw error;
          errorMessage = 'This linked alert is no longer available. Recent stock alerts are shown below.';
        }
      }
      if (!valid()) return;
      setStockAlertsError(errorMessage);
      setStockAlerts(alerts.filter(alert => alert.category === 'stocks'));
      setStockAlertsStatus('ready');
    } catch (_) {
      if (!valid()) return;
      setStockAlertsStatus('error');
      setStockAlertsError('Stock alerts could not refresh. Try again; any alerts already shown remain saved.');
    }
  }, [activeUserRef, apiBase, destination?.alertId]);

  const loadPreferences = useCallback(async () => {
    const session = activeUserRef.current;
    if (!session?.active_session_id || sameSession(changingPreference.current, session)) return;
    const revision = ++preferenceRevision.current;
    const valid = () => revision === preferenceRevision.current && sameSession(activeUserRef.current, session);
    try {
      const response = await axios.get(`${apiBase}/stocks/notification-preferences`, { headers: sessionHeaders(session) });
      if (!valid()) return;
      const enabled = response.data?.stocks_enabled === true;
      if (!enabled) {
        const local = await notificationService.disableStockNotifications(session);
        if (valid()) setStockNotifications({ enabled: false, status: local.ok ? 'off' : 'error', message: local.ok ? 'Push is off. Stock alerts are still saved here.' : local.message });
        return;
      }
      const result = await notificationService.initializeForUser(session.id, session.active_session_id, { stocksEnabled: true });
      if (valid()) setStockNotifications({ enabled: true, status: result.status, message: result.message });
    } catch (_) {
      if (valid()) setStockNotifications(previous => ({ ...previous, status: 'error', message: 'Your stock notification setting could not be checked. Try again.' }));
    }
  }, [activeUserRef, apiBase]);

  const onToggleStockNotifications = useCallback(async enabled => {
    const session = activeUserRef.current;
    if (!session?.active_session_id || sameSession(changingPreference.current, session)) return;
    changingPreference.current = session;
    const revision = ++preferenceRevision.current;
    const valid = () => revision === preferenceRevision.current && sameSession(activeUserRef.current, session);
    setStockNotifications(previous => ({ ...previous, status: 'loading', message: enabled ? 'Setting up stock alerts…' : 'Turning stock push off…' }));
    let preferenceSaved = false;
    let localDisable = null;
    try {
      // Must start before the first await so iOS retains the user's tap.
      if (enabled) {
        const permission = await notificationService.requestPermissionForStocks();
        if (!valid()) return;
        if (!permission.ok) {
          setStockNotifications(previous => ({ ...previous, status: permission.status, message: permission.message }));
          return;
        }
      } else {
        localDisable = await notificationService.disableStockNotifications(session);
        if (!valid()) return;
      }
      await axios.put(`${apiBase}/stocks/notification-preferences`, { stocks_enabled: Boolean(enabled) }, { headers: sessionHeaders(session) });
      preferenceSaved = true;
      if (!valid()) return;
      if (!enabled) {
        setStockNotifications({ enabled: false, status: localDisable?.ok ? 'off' : 'error', message: localDisable?.ok ? 'Push is off. Stock alerts are still saved here.' : localDisable?.message || 'Stock push is off for your account. Reload this browser to finish clearing its notification setting.' });
        return;
      }
      const result = await notificationService.initializeForUser(session.id, session.active_session_id, { stocksEnabled: true });
      if (valid()) setStockNotifications({ enabled: true, status: result.status, message: result.message });
    } catch (_) {
      if (valid()) setStockNotifications(previous => ({
        ...previous,
        enabled: preferenceSaved ? Boolean(enabled) : previous.enabled,
        status: 'error',
        message: preferenceSaved
          ? 'Your setting is saved, but this device could not finish registering. Try enabling stock alerts again.'
          : 'Your stock notification setting could not be saved. Please try again.'
      }));
    } finally {
      if (sameSession(changingPreference.current, session)) changingPreference.current = null;
    }
  }, [activeUserRef, apiBase]);

  useEffect(() => {
    const session = currentUser;
    ++feedRevision.current;
    ++preferenceRevision.current;
    changingPreference.current = null;
    setStockAlerts([]);
    setStockAlertsError('');
    setStockAlertsStatus('loading');
    setStockNotifications({ enabled: false, status: 'loading', message: '' });
    if (!session?.active_session_id) return undefined;
    loadPreferences();
    return () => {
      ++feedRevision.current;
      ++preferenceRevision.current;
      notificationService.clearSession(session);
    };
  }, [currentUser?.id, currentUser?.active_session_id, loadPreferences]);

  useEffect(() => {
    if (!currentUser?.active_session_id || activeTab !== 'stocks') return undefined;
    loadStockAlerts();
    const timer = window.setInterval(() => {
      if (!document.hidden) loadStockAlerts();
    }, 30000);
    return () => window.clearInterval(timer);
  }, [currentUser?.id, currentUser?.active_session_id, activeTab, loadStockAlerts]);

  useEffect(() => {
    const refresh = () => {
      if (document.hidden || !activeUserRef.current) return;
      loadPreferences();
      if (activeTab === 'stocks') loadStockAlerts();
    };
    const incoming = () => {
      if (activeUserRef.current && activeTab === 'stocks') loadStockAlerts();
    };
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', refresh);
    window.addEventListener('cashoutai:stock-alert', incoming);
    return () => {
      window.removeEventListener('focus', refresh);
      document.removeEventListener('visibilitychange', refresh);
      window.removeEventListener('cashoutai:stock-alert', incoming);
    };
  }, [activeTab, activeUserRef, loadStockAlerts, loadPreferences]);

  useEffect(() => {
    const openLink = value => {
      try {
        const url = new URL(value, window.location.origin);
        if (url.origin !== window.location.origin || url.pathname !== '/') return;
        const next = readStockAlertLink(url.search);
        if (!next) return;
        setDestination(next);
        setActiveTab('stocks');
        window.history.replaceState({}, '', `${url.pathname}${url.search}`);
      } catch (_) { /* Ignore malformed or external notification destinations. */ }
    };
    const message = event => {
      if (event.data?.type === 'OPEN_STOCK_ALERT') openLink(event.data.url);
    };
    const popstate = () => openLink(window.location.href);
    navigator.serviceWorker?.addEventListener('message', message);
    window.addEventListener('popstate', popstate);
    return () => {
      navigator.serviceWorker?.removeEventListener('message', message);
      window.removeEventListener('popstate', popstate);
    };
  }, [setActiveTab]);

  return {
    stockAlerts, stockAlertsStatus, stockAlertsError, stockNotifications,
    onRefreshStockAlerts: loadStockAlerts, onToggleStockNotifications,
    initialStockSymbol: destination?.symbol || '', selectedStockAlertId: destination?.alertId || ''
  };
}
