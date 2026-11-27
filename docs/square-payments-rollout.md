# Square purchases: manual launch and optional future automation

**Status: implementation draft; production has not been updated.** The owner chose one-time purchases with manual administrator approval and a welcome email. The retained automatic Square integration is dormant and is not a launch dependency.

## 1. Fixed membership catalog and supplied links

| Membership | Plan ID | USD cents | Supplied reusable Square link |
| --- | --- | ---: | --- |
| 1 month — $99 once | `monthly` | 9900 | [1-month checkout](https://checkout.square.site/merchant/VMNWS6K9Y9SN5/checkout/SGEVW3GCMZ2X4WSWREYY2RF2) |
| 6 months — $499 once | `six_months` | 49900 | [6-month checkout](https://checkout.square.site/merchant/VMNWS6K9Y9SN5/checkout/FEYSOTOHEO6HE6N4ONWO4F7C) |
| Lifetime — $899 once | `lifetime` | 89900 | [Lifetime checkout](https://checkout.square.site/merchant/VMNWS6K9Y9SN5/checkout/7YFX27AOC4IUYZ5DXP4W3VBL) |

Every purchase is one-time, as confirmed by the owner. The owner clarified that these supplied links already charge discounted prices: $99 instead of the regular $199, $499 instead of $999, and $899 instead of $2,499. Savings are $100, $500, and $1,600 respectively. Regular prices are display metadata; checkout amounts remain 9900, 49900, and 89900 USD cents. No subscription, automatic renewal, rolling trial, coupon, or automatic price reset is introduced. The free-event cutoff does not expire these offers; no discount deadline has been specified. Another fixed term needs a new purchase. The public checkout pages could not be rendered by the research tool, so their live settings and tax treatment have not been independently verified. No transaction was submitted.

These supplied links are the **primary payment path for this manual launch**. Do not invent an account parameter as payment proof. Square distinguishes reusable Dashboard links from transaction-specific API links. [Dashboard/API differences](https://developer.squareup.com/docs/checkout-api/common-pitfalls)

## 2. Manual-mode deployment settings

Set `MEMBERSHIP_APPROVAL_MODE=manual` explicitly in the intended backend deployment. Manual is also the default for an absent or invalid value. In manual mode, former `SQUARE_BILLING_ENABLED` or credential values do not enable automatic checkout, webhook activation, or the billing worker.

**No Square API token, webhook key, subscription, or persistent billing worker is needed for this workflow.** The owner continues to receive their existing Square alert and reviews the payment in Square. The app does not read that alert or automatically verify the payment.

The active backend is the existing Render `CashoutAi` web service at `https://cashoutai.onrender.com`; the frontend is the Render `CashoutAi-Static` site at `https://cashoutai.app`. The existing MongoDB and frontend-to-backend routing were verified during the hosting migration. This membership feature release still requires preserved member records, current administrator access, a restorable backup, and a verified email/recovery path. Database and email settings have not been changed by the release review.

## 3. Member entry and payment matching

The coordinated plan-entry URLs are:

- `https://cashoutai.app/?join=monthly`
- `https://cashoutai.app/?join=six_months`
- `https://cashoutai.app/?join=lifetime`

Deploy and verify those app routes before publishing the marketing buttons. The plan survives switching between registration and sign-in. Existing members use their current accounts. The `?billing=1` route opens membership or asks for sign-in; it never proves payment or changes access.

Pending and expired accounts can use `POST /api/billing/auth` with their username/password to obtain short-lived billing-only proof, sent through `X-Billing-Token`. That portal cannot authorize paid rooms or admin actions.

The **Membership & payments** screen shows **One-time payment · Manual approval**, account email, username, and account ID. Members use the same email at Square where possible. If they paid under another email, they give the team their CashOutAI account email and receipt/payment reference. **Awaiting admin approval** remains until a real administrator decision changes access. A browser return from Square is not activation.

## 4. Owner's approval procedure

1. Open the Square payment record associated with the alert. Check completed payment, actual buyer, matching CashOutAI account, and the purchased $99, $499, or $899 plan. Resolve mismatches, refunds, or incomplete payments before approval.
2. Sign in to CashOutAI as an administrator and open **Approve a paid purchase**. Select the existing member and the actual purchased plan, rather than assuming their registration choice was correct.
3. Enter the Square payment or receipt **code**: 3–192 letters, numbers, underscores, or hyphens. Do not paste a receipt URL. Confirm that payment and account have been reviewed.
4. Choose **Approve access & send welcome email**. The app records the reference, administrator review, member, plan, amount, approval time, and entitlement, then schedules one welcome email through the existing service.
5. Check membership dates and the separate email outcome. Members can refresh and sign in after approval even if email fails. A `sent` email was accepted by the service; inbox delivery is not independently established.

The endpoint is `POST /api/billing/admin/approve` with `{user_id, plan_id, payment_reference, confirm_payment_reviewed: true}`. It requires the current administrator session, not a billing token. The ledger is `GET /api/billing/admin/payments`.

References are deduplicated case-insensitively. Repeating the same member/plan/reference returns the prior grant without extra time or another welcome email. Reusing it for another member or plan returns a conflict. Do not invent a new reference to force a retry or resend.

This is an **administrator-reviewed purchase**, not a Square-API-verified payment. The separate **Grant complimentary access** control records independent membership without a paid-through date. Use paid approval for purchased one- and six-month terms.

### Dates, renewals, and exceptions

A new dated term starts at approval. Another purchased term extends from the later of the current paid-through date and approval time. One- and six-calendar-month calculations clamp shorter month ends. Lifetime has no expiry and is not downgraded by a shorter purchase.

Existing approved, lifetime, and independent complimentary access is retained. A dated purchase does not silently replace it. Existing trial dates stay unchanged; ordinary rolling trials are disabled. The separately enabled, email-verified practice event uses its own fixed cutoff.

Refunds, wrong-account assignments, and corrections require owner review. This release does not automatically revoke refunded access or add an arbitrary entitlement/receipt editor. A repeated approval is not an email resend. Welcome status can be `pending`, `sending`, `sent`, `failed`, `unavailable`, or `unknown`; resolve failed/uncertain email separately from the membership already recorded.

## 5. Verification before the manual launch

Use an isolated app database and stubbed/non-production email service to verify the proposed release:

1. Existing accounts retain IDs, access, profile/history, and recovery options. New registration stays pending. Event access is granted only after the enabled campaign's explicit email confirmation; paid access still requires owner approval.
2. Each plan-entry route reaches the correct one-time Square link after account entry. Billing proof cannot open paid rooms or another account's records.
3. Only a current administrator can approve each plan with confirmed review, receipt evidence, correct dates, and separate email status.
4. Duplicate references do not add time or send twice; reassignment conflicts; a new-receipt renewal extends correctly. Lifetime and independent legacy access remain.
5. Expiry is enforced without deleting login or member history. Failed/unavailable email does not undo approval.
6. Manual mode makes no provider API call and grants nothing through automatic webhook/worker paths, even with old Square flags or credentials present.

These checks do not establish live email delivery, Square notification delivery, or checkout settings. Verify those facts before opening the campaign. Production routing was checked during the separate Render hosting migration; this feature review does not send email, purchase anything, or approve real users.

## 6. Optional future automatic mode — disabled for this launch

Automatic code remains available for a later explicit decision. It only becomes eligible with `MEMBERSHIP_APPROVAL_MODE=automatic` **and** all existing Square enable/configuration checks. Do not switch modes just to use the supplied manual links.

Automatic mode rejects new manual paid approvals, while allowing idempotent recovery of a previously recorded manual receipt. Before changing modes, drain old in-flight billing work and deploy the new mode consistently across backend instances. Do not run mixed manual and automatic approval workers against the same live payment records.

### Future configuration

| Variable | Purpose if automatic mode is deliberately selected |
| --- | --- |
| `SQUARE_BILLING_ENABLED` | Explicit `true`; insufficient without automatic mode. |
| `SQUARE_ENVIRONMENT` | Explicit `sandbox` or `production`. |
| `SQUARE_ACCESS_TOKEN` | Server credential for the chosen seller/environment. |
| `SQUARE_MERCHANT_ID` | Expected seller; production must match `VMNWS6K9Y9SN5`. |
| `SQUARE_LOCATION_ID` | Active USD location belonging to that seller. |
| `SQUARE_WEBHOOK_SIGNATURE_KEY` | Subscription key for this exact environment. |
| `SQUARE_WEBHOOK_NOTIFICATION_URL` | Exact public HTTPS URL ending `/api/billing/square/webhook`. |
| `SQUARE_CHECKOUT_RETURN_URL` | Verified neutral app route such as supported `https://cashoutai.app/?billing=1`; never proof of payment. |

The draft pins `Square-Version: 2026-11-18`. Keep server secrets out of frontend files, commits, chat, URLs, and logs. Separate sandbox and production credentials/objects; sandbox must never activate actual members. [Square sandbox](https://developer.squareup.com/docs/devtools/sandbox/overview)

Future API permissions are `ORDERS_READ`, `ORDERS_WRITE`, and `PAYMENTS_WRITE` for checkout; `PAYMENTS_READ` for payment lookup; and `MERCHANT_PROFILE_READ` for location verification. [CreatePaymentLink](https://developer.squareup.com/reference/square/checkout-api/create-payment-link), [GetPayment](https://developer.squareup.com/reference/square/payments-api/get-payment), [RetrieveLocation](https://developer.squareup.com/reference/square/locations-api/retrieve-location)

### Future verification and recovery

`POST /api/billing/checkout` creates a stored account/plan/order intent with a stable provider idempotency key. The receiver verifies the raw-body signature against the exact notification URL, re-reads payment/order data, requires the expected completed USD amount and merchant/location/account binding, and grants once. Payment created/updated subscriptions are required; refund events flag review rather than inventing a revocation policy. [Signature verification](https://developer.squareup.com/docs/webhooks/step3validate), [payment methods](https://developer.squareup.com/docs/checkout-api/optional-checkout-configurations)

Durable checkout, event, and payment records support retries. The optional worker reconciles known ready orders first after two minutes, then no more often than every five minutes, with a seven-day polling window. Later valid webhooks can still be processed. Square retries unacknowledged webhooks for up to 24 hours and may deliver events out of order. [Webhook delivery](https://developer.squareup.com/docs/webhooks/overview)

The worker does not implement [Events API backfill](https://developer.squareup.com/docs/events-api/overview). Provider credentials, subscription setup, signed-event tests, sandbox exercise, recovery, and worker deployment need a separate review before a future automatic launch. They are not prerequisites for the selected manual workflow.
