# Running the five PAPER bots with CashOutAI

## What runs where

The application displays one shared broadcast from the owner's five PAPER engines. Opening a member's browser does not start another engine, give that member control of the Commander, or place a venue order.

| Location | Responsibility |
| --- | --- |
| Owner's Windows computer | Runs the five independent PAPER engines and one publisher process. The engines produce the Nautilus charts, bot entries, current positions, and bot trade history. |
| Render backend | Accepts authenticated display snapshots, checks member access, serves the rooms and chat, and maintains each member's practice ledger. |
| MongoDB Atlas | Stores member accounts, the latest shared bot snapshots, community records, and member practice state. Upgrading Atlas does not move or start the engines. |
| Phone, computer, or TV | Displays the app. Each participant practices with their own account; the shared bot feed is the training reference. |

The five bot PAPER ledgers remain separate from each other and from member practice. In the inspected engine launcher, each bot defaults to its own $1,000 simulated balance. CashOutAI members instead receive one resettable **$100 virtual practice balance shared across the five rooms**. Neither is a funded venue account.

## Source compatibility updated November 27, 2026

The current source package is the complete private **TACHYOS 0.0.10.20 WINDOWS_FIX1 PAPER** release. It retains separate six-hour and twelve-hour launchers and adds no venue-order transport. Its strategy source and recorded sessions are not copied into this public app repository. The deployed CashOutAI app has passed its public HTTP checks and owner/admin UI review; connecting the owner's Windows feeds remains a separate live gate.

The source confirms:

- `05_START_FIVE_ASSET_PAPER_12H.cmd` starts five separate `START_CONNECTED_PAPER.py` processes for 720 minutes, each with an explicit asset, port, and output folder. `05_START_FIVE_ASSET_PAPER_6H.cmd` remains available for 360-minute sessions.
- The current engine identity is `0.0.10.20_PAPER_ONLY`, and the package revision is `WINDOWS_FIX1`.
- The browser dashboard requires its own current `ui_build=0.0.10.20` when that hint is supplied. Dashboard build identifiers are separate from the read-only API contract.
- The publisher uses plain `GET /api/nautilus`, which the native server explicitly supports for read-only API tools. It binds only to `127.0.0.1` and exposes PAPER telemetry. The old companion's hardcoded `ui_build=0.0.8.4` causes a reload-required response on the new engine and must not be used.
- The adapter supplies `mode: "PAPER_ONLY"`, `readonly: true`, the actual asset symbol, source timestamps, run flags, chart data, positions, and trades expected by the app's display contract.

This is a source compatibility check. It does not establish which folder is currently running on the owner's computer, actual source freshness, the complete latest payload's acceptance by the deployed backend, or prospective bot performance. A current Windows packet and controlled end-to-end check remain necessary before presenting a feed as live.

## Windows connection companion

The release includes two small Windows entry points in `scripts/windows`, with instructions in [README.md](../scripts/windows/README.md). [CashOutAI_Publisher_Windows.zip](../downloads/CashOutAI_Publisher_Windows.zip) preserves that layout and includes the same standard-library publisher. Keep it beside the complete private bot package.

**01_CHECK_LOCAL_FEEDS.cmd** reads the five fixed local endpoints once, requires no key, and contacts no backend or public provider. A pass establishes reachable, matching read-only PAPER identities only; source freshness and backend schema acceptance remain separate checks. Wait for engine startup/prewarm to complete; five opened command windows alone are not a readiness signal.

**02_START_PUBLISHER.cmd** is for the coordinated live connection after the new routes and matching key are configured. It uses the fixed HTTPS backend origin and asks for a hidden publisher key. That explicit prompt overrides an environment key for the current run, leaves the environment unchanged, and never saves or prints the key. It refuses an echoed-input fallback. Both helpers use the existing `py -3` launcher and preserve the exit status for review.

Equivalent explicit modes are `py -3 -X utf8 scripts\publish_nautilus.py --check-local` and `py -3 -X utf8 scripts\publish_nautilus.py --backend https://cashoutai.onrender.com --prompt-key`. Both companion buttons explicitly enable UTF-8. Native Windows double-click execution and deployed publication remain unverified until performed on the operator's machine.

