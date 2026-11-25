# Nautilus bot rooms

This release candidate adds BTC, ETH, SOL, XRP, and DOGE rooms with the native Nautilus chart, an asset-specific community chat, bot positions and trades, and a member practice account. These feature changes are prepared in source; the hosting migration alone did not deploy them. Bounded legacy ownership, administrator-role, and privacy repairs are included. Source validation does not establish live publisher, provider, email, or device delivery readiness.

## Backend and publisher setup

The app mounts `create_nautilus_router(db, settlement_service=nautilus_settlement_service)` from `backend/nautilus_api.py` under `/api/nautilus`. It uses the existing Mongo connection and three collections: `nautilus_snapshots`, `nautilus_chat`, and `nautilus_practice`. The backend lifespan starts one shared `NautilusSettlementService`; member refreshes and the background worker use that same resolver.

Configure the same `NAUTILUS_PUBLISHER_KEY` on the backend and on the machine running the five PAPER engines. Use a generated secret containing 32–512 printable ASCII characters and store it in environment/secret configuration. Do not put it in React variables, source control, browser storage, or member requests. Also configure `NAUTILUS_BACKEND_URL` on the engine machine with the HTTPS backend origin.

The publisher uses Python's standard library:

```bash
export NAUTILUS_BACKEND_URL=https://your-backend.example
# Set NAUTILUS_PUBLISHER_KEY from your secret configuration in this environment.
python scripts/publish_nautilus.py --once
python scripts/publish_nautilus.py
```

Start the existing PAPER engines first. Their read-only native endpoints must be available on the following loopback ports:

| Asset | Local port |
|---|---:|
| BTC | 8787 |
| ETH | 8788 |
| SOL | 8789 |
| XRP | 8790 |
| DOGE | 8791 |

The publisher polls `/api/nautilus?ui_build=0.0.8.4` once per second and sends packets to `POST /api/nautilus/ingest/{asset}`. Sources are fixed to `127.0.0.1`. Redirects are refused; the publisher secret is sent only to the configured backend, never to the local engine. The publisher has no venue credentials, order API, or strategy controls. A development-only `--allow-local-http` option permits an explicitly supplied localhost HTTP backend.

The `ui_build` value identifies the dashboard protocol, not the PAPER engine version. The available recorded examples pair dashboard build `0.0.8.4` with engine `0.0.10.4_PAPER_ONLY`; the API fixture also covers the `0.0.10.7_PAPER_ONLY` display schema. Before enabling the user's current Windows engines, verify their actual asset, port, freshness fields, and packet shape. Do not change the dashboard identifier merely to match a newer engine's version number.

Only matching asset packets with `mode: "PAPER_ONLY"`, `readonly: true`, and a PAPER engine version are accepted. The API stores an explicit recursive allowlist of public display fields and rejects oversized, malformed, or out-of-order packets. Native strategy normalization has already been reversed by the native adapter: the legacy `market.btc` field contains the selected asset's actual USD price.

## Member API

Every member route requires `X-User-ID` and `X-Session-ID`. The latter must match the user's stored active session. Access requires an approved membership or an unexpired trial. Author names, account ownership, balances, and execution prices are supplied by the server.

| Method and route | Request / result |
|---|---|
| `GET /bots/{asset}` | `{snapshot, state, receivedAt}`; state is `live`, `stale`, or `offline` |
| `GET /chat/{asset}` | `{messages: [{id, author, content, createdAt, isAdmin}]}` |
| `POST /chat/{asset}` | `{text}` → `{message}`; plaintext, maximum 1,000 characters |
| `GET /practice` | Reconciles eligible official results, then returns `{account, revision, feePolicy: "fees-excluded"}` |
| `POST /practice/buy` | `{attemptId, revision, transactionId, asset, contractId, side, budget}` |
| `POST /practice/close` | `{attemptId, revision, transactionId, positionId}` |
| `POST /practice/reset` | `{attemptId, revision, transactionId}` |

All routes above are relative to `/api/nautilus`. Practice mutations return the same account/revision shape as GET. Errors contain a human-readable `detail` string. Refresh the account on a 409 conflict; do not silently resubmit a different action using an old revision or transaction ID.

