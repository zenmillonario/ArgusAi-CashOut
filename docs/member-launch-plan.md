# CashOutAI member continuity, signup and launch plan

**Reviewed November 25, 2026. Status: implementation draft and launch plan; production has not been updated.**

## Existing members keep their accounts

The redesign should be deployed as an upgrade of the existing application, using the existing production MongoDB database and stable `users.id`. Existing members should sign in with their current account, not register again. Preserve their membership status, plan, expiration dates, avatar, banner, profile, following relationships, XP, badges, community content and practice history. The new bot practice ledger and Stocks alert collections attach to the existing member ID.

The private visual preview is separate from production. Its local demo profile, posts and practice balance are not migrated member data.

The draft repairs a specific legacy signup defect: registration could delete a rejected account and some related records when the same username or email was supplied. Public signup now rejects an existing identity without deleting or recreating it. New-input whitespace and case are normalized for duplicate checks; existing records are not renamed or silently merged. Regression coverage verifies preservation across approved, pending, rejected, trial and expired-trial statuses.

### Deployment sequence

1. Verify the current production database and uploaded-image storage configuration. Take a restorable backup and verify a restoration in an isolated environment. Do not point the new release at an empty replacement database.
2. Compare member counts, stable IDs, membership fields and representative related-record counts in the isolated copy. Audit existing duplicate usernames/emails before adding uniqueness constraints or proposing any merge.
3. Verify existing-member sign-in and email recovery against the isolated copy. Check an approved account, an active trial, an expired trial and an administrator. Use non-production email delivery for the rehearsal.
4. Apply additive schemas/indexes and deploy frontend, backend and service worker together. Coordinate the authenticated Stocks webhook mapping with Zapier; the current Assistro branch remains in place.
5. Check existing members' access before opening a new-member campaign. Preserve current membership terms; a sale must not silently replace existing lifetime plans or expiration dates.
6. Retain a rollback that preserves new member activity and writes. Rolling back application code is different from restoring an older database and discarding activity since that backup.

These are required operational steps, not actions already performed. Production database, email, payment and provider credentials have not been accessed or changed in this review.

### Password compatibility

Existing bcrypt and legacy SHA-256 hashes are supported; a verified legacy password is upgraded in place. Some historical registrations may have no saved password hash because the original registration model dropped the field. Such an account must use verified email recovery on the same ID. Re-registering is not the recovery method.

A one-time reauthentication may be needed during a deliberate security cutover or after a hostname/storage change. The draft does not automatically revoke every member's session at deployment. Any coordinated revocation must wait until recovery delivery works. Reauthentication must not reset membership or community history.

## Keep members signed in while they switch apps

The legacy login screen says “Remember me for 30 days,” but its client stores the session for up to 365 days. Selecting the checkbox also enables a rolling local timestamp refresh after server validation, checked every 23 hours. Unchecked sessions currently also use a fixed 365-day client limit; this is a legacy policy mismatch, not a reason to claim the unchecked option is a short session.

The draft changes the wording to “Keep me signed in on this device” without silently changing the lifetime policy. A temporary network failure must not clear a valid local login. Backgrounding the phone app, switching apps and reconnecting the network do not by themselves revoke the server session. The 30-minute stale-presence cleanup changes the online indicator only.

One active login remains the chosen account-sharing rule. A new login on a separate device replaces the old login; multiple browser tabs using the same session can coexist. Consequently, signing in separately on a TV can replace a phone login, whereas displaying/casting the existing session is a different case. A future paired, read-only TV mode would need an explicit design if simultaneous independent TV and phone access is desired.

Use one canonical app origin in marketing, notification links and installation guidance. A browser, an installed web app and `www` versus non-`www` origins may have different local storage. Inspect the deployed redirects before changing them.

## Current signup and the intended paid-member flow

The reviewed live public signup screen and original source ask for username, real name, email, membership plan and password. They display administrator review. Selecting a plan does not confirm payment. In that legacy flow, the 14-day trial option creates a pending account; the reviewed registration path does not automatically establish an approved trial or trial dates.

