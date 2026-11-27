const finite = value => typeof value === 'number' && Number.isFinite(value);

function closeTimestamp(value) {
  if (finite(value) && value > 0) {
    const milliseconds = value < 1e12 ? value * 1000 : value;
    return Number.isFinite(new Date(milliseconds).getTime()) ? milliseconds : null;
  }
  // API contract times are ISO timestamps with an explicit timezone. A blank,
  // date-only string or a locale-specific date must never become a live clock.
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value)) return null;
  const milliseconds = Date.parse(value);
  return finite(milliseconds) && milliseconds > 0 ? milliseconds : null;
}

/** A known contract closes at the same instant even when a quote is delayed. */
export function deriveContractClock(snapshot = {}, nowMs = Date.now()) {
  const contract = snapshot.contract || {};
  const closeTime = closeTimestamp(contract.closeTime);
  const run = snapshot.native?.run;
  const recorded = ['replay', 'demo'].includes(snapshot.mode) || run?.review === true || run?.stopped === true;
  const savedRemaining = finite(contract.remainingSeconds) && contract.remainingSeconds >= 0
    ? Math.floor(contract.remainingSeconds) : null;
  if (recorded) return { kind: 'recorded', remainingSeconds: savedRemaining, closeTime, ended: false };
  const knownContract = typeof contract.id === 'string' && contract.id.trim().length > 0;
  if (!knownContract || closeTime === null || !finite(nowMs) || nowMs <= 0) {
    return { kind: 'unavailable', remainingSeconds: null, closeTime: null, ended: false };
  }
  if (run?.stopped !== false || run?.review !== false) {
    return { kind: 'recorded', remainingSeconds: savedRemaining, closeTime, ended: false };
  }
  return {
    kind: 'countdown',
    remainingSeconds: Math.max(0, Math.floor((closeTime - nowMs) / 1000)),
    closeTime,
    ended: nowMs >= closeTime,
  };
}
