# Database backup and existing-account recovery runbook

**Status, November 25, 2026:** The owner completed payment setup and upgraded the existing cluster to **Flex**. Atlas reports `IDLE`, backups are enabled, and the restarted production backend reports `healthy` / `connected`. The backup page currently lists **zero completed snapshots** and estimates its first snapshot for November 26; a usable backup and isolated restore remain unverified. One owner-approved plain email reached the Inbox; account recovery through a reset link remains a separate verification step. This runbook describes the minimum work before deploying the feature release.

## 1. Retain one consistent, restorable backup

Prefer an **existing provider-native Atlas backup** that supports restoration into a separate target. Confirm that the snapshot completed, record its timestamp and retention privately, and verify the permitted restore destination. A fresh native snapshot is sufficient; a second logical backup is not required merely to satisfy this runbook. Backup availability depends on the actual cluster tier and enabled features. Check the existing configuration rather than assuming availability or enabling a new recurring charge. See [Atlas backup options](https://www.mongodb.com/docs/atlas/backup-restore-cluster/).

If no usable native backup exists, use MongoDB Database Tools to create a **BSON archive with collection metadata and index definitions**. Include every application collection: accounts, community content, notifications, trades, positions, device registrations, and any additional collections present at capture. Preserve inline images and external asset references. Inventory files uploaded to the runtime and their storage locations; separately retain any stored outside MongoDB. A user-only or JSON/CSV export is insufficient for this restore rehearsal.

Establish consistency before the logical dump. Without oplog capture, briefly pause all writers for the dump: application requests, background workers, and external integrations that can write. Blocking only the website does not stop background changes. Resume writers after successful capture. Where the deployment and permissions support it, oplog capture/replay is an alternative, but `mongodump --oplog` requires a full replica-set dump and cannot be combined with `--db`; it is not a generic flag for a database-scoped backup. See [mongodump consistency requirements](https://www.mongodb.com/docs/database-tools/mongodump/).

Keep the completed backup in a durable, private, access-controlled destination outside the application runtime. Protect it as sensitive account data, record an integrity checksum for an archive, and verify it can be retrieved. Do not place dump contents, credentials, or member details in Git, build artifacts, or chat. Temporary runtime storage alone does not complete the backup step.

## 2. Restore before running the application

Restore into an **empty, isolated MongoDB target**. Use a MongoDB 8 target compatible with the source major version and feature compatibility version (FCV); check the provider's destination restrictions before a native restore. Never restore over production or use `--drop` against production. Use [Atlas snapshot restore guidance](https://www.mongodb.com/docs/atlas/backup/cloud-backup/restore-from-snapshot/) or [mongorestore](https://www.mongodb.com/docs/database-tools/mongorestore/) for the selected backup format. Commands must be prepared for the actual environment; this runbook does not claim any backup command has been tested.

A downloaded Atlas snapshot contains **raw database data files**, not a BSON dump. `mongorestore` cannot read that archive directly. Preserve the archive and its checksum, start a working copy with a compatible isolated `mongod --dbpath`, then make a local-only logical copy into a `cashout_rehearsal_*` database for the guarded launcher below. Compare that copy with the raw restored baseline before exercising it. Retain the launcher's refusal of the original production database name. See [restoring a locally downloaded snapshot](https://www.mongodb.com/docs/atlas/backup/cloud-backup/restore-from-local-file/). For a managed restore, use the actual Flex restore selector/API to verify an eligible separate target; no additional target or charge has been approved or provisioned by this runbook.

Before starting the app, compare the captured backup state with the restored copy:

- Collection and document counts, collection options, and index definitions.
- The stable member-ID set and account status, membership plan, original expiry, administrator status, and credential-field presence.
- Preserved profiles, follows, XP, badges, community content, and practice/trade history.

Record aggregate counts and equality results or private digests from the raw restored baseline **before application startup or rehearsal changes**. Retain the source backup so the working copy can be recreated. Account for the backup timestamp rather than comparing with a moving production database. Keep any discrepancies unresolved until explained.

## 3. Start the release only inside the isolated environment

Set `MONGO_URL` and `DB_NAME` explicitly **before importing `server.py`**; the module reads them before `load_dotenv`. Use database credentials restricted to the isolated target. Do not copy the production environment file or provider credentials into the rehearsal. Set `FRONTEND_URL` to the isolated frontend so captured reset links cannot lead to production.

Use a separate launcher with the **real Motor client and restored MongoDB**, not the synthetic script's mocked client or seed routine. Validate the target before import, construct a minimal environment, and disable dotenv loading in both the server and email module. Permit network traffic only to the isolated database and preview origins; the synthetic script's blanket socket denial cannot support a real database or browser.

Install a captured email transport and deny outbound provider traffic before startup. Preserve the actual application routes, validation, password hashing, database operations, and email templates; capture the final Resend SDK send. Restrict captured recipients to the selected restored test identities and keep messages, addresses, and reset tokens private. Replace the FCM module before import: clearing environment variables alone is insufficient because `fcm_service.py` can load `/app/backend/firebase-admin.json`.

The release has no global switch that disables every worker. Starting it can change the database even before member traffic:

| Operation | Expected effect |
| --- | --- |
| Main lifespan | Adds message/user indexes; checks for an administrator without creating one. |
| Manual billing initialization | Adds billing indexes, including TTL indexes for temporary credentials and rate limits. It starts no continuous Square worker. |
| Stocks worker | Updates queued delivery state and may attempt push delivery immediately. |
| Practice settlement worker | May settle open virtual positions using verified official outcomes. |
| Cleanup after ten minutes | Updates stale presence and existing trial expiry; may send expiry email. |

For the targeted recovery rehearsal, replace `server.periodic_cleanup`, `server.stock_alert_service.run`, and `server.nautilus_settlement_service.run` with cancellation-safe idle coroutines **before entering the real lifespan**. This prevents restored queues and historical trial records from being processed while recovery is under examination. Keep the actual lifespan and real index initialization; explicitly call `stock_alert_service.initialize()` once if validating its indexes, since its replaced `run()` would normally initialize them. Keep manual approval explicitly selected with `MEMBERSHIP_APPROVAL_MODE=manual`.

The idle substitutions belong only in the isolated rehearsal launcher. They do not change production worker behavior or establish that processing restored queues has been tested. Build the matching frontend for the isolated API and use a fresh preview origin with external requests and service workers blocked.

## 4. Rehearse recovery of an existing identity

Use an approved account from the restored copy that lacks a saved password hash. Also verify the existing administrator remains usable. Use existing active/expired trial records where present to check their original access rules.

1. Confirm the member's copied saved session works before recovery.
2. Submit the real recovery request and capture its email. Confirm the request stores an expiring token hash without changing the password or revoking the saved session.
3. Open the captured link in the matching isolated frontend, choose a valid password, and complete recovery through the real API.
4. Verify the consumed token cannot be reused, the new credential verifies, and only that member's previous session is invalidated.
5. Sign in with the new password. Confirm the same member ID, membership, expiry, profile, follows, badges, and history. Normal login may update presence, streak, and XP; it must not create another account or require another purchase.

Compare strict account/history preservation immediately after reset confirmation. Then evaluate login separately: its real background reward task can legitimately add XP, achievements, notifications, and achievement chat posts. Record those expected additions and require existing records, identity, and entitlement to remain intact. Do not reuse the synthetic fixture's exact post-login equality check without accounting for its deliberately current login dates, or suppress real login rewards and claim that behavior was exercised.

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

## 7. Atlas inspection and completed upgrade — November 25, 2026

### Current verified state

After the owner completed payment setup and the upgrade, the Atlas integration reports **Flex**, `IDLE`, unpaused, AWS `US_EAST_1`, and MongoDB `8.0.39-patch-a3d00565977`. The existing cluster's connection hostname is unchanged. The dashboard shows **Backups ON** and **zero completed snapshots**. Its estimated next snapshot label is **`11/26/26 - 05:01 PM`**; that label did not explicitly state a timezone, so do not convert it to a promised Eastern deadline. Verify completion from the actual snapshot list.

The existing Render backend was restarted after the upgrade. Render's event history confirms the restart at **5:16 p.m. Eastern on November 25**, its application startup completed at `2026-11-25T22:16:32Z`, and a subsequent HTTPS health request returned `200` with `healthy` / `connected`. It still runs the unchanged production commit `5702460a275cda067dba510dc4ba4432f1051359`; the feature release remains a draft.

The upgrade is complete. **Do not retry it or request the same cost approval again.** A successful tier change and enabled backup schedule do not prove that the first backup is complete or restorable. The next database step is a completed snapshot and an isolated restore/recovery rehearsal.

### Historical inspection before the upgrade

Atlas integration reads now succeed. The inspected CashOutAI database is on the **Free / M0 tier**, reports **IDLE**, and has no open project alerts. Its dashboard shows **Backups OFF**, and no usable snapshot was available. These observations establish the current backup gap; they do not establish a completed backup or restore.

The account's inspected upgrade screen offered Free with **No backups**, Flex with daily backups, and M10. Although MongoDB documents a paid Free-tier backup private preview, that option was not offered in this account's observed UI; do not treat it as an available plan. See the [Free-tier backup private preview](https://www.mongodb.com/docs/atlas/backup/cloud-backup/free-cluster-backup/).

The Flex option was prepared for owner review with the following observed terms:

| Item | Reviewed setting or term |
| --- | --- |
| Provider and region | AWS `us-east-1`, matching the existing source |
| Storage | 5 GB |
| Price | From $0.011 per hour, up to $30 per month, excluding tax |
| Upgrade interruption | Estimated 7–10 minutes of downtime |
| Reversibility | The upgrade is irreversible; a direct return to Free is unavailable |
| Backup schedule | Automatic daily snapshots retained for eight days; no on-demand snapshot |

MongoDB documents the first Flex snapshot as occurring 24 hours after cluster creation. An upgrade must therefore not be treated as an immediately completed backup: wait for an actual snapshot to finish, verify its timestamp and restore eligibility, and then perform the separate restore checks. See [Flex costs](https://www.mongodb.com/docs/atlas/billing/atlas-flex-costs/) and [Flex backup behavior](https://www.mongodb.com/docs/atlas/backup/cloud-backup/flex-cluster-backup/).

At this earlier inspection the upgrade was prepared only, and no production backup or isolated restore had been performed. The alternative consistent BSON backup route in section 1 remains subject to its writer-pause, durable-storage, and restore requirements.

### Historical payment prerequisite, now resolved

The owner subsequently approved Flex at the reviewed price and maintenance interruption. The backend was briefly suspended to stop application writes, but Atlas rejected the upgrade with **402 Payment Required** because the organization has no payment method. No cluster upgrade was applied. The existing backend was resumed on its unchanged production commit; Render reported the resumed deployment live, and its health endpoint again returned `healthy` with the database `connected`. Atlas still reported Free/M0 and `IDLE`.

The owner subsequently completed payment setup and the upgrade directly. The current verified state above supersedes this failed initial attempt. No additional payment setup or upgrade retry is needed.

## 8. Isolated real-Mongo launcher prepared

`backend/tests/rehearse_restored_app_recovery.py` prepares the missing real-database rehearsal without substituting the application's Motor client. It accepts only a loopback, standalone MongoDB 8 target and an explicitly rehearsal-prefixed database. It provides `inspect`, `exercise`, and same-origin compiled-frontend `serve` modes. It does not download, restore, drop, or export a database; source backup integrity and restoration must be established separately.

The launcher records private raw document/index/collection digests before app startup, uses the actual app and lifespan, captures final email delivery, replaces FCM, and idles the three processing workers. It compares identity and saved history before and after recovery while accounting for legitimate login XP, achievement, notification, and chat additions. Captures and operator details stay in private files. Its process audit guard permits only the selected local endpoints; a real operating-system sandbox remains a separate protection.

Preparation checks passed: Python compilation, **13 target/network refusal checks**, and **11 preview request-boundary checks**. A separate mocked-storage regression exercised the launcher with the real app for a synthetic member and administrator, including recovery, replacement login, administrator read authorization, and expected reward additions. It captured four emails and made zero external network attempts. This is explicitly mocked-storage evidence.

An official MongoDB 8.0.38 Debian binary was downloaded and its official SHA-256 verified for a synthetic-only local run. It aborts before startup because this execution environment lacks the CPU topology files the binary requires. No system mounts or executor restrictions were changed to work around that. **This local attempt started no real MongoDB process and completed no backup/restore or recovery rehearsal.** A separate compatible GitHub runner is used for the synthetic real-Mongo check; actual backup restoration remains separate.

The event release also passed the original eight-scenario synthetic ASGI recovery rehearsal again. After the publisher acknowledgement correction, the current full release tests are **226 backend tests** and **70 JavaScript model tests**, and the complete CRA production build passes. Those counts and captured exercises do not establish deployed recovery. See [practice-event-rollout.md](practice-event-rollout.md) for event-specific evidence and the remaining frontend verification boundary.

## 9. Completed recovery rehearsal on real MongoDB with synthetic accounts

[GitHub Actions run 45714470226](https://github.com/zenmillonario/ArgusAi-CashOut/actions/runs/45714470226) completed successfully on November 25, 2026 at **5:35 p.m. Eastern**, using commit `0fc675e32dc190284842fb1a2d72bb28454de279`. The actual application and its real Motor client ran against **MongoDB 8.0.38** on an isolated Ubuntu runner with wholly synthetic accounts. This resolves the incompatible local-runtime limitation for this synthetic exercise.

The workflow installs the required application dependency subset using the repository's version constraints, verifies the official Mongo binary's SHA-256, binds a standalone database only to loopback, and stops it afterward. It has read-only repository permissions, no production secrets, no Atlas connection, a ten-minute limit, and no artifact upload. Only the release branch's backend or workflow changes trigger it.

The passing run verifies:

- Recovery for a synthetic member and administrator through the actual app routes, followed by successful login and one-active-session enforcement.
- Preservation of their saved identities, access, profiles, and existing history, allowing the expected login streak, XP, date, and level changes.
- **Four captured messages, zero real emails, and zero forbidden external network attempts**. Continuous workers remain deliberately idle.
- **17 refusal checks and 11 preview request-boundary checks**. These are separate from the 226 backend unit tests.

The real run exposed a harness compatibility error: pinned PyMongo creates stream sockets with the close-on-exec flag, which the original guard rejected before connecting. The guard now accounts for that flag while retaining its destination, port, family, and protocol restrictions. UDP, raw, IPv6, external destinations, and unapproved ports remain rejected. The earlier workflow expression error was also corrected before this passing run. No production application behavior changed for these fixes.

**This is not a production-backup restore.** No member data was copied into the runner. The run does not prove Atlas backup integrity, restoration of the actual member database, browser reset-link completion, or live email/feed/push integration. The first completed Flex snapshot and the real-data comparisons in sections 1–5 remain required before the member-facing authentication release.
