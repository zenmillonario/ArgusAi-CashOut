# CashOutAI member continuity, signup and launch plan

**Release preparation update, November 27, 2026 UTC:** The production frontend hosting migration, isolated native snapshot comparison, and private restored-member recovery are complete. The member-facing release is being prepared for a coordinated backend/frontend deployment. The event stays disabled and memberships stay manually approved until the corresponding live checks pass. See the [completed private recovery evidence](private-recovery-workflow.md) for its exact tested revision and limitations.

## Existing members keep their accounts

The redesign should be deployed as an upgrade of the existing application, using the existing production MongoDB database and stable `users.id`. Existing members should sign in with their current account, not register again. Preserve their membership status, plan, expiration dates, avatar, banner, profile, following relationships, XP, badges, community content and practice history. The new bot practice ledger and Stocks alert collections attach to the existing member ID.

The private visual preview is separate from production. Its local demo profile, posts and practice balance are not migrated member data.

The draft repairs a specific legacy signup defect: registration could delete a rejected account and some related records when the same username or email was supplied. Public signup now rejects an existing identity without deleting or recreating it. New-input whitespace and case are normalized for duplicate checks; existing records are not renamed or silently merged. Regression coverage verifies preservation across approved, pending, rejected, trial and expired-trial statuses.

### Deployment sequence

Follow the [backup and existing-account recovery runbook](backup-and-recovery-runbook.md) for the minimum backup, isolated restore, and recovery rehearsal before deployment.

**Recovery prerequisite completed:** Following the owner's Atlas Flex upgrade, a completed native snapshot passed an isolated M10 restore and record comparison. A separate private runtime then completed recovery on copied member and administrator identities, including the selected member's compiled-browser journey, while preserving records. Both disposable recovery workflows were deleted and the source snapshot retained. Captured recovery emails do not establish production delivery or live provider readiness. Follow [administrator operations](admin-operations.md) for the paid-purchase review controls and [bot operations](bot-operations.md) for the five-asset Windows launcher and publisher; their live integration checks remain separate.

1. Verify the current production database and uploaded-image storage configuration. Take a restorable backup and verify a restoration in an isolated environment. Do not point the new release at an empty replacement database.
2. Compare member counts, stable IDs, membership fields and representative related-record counts in the isolated copy. Audit existing duplicate usernames/emails before adding uniqueness constraints or proposing any merge.
3. Verify existing-member sign-in and email recovery against the isolated copy. Check an approved account, an active trial, an expired trial and an administrator. Use non-production email delivery for the rehearsal.
4. Apply additive schemas/indexes and deploy frontend, backend and service worker together. Coordinate the authenticated Stocks webhook mapping with Zapier; the current Assistro branch remains in place.
5. Check existing members' access before opening a new-member campaign. Preserve current membership terms; a sale must not silently replace existing lifetime plans or expiration dates.
6. Retain a rollback that preserves new member activity and writes. Rolling back application code is different from restoring an older database and discarding activity since that backup.

Read-only aggregate database and provider checks have been completed. They do not replace the backup/restore rehearsal, isolated member-continuity checks, recovery-email delivery verification, or coordinated deployment above. Those checks changed no member records, credentials, memberships, or payment records and sent no emails or notifications.

After those checks, one owner-approved plain delivery test was sent using the existing email configuration. The provider accepted the message, and the owner confirmed it arrived directly in the Inbox. The test contained no recovery token and changed no member records, credentials, memberships, or payments. This confirms inbox receipt for that test; it does not complete an account recovery or verify the reset link and subsequent sign-in.

### Password compatibility

