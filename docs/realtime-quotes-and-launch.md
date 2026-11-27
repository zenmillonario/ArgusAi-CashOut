# Real-time stock quotes and launch planning

Research date: **25 November 2026**. Prices below are published US-dollar prices, checked against provider-owned pages. They are planning inputs, not a subscription or a negotiated commercial quote. No paid service, user financial account, quote feed, or live notification was activated for this research.

For signup, account approval, the launch sequence, and the existing app’s implementation status, see [member-launch-plan.md](member-launch-plan.md).

## Recommended direction

CashOutAI should obtain one licensed provider feed on the server, share subscriptions for the same symbols, and distribute updates to authenticated members. Each person opening the same stock should not create another provider request or connection.

Start by requesting commercial display terms from the existing Financial Modeling Prep provider. Compare that proposal with Twelve Data’s business entry tier. Treat Massive’s consolidated-market option as a higher-cost benchmark if full US-market coverage is required. A published personal API price is not the price of permission to display data inside a paid membership app.

Before choosing a provider, decide which output the app needs:

- A live last-price display and practice chart can use an appropriately licensed trade-price feed, with its venue coverage disclosed.
- Executable bid/ask, spread-sensitive practice fills, consolidated volume, or a claim of consolidated US prices require the relevant quote data and exchange entitlements.
- A ticker being available does not establish that the feed contains every US exchange’s trades.
- The thinkorswim email → Zapier → stock alert intake is separate from a continuous quote stream. Alert delivery alone does not require streaming the entire market.

## Provider comparison

### Financial Modeling Prep: retain the existing integration if commercial terms fit

