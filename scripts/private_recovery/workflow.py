"""Deliberately unchained private tasks; none accepts retained inputs.

Only a strict, aggregate result is returned to Render. Snapshot credentials live
in runtime environment variables, never task arguments, and are forwarded only
to the restored runner. Child output stays in temporary private files and is
discarded on both success and failure. This module does not deploy anything.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time

from render import Retry, TaskContext, Workflows


ROOT = Path(__file__).resolve().parents[2]
APP_PYTHON = Path("/opt/cashout-app/bin/python")
CHILD_TIMEOUT_SECONDS = 1700
MAX_STDOUT_BYTES = 65536
MAX_STDERR_BYTES = 16 * 1024 * 1024
MAX_FAILURE_BYTES = 1024
STORAGE_CHILD_TIMEOUT_SECONDS = 20
MAX_STORAGE_OUTPUT_BYTES = 8192
MAX_STORAGE_NUMBER = 2 ** 53 - 1
# This list is deliberately literal, independent of child output and receipt
# values. New importer reasons stay generic until separately reviewed here.
RESTORED_FAILURE_REASONS = frozenset({
    "EXPLICIT_RESTORED_MODE_REQUIRED",
    "REMOTE_DATABASE_CONFIGURATION_REFUSED",
    "PRODUCTION_CREDENTIAL_ENVIRONMENT_REFUSED",
    "SNAPSHOT_RECEIPT_REQUIRED",
    "INVALID_SNAPSHOT_RECEIPT",
    "INCOMPLETE_SNAPSHOT_RECEIPT",
    "EXACTLY_ONE_SNAPSHOT_IDENTITY_REQUIRED",
    "SOURCE_DECLARATION_REFUSED",
    "INVALID_PROJECT_DECLARATION",
    "INVALID_SNAPSHOT_IDENTITY",
    "INVALID_SNAPSHOT_ARCHIVE_NAME",
    "SNAPSHOT_ARCHIVE_URL_MISMATCH",
    "SOURCE_VERSION_REFUSED",
    "INVALID_RECEIPT_TIME",
    "RECEIPT_TIME_MUST_BE_UTC",
    "SNAPSHOT_DOWNLOAD_RECEIPT_EXPIRED",
    "INVALID_ARCHIVE_LIMITS",
    "INVALID_COLLECTION_DECLARATION",
    "INVALID_DOCUMENT_COUNT_DECLARATION",
    "INVALID_DOWNLOAD_URL",
    "DOWNLOAD_HOST_MISMATCH",
    "IP_LITERAL_DOWNLOAD_REFUSED",
    "DOWNLOAD_PROVIDER_REFUSED",
    "SNAPSHOT_HOST_LOOKUP_FAILED",
    "NONPUBLIC_DOWNLOAD_ADDRESS_REFUSED",
    "NETWORK_BOUNDARY_REFUSED",
    "PRIVATE_PARENT_DIRECTORY_REQUIRED",
    "PRIVATE_PARENT_DIRECTORY_REFUSED",
    "INSUFFICIENT_PRIVATE_DISK",
    "INSUFFICIENT_PRIVATE_EXPANSION_DISK",
    "SNAPSHOT_DOWNLOAD_HTTP_FAILED",
    "ENCODED_DOWNLOAD_REFUSED",
    "DOWNLOAD_LENGTH_REFUSED",
    "DOWNLOAD_TIME_LIMIT",
    "DOWNLOAD_SIZE_LIMIT",
    "DOWNLOAD_LENGTH_MISMATCH",
    "ARCHIVE_EXPANSION_LIMIT",
    "TRUNCATED_ARCHIVE",
    "ARCHIVE_TRAILER_REFUSED",
    "ARCHIVE_MEMBER_LIMIT",
    "ARCHIVE_SPECIAL_FILE_REFUSED",
    "ARCHIVE_MEMBER_SIZE_REFUSED",
    "ARCHIVE_EXTENSION_LIMIT",
    "ARCHIVE_SPARSE_REFUSED",
    "ARCHIVE_PATH_REFUSED",
    "ARCHIVE_DUPLICATE_PATH",
    "SINGLE_RAW_DATABASE_REQUIRED",
    "LOCAL_PORT_REFUSED",
    "MONGODB_BINARY_UNAVAILABLE",
    "MONGODB_START_FAILED",
    "LOCAL_MONGODB_VERSION_REFUSED",
    "SOURCE_FCV_REFUSED",
    "UNEXPECTED_LOCAL_MONGODB",
    "MONGODB_RUNTIME_MISMATCH",
    "INCOMPLETE_INDEX_REFUSED",
    "SOURCE_COLLECTIONS_MISMATCH",
    "SOURCE_DOCUMENT_LIMIT",
    "DUPLICATE_DOCUMENT_IDENTITY",
    "SOURCE_DOCUMENT_COUNTS_MISMATCH",
    "EMPTY_REHEARSAL_DATABASE_REQUIRED",
    "UNSUPPORTED_COLLECTION_TYPE",
    "RESTORED_COPY_COMPARISON_FAILED",
    "RESTORED_SOURCE_CHANGED",
    "ELIGIBLE_RESTORED_ACCOUNTS_UNAVAILABLE",
    "CHILD_OUTPUT_LIMIT",
    "CHILD_RESULT_UNAVAILABLE",
    "CHILD_REHEARSAL_FAILED",
    "CHILD_REHEARSAL_TIME_LIMIT",
    "API_RECOVERY_EVIDENCE_FAILED",
    "BROWSER_RECOVERY_EVIDENCE_FAILED",
    "CAPTURED_EMAIL_EVIDENCE_FAILED",
    "INVALID_AGGREGATE_INPUT",
    "PARENT_NETWORK_BOUNDARY_FAILED",
    "COMMAND_ARGUMENTS_REFUSED",
    "PRIVATE_REHEARSAL_INTERRUPTED",
    "PRIVATE_RUNTIME_FAILED",
})
SNAPSHOT_ENV = (
    "CASHOUT_REHEARSAL_MODE",
    "CASHOUT_SNAPSHOT_URL",
    "CASHOUT_SNAPSHOT_DECLARATION_JSON",
)

app = Workflows()


class PrivateTaskError(RuntimeError):
    """Only fixed, non-sensitive error codes cross the Workflow boundary."""


def require(condition, code):
    if not condition:
        raise PrivateTaskError(code)


def child_environment(mode, private_root):
    # Explicit allowlist prevents inherited provider/database/API credentials
    # from reaching the app or browser. No env file or env group is loaded.
    environment = {
        "PATH": "/opt/cashout-app/bin:/opt/mongodb/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "TZ": "UTC",
        "PYTHONUNBUFFERED": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PLAYWRIGHT_BROWSERS_PATH": "/opt/playwright",
        "TMPDIR": str(private_root),
    }
    if mode == "restored_snapshot":
        require(all(os.environ.get(name) for name in SNAPSHOT_ENV), "missing_snapshot_configuration")
        require(os.environ["CASHOUT_REHEARSAL_MODE"] == "atlas_native_snapshot_v1",
                "unexpected_snapshot_mode")
        environment.update({name: os.environ[name] for name in SNAPSHOT_ENV})
    else:
        require(mode == "synthetic_only", "unexpected_task_mode")
    return environment


def aggregate_result(value, mode):
    """Reject arbitrary keys/text so logs and retained state cannot carry PII."""
    constants = {
        "schema": "cashout_private_recovery_v1",
        "result": "PASS",
        "mode": mode,
        "mongo_version": "8.0.38",
        "source_fcv": "8.0",
        "accounts_exercised": 2,
        "browser_accounts_exercised": 1,
        "real_emails_sent": 0,
        "external_app_connections": 0,
        "record_preservation": "PASS",
        "backup_restore_verified": False,
        "real_member_recovery_verified": mode == "restored_snapshot",
        "production_deployment_verified": False,
    }
    counts = {"captured_emails"}
    extras = set()
    if mode == "restored_snapshot":
        constants.update({
            "source_identity": "operator_selected_snapshot",
            "archive_checksum": "computed_after_https_download",
            "local_snapshot_restore": "PASS",
            "logical_copy_verified": True,
        })
        counts.update({"source_documents", "source_collections"})
        extras.add("archive_sha256")
    require(type(value) is dict and set(value) == set(constants) | counts | extras,
            "unexpected_aggregate_shape")
    for key, expected in constants.items():
        require(type(value[key]) is type(expected) and value[key] == expected,
                "aggregate_invariant_failed")
    for key in counts:
        require(type(value[key]) is int and 0 <= value[key] <= 10_000_000,
                "invalid_aggregate_count")
    require(value["captured_emails"] >= 1, "email_capture_missing")
    if mode == "restored_snapshot":
        require(value["source_documents"] >= 2 and value["source_collections"] >= 1,
                "restored_source_missing")
        require(type(value["archive_sha256"]) is str
                and re.fullmatch(r"[0-9a-f]{64}", value["archive_sha256"]),
                "invalid_archive_digest")
    return value


def restored_failure_code(raw):
    """Expose only reviewed literals from a bounded, exact failure object."""
    generic = "private_runner_failed"
    if type(raw) is not bytes or len(raw) > MAX_FAILURE_BYTES:
        return generic

    def unique_keys(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate_failure_key")
            value[key] = item
        return value

    try:
        value = json.loads(raw, object_pairs_hook=unique_keys)
    except (ValueError, UnicodeError, RecursionError):
        return generic
    if type(value) is not dict or set(value) != {"schema", "result", "stage", "reason"}:
        return generic
    if (type(value["schema"]) is not str or value["schema"] != "cashout_private_recovery_v1"
            or type(value["result"]) is not str or value["result"] != "FAIL"
            or type(value["stage"]) is not str
            or value["stage"] not in {"configuration", "restored_rehearsal"}
            or type(value["reason"]) is not str
            or value["reason"] not in RESTORED_FAILURE_REASONS):
        return generic
    return f"private_runner_failed:{value['stage']}:{value['reason']}"


def stop_child(process):
    """Give the runner time to stop Mongo/preview and remove private state."""
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=40)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)


def run_private(mode):
    script = "run_synthetic_preflight.py" if mode == "synthetic_only" else "run_restored_recovery.py"
    require(mode in {"synthetic_only", "restored_snapshot"}, "unexpected_task_mode")
    require(APP_PYTHON.is_file() and (ROOT / "scripts/private_recovery" / script).is_file(),
            "private_runtime_missing")
    with tempfile.TemporaryDirectory(prefix="cashout_workflow_") as directory:
        private_root = Path(directory)
        os.chmod(private_root, 0o700)
        environment = child_environment(mode, private_root)
        with tempfile.TemporaryFile(dir=private_root) as output, tempfile.TemporaryFile(dir=private_root) as errors:
            process = subprocess.Popen(
                [str(APP_PYTHON), str(ROOT / "scripts/private_recovery" / script)],
                cwd=ROOT, env=environment, stdin=subprocess.DEVNULL,
                stdout=output, stderr=errors, start_new_session=True,
            )
            try:
                deadline = time.monotonic() + CHILD_TIMEOUT_SECONDS
                while process.poll() is None:
                    require(time.monotonic() < deadline, "private_runner_timeout")
                    require(os.fstat(output.fileno()).st_size <= MAX_STDOUT_BYTES
                            and os.fstat(errors.fileno()).st_size <= MAX_STDERR_BYTES,
                            "private_output_limit")
                    time.sleep(0.2)
                if process.returncode != 0:
                    code = "private_runner_failed"
                    if mode == "restored_snapshot":
                        output.seek(0)
                        code = restored_failure_code(output.read(MAX_FAILURE_BYTES + 1))
                    # Keep the task failed; never return failure data as success
                    # and never read or forward stderr or arbitrary child text.
                    raise PrivateTaskError(code) from None
                require(os.fstat(output.fileno()).st_size <= MAX_STDOUT_BYTES,
                        "private_output_limit")
                output.seek(0)
                try:
                    result = json.loads(output.read(MAX_STDOUT_BYTES + 1))
                except (ValueError, UnicodeError):
                    raise PrivateTaskError("private_result_unavailable") from None
                return aggregate_result(result, mode)
            finally:
                stop_child(process)


def safe_run(mode):
    try:
        return run_private(mode)
    except PrivateTaskError as error:
        # The fixed code is useful without forwarding child output or paths.
        raise PrivateTaskError(str(error)) from None
    except BaseException:
        raise PrivateTaskError("private_runtime_interrupted") from None


def storage_environment(private_root):
    # The actual parent-selected temporary filesystem is forwarded locally,
    # without inheriting any runtime credentials or retaining a path in output.
    return {"PATH": "/opt/cashout-app/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "TZ": "UTC",
            "PYTHONUNBUFFERED": "1", "PYTHONDONTWRITEBYTECODE": "1", "TMPDIR": str(private_root)}


def aggregate_storage_result(value):
    constants = {"schema": "cashout_private_storage_v1", "result": "PASS", "mode": "metadata_only",
                 "network_attempts": 0, "snapshot_data_accessed": False, "probe_cleanup_verified": True}
    require(type(value) is dict and set(value) == set(constants) | {"candidates"}, "invalid_storage_result")
    for key, expected in constants.items():
        require(type(value[key]) is type(expected) and value[key] == expected, "invalid_storage_result")
    rows = value["candidates"]
    labels = ("default", "tmp", "var_tmp", "home")
    numbers = {"total_bytes", "free_bytes", "total_inodes", "free_inodes"}
    booleans = {"available", "writable", "same_filesystem_as_default"}
    fields = {"label", "filesystem_type"} | numbers | booleans
    kinds = {"tmpfs", "overlay", "ext4", "xfs", "btrfs", "other", "unknown"}
    require(type(rows) is list and len(rows) == len(labels), "invalid_storage_result")
    for row, label in zip(rows, labels):
        require(type(row) is dict and set(row) == fields, "invalid_storage_result")
        require(type(row["label"]) is str and row["label"] == label
                and type(row["filesystem_type"]) is str and row["filesystem_type"] in kinds,
                "invalid_storage_result")
        require(all(type(row[key]) is bool for key in booleans), "invalid_storage_result")
        require(all(type(row[key]) is int and 0 <= row[key] <= MAX_STORAGE_NUMBER for key in numbers),
                "invalid_storage_result")
        require(row["free_bytes"] <= row["total_bytes"] and row["free_inodes"] <= row["total_inodes"],
                "invalid_storage_result")
        if row["available"]:
            require(row["total_bytes"] > 0, "invalid_storage_result")
        else:
            require(not row["writable"] and not row["same_filesystem_as_default"]
                    and row["filesystem_type"] == "unknown" and all(row[key] == 0 for key in numbers),
                    "invalid_storage_result")
    require(rows[0]["available"] and rows[0]["same_filesystem_as_default"], "invalid_storage_result")
    return value


def parse_storage_result(raw):
    require(type(raw) is bytes and len(raw) <= MAX_STORAGE_OUTPUT_BYTES, "invalid_storage_result")
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_storage_key")
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=unique_keys)
    except (ValueError, UnicodeError, RecursionError):
        raise PrivateTaskError("invalid_storage_result") from None
    return aggregate_storage_result(value)


def stop_storage_child(process):
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=2)
        except ProcessLookupError:
            return
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=2)


def run_storage_probe():
    script = ROOT / "scripts/private_recovery/inspect_private_storage.py"
    require(APP_PYTHON.is_file() and script.is_file(), "private_storage_runtime_missing")
    # Use the same default tempfile selection as the recovery wrapper. The
    # child measures this exact directory's filesystem, even if Render sets a
    # default other than /tmp. The path never becomes a retained task argument.
    with tempfile.TemporaryDirectory(prefix="cashout_workflow_storage_") as directory:
        private_root = Path(directory).resolve()
        os.chmod(private_root, 0o700)
        with tempfile.TemporaryFile(dir=private_root) as output, tempfile.TemporaryFile(dir=private_root) as errors:
            process = subprocess.Popen([str(APP_PYTHON), str(script)], cwd=ROOT,
                env=storage_environment(private_root), stdin=subprocess.DEVNULL,
                stdout=output, stderr=errors, start_new_session=True)
            try:
                try:
                    process.wait(timeout=STORAGE_CHILD_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired:
                    raise PrivateTaskError("private_storage_probe_timeout") from None
                require(process.returncode == 0, "private_storage_probe_failed")
                require(os.fstat(output.fileno()).st_size <= MAX_STORAGE_OUTPUT_BYTES
                        and os.fstat(errors.fileno()).st_size == 0, "private_storage_output_refused")
                output.seek(0)
                return parse_storage_result(output.read(MAX_STORAGE_OUTPUT_BYTES + 1))
            finally:
                stop_storage_child(process)


def safe_storage_probe():
    try:
        return run_storage_probe()
    except PrivateTaskError as error:
        raise PrivateTaskError(str(error)) from None
    except BaseException:
        raise PrivateTaskError("private_storage_probe_interrupted") from None


@app.task(name="synthetic_preflight", retry=Retry(max_retries=0, wait_duration_ms=1000),
          timeout_seconds=1800, plan="2c-4g")
def synthetic_preflight(ctx: TaskContext) -> dict:
    """Run actual MongoDB and compiled-browser checks with empty synthetic data."""
    return safe_run("synthetic_only")


@app.task(name="rehearse_restored_copy", retry=Retry(max_retries=0, wait_duration_ms=1000),
          timeout_seconds=1800, plan="2c-4g")
def rehearse_restored_copy(ctx: TaskContext) -> dict:
    """Use the runtime-only selected snapshot; do not chain or retry this task."""
    return safe_run("restored_snapshot")


@app.task(name="inspect_private_storage", retry=Retry(max_retries=0, wait_duration_ms=1000),
          timeout_seconds=30, plan="2c-4g")
def inspect_private_storage(ctx: TaskContext) -> dict:
    """Inspect fixed filesystem candidates without snapshot inputs or data."""
    return safe_storage_probe()


if __name__ == "__main__":
    app.start()
