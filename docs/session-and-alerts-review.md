# Sessions, quotes, and stock alerts

Updated: November 25, 2026. This document describes source findings and draft repairs. Read-only aggregate database and provider checks have been completed; provider subscriptions and display rights, external automation state, and end-to-end delivery still require verification. The isolated tests sent no real emails or push notifications. A separate owner-approved plain email test is recorded below; no member data or credentials were changed.

## Accepted product direction

- Cash rewards are outside the current scope. Keep the learning points, badges, and resettable practice balance separate from any future cash program.
- Keep one active authenticated login per account. A successful new login replaces the previous login. Multiple tabs sharing that same login are not separate account sessions.
- The owner confirmed **Schwab thinkorswim email → Zapier → CashOutAI**, plus the existing **Zapier → Assistro → WhatsApp** action. Make CashOutAI the main saved alert record while keeping WhatsApp during the transition.
- Only Stocks alerts send device push. Community chat, admin posts, follows, reactions, mentions, XP, and the five bot rooms stay inside the app. Push is an explicit member opt-in, initially off.

The current single-login policy also applies across a phone and an independently signed-in TV browser. Casting the active screen uses the same session. A paired, read-only TV display could be a future explicit feature; it is not included or silently exempted from this policy.

## Single-session repairs in this draft

The original login stored one `active_session_id`, and the client reacted to a session-invalidated event. However, logout cleared the user's stored session using only the user ID, so a delayed logout from the replaced device could clear the replacement login. The old socket manager also identified connections by user rather than by the exact login; connection-time checks alone were not sufficient to revoke an already open socket on another server worker.

The draft now saves the replacement session before invalidating old connections, targets invalidation to the replaced session, and clears a session on logout only when the presented credential matches the stored one. Quiet sockets revalidate periodically, private outgoing socket deliveries check the stored session, and stale disconnect cleanup cannot mark a replacement login offline. Legacy member REST routes require an active session; the new Nautilus API already performed that check independently.

The browser captures the session that starts each connection or asynchronous account request. A stale socket, poll, profile response, password response, or logout completion cannot clear or overwrite a newer login. Forced invalidation clears local state without sending a second logout request. Manual logout sends the captured credentials. Session-status polling uses headers instead of putting credentials in the query URL. Polling and socket cleanup handle their respective resources separately.

Push registrations are bound to the active login, with a hash-only device ownership marker and recipient context. The new Stocks dispatcher rechecks the account preference, active session, membership and device ownership near sending. The browser worker requires the matching context before display. Historical registrations must re-register. The older generic push paths are now suppressed. The existing token registration scheme remains coherent across browser and server; a separate migration to newer Firebase Installation IDs has not been attempted.

An active-session check is not a complete ownership or administrator-role audit. Both existing alert intake URL paths now require a dedicated webhook secret and stable source identity. Deploy the backend and update the Zapier header/field mapping together; an unchanged unsigned Zap will be rejected. No live workflow was changed during this work.

## Existing integrations: code versus current operation

| Integration | Verified in the reviewed source | Still needs runtime verification |
| --- | --- | --- |
| Stock quotes | Ticker and portfolio reads share the bounded five-second FMP `/stable/quote` adapter, with observation/receipt timestamps and explicit unavailable states. Generated and profile-price fallbacks are removed. | Current subscription, symbol access, quote delay, market-session state, and member-display entitlement. |
| Quote refresh | Stock Practice loads after a ticker change; Favorites loads on mount/list change or manual refresh. Concurrent normalized symbols share in-flight work and a short cache within one server process. | A deliberate refresh cadence, multi-worker quota budget and actual streaming integration. These UI paths are not streaming feeds. |
| Stock-alert ingestion | Both legacy URL paths now save authenticated, deduplicated Stocks alerts in a dedicated feed. | Actual Zapier field mapping, deployed backend origin, secret configuration and last successful delivery. |
| App push | Stocks-only data messages, explicit mobile-capable opt-in, active-login/device context checks, safe alert links and shared foreground/background duplicate suppression are implemented in the draft. | Firebase service-account/VAPID validity, deployed SDK versions, real browser delivery and production-origin configuration. |
| Imported-alert push | Durable alert and per-recipient dispatch records distinguish pending, accepted, failed/unknown and expired attempts. Generic chat/admin/social push is suppressed. | Coordinated deployment and controlled real-device verification. |
| WhatsApp | The owner confirmed the external Zapier/Assistro branch. It remains the transition channel; no provider switch is needed. | Its current action/account configuration; it was not changed or tested. |

The separate internal portfolio helper previously fell back to generated prices, and the old quote route stamped retrieval time as observation time. Both hazards are corrected in this draft. Observations now retain their source time, while unavailable quotes preserve earlier position values with an explicit status. Stock quote-based fills and automatic stop/take-profit closures remain suspended until market-session and delay entitlement are verified; explicitly entered manual journal prices remain unverified practice entries. See [quote-service-review.md](quote-service-review.md) for the cache, metadata, tests and execution limits.

The original client blocked mobile browsers and asked for permission automatically. The draft removes those paths and the obsolete background admin-check registration. Permission now starts only from Enable stock alerts. Browser capability checks and Home Screen guidance replace blanket mobile exclusion. An alert link retains its Stocks destination through login. The existing manifest already uses standalone display; native Capacitor push is separate future work.

