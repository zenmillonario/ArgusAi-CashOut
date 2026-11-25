# Nautilus bot rooms

This draft integration adds BTC, ETH, SOL, XRP, and DOGE rooms with the native Nautilus chart, an asset-specific community chat, bot positions and trades, and a member practice account. It has not been deployed. The existing app's broader authentication and authorization audit remains separate; these isolated checks are not a production security certification.

## Backend and publisher setup

The app mounts `create_nautilus_router(db)` from `backend/nautilus_api.py` under `/api/nautilus`. It uses the existing Mongo connection and three collections: `nautilus_snapshots`, `nautilus_chat`, and `nautilus_practice`.

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

Only matching asset packets with `mode: "PAPER_ONLY"`, `readonly: true`, and a PAPER engine version are accepted. The API stores an explicit recursive allowlist of public display fields and rejects oversized, malformed, or out-of-order packets. Native strategy normalization has already been reversed by the native adapter: the legacy `market.btc` field contains the selected asset's actual USD price.

## Member API

Every member route requires `X-User-ID` and `X-Session-ID`. The latter must match the user's stored active session. Access requires an approved membership or an unexpired trial. Author names, account ownership, balances, and execution prices are supplied by the server.

| Method and route | Request / result |
|---|---|
| `GET /bots/{asset}` | `{snapshot, state, receivedAt}`; state is `live`, `stale`, or `offline` |
| `GET /chat/{asset}` | `{messages: [{id, author, content, createdAt, isAdmin}]}` |
| `POST /chat/{asset}` | `{text}` → `{message}`; plaintext, maximum 1,000 characters |
| `GET /practice` | `{account, revision, feePolicy: "fees-excluded"}` |
| `POST /practice/buy` | `{attemptId, revision, transactionId, asset, contractId, side, budget}` |
| `POST /practice/close` | `{attemptId, revision, transactionId, positionId}` |
| `POST /practice/reset` | `{attemptId, revision, transactionId}` |

All routes above are relative to `/api/nautilus`. Practice mutations return the same account/revision shape as GET. Errors contain a human-readable `detail` string. Refresh the account on a 409 conflict; do not silently resubmit a different action using an old revision or transaction ID.

## Practice behavior

Each member has **one $100 USD practice balance shared across all five asset rooms**. Bot performance and the member's practice account are separate ledgers. Money is stored as integer microdollars. An order buys the whole number of contracts that fits the selected budget and available cash; closing uses the matching contract's native bid.

The server selects the ask or bid from its authenticated native snapshot. Browser-supplied balances, quotes, marks, and fees are rejected. These are top-of-book practice fills with **fees excluded**: the explicit practice fee is zero until applicable venue fee metadata is supplied. Do not present practice results as net-of-fee venue performance.

Before a fill, the backend requires a received snapshot no older than 15 seconds, source/run/underlying-price timestamps no older than five seconds, and a verified native quote no older than three seconds whose `valid_until` has not elapsed. Asset, side, quote ticker, and current market ticker must match; the contract must remain open. Stopped, archived/review, stale, missing-price, and expired sources cannot fill practice orders.

Each mutation includes the current attempt ID, revision, and a unique transaction ID. Mongo compare-and-swap persistence prevents concurrent requests from spending the same balance twice. A repeat of the same recorded request returns the account without another fill. Reset restores $100, clears the active attempt, advances the revision, and generates a new attempt ID, so delayed actions from an old tab cannot cross the reset.

**Expiration limitation:** this first bridge does not yet ingest a general official settlement feed for every member-held contract. An expired practice position cannot be sold using a newer contract's quote, and its outcome is never inferred from the displayed underlying price. Official settlement needs a verified outcome integration; a member can reset to start a new attempt in the meantime.

## Verification

Run from the repository root after installing the backend dependencies:

```bash
python -B -m unittest discover -s backend/tests -p 'test_*.py'
node --test frontend/src/nautilus/practiceEngine.test.mjs frontend/src/sessionAuth.test.mjs frontend/src/stockNotifications.test.mjs
```

API tests use an in-memory fake database and an ASGI transport; they do not contact Mongo, local engines, a venue, or a production account. They cover session/trial access, publisher credentials and projection, quote freshness and matching, chat ownership, native-price accounting, duplicate requests, concurrent writes, reset isolation, input limits, and publisher URL/redirect restrictions. Real deployment still needs the configured engine host, HTTPS backend, publisher secret, and a controlled integration run.

## Account maintenance included in this draft

The legacy account flow now requires an expiring email verification token for password recovery, keeps session credentials out of public user records, persists registration password hashes, fails closed for accounts without a hash, and requires an existing session to change the recovery email. Predictable default-admin creation and automatic promotion have been removed. Existing accounts created with missing hashes must use verified email recovery; the email provider must be configured before rollout. Existing production credentials are not changed by this source patch.