The [published pricing page](https://site.financialmodelingprep.com/pricing-plans) lists:

| Plan | Monthly billing | Annual billing, monthly equivalent | Published API limit |
| --- | ---: | ---: | ---: |
| Basic | $0 | $0 | 250 calls/day |
| Starter | $29/month | $19/month | 300 calls/minute |
| Premium | $69/month | $49/month | 750 calls/minute |
| Ultimate | $139/month | $99/month | 3,000 calls/minute |

These public personal/developer figures are useful for comparison, but **none should be treated as an approved CashOutAI commercial display budget**. The same pricing page requires a specific Data Display and Licensing Agreement for displaying or redistributing data. The [terms of service](https://site.financialmodelingprep.com/terms-of-service) likewise distinguish personal use from licensed commercial use. [Enterprise plans](https://site.financialmodelingprep.com/enterprise) provide custom commercial arrangements, streaming access, and limits; no fixed commercial price was verified.

The [current stable quote documentation](https://site.financialmodelingprep.com/developer/docs/stable/quote) documents the stable quote endpoint and provider timestamp. The current percentage-change field is `changePercentage`; integration code should map that field explicitly rather than assume a legacy field name. After-hours data uses separate endpoints and should not be presented as regular-session data without a label.

The [WebSocket documentation](https://site.financialmodelingprep.com/developer/docs/websocket-api) is explicitly labeled legacy. It documents subscription and unsubscription events plus trade and top-of-book message types, but production implementation should use the account’s currently approved endpoint and entitlement. The [FAQ](https://site.financialmodelingprep.com/faqs) describes Ultimate-level personal streaming access after a User Declaration approval and a connection limit per cluster. That does not grant external member-display permission.

**Questions for the FMP commercial quote:** paid-member display; permitted markets and venues; consolidated versus venue-limited trades/quotes; regular and extended hours; connection and symbol limits; message or bandwidth ceilings; caching and historical retention; whether batch REST calls are billed per request or per symbol; exchange reporting; and total recurring cost.

### Twelve Data: lower published business entry price, with coverage and rights to confirm

The [business pricing page](https://twelvedata.com/pricing-business) lists these Venture configurations:

| Venture configuration | Monthly billing | Annual billing, monthly equivalent | API credits/minute | WebSocket credits |
| --- | ---: | ---: | ---: | ---: |
| Entry | $149/month | $124/month | 610 | 500 |
| Mid | $299/month | $248/month | 1,597 | 1,500 |
| Larger | $499/month | $414/month | 2,584 | 2,500 |

The entry configuration is also described in the provider’s [trial information](https://support.twelvedata.com/en/articles/5335783-trial). A pricing card’s selected larger configuration should not be mistaken for the minimum plan.

Business pricing includes external-display language. However, the [US equities data guide](https://support.twelvedata.com/en/articles/9935903-us-equities-market-data) says external distribution requires the applicable US equities add-on. Obtain written confirmation covering this exact use: an authenticated, paid-member web app, expected users, displayed fields, and caching. **$149/month is a published base price, not a verified all-in commercial quote.**

The same US-equities guide describes the standard real-time feed as covering listed US symbols while representing approximately **5% of total US trading volume**. Symbol coverage and trade coverage are different. Full-market licensed access requires discussion with the provider. Do not describe the standard feed as a consolidated US feed or use its volume as total-market volume.

The [credits guide](https://support.twelvedata.com/en/articles/5615854-credits) specifies:

- A WebSocket credit is tied to a subscribed symbol, rather than each incoming price tick.
- REST usage depends on endpoint weight and symbol count. Putting multiple symbols in one HTTP request does not necessarily save API credits.
- The standard connection allowance is three concurrent WebSocket connections; opening another can close an earlier connection.
- REST quota exhaustion returns HTTP 429.

The [WebSocket FAQ](https://support.twelvedata.com/en/articles/5194610-websocket-faq) describes the price stream as prices, not a bid/ask, OHLC, or technical-indicator stream. Its 100-events-per-minute restriction concerns outgoing subscription control events, not incoming price updates. Use the current pricing table for symbol allowances because older FAQ examples may refer to different configurations.

For a small initial set of 20 shared symbols, the entry tier’s 500 WebSocket credits leaves ample subscription capacity. Required commercial rights and feed adequacy are the remaining decision points.

### Massive: useful benchmark for full-market data

The [business page](https://massive.com/business) publishes:

| Item | Monthly price | Meaning |
| --- | ---: | --- |
| Stocks Business base | $2,499 | Business platform with the base data package |
| Full Market real-time expansion | +$1,999 | Full-market real-time data, plus applicable exchange fees |
| IEX expansion | +$499 | A single-exchange feed |
| Full Market delayed expansion | +$499 | 15-minute delayed full-market data |

The base plus full-market real-time expansion totals **$4,498/month before exchange fees**. Confirm the exact rights and exchange obligations in the proposal. This is not interchangeable with Massive’s approximately $199/month [individual Advanced plan](https://massive.com/pricing), which is not a commercial membership-app license.

Massive explicitly explains that the business base’s real-time [Fair Market Value data](https://massive.com/knowledge-base/article/does-the-business-plan-include-real-time-trades-and-quotes-or-only-fair-market-value) is an estimated value. It is not the same as an actual exchange last trade or an executable bid/ask quote. The relevant expansion is needed for those real-time exchange data products.

[Business Stocks documentation](https://massive.com/business-stocks) describes three WebSocket connections with the base plan, with an additional connection for an expansion, and broad API access. “Unlimited API calls” still requires a consumer capable of handling the stream and does not remove data licensing, connection, or operational constraints.

## TradingView widget boundaries

An embedded TradingView widget can remain a separate chart experience. Its data availability follows the widget’s supported exchanges and delays. Purchasing a personal TradingView plan or additional exchange data does not automatically upgrade data in embedded widgets.

TradingView’s [widget data FAQ](https://www.tradingview.com/widget-docs/faq/data/) also states that widgets do not provide an API for extracting the underlying data and cannot be supplied with the app’s own feed. Consequently:

- Do not scrape a widget to drive CashOutAI’s price panel, practice calculator, or Nautilus.
- Label the native quote feed and the widget’s data separately if they differ.
- A future native stock Nautilus should consume CashOutAI’s properly licensed feed.
- A quote subscription purchased from another provider does not change TradingView widget entitlements.

## Transparent usage model

Assume:

- 100 members viewing the app at once.
- 10 symbols per member.
- A five-second refresh interval.
- Only 20 distinct symbols across all those members.
- A regular US session modeled as 6.5 hours = 390 minutes.
- 21 sessions in an illustrative month.

These are workload assumptions, not observed app traffic. Extended-hours operation increases totals.

### REST polling

Individual browser-driven polling:

```text
100 users × 10 symbols ÷ 5 seconds = 200 symbol requests/second
200 × 60 = 12,000 requests/minute
12,000 × 390 = 4,680,000 requests/session
4,680,000 × 21 = 98,280,000 requests/month
```

Shared server polling of only the 20 unique symbols:

```text
20 symbols ÷ 5 seconds = 4 symbol requests/second
4 × 60 = 240 requests/minute
240 × 390 = 93,600 requests/session
93,600 × 21 = 1,965,600 requests/month
```

| Approach | HTTP requests/minute | Requests/session | Requests/21-session month |
| --- | ---: | ---: | ---: |
| Each user polls 10 symbols | 12,000 | 4,680,000 | 98,280,000 |
| Server polls 20 unique symbols individually | 240 | 93,600 | 1,965,600 |
| One supported 20-symbol batch every 5 seconds | 12 | 4,680 | 98,280 |

Deduplication reduces provider symbol polling by **98%**, or **50 times** in this example.

Batching reduces HTTP overhead further, but the provider may still charge 20 symbol credits per batch. Twelve Data, for example, documents symbol-weighted endpoint accounting. A batch request every five seconds could therefore remain **240 credits/minute**, even though there are only 12 HTTP requests/minute. FMP has a [batch quote endpoint](https://site.financialmodelingprep.com/developer/docs/stable/batch-quote); confirm its commercial plan accounting before treating batching as a quota reduction.

### WebSocket streaming

The same scenario would normally require **20 upstream subscribed symbols**, not 1,000 member-symbol subscriptions. For a provider that meters concurrent subscribed symbols, that is 20 active symbol credits.

Incoming message volume is a separate quantity. At a purely illustrative average of one update per second per symbol, the provider would send around 20 updates per second. Actual trade activity can be bursty and much higher. The app’s server sends those updates to interested members; that downstream traffic still grows with audience size.

Do not equate a WebSocket message with a REST API call or assume a universal per-message price. Total cost is the relevant commercial data license, exchange charges if any, provider plan, server capacity, and downstream bandwidth.

## Implementation guardrails

These describe the proposed next implementation. They are not a claim that streaming is already connected in the live app.

1. **One collector per provider feed.** A shared service owns the provider connection, active subscriptions, and last valid quotes. Starting an in-memory singleton inside every web worker would still create duplicate upstream connections; use one designated collector or coordinated shared ownership.

2. **Canonical, counted subscriptions.** Track interests by normalized symbol, venue/feed, and session where relevant. Reference-count members interested in each symbol. Unsubscribe after a short 15–30 second grace period when interest reaches zero, rather than reconnecting on every tab change.

3. **Visible-symbol limits.** Begin with one selected stock plus a small watchlist, such as ten visible symbols per member. Suspend unnecessary subscriptions for hidden or inactive views. Avoid requesting the full market for a single ticker screen.

4. **Shared cache and in-flight deduplication.** The first subscriber uses the latest cached quote while the upstream subscription starts. Concurrent requests for the same REST fallback use one in-flight request. Cache symbol metadata, names, and logos longer than prices.

5. **Global and per-member budgets.** Use token buckets for REST fallback, search, and history. Keep quota headroom, back off on 429 responses, and prevent typing in the ticker field from issuing an unbounded request for every keystroke.

6. **Authenticated delivery.** Keep vendor credentials on the server. App WebSocket or SSE sessions must use approved membership and the current account session. Session replacement should revoke the old live-data subscription, consistently with the single-session policy.

7. **Honest quote status.** Keep the provider’s event time separately from the server receive time. Display source, venue scope, regular/extended session, and whether data is live, delayed, closed-market, reconnecting, or stale. Retain a clearly labeled last known quote through outages; do not generate random prices as a fallback for live data.

8. **Freshness-aware practice.** Use the appropriate fresh quote and side for a simulated fill. If no eligible quote is available, wait or explain why the practice action is unavailable. A last-price-only feed cannot simulate a real bid/ask spread without an explicit modeling assumption.

9. **Controlled rendering.** The server or client may coalesce screen updates, for example every 250–1,000 milliseconds, without inventing intermediate prices. Display cadence and provider event cadence are different.

10. **Useful monitoring.** Track unique subscribed symbols, provider connections, REST credits, subscription churn, source and downstream bytes, stale ages, and quota errors. This makes spending and feed quality visible before the user base grows.

## Launch handoff

The separate ZenMillionaires marketing draft links both existing and new members to the verified app root, **https://cashoutai.app/**. It describes the new workspace as upcoming, while allowing access to the current app. It does not invent a signup path, checkout URL, promotion, launch date, data vendor selection, or real-time entitlement.

Before changing that draft to “available now,” verify the relevant deployed features and a real member journey. A Black Friday offer also needs its exact plan, currency, billed amount, renewal behavior, discount duration, eligibility, start/end time and timezone, cancellation/refund terms, and working checkout/entitlement path. Those business inputs remain separate from this API cost comparison.