Original-source references: [backend routes](https://github.com/zenmillonario/ArgusAi-CashOut/blob/5702460a275cda067dba510dc4ba4432f1051359/backend/server.py), [frontend app](https://github.com/zenmillonario/ArgusAi-CashOut/blob/5702460a275cda067dba510dc4ba4432f1051359/frontend/src/App.js), [Firebase client](https://github.com/zenmillonario/ArgusAi-CashOut/blob/5702460a275cda067dba510dc4ba4432f1051359/frontend/src/firebase-config.js), [Firebase sending service](https://github.com/zenmillonario/ArgusAi-CashOut/blob/5702460a275cda067dba510dc4ba4432f1051359/backend/fcm_service.py), and [email service](https://github.com/zenmillonario/ArgusAi-CashOut/blob/5702460a275cda067dba510dc4ba4432f1051359/backend/email_service.py).

## Current provider options

### Stock data

FMP still documents the app's `/stable/quote` endpoint. Its free Basic plan lists 250 calls/day and excludes real-time data; permitted symbols and display rights also depend on the account. A functioning URL alone does not prove that the deployed key still has the coverage CashOutAi needs. Sources: [quote endpoint](https://site.financialmodelingprep.com/developer/docs/stable/quote), [current pricing/access matrix](https://site.financialmodelingprep.com/pricing-plans).

### App and phone alerts

Firebase Cloud Messaging itself has no messaging charge. Other infrastructure can have separate costs. Current Firebase web guidance recommends installation-based registration and marks the older token APIs deprecated; update the client and server together instead of mixing registration schemes. Sources: [FCM pricing](https://firebase.google.com/products/cloud-messaging), [web registration](https://firebase.google.com/docs/cloud-messaging/web/get-started).

On iPhone/iPad, web push requires a Home Screen web app on iOS/iPadOS 16.4 or newer and permission requested from a user action. Capability detection and an explicit Enable alerts control should replace the blanket mobile exclusion. Source: [WebKit requirements](https://webkit.org/blog/13878/).

### Existing WhatsApp group

Assistro/SyncMate advertises a free tier of 15 messages/day, up to 450/month, on selected automation integrations with branding. It uses a linked personal/business number rather than the official Cloud API, with associated account/reliability risk. The exact existing integration and any automation-platform costs need checking; the published free tier should not be assumed to cover an arbitrary direct custom-API integration. Source: [Assistro pricing](https://www.assistro.co/pricing/).

Meta's current official Groups API requires an Official Business Account and caps groups at eight participants. Billable messages are priced per delivered recipient; current group service-window/free-tier rules are conditional. It is not a straightforward free replacement for a larger existing trading group. Sources: [Groups API](https://developers.facebook.com/documentation/business-messaging/whatsapp/groups), [group pricing](https://developers.facebook.com/documentation/business-messaging/whatsapp/groups/pricing).

### Optional separate community channel

Telegram permits ordinary bot messages without a messaging charge, with documented rate limits including 20 messages/minute per group. A group or channel would require members to opt into that destination. It is an alternative channel, not an assumed migration from WhatsApp. Source: [Telegram Bot FAQ](https://core.telegram.org/bots/faq).

## Agreed rollout

The complete alert implementation and exact Zapier mapping are documented in [stock-alert-rollout.md](stock-alert-rollout.md). CashOutAI stores the alert before acknowledging intake. Stable email IDs prevent a replay from generating another alert or push. Source time and app receipt time are separate. Alert prices are not presented as current market quotes or fills.

Only opted-in active logins are eligible for push. Provider acceptance does not prove device display. Unconfigured-provider failures can retry before expiry; ambiguous provider outcomes are recorded without blind resend. Push expires after five minutes, capped by source time where supplied, while the record remains in the app feed. Data-only messages use one worker display path, avoiding automatic-plus-manual notification duplication. [Firebase receive behavior](https://firebase.google.com/docs/cloud-messaging/web/receive-messages), [message lifespan](https://firebase.google.com/docs/cloud-messaging/customize-messages/setting-message-lifespan).

The app and Assistro branches can run together during adoption. Keep the existing email trigger and WhatsApp action, add the app's secret header and source identity fields, then verify the coordinated deployment using a staging member. Real-device or WhatsApp test transmissions require explicit authorization; none were performed. The additional provider alternatives above are reference material, not proposed replacements for the agreed route.

## Verification of this draft

The November 25 release candidate passed the complete CRA production build, **181 consolidated backend tests**, and **61 JavaScript tests**. The isolated tests cover ingestion, deduplication, dispatch, opt-in, session context, expiry, worker behavior, and the other account, practice, billing, and social contracts in this draft.

Browser QA used the actual compiled app with synthetic accounts and an isolated same-origin API fixture. Phone and TV frames had no horizontal overflow; fullscreen fallback, TV mode, room-chat open/Escape, entry inspection, practice reset and result presentation, manual-approval status, and community/profile/achievement screens were checked. Stocks displayed a labeled synthetic alert, accepted an NVDA ticker selection, and showed the honest unavailable state when the fixture blocked the external chart. Real email, payment, push, service-worker registration, and external provider connections were disabled. See [nautilus-rooms.md](nautilus-rooms.md) for the detailed checks and limits.

Separately, Resend accepted one owner-approved plain test email with HTTP 200 using the existing configured sender and key. The owner confirmed the message arrived directly in the Inbox. The message contained no password-reset token and made no member or credential changes. This confirms inbox receipt for that test, not a completed account recovery; it did not exercise Stocks push or the Zapier/Assistro workflow.

The feature changes remain on the draft review branch `codex/cashoutai-square-launch-2026-11-25`; the current live app has not been updated with this release. Read-only readiness checks are separate from the isolated UI tests. A coordinated deployment, recovery-email delivery, the actual Zapier action, live publishers, official settlement retrieval, real-device push, and licensed streaming remain unverified.