## Practice behavior

Each member has **one $100 USD practice balance shared across all five asset rooms**. Bot performance and the member's practice account are separate ledgers. Money is stored as integer microdollars. An order buys the whole number of contracts that fits the selected budget and available cash; closing uses the matching contract's native bid.

The server selects the ask or bid from its authenticated native snapshot. Browser-supplied balances, quotes, marks, and fees are rejected. These are top-of-book practice fills with **fees excluded**: the explicit practice fee is zero until applicable venue fee metadata is supplied. Do not present practice results as net-of-fee venue performance.

Before a fill, the backend requires a received snapshot no older than 15 seconds, source/run/underlying-price timestamps no older than five seconds, and a verified native quote no older than three seconds whose `valid_until` has not elapsed. Asset, side, quote ticker, and current market ticker must match; the contract must remain open. Stopped, archived/review, stale, missing-price, and expired sources cannot fill practice orders.

Each mutation includes the current attempt ID, revision, and a unique transaction ID. Mongo compare-and-swap persistence prevents concurrent requests from spending the same balance twice. A repeat of the same recorded request returns the account without another fill. Reset restores $100, clears the active attempt, advances the revision, and generates a new attempt ID, so delayed actions from an old tab cannot cross the reset.

### Official settlement after expiration

`backend/kalshi_settlements.py` resolves outcomes directly from Kalshi's public HTTPS market API. It uses the exact held contract's `/markets/{ticker}` record and falls back to `/historical/markets/{ticker}` only after a `404`. No exchange authentication key, trading endpoint, or new environment setting is required. The request origin and paths are fixed, and redirects are refused. See the official [Get Market schema](https://docs.kalshi.com/api-reference/market/get-market.md) and [Get Historical Market schema](https://docs.kalshi.com/api-reference/historical/get-historical-market.md).

Only an exact supported ticker with `market_type: binary`, `status: finalized`, explicit YES/NO result, $1 notional, default settlement bounds, and a matching $1/$0 YES payout is accepted. Close and settlement timestamps must be valid and settlement must already have occurred. Provisional markets are excluded. A closed, determined, disputed, scalar, fractional, mismatched, missing, or unavailable result leaves the position reserved. The outcome is never inferred from the underlying price, a newer contract, or the bot's own trade history.

The service applies the full remaining position to the virtual ledger using the official result and records a `SETTLE` transaction with source, contract, winning side, close time, settlement time, verification time, notional, and payout evidence. It uses the account revision and attempt ID in the same compare-and-swap update. Concurrent workers cannot credit a position twice, and a result arriving after Reset cannot restore the old attempt. New purchases retain a server-owned `contractCloseTime`; older positions without that field remain eligible for official lookup.

Authenticated account refresh reconciles results. The background worker scans accounts with open positions in pages of 20, with a 15-second pause between passes. Each account pass checks at most eight distinct eligible contracts, rotating through larger sets. In one backend process the resolver shares requests, permits four simultaneous lookups and at most 16 in-flight keys, limits each lookup to six seconds, and keeps at most 256 cache entries. Pending/unavailable results are cached for 30 seconds; verified final results for one hour. These are process-local limits, not a global multi-replica quota.

Members see cash reserved while a final result is unavailable and may reset to a new $100 attempt. The interface refreshes the account every 15 seconds while open positions exist and the page is visible; newer account revisions protect buys, closes, resets, and settlements from delayed polling responses. Recent practice results distinguish closes at bid from official settlements. Fees remain excluded from both forms of practice result.

### Network and session behavior

While the page is visible, bot snapshots refresh for the selected asset and assets with open practice positions, rather than all five rooms. Chat refreshes only for the selected room. Polls stop and outstanding polling requests are canceled when the page becomes hidden; returning to the page refreshes immediately. Freshness timers continue to prevent an old quote from becoming executable merely because a prior snapshot remains on screen.

The backend enables gzip for HTTP responses of at least 1,024 bytes with compression level 5. This reduces repeated full-snapshot transfer without changing native values or WebSocket messages. These changes do not introduce delta streaming or a provider-wide quote budget. Actual transfer, CPU usage, and provider quotas still need observation after the live publishers are connected.

## Verification

Run from the repository root after installing the backend dependencies:

```bash
python -B -m unittest discover -s backend/tests -p 'test_*.py'
node --test frontend/src/*.test.mjs frontend/src/nautilus/*.test.mjs frontend/src/social/*.test.mjs frontend/src/billing/*.test.mjs
```

API tests use an in-memory fake database and an ASGI transport; they do not contact Mongo, local engines, a venue, or a production account. They cover session/trial access, publisher credentials and projection, quote freshness and matching, chat ownership, native-price accounting, duplicate requests, concurrent writes, reset isolation, input limits, and publisher URL/redirect restrictions. The settlement tests use synthetic official-response fixtures and HTTP mock transports to cover outcome validation, cache/concurrency bounds, timeout/failure behavior, historical fallback, duplicate-credit prevention, and reset races. Real deployment still needs the configured Windows engine host, HTTPS backend, publisher secret, and a controlled integration run.

## Account maintenance included in this draft

The legacy account flow now requires an expiring email verification token for password recovery, keeps session credentials out of public user records, persists registration password hashes, fails closed for accounts without a hash, and requires an existing session to change the recovery email. Predictable default-admin creation and automatic promotion have been removed. Existing accounts created with missing hashes must use verified email recovery; the email provider must be configured before rollout. Existing production credentials are not changed by this source patch.

The legacy router now binds its member operations to the verified active session, checks administrator-only operations, rejects conflicting acting user/admin IDs, and protects private account, ledger, referral, inbox, and mutation paths. Member-visible profiles, follow lists, and earned badges keep their intended visibility. Hidden profile locations are omitted from other members' JSON responses. The old administrative re-registration action reopens the existing rejected identity as pending while preserving credentials, profile, relationships, and history. These bounded repairs do not constitute a complete audit of every legacy business rule; see [social-training-review.md](social-training-review.md).

The standalone private design preview uses real recorded PAPER packets and local browser-only practice/chat. It is separate from the current production app and does not exercise the production Mongo/email services.

The November 25 release candidate passed the **complete CRA production build**, **181 consolidated backend tests**, and **61 JavaScript tests**. The backend total includes **15 official-settlement tests** and the **20 existing Nautilus API/ledger tests**. Settlement tests use synthetic official-response fixtures; they do not verify live official-result retrieval.

The current browser review served the actual compiled app inside a clearly labeled, isolated review fixture. It used synthetic accounts, messages, payments, and practice ledgers, plus unchanged archived PAPER packets. Real payments, email, push, service-worker registration, and external provider connections were disabled. Confirmed checks were:

- Responsive layouts at 375px phone, 1280px desktop, and 1920px TV widths, with no horizontal app overflow at the phone and TV sizes; fullscreen fallback and TV mode.
- Room chat opening and closing with Escape, plus inspection of a recorded entry.
- A position awaiting settlement remaining reserved and unpriced; Reset starting a new $100 attempt; an explicitly synthetic settled result appearing in practice history.
- Synthetic manual approval with the unavailable-email outcome displayed, followed by the pending account showing active membership after refresh.
- Stocks accepting NVDA and showing its honest unavailable state when the external chart was blocked.
- Community and profile screens, plus achievements retaining XP and badges without a cash-reward promise.

These checks cover the compiled UI and fixture response contracts. They do not establish production authentication, calendar-month entitlement calculations, live feed freshness, fresh-quote executions, actual settlement retrieval, recovery-email delivery, device push, or licensed streaming. The feature release remains a draft and has not changed the current live app; the deployed frontend/backend/service-worker combination still needs coordinated verification.

Separately from the isolated fixture, Resend accepted one owner-approved plain test email with HTTP 200 using the existing configured sender and key. No password-reset token was included, and no member or credential data was changed. Inbox receipt awaits user confirmation; provider acceptance does not establish inbox delivery or completed account recovery.

Earlier standalone design-preview checks covered a 390px phone frame, native fullscreen, entry at ask, close at bid, a shared balance between rooms, and reset. Those older checks used recorded data and browser-local state; they are separate from the current compiled-app review.

## November 24 revision: chart space, study guide, chat, and Stocks

The native chart measures formatted price labels to choose its price gutter. All recovered width goes to Looking Glass; the historical panel and its time mapping stay unchanged. Prices retain their asset-specific precision. Actual native entries use labeled triangles and exits use hollow diamonds. The entry guide selects a current or recorded real entry, shows side, ask, quantity and Eastern Time, and offers **Inspect entry** and **Choose YES/NO**. Inspect recenters the native chart; Choose only selects a calculator side and focuses its budget. It never submits a practice order. Historical entries and current practice quotes are explicitly distinguished.

A 45px chat strip is directly below Nautilus. It shows the latest real messages and moves slowly only when content overflows. Hover, keyboard focus, an open room, and reduced-motion settings pause motion. Clicking opens a larger chat dialog inside the fullscreen root, with Escape, focus trapping and focus restoration. Empty rooms are clearly empty.

A sixth **Stocks** tab uses TradingView's public hosted advanced-chart widget, with explicit public symbol and interval settings. Users can enter a ticker or `EXCHANGE:TICKER`, save up to ten symbols and keep up to 2,000 characters of notes per symbol. Notes and watchlist are scoped to the current user in browser storage; they do not yet synchronize between devices. The widget receives the selected public symbol and chart configuration, never app credentials, member profile data or practice orders. The external widget and market availability may be delayed or unavailable; the page provides attribution, delay guidance and a failure state with a provider link. Earlier standalone-preview browser verification loaded AAPL and NVDA charts and confirmed the provider's own delay label. The current isolated compiled-app review blocked external providers and verified the unavailable state instead; it does not revalidate live chart availability.

The draft app's stock discussion strip opens the existing community Chat tab. The standalone private preview instead has a browser-local per-symbol room. A native stock Nautilus, a stock bot, stock candle ingestion, and equity trade practice in this workspace are **not implemented**. Stocks do not use or spend the five-room binary practice balance. A native stock integration needs timestamped OHLCV bars, exchange sessions and timezone handling, split/dividend treatment, explicit quote delay/freshness, and a stock-specific practice model.

The profile-update request model and follower-state/list contract mismatches found in the old app are corrected in this draft. See `docs/social-training-review.md` for the full feature audit, proposed training progression and remaining launch requirements. No new XP rules, leaderboard, cash payout or direct-message system has been activated.

Additional checks in the earlier standalone preview confirmed entry inspection, side preselection without spending cash, chat inside native fullscreen, Escape returning focus, stock ticker switching, per-symbol note persistence and stock fullscreen. Current compiled-app checks are listed separately above.

## Single-login and alert integration review

The accepted account policy is one active login per member. This draft extends active-session checks to legacy member REST, protects login/logout and socket replacement races, guards delayed browser account responses, and associates push registrations with the current login. Legacy component requests receive the current session headers only for the app's own API origin; delayed responses from replaced sessions cannot overwrite the active account. Deploy the updated frontend and backend together: older clients do not consistently supply the required session headers, and older unbound push registrations must register again. These changes do not activate a new alert destination or send messages. See `docs/session-and-alerts-review.md` for integration findings and remaining provider checks.

Cash rewards are excluded. Earned XP and badges remain, the referral badge no longer advertises a cash award, new cash-award creation is removed, and the historical cash-approval mutation is disabled. Preserved historical bookkeeping is not proof of payment.

## November 25 revision: Stocks-only alerts

The owner confirmed thinkorswim email → Zapier → app, with Zapier → Assistro → WhatsApp continuing during adoption. The draft now includes a saved Stocks feed, exact alert/ticker links through login, explicit mobile-capable opt-in, verified webhook intake with stable email IDs, and a durable dispatcher that checks the current login/device and expires old pushes. Chat, social activity, admin posts and bot-room events do not send device notifications. Firebase outcomes are reported honestly; generic test sends and false-success fallbacks are suppressed.

Deploy the app and the Zapier header/identity mapping together. The private preview shows the feed placement and inactive controls without receiving real alerts. See [stock-alert-rollout.md](stock-alert-rollout.md) for the exact contract and remaining live verification. No WhatsApp action was changed and no real Stocks push was sent.
