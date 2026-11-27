"""Synthetic-only refusal, archive and output-boundary tests; no network."""
from copy import deepcopy
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_restored_recovery as runner

NOW = datetime(2026, 11, 27, 1, 0, tzinfo=timezone.utc)


def receipt():
    return {"schema": runner.SCHEMA, "project_id": "0" * 24, "source_cluster": "SyntheticCluster",
            "snapshot_id": "synthetic-snapshot", "snapshot_created_at": (NOW - timedelta(hours=2)).isoformat(),
            "source_mongodb_version": "8.0.39", "source_fcv": "8.0", "source_database": "cashoutai",
            "download_created_at": (NOW - timedelta(minutes=5)).isoformat(),
            "download_expires_at": (NOW + timedelta(minutes=50)).isoformat(),
            "download_host": "synthetic-bucket.s3.amazonaws.com", "archive_min_bytes": 1,
            "archive_max_bytes": 1024 * 1024, "expanded_max_bytes": 2 * 1024 * 1024,
            "member_limit": 100, "document_limit": 100, "expected_collections": ["users", "messages"]}


def environment(value=None, url=None):
    return {"CASHOUT_REHEARSAL_MODE": runner.MODE, "CASHOUT_SNAPSHOT_DECLARATION_JSON": json.dumps(value or receipt()),
            "CASHOUT_SNAPSHOT_URL": url or "https://synthetic-bucket.s3.amazonaws.com/fixture?signature=PRIVATE_SENTINEL"}


def archive_receipt():
    value = receipt()
    value.pop("snapshot_id")
    value["snapshot_archive_name"] = "SyntheticCluster-2026-11-26T22-58-00.123Z.tgz"
    return value


def archive_environment(value=None, component=None):
    value = archive_receipt() if value is None else value
    component = value["snapshot_archive_name"] if component is None else component
    return environment(value, "https://synthetic-bucket.s3.amazonaws.com/downloads/" + component
                       + "?signature=PRIVATE_SENTINEL")


def plan():
    return runner.Plan.from_environment(environment(), NOW)


def write_tar(path, additions=()):
    with tarfile.open(path, "w:gz") as archive:
        for name, payload in (("data/WiredTiger", b"synthetic marker"), ("data/WiredTiger.wt", b"synthetic table")):
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        for info, payload in additions:
            archive.addfile(info, io.BytesIO(payload) if payload is not None else None)


class FakeResponse:
    def __init__(self, body, headers=None, status=200):
        self.status_code = status
        self.headers = headers or {}
        stream = io.BytesIO(body)
        self.raw = SimpleNamespace(read=lambda size, decode_content=False: stream.read(size))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.response


