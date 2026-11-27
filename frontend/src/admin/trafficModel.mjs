// No visitor IDs, query strings, referrers, credentials or personal details.
export async function recordAppOpen(browser, send, backend = '') {
  try {
    if (browser.__CASHOUTAI_PRIVATE_LANDING__ !== false || browser.self !== browser.top) return false;
    const response = await send(backend.replace(/\/+$/, '') + '/api/traffic/open', {
      method: 'POST', credentials: 'omit', referrerPolicy: 'no-referrer', keepalive: true,
    });
    return response.ok === true;
  } catch (_) { return false; } // Analytics must never interrupt sign-in.
}
