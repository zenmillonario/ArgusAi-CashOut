"""Exercise native-file import/copy using only a freshly generated local fixture.

Run inside the built image with --network none. No URL, receipt, file path,
production credential or externally supplied data is accepted. The fixture is
created in an empty private directory and discarded after this check.
"""
from datetime import datetime, timedelta, timezone
import json
import hashlib
import logging
import os
from pathlib import Path
import signal
import sys
import tarfile
import tempfile

from bson import Binary, Decimal128, Int64, MaxKey, MinKey, ObjectId, Regex, Timestamp
import pymongo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_restored_recovery as runner


def synthetic_plan():
    now = datetime.now(timezone.utc)
    declaration = {
        "schema": runner.SCHEMA, "project_id": "0" * 24, "source_cluster": "SyntheticLocalFixture",
        "snapshot_id": "synthetic-local-fixture", "snapshot_created_at": (now - timedelta(minutes=2)).isoformat(),
        "source_mongodb_version": "8.0.38", "source_fcv": "8.0", "source_database": "cashoutai",
        "download_created_at": (now - timedelta(minutes=1)).isoformat(),
        "download_expires_at": (now + timedelta(minutes=50)).isoformat(),
        "download_host": "synthetic-only.s3.amazonaws.com", "archive_min_bytes": 1,
        "archive_max_bytes": 256 * runner.CHUNK, "expanded_max_bytes": 512 * runner.CHUNK,
        "member_limit": 10000, "document_limit": 100,
        "expected_collections": ["users", "messages", "typed_records"],
        "expected_document_counts": {"users": 2, "messages": 2, "typed_records": 2},
    }
    return runner.Plan.from_environment({"CASHOUT_REHEARSAL_MODE": runner.MODE,
        "CASHOUT_SNAPSHOT_URL": "https://synthetic-only.s3.amazonaws.com/NEVER_REQUESTED",
        "CASHOUT_SNAPSHOT_DECLARATION_JSON": json.dumps(declaration)}, now)


def seed_fixture(database):
    runner.require(not database.list_collection_names(), "SYNTHETIC_DATABASE_MUST_BE_EMPTY")
    database.create_collection("users", validator={"$jsonSchema": {"bsonType": "object", "required": ["id", "email"]}},
                               validationLevel="strict", validationAction="error")
    database.users.create_index("id", unique=True)
    database.users.create_index("email", name="member_email", unique=True, collation={"locale": "en", "strength": 2})
    now = datetime.now(timezone.utc)
    database.users.insert_many([
        {"_id": ObjectId(), "id": "synthetic-member", "username": "synthetic_member", "email": "member@example.test",
         "status": "approved", "is_admin": False, "role": "member", "active_session_id": "synthetic-member-session", "created_at": now},
        {"_id": ObjectId(), "id": "synthetic-admin", "username": "synthetic_admin", "email": "admin@example.test",
         "status": "approved", "is_admin": True, "role": "admin", "active_session_id": "synthetic-admin-session", "created_at": now,
         "password_hash": "synthetic-existing-credential"},
    ])
    database.users.update_many({}, {"$set": {
        "real_name": "Synthetic Recovery Account", "session_created_at": now, "is_online": True,
        "last_login_date": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
        "last_membership_check": now.strftime("%Y-%m-%d"), "experience_points": 321, "level": 3,
        "daily_login_streak": 2, "achievements": [], "followers": [], "following": [],
        "bio": "Synthetic profile to preserve", "membership_plan": "Lifetime Member",
    }})
    database.create_collection("messages", capped=True, size=1024 * 1024, max=100)
    database.messages.insert_many([
        {"_id": ObjectId(), "user_id": "synthetic-member", "content": "Synthetic preserved record",
         "created_at": datetime(2000, 1, 1, tzinfo=timezone.utc)},
        {"_id": ObjectId(), "user_id": "synthetic-admin", "content": "Synthetic preserved record",
         "created_at": datetime(2000, 1, 1, tzinfo=timezone.utc)},
    ])
    database.create_collection("typed_records", collation={"locale": "en", "strength": 2})
    database.typed_records.create_index([("group", 1), ("score", -1)], name="ordered_partial_unique", unique=True,
                                       partialFilterExpression={"enabled": True})
    database.typed_records.create_index("expires_at", name="old_records_retained", expireAfterSeconds=3600)
    database.typed_records.insert_many([
        {"_id": ObjectId(), "group": "alpha", "score": 1.25, "enabled": True, "long": Int64(1), "small": 1,
         "decimal": Decimal128("1.2300"), "binary": Binary(b"\x00\xff", subtype=128), "null": None,
         "timestamp": Timestamp(1700000000, 4), "regex": Regex("^synthetic$", "i"),
         "min": MinKey(), "max": MaxKey(), "when": now, "expires_at": datetime(2000, 1, 1, tzinfo=timezone.utc),
         "array": [1, Int64(1), "1", None, True],
         "nested": {"first": 1, "second": 2.75}},
        {"_id": "synthetic-string-id", "group": "beta", "score": 2.5, "enabled": False,
         "expires_at": datetime(2000, 1, 1, tzinfo=timezone.utc)},
    ])


