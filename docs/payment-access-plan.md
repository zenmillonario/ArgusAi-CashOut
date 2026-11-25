# One-time Square purchases and manual membership approval

**Status: implementation draft for review; not deployed.** The owner confirmed one-time purchases and chose manual approval for this launch. Members create or use one CashOutAI account, pay through a supplied Square link, and wait for the owner to review the payment and approve access. The approval action starts the welcome-email process. Square API credentials, webhook subscriptions, and a billing reconciliation worker are not required for this selected workflow.

## Approved membership options

| Display label | Billing plan ID | USD price | Access from a new paid approval |
| --- | --- | ---: | --- |
| 1 month | `monthly` | $99 once | One calendar month |
| 6 months | `six_months` | $499 once | Six calendar months |
| Lifetime | `lifetime` | $899 once | Lifetime, without an expiry date |

All three are **one-time purchases with no automatic renewal**. The internal ID `monthly` means one month of access, not a recurring charge. A member who wants another term makes a new purchase. The paid offers add no recurring trial, discount, tax assumption, or refund policy. The separately approved free practice event has a fixed cutoff described in the member launch plan. The owner confirmed the purchase terms; the live Square Dashboard settings have not been independently inspected.

## The selected member journey

1. **Use one account.** Existing members keep their stable member ID, profile, history, and established access. Valid saved credentials remain supported; historical accounts without a saved hash establish a password through verified recovery on the same account. The website's `?join=monthly`, `?join=six_months`, and `?join=lifetime` routes select a plan within the app. Do not register a second account or repurchase access to recover login.
2. **Keep a new request pending.** Registration does not unlock paid rooms. The separate billing sign-in verifies the account password and gives limited access to its membership screen. Event access uses a separate explicit email confirmation flow. Password recovery and billing authentication do not establish event enrollment.
3. **Pay the selected one-time price at Square.** The membership screen opens the corresponding owner-supplied reusable link and shows the member's account email and identity. Ask members to use that email at Square. If their payment email differs, they give the team their CashOutAI account email and Square receipt/payment reference for matching.
4. **The owner reviews the purchase.** The owner uses their existing Square alert and payment record to check the buyer, purchased plan, amount, and completed payment. A selected plan, screenshot, browser return, or email match alone does not activate access. The app does not automatically consume the Square alert in manual mode.
5. **Approve the paid purchase in CashOutAI.** A current administrator selects the member and actual purchased plan, records the Square payment or receipt reference, confirms the match, and chooses **Approve access & send welcome email**. The app records an administrator-reviewed purchase and its term once.
6. **Welcome the member.** The approval schedules the existing welcome-email path once. The member can refresh membership status and sign in after approval. If the email fails or is unavailable, access remains approved and the administrator sees that separate outcome.

