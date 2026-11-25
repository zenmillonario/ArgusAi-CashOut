# Stocks alert rollout: thinkorswim → Zapier → CashOutAI

Updated November 25, 2026. This is the setup plan for the prepared source patch. No live Zapier setting, Assistro action, provider credential, or notification destination was changed.

## Member experience

The Stocks tab contains a ticker-driven chart and a saved alert feed. Incoming thinkorswim alerts arrive through the existing email/Zapier flow. Members read the feed with push off, or tap **Enable stock alerts** on their active device. A notification opens Stocks, selects the saved alert, and loads its symbol. Community notices stay inside the app; the five PAPER bot rooms do not send device pushes.

WhatsApp continues through the current Assistro action while members adopt the app. No replacement WhatsApp service, group migration, or additional channel is required for this phase.

## Update the existing app action in Zapier

Keep the thinkorswim email trigger and Assistro/WhatsApp action. Coordinate the app action with deployment. Both existing URL paths remain available:

- `POST <verified-backend-origin>/api/bot/email-webhook`
- `POST <verified-backend-origin>/api/bot/message`

Use the actual backend origin from deployment or the existing Zap. The visible website URL may be a separate frontend origin; do not guess the API host.

Set a generated secret of at least 32 characters as `STOCK_ALERT_WEBHOOK_SECRET` on the backend. Add the same value to Zapier's **Headers** as `X-Stock-Alert-Secret`. Keep it in private configuration, outside React variables, URLs, source and screenshots. `Authorization: Bearer <secret>` is also accepted. A member session credential is not this integration secret.