At the initial source/live-screen review, the old screen listed a 14-day free trial, $199 monthly, $1,296 yearly and $3,969 lifetime. That observation is historical, not the new offer. The owner has now supplied Square links and approved **1 month for $99, 6 months for $499, and Lifetime for $899 (USD)**. The owner explicitly confirmed that all three are **one-time purchases, with no automatic renewal**, and chose **manual administrator approval** for this launch. The local signup, billing catalog, and marketing draft use those options. Existing membership terms are preserved. A promotional discount or sale deadline has not been approved.

**Current decision: no new trial signups for now.** The local signup UI no longer offers a trial, and the registration backend rejects explicit trial requests and trial-labelled plans before creating or changing an account, including requests from older clients. Future checkout offers must also omit new trials; removing the visible choice alone is insufficient. New checkout offers must not create a free trial, trial period, or unpaid access grant. Paid-plan selections still create pending requests and do not imply payment. These changes are in the local draft; production has not been updated.

Preserve existing trial accounts, their stable IDs, established trial dates, and the normal active/expired access rules. Do not delete, shorten, extend, renew, or convert an existing trial merely because new trials are disabled. Preserve all existing paid, lifetime, and administrator-approved memberships as well. See [payment-access-plan.md](payment-access-plan.md) and [square-payments-rollout.md](square-payments-rollout.md) for the manual approval draft, receipt tracking, and term rules. It has not been deployed.

Selected flow:

1. **Existing member:** choose Sign in, then manage or upgrade the existing membership. Never create a second identity to purchase a sale.
2. **New member:** create one account and select 1 month, 6 months, or Lifetime. No new trial is offered. A pending account uses the separate password-proven billing session to purchase/check its own membership; this does not unlock paid rooms or normal member login. New-signup email verification remains separate work and must not be claimed as completed by password recovery or billing authentication.
3. **Checkout:** the app opens the supplied reusable Square link for the selected one-time purchase. Ask members to use their CashOutAI account email at Square; if it differs, they give the team their account email and receipt/payment reference. The marketing draft uses account-first `?join=monthly`, `?join=six_months`, and `?join=lifetime` links; deploy those app routes before publishing the marketing draft.
4. **Activation:** the owner receives their existing Square alert, checks the actual payment and member match, then uses **Approve a paid purchase** with the actual purchased plan and receipt/reference. **Approve access & send welcome email** records administrator-reviewed evidence, applies the term once, and schedules the existing welcome-email path. It does not claim Square API verification. A browser return, selected plan, or email match alone does not activate membership.
5. **Lifecycle:** a new dated term begins at approval; a further purchased term extends from the later of approval time or current paid-through time. One- and six-month terms use calendar months; Lifetime has no expiry. Repeating the same receipt/member/plan does not extend access or send another email. Paid expiry is enforced alongside the existing session. Preserve independent legacy access. Refunds and corrections still need owner review; no automatic renewal or refund revocation is added.
6. **Onboarding:** show the separate welcome-email outcome; service acceptance is not proof of inbox delivery, and email failure does not undo access. Introduce the five bot rooms, the $100 simulation, profile setup and the explicit Stocks push opt-in. Social notifications stay in the app.

Manual approval is the chosen launch workflow, not a temporary provider-configuration error. `MEMBERSHIP_APPROVAL_MODE` defaults to `manual`; old Square settings alone cannot enable automatic checkout, webhook grants, or the billing worker. The manual path needs no Square API keys or webhook subscription. The future automatic implementation remains dormant unless explicitly selected and fully configured. The new paid-approval draft still needs deployment and verification of the real database, administrator access, email service, and supplied checkout links. Do not advertise instant activation.

## Hosting: evidence and remaining confirmation

The owner recalls both Vercel and Railway. A Vercel frontend calling a Railway backend is a possible arrangement, but committed files do not establish the current production split:

| Repository evidence | What it establishes |
| --- | --- |
| `deploy-vercel.json` | A committed configuration describes a React static build and Python backend with `/api` routing on Vercel; it does not prove that configuration was deployed. |
| `vercel-deployment-package/README.md` | A separate package explicitly describes a frontend-only demo. Its example backend hostname is a placeholder. |
| `DEPLOYMENT_GUIDE.md` | Lists alternative Vercel, Netlify + Railway, and Heroku options; these are instructions, not deployment records. |

