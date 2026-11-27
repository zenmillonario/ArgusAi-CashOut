# Stock quote safety and shared reads

Updated November 25, 2026. This is a reviewed implementation draft, not a production provider verification or a streaming-data launch. No API key, live stock quote request, member trade, or production mutation was used in verification.

## Problem corrected

The original `get_current_stock_price` tried the FMP quote endpoint, then a company profile endpoint, and finally generated a plausible price. Portfolio valuation, automatic stop-loss/take-profit closure, and quote-based position actions could therefore treat a generated value as a market price. Separately, `/api/stock/{symbol}` labeled retrieval time as `timestamp` and read only the older percent-change field.

The draft removes the generated-price helper and the company-profile fallback from these paths. A shared `backend/stock_quotes.py` adapter now provides the last reported FMP quote to the ticker route and legacy portfolio valuation. Provider failure never produces a fabricated price.

FMP continues to document `/stable/quote` at [Stock Quote API](https://site.financialmodelingprep.com/developer/docs/stable/quote). A valid endpoint does not verify the deployed key's current coverage, realtime entitlement, display permission, or exchange-session state. Those remain deployment prerequisites.

## Shared read behavior

- Symbols are trimmed, uppercased and validated. Equivalent `aapl`, ` AAPL ` and `$AAPL` requests share the same key.
- Successful responses are cached for five seconds in one Python process. Cache storage is bounded to 256 entries.
- Requests already in progress for the same symbol are shared. One canceled browser request does not cancel other consumers' provider request.
- Known unavailable results are cached for two seconds to avoid a repeated-request burst during failure. Concurrent in-flight symbols are also bounded.
- Only `/stable/quote` is called. There is no extra profile lookup, generated fallback, new vendor, Redis dependency, or automatic background symbol polling.
- The cache is **per process**. Several server workers or replicas have separate caches and can still issue separate upstream requests. It is not a global market-data stream, and it does not by itself make an insufficient API plan suitable for continuous viewing.

## Quote response contract

`GET /api/stock/{symbol}` preserves `symbol`, `price`, `formatted_price`, `change`, and `changesPercentage`. It also returns canonical `changePercentage`; the canonical provider field is preferred, with the legacy spelling accepted when necessary. Missing numeric changes remain `null` rather than being invented as zero.

Additional fields:

| Field | Meaning |
| --- | --- |
| `source` | `FMP /stable/quote` |
| `source_timestamp` | Valid provider observation time in UTC, or `null` |
| `timestamp` | Compatibility alias of `source_timestamp`, never retrieval time |
| `received_at` | When this process received the provider response |
| `timestamp_status` | `valid`, `missing`, or `invalid` |
| `status` | `recent`, `stale`, `timestamp_missing`, `timestamp_invalid`, or `timestamp_future` |
| `age_seconds` | Age of the provider observation, or `null` |
| `cache_hit` | Whether this caller reused a cached or shared response |
| `market_status` | `unverified` in this integration |
| `delay_status` | `unverified` in this integration |
| `execution_eligible` | `false` in this integration |
| `execution_reason` | Explains the missing market-session and realtime-entitlement verification |

`recent` means only that the provider timestamp is no more than 30 seconds old. It does not establish an open exchange, an undelayed subscription, available liquidity, or an executable bid/ask. Age is recomputed on cache reads; cache access does not refresh the provider timestamp or original receipt time. Missing, invalid, timezone-free, and implausibly future timestamps are not replaced with the current time.

Provider failures produce an HTTP error with a structured `detail` containing `code`, `message`, `symbol`, `source`, and `status: unavailable`. Error responses do not contain provider request URLs or API keys.

## Portfolio and paper-journal behavior

A valid provider last price may update observed valuation and unrealized P&L, with its source and timestamps. If the quote is unavailable, the previous price, quantity, P&L, and observation timestamps are retained. The row is explicitly marked unavailable. Older saved prices with no provenance are labeled `legacy_unverified`; they are not retroactively certified as genuine observations.

`GET /api/positions/{user_id}` includes `quote`, `valuation_status`, `valuation_as_of`, `valuation_received_at`, `price_provenance`, and `execution_eligible` explicitly, so the existing Position model cannot silently drop that metadata.

Automatic stock stop-loss/take-profit closure is suspended for this unverified last-price integration. A portfolio read cannot create a synthetic exit. Quote-based Close and position actions with no supplied price fail before any trade or position mutation while execution eligibility is unverified.

Explicitly entered manual journal prices remain available. New records carry `price_source: manual_journal` and `price_verified: false`, including trade-history output. These are member-entered practice records, not verified market executions. The prior paper-journal accounting and XP system still needs its separately documented broader review before competitive performance claims.

The five-bot binary `$100` practice ledger, its venue snapshots, and its quote checks are separate and unchanged by this adapter.

## Verification and remaining work

Focused tests use synthetic provider fixtures and isolated data collections. They cover normalized concurrent reuse, cache expiry and size, cancellation shielding, provider failures, invalid prices, missing/invalid/future/stale timestamps, percent-field compatibility, preservation of positions on failure, suppression of automatic exits, quote-based mutation failure, and manual-journal provenance.

Before enabling market-derived stock fills or automatic exits, verify the actual FMP account and display rights, integrate authoritative market-session/delay information, and define an explicit paper-fill policy. A last-trade price alone does not justify treating every displayed observation as an executable current tick. No production API configuration or provider subscription was changed.
