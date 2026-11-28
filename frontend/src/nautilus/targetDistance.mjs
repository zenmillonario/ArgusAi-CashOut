// Display only. Never use this distance for execution or substitute missing marks.
export function targetDistance(underlying, target) {
  if (!Number.isFinite(underlying) || !Number.isFinite(target) || underlying <= 0 || target <= 0)
    return { direction: 'unknown', label: '—' };
  const delta = underlying - target;
  if (!Number.isFinite(delta)) return { direction: 'unknown', label: '—' };
  if (delta === 0) return { direction: 'at', label: '$0.00' };
  const direction = delta > 0 ? 'above' : 'below';
  const sign = delta > 0 ? '+' : '−';
  const magnitude = Math.abs(delta);
  // Keep small XRP/DOGE differences visible without long BTC decimal tails.
  const decimals = magnitude >= 1 ? 2 : magnitude >= .01 ? 4 : 6;
  const label = magnitude < .000001 ? sign + '<$0.000001' : sign + new Intl.NumberFormat('en-US', {
    style: 'currency', currency: 'USD', minimumFractionDigits: decimals, maximumFractionDigits: decimals,
  }).format(magnitude);
  return { direction, label };
}
