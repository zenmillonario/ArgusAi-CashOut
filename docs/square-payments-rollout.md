# Square payments: rollout and operational verification

**Status: implementation draft; production setup and payment testing have not been performed by this review.** This guide documents the selected Square integration and the owner-supplied prices. Do not describe live automatic activation as available until deployment and provider configuration are verified.

## 1. Fixed membership catalog and supplied links

| Membership | Plan ID | Server amount in USD cents | Supplied reusable Square link |
| --- | --- | ---: | --- |
| 1 month — $99 | `monthly` | 9900 | [1-month checkout](https://checkout.square.site/merchant/VMNWS6K9Y9SN5/checkout/SGEVW3GCMZ2X4WSWREYY2RF2) |
| 6 months — $499 | `six_months` | 49900 | [6-month checkout](https://checkout.square.site/merchant/VMNWS6K9Y9SN5/checkout/FEYSOTOHEO6HE6N4ONWO4F7C) |
| Lifetime — $899 | `lifetime` | 89900 | [Lifetime checkout](https://checkout.square.site/merchant/VMNWS6K9Y9SN5/checkout/7YFX27AOC4IUYZ5DXP4W3VBL) |

These prices come from the owner. The public checkout pages could not be rendered by the research tool, so their current settings, tax treatment, and any renewal configuration were not independently verified. No transaction was submitted. The URL pattern matches Square’s documented Dashboard-link format.

The new automated flow creates one-time API links for a stored member/order intent. Keep the supplied Dashboard links intact as the documented manual-review fallback. Do not append an invented account parameter and treat it as an authenticated binding. [Dashboard/API differences](https://developer.squareup.com/docs/checkout-api/common-pitfalls)

The API plan ID `monthly` means one month of access in this draft. It is not an automatic monthly charge. No new trials or subscriptions are created.

## 2. Server configuration

Configure these on the backend through the deployment’s secret/configuration mechanism. Do not place access tokens or webhook keys in frontend code, committed files, chat, URLs, or logs.

| Variable | Required meaning |
| --- | --- |
| `SQUARE_BILLING_ENABLED` | Explicit `true` to enable configured API checkout. Merely storing the public links does not enable it. |
| `SQUARE_ENVIRONMENT` | Explicit `sandbox` or `production`; do not silently fall back between them. |
| `SQUARE_ACCESS_TOKEN` | Server credential for the selected environment and seller. |
| `SQUARE_MERCHANT_ID` | Expected seller. Production must match owner-supplied `VMNWS6K9Y9SN5`. Sandbox uses its own test seller. |
| `SQUARE_LOCATION_ID` | The intended location; the draft verifies its merchant, USD currency, active status, and ID. |
| `SQUARE_WEBHOOK_SIGNATURE_KEY` | Signing key for this exact environment’s webhook subscription. |
| `SQUARE_WEBHOOK_NOTIFICATION_URL` | Exact public HTTPS URL ending in `/api/billing/square/webhook`, including the correct host/path. Signature validation uses this value. |
| `SQUARE_CHECKOUT_RETURN_URL` | The draft supports `https://cashoutai.app/?billing=1` as its neutral HTTPS membership return route. Deploy and verify that app route before using it in live configuration. It is navigation, never payment proof. |

The draft pins `Square-Version: 2026-11-18`. The owner’s real API/backend origin and return route must be used; this document does not invent a production callback host.

Square’s sandbox API base is `https://connect.squareupsandbox.com`; production uses `https://connect.squareup.com`. Credentials and objects cannot be mixed across environments. Sandbox records must be labeled test-only and must never activate actual members. [Sandbox guide](https://developer.squareup.com/docs/devtools/sandbox/overview)

### Permissions

| Operation | Required permissions |
| --- | --- |
| CreatePaymentLink | `ORDERS_READ`, `ORDERS_WRITE`, `PAYMENTS_WRITE` |
| GetPayment and payment event access | `PAYMENTS_READ` |
| RetrieveOrder | `ORDERS_READ` |
| RetrieveLocation | `MERCHANT_PROFILE_READ` |

Sources: [CreatePaymentLink](https://developer.squareup.com/reference/square/checkout-api/create-payment-link), [GetPayment](https://developer.squareup.com/reference/square/payments-api/get-payment), [RetrieveOrder](https://developer.squareup.com/reference/square/orders-api/retrieve-order), [RetrieveLocation](https://developer.squareup.com/reference/square/locations-api/retrieve-location), [webhook permissions](https://developer.squareup.com/docs/webhooks/troubleshooting).

For one owner-operated merchant, choose the appropriate server credential for that seller. If OAuth is used, the seller must have granted the required scopes. Configuring a webhook does not substitute for API permission.

## 3. Checkout and member binding

The app’s plan entries are:

- `https://cashoutai.app/?join=monthly`
- `https://cashoutai.app/?join=six_months`
- `https://cashoutai.app/?join=lifetime`

These routes belong to the implementation draft and must deploy with the marketing links. The chosen plan survives switching from registration to sign-in. Already signed-in users use their existing account. The neutral return query `?billing=1` opens Profile membership for an existing session, keeps a pending account in its restricted billing portal, or asks a signed-out user to sign in. It does not claim checkout success or change membership.

Pending users cannot use normal member login solely to obtain checkout. The separate `POST /api/billing/auth` accepts username/password and returns a short-lived token scoped to billing. Subsequent billing requests send `X-Billing-Token`; paid rooms still require an eligible membership and normal active session.

`POST /api/billing/checkout` accepts only a catalog `plan_id` and an `idempotency_key`. The server records the member/plan/amount/environment intent and creates the Square-hosted link using its own fixed price. Persist the order ID and opaque order reference. A preparing response with no URL is not an invitation for the client to invent a checkout URL or retry with a new payment identity.

Square’s [creation API](https://developer.squareup.com/reference/square/checkout-api/create-payment-link) treats a missing/empty provider idempotency key as a separate request. Reuse the stored key for the same attempt; create a new intent only for a deliberate new purchase.

## 4. Webhooks and eligibility

Configure `payment.created` and `payment.updated` for the deployed endpoint and selected environment. The handler also accepts `refund.created` and `refund.updated` to flag review; subscribe to those when exercising refund tracking. Verify the raw body, `x-square-hmacsha256-signature`, exact configured notification URL, and signing key before recording a trusted event. Compare signatures in constant time. [Signature validation](https://developer.squareup.com/docs/webhooks/step3validate)

The handler retrieves current Square payment/order data and verifies all of the following before a new production grant:

- Correct environment and configured merchant/location.
- A stored checkout intent owned by the target member.
- Exact order ID, opaque reference, plan, and expected USD amount.
- `Payment.status = COMPLETED`, with no refund indication requiring review.
- No previous grant for that payment.

Square documents that a checkout redirect can precede settlement for asynchronous methods. `PENDING`, authorization, or browser success is not sufficient. Order fulfillment state can also remain open after successful payment, so it is not the sole payment test. [Payment-method behavior](https://developer.squareup.com/docs/checkout-api/optional-checkout-configurations), [order-state limitation](https://developer.squareup.com/docs/checkout-api/common-pitfalls)

Refund indications stop a new automatic grant. Existing grants are not automatically revoked under an invented refund policy. The owner must define and approve that policy before enforcement is added.

## 5. Review, retries, and reconciliation

The admin read-only payment view is `GET /api/billing/admin/payments`. Use it to inspect matched, pending, test-only, failed, duplicate, and manual-review cases. Keep payment confirmation separate from any manual membership decision and retain the member’s existing identity.

Square retries unacknowledged webhooks for up to 24 hours and does not guarantee event order. Store received events durably and deduplicate by event ID and payment grant. Provider read failures must stay retryable, not turn into a final “paid” or “unpaid” guess. [Delivery behavior](https://developer.squareup.com/docs/webhooks/overview)

For an outage, inspect [webhook logs](https://developer.squareup.com/docs/devtools/webhook-logs) and re-read the relevant payment/order. The [Events API](https://developer.squareup.com/docs/events-api/overview) supports a 28-day recovery window, requires prior enablement, and uses the application’s personal access token rather than an OAuth token. Access to event types must have existed when those events occurred. Do not promise it can recover arbitrary older or previously unavailable events.

The draft includes a scheduled worker with bounded batches. It retries persisted checkout creation and received events, then reconciles known ready checkouts by reading their orders. The first order check is scheduled after two minutes and later checks no more often than every five minutes. Polling pauses seven days after checkout creation, and canceled orders stop polling. The stored record remains; a later valid signed payment notification can still be verified. Each discovered tender payment ID goes through the full independent payment/order validation; an order alone does not grant access. This worker does not implement Events API backfill.

Automatic refunds and a new audited manual-override editor are not implemented. The retained admin Approve action gives independent manual access without setting a paid-through date; it is not an automatic one- or six-month grant for a shared-link purchase. Payment records and that manual access decision remain separate; a support action must not silently rewrite a receipt as paid.

## 6. Verification before live enablement

Use an isolated app database and Square sandbox to exercise:

1. Register / existing-member sign-in / pending-account billing proof, with no new trials.
2. Each fixed plan and exact amount; unauthorized plan/amount changes rejected.
3. Invalid signature, wrong merchant/location, wrong reference, and unmatched shared-link payment.
4. Successful payment, pending payment, failed payment, refund indication, and provider read failure.
5. Duplicate events, distinct events for one payment, concurrent checkout retries, interrupted processing, and lost browser return.
6. One- and six-calendar-month expiry, lifetime preservation, existing approved/trial accounts, and current-session protection.
7. Sandbox success recorded without activating a real member; production readiness and activation flags remain distinct.

Local automated fixtures test implementation logic; they do not verify live credentials, Square Dashboard configuration, actual settlement, email delivery, or deployment. No live charge is needed to review the code.

After verified configuration and deployment, expose account-first checkout. Keep unconfigured behavior explicit and the supplied static-link fallback labeled manual review. Do not advertise instant activation, recurring charges, a discount, or a sale deadline that has not been approved.

See [payment-access-plan.md](payment-access-plan.md) for the access rules and [member-launch-plan.md](member-launch-plan.md) for continuity and launch sequencing.