Existing bcrypt and legacy SHA-256 hashes are supported; a verified legacy password is upgraded in place. The historical `hashed_password` alias is accepted only when the canonical `password_hash` is absent and the alias is a recognized hash. A canonical credential always takes precedence, and conditional updates prevent a concurrent password reset being overwritten. Historical registrations may have no saved password hash because the original registration model dropped the field. Such an account must use verified email recovery on the same ID. Re-registering or repurchasing is not the recovery method. Verify the configured email credential and sender, then rehearse recovery before changing production sign-in behavior. Presence of an environment variable alone does not prove that email can be sent.

A one-time reauthentication may be needed during a deliberate security cutover or after a hostname/storage change. The draft does not automatically revoke every member's session at deployment. Any coordinated revocation must wait until recovery delivery works. Reauthentication must not reset membership or community history.

## Keep members signed in while they switch apps

The legacy login screen says “Remember me for 30 days,” but its client stores the session for up to 365 days. Selecting the checkbox also enables a rolling local timestamp refresh after server validation, checked every 23 hours. Unchecked sessions currently also use a fixed 365-day client limit; this is a legacy policy mismatch, not a reason to claim the unchecked option is a short session.

The draft changes the wording to “Keep me signed in on this device” without silently changing the lifetime policy. A temporary network failure must not clear a valid local login. Backgrounding the phone app, switching apps and reconnecting the network do not by themselves revoke the server session. The 30-minute stale-presence cleanup changes the online indicator only.

One active login remains the chosen account-sharing rule. A new login on a separate device replaces the old login; multiple browser tabs using the same session can coexist. Consequently, signing in separately on a TV can replace a phone login, whereas displaying/casting the existing session is a different case. A future paired, read-only TV mode would need an explicit design if simultaneous independent TV and phone access is desired.

Use one canonical app origin in marketing, notification links and installation guidance. A browser, an installed web app and `www` versus non-`www` origins may have different local storage. Inspect the deployed redirects before changing them.

## Current signup and the intended paid-member flow

The reviewed live public signup screen and original source ask for username, real name, email, membership plan and password. They display administrator review. Selecting a plan does not confirm payment. In that legacy flow, the 14-day trial option creates a pending account; the reviewed registration path does not automatically establish an approved trial or trial dates.

At the initial source/live-screen review, the old screen listed a 14-day free trial, $199 monthly, $1,296 yearly and $3,969 lifetime. That observation is historical, not the new offer. The owner has now supplied Square links and confirmed that **1 month for $99, 6 months for $499, and Lifetime for $899 (USD)** are already discounted. Current regular/reference prices are **$199, $999, and $2,499**, giving savings of **$100, $500, and $1,600**. All three are **one-time purchases, with no automatic renewal**, with **manual administrator approval** for this launch. The signup, billing catalog, and marketing draft use the same charged amounts and links. Existing membership terms are preserved. No deadline or automatic price change has been specified for the discounts.

**Current decision: ordinary rolling trials stay disabled.** The registration backend rejects explicit trial requests and trial-labelled plans before creating or changing an account, including requests from older clients. The separately approved fixed practice event below is the only new free-access path: it requires an enabled campaign and email verification, and all participants share one cutoff. Paid-plan selections still create pending requests and do not imply payment. The event does not add a free trial to any Square purchase. These changes are in the release draft; production has not been updated.

Preserve existing trial accounts, their stable IDs, established trial dates, and the normal active/expired access rules. Do not delete, shorten, extend, renew, or convert an existing trial merely because new trials are disabled. Preserve all existing paid, lifetime, and administrator-approved memberships as well. See [payment-access-plan.md](payment-access-plan.md) and [square-payments-rollout.md](square-payments-rollout.md) for the manual approval draft, receipt tracking, and term rules. It has not been deployed.

Legacy trial-expiry and trial-account emails now direct members to the app's current Membership screen instead of repeating the retired checkout offers. They explain one-time purchases and manual review, preserve the original trial expiry, and direct sign-in problems to recovery of the same account. Approval emails also include recovery guidance. No email promises a new trial, automatic activation, a fixed approval deadline, or guaranteed trading results.

Selected flow:

1. **Existing member:** choose Sign in, then manage or upgrade the existing membership. Never create a second identity to purchase a sale.
2. **New member:** create one account and select the open practice event when enabled, or 1 month, 6 months, or Lifetime. Event access requires the separate email confirmation flow. A pending paid-plan account uses the password-proven billing session to purchase/check its own membership; that proof does not unlock paid rooms or normal member login. Password recovery and billing authentication do not substitute for event email verification.
3. **Checkout:** the app opens the supplied reusable Square link for the selected one-time purchase. Ask members to use their CashOutAI account email at Square; if it differs, they give the team their account email and receipt/payment reference. The marketing draft uses account-first `?join=monthly`, `?join=six_months`, and `?join=lifetime` links; deploy those app routes before publishing the marketing draft.
4. **Activation:** the owner receives their existing Square alert, checks the actual payment and member match, then uses **Approve a paid purchase** with the actual purchased plan and receipt/reference. **Approve access & send welcome email** records administrator-reviewed evidence, applies the term once, and schedules the existing welcome-email path. It does not claim Square API verification. A browser return, selected plan, or email match alone does not activate membership.
5. **Lifecycle:** a new dated term begins at approval; a further purchased term extends from the later of approval time or current paid-through time. One- and six-month terms use calendar months; Lifetime has no expiry. Repeating the same receipt/member/plan does not extend access or send another email. Paid expiry is enforced alongside the existing session. Preserve independent legacy access. Refunds and corrections still need owner review; no automatic renewal or refund revocation is added.
6. **Onboarding:** show the separate welcome-email outcome; service acceptance is not proof of inbox delivery, and email failure does not undo access. Introduce the five bot rooms, the $100 simulation, profile setup and the explicit Stocks push opt-in. Social notifications stay in the app.

Manual approval is the chosen launch workflow, not a temporary provider-configuration error. `MEMBERSHIP_APPROVAL_MODE` defaults to `manual`; old Square settings alone cannot enable automatic checkout, webhook grants, or the billing worker. The manual path needs no Square API keys or webhook subscription. The future automatic implementation remains dormant unless explicitly selected and fully configured. The new paid-approval draft still needs deployment and verification of the real database, administrator access, email service, and supplied checkout links. Do not advertise instant activation.

## Hosting: verified Render deployment

The active production arrangement was verified in Render and through public HTTPS checks on November 25, 2026. Repository Vercel/Railway examples are historical deployment alternatives.

| Service | Verified role and state |
| --- | --- |
| `CashoutAi` | Existing Starter Python web service. Serves the backend at `https://cashoutai.onrender.com` from `backend/` on GitHub `main`; the existing MongoDB is retained. |
| `CashoutAi-Static` | New active Static Site. Serves `https://cashoutai.app/`, with `www.cashoutai.app` redirecting to the canonical apex. Both certificates were issued. Builds `cd frontend && yarn install && yarn build` and publishes `frontend/build` from `main`. |
| `CashoutAi-App` | Previous paid frontend web service. Suspended after production verification and retained for recovery. |

The hosting migration used the existing production commit `5702460a275cda067dba510dc4ba4432f1051359`; it did not deploy this feature branch. A `/*` to `/index.html` rewrite preserves app deep links. Public build configuration and notification files were preserved during the migration. HTTPS, main assets, the reset-password route, backend health/database connectivity, and production-origin CORS checks passed again after the old frontend was suspended.