## First live connection

The app release and owner/admin access checks are complete. Before advertising live practice, complete the publisher-key configuration and verify the five actual Windows feeds. Keep the practice event disabled during this preparation.

### 1. Start the complete Windows package

Use the complete, separately extracted `TACHYOS_0120_PAPER` folder from **0.0.10.20 WINDOWS_FIX1** for twelve-hour sessions. Do not copy a new launcher into an older package. Its sequence is:

1. Run `03_VERIFY_PACKAGE.cmd`.
2. If its required dependencies are missing, use `04_INSTALL_PUBLIC_FEEDS.cmd`, then verify again.
3. Run `05_START_FIVE_ASSET_PAPER_12H_MINIMIZED.cmd` after verification passes, or `05_START_FIVE_ASSET_PAPER_12H.cmd` for visible command windows. The retained `05_START_FIVE_ASSET_PAPER_6H.cmd` selects a shorter session.

The five-asset launcher performs its own validation before starting these processes:

| Asset | Native port | Launcher command inside the package |
| --- | ---: | --- |
| BTC | 8787 | `py -3 START_CONNECTED_PAPER.py --asset BTC --minutes 720 --port 8787 --output paper_runs\BTC` |
| ETH | 8788 | `py -3 START_CONNECTED_PAPER.py --asset ETH --minutes 720 --port 8788 --output paper_runs\ETH` |
| SOL | 8789 | `py -3 START_CONNECTED_PAPER.py --asset SOL --minutes 720 --port 8789 --output paper_runs\SOL` |
| XRP | 8790 | `py -3 START_CONNECTED_PAPER.py --asset XRP --minutes 720 --port 8790 --output paper_runs\XRP` |
| DOGE | 8791 | `py -3 START_CONNECTED_PAPER.py --asset DOGE --minutes 720 --port 8791 --output paper_runs\DOGE` |

These commands are recorded to explain the launcher; use the verified launcher so its validation step is retained. The minimized variant also passes `--no-browser`. The similarly named `05_START_PUBLIC_PAPER_6H.cmd` is BTC-only. Use the current package's viewer launcher or the URLs printed by each running engine to open Nautilus later; closing a viewer does not stop its PAPER process.

### 2. Configure one publisher secret

Set the generated `NAUTILUS_PUBLISHER_KEY` in the Render backend's secret configuration. On Windows, supply that same key through the companion's hidden prompt or the publisher process environment. The existing publisher requires 32–512 printable ASCII characters. Store it privately; it belongs only on those two systems, never in React settings, a public repository, a member's browser, or a chat post.

On the Windows publisher machine, set `NAUTILUS_BACKEND_URL` to the deployed backend origin, currently `https://cashoutai.onrender.com`. The publisher accepts HTTPS, refuses redirects, and sends its secret only to that configured backend. It sends no publisher secret to the local bots and contains no venue credentials or trading transport.

### 3. Run the bridge once, then continuously

Use [scripts/publish_nautilus.py](../scripts/publish_nautilus.py) from this app release. It is a standalone standard-library script; it can be kept in a separate app-tools folder beside the intact bot package. In PowerShell, from the app repository folder, with the secret already configured in that process environment:

```powershell
$env:NAUTILUS_BACKEND_URL = 'https://cashoutai.onrender.com'
py -3 -X utf8 .\scripts\publish_nautilus.py --once
```

This makes one bounded attempt per asset. It exits successfully only if the backend explicitly accepts a new snapshot for all five assets. Exit code 1 can also mean that a native timestamp was unchanged; wait for a newer native packet and retry. An unchanged result alone does not establish an authentication or backend failure. After that check succeeds, leave one continuous publisher process running:

```powershell
py -3 -X utf8 .\scripts\publish_nautilus.py
```

The default target is one round per second, with up to five concurrent requests. Each round reads the fixed local ports above and sends the packets to `POST /api/nautilus/ingest/{asset}`. A slow or unavailable source can lengthen a round; the publisher never fabricates data to fill a gap. Do not run multiple copies of the publisher against the same five local sources.

