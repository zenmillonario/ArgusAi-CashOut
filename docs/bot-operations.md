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

## Source verified November 25, 2026

The latest five-asset package located for this review was `TACHYOS_CLEAN_ROOM_0.0.10.10_BOUNDED_DEPTH_FIVE_ASSET_PAPER.zip`. Its launchers and read-only API source were inspected privately; its engine strategy source was not copied into this app repository.

The source confirms:

- `05_START_FIVE_ASSET_PAPER_6H.cmd` starts five separate `START_CONNECTED_PAPER.py` processes, each with an explicit asset, port, and output folder.
- The current engine identity is `0.0.10.10_PAPER_ONLY`.
- The dashboard protocol remains `ui_build=0.0.8.4`, with `ui_protocol: 1`. The dashboard build and engine version are separate identifiers.
- The native endpoint is `GET /api/nautilus?ui_build=0.0.8.4`. It binds only to `127.0.0.1` and exposes read-only PAPER telemetry.
- The adapter supplies `mode: "PAPER_ONLY"`, `readonly: true`, the actual asset symbol, source timestamps, run flags, chart data, positions, and trades expected by the app's display contract.

This is a source compatibility check. It does not establish which folder is currently running on the owner's computer, actual source freshness, the complete latest payload's acceptance by the deployed backend, or prospective bot performance. A current Windows packet and controlled end-to-end check remain necessary before presenting a feed as live.

## Windows connection companion

The release includes two small Windows entry points in `scripts/windows`, with instructions in [README.md](../scripts/windows/README.md). [CashOutAI_Publisher_Windows.zip](../downloads/CashOutAI_Publisher_Windows.zip) preserves that layout and includes the same standard-library publisher. Keep it beside the complete private bot package.

**01_CHECK_LOCAL_FEEDS.cmd** can be used while waiting for the app release. It reads the five fixed local endpoints once, requires no key, and contacts no backend or public provider. A pass establishes reachable, matching read-only PAPER identities only; source freshness and backend schema acceptance remain separate checks.

**02_START_PUBLISHER.cmd** is for the coordinated live connection after the new routes and matching key are configured. It uses the fixed HTTPS backend origin and asks for a hidden publisher key. That explicit prompt overrides an environment key for the current run, leaves the environment unchanged, and never saves or prints the key. It refuses an echoed-input fallback. Both helpers use the existing `py -3` launcher and preserve the exit status for review.

Equivalent explicit modes are `py -3 scripts\publish_nautilus.py --check-local` and `py -3 scripts\publish_nautilus.py --backend https://cashoutai.onrender.com --prompt-key`. Native Windows double-click execution and deployed publication remain unverified until performed on the operator's machine.

## First live connection

Complete the coordinated app release and access checks first. The prior live application does not become a five-bot app merely because its database tier changed.

### 1. Start the existing Windows package

Use a complete, separately extracted package folder. The inspected package's sequence is:

1. Run `03_VERIFY_PACKAGE.cmd`.
2. If its required dependencies are missing, use `04_INSTALL_PUBLIC_FEEDS.cmd`, then verify again.
3. Run `05_START_FIVE_ASSET_PAPER_6H.cmd` after verification passes.

The five-asset launcher performs its own validation before starting these processes:

| Asset | Native port | Launcher command inside the package |
| --- | ---: | --- |
| BTC | 8787 | `py -3 START_CONNECTED_PAPER.py --asset BTC --minutes 360 --port 8787 --output paper_runs\BTC` |
| ETH | 8788 | `py -3 START_CONNECTED_PAPER.py --asset ETH --minutes 360 --port 8788 --output paper_runs\ETH` |
| SOL | 8789 | `py -3 START_CONNECTED_PAPER.py --asset SOL --minutes 360 --port 8789 --output paper_runs\SOL` |
| XRP | 8790 | `py -3 START_CONNECTED_PAPER.py --asset XRP --minutes 360 --port 8790 --output paper_runs\XRP` |
| DOGE | 8791 | `py -3 START_CONNECTED_PAPER.py --asset DOGE --minutes 360 --port 8791 --output paper_runs\DOGE` |

These commands are recorded to explain the launcher; use the verified launcher so its validation step is retained. The similarly named `05_START_PUBLIC_PAPER_6H.cmd` is BTC-only. The older `07_OPEN_NAUTILUS.cmd` also opens only BTC and carries an older UI identifier; use the URLs printed by the running five-asset engines for their local cockpits.

### 2. Configure one publisher secret

Set the generated `NAUTILUS_PUBLISHER_KEY` in the Render backend's secret configuration. On Windows, supply that same key through the companion's hidden prompt or the publisher process environment. The existing publisher requires 32–512 printable ASCII characters. Store it privately; it belongs only on those two systems, never in React settings, a public repository, a member's browser, or a chat post.

On the Windows publisher machine, set `NAUTILUS_BACKEND_URL` to the deployed backend origin, currently `https://cashoutai.onrender.com`. The publisher accepts HTTPS, refuses redirects, and sends its secret only to that configured backend. It sends no publisher secret to the local bots and contains no venue credentials or trading transport.

