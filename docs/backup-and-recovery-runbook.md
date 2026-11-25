# Database backup and existing-account recovery runbook

**Status:** No production backup has been created or isolated restore completed by this review. One owner-approved plain email reached the Inbox; account recovery through a reset link remains a separate verification step. This runbook describes the minimum work before deploying the feature release.

## 1. Retain one consistent, restorable backup

Prefer an **existing provider-native Atlas backup** that supports restoration into a separate target. Confirm that the snapshot completed, record its timestamp and retention privately, and verify the permitted restore destination. A fresh native snapshot is sufficient; a second logical backup is not required merely to satisfy this runbook. Backup availability depends on the actual cluster tier and enabled features. Check the existing configuration rather than assuming availability or enabling a new recurring charge. See [Atlas backup options](https://www.mongodb.com/docs/atlas/backup-restore-cluster/).

If no usable native backup exists, use MongoDB Database Tools to create a **BSON archive with collection metadata and index definitions**. Include every application collection: accounts, community content, notifications, trades, positions, device registrations, and any additional collections present at capture. Preserve inline images and external asset references. Inventory files uploaded to the runtime and their storage locations; separately retain any stored outside MongoDB. A user-only or JSON/CSV export is insufficient for this restore rehearsal.

Establish consistency before the logical dump. Without oplog capture, briefly pause all writers for the dump: application requests, background workers, and external integrations that can write. Blocking only the website does not stop background changes. Resume writers after successful capture. Where the deployment and permissions support it, oplog capture/replay is an alternative, but `mongodump --oplog` requires a full replica-set dump and cannot be combined with `--db`; it is not a generic flag for a database-scoped backup. See [mongodump consistency requirements](https://www.mongodb.com/docs/database-tools/mongodump/).

Keep the completed backup in a durable, private, access-controlled destination outside the application runtime. Protect it as sensitive account data, record an integrity checksum for an archive, and verify it can be retrieved. Do not place dump contents, credentials, or member details in Git, build artifacts, or chat. Temporary runtime storage alone does not complete the backup step.

## 2. Restore before running the application

Restore into an **empty, isolated MongoDB target**. Use a MongoDB 8 target compatible with the source major version and feature compatibility version (FCV); check the provider's destination restrictions before a native restore. Never restore over production or use `--drop` against production. Use [Atlas snapshot restore guidance](https://www.mongodb.com/docs/atlas/backup/cloud-backup/restore-from-snapshot/) or [mongorestore](https://www.mongodb.com/docs/database-tools/mongorestore/) for the selected backup format. Commands must be prepared for the actual environment; this runbook does not claim any backup command has been tested.

Before starting the app, compare the captured backup state with the restored copy:

- Collection and document counts, collection options, and index definitions.
- The stable member-ID set and account status, membership plan, original expiry, administrator status, and credential-field presence.
- Preserved profiles, follows, XP, badges, community content, and practice/trade history.

Record aggregate counts and equality results or private digests. Account for the backup timestamp rather than comparing with a moving production database. Keep any discrepancies unresolved until explained.

## 3. Start the release only inside the isolated environment

Set `MONGO_URL` and `DB_NAME` explicitly **before importing `server.py`**; the module reads them before `load_dotenv`. Use database credentials restricted to the isolated target. Do not copy the production environment file or provider credentials into the rehearsal. Set `FRONTEND_URL` to the isolated frontend so captured reset links cannot lead to production.

Install a captured email transport and deny outbound provider traffic before startup. Preserve the actual application routes, validation, password hashing, and database operations; replace only external delivery boundaries. Captured tokens remain private rehearsal data.

The release has no global switch that disables every worker. Starting it can change the database even before member traffic:

| Operation | Expected effect |
| --- | --- |
| Main lifespan | Adds message/user indexes; checks for an administrator without creating one. |
| Manual billing initialization | Adds billing indexes, including TTL indexes for temporary credentials and rate limits. It starts no continuous Square worker. |
| Stocks worker | Updates queued delivery state and may attempt push delivery immediately. |
| Practice settlement worker | May settle open virtual positions using verified official outcomes. |
| Cleanup after ten minutes | Updates stale presence and existing trial expiry; may send expiry email. |

These effects are acceptable only in the isolated copy during rehearsal. Keep manual approval explicitly selected with `MEMBERSHIP_APPROVAL_MODE=manual`.

## 4. Rehearse recovery of an existing identity

Use an approved account from the restored copy that lacks a saved password hash. Also verify the existing administrator remains usable. Use existing active/expired trial records where present to check their original access rules.

1. Confirm the member's copied saved session works before recovery.
2. Submit the real recovery request and capture its email. Confirm the request stores an expiring token hash without changing the password or revoking the saved session.
3. Open the captured link in the matching isolated frontend, choose a valid password, and complete recovery through the real API.
4. Verify the consumed token cannot be reused, the new credential verifies, and only that member's previous session is invalidated.
5. Sign in with the new password. Confirm the same member ID, membership, expiry, profile, follows, badges, and history. Normal login may update presence, streak, and XP; it must not create another account or require another purchase.

No production member credentials or access are changed by this rehearsal. The confirmed plain-email delivery and captured recovery exercise provide different evidence; neither should be described as a completed production recovery.

## 5. Record the release evidence

Record the backup timestamp/location reference, successful restore, comparison results, tested release revision, and recovery outcome privately. A full-ASGI test with fake MongoDB is useful additional evidence; it does not replace a real database restore and rehearsal. Retain the backup through deployment verification. A routine application rollback should preserve subsequent member writes; restoring an old database is a separate recovery decision that can discard newer activity.

## 6. Completed synthetic ASGI rehearsal

`backend/tests/rehearse_full_app_recovery.py` passed **eight scenario groups** with six synthetic accounts. This is separate evidence from the **189 backend unit tests and 61 JavaScript tests**; it does not change those suite counts.

The script imports the actual `server.py`, enters its actual lifespan, and calls its routes in process through `httpx.ASGITransport`. FastAPI dependencies, Pydantic validation, SlowAPI limits, bcrypt, recovery email templates, and request background tasks execute normally. Mongo storage uses `mongomock-motor`; the final Resend SDK send is captured locally; Firebase is replaced. The process clears inherited configuration, disables dotenv loading, and installs a socket/DNS denial hook before application import. It starts no HTTP server. The hook's deliberate self-test passes; urllib3's local IPv6 capability probe is disabled inside this disposable process.

The eight groups cover:

1. Recovery of an approved historical account without a saved hash, preserving its identity and access.
2. Recovery of an account with an existing bcrypt hash, rejecting its old password afterward.
3. Recovery of a pending account without approving it or changing membership.
4. Actual login and canonical migration of a recognized alternate bcrypt credential.
5. Actual login and bcrypt migration of a legacy SHA-256 credential.
6. Rejection of superseded and expired verification links without credential/session changes.
7. Actual reset-request throttling: request six receives `429`; an unknown email sends nothing.
8. Actual startup/shutdown of all three workers against isolated, empty queues, with unchanged saved history and no external network attempts.

The recovery groups also verify saved-session continuity before confirmation, invalidation after confirmation, rejection of token reuse and obsolete direct reset, successful new-password login, single-session replacement, unchanged unrelated sessions, and preservation of profiles, follows, achievements, XP, messages, trades, and notifications. The run captured **eight synthetic emails**, sent **zero real emails**, and recorded **zero unintended network attempts** after the denial self-test.

### Reproduce the isolated exercise

From the repository root, use Python 3.12 and a separate environment. This recipe pins the directly used package versions measured in the successful rehearsal. It reproduces the tested dependency subset; it is **not a claim that the complete production requirements were installed or verified**.

```bash
python3.12 -m venv recovery-venv
recovery-venv/bin/python -m pip install \
  fastapi==0.110.1 starlette==0.37.2 pydantic==2.11.7 \
  slowapi==0.1.9 limits==5.8.0 bcrypt==5.0.0 \
  motor==3.3.1 pymongo==4.5.0 resend==2.26.0 httpx==0.28.1 \
  mongomock==4.3.0 mongomock-motor==0.0.36 \
  aiohttp==3.14.5 python-dotenv==1.2.2 \
  python-multipart==0.0.32 requests==2.34.2
recovery-venv/bin/python backend/tests/rehearse_full_app_recovery.py
```

The core application versions above match their production pins. These supporting versions differed in the tested environment:

| Package | Rehearsal version | Production requirement |
| --- | --- | --- |
| `aiohttp` | 3.14.5 | 3.12.14 |
| `python-dotenv` | 1.2.2 | 1.1.1 |
| `python-multipart` | 0.0.32 | 0.0.20 |
| `requests` | 2.34.2 | 2.32.4 |

### Limits of this evidence

This rehearsal does **not** complete the backup, restore, and restored-data comparisons in sections 1–5. Synthetic Mongo storage does not establish Atlas durability, deployed index behavior, or real database concurrency. Captured delivery verifies email generation and invocation, not provider or Inbox delivery. Actual backend ASGI requests do not verify browser rendering, opening a reset link in the frontend, public routing, or the deployed frontend/backend combination. Empty worker queues do not exercise live Windows feeds, official settlement retrieval, stock quotes, Square, or FCM. No production member was reset or changed.