def run(root, progress):
    progress["phase"] = "prepare_synthetic_fixture"
    plan = synthetic_plan()
    environment = runner.child_environment(root)
    (root / "tmp").mkdir(mode=0o700)
    seed_path = root / "seed"
    seed_path.mkdir(mode=0o700)
    # The source port is used again after extraction. Keep seed-process logs in
    # their own private directory; the production launcher's exclusive file
    # creation must continue to reject accidental log reuse.
    seed_runtime = root / "seed-runtime"
    seed_runtime.mkdir(mode=0o700)
    boundary = runner.NetworkBoundary("unused.invalid", set())
    boundary.local_only = True
    sys.addaudithook(boundary)
    progress["phase"] = "start_seed_mongodb"
    with runner.running_mongo(seed_path, runner.SOURCE_PORT, seed_runtime, environment) as (client, version):
        progress["phase"] = "seed_synthetic_records"
        seed_fixture(client.cashoutai)
        progress["phase"] = "fingerprint_synthetic_source"
        baseline = runner.database_fingerprint(client.cashoutai, plan)
        chosen = runner.choose_accounts(client.cashoutai)
        runner.require(chosen == {"member_id": "synthetic-member", "admin_id": "synthetic-admin"},
                       "SYNTHETIC_SELECTION_FAILED")
    archive = root / "synthetic-native.tar.gz"
    progress["phase"] = "capture_synthetic_raw_archive"
    # Source Mongo has shut down cleanly before capturing these raw data files.
    with tarfile.open(archive, "w:gz") as bundle:
        bundle.add(seed_path, arcname="synthetic-native")
    progress["phase"] = "extract_synthetic_raw_archive"
    restored_path = runner.extract_archive(archive, root / "restored", plan)
    target_path = root / "target"
    target_path.mkdir(mode=0o700)
    api_name = "cashout_rehearsal_synthetic_archive_api"
    browser_name = "cashout_rehearsal_synthetic_archive_browser"
    progress["phase"] = "start_clone_mongodb"
    with runner.running_mongo(target_path, runner.TARGET_PORT, root, environment) as (target, target_version):
        progress["phase"] = "start_restored_source_mongodb"
        with runner.running_mongo(restored_path, runner.SOURCE_PORT, root, environment) as (source, source_version):
            progress["phase"] = "verify_raw_restore"
            runner.require(source_version == version and runner.database_fingerprint(source.cashoutai, plan) == baseline,
                           "SYNTHETIC_RAW_RESTORE_MISMATCH")
            progress["phase"] = "clone_api_database"
            clone = runner.clone_database(source.cashoutai, target, api_name, baseline, plan)
            progress["phase"] = "clone_browser_database"
            runner.clone_database(source.cashoutai, target, browser_name, baseline, plan)
            progress["phase"] = "verify_clone_preservation"
            runner.require(target_version == version and runner.database_fingerprint(clone, plan) == baseline
                           and runner.choose_accounts(clone) == chosen, "SYNTHETIC_CLONE_MISMATCH")
            # Deliberately change only the clone. The immutable source baseline
            # must stay unchanged, and the comparison must notice the mutation.
            clone.typed_records.update_one({"group": "alpha"}, {"$set": {"score": 1.26}})
            runner.require(runner.database_fingerprint(clone, plan) != baseline
                           and runner.database_fingerprint(source.cashoutai, plan) == baseline,
                           "SYNTHETIC_MUTATION_DETECTION_FAILED")
            clone.typed_records.update_one({"group": "alpha"}, {"$set": {"score": 1.25}})
            runner.require(runner.database_fingerprint(clone, plan) == baseline, "SYNTHETIC_FIXTURE_RESTORE_FAILED")
        # The restored-source listener is stopped before either actual app
        # journey; the two children receive distinct, unchanged logical clones.
        runner.private_json(root / "selection.json", chosen)
        progress["phase"] = "exercise_actual_api_child"
        api = runner.run_child([sys.executable, str(runner.APP_ROOT / "backend/tests/rehearse_restored_app_recovery.py"),
            "--mode", "exercise", "--restored-copy", "--database", api_name, "--mongo-port", str(runner.TARGET_PORT),
            "--selection-file", str(root / "selection.json")], environment, root / "api-output.json", 300)
        progress["phase"] = "exercise_restored_browser_child"
        browser = runner.run_child([sys.executable, str(runner.APP_ROOT / "scripts/private_recovery/test_restored_browser.py"),
            "--frontend-build", str(runner.APP_ROOT / "frontend/build"), "--database", browser_name,
            "--selection-file", str(root / "selection.json"), "--mongo-port", str(runner.TARGET_PORT),
            "--http-port", str(runner.HTTP_PORT)], environment, root / "browser-output.json", 480)
        progress["phase"] = "verify_aggregate_contract"
        with archive.open("rb") as archived:
            digest = hashlib.file_digest(archived, "sha256").hexdigest()
        aggregate_contract = runner.public_result(digest, version, baseline, api, browser)
        runner.require(aggregate_contract["local_snapshot_restore"] == "PASS"
                       and aggregate_contract["logical_copy_verified"], "SYNTHETIC_RESULT_CONTRACT_FAILED")
    runner.require(boundary.denied == 0, "SYNTHETIC_NETWORK_BOUNDARY_FAILED")
    return {"schema": "cashout_synthetic_archive_integration_v1", "result": "PASS",
            "mode": "synthetic_archive_integration", "mongo_version": version,
            "synthetic_records": 6, "synthetic_collections": 3, "raw_restore": "PASS",
            "typed_bson_and_identity": "PASS", "collection_and_index_options": "PASS",
            "selected_account_eligibility": "PASS", "source_clone_fingerprints": "PASS",
            "clone_mutation_detected": "PASS", "source_preserved": "PASS",
            "actual_api_child": "PASS", "actual_restored_browser_child": "PASS", "restored_result_contract": "PASS",
            "captured_emails": api["captured_emails"] + browser["captured_emails"], "real_emails_sent": 0,
            "external_network_attempts": 0, "real_member_recovery_verified": False,
            "backup_restore_verified": False, "production_deployment_verified": False}