class RestoredRecoveryTests(unittest.TestCase):
    def test_default_and_command_source_configuration_are_refused(self):
        for config in ({}, {**environment(), "MONGO_URL": "mongodb://production.invalid/cashoutai"},
                       {**environment(), "RESEND_API_KEY": "PRIVATE_SENTINEL"},
                       {**environment(), "UNRELATED": "mongodb+srv://private.invalid"}):
            with self.subTest(keys=sorted(config)):
                with self.assertRaises(runner.Refusal):
                    runner.Plan.from_environment(config, NOW)
        self.assertNotIn("PRIVATE_SENTINEL", repr(plan()))

    def test_receipt_requires_identity_limits_and_supported_version(self):
        changes = ({"source_database": "another_database"}, {"source_mongodb_version": "7.0.5"},
                   {"source_fcv": "7.0"}, {"archive_max_bytes": True}, {"archive_min_bytes": 100000000},
                   {"expanded_max_bytes": 100 * runner.GIB}, {"expected_collections": [{"bad": "shape"}]},
                   {"expected_document_counts": {"users": 2}}, {"unknown": "PRIVATE_SENTINEL"})
        for change in changes:
            with self.subTest(fields=list(change)):
                with self.assertRaises(runner.Refusal):
                    runner.Plan.from_environment(environment({**receipt(), **change}), NOW)
        missing = receipt()
        missing.pop("snapshot_id")
        with self.assertRaises(runner.Refusal):
            runner.Plan.from_environment(environment(missing), NOW)

    def test_expired_or_unbounded_download_receipt_is_refused(self):
        for change in ({"download_expires_at": NOW.isoformat()},
                       {"download_expires_at": (NOW + timedelta(hours=2)).isoformat()},
                       {"download_created_at": (NOW + timedelta(hours=1)).isoformat()},
                       {"snapshot_created_at": "2026-11-27T00:00:00"}):
            with self.subTest(fields=list(change)):
                with self.assertRaises(runner.Refusal):
                    runner.Plan.from_environment(environment({**receipt(), **change}), NOW)

    def test_archive_identity_accepts_exact_name_and_once_decoded_url_basename(self):
        value = archive_receipt()
        name = value["snapshot_archive_name"]
        for component in (name, name.replace("-", "%2D").replace(".", "%2E")):
            with self.subTest(encoded=component != name):
                result = runner.Plan.from_environment(archive_environment(value, component), NOW)
                self.assertEqual(result.receipt["snapshot_archive_name"], name)
                self.assertNotIn("snapshot_id", result.receipt)
                self.assertNotIn(name, repr(result))
                self.assertNotIn("PRIVATE_SENTINEL", repr(result))
        # Archive-name time and provider-displayed snapshot completion time have distinct provenance.
        self.assertEqual(value["snapshot_created_at"], (NOW - timedelta(hours=2)).isoformat())
        self.assertEqual(plan().receipt["snapshot_id"], "synthetic-snapshot")

    def test_snapshot_identity_requires_exactly_one_present_key(self):
        missing = receipt()
        missing.pop("snapshot_id")
        both = {**receipt(), "snapshot_archive_name": archive_receipt()["snapshot_archive_name"]}
        for value in (missing, both, {**both, "snapshot_id": None}, {**both, "snapshot_archive_name": None}):
            with self.subTest(keys=sorted(value)):
                with self.assertRaisesRegex(runner.Refusal, "^EXACTLY_ONE_SNAPSHOT_IDENTITY_REQUIRED$"):
                    runner.Plan.from_environment(environment(value), NOW)

    def test_archive_identity_rejects_unsafe_names_or_wrong_cluster(self):
        valid = archive_receipt()["snapshot_archive_name"]
        names = (None, 123, [], "", "../" + valid, "/" + valid, "nested/" + valid,
                 "..\\" + valid, valid + "/", valid + "\0", valid + "\n", " " + valid,
                 valid.replace("SyntheticCluster", "AnotherCluster"), valid.replace(".tgz", ".tar.gz"),
                 valid.replace(".tgz", ".TGZ"), valid.replace("-", "%2D"), valid + "?signature=x")
        for name in names:
            with self.subTest(name_type=type(name).__name__):
                with self.assertRaisesRegex(runner.Refusal, "^INVALID_SNAPSHOT_ARCHIVE_NAME$"):
                    runner.Plan.from_environment(archive_environment({**archive_receipt(), "snapshot_archive_name": name}, valid), NOW)
        for cluster in ("../SyntheticCluster", "SyntheticCluster/child", "SyntheticCluster\\child"):
            with self.assertRaisesRegex(runner.Refusal, "^INVALID_SNAPSHOT_IDENTITY$"):
                runner.Plan.from_environment(archive_environment({**archive_receipt(), "source_cluster": cluster}), NOW)

    def test_archive_identity_requires_valid_utc_millisecond_timestamp(self):
        for stamp in ("2026-02-30T22-58-00.123Z", "2026-13-26T22-58-00.123Z", "2026-11-26T24-58-00.123Z",
                      "2026-11-26T22-60-00.123Z", "2026-11-26T22-58-60.123Z", "2026-11-26T22-58-00Z",
                      "2026-11-26T22-58-00.1Z", "2026-11-26T22-58-00.123456Z", "2026-11-26T22:58:00.123Z",
                      "2026-11-26T22-58-00.123+00:00", "２０２６-11-26T22-58-00.123Z"):
            value = {**archive_receipt(), "snapshot_archive_name": "SyntheticCluster-" + stamp + ".tgz"}
            with self.subTest(timestamp_shape=stamp[-9:]):
                with self.assertRaisesRegex(runner.Refusal, "^INVALID_SNAPSHOT_ARCHIVE_NAME$"):
                    runner.Plan.from_environment(archive_environment(value), NOW)

    def test_archive_identity_requires_exact_decoded_final_url_component(self):
        value = archive_receipt()
        name = value["snapshot_archive_name"]
        for component in ("different.tgz", name.replace("123Z", "124Z"), name + "/", "?filename=" + name,
                          "..%2F" + name, "%2F" + name, "%5C" + name, name.replace("-", "%252D"),
                          name + "%00", name + "%FF", name + "%ZZ", name.replace(".", "+")):
            with self.subTest(component_length=len(component)):
                with self.assertRaisesRegex(runner.Refusal, "^SNAPSHOT_ARCHIVE_URL_MISMATCH$") as refusal:
                    runner.Plan.from_environment(archive_environment(value, component), NOW)
                self.assertNotIn(name, str(refusal.exception))
                self.assertNotIn("PRIVATE_SENTINEL", str(refusal.exception))

    def test_archive_identity_keeps_source_time_provider_and_environment_guards(self):
        for change in ({"source_mongodb_version": "7.0.5"}, {"source_fcv": "7.0"},
                       {"download_expires_at": (NOW + timedelta(hours=2)).isoformat()},
                       {"download_expires_at": NOW.isoformat()}, {"archive_max_bytes": True}):
            with self.subTest(fields=list(change)):
                with self.assertRaises(runner.Refusal):
                    runner.Plan.from_environment(archive_environment({**archive_receipt(), **change}), NOW)
        config = archive_environment()
        for change in ({"CASHOUT_SNAPSHOT_URL": config["CASHOUT_SNAPSHOT_URL"].replace("https:", "http:")},
                       {"CASHOUT_SNAPSHOT_URL": config["CASHOUT_SNAPSHOT_URL"].replace("synthetic-bucket", "other-bucket")},
                       {"MONGODB_URI": "mongodb+srv://production.invalid/cashoutai"}):
            with self.assertRaises(runner.Refusal):
                runner.Plan.from_environment({**config, **change}, NOW)

    def test_url_requires_exact_https_provider_host_without_credentials_or_ip(self):
        for url in ("http://synthetic-bucket.s3.amazonaws.com/a", "https://other.s3.amazonaws.com/a",
                    "https://user:secret@synthetic-bucket.s3.amazonaws.com/a",
                    "https://synthetic-bucket.s3.amazonaws.com:444/a", "https://synthetic-bucket.s3.amazonaws.com/a#x",
                    "https://synthetic-bucket.s3.amazonaws.com/a\n"):
            with self.subTest(url_type=url.split(":", 1)[0]):
                with self.assertRaises(runner.Refusal):
                    runner.Plan.from_environment(environment(url=url), NOW)
        for host in ("127.0.0.1", "example.com", "s3.amazonaws.com.attacker.example"):
            with self.subTest(host=host):
                with self.assertRaises(runner.Refusal):
                    runner.Plan.from_environment(environment({**receipt(), "download_host": host}, "https://" + host + "/a"), NOW)

    def test_snapshot_dns_must_resolve_only_public_addresses(self):
        for address in ("127.0.0.1", "10.0.0.1", "169.254.169.254", "::1"):
            with patch.object(runner.socket, "getaddrinfo", return_value=[(2, 1, 6, "", (address, 443))]):
                with self.assertRaises(runner.Refusal):
                    runner.resolve_public_addresses("synthetic-bucket.s3.amazonaws.com")

    def test_parent_network_boundary_switches_permanently_to_loopback(self):
        guard = runner.NetworkBoundary("synthetic-bucket.s3.amazonaws.com", {"8.8.8.8"})
        sock = SimpleNamespace(family=runner.socket.AF_INET)
        guard("socket.connect", (sock, ("8.8.8.8", 443)))
        for address in (("8.8.4.4", 443), ("127.0.0.1", 27217)):
            with self.assertRaises(runner.Refusal):
                guard("socket.connect", (sock, address))
        guard.local_only = True
        guard("socket.connect", (sock, ("127.0.0.1", runner.TARGET_PORT)))
        with self.assertRaises(runner.Refusal):
            guard("socket.connect", (sock, ("8.8.8.8", 443)))
        with self.assertRaises(runner.Refusal):
            guard("socket.getaddrinfo", ("production.invalid",))

    def test_download_is_exact_bounded_no_redirect_and_hash_recorded(self):
        body = b"synthetic archive bytes"
        session = FakeSession(FakeResponse(body, {"Content-Length": str(len(body))}))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "archive"
            digest = runner.download_archive(plan(), path, session, runner.time.monotonic() + 10)
            self.assertEqual(digest, hashlib.sha256(body).hexdigest())
            self.assertEqual(path.read_bytes(), body)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o400)
        self.assertFalse(session.calls[0][1]["allow_redirects"])
        self.assertEqual(session.calls[0][1]["headers"], {"Accept-Encoding": "identity"})

    def test_download_refuses_redirect_length_encoding_and_size_failures(self):
        responses = (FakeResponse(b"x", status=302), FakeResponse(b"xx", {"Content-Length": "1"}),
                     FakeResponse(b"x", {"Content-Encoding": "gzip"}),
                     FakeResponse(b"x" * (1024 * 1024 + 1)))
        for response in responses:
            with self.subTest(status=response.status_code), tempfile.TemporaryDirectory() as temporary:
                with self.assertRaises(runner.Refusal):
                    runner.download_archive(plan(), Path(temporary) / "archive", FakeSession(response), runner.time.monotonic() + 10)

    def test_safe_archive_extracts_regular_files_privately(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "fixture.tar.gz"
            write_tar(archive)
            dbpath = runner.extract_archive(archive, root / "raw", plan())
            self.assertEqual(dbpath, root / "raw/data")
            self.assertEqual((dbpath / "WiredTiger").read_bytes(), b"synthetic marker")
            self.assertEqual(stat.S_IMODE((dbpath / "WiredTiger").stat().st_mode), 0o600)

    def test_archive_refuses_path_traversal_and_duplicate_files(self):
        for name in ("../escape", "/absolute", "data/../../escape", "data\\escape", "C:/escape", "data/WiredTiger"):
            info = tarfile.TarInfo(name)
            info.size = 1
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                archive = root / "fixture.tar.gz"
                write_tar(archive, [(info, b"x")])
                with self.assertRaises(runner.Refusal):
                    runner.extract_archive(archive, root / "raw", plan())

    def test_archive_refuses_symlinks_hardlinks_devices_and_sparse_members(self):
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.FIFOTYPE, tarfile.GNUTYPE_SPARSE):
            info = tarfile.TarInfo("data/unsafe")
            info.type = kind
            info.linkname = "../../escape"
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                archive = root / "fixture.tar.gz"
                write_tar(archive, [(info, None)])
                with self.assertRaises(runner.Refusal):
                    runner.extract_archive(archive, root / "raw", plan())

    def test_archive_bounds_extension_headers_and_total_decompression(self):
        info = tarfile.TarInfo("pax-header")
        info.type = tarfile.XHDTYPE
        info.size = 65537
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "fixture.tar.gz"
            write_tar(archive, [(info, b"x" * info.size)])
            with self.assertRaises(runner.Refusal):
                runner.preflight_tar(archive, 2 * 1024 * 1024, 100)
            bomb = root / "bounded.gz"
            with gzip.open(bomb, "wb") as output:
                output.write(b"\0" * 20000)
            with self.assertRaises(runner.Refusal):
                runner.preflight_tar(bomb, 1024, 100)

    def test_missing_or_multiple_raw_database_roots_are_refused(self):
        info = tarfile.TarInfo("other/WiredTiger")
        info.size = 1
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "fixture.tar.gz"
            write_tar(archive, [(info, b"x")])
            with self.assertRaises(runner.Refusal):
                runner.extract_archive(archive, root / "raw", plan())

    def test_source_copy_fingerprint_distinguishes_bson_types_and_index_key_order(self):
        from bson import BSON, Int64, SON
        from bson.raw_bson import RawBSONDocument
        class Collection:
            def __init__(self, value):
                self.value = value
                self.keys = SON([("first", 1), ("second", -1)])
            def find(self, query):
                return iter([RawBSONDocument(BSON.encode({"_id": "synthetic", "value": self.value}))])
            def options(self):
                return {"validationLevel": "strict"}
            def list_indexes(self):
                return [{"name": "ordered", "key": self.keys, "v": 2, "unique": True}]
        collection = Collection(1)
        database = SimpleNamespace(list_collection_names=lambda: ["users", "messages"],
                                   get_collection=lambda *args, **kwargs: collection)
        class Database:
            def list_collection_names(self): return database.list_collection_names()
            def get_collection(self, *args, **kwargs): return collection
            def __getitem__(self, name): return collection
        baseline = runner.database_fingerprint(Database(), plan())
        collection.value = Int64(1)
        self.assertNotEqual(runner.database_fingerprint(Database(), plan()), baseline)
        collection.value = 1.25
        self.assertNotEqual(runner.database_fingerprint(Database(), plan()), baseline)
        collection.value = 1
        collection.keys = SON(reversed(list(collection.keys.items())))
        self.assertNotEqual(runner.database_fingerprint(Database(), plan()), baseline)

    def test_selection_requires_existing_approved_distinct_member_and_administrator(self):
        member = {"id": "synthetic-member", "status": "approved", "username": "member", "email": "member@example.test",
                  "active_session_id": "synthetic-session", "is_admin": False, "role": "member"}
        admin = {**member, "id": "synthetic-admin", "username": "admin", "email": "admin@example.test", "is_admin": True, "role": "admin"}
        documents = [member, admin]
        database = SimpleNamespace(users=SimpleNamespace(find=lambda *args: documents))
        self.assertEqual(runner.choose_accounts(database), {"member_id": member["id"], "admin_id": admin["id"]})
        for change in ({"password_hash": "existing-credential"}, {"active_session_id": ""}, {"email": admin["email"]}):
            documents[:] = [{**member, **change}, admin]
            with self.assertRaises(runner.Refusal):
                runner.choose_accounts(database)

    def test_selection_excludes_bot_system_and_flag_only_admins(self):
        member = {"id": "synthetic-member", "status": "approved", "username": "member", "email": "member@example.test",
                  "active_session_id": "synthetic-session", "is_admin": False, "role": "member"}
        admin = {**member, "id": "synthetic-admin", "username": "admin", "email": "admin@example.test", "is_admin": True, "role": "admin"}
        bot = {**admin, "id": "synthetic-bot", "username": "cashoutai_bot", "email": "bot@example.test", "role": "bot", "is_bot": True}
        documents = [bot, member, admin]
        database = SimpleNamespace(users=SimpleNamespace(find=lambda *args: documents))
        self.assertEqual(runner.choose_accounts(database)["admin_id"], admin["id"])
        for change in ({"is_bot": True}, {"is_system": True}, {"system_account": True}, {"role": "bot"},
                       {"account_type": "system"}, {"role": "member"}, {"role": None}, {"disabled": True}):
            with self.subTest(fields=list(change)):
                documents[:] = [bot, member, {**admin, **change}]
                with self.assertRaises(runner.Refusal):
                    runner.choose_accounts(database)

    def test_children_receive_no_snapshot_or_production_secrets(self):
        with patch.dict(os.environ, {**environment(), "RESEND_API_KEY": "PRIVATE_SENTINEL"}, clear=True):
            clean = runner.child_environment(Path("/private/synthetic"))
        self.assertFalse(set(clean) & runner.ENV_NAMES)
        self.assertNotIn("PRIVATE_SENTINEL", json.dumps(clean))
        self.assertNotIn("MONGO_URL", clean)

    def test_private_selection_file_is_not_world_readable(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "selection.json"
            runner.private_json(target, {"member_id": "synthetic-member", "admin_id": "synthetic-admin"})
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)

    def test_restored_material_requires_the_owned_private_parent_cleanup_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            self.assertEqual(runner.private_temp_parent({"TMPDIR": temporary}), path)
            link = path / "linked"
            link.symlink_to(path, target_is_directory=True)
            for environment in ({}, {"TMPDIR": "relative"}, {"TMPDIR": str(link)}):
                with self.assertRaises(runner.Refusal):
                    runner.private_temp_parent(environment)
            os.chmod(path, 0o755)
            with self.assertRaises(runner.Refusal):
                runner.private_temp_parent({"TMPDIR": temporary})
            os.chmod(path, 0o700)

    def test_aggregate_output_excludes_private_child_fields(self):
        api = {"result": "PASS", "storage": "real_local_MongoDB_8", "captured_emails": 4, "real_emails_sent": 0,
               "external_network_attempts": 0, "accounts": [{"account": name, "recovery": "PASS", "single_session": "PASS"}
                for name in ("member", "admin")], "private": "PRIVATE_SENTINEL"}
        browser = {"result": "PASS", "accounts_exercised": 1, "browser_reset_completed": True,
                   "captured_emails": 2, "real_emails_sent": 0, "external_app_connections": 0,
                   "record_preservation": "PASS", "private": "PRIVATE_SENTINEL"}
        result = runner.public_result("a" * 64, "8.0.38", {"users": {"count": 2}}, api, browser)
        self.assertNotIn("PRIVATE_SENTINEL", json.dumps(result))
        self.assertFalse(result["backup_restore_verified"])
        self.assertFalse(result["production_deployment_verified"])
        self.assertEqual(result["local_snapshot_restore"], "PASS")
        self.assertEqual(result["captured_emails"], 6)
        browser["external_app_connections"] = 1
        with self.assertRaises(runner.Refusal):
            runner.public_result("a" * 64, "8.0.38", {"users": {"count": 2}}, api, browser)

    def test_child_output_parse_refuses_logs_and_unsuccessful_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "child.json"
            target.write_text('{"private_state_directory":"PRIVATE_SENTINEL"}\n{"result":"PASS"}')
            self.assertEqual(runner.parse_child_result(target), {"result": "PASS"})
            for text in ('PRIVATE_SENTINEL\n{"result":"PASS"}', '{"result":"FAIL","detail":"PRIVATE_SENTINEL"}'):
                target.write_text(text)
                with self.assertRaises(runner.Refusal) as error:
                    runner.parse_child_result(target)
                self.assertNotIn("PRIVATE_SENTINEL", str(error.exception))

    def test_unexpected_exception_is_sanitized_and_temporary_files_are_removed(self):
        created = []
        def private_failure(selected_plan, root):
            created.append(root)
            (root / "private.txt").write_text("PRIVATE_SENTINEL")
            raise RuntimeError("https://private.invalid/?token=PRIVATE_SENTINEL")
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as parent, \
             patch.dict(os.environ, {**environment(), "TMPDIR": parent}, clear=True), patch.object(sys, "argv", ["runner"]), \
             patch.object(runner.Plan, "from_environment", return_value=plan()), \
             patch.object(runner, "execute", side_effect=private_failure), \
             patch.object(runner.signal, "signal"), patch.object(runner.signal, "alarm"), \
             patch.object(runner.os, "umask"), redirect_stdout(output):
            self.assertEqual(runner.main(), 1)
            self.assertEqual(created[0].parent, Path(parent))
        self.assertEqual(len(created), 1)
        self.assertFalse(created[0].exists())
        self.assertNotIn("PRIVATE_SENTINEL", output.getvalue())
        self.assertEqual(json.loads(output.getvalue())["reason"], "PRIVATE_RUNTIME_FAILED")


if __name__ == "__main__":
    unittest.main()
