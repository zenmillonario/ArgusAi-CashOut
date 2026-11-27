# CashOutAI Windows publisher companion

Updated November 27, 2026 for the deployed CashOutAI app and the complete **TACHYOS 0.0.10.20 WINDOWS_FIX1 PAPER** package. Native Windows execution and Windows-to-Render publication still require the operator's first connection check.

This companion connects the display data from your five existing PAPER engines to CashOutAI. Keep it in its own folder beside the complete bot package. It requires the same `py -3` Python launcher your bots already use.

## What you can check now

1. Extract the complete companion ZIP into its own folder.
2. In the separately extracted `TACHYOS_0120_PAPER` folder, run **03_VERIFY_PACKAGE.cmd** and wait for success. Then run **05_START_FIVE_ASSET_PAPER_12H_MINIMIZED.cmd**, or the visible **05_START_FIVE_ASSET_PAPER_12H.cmd**. Both start twelve-hour PAPER sessions. Keep each complete package together; do not copy these files into the bot package or mix its launcher versions.
3. Open the companion's `scripts\windows` folder.
4. Double-click **01_CHECK_LOCAL_FEEDS.cmd**.

The check reads each of the five fixed local endpoints once: BTC 8787, ETH 8788, SOL 8789, XRP 8790, and DOGE 8791. It uses plain **GET /api/nautilus**, the native endpoint supported for read-only API tools. It requires no publisher key and sends no data to the app or a public market provider.

The older companion requested a particular dashboard build (`ui_build=0.0.8.4`). The current engine correctly rejects that older viewer version. This companion omits the dashboard-only hint and still requires the expected asset, `PAPER_ONLY`, and `readonly: true`. The private trading engine and its package hashes are unchanged. Both Windows buttons explicitly enable Python UTF-8 mode.

For each asset, **reachable; matching read-only PAPER identity** means the expected local bot endpoint answered. The check does not establish backend acceptance or source/quote freshness. Exit code 0 means all five identity checks passed; exit code 1 means at least one did not. The window stays open so you can read the result.

Wait until the engines finish their startup/prewarm before checking. The launcher saying it opened five windows does not prove that all five feeds started successfully. If a source is unavailable, restore that asset's engine window and check its startup result, port, and whether its selected session has finished. The companion does not start or restart the engines.

## Connect the publisher

The Nautilus routes are deployed at the backend below. The same private **NAUTILUS_PUBLISHER_KEY** must be configured on the Render **CashoutAi** web service and supplied to this publisher. A configured key is active only after the backend deploy completes. Use the connection key from the owner-controlled setup; do not put it in this ZIP, the strategy package, or a chat message.

1. Keep the five PAPER engines running.
2. Double-click **02_START_PUBLISHER.cmd**.
3. Paste the matching publisher key at the hidden prompt and press Enter. No characters appear while entering it. This is a connection key, separate from your CashOutAI account password.
4. Check that all five assets report **snapshot accepted**, then leave this one publisher window open.

The button sends snapshots to **https://cashoutai.onrender.com**. The key is used for that run, is not printed or saved, and overrides an existing environment key only for the current publisher process. If hidden input is unavailable, the program stops before accepting an echoed key. Closing the program means you will enter the key again next time.

**snapshot accepted** confirms that the backend accepted a new packet. **source unchanged; no new snapshot accepted** means the source timestamp has not advanced; it is not by itself an authentication failure. The app separately checks native quote freshness before allowing practice entries.

Press **Ctrl+C** to stop the publisher. The bots continue under their own launchers and selected duration. Keep the computer awake and online for the advertised running session. Around the intended 8 a.m./8 p.m. Eastern review windows, finish and preserve the prior run before launching the next one. Expect a short review gap; the publisher can keep waiting for fresh local feeds.

A newly accepted fresh PAPER run creates an in-app room notice and a dated entry in Notifications. Five near-simultaneous starts share one compact banner. Repeated heartbeats do not repeat the notice, and an eight-o'clock timer does not announce an unavailable feed. Device push remains Stocks-only. The free practice event stays disabled until the live checks are completed.

## Common results

| Result | What to check |
| --- | --- |
| Python launcher not found | Use the Python installation already required by your bot package. These helpers install nothing. |
| Cannot find bundled publisher | Extract the full ZIP and preserve its folder layout. |
| Local source unavailable | Check the corresponding engine and its local port. |
| HTTP 404 | Confirm that the updated app's Nautilus routes are deployed. |
| HTTP 401 | Confirm that the entered publisher key matches the backend's key. |
| HTTP 503 | Run the local check first: the native snapshot may be temporarily unavailable. If local reads pass, check backend availability and publisher-key configuration. |
| HTTP 422 | Review the actual packet against the deployed schema; a local identity pass is not full backend validation. |

This companion has no trading controls or venue credentials. Each member's virtual $100 practice account is handled by the app. Preserve completed engine runs using the original bot package's review tools.

The app displays its existing Nautilus chart, quotes, positions, and trades. The package's separate Long View and newer local analytics remain in the Windows viewer; this connection update does not add them to the website.

## Included files

- `scripts/publish_nautilus.py`
- `scripts/windows/01_CHECK_LOCAL_FEEDS.cmd`
- `scripts/windows/02_START_PUBLISHER.cmd`
- This README and a SHA-256 file manifest

The companion contains no publisher key, member records, or private strategy source.
