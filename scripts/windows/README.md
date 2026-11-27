# CashOutAI Windows publisher companion

Prepared for the November 25, 2026 release draft. The Python checks pass; native Windows double-click execution and publication to the updated app are still pending.

This companion connects the display data from your five existing PAPER engines to CashOutAI. Keep it in its own folder beside the complete bot package. It requires the same `py -3` Python launcher your bots already use.

## What you can check now

1. Extract the complete companion ZIP into its own folder.
2. Start a validated five-asset run from the complete private bot package. The updated 0.0.10.11 package adds `05_START_FIVE_ASSET_PAPER_12H.cmd`; the existing `05_START_FIVE_ASSET_PAPER_6H.cmd` remains available. Do not mix launcher files between package versions.
3. Open the companion's `scripts\windows` folder.
4. Double-click **01_CHECK_LOCAL_FEEDS.cmd**.

The check reads each of the five fixed local endpoints once: BTC 8787, ETH 8788, SOL 8789, XRP 8790, and DOGE 8791. It requires no publisher key and sends no data to the app or a public market provider.

For each asset, **reachable; matching read-only PAPER identity** means the expected local bot endpoint answered. The check does not establish backend acceptance or source/quote freshness. Exit code 0 means all five identity checks passed; exit code 1 means at least one did not. The window stays open so you can read the result.

If a source is unavailable, check that asset's engine window and whether its selected six- or twelve-hour session has finished. The companion does not start or restart the engines.

## Connect after the updated app is deployed

The live app must have the new Nautilus routes and the matching publisher key configured first. **Keep this step for the coordinated live-connection check.**

1. Keep the five PAPER engines running.
2. Double-click **02_START_PUBLISHER.cmd**.
3. Enter the matching publisher key at the hidden prompt. This is a connection key, separate from your CashOutAI account password.
4. Check that all five assets report **snapshot accepted**, then leave this one publisher window open.

The button sends snapshots to **https://cashoutai.onrender.com**. The key is used for that run, is not printed or saved, and overrides an existing environment key only for the current publisher process. If hidden input is unavailable, the program stops before accepting an echoed key. Closing the program means you will enter the key again next time.

**snapshot accepted** confirms that the backend accepted a new packet. **source unchanged; no new snapshot accepted** means the source timestamp has not advanced; it is not by itself an authentication failure. The app separately checks native quote freshness before allowing practice entries.

Press **Ctrl+C** to stop the publisher. The bots continue under their own launchers and selected duration. Keep the computer awake and online for the advertised running session. Around the intended 8 a.m./8 p.m. Eastern review windows, finish and preserve the prior run before launching the next one. Expect a short review gap; the publisher can keep waiting for fresh local feeds.

After the app update is deployed, a newly accepted fresh PAPER run creates an in-app room notice and a dated entry in Notifications. Five near-simultaneous starts share one compact banner. Repeated heartbeats do not repeat the notice, and an eight-o'clock timer does not announce an unavailable feed. Device push remains Stocks-only.

## Common results

| Result | What to check |
| --- | --- |
| Python launcher not found | Use the Python installation already required by your bot package. These helpers install nothing. |
| Cannot find bundled publisher | Extract the full ZIP and preserve its folder layout. |
| Local source unavailable | Check the corresponding engine and its local port. |
| HTTP 404 | Confirm that the updated app's Nautilus routes are deployed. |
| HTTP 401 | Confirm that the entered publisher key matches the backend's key. |
| HTTP 503 | Check backend availability and publisher-key configuration. |
| HTTP 422 | Review the actual packet against the deployed schema; a local identity pass is not full backend validation. |

This companion has no trading controls or venue credentials. Each member's virtual $100 practice account is handled by the app. Preserve completed engine runs using the original bot package's review tools.

## Included files

- `scripts/publish_nautilus.py`
- `scripts/windows/01_CHECK_LOCAL_FEEDS.cmd`
- `scripts/windows/02_START_PUBLISHER.cmd`
- This README and a SHA-256 file manifest

The companion contains no publisher key, member records, or private strategy source.