The same-email instruction helps the owner find the right record; it is not payment proof. Shared Square links do not create an authenticated CashOutAI account binding. Do not append an invented member parameter and treat it as verification. Square documents reusable Dashboard links and transaction-specific API links in its [Checkout API guidance](https://developer.squareup.com/docs/checkout-api/common-pitfalls).

## Paid approval and renewal rules

A new one- or six-month term starts when the administrator approves it. Another purchased term extends from the later of approval time or the current paid-through time. Calendar-month arithmetic clamps to the end of a shorter month where needed. Lifetime has no expiry and must not be downgraded by a shorter purchase.

The approval record links the member, selected plan, fixed USD amount, receipt/reference, approving administrator, approval time, and entitlement. It is **administrator-reviewed evidence**, not a Square-API-verified payment. Keep that distinction visible in the ledger.

A receipt/reference is required: 3–192 letters, numbers, underscores, or hyphens. Enter the payment/receipt code, not a receipt URL. References are deduplicated case-insensitively. Retrying the same reference for the same member and plan returns the existing approval, adds no time, and sends no second welcome email. Reassigning that reference to another member or plan is rejected for review. A renewal needs a new real payment reference.

The separate **Grant complimentary access** action records independent access without a purchased term or paid-through date. Use **Approve a paid purchase** for Square purchases so the receipt, dates, and email outcome are tracked together. This release does not add a receipt editor, arbitrary entitlement override, or automatic refund revocation.

## Draft API contract

All paths below are beneath `/api`.

| Endpoint | Purpose in manual mode |
| --- | --- |
| `GET /billing/plans` | Fixed one-time plans, supplied Square URLs, approval mode, and automatic-feature availability flags. |
| `POST /billing/auth` | Body `{username, password}`; returns short-lived billing-only proof without unlocking paid rooms. |
| `GET /billing/status` | The authenticated account's membership, payment, and approval state. |
| `GET /billing/admin/payments` | Payment/approval ledger for a current administrator. |
| `POST /billing/admin/approve` | Body `{user_id, plan_id, payment_reference, confirm_payment_reviewed: true}`; a current administrator approves one reviewed purchase. |

Restricted billing requests use `X-Billing-Token`; eligible members can also use their current normal session. A billing token cannot authorize another account's records, member-room APIs, or admin actions. Paid approval requires the administrator's actual active session.

The approval response includes the authoritative entitlement/payment and `welcome_email.status`: `pending`, `sending`, `sent`, `failed`, `unavailable`, or `unknown`. `sent` means the email service accepted the message, not proof of inbox delivery. Repeating an approval is not an email-resend feature.

## Preserve existing access

The release must reuse the production database and stable `users.id`; existing members do not register again. Preserve existing approved, lifetime, and independently administrator-granted access. If such a member later buys a dated term, that independent access is retained; expiry of the new purchase does not silently remove it.

Existing trial accounts keep their established dates and normal active/expired rules. Ordinary rolling trials stay disabled in both registration UI and server. The explicitly enabled, email-verified practice event is the sole new free-access exception and has one fixed deadline. A new paid-plan selection still creates a pending request until the owner approves it.

Paid expiry is enforced alongside the active session on protected APIs and room/stream access. Keeping a device signed in does not make a one-month membership permanent. Renewal does not require a new identity or an artificial login reset. The single-active-session rule remains.

## Optional automatic Square integration: dormant

`MEMBERSHIP_APPROVAL_MODE` defaults to `manual`; an invalid value also resolves to manual. In that mode, previously stored Square settings do not enable API checkout, webhook grants, or the billing reconciliation worker. A future switch requires explicit `automatic` mode **and** the existing Square enable/configuration checks. Automatic activation is not part of this launch decision.

New manual paid approvals are disabled in automatic mode; an already-recorded manual receipt can still be recovered idempotently. A future mode change must be a coordinated deployment that drains the old billing work before enabling the other mode, rather than running manual and automatic approval workers concurrently.

The retained automatic draft creates an account-bound checkout intent, verifies the raw webhook signature against the exact configured notification URL, then checks Square's current payment/order, merchant/location, currency, amount, reference, and completed status. Durable records and payment-level deduplication prevent repeated grants. Sandbox transactions never grant real access. [Square signature verification](https://developer.squareup.com/docs/webhooks/step3validate), [GetPayment](https://developer.squareup.com/reference/square/payments-api/get-payment), [RetrieveOrder](https://developer.squareup.com/reference/square/orders-api/retrieve-order)

That future path has separate configuration, sandbox, deployment, and recovery requirements in [square-payments-rollout.md](square-payments-rollout.md). It does not create subscriptions, automatically revoke refunded access, or implement Events API backfill. Those optional requirements do not block the selected manual workflow.

## Release boundary

The draft is reviewable without Square credentials. Production needs coordinated app deployment, preservation of the existing database, current administrator access, and verification of the email service and live Square links. No live payment, approval, email, or member-data migration was performed by this feature review. The separate Render hosting migration is complete; see [member-launch-plan.md](member-launch-plan.md) for account continuity and verified hosting evidence.