### 4. Verify the member view

Sign in to the deployed app and inspect each asset tab. Verify the expected asset/contract, the feed state, advancing source times, current native quotes, and the correspondence of bot entries and positions with that asset's local Nautilus. Check a phone-sized view and TV fullscreen.

`snapshot accepted` confirms a valid backend acknowledgement for a newly accepted packet. It does **not** prove the native quote is fresh enough for a practice fill. `source unchanged; no new snapshot accepted` means the server retained the prior timestamp, even though the HTTP request completed successfully. Malformed or wrong-asset acknowledgements are failures.

The app separately enforces source and quote freshness before allowing practice orders. A stopped, stale, archived, or unavailable feed cannot fill a new practice order. Keep those labels visible rather than treating the last picture as a live signal.

## Operating the event

Keep the Windows computer powered, connected to the internet, and awake. Keep all five engine processes and the publisher running. A browser window is a viewer and is not required to keep those processes alive. Members can close their own browsers without stopping the bots.

**The updated package supports attended runs of 1–720 minutes.** The twelve-hour launcher selects 720 minutes, while the retained six-hour launcher selects 360. Each engine uses its normal deadline and shutdown path, closes its read-only HTTP listener, and saves the finished session. The publisher does not restart an engine.

Use **about 8 a.m. and 8 p.m. America/New_York** as the operator's review/relaunch windows:

1. Let the five engines finish and confirm their saved receipts. Do not start a second set on the same ports while the prior set is still running.
2. Preserve and inspect the completed runs using `06_COMPARE_FIVE_ASSET_RUNS.cmd` and `08_PACKAGE_FIVE_ASSET_REVIEWS.cmd`. Review missing sources, gaps, positions, outcomes, and discrepancies before proceeding. The review packager now hashes large capture files in chunks, without loading an entire twelve-hour file into memory.
3. Start the next validated twelve-hour session, check the five local feeds, and confirm fresh room states in the app. One continuous publisher can wait through this gap; it never fills missing data with fabricated prices.

The review creates a short gap, so these are approximate operator times, not an automatic 8:00 schedule or a promise of uninterrupted 24/7 operation. A new bot run has its own PAPER ledger; member practice balances and history stay in CashOutAI and are not reset by this handoff. High-frequency display buffers are bounded, but full-session audit/candle history and on-disk captures grow with session length. Check the Windows computer's actual memory, disk use, and source continuity during the first full twelve-hour run.

Continuous unattended operation requires a separate supervised runner with tested restart behavior, source recovery, run-history retention, and graceful shutdown. It has not been installed or implemented by this app release. Do not add an endless restart loop and present that as preserved trading-state continuity. A dedicated always-on host can be considered later; no additional hosting service or charge is introduced here.

If one bot or the publisher stops, the website can remain online for accounts and community use. The corresponding feed becomes delayed/offline and new practice fills pause. Member practice state remains in the backend; official settlement is resolved independently of a bot's new-session chart. Restarting a bot does not reset a member's $100 account.

### In-app notices when a run is observed

After the backend accepts the first fresh, active PAPER snapshot of a new asset/run identity, it saves one shared room announcement. It then sends a `bot_session_started` event through the existing authenticated WebSocket connections. The app groups recently received rooms into one dismissible banner with direct room buttons. **Notifications → Bot session history** keeps dated shared notices, and the room chat retains the announcement. A past notice does not claim the feed is still live; the room's current source status remains authoritative.

The notice is keyed by the exact asset and canonical run ID. MongoDB's unique document ID deduplicates restarts and concurrent submissions; a bounded cache avoids an extra notice lookup on every heartbeat. Exact retries can repair a failed insert using the already-accepted snapshot identity. A repeated heartbeat, a stale/review/replay packet, or the clock reaching eight does not announce a run. The first fresh run observed after this feature is enabled can produce a notice even if that engine started earlier.

