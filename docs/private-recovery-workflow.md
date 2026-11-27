# CashOutAI private restored-member recovery rehearsal

## Status and purpose

This is the prepared next step after the passing [compiled-browser and MongoDB 8 check](https://github.com/zenmillonario/ArgusAi-CashOut/actions/runs/45922895554) at application revision `44783e1af968226519a1998605391c9d96d44f24`. That check used synthetic accounts. This separate workflow is intended to exercise the same application against a local copy of the owner's selected Atlas snapshot, preserving existing member identities and history.

The workflow has not been created or run. Its actual Render registration, instance startup, and restored-member results remain unverified until those operations complete. No snapshot URL, receipt containing customer information, database archive, selected member identifier, credential, session, or captured recovery link belongs in this repository or in GitHub Actions.

Before creating it, require the draft's private-image CI job to pass for the reviewed source revision. That job builds the exact Docker image, creates and reopens a synthetic native MongoDB archive, compares raw BSON and full collection/index settings, and exercises both the API and restored-browser entry points on generated identities. It also runs the actual SDK synthetic task locally. Both containers have external networking disabled; neither registers a Render workflow or handles existing-member data. The PR records the passing run and reviewed revision.

## Concrete deployment configuration

| Setting | Prepared value |
| --- | --- |
| Workflow name | `cashoutai-private-recovery` |
| Render workspace | The owner's existing CashOutAI workspace |
| Region | Virginia |
| Repository | `https://github.com/zenmillonario/ArgusAi-CashOut` |
| Branch | `codex/cashoutai-square-launch-2026-11-25` |
| Revision | Pin the reviewed full commit recorded in the PR when creating the workflow |
| Nonsecret build setting | Set `CASHOUT_SOURCE_REVISION` to that same reviewed full commit SHA |
| Runtime | Docker |
| Dockerfile | `scripts/private_recovery/Dockerfile` |
| Docker context | Repository root |
| Start command | `/app/scripts/private_recovery/start_workflow.sh` |
| Automatic deployment | Off |
| Production environment groups | None |
| Public application ports | None |
| Persistent disk | None |

Docker workflow creation is currently supported through **New → Workflow** in the Render Dashboard. The Docker creation path is not available through the current CLI/API or Blueprint interfaces. Creation registers task definitions; a separate **Run Task** action starts an execution. See [Render's current workflow tutorial](https://render.com/docs/workflows-tutorial#using-docker).

Render translates environment variables into Docker build arguments. The Dockerfile consumes only the nonsecret `CASHOUT_SOURCE_REVISION` argument and records it in the image revision label and rehearsal environment. Verify it matches the deployed commit before running either task; do not add snapshot material or credentials to Dockerfile arguments. See [Render's Docker environment-variable behavior](https://render.com/docs/docker#environment-variable-translation).

## Tasks and cost boundary

Both tasks accept no user arguments; start them with `[]`. Snapshot delivery material is configured privately at runtime rather than in retained task input.

| Task | Purpose | Compute | Timeout | Automatic retries |
| --- | --- | --- | --- | --- |
| `synthetic_preflight` | Verify MongoDB, the actual application, and the compiled browser inside this exact Render image | `2c-4g` | 1,800 seconds | 0 |
| `rehearse_restored_copy` | Import the selected native snapshot and exercise the selected copied accounts | `2c-4g` | 1,800 seconds | 0 |

Render's published `2c-4g` workflow price is **$0.40 per hour**, prorated by the second. One 30-minute attempt is therefore approximately **$0.20 in task compute**; the two planned attempts total at most approximately **$0.40 in task compute**. This is not an all-inclusive invoice cap: build/pipeline usage, snapshot-download or transfer charges, and workflow state retention are separate. Starting another attempt adds another charge. See [current workflow pricing](https://render.com/docs/workflows-limits).

Each completed workflow execution is deprovisioned. The task definition itself does not require an always-running application server. The source Atlas snapshot is retained; this plan does not provision another M10.

## Private runtime configuration

The workflow SDK and application use separate Python environments: `/opt/cashout-workflow/bin/python` and `/opt/cashout-app/bin/python`. This keeps the workflow SDK's dependencies separate from the app's existing pins.

Configure only these three snapshot-specific environment variables for the restored task:

| Variable | Value source |
| --- | --- |
| `CASHOUT_REHEARSAL_MODE` | Literal `atlas_native_snapshot_v1` |
| `CASHOUT_SNAPSHOT_URL` | Fresh secret Atlas snapshot delivery URL |
| `CASHOUT_SNAPSHOT_DECLARATION_JSON` | Private declaration assembled from the selected snapshot and download receipt |

The declaration uses schema `cashout_atlas_snapshot_v1` and records `project_id`, `source_cluster`, `snapshot_id`, `snapshot_created_at`, `source_mongodb_version`, `source_fcv`, `source_database`, `download_created_at`, `download_expires_at`, and `download_host`. The application database is `cashoutai`, the FCV is `8.0`, and timestamps use UTC ISO format. It also supplies bounded `archive_min_bytes`, `archive_max_bytes`, `expanded_max_bytes`, `member_limit`, and `document_limit`, plus the exact `expected_collections` and, when available from the verified snapshot evidence, `expected_document_counts`.

Copy the provider-returned identifiers and host exactly; do not infer them from a filename or recreate an expired URL. No archive checksum has been assumed in advance. The importer records the received archive's checksum and separately verifies the logical copy. The declaration is a private operator attestation of the selected source, not a claim that the archive cryptographically embeds those provider identifiers.

Leave all snapshot material absent for `synthetic_preflight`. Do not attach production environment groups, database connection strings, email credentials, Firebase credentials, or payment secrets. Remove snapshot configuration after the restored task reaches its terminal result.

## Execution sequence

1. Review and pin the exact prepared source revision. Create only the separate workflow described above. Verify both task definitions have the declared compute, timeout, and zero-retry settings.
2. Run `synthetic_preflight` once with no snapshot material configured. Require a terminal pass before handling restored member records. A source build or task-registration success alone is insufficient.
3. In Atlas, select the retained snapshot whose prior native restore was verified. Record its actual identifier, completion time, source cluster, application database, and MongoDB major/minor version in the private receipt. Confirm the selected source in the Dashboard before requesting its download.
4. Request a fresh native snapshot download and configure its exact HTTPS delivery host and short-lived URL privately. Atlas documents a one-time link that expires within one hour. Generate it only when the workflow is ready. Keep the URL out of commands, source, task inputs, logs, and report text. If the provider requires an access-list change, use the specific necessary client address; do not open broad network access.
5. Run `rehearse_restored_copy` once. The importer bounds download/extraction size, refuses unsafe archive paths, records the downloaded archive's SHA-256, starts MongoDB only on loopback, and creates the rehearsal-prefixed logical copy. Its checksum identifies the received archive; unless an independently trusted expected checksum was supplied, it is not independent proof of the source bytes.
6. Verify copied document values, account selection, collection metadata, and index definitions before starting the application. The actual app uses the existing localhost-only restored-copy launcher; it receives no managed Atlas URI or snapshot download credential. The browser entry point is separate from the synthetic-only runner.
7. Require successful recovery for the selected copied member and administrator, preservation of the original identities/history, and the selected member's completed browser recovery/login/session journey. Email is captured locally, provider workers remain isolated, and output contains aggregate evidence only.
8. Retain the aggregate result and source revision. Remove the temporary delivery configuration and workflow after the private files/process cleanup has been confirmed. The remote source snapshot remains available for recovery.

## Evidence and release boundary

The result must distinguish source-snapshot selection, local copy verification, actual API recovery, browser completion, and preservation. A missing eligible copied member, missing administrator/session, incompatible storage version, download failure, or failed comparison is a refusal/failure, not permission to substitute a new synthetic identity or relax the existing launcher.

The native snapshot download contains raw data files. It must be opened using a compatible `mongod`; it is not a BSON dump accepted by `mongorestore`. MongoDB documents restoration across patch versions within the same major/minor version, subject to pinned FCV requirements. The prepared image uses the officially available, checksum-verified MongoDB 8.0.38 binary, matching the selected source's 8.0 major/minor line. See [MongoDB's local snapshot procedure](https://www.mongodb.com/docs/atlas/backup/cloud-backup/restore-from-local-file/).

A successful private rehearsal still does not establish live email delivery, device push, current Windows publisher feeds, phone/TV presentation under live traffic, or a coordinated frontend/backend/service-worker deployment. Those remain separate release checks. This workflow does not merge the app PR or deploy either existing production service.
