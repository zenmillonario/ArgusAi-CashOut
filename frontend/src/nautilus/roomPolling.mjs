// Keep large room snapshots off the network while the app is in the background.
// A visibility change never starts a second request while an earlier one settles.
export function startVisiblePolling(task, intervalMs, {
  visibility = document,
  setTimer = setTimeout,
  clearTimer = clearTimeout,
  onError = () => {},
} = {}) {
  let stopped = false;
  let running = false;
  let timer = null;
  let controller = null;
  let refreshRequested = false;
  const hidden = () => visibility.visibilityState === 'hidden';
  const cancelTimer = () => { if (timer !== null) clearTimer(timer); timer = null; };
  const schedule = delay => {
    if (stopped || hidden()) return;
    cancelTimer();
    timer = setTimer(run, delay);
  };
  async function run() {
    timer = null;
    if (stopped || hidden() || running) return;
    running = true;
    controller = new AbortController();
    const signal = controller.signal;
    try { await task(signal); }
    catch (error) { if (!stopped && !signal.aborted) onError(error); }
    finally {
      running = false;
      controller = null;
      const delay = refreshRequested ? 0 : intervalMs;
      refreshRequested = false;
      schedule(delay);
    }
  }
  const visibilityChanged = () => {
    cancelTimer();
    if (hidden()) { refreshRequested = false; controller?.abort(); }
    else if (running) refreshRequested = true;
    else run();
  };
  visibility.addEventListener('visibilitychange', visibilityChanged);
  run();
  return () => {
    stopped = true;
    cancelTimer();
    controller?.abort();
    visibility.removeEventListener('visibilitychange', visibilityChanged);
  };
}

export function roomAssetsToPoll(activeAsset, positions = [], supportedAssets = []) {
  return [...new Set([activeAsset, ...positions.filter(position => position.quantity > 0).map(position => position.asset)])]
    .filter(asset => supportedAssets.includes(asset));
}

// A background read started before a buy/close/reset may return afterward.
// Revisions belong to the same session-scoped component and only advance.
export function preferNewerPracticeLedger(current, incoming) {
  if (!Number.isSafeInteger(incoming?.revision) || incoming.revision < 0 || !incoming.account) return current;
  return !current || incoming.revision >= current.revision ? incoming : current;
}