These are in-app notices only. No email, WhatsApp message, or device push is sent for a bot run; **device push remains Stocks-only**. The shared history is one record per asset/run, with no per-member fanout. It is authenticated and bounded to 1–50 notices per request. The frontend refreshes it on entry/visibility and once per visible minute as a connection fallback, grouping only recent notices and keeping older history dated. A grouped banner does not replace a live feed health check.

## Load and cost boundaries

One shared publication path avoids starting a bot or opening a provider stream for every viewer. The current bridge still sends full snapshots, and each accepted packet replaces that asset's latest snapshot in MongoDB. More viewers add backend reads and network transfer even though they share the same bot source.

The app currently polls the visible asset and assets with open member practice positions approximately every three seconds after each response. Hidden pages stop polling. Chat has its own five-second visible-page interval; practice positions refresh every fifteen seconds. These controls reduce unnecessary work, but no measured public-event capacity or global provider spending cap is claimed.

Before increasing audience size, observe actual packet size, backend response time, database operations, and transfer use. A future shared in-process cache or changed-snapshot/delta transport can reduce repeat work while preserving the source timestamps. Keep provider licensing and quote limits under the separate [quote and launch plan](realtime-quotes-and-launch.md).

The twelve-hour compatibility fixture used the actual native converter with 720 displayed candles, 720 EMA points, 4,500 quote samples, 48 targets, and 40 commands for each asset. All five packets passed the current app sanitizer; sizes were 738,066–742,621 bytes before compression. This non-economic fixture contained no positions or trades, so it does not prove a production session can never reach the 4 MiB packet limit. At the default one-round-per-second bridge cadence, five packets of this size would represent about 3.7 MB/s of input before compression. Use the first controlled Windows session to measure actual payloads and transfer; twelve-hour compatibility is not a public-audience load test or a spending guarantee.

### Initial event measurements

For a visible bot workspace, the source-defined cadence is approximately `20A + 12 + 4P` HTTP requests per minute, where `A` is the number of unique polled assets (one to five), and `P` is one while practice positions are open. That is about 32 requests/minute for one room without positions, 36 with positions only in that asset, or 116 with all five assets needed. Response duration reduces the polling rate; initial loads, actions, reconnections, and the broader app's community/session requests add separate traffic. These calculations are not a load test or a verified audience limit.

Measure actual compressed snapshot response bytes, `C`, during the first controlled session. Snapshot transfer alone is approximately `20 × A × C` bytes per visible viewer per minute. The four-megabyte rejection limit is not a typical packet size. Five continuously changing publishers can produce approximately 300 ingest requests and up to 300 latest-snapshot writes per minute before request duration is accounted for.

Use the following as proposed review thresholds for the first event, not configured alerts or guaranteed capacity:

| Signal | Starting review threshold | Next check |
| --- | --- | --- |
| Bot/chat response latency | p95 above 750 ms for five minutes | Query plans, response size, backend saturation. |
| Backend errors | More than 1% 5xx over five minutes with at least 100 requests | Investigate before further audience expansion; count expected stale-quote 409 responses separately. |
| Backend resources | CPU above 70% or memory above 75% for ten minutes | Inspect sustained work before choosing more capacity. |
| Bot display status | Stale/offline for 30 seconds during an advertised session | Inspect the corresponding Windows engine and publisher. Existing practice freshness checks remain immediate. |
| Quote provider | Any 429 response | Confirm the account allowance and request pattern. |

The FMP adapter already shares concurrent same-symbol requests inside one process and caches successful quotes for five seconds, with a two-second failure cache. Those controls are not a global daily budget. The new Stocks workspace's ten-symbol watchlist does not create ten FMP streams; legacy Favorites has no equivalent ten-symbol limit. Room polling pauses when hidden, but separate community/session fallback requests still exist. Monitor actual totals before describing an event size as supported.

The release adds non-unique `nautilus_chat_asset_created_at` and `nautilus_chat_kind_created_at` indexes for the room filter/newest-message sort and shared announcement history. The disposable real MongoDB CI rehearsal checks the query plans, repeated startup, and actual concurrent/durable notice deduplication using synthetic records. No production chat index or member record is changed while the release remains a draft.