Zapier supports custom headers in its Webhooks action, allowing reuse of the existing trigger and POST. [Official Webhooks instructions](https://help.zapier.com/hc/en-us/articles/8496326446989-Send-webhooks-in-Zap-workflows).

### Payload mapping

| App field | Map from | Requirement |
| --- | --- | --- |
| `category` | Literal `stocks` | Recommended explicit value; other categories are rejected. |
| `message_id` | Original email Message-ID or stable mail-provider message ID | Preferred identity; keep the same ID on retry. Do not use Zap execution time. |
| `source_timestamp` | Original sent/date field with timezone | Recommended even with an ID; provides source time and stale-alert suppression. |
| `symbol` | Extracted ticker, such as `AAPL` | Prefer an explicit ticker. The app can otherwise try limited recognized email patterns. |
| `price` | Extracted alert price as text | Optional; recognized body patterns are also parsed. This is an alert price, not a live quote. |
| `subject` | Original email subject | Existing subject aliases remain accepted. |
| `body` | Plain-text alert body | Existing `content`, `text`, `message`, `email_body` and `Body` aliases remain accepted. |

No mailbox provider is assumed. Inspect the trigger's actual fields to identify its stable original ID. Without that ID, the app requires an original timezone-qualified timestamp and derives an identity from dated normalized content. That fallback cannot distinguish identical messages with exactly the same source timestamp; a stable email ID is preferred.

The shared record contains the ticker, optional alert price, source/receipt times, and a generated summary. It does not display the mailbox envelope or raw email as a trusted administrator message. Richer strategy-condition text requires a defined mapping from a redacted representative alert before it is added.

Malformed ticker, invalid price/date, missing identity, and unrelated categories produce errors rather than invented signals. Reusing the same ID for changed normalized content returns `409`. Replaying the same valid email returns its existing record without another push. [Zapier replay behavior](https://help.zapier.com/hc/en-us/articles/19220226086797-What-is-replay).

## App API

Member endpoints require the current `X-User-ID` and `X-Session-ID`, plus approved membership or an unexpired trial. Preference ownership comes from the verified login.

| Method and route | Result |
| --- | --- |
| `GET /api/stocks/alerts?limit=50` | `{alerts, has_more}`; newest first. Optional `symbol=AAPL`. |
| `GET /api/stocks/alerts/{alert_id}` | `{alert}`; retrieves the exact older record selected by a notification. |
| `GET /api/stocks/notification-preferences` | `{stocks_enabled: boolean}`; defaults false. |
| `PUT /api/stocks/notification-preferences` | Body/result `{stocks_enabled: boolean}`. |
| `GET /api/stocks/alerts/{alert_id}/dispatch` | Administrator-only aggregate attempt counts. |

Public alert fields: `id`, `category: stocks`, `source: schwab_thinkorswim`, `symbol`, `title`, `body`, optional `price`, optional `source_timestamp`, `received_at`, and a same-origin URL. HTTP success confirms storage, not device delivery.

Stocks refreshes while visible, on focus and after a foreground stock push. The feed works with push off or unsupported. Exact older records are fetched when a link selects them. This version displays recent records; it has no pagination UI. The endpoint permits up to 100 recent rows per request.

## Dispatch and failure behavior

The existing backend process starts the dispatcher. Mongo collections `stock_alerts` and `stock_alert_deliveries` preserve alert and attempt state. Atomic claims prevent simultaneous workers from sending the same pending job. Each attempt rechecks opt-in, membership, current login, device ownership and expiry close to sending.

| State | Meaning |
| --- | --- |
| `pending` | A durable attempt is waiting. |
| `sending` | One worker owns the provider attempt. |
| `accepted` | Firebase accepted the request; phone display is not proven. |
| `retry` | A known pre-send failure can retry within expiry. |
| `unknown` | Interrupted or ambiguous provider outcome; no blind automatic resend. |
| `rejected` | Explicit invalid registration/payload rejection. |
| `skipped` | Opt-in, login or device eligibility changed. |
| `expired` | Too old for push; still saved in the feed. |

The loop checks every five seconds. Push lifetime is five minutes, capped by source time when supplied. Old replays therefore remain history without fresh urgent pushes. The worker checks recipient context and expiry, and shares foreground/background duplicate suppression. Unknown outcomes require investigation; this draft has no manual-resend endpoint.

Generic chat/admin/social send helpers and the legacy test-notification sender are suppressed. The Firebase service no longer calls an unavailable multicast method or reports fake success when configuration/provider calls fail. It sends individual data-only Stocks messages with the existing registration-token scheme. A future Installation-ID migration must update browser, worker, server SDK and stored target types together.

## Phone and login behavior

Permission is requested only after a member taps the control. Saved preferences reconnect only if that browser already has permission. The screen distinguishes ON from a preference that still needs device setup and offers reconnect or opt-out.

For iPhone/iPad web push, add CashOutAI to the Home Screen, open it there, sign in, then enable stock alerts. iOS/iPadOS 16.4 or later is required. Other browsers are checked for secure-context, service-worker, Push API and notification support. Native Capacitor push is not part of this web-push patch. [WebKit guidance](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/).

One active login still applies. A separate TV login replaces a phone login and its push eligibility. The new device still needs browser support and permission; moving access does not guarantee push on a TV. Casting keeps the phone login. Provider-accepted messages cannot be recalled, but local opt-out/logout clears the matching browser state and displayed notifications when its worker is reachable.

## Coordinated rollout

1. GitHub write access is verified and the review branch is `codex/cashoutai-square-launch-2026-11-25`. Current main was rechecked against reviewed commit `5702460a275cda067dba510dc4ba4432f1051359`. Review the complete branch before merging; it is not a production deployment.
2. Verify backend origin, Mongo access, Firebase service account, public client/worker project match, VAPID configuration and installed dependency versions. Keep credentials out of source/reports.
3. Deploy backend, frontend, worker, secret and Zapier app-action mapping together. Existing unsigned intake fails closed under the new code. Keep the Assistro action intact.
4. Use a staging/test member and representative redacted email for a controlled check: one record after a duplicate ID, no social/chat push, mobile opt-in, exact alert link, and replacement-login behavior. Real pushes or WhatsApp messages require explicit authorization for the destination. Avoid replaying a full live Zap, which may repeat the WhatsApp action.
5. Keep both channels during adoption. Use observed app adoption and delivery reliability to decide when to retire WhatsApp.

Local tests use isolated fake databases/providers and synthetic alerts. They do not certify Firebase delivery or the current Zapier setup. The private preview has an honest empty feed and no permission prompts. A full production build and deployment check remain separate from the local module bundle. No production code, real message or external workflow has been changed by this draft.
