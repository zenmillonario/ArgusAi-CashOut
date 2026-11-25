# Square payment confirmation and membership access

**Status: implementation draft for review; not deployed or connected to live payments.** The owner has identified Square and supplied the three membership prices and reusable checkout links below. The earlier Stripe/PayPal examples are superseded by this Square-specific plan. Production configuration, sandbox exercise, and launch verification are still separate steps.

## Approved membership options

| Display label | Billing API plan ID | USD price | New API checkout behavior |
| --- | --- | ---: | --- |
| 1 month | `monthly` | $99 | One purchase for one calendar month |
| 6 months | `six_months` | $499 | One purchase for six calendar months |
| Lifetime | `lifetime` | $899 | One purchase for a lifetime grant |

The internal ID `monthly` is not a promise of recurring billing. The new API-created checkout flow is one-time; it does not create a subscription or automatic renewal. Existing Dashboard-link renewal settings have not been independently inspected. No free trial, discount, promotional deadline, tax assumption, or refund policy is invented here.

## The member journey

1. **Use one account.** Existing members sign in with their current credentials. The website’s `?join=monthly`, `?join=six_months`, and `?join=lifetime` entry points select the relevant plan. Signed-out visitors can register or switch to sign-in; restored/signed-in members use their existing account.
2. **Allow checkout without opening paid rooms.** New registrations remain pending. The separate billing authentication endpoint verifies username/password and returns a short-lived billing-only token. It does not grant member-room access or replace the normal login session.
3. **Create a member-bound Square checkout.** The server chooses the fixed plan price and creates a checkout intent, then requests a Square payment link with a stable idempotency key. The stored intent binds the member, plan, environment, amount, merchant, location, order, and reference before the link is returned.
4. **Confirm payment on the server.** The app displays payment status while the signed event is verified and Square’s current payment/order records are retrieved. A return to the app is only navigation. A success-page URL cannot activate membership.
5. **Apply access once.** A qualifying production payment grants the purchased term once. Sandbox payments are recorded as tests and never activate real member access. Provider errors, missing configuration, unmatched payments, and pending payments keep access unchanged.

Square’s [Checkout API](https://developer.squareup.com/docs/checkout-api) returns a payment link plus an order ID. Its [payment-method guidance](https://developer.squareup.com/docs/checkout-api/optional-checkout-configurations) specifically requires a completed payment before fulfillment; bank transfers can remain pending after checkout.

## The three supplied links are a separate path

The owner-provided URLs follow Square’s documented reusable Dashboard `/checkout/` format. API-created links are transaction-specific and single-use. A payment through a shared Dashboard link does not automatically establish which CashOutAI account should receive it. [Square’s distinction](https://developer.squareup.com/docs/checkout-api/common-pitfalls)

The draft therefore keeps those URLs as an explicitly labeled **manual-review fallback**. No matching by payer email, amount alone, editable member ID, or screenshot grants automatic access. A verified but unmatched transaction stays available for review. The exact supplied URLs and operational setup are in [square-payments-rollout.md](square-payments-rollout.md).

The website routes members through the app rather than sending anonymous visitors straight to a reusable payment link.

## Draft API contract

All paths below are beneath `/api`.

| Endpoint | Purpose |
| --- | --- |
| `GET /billing/plans` | Public fixed plans, environment, `recurring: false`, manual URLs, and separate automatic-checkout / automatic-activation availability flags. |
| `POST /billing/auth` | Body `{username, password}`; returns `{billing_token, expires_at, user_id, scope: "billing"}`. This is restricted billing proof. |
| `GET /billing/status` | The authenticated account’s payment and membership state. |
| `POST /billing/checkout` | Body `{plan_id, idempotency_key}`; accepts billing proof or a current normal session. Returns a ready hosted URL or a preparing state without a URL. Missing configuration fails closed. |
| `POST /billing/square/webhook` | Public provider notification route, protected by Square signature verification rather than member login. |
| `GET /billing/admin/payments` | Read-only payment review for a current administrator. |

Restricted requests use `X-Billing-Token`. A token cannot authorize other users’ billing records or normal app APIs. Normal members can also use their active app session. Secret Square credentials remain server-side.

## What qualifies as a payment

The receiver verifies `x-square-hmacsha256-signature` against the raw request body, the subscription signature key, and the **exact configured notification URL**, using constant-time comparison. [Square verification](https://developer.squareup.com/docs/webhooks/step3validate)

It then retrieves the current payment and order and checks the recorded intent, expected merchant/location, order/reference, USD amount, and `Payment.status = COMPLETED`. Production is restricted to merchant `VMNWS6K9Y9SN5`; the location must belong to that merchant, be active, and use USD. The new grant is held for review when refund data is present. A completed order or signed notification alone is insufficient. [GetPayment](https://developer.squareup.com/reference/square/payments-api/get-payment), [RetrieveOrder](https://developer.squareup.com/reference/square/orders-api/retrieve-order), [RetrieveLocation](https://developer.squareup.com/reference/square/locations-api/retrieve-location)

Checkout intents, received events, and payment records persist in `billing_checkouts`, `billing_events`, and `billing_payments`. Environment and merchant form part of their identity. The user's `billing_entitlement` stores both the effective grant and applied payment IDs in one atomic, conditional update. That prevents two different events for the same payment from extending access twice and allows bookkeeping to recover after interruption without requiring a multi-document Mongo transaction. Retrying checkout creation reuses its stored provider idempotency key.

## Preserve existing access

Current approved members retain their established membership when no historical Square IDs exist. If such an account later receives a Square grant, `legacy_access` preserves its independently established access; the end of the newly purchased term does not silently remove that legacy membership. Existing lifetime access is not downgraded by a shorter purchase or a failed transaction. Existing trial accounts keep their original dates and normal expiration behavior; new trials remain disabled in both the UI and server.

Paid terms use calendar-month expiry rather than a permanent one-time approval flag. Effective entitlement is checked alongside the active session on protected APIs and room/stream access, so a membership renewal does not require a new login every billing cycle.

Payment records are evidence of payment; administrator approval and manual decisions remain separate. The retained administrator Approve action records independent manual access without a paid-through date. It does not automatically assign a one- or six-month term to a purchase made through a supplied shared link. Use the account-bound verified payment flow for automatic term tracking; any dated manual-grant workflow needs a separate defined policy and implementation. The draft does **not** implement automatic recurring charges, a blanket refund revocation policy, or a new audited manual-override editor. Refunds and unmatched static-link purchases require owner review without erasing unrelated legacy access.

## Reliability and release boundary

Square can deliver duplicates and out-of-order events and retries failed delivery for up to **24 hours**. Durable event state and payment-level deduplication are therefore required. [Webhook behavior](https://developer.squareup.com/docs/webhooks/overview)

A provider outage or lost browser return must not turn into a second charge or a fabricated paid state. The draft worker retries durable unfinished work and reconciles known ready checkouts by reading their Square orders, then independently verifies any discovered payment. This is separate from Square’s [Events API](https://developer.squareup.com/docs/events-api/overview), which can help recover eligible events from the preceding 28 days but must be enabled and has its own authentication rules. An Events API recovery job is not implemented by the checkout polling worker.

The draft can be reviewed without credentials. It becomes a live activation path only after the explicit enable flag, correct production configuration, real webhook subscription, and verified deployment are in place. Testing must keep sandbox and production separate. See [square-payments-rollout.md](square-payments-rollout.md) and [member-launch-plan.md](member-launch-plan.md).
