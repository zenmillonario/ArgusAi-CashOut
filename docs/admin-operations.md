# CashOutAI administrator workflow

This guide describes the release draft. Verify the matching deployed frontend and backend before relying on these controls with real members. The existing administrator account and member records remain in the current database.

## Open Administration

Sign in with the existing administrator account and choose **Admin** in the top header. The button remains available in the phone layout. Ordinary members do not see it, and the server separately checks the administrator's active session before allowing administration.

The screen contains:

- **Approve a paid purchase** — record a verified Square purchase and grant its purchased term.
- **Member access & reviews** — pending accounts and accounts with temporary access, including expired temporary access.
- **All Users** — existing account and role management.

The review list shows the account status returned by the server and a temporary-access end time when the returned date is valid. A plan's display name does not establish email verification, current entitlement, or payment. The list therefore uses generic status labels rather than inferring event eligibility from a plan name.

## Approve a paid purchase

1. Check the actual transaction in Square. Match the buyer, amount, and purchased plan to the CashOutAI account. If the checkout email differs, use the member's account details and receipt/reference to resolve the match.
2. Open **Admin**. Choose the member in **Approve a paid purchase**, or use **Review paid purchase** on their account card.
3. Select the purchased plan: one month, six months, or Lifetime.
4. Enter the Square payment or receipt code. Use the reference itself rather than a receipt URL.
5. Check the confirmation that you reviewed the Square transaction and matched its buyer, amount, and plan.
6. Select **Approve access & send welcome email**. Review both the access result and the email status.

The current offers are $99 for one month, $499 for six months, and $899 Lifetime, all one-time purchases. The recorded evidence identifies this as an administrator-reviewed purchase; it does not claim automatic verification by the Square API.

Repeating the same receipt for the same member and plan does not add another term or send a second welcome email. A receipt already assigned to a different member or plan is rejected for review. Email delivery status is separate from access: a welcome-email problem does not remove an approved membership. Verify any failed or uncertain email outcome separately rather than recording another purchase.

A new dated term begins at approval. An additional dated purchase extends from the later of the approval time or the existing paid-through date. Existing independent legacy, lifetime, and complimentary access is preserved. Refunds and receipt corrections remain owner review.

## Free event participation

Eligible participants receive temporary event access after explicitly confirming their email. They do not need individual administrator approval to enter the free event. They remain visible in the access review list because that list includes temporary accounts.

Use paid-purchase review after checking a participant's Square receipt. Their account, profile, and practice history stay on the same identity. The fixed event cutoff and original membership terms are enforced separately; see [practice-event-rollout.md](practice-event-rollout.md).

**Grant complimentary access** is an intentional free membership decision. It is separate from recording a purchased term and requires its own confirmation. **Reject** denies the account's access. Neither action is the normal way to record a Square purchase.

## Administrator login and testing

The real administrator may retain the username `admin`. The release preserves that account and does not reset its password. It does not automatically create a default public administrator, elevate a public signup named `admin`, or provide a special password bypass. A login must verify the account's stored credential.

Use the isolated review fixture for generic test credentials:

| Fixture login | Purpose |
| --- | --- |
| `admin` / `admin123` | Synthetic administrator alias, available only in the isolated review server. |
| `reviewadmin` / `review-only` | The same synthetic administrator under its original fixture username. |
| `reviewmember` / `review-only` | Synthetic member. |
| `reviewpending` / `review-only` | Synthetic pending account for membership and approval practice. |

The fixture alias maps to an existing in-memory test identity. It does not create or change a production account. The preview uses the compiled application with synthetic members and payment records; it blocks external requests, payment links, push, and email delivery. It is not the production app and must not be deployed as the real service. The fixture is prepared locally; this guide does not claim that a public test URL has been hosted.

The one-active-session rule remains in production. A fresh login to the real administrator account replaces its previous session. Using the isolated fixture avoids interrupting the owner's live session or performing real approvals during UI review. Live administration should use a private password; the generic fixture credentials are not a production access mechanism.

## Implementation references

- `frontend/src/social/AppNavigation.js` — administrator header entry.
- `frontend/src/App.js` — member review cards, complimentary access, and user management.
- `frontend/src/billing/BillingPanel.js` — paid-purchase form and recorded outcomes.
- `backend/square_billing.py` — authenticated receipt review, duplicate handling, term grant, and welcome delivery state.
- `backend/server.py` — administrator/session checks, account continuity, and temporary-account listing.
- `verification/release-preview` in the review workspace — synthetic API and generic test alias; excluded from production application code.
