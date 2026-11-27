"""Validate the built private runtime with wholly synthetic, disposable data.

No arguments or snapshot configuration are accepted. The exact app rehearsal
and compiled frontend run against a newly started standalone loopback MongoDB.
Only the aggregate schema accepted by workflow.py is printed; temporary logs,
reset links, account details and database files are removed in finally.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import signal
import socket
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[2]
MONGOD = Path("/opt/mongodb/bin/mongod")
MONGO_PORT = 27217
HTTP_PORT = 4185
PHASE = "configuration"


class PreflightError(RuntimeError):
    pass


def require(condition, code):
    if not condition:
        raise PreflightError(code)


def stop_process(process, timeout=30):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            raise PreflightError("child_cleanup_timeout")


def child_environment(private_root):
    return {
        "PATH": "/opt/cashout-app/bin:/opt/mongodb/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "TZ": "UTC",
        "PYTHONUNBUFFERED": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PLAYWRIGHT_BROWSERS_PATH": "/opt/playwright",
        "TMPDIR": str(private_root),
    }


def last_json_result(raw):
    # The established app rehearsal emits one metadata object followed by a
    # pretty-printed result; the browser emits one result. Parse both safely.
    text = raw.decode("utf-8")
    decoder = json.JSONDecoder()
    values = []
    while text.strip():
        value, offset = decoder.raw_decode(text.lstrip())
        values.append(value)
        require(len(values) <= 2, "unexpected_child_output")
        text = text.lstrip()[offset:]
    require(bool(values), "aggregate_output_missing")
    return values[-1]


def run_check(command, private_root, label, timeout):
    with tempfile.TemporaryFile(dir=private_root) as output, tempfile.TemporaryFile(dir=private_root) as errors:
        process = subprocess.Popen(command, cwd=ROOT, env=child_environment(private_root),
                                   stdin=subprocess.DEVNULL, stdout=output, stderr=errors)
        try:
            process.wait(timeout=timeout)
            require(process.returncode == 0, label + "_failed")
            require(os.fstat(output.fileno()).st_size < 65536, "aggregate_output_too_large")
            output.seek(0)
            result = last_json_result(output.read(65536))
            require(type(result) is dict and result.get("result") == "PASS", label + "_not_passed")
            require(result.get("real_emails_sent") == 0
                    and result.get("backup_restore_verified") is False,
                    "synthetic_evidence_boundary_failed")
            return result
        finally:
            stop_process(process)


def wait_mongo(process):
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure

    with MongoClient(f"mongodb://127.0.0.1:{MONGO_PORT}/?directConnection=true",
                     serverSelectionTimeoutMS=500, connectTimeoutMS=500) as client:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            require(process.poll() is None, "mongo_start_failed")
            try:
                hello = client.admin.command("hello")
                version = client.admin.command("buildInfo")["version"]
                pid = client.admin.command("serverStatus")["pid"]
                require(pid == process.pid, "unexpected_mongo_process")
                require(version == "8.0.38" and "setName" not in hello
                        and hello.get("msg") != "isdbgrid", "unexpected_mongo_runtime")
                require(set(client.list_database_names()) <= {"admin", "config", "local"},
                        "preflight_database_not_empty")
                fcv = client.admin.command({"getParameter": 1, "featureCompatibilityVersion": 1})
                require(fcv["featureCompatibilityVersion"] == {"version": "8.0"},
                        "unexpected_mongo_fcv")
                return
            except ConnectionFailure:
                time.sleep(0.1)
    raise PreflightError("mongo_start_timeout")


def run():
    global PHASE
    require(len(sys.argv) == 1, "preflight_arguments_forbidden")
    require(not any(name.startswith("CASHOUT_SNAPSHOT_") for name in os.environ),
            "snapshot_configuration_forbidden_in_preflight")
    require(platform.system() == "Linux" and platform.machine() == "x86_64",
            "linux_amd64_required")
    require(Path("/sys/devices/system/cpu/possible").is_file(), "supported_cpu_topology_required")
    require(MONGOD.is_file() and (ROOT / "frontend/build/index.html").is_file(),
            "built_runtime_missing")
    # Bind-probe before starting, then verify Mongo's PID to exclude another DB.
    for port in (MONGO_PORT, HTTP_PORT):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
    with tempfile.TemporaryDirectory(prefix="cashout_preflight_") as directory:
        private_root = Path(directory)
        os.chmod(private_root, 0o700)
        data = private_root / "db"
        data.mkdir(mode=0o700)
        process = None
        with tempfile.TemporaryFile(dir=private_root) as mongo_log:
            try:
                PHASE = "start_empty_mongo"
                process = subprocess.Popen([
                    str(MONGOD), "--dbpath", str(data), "--bind_ip", "127.0.0.1",
                    "--port", str(MONGO_PORT), "--nounixsocket",
                    "--wiredTigerCacheSizeGB", "0.25",
                    "--setParameter", "diagnosticDataCollectionEnabled=false",
                    "--setParameter", "ttlMonitorEnabled=false",
                ], cwd=ROOT, stdin=subprocess.DEVNULL, stdout=mongo_log, stderr=mongo_log,
                    env=child_environment(private_root))
                wait_mongo(process)
                PHASE = "synthetic_actual_app"
                app_result = run_check([
                    sys.executable, str(ROOT / "backend/tests/rehearse_restored_app_recovery.py"),
                    "--mode", "exercise", "--seed-synthetic",
                    "--database", "cashout_rehearsal_docker_preflight",
                    "--mongo-port", str(MONGO_PORT),
                ], private_root, "app_recovery", 300)
                require(len(app_result.get("accounts", [])) == 2
                        and app_result.get("external_network_attempts") == 0,
                        "app_recovery_invariant_failed")
                PHASE = "synthetic_compiled_browser"
                browser_result = run_check([
                    sys.executable, str(ROOT / "scripts/test_recovery_browser.py"),
                    "--frontend-build", str(ROOT / "frontend/build"),
                    "--mongo-port", str(MONGO_PORT), "--http-port", str(HTTP_PORT),
                ], private_root, "browser_recovery", 300)
                require(browser_result.get("record_preservation") == "PASS"
                        and browser_result.get("real_member_recovery_verified") is False
                        and browser_result.get("checks", {}).get("external_browser_requests_allowed") == 0,
                        "browser_recovery_invariant_failed")
                PHASE = "cleanup"
                stop_process(process)
                require(process.returncode == 0, "mongo_cleanup_failed")
                captured = app_result.get("captured_emails", 0) + browser_result.get("captured_emails", 0)
                require(type(captured) is int and 1 <= captured <= 100, "invalid_email_count")
                return {
                    "schema": "cashout_private_recovery_v1", "result": "PASS", "mode": "synthetic_only",
                    "mongo_version": "8.0.38", "source_fcv": "8.0", "accounts_exercised": 2,
                    "browser_accounts_exercised": 1, "captured_emails": captured,
                    "real_emails_sent": 0, "external_app_connections": 0, "record_preservation": "PASS",
                    "backup_restore_verified": False, "real_member_recovery_verified": False,
                    "production_deployment_verified": False,
                }
            finally:
                stop_process(process)


def main():
    os.umask(0o077)
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        result = run()
    except BaseException:
        # Never forward driver, browser, process, file, or environment details.
        print(json.dumps({"result": "FAIL", "mode": "synthetic_only", "phase": PHASE,
                          "reason": "private_synthetic_preflight_failed"}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
