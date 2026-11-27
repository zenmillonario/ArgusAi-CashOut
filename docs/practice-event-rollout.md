# Fixed CashOutAI practice event

## Approved behavior

The owner approved a short open practice event on November 25, 2026. Open it as soon as the application is ready, including before Friday. The shared cutoff is **Tuesday, December 1, 2026 at 12:00 a.m. America/New_York**, stored as **`2026-12-01T05:00:00Z`**. Member copy describes access through **Monday, November 30 at 11:59 p.m. Eastern**. A person joining late receives the same deadline.

Ordinary rolling trials remain disabled. The event uses virtual funds and the existing resettable $100 practice ledger. No paid plan, Square link, discount, automatic renewal, or cash reward is introduced by this event. Paid access continues to require the owner's manual review of the actual Square payment.

The event implementation is in the release draft. It has not been enabled in production, and no campaign announcement has been sent.

## Member flow

1. A new participant registers once with the event option. The account remains pending until email confirmation. Someone who already has an account uses its existing registered email instead of creating another identity.
2. The participant requests a verification link. The response is generic for eligible, unknown, and blocked accounts. Delivery uses the existing mail transport, with provider failure recorded separately from access.
3. Opening the link displays an explicit confirmation button. A page load or an email scanner following the URL does not grant access. The browser removes the token from the address and holds it only in memory; refreshing before confirmation requires reopening the email or requesting a new link.
4. The server consumes the token and grants eligible temporary access. The link creates no login session and changes no password. The member signs in normally; an account without a usable saved credential still follows the separate recovery path on the same account ID.
5. The app shows the common deadline and a short practice guide. The Membership screen retains the approved one-time purchase options. Existing paid, lifetime, complimentary, and legacy membership takes precedence over event expiry.
6. At the cutoff, server-side membership checks deny event-only access. Existing accounts, profiles, posts, follows, XP, badges, and practice history remain stored. Recovery and the limited Membership sign-in remain available. A later verified paid approval restores access on the same identity.

The event is an access grant, not a payment receipt. It must never be implemented as blanket permanent approval. Repeated requests or confirmations cannot extend its fixed end time.

## Release configuration

| Setting | Required value or behavior |
| --- | --- |
| `PRACTICE_EVENT_ENABLED` | Defaults to `false`. Set to `true` only when the coordinated release and recovery checks are complete. |
| `PRACTICE_EVENT_STARTS_AT` | Explicit UTC ISO timestamp at release readiness. No Friday restriction. It must be before the fixed cutoff. |
| Campaign ID | `cashoutai-practice-2026`, fixed in code. |
| End time | `2026-12-01T05:00:00Z`, fixed in code. No client-supplied extension. |
| `FRONTEND_URL` | Canonical HTTPS application origin, `https://cashoutai.app`, so confirmation links reach the matching frontend. |
| `MEMBERSHIP_APPROVAL_MODE` | `manual`, preserving the owner-reviewed Square workflow. |

Keep the event disabled while deploying and checking the matching frontend and backend. Enable it with the actual readiness timestamp after verification, then check the public configuration and the member flow. Disabling the event later withdraws event-only access; independent membership remains effective. Application restart is required for changed service settings.

## API and storage boundaries

`GET /api/practice-event` exposes campaign status, server time, start/end, Eastern timezone, and the virtual starting balance. `POST /api/practice-event/request` takes `{email, campaign_id}`. `POST /api/practice-event/confirm` takes `{token}` and returns an explicit result requiring normal sign-in. `POST /api/users/register` accepts `practice_event_id` only while that campaign is open; a display plan label alone grants nothing. Billing status includes the event's enrollment state.

Only a SHA-256 token hash is stored. A link lasts for at most one hour and never beyond the event cutoff. It is bound to the account's email and credential version; reset, credential change, email change, supersession, use, rejection, or disabling can invalidate it. Conditional writes protect concurrent paid approval and enrollment. Confirmation rejects disabled and rejected accounts.

The request path limits attempts by client IP and normalized email; confirmation has its own IP limit. The current thresholds are five link requests per minute per IP, three per fifteen minutes per email, and twenty confirmation attempts per minute per IP. Verify the actual proxy-derived client identity in the deployed runtime; do not accept arbitrary forwarded headers from clients. These limits reduce abuse but do not establish public-event capacity or a provider spending ceiling.

New registrations receive normalized unique keys with sparse unique indexes. Existing accounts are not renamed, merged, or backfilled by this change. Event token fields and grants are excluded from public account responses. Temporary rate-limit records have their own TTL index; no TTL index deletes member accounts.

## Before opening

Follow the [backup and recovery runbook](backup-and-recovery-runbook.md) against the existing database. A Flex upgrade does not itself establish a completed backup. Check a completed backup, isolated restoration, and recovery of an existing identity before the new authentication path is relied on by members.

Verify the deployed route/SPA behavior, canonical email destination, public event configuration, sign-in after confirmation, pending/expired Membership access, cutoff enforcement on HTTP and sockets, and paid-access precedence. Check phone and TV layouts against the compiled event release. Provider email delivery and a captured verification message are separate evidence; do not describe a captured send as an actual Inbox receipt.

Confirm the bot publishers and source freshness before presenting live practice. Label archived or unavailable data accurately. Keep Stocks push and the existing Assistro branch under their separate rollout plan.

## Conversion terms

The current discounted offers are **$99 for one month (regular $199), $499 for six months (regular $999), and $899 Lifetime (regular $2,499)**, all one-time purchases with manual approval. The owner confirmed that the existing Square links already use these discounted amounts. The event cutoff does not automatically change those prices or disable ordinary paid signup. No discount expiry has been supplied.

If the owner later supplies a deadline for the discounted offers, record eligibility from Square's actual payment completion time and the matching offer, even if the owner reviews the receipt afterward. The present manual record stores the receipt and approval time but has no dedicated completion-time field. Do not treat a member's claim, checkout visit, or selected plan as payment proof. No extra review grace or price-expiry rule is configured here.

## Verification recorded November 25, 2026

The updated release passed **222 backend tests** and **70 JavaScript model tests**, including 27 focused event backend regressions and nine new event model tests. Coverage includes fixed-boundary HTTP/socket denial, failed mail without access, token expiry/supersession/reuse, credential and email binding, duplicate registration, paid-approval races, paid conversion, legacy access, and event disabling. The complete CRA production build passed with `CI=true`.

The separate eight-scenario full-application ASGI recovery rehearsal passed again against synthetic Mongo storage, with eight captured messages and zero real mail or unintended network attempts. This remains distinct from a real restored database or an actual browser/email flow.

Earlier compiled-app browser checks covered the pre-event phone, desktop, and TV layouts. A fresh event browser review was not completed: reacquiring the local preview tab was rejected by the browser URL policy, and no bypass was attempted. Production browser, backup/restore, email confirmation, provider-feed, and deployed concurrency checks remain release prerequisites. Unit and model tests must not be presented as those live results.
