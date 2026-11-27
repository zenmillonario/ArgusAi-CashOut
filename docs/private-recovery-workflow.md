# CashOutAI private restored-member recovery rehearsal

## Status and purpose

**The private restored-member recovery rehearsal passed**, completing on November 26, 2026 at 10:33:21 p.m. Eastern (2026-11-27 03:33:21 UTC) on exact runtime revision `1d80519c6c9da861001005a20eccea1cbe7359f4` with `TMPDIR=/var/tmp`. It locally restored the operator-selected native Atlas snapshot, verified the logical copies and record preservation, completed recovery through the copied member and administrator API flows, and completed the selected copied member's compiled-browser journey. Recovery emails were captured locally; no real emails or external application connections were made.

The earlier [compiled-browser and MongoDB 8 check](https://github.com/zenmillonario/ArgusAi-CashOut/actions/runs/45922895554) at application revision `44783e1af968226519a1998605391c9d96d44f24` used synthetic accounts. The completed private rehearsal separately exercised existing copied identities and history.

The original temporary workflow was created with owner approval. Its hosted synthetic preflight passed on revision `6aa49eaed4e3cc17a5c8b5227246ecab9395928e`: MongoDB 8.0.38, two synthetic API accounts, the compiled browser journey, record preservation, six locally captured emails, zero sent emails, and zero external application connections. That preliminary run verified the synthetic application flow.

Two earlier restored-snapshot attempts stopped at storage guards:

| Attempt | Fixed refusal | Last completed stage |
| --- | --- | --- |
| Initial storage accounting | `INSUFFICIENT_PRIVATE_DISK` | Refused before DNS, snapshot download, extraction, MongoDB startup, or application execution |
| Staged storage accounting | `INSUFFICIENT_PRIVATE_EXPANSION_DISK` | Downloaded and scanned the bounded archive, then refused the measured expansion reserve before extraction, MongoDB startup, or application execution |

The three snapshot-specific environment variables were removed from the original workflow, and that workflow was deleted. Both [CI jobs passed](https://github.com/zenmillonario/ArgusAi-CashOut/actions/runs/45933198081) for the storage diagnostic at [revision `1d80519c6c9da861001005a20eccea1cbe7359f4`](https://github.com/zenmillonario/ArgusAi-CashOut/commit/1d80519c6c9da861001005a20eccea1cbe7359f4). The exact-image checks passed the storage task entry on distinct temporary filesystems, the synthetic native restore, and the synthetic application/browser preflight.

The hosted storage-only diagnostic passed in a separate temporary workflow in Virginia, without snapshot inputs or member data. The `default` and `tmp` candidates shared an XFS filesystem with a 2 GiB capacity. The writable `var_tmp` and `home` candidates used a different overlay filesystem with more than 117 GiB free at inspection time. The diagnostic reported zero network attempts, no snapshot access, and successful removal of its empty probe directories. This verifies filesystem metadata and directory writability, not restored-member recovery.

The chosen runtime setting is `TMPDIR=/var/tmp`, using the same temporary workflow. A hosted check after **Save only** still used the previous 2 GiB default: saving a variable did not update an already registered workflow version. After explicitly deploying the same reviewed revision with the new configuration, the hosted metadata check confirmed that `default` followed `var_tmp` on the overlay filesystem, with more than 99 GiB free; `tmp` remained a separate 2 GiB filesystem.

The hosted synthetic preflight then passed on exact revision `1d80519c6c9da861001005a20eccea1cbe7359f4` with `TMPDIR=/var/tmp`. It exercised both synthetic API roles and the compiled browser, preserved records, captured recovery emails locally, and reported zero sent emails and external application connections. Fresh snapshot delivery configuration was supplied privately and activated through a new deployment of the same reviewed revision before the successful restored-member run. Capacity observations apply to their individual task instances; the passing restored run also satisfied both storage guards.

The restored result reports `local_snapshot_restore: PASS`, `logical_copy_verified: true`, `record_preservation: PASS`, and `real_member_recovery_verified: true`, using MongoDB 8.0.38 with actual restored FCV 8.0. Its source identity remains `operator_selected_snapshot`, and its archive checksum was `computed_after_https_download`; no independent expected archive checksum was available in advance. The distinct `backup_restore_verified` and `production_deployment_verified` fields remain `false`.

**Final cleanup is confirmed.** The snapshot-specific environment variables were removed from the continuation workflow, and that workflow was deleted. Both disposable workflows are now deleted. At November 26, 2026, 10:35:21 p.m. Eastern (2026-11-27 03:35:21 UTC), the provider API returned no remaining workflow entries or further page cursor, and the Dashboard showed only the two original active production services. Temporary browser-held delivery links and clipboard contents were cleared. The source Atlas snapshot was retained. The application PR remains draft and unmerged, and both production services remain on `5702460a275cda067dba510dc4ba4432f1051359`.

The PR and private verification record track operational results and cleanup. No snapshot URL, receipt containing customer information, database archive, selected member identifier, credential, session, or captured recovery link belongs in this repository or in GitHub Actions.

Before deploying a revision, require the draft's private-image CI job to pass for that reviewed source revision. That job builds the exact Docker image, creates and reopens a synthetic native MongoDB archive, compares raw BSON and full collection/index settings, and exercises both the API and restored-browser entry points on generated identities. It also runs the actual SDK synthetic task locally. The storage diagnostic has separate privacy/cleanup checks and an actual task-entry check using distinct temporary filesystems. These runtime checks have external networking disabled; they do not register a Render workflow or handle existing-member data. The PR records the passing run and reviewed revision.

## Concrete deployment configuration

| Setting | Prepared value |
| --- | --- |
| Workflow name used | `cashoutai-private-storage-check` for the completed continuation; both temporary workflows were deleted |
| Render workspace | The owner's existing CashOutAI workspace |
| Region | Virginia |
| Repository | `https://github.com/zenmillonario/ArgusAi-CashOut` |
| Branch | `codex/cashoutai-square-launch-2026-11-25` |
| Revision | Pin the reviewed full commit recorded in the PR when creating the workflow |
| Nonsecret build setting | Set `CASHOUT_SOURCE_REVISION` to that same reviewed full commit SHA |
| Nonsecret runtime temporary directory | `TMPDIR=/var/tmp`; deploy a new workflow version, verify its effective default filesystem, then verify the hosted synthetic flow before the restored attempt |
| Runtime | Docker |
| Dockerfile | `scripts/private_recovery/Dockerfile` |
| Docker context | Repository root |
| Start command | `/app/scripts/private_recovery/start_workflow.sh` |
| Automatic deployment | Off |
| Production environment groups | None |
| Public application ports | None |
| Persistent disk | None |

Docker workflow creation is currently supported through **New → Workflow** in the Render Dashboard. The Docker creation path is not available through the current CLI/API or Blueprint interfaces. Creation registers task definitions; a separate **Run Task** action starts an execution. See [Render's current workflow tutorial](https://render.com/docs/workflows-tutorial#using-docker).

Render translates environment variables into Docker build arguments. The Dockerfile consumes only the nonsecret `CASHOUT_SOURCE_REVISION` argument and records it in the image revision label and rehearsal environment. Verify it matches the deployed commit before running any task; do not add snapshot material or credentials to Dockerfile arguments. See [Render's Docker environment-variable behavior](https://render.com/docs/docker#environment-variable-translation).

## Tasks and cost boundary

All three tasks accept no user arguments; start them with `[]`. They are separate executions and do not chain automatically. Snapshot delivery material is configured privately at runtime only for the restored task, rather than in retained task input.

| Task | Purpose | Compute | Timeout | Automatic retries |
| --- | --- | --- | --- | --- |
| `synthetic_preflight` | Verify MongoDB, the actual application, and the compiled browser inside this exact Render image | `2c-4g` | 1,800 seconds | 0 |
| `rehearse_restored_copy` | Import the selected native snapshot and exercise the selected copied accounts | `2c-4g` | 1,800 seconds | 0 |
| `inspect_private_storage` | Inspect filesystem capacity and directory writability without snapshot inputs, MongoDB, or the application | `2c-4g` | 30 seconds | 0 |

Render's published `2c-4g` workflow price is **$0.40 per hour**, prorated by the second. One full 30-minute attempt is therefore approximately **$0.20 in task compute**, and two full attempts would total approximately **$0.40**. The 30-second storage diagnostic has a task-compute ceiling of approximately **$0.0033**. Count actual executions against the owner's approved allowance; an early refusal still counts as an execution. These figures are not an all-inclusive invoice cap: build/pipeline usage, snapshot-download or transfer charges, and workflow state retention are separate. Starting another attempt adds another charge. See [current workflow pricing](https://render.com/docs/workflows-limits).

Each completed workflow execution is deprovisioned. The task definition itself does not require an always-running application server. The source Atlas snapshot is retained; this plan does not provision another M10.

## Private runtime configuration

The workflow SDK and application use separate Python environments: `/opt/cashout-workflow/bin/python` and `/opt/cashout-app/bin/python`. This keeps the workflow SDK's dependencies separate from the app's existing pins.

**Configuration changes require a deployed workflow version.** In the hosted checks, saving an environment change with **Save only** left already registered tasks on their prior environment. After changing `TMPDIR` or snapshot variables, explicitly deploy a new version of the same reviewed source revision and wait for its task registration to complete. Select that version for the next execution. Do not treat a successful environment save as evidence that a task will receive the new values. For `TMPDIR`, verify the effective location with the storage diagnostic before handling data.

Configure only these three snapshot-specific environment variables for the restored task:

| Variable | Value source |
| --- | --- |
| `CASHOUT_REHEARSAL_MODE` | Literal `atlas_native_snapshot_v1` |
| `CASHOUT_SNAPSHOT_URL` | Fresh secret Atlas snapshot delivery URL |
| `CASHOUT_SNAPSHOT_DECLARATION_JSON` | Private declaration assembled from the selected snapshot and download receipt |

The declaration uses schema `cashout_atlas_snapshot_v1` and records `project_id`, `source_cluster`, exactly one of `snapshot_id` or `snapshot_archive_name`, `snapshot_created_at`, `source_mongodb_version`, `source_fcv`, `source_database`, `download_created_at`, `download_expires_at`, and `download_host`. Supplying both identity keys, including a null placeholder, or neither is refused. The application database is `cashoutai`, the required FCV is `8.0`, and timestamps use UTC ISO format. The importer verifies the actual restored source FCV before copying data. The declaration also supplies bounded `archive_min_bytes`, `archive_max_bytes`, `expanded_max_bytes`, `member_limit`, and `document_limit`, plus the exact `expected_collections` and, when available from the verified snapshot evidence, `expected_document_counts`.

Use the exact provider-returned `snapshot_id` when available. When the Atlas download receipt exposes an archive filename instead, omit `snapshot_id` and copy that name verbatim into `snapshot_archive_name`; never invent an ID from it. This additive alternative retains schema v1. The filename must have the exact declared source-cluster prefix and the form `ClusterName-YYYY-MM-DDTHH-MM-SS.sssZ.tgz`, with a valid UTC calendar timestamp and exactly three fractional digits. Paths and other filename forms are refused. The final URL path component, percent-decoded exactly once as UTF-8, must equal this filename exactly. The host must still match the separately declared approved HTTPS provider host, and all other URL and network guards remain in force.

Keep the archive filename timestamp's provenance separate from the Dashboard's displayed snapshot completion time, recorded in `snapshot_created_at`; they need not be identical. Copy the provider-returned host exactly and do not recreate an expired URL. The download receipt must still describe a link valid for no more than one hour. No archive checksum has been assumed in advance. The importer records the received archive's checksum and separately verifies the logical copy. Both identity alternatives remain a private operator attestation of the selected source, reported as `source_identity: operator_selected_snapshot`, rather than independent cryptographic verification of provider identity.

Leave all snapshot material absent for `synthetic_preflight` and `inspect_private_storage`. Do not attach production environment groups, database connection strings, email credentials, Firebase credentials, or payment secrets. Remove snapshot configuration after the restored task reaches its terminal result.

Storage is checked in stages. Before download, require free space for the declared maximum archive plus a 64 MiB reserve; failure returns `INSUFFICIENT_PRIVATE_DISK`. After download, the bounded gzip/tar preflight measures the complete expansion without writing extracted files. Before extraction, require free space for four times that measured expansion plus the same reserve; failure returns `INSUFFICIENT_PRIVATE_EXPANSION_DISK`. The downloaded archive already occupies disk at the second check and is not counted twice. The declared archive and expansion limits still apply. A refusal at the second stage can consume the one-use delivery link even though no files have been extracted.

The storage diagnostic reports only the fixed labels `default`, `tmp`, `var_tmp`, and `home`, bounded filesystem byte/inode statistics, directory-writability booleans, and a fixed filesystem-type classification. Its `default` label measures the wrapper's actual selected temporary filesystem. Empty private probe directories are removed before a successful result, and cleanup failure prevents success. It has no snapshot configuration, database connection, application process, or network access. Its result can establish available storage at inspection time; it cannot establish a restored-member recovery pass.

## Execution sequence

1. Review and pin the exact prepared source revision. Create only the separate workflow described above. Verify all three task definitions have the declared compute, timeout, and zero-retry settings. After setting `TMPDIR=/var/tmp`, explicitly deploy a new version of that same reviewed revision and wait for registration.
2. Run `inspect_private_storage` on the newly registered version with no snapshot material configured. Confirm that `default` follows `var_tmp`, record the aggregate capacity result, and compare it with the guarded storage requirements. A result still showing the previous default means the configuration is not effective for that version; correct the deployment rather than lowering a guard.
3. Run `synthetic_preflight` with no snapshot material configured on the selected temporary filesystem when preparing an image for a restored attempt. Require a terminal hosted pass before handling restored member records. A source build, storage diagnostic, or task-registration success alone is insufficient.
4. In Atlas, select the retained snapshot whose prior native restore was verified. Record its actual identifier when available, completion time, source cluster, application database, and MongoDB major/minor version in the private receipt. If the UI does not expose an ID, use the actual download receipt's archive filename alternative described above. Confirm the selected source in the Dashboard before requesting its download.
5. Request a fresh native snapshot download and configure all three snapshot-specific variables privately, including the exact HTTPS delivery host and short-lived URL. Then explicitly deploy a new workflow version of the same reviewed revision and wait for registration; **Save only followed by Run Task is insufficient**. Atlas documents a one-time link that expires within one hour, so allow for deployment and registration within that window. If the link expires, obtain a fresh receipt and deploy the replacement configuration before running. Keep the URL out of commands, source, task inputs, logs, and report text. If the provider requires an access-list change, use the specific necessary client address; do not open broad network access.
6. Run `rehearse_restored_copy` once on the version registered with that fresh snapshot configuration. Do not invoke an older version with stale environment values. The importer bounds download/extraction size, refuses unsafe archive paths, records the downloaded archive's SHA-256, starts MongoDB only on loopback, and creates the rehearsal-prefixed logical copy. Its checksum identifies the received archive; unless an independently trusted expected checksum was supplied, it is not independent proof of the source bytes.
7. Verify copied document values, account selection, collection metadata, and index definitions before starting the application. The actual app uses the existing localhost-only restored-copy launcher; it receives no managed Atlas URI or snapshot download credential. The browser entry point is separate from the synthetic-only runner.
8. Require successful recovery for the selected copied member and administrator, preservation of the original identities/history, and the selected member's completed browser recovery/login/session journey. Email is captured locally, provider workers remain isolated, and output contains aggregate evidence only.
9. Retain the aggregate result and source revision. Remove the temporary delivery configuration and workflow after the private files/process cleanup has been confirmed. This cleanup also applies to a workflow used only for storage inspection. The remote source snapshot remains available for recovery.

## Evidence and release boundary

The result must distinguish source-snapshot selection, local copy verification, actual API recovery, browser completion, and preservation. A missing eligible copied member, missing administrator/session, incompatible storage version, download failure, or failed comparison is a refusal/failure, not permission to substitute a new synthetic identity or relax the existing launcher.

The native snapshot download contains raw data files. It must be opened using a compatible `mongod`; it is not a BSON dump accepted by `mongorestore`. MongoDB documents restoration across patch versions within the same major/minor version, subject to pinned FCV requirements. The prepared image uses the officially available, checksum-verified MongoDB 8.0.38 binary, matching the selected source's 8.0 major/minor line. See [MongoDB's local snapshot procedure](https://www.mongodb.com/docs/atlas/backup/cloud-backup/restore-from-local-file/).

A successful private rehearsal still does not establish live email delivery, device push, current Windows publisher feeds, phone/TV presentation under live traffic, or a coordinated frontend/backend/service-worker deployment. Those remain separate release checks. This workflow does not merge the app PR or deploy either existing production service.
