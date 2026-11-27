/* global self, caches, URL */
// Retirement update for the obsolete cache-first worker. Keep this URL served:
// browsers with an older installation can update even before loading new HTML.
// No fetch handler means an existing tab's next request goes to the network.
const LEGACY_CACHE = 'cashoutai-v1';

function ownsLegacyRegistration() {
  const expected = new URL('/sw.js', self.location.origin).href;
  if (self.location.href !== expected || self.registration.scope !== new URL('/', self.location.origin).href) return false;
  return [self.registration.installing, self.registration.waiting, self.registration.active]
    .filter(Boolean).every(worker => worker.scriptURL === expected);
}

self.addEventListener('install', event => {
  event.waitUntil(Promise.resolve().then(() => {
    // A concurrent Firebase registration must not be replaced by this retired
    // script. Reject only this installation and leave that registration alone.
    if (!ownsLegacyRegistration()) throw new Error('Legacy worker retirement does not own this registration.');
    return self.skipWaiting();
  }));
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    try { await caches.delete(LEGACY_CACHE); } catch (_) { /* Unregister even if cache storage is unavailable. */ }
    // Recheck after the asynchronous delete: another tab may now be installing
    // the Firebase worker on the same scope. Never unregister that update.
    if (ownsLegacyRegistration()) await self.registration.unregister();
    // Do not navigate clients or claim unrelated pages. Existing drafts and
    // sessions stay in place; one manual refresh loads the current app.
  })());
});