def main():
    progress = {"phase": "validate_synthetic_inputs"}
    try:
        runner.require(len(sys.argv) == 1 and not (runner.ENV_NAMES & os.environ.keys()), "SYNTHETIC_INPUTS_REFUSED")
        runner.require(not any("mongodb://" in value or "mongodb+srv://" in value for value in os.environ.values()),
                       "SYNTHETIC_DATABASE_INPUT_REFUSED")
        os.environ.clear()
        os.umask(0o077)
        logging.disable(logging.CRITICAL)
        def timeout(signum, frame):
            raise runner.Refusal("SYNTHETIC_ARCHIVE_TIME_LIMIT")
        signal.signal(signal.SIGALRM, timeout)
        signal.signal(signal.SIGTERM, timeout)
        signal.alarm(900)
        with tempfile.TemporaryDirectory(prefix="cashout_synthetic_archive_") as temporary:
            result = run(Path(temporary), progress)
        signal.alarm(0)
    except BaseException as error:
        # This inputless exercise contains generated fixtures only. Fixed stage,
        # exception class and numeric code make CI failures actionable without
        # publishing exception text, database records, child output or logs.
        known_types = {"Refusal", "FileExistsError", "FileNotFoundError", "PermissionError", "OSError",
                       "KeyError", "IndexError", "TypeError", "ValueError", "AssertionError", "OperationFailure",
                       "InvalidOperation", "ConnectionFailure", "ServerSelectionTimeoutError", "InvalidBSON",
                       "TimeoutExpired", "TimeoutError", "MemoryError"}
        error_type = type(error).__name__
        numeric_code = getattr(error, "code", getattr(error, "errno", None))
        result = {"schema": "cashout_synthetic_archive_integration_v1", "result": "FAIL",
                  "mode": "synthetic_archive_integration", "reason": str(error) if isinstance(error, runner.Refusal) else "SYNTHETIC_RUNTIME_FAILED",
                  "phase": progress["phase"], "error_type": error_type if error_type in known_types else "UnexpectedException",
                  "error_code": numeric_code if type(numeric_code) is int and 0 <= numeric_code <= 10**9 else None,
                  "real_member_recovery_verified": False}
        print(json.dumps(result, sort_keys=True), flush=True)
        return 1
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
