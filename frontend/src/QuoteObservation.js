import React from 'react';

// A receipt time does not establish when the market observation occurred.
export default function QuoteObservation({ quote, unavailable = false }) {
  const stamp = quote?.source_timestamp;
  const date = stamp ? new Date(stamp) : null;
  const validTime = date && Number.isFinite(date.getTime());
  const provider = String(quote?.source || '').startsWith('FMP') ? 'FMP' : 'Market data';
  return <div className="text-xs mt-1 space-y-1 opacity-80">
    <div>{unavailable ? 'Refresh unavailable. ' : ''}{validTime
      ? `${provider} · Observed ${date.toLocaleString()}`
      : 'Quote time unavailable'}</div>
    <div>Market session and feed delay are not verified.</div>
  </div>;
}
