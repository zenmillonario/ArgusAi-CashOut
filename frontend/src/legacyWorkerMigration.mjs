const LEGACY_CACHE = 'cashoutai-v1';

function isLegacyRegistration(registration, origin) {
  try {
    const expected = new URL('/sw.js', origin).href;
    if (registration.scope !== new URL('/', origin).href) return false;
    const workers = [registration.installing, registration.waiting, registration.active].filter(Boolean);
    // A registration can temporarily contain an old active worker and a new
    // Firebase worker. Only an entirely legacy registration is ours to retire.
    return workers.length > 0 && workers.every(worker => worker.scriptURL === expected);
  } catch (_) { return false; }
}

export async function retireLegacyServiceWorker({
  serviceWorker = globalThis.navigator?.serviceWorker,
  cacheStorage = globalThis.caches,
  origin = globalThis.location?.origin,
} = {}) {
  const result = { matched: 0, unregistered: 0 };
  if (!serviceWorker?.getRegistrations || !origin) return result;
  let registrations;
  try { registrations = await serviceWorker.getRegistrations(); }
  catch (_) { return result; }

  for (const registration of registrations) {
    if (!isLegacyRegistration(registration, origin)) continue;
    result.matched += 1;
    // Fetch the retirement script for tabs still controlled by the old worker.
    // Offline/update failure must not prevent retiring the known old cache.
    try { await registration.update(); } catch (_) { /* Continue with guarded retirement. */ }
    if (!isLegacyRegistration(registration, origin)) continue;
    try { await cacheStorage?.delete(LEGACY_CACHE); } catch (_) { /* Registration removal still helps the next navigation. */ }
    if (!isLegacyRegistration(registration, origin)) continue;
    try { if (await registration.unregister()) result.unregistered += 1; }
    catch (_) { /* A future startup can retry; never interrupt app rendering. */ }
  }
  return result;
}