The base running compute is the existing $7 backend; the new frontend uses Render Static Sites. Usage allowances and any extra bandwidth/build charges are separate. See [Render Static Sites](https://render.com/docs/static-sites) and [Render billing](https://render.com/docs/billing). Preserve the current custom domain and database when deploying the feature release. Do not resume the retired frontend during routine releases.

The feature release still requires recovery-email verification, a restorable database backup, isolated member continuity checks, the actual bot publishers, and coordinated Zapier intake changes. No member account, credential, email, or payment was modified during the hosting migration or read-only readiness checks.

## Social navigation and training identity

The redesigned primary navigation exposes Trading, Community, Notifications, Achievements and Profile. Trading contains the five bot rooms plus Stocks. Existing Portfolio, stock practice, Favorites and administrator tools remain accessible.

Preserve the existing community capabilities: text/image posts, replies, reactions, member discovery, follows, avatar, banner, biography and profile styling. “Share a win or lesson” should open an editable community-post template and require the member to send it. It should not automatically publish a trade or imply that a self-entered stock trade is verified profit.

The notification repair leaves unread items unread when the inbox is fetched; explicit read actions change their state. Reactions are persisted through the backend and attributed to the correct member and message author. Both remain in-app activities under the Stocks-only device-push policy.

Achievements already exist, but some catalog badges lack working award logic. Preserve existing earned badges and label future training goals honestly. New training milestones should reward completing lessons, explaining a decision and reviewing practice, rather than only profit, message volume or repeated follows. Cash rewards are excluded from this release.

## ZenMillionaires website and campaign

The existing [ZenMillionaires site](https://zenmillionaires.com/) already has a CashOutAI Resources card and app links. The prepared marketing draft gives the app a more prominent section, keeps the free class and eBook, and separates existing-member sign-in from new registration. It shows the owner's current discounted $99 / $499 / $899 one-time offers beside regular/reference prices and dollar savings, uses app-first links, explains manual approval, and mentions the welcome email. Unlaunched capabilities remain labeled as an upcoming release. No discount deadline or instant activation is promised.

Black Friday is November 27, 2026. A launch event can focus on a short walkthrough, $100 simulated practice and profile/community onboarding. A proposed live-stock segment must account for the NYSE early close at 1:00 p.m. Eastern that Friday; Thanksgiving November 26 is closed. Source: [NYSE holiday calendar](https://www.nyse.com/trade/hours-calendars).

The owner approved opening the practice event as soon as the release is ready, including before Friday; the common deadline is recorded below. Current discounted and regular/reference prices, durations, one-time purchase terms, and manual approval are confirmed. The existing Square links already reflect the discounted offers. Any later price change or discount deadline requires its own explicit terms. Another paid term requires a new purchase. No event announcement has been sent to members.

The owner plans short videos and live trading training, with a possible weekly cadence. The public draft describes this as upcoming education with dates and frequency to be announced. Do not advertise a guaranteed weekly session, completed video library, instructor timetable, or automatic trading service before those exist. A useful initial set is a room walkthrough, a $100 practice example, and a review of one completed PAPER session.

## Source and verification boundaries

The app baseline is [ArgusAi-CashOut commit 5702460](https://github.com/zenmillonario/ArgusAi-CashOut/tree/5702460a275cda067dba510dc4ba4432f1051359). Account and social findings come from `backend/server.py`, `frontend/src/App.js` and the profile, notification, chat and achievement components. The marketing baseline is [zenmillionaires-site commit 170c092](https://github.com/zenmillonario/zenmillionaires-site/tree/170c092639c575fd55b674886f8c8fe60c917f29).

The live login and registration screens were inspected without submitting a registration. Hosting state, aggregate database readiness, and provider responses were checked read-only without changing member records or credentials, approving access, logging in as a member, or sending a message. The later owner-approved delivery test is recorded above separately. A provider response does not establish recovery-email delivery, device-push delivery, licensed streaming access, or end-to-end integration readiness.

The complete CRA production build and **189 backend plus 61 JavaScript tests** passed for the pre-event release candidate. The backend total includes eight email regressions that render legacy trial and approval messages through a simulated provider, without live email or account changes. Browser checks used that compiled app with synthetic accounts and an isolated API fixture, including manual-approval presentation and a pending account becoming active on refresh. These fixture interactions did not change production data. The feature release remains a draft; the current live app has not been updated with it. See [nautilus-rooms.md](nautilus-rooms.md) for the responsive browser checks and their limits.

Before event implementation, the compiled-app signup screen showed only the three one-time membership plans and no trial option. The **Recover existing account** dialog displayed registered-email guidance and explained that recovery preserves the same account without re-registration. The dialog was canceled without submitting a request; this verifies its presentation, not email delivery or a completed recovery.

See also [social-training-review.md](social-training-review.md), [session-and-alerts-review.md](session-and-alerts-review.md), [stock-alert-rollout.md](stock-alert-rollout.md), and [realtime-quotes-and-launch.md](realtime-quotes-and-launch.md).

## Approved open practice event — release readiness required

On November 25, 2026, the owner approved opening registration for a short practice event followed by a Cyber Monday membership cutoff. Enrollment should open as soon as the app is ready, including before Friday. Ordinary rolling trial registration remains disabled. The release draft implements the event; production deployment and verification are required before activation. The owner subsequently clarified that the supplied paid links already use discounted prices. No campaign email has been sent or scheduled, and no discount expiry has been set.

The approved common deadline is **Tuesday, December 1 at 12:00 a.m. America/New_York** (`2026-12-01T05:00:00Z`), advertised as access through **Monday, November 30 at 11:59 p.m. Eastern**. Set the explicit start timestamp when the release is ready; do not hard-code a Friday opening. Every participant receives the same deadline; enrollment on the last day must not create a new rolling trial.

Implemented event flow:

1. Register once, request the verification email, and explicitly confirm the link to receive a temporary event grant. Returning members request a link for their existing registered email. Confirmation creates no login session and changes no password; members then sign in normally or use account recovery when needed.
2. Begin with a short walkthrough of a bot entry, the Nautilus, YES/NO practice, and the resettable virtual $100 balance. Use clearly labeled recorded examples when teaching; an unavailable publisher must not appear live.
3. Show the event deadline and a membership action in the app. Event access is for practice and education; no real-money prize or promised return is introduced.
4. At the fixed cutoff, expire only the event grant, including already-open sessions and sockets. Preserve the account, profile, history, XP, and practice results. Keep sign-in/recovery and membership purchase/status available.
5. A manual paid approval continues access on the same account. Existing paid, lifetime, complimentary, and legacy access takes precedence over event expiration.

Do not implement this by bulk-approving visitors: an approved account without a billing entitlement currently receives legacy access. Keep enrollment idempotent, reject disabled/rejected accounts, and enforce the deadline in the shared server-side access decision rather than relying on periodic cleanup or a browser countdown. Verify concurrent approval, expiry, and enrollment behavior before opening registration. Review posting/upload/login limits and moderation for public participation; shared quote caching is useful but does not establish a provider spending ceiling or public-event capacity.

For a sale, separate the **Square payment completion deadline** from the owner's review time. A completed eligible payment before the advertised cutoff should retain the offer even when reviewed the next morning. A claimed payment alone must not grant paid access. The present manual approval record has the receipt/reference and approval time, but no dedicated Square completion timestamp; add or explicitly document that evidence before using a payment-time cutoff. Any temporary review grace must be explicit and bounded.

See [practice-event-rollout.md](practice-event-rollout.md) for the implemented API, email confirmation, configuration, and release checks.

The supplied $99 / $499 / $899 links are the current discounted one-time offers; regular/reference prices are $199 / $999 / $2,499. They remain separate from the fixed free-event deadline. Keep the actual launch date conditional on a verified backup/restore, recovered-account rehearsal, working bot feeds, and deployed access-expiry checks.

The implemented event revision passed 222 backend tests, 70 JavaScript model tests, and a full CI production build. Its separate eight-scenario synthetic ASGI recovery rehearsal passed again. Fresh event browser checks and a real database restore remain unverified; see the event rollout for the exact evidence boundaries.