Both platforms can host Python APIs. Vercel documents FastAPI as a Function, while Railway documents running a FastAPI server with a configured start command and public service domain. The actual service must be confirmed by matching the frontend's deployed API origin to the provider project, source branch/commit, runtime, and existing database. Merely finding two host accounts is insufficient. [Vercel FastAPI](https://vercel.com/docs/frameworks/backend/fastapi), [Railway start commands](https://docs.railway.com/deployments/troubleshooting/no-start-command-could-be-found), [Railway public networking](https://docs.railway.com/networking/public-networking)

Do not rely on the old blanket statement that Vercel cannot serve WebSockets: Vercel announced general availability on October 20, 2026, subject to Function limits. Persistent app workers, connection duration, reconnection, and state still need to be checked against the actual deployment. Manual payment approval itself does not depend on the optional Square worker. [Vercel WebSocket announcement](https://vercel.com/changelog/websocket-support-is-now-generally-available)

No host dashboard, production environment values, database, or deployment settings were accessed or changed in this review. Hosting choices remain a deployment-verification item rather than a reason to delay the manual workflow implementation.

## Social navigation and training identity

The redesigned primary navigation exposes Trading, Community, Notifications, Achievements and Profile. Trading contains the five bot rooms plus Stocks. Existing Portfolio, stock practice, Favorites and administrator tools remain accessible.

Preserve the existing community capabilities: text/image posts, replies, reactions, member discovery, follows, avatar, banner, biography and profile styling. “Share a win or lesson” should open an editable community-post template and require the member to send it. It should not automatically publish a trade or imply that a self-entered stock trade is verified profit.

The notification repair leaves unread items unread when the inbox is fetched; explicit read actions change their state. Reactions are persisted through the backend and attributed to the correct member and message author. Both remain in-app activities under the Stocks-only device-push policy.

Achievements already exist, but some catalog badges lack working award logic. Preserve existing earned badges and label future training goals honestly. New training milestones should reward completing lessons, explaining a decision and reviewing practice, rather than only profit, message volume or repeated follows. Cash rewards are excluded from this release.

## ZenMillionaires website and campaign

The existing [ZenMillionaires site](https://zenmillionaires.com/) already has a CashOutAI Resources card and app links. The prepared marketing draft gives the app a more prominent section, keeps the free class and eBook, and separates existing-member sign-in from new registration. It shows the owner's approved $99 / $499 / $899 one-time membership options through app-first links, explains manual approval, and mentions the welcome email. Unlaunched capabilities remain labeled as an upcoming release. No promotional sale or instant activation is promised.

Black Friday is November 27, 2026. A launch event can focus on a short walkthrough, $100 simulated practice and profile/community onboarding. A proposed live-stock segment must account for the NYSE early close at 1:00 p.m. Eastern that Friday; Thanksgiving November 26 is closed. Source: [NYSE holiday calendar](https://www.nyse.com/trade/hours-calendars).

Given the two-day window from this review date, a member preview and join event is more realistic than promising that all remaining production/payment/feed work will be finished. The base prices, durations, one-time purchase terms, and manual approval workflow are confirmed. Any separate promotional discount still needs approval, eligibility, duration, and start/end time with timezone. Another paid term requires a new purchase. A discount and scheduled event remain proposals; nothing has been announced or sent to members.

## Source and verification boundaries

The app baseline is [ArgusAi-CashOut commit 5702460](https://github.com/zenmillonario/ArgusAi-CashOut/tree/5702460a275cda067dba510dc4ba4432f1051359). Account and social findings come from `backend/server.py`, `frontend/src/App.js` and the profile, notification, chat and achievement components. The marketing baseline is [zenmillionaires-site commit 170c092](https://github.com/zenmillonario/zenmillionaires-site/tree/170c092639c575fd55b674886f8c8fe60c917f29).

The live login and registration screens were inspected without submitting a registration. Signed-in production screens require the browser's secure sign-in workflow; source review alone does not verify current production member records or deployment configuration. The preview's demo interactions are isolated from production.

See also [social-training-review.md](social-training-review.md), [session-and-alerts-review.md](session-and-alerts-review.md), [stock-alert-rollout.md](stock-alert-rollout.md), and [realtime-quotes-and-launch.md](realtime-quotes-and-launch.md).