Other legacy REST actions still trust caller-supplied user/admin IDs. Complete a role and ownership authorization pass and review existing bootstrap accounts before merging for public production. The new isolated API and account tests do not replace that review.

The standalone private design preview uses real recorded PAPER packets and local browser-only practice/chat. It is separate from the current production app and does not exercise the production Mongo/email services.

Verification performed for this draft: 67 isolated Python tests and 28 JavaScript ledger/session/stock-notification tests passed; App.js and its local modules bundled successfully with third-party packages externalized. The private preview built and was checked in a browser at desktop and a 390px-wide phone frame, including full screen, TV text, entry at ask, close at bid, a shared balance between rooms, and reset to $100. A full legacy CRA/backend deployment smoke test remains a rollout requirement.

## November 24 revision: chart space, study guide, chat, and Stocks

The native chart measures formatted price labels to choose its price gutter. All recovered width goes to Looking Glass; the historical panel and its time mapping stay unchanged. Prices retain their asset-specific precision. Actual native entries use labeled triangles and exits use hollow diamonds. The entry guide selects a current or recorded real entry, shows side, ask, quantity and Eastern Time, and offers **Inspect entry** and **Choose YES/NO**. Inspect recenters the native chart; Choose only selects a calculator side and focuses its budget. It never submits a practice order. Historical entries and current practice quotes are explicitly distinguished.

A 45px chat strip is directly below Nautilus. It shows the latest real messages and moves slowly only when content overflows. Hover, keyboard focus, an open room, and reduced-motion settings pause motion. Clicking opens a larger chat dialog inside the fullscreen root, with Escape, focus trapping and focus restoration. Empty rooms are clearly empty.

A sixth **Stocks** tab uses TradingView's public hosted advanced-chart widget, with explicit public symbol and interval settings. Users can enter a ticker or `EXCHANGE:TICKER`, save up to ten symbols and keep up to 2,000 characters of notes per symbol. Notes and watchlist are scoped to the current user in browser storage; they do not yet synchronize between devices. The widget receives the selected public symbol and chart configuration, never app credentials, member profile data or practice orders. The external widget and market availability may be delayed or unavailable; the page provides attribution, delay guidance and a failure state with a provider link. Browser verification loaded both AAPL and NVDA charts and confirmed the provider's own delay label.

The draft app's stock discussion strip opens the existing community Chat tab. The standalone private preview instead has a browser-local per-symbol room. A native stock Nautilus, a stock bot, stock candle ingestion, and equity trade practice in this workspace are **not implemented**. Stocks do not use or spend the five-room binary practice balance. A native stock integration needs timestamped OHLCV bars, exchange sessions and timezone handling, split/dividend treatment, explicit quote delay/freshness, and a stock-specific practice model.

The profile-update request model and follower-state/list contract mismatches found in the old app are corrected in this draft. See `docs/social-training-review.md` for the full feature audit, proposed training progression and remaining launch requirements. No new XP rules, leaderboard, cash payout or direct-message system has been activated.

Additional browser checks confirmed entry inspection, side preselection without spending cash, chat inside native fullscreen, Escape returning focus, stock ticker switching, per-symbol note persistence and stock fullscreen.

## Single-login and alert integration review

The accepted account policy is one active login per member. This draft extends active-session checks to legacy member REST, protects login/logout and socket replacement races, guards delayed browser account responses, and associates push registrations with the current login. Deploy the updated frontend and backend together: older clients do not consistently supply the required session headers, and older unbound push registrations must register again. These changes do not activate a new alert destination or send messages. See `docs/session-and-alerts-review.md` for the exact integration findings, provider checks, accepted scope and remaining rollout work. Cash rewards are outside the current scope.

## November 25 revision: Stocks-only alerts

The owner confirmed thinkorswim email → Zapier → app, with Zapier → Assistro → WhatsApp continuing during adoption. The draft now includes a saved Stocks feed, exact alert/ticker links through login, explicit mobile-capable opt-in, verified webhook intake with stable email IDs, and a durable dispatcher that checks the current login/device and expires old pushes. Chat, social activity, admin posts and bot-room events do not send device notifications. Firebase outcomes are reported honestly; generic test sends and false-success fallbacks are suppressed.

Deploy the app and the Zapier header/identity mapping together. The private preview shows the feed placement and inactive controls without receiving real alerts. See [stock-alert-rollout.md](stock-alert-rollout.md) for the exact contract and remaining live verification. No WhatsApp action or real notification has been changed/sent.