### 3. Run the bridge once, then continuously

Use [scripts/publish_nautilus.py](../scripts/publish_nautilus.py) from this app release. It is a standalone standard-library script; it can be kept in a separate app-tools folder beside the intact bot package. In PowerShell, from the app repository folder, with the secret already configured in that process environment:

```powershell
$env:NAUTILUS_BACKEND_URL = 'https://cashoutai.onrender.com'
py -3 .\scripts\publish_nautilus.py --once
```

This makes one bounded attempt per asset. It exits successfully only if the backend explicitly accepts a new snapshot for all five assets. Exit code 1 can also mean that a native timestamp was unchanged; wait for a newer native packet and retry. An unchanged result alone does not establish an authentication or backend failure. After that check succeeds, leave one continuous publisher process running:

```powershell
py -3 .\scripts\publish_nautilus.py
```

The default target is one round per second, with up to five concurrent requests. Each round reads the fixed local ports above and sends the packets to `POST /api/nautilus/ingest/{asset}`. A slow or unavailable source can lengthen a round; the publisher never fabricates data to fill a gap. Do not run multiple copies of the publisher against the same five local sources.

### 4. Verify the member view

Sign in to the deployed app and inspect each asset tab. Verify the expected asset/contract, the feed state, advancing source times, current native quotes, and the correspondence of bot entries and positions with that asset's local Nautilus. Check a phone-sized view and TV fullscreen.

`snapshot accepted` confirms a valid backend acknowledgement for a newly accepted packet. It does **not** prove the native quote is fresh enough for a practice fill. `source unchanged; no new snapshot accepted` means the server retained the prior timestamp, even though the HTTP request completed successfully. Malformed or wrong-asset acknowledgements are failures.

The app separately enforces source and quote freshness before allowing practice orders. A stopped, stale, archived, or unavailable feed cannot fill a new practice order. Keep those labels visible rather than treating the last picture as a live signal.

## Operating the event

Keep the Windows computer powered, connected to the internet, and awake. Keep all five engine processes and the publisher running. A browser window is a viewer and is not required to keep those processes alive. Members can close their own browsers without stopping the bots.

**The inspected package is a six-hour runner, not a 24/7 service.** `START_CONNECTED_PAPER.py` enforces a 1–360 minute duration and shuts down its read-only HTTP listener when the session finishes. The publisher does not restart an engine. For an event using this package, plan attended six-hour runs and a new validated launch after normal completion. Preserve finished runs using `06_COMPARE_FIVE_ASSET_RUNS.cmd` and `08_PACKAGE_FIVE_ASSET_REVIEWS.cmd`.

Continuous unattended operation requires a separate supervised runner with tested restart behavior, source recovery, run-history retention, and graceful shutdown. It has not been installed or implemented by this app release. Do not add an endless restart loop and present that as preserved trading-state continuity. A dedicated always-on host can be considered later; no additional hosting service or charge is introduced here.

If one bot or the publisher stops, the website can remain online for accounts and community use. The corresponding feed becomes delayed/offline and new practice fills pause. Member practice state remains in the backend; official settlement is resolved independently of a bot's new-session chart. Restarting a bot does not reset a member's $100 account.

## Load and cost boundaries

One shared publication path avoids starting a bot or opening a provider stream for every viewer. The current bridge still sends full snapshots, and each accepted packet replaces that asset's latest snapshot in MongoDB. More viewers add backend reads and network transfer even though they share the same bot source.

The app currently polls the visible asset and assets with open member practice positions approximately every three seconds after each response. Hidden pages stop polling. Chat has its own five-second visible-page interval; practice positions refresh every fifteen seconds. These controls reduce unnecessary work, but no measured public-event capacity or global provider spending cap is claimed.

Before increasing audience size, observe actual packet size, backend response time, database operations, and transfer use. A future shared in-process cache or changed-snapshot/delta transport can reduce repeat work while preserving the source timestamps. Keep provider licensing and quote limits under the separate [quote and launch plan](realtime-quotes-and-launch.md).

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

The release adds a non-unique `nautilus_chat_asset_created_at` index for the existing room filter and newest-message sort. Its query-plan verification uses synthetic room messages on the disposable real MongoDB CI instance. No production chat index or member record is changed while the release remains a draft.

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

The inspected private engine source supplied the exact Windows launcher, six-hour limit, ports, protocol, and endpoint behavior above. No engine, strategy replay, public feed, real trade, or live venue request was run for this review.

The publisher correction was verified with isolated responses for explicit acceptance, unchanged packets, malformed/mismatched acknowledgements, and unsuccessful HTTP statuses. The Windows companion adds eight checks for local-only behavior, bounded identity reads, hidden-key handling, cancellation, and prevention of echoed fallback. All 23 Nautilus API/publisher tests pass. Existing HTTPS/redirect and router checks remain in [test_nautilus_api.py](../backend/tests/test_nautilus_api.py). Actual Windows double-click execution, Windows-to-Render publication, current five-bot payload acceptance, and mobile/TV viewing of live data still require the controlled deployed check.