## Troubleshooting

| Observation | Check |
| --- | --- |
| One asset is unavailable | Its engine window, native port, asset identity, and source health. Other engine windows are independent. |
| All five stop together | Computer sleep/network, publisher process, backend health, or a common provider interruption. |
| HTTP 401 | The configured backend and publisher keys must match. Do not print the key while checking. |
| HTTP 503 | Backend availability and whether the publisher secret is configured. |
| HTTP 404 | Correct backend origin and whether the Nautilus release routes are actually deployed. |
| HTTP 409 | An older/concurrent source packet was rejected; let the next normal round supply a newer native packet. |
| HTTP 422 | Actual native packet identity/schema/timestamps must be checked against the deployed allowlist. Do not remove validation to make the error disappear. |
| Accepted packet, practice still unavailable | Check native source/quote freshness, open contract, and the selected member's active access. HTTP acknowledgement alone is insufficient. |

## Verification boundary

### November 27 publisher compatibility correction

The earlier companion's browser-specific build query was incompatible with the current private package. The corrected publisher uses the native server's supported plain API path while retaining fixed loopback sources, PAPER identity, size bounds, redirect rejection, and private-key handling. All 24 focused Nautilus API/publisher regressions pass, including a newer-dashboard fixture that fails with the old query and succeeds for all five assets after the fix.

A separate offline integration used the uploaded package's actual HTTP handler and converter with synthetic observations for all five assets, followed by the app's actual router with an in-memory database. It reproduced the old reload-required response, then passed native packet read, ingestion, authenticated member retrieval, native price/candle preservation, both YES/NO quote actions, live/stale/offline transitions, unchanged-timestamp handling, and deduplicated session notices. It made no external connections or production writes and used no real credentials. This establishes the existing app contract, not a live Windows/network connection.

The current package's unmodified validator passed 913 tests with no failures, errors, or skips in Linux with Python 3.12 and Node available. Its four diagnostic-runner tests and JavaScript gates passed. All 1,199 sealed manifest entries and all 49 runtime hashes matched before and after validation. Native Windows execution and a fresh twelve-hour session remain separate checks.

CashOutAI's existing allowlist does not expose the new local Long View/macro context and private analytics fields. Those remain available in the Windows viewer; this bridge correction does not add those interfaces to the website. Preserve the native three-second quote expiry, and verify actual internet latency before opening practice. At ordinary engine shutdown the listener closes; the last app snapshot ages to stale and later offline instead of being presented as an indefinitely live feed.

The companion ZIP can be rebuilt with `python scripts/build_windows_publisher.py` and checked without changes using `python scripts/build_windows_publisher.py --check`. Its explicit four-file allowlist includes only the publisher, two Windows commands, and their README, plus a checksum manifest.

### Historical twelve-hour preparation

The private engine source supplied the exact Windows launchers, twelve-hour duration path, ports, protocol, and endpoint behavior above. The updated duration, shutdown, retention, and twelve-hour timestamp-range export received offline checks. Neither an actual twelve-hour endurance run nor Windows double-click execution is established by those checks. No public feed or real venue trade was run for this preparation.

The publisher correction was verified with isolated responses for explicit acceptance, unchanged packets, malformed/mismatched acknowledgements, and unsuccessful HTTP statuses. The Windows companion adds eight checks for local-only behavior, bounded identity reads, hidden-key handling, cancellation, and prevention of echoed fallback. The 23 existing Nautilus API/publisher tests and 15 new session-notice tests pass. The combined app suite passed 249 backend tests, 74 JavaScript model tests, and a CI production build. The private twelve-hour package separately passed 685 Python tests and its JavaScript gates from a clean ZIP extraction. Existing HTTPS/redirect and router checks remain in [test_nautilus_api.py](../backend/tests/test_nautilus_api.py). Actual Windows double-click execution, Windows-to-Render publication, current five-bot payload acceptance, and mobile/TV viewing of live data still require the controlled deployed check.
