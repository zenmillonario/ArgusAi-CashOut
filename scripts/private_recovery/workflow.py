"""Two deliberately unchained private tasks; neither accepts retained inputs.

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
                require(process.returncode == 0, "private_runner_failed")
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


if __name__ == "__main__":
    app.start()
