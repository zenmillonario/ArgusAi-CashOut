"""Private, one-shot rehearsal of an operator-selected native Atlas snapshot.

This file accepts no command-line arguments or MongoDB URI. Three explicitly
configured environment values identify the selected snapshot and its short-lived
HTTPS download. It never calls Atlas, changes an access list, or obtains a URL.
The retained result is aggregate-only; all data, logs and links are temporary.

Atlas documents Flex downloads as raw .tar.gz data files and supports restores
within the same major/minor release across patch versions:
https://www.mongodb.com/docs/atlas/backup/cloud-backup/restore-from-local-file/
The supplied receipt attests source selection. The computed archive SHA-256 is
an integrity record, not an independently pre-known source checksum.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import ipaddress
import json
import logging
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from urllib.parse import urlsplit


APP_ROOT = Path(__file__).resolve().parents[2]
MONGOD = Path("/opt/mongodb/bin/mongod")
SOURCE_PORT = 27216
TARGET_PORT = 27217
HTTP_PORT = 4185
MAX_SECONDS = 1500
CHUNK = 1024 * 1024
GIB = 1024 ** 3
MODE = "atlas_native_snapshot_v1"
SCHEMA = "cashout_atlas_snapshot_v1"
ENV_NAMES = frozenset({"CASHOUT_REHEARSAL_MODE", "CASHOUT_SNAPSHOT_URL", "CASHOUT_SNAPSHOT_DECLARATION_JSON"})
RECEIPT_FIELDS = frozenset({
    "schema", "project_id", "source_cluster", "snapshot_id", "snapshot_created_at",
    "source_mongodb_version", "source_fcv", "source_database", "download_created_at",
    "download_expires_at", "download_host", "archive_min_bytes", "archive_max_bytes",
    "expanded_max_bytes", "member_limit", "document_limit", "expected_collections",
})


class Refusal(Exception):
    """Only fixed public failure codes belong in this exception."""


def require(condition, code):
    if not condition:
        raise Refusal(code)


def instant(value):
    require(isinstance(value, str) and len(value) <= 40, "INVALID_RECEIPT_TIME")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        raise Refusal("INVALID_RECEIPT_TIME") from None
    require(parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0), "RECEIPT_TIME_MUST_BE_UTC")
    return parsed


def validate_download_url(url, expected_host):
    require(isinstance(url, str) and 0 < len(url) <= 16384, "INVALID_DOWNLOAD_URL")
    require(not any(ord(char) < 32 or ord(char) == 127 for char in url), "INVALID_DOWNLOAD_URL")
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        port = parsed.port
    except ValueError:
        raise Refusal("INVALID_DOWNLOAD_URL") from None
    require(parsed.scheme == "https" and port in (None, 443) and not parsed.username
            and not parsed.password and not parsed.fragment, "INVALID_DOWNLOAD_URL")
    require(isinstance(expected_host, str) and expected_host == expected_host.lower()
            and re.fullmatch(r"[a-z0-9]+(?:[a-z0-9.-]*[a-z0-9])?", expected_host)
            and host == expected_host and not host.endswith("."), "DOWNLOAD_HOST_MISMATCH")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise Refusal("IP_LITERAL_DOWNLOAD_REFUSED")
    suffixes = (".mongodb.com", ".mongodb.net", ".amazonaws.com", ".blob.core.windows.net", ".storage.googleapis.com")
    require(host == "storage.googleapis.com" or any(host.endswith(suffix) for suffix in suffixes),
            "DOWNLOAD_PROVIDER_REFUSED")
    return host


@dataclass(frozen=True)
class Plan:
    url: str = field(repr=False)
    receipt: dict = field(repr=False)

    @classmethod
    def from_environment(cls, environment, now=None):
        now = now or datetime.now(timezone.utc)
        require(environment.get("CASHOUT_REHEARSAL_MODE") == MODE, "EXPLICIT_RESTORED_MODE_REQUIRED")
        for key, value in environment.items():
            upper = key.upper()
            require(not any(uri in str(value).lower() for uri in ("mongodb://", "mongodb+srv://")),
                    "REMOTE_DATABASE_CONFIGURATION_REFUSED")
            require(upper not in {"MONGO_URL", "MONGODB_URI", "DATABASE_URL", "DB_NAME", "GOOGLE_APPLICATION_CREDENTIALS"}
                    and not upper.startswith(("RESEND_", "FCM_", "FIREBASE_", "SQUARE_", "KALSHI_", "AWS_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY")),
                    "PRODUCTION_CREDENTIAL_ENVIRONMENT_REFUSED")
        raw = environment.get("CASHOUT_SNAPSHOT_DECLARATION_JSON", "")
        require(isinstance(raw, str) and 0 < len(raw) <= 16384, "SNAPSHOT_RECEIPT_REQUIRED")
        try:
            receipt = json.loads(raw)
        except (TypeError, ValueError):
            raise Refusal("INVALID_SNAPSHOT_RECEIPT") from None
        require(isinstance(receipt, dict) and RECEIPT_FIELDS <= receipt.keys()
                and receipt.keys() <= RECEIPT_FIELDS | {"expected_document_counts"}, "INCOMPLETE_SNAPSHOT_RECEIPT")
        require(receipt["schema"] == SCHEMA and receipt["source_database"] == "cashoutai"
                and receipt["source_fcv"] == "8.0", "SOURCE_DECLARATION_REFUSED")
        require(isinstance(receipt["project_id"], str) and re.fullmatch(r"[0-9a-f]{24}", receipt["project_id"]),
                "INVALID_PROJECT_DECLARATION")
        for key in ("source_cluster", "snapshot_id"):
            require(isinstance(receipt[key], str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{1,127}", receipt[key]),
                    "INVALID_SNAPSHOT_IDENTITY")
        require(isinstance(receipt["source_mongodb_version"], str)
                and re.fullmatch(r"8\.0\.[0-9]+(?:-patch-[A-Za-z0-9]+)?", receipt["source_mongodb_version"]),
                "SOURCE_VERSION_REFUSED")
        snapshot_at = instant(receipt["snapshot_created_at"])
        issued_at = instant(receipt["download_created_at"])
        expires_at = instant(receipt["download_expires_at"])
        require(snapshot_at <= issued_at <= now + timedelta(minutes=5)
                and issued_at < expires_at <= issued_at + timedelta(hours=1)
                and expires_at > now + timedelta(seconds=60), "SNAPSHOT_DOWNLOAD_RECEIPT_EXPIRED")
        limits = {"archive_min_bytes": (1, 8 * GIB), "archive_max_bytes": (1, 8 * GIB),
                  "expanded_max_bytes": (512, 16 * GIB), "member_limit": (1, 100000),
                  "document_limit": (1, 1000000)}
        for key, (minimum, maximum) in limits.items():
            require(type(receipt[key]) is int and minimum <= receipt[key] <= maximum, "INVALID_ARCHIVE_LIMITS")
        require(receipt["archive_min_bytes"] <= receipt["archive_max_bytes"], "INVALID_ARCHIVE_LIMITS")
        names = receipt["expected_collections"]
        require(isinstance(names, list) and 1 <= len(names) <= 100
                and all(isinstance(name, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,99}", name) for name in names)
                and len(names) == len(set(names))
                and "users" in names, "INVALID_COLLECTION_DECLARATION")
        if "expected_document_counts" in receipt:
            counts = receipt["expected_document_counts"]
            require(isinstance(counts, dict) and set(counts) == set(names)
                    and all(type(count) is int and 0 <= count <= receipt["document_limit"] for count in counts.values())
                    and sum(counts.values()) <= receipt["document_limit"], "INVALID_DOCUMENT_COUNT_DECLARATION")
        url = environment.get("CASHOUT_SNAPSHOT_URL", "")
        validate_download_url(url, receipt["download_host"])
        return cls(url, receipt)


class NetworkBoundary:
    """Parent-process network allowlist; child app uses its existing guard."""
    def __init__(self, host, addresses):
        self.host = host
        self.addresses = frozenset(addresses)
        self.local_only = False
        self.denied = 0

    def __call__(self, event, args):
        deny = False
        if event in {"socket.getaddrinfo", "socket.gethostbyname"}:
            deny = args[0] != ("127.0.0.1" if self.local_only else self.host)
        elif event in {"socket.gethostbyaddr", "socket.getnameinfo", "socket.sendto", "socket.sendmsg"}:
            deny = True
        elif event in {"socket.connect", "socket.bind"}:
            sock, address = args[:2]
            if sock.family != socket.AF_UNIX:
                if self.local_only:
                    deny = not (isinstance(address, tuple) and address[0] == "127.0.0.1"
                                and address[1] in {SOURCE_PORT, TARGET_PORT})
                else:
                    deny = event == "socket.bind" or not (isinstance(address, tuple)
                        and address[0] in self.addresses and address[1] == 443)
        if deny:
            self.denied += 1
            raise Refusal("NETWORK_BOUNDARY_REFUSED")


def resolve_public_addresses(host):
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    except OSError:
        raise Refusal("SNAPSHOT_HOST_LOOKUP_FAILED") from None
    require(addresses and all(ipaddress.ip_address(address).is_global for address in addresses),
            "NONPUBLIC_DOWNLOAD_ADDRESS_REFUSED")
    return addresses


def download_archive(plan, path, session, deadline):
    minimum = plan.receipt["archive_min_bytes"]
    maximum = plan.receipt["archive_max_bytes"]
    digest = hashlib.sha256()
    size = 0
    with session.get(plan.url, stream=True, allow_redirects=False, timeout=(15, 30),
                     headers={"Accept-Encoding": "identity"}) as response:
        require(response.status_code == 200, "SNAPSHOT_DOWNLOAD_HTTP_FAILED")
        require(response.headers.get("Content-Encoding", "identity").lower() in {"", "identity"},
                "ENCODED_DOWNLOAD_REFUSED")
        announced = response.headers.get("Content-Length")
        if announced is not None:
            require(announced.isdigit() and minimum <= int(announced) <= maximum, "DOWNLOAD_LENGTH_REFUSED")
        with path.open("xb") as output:
            os.chmod(path, 0o600)
            while True:
                require(time.monotonic() < deadline, "DOWNLOAD_TIME_LIMIT")
                chunk = response.raw.read(CHUNK, decode_content=False)
                if not chunk:
                    break
                size += len(chunk)
                require(size <= maximum, "DOWNLOAD_SIZE_LIMIT")
                digest.update(chunk)
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
    require(minimum <= size <= maximum and (announced is None or size == int(announced)), "DOWNLOAD_LENGTH_MISMATCH")
    os.chmod(path, 0o400)
    return digest.hexdigest()


def preflight_tar(archive, maximum, member_limit):
    """Bound gzip expansion and tar extension headers before tarfile parses them."""
    consumed = 0
    members = 0
    with gzip.open(archive, "rb") as stream:
        while True:
            header = stream.read(512)
            consumed += len(header)
            require(consumed <= maximum, "ARCHIVE_EXPANSION_LIMIT")
            if not header:
                break
            require(len(header) == 512, "TRUNCATED_ARCHIVE")
            if header == b"\0" * 512:
                while True:
                    padding = stream.read(CHUNK)
                    if not padding:
                        return
                    consumed += len(padding)
                    require(consumed <= maximum and not padding.strip(b"\0"), "ARCHIVE_TRAILER_REFUSED")
            info = tarfile.TarInfo.frombuf(header, "utf-8", "surrogateescape")
            members += 1
            require(members <= member_limit, "ARCHIVE_MEMBER_LIMIT")
            extension = info.type in {tarfile.XHDTYPE, tarfile.XGLTYPE, tarfile.GNUTYPE_LONGNAME}
            require(extension or info.isfile() or info.isdir(), "ARCHIVE_SPECIAL_FILE_REFUSED")
            require(not info.issparse() and 0 <= info.size <= maximum, "ARCHIVE_MEMBER_SIZE_REFUSED")
            require(not extension or info.size <= 65536, "ARCHIVE_EXTENSION_LIMIT")
            remaining = ((info.size + 511) // 512) * 512
            require(consumed + remaining <= maximum, "ARCHIVE_EXPANSION_LIMIT")
            extension_data = bytearray()
            while remaining:
                part = stream.read(min(CHUNK, remaining))
                require(part, "TRUNCATED_ARCHIVE")
                remaining -= len(part)
                consumed += len(part)
                if extension:
                    extension_data.extend(part)
            require(not extension or b"GNU.sparse" not in extension_data, "ARCHIVE_SPARSE_REFUSED")


def safe_member_path(root, name):
    require(isinstance(name, str) and 0 < len(name) <= 4096 and not name.startswith("/")
            and "\\" not in name and "\0" not in name and ":" not in name, "ARCHIVE_PATH_REFUSED")
    relative = PurePosixPath(name)
    require(".." not in relative.parts and not relative.is_absolute(), "ARCHIVE_PATH_REFUSED")
    destination = root.joinpath(*relative.parts)
    require(destination.resolve().is_relative_to(root.resolve()), "ARCHIVE_PATH_REFUSED")
    return destination


def extract_archive(archive, root, plan):
    maximum = plan.receipt["expanded_max_bytes"]
    preflight_tar(archive, maximum, plan.receipt["member_limit"])
    root.mkdir(mode=0o700)
    files = set()
    size = 0
    with tarfile.open(archive, mode="r|gz") as bundle:
        for number, info in enumerate(bundle, 1):
            require(number <= plan.receipt["member_limit"], "ARCHIVE_MEMBER_LIMIT")
            require((info.isfile() or info.isdir()) and not info.issparse(), "ARCHIVE_SPECIAL_FILE_REFUSED")
            path = safe_member_path(root, info.name)
            if info.isdir():
                require(not path.exists() or path.is_dir(), "ARCHIVE_DUPLICATE_PATH")
                path.mkdir(parents=True, exist_ok=True, mode=0o700)
                continue
            require(path != root, "ARCHIVE_PATH_REFUSED")
            size += info.size
            require(info.size >= 0 and size <= maximum and path not in files, "ARCHIVE_EXPANSION_LIMIT")
            files.add(path)
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
            with os.fdopen(descriptor, "wb") as output, bundle.extractfile(info) as content:
                remaining = info.size
                while remaining:
                    chunk = content.read(min(CHUNK, remaining))
                    require(chunk, "TRUNCATED_ARCHIVE")
                    output.write(chunk)
                    remaining -= len(chunk)
    candidates = [path.parent for path in root.rglob("WiredTiger") if path.is_file()]
    require(len(candidates) == 1 and (candidates[0] / "WiredTiger.wt").is_file(), "SINGLE_RAW_DATABASE_REQUIRED")
    return candidates[0]


def private_json(path, value):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(value, output, sort_keys=True)


def child_environment(root):
    return {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1", "TMPDIR": str(root / "tmp"),
            "PLAYWRIGHT_BROWSERS_PATH": "/opt/playwright", "PYTHON_DOTENV_DISABLED": "1"}


def private_temp_parent(environment):
    """Keep all restored material inside the workflow wrapper's cleanup root."""
    raw = environment.get("TMPDIR")
    require(isinstance(raw, str) and raw, "PRIVATE_PARENT_DIRECTORY_REQUIRED")
    path = Path(raw)
    require(path.is_absolute() and path.resolve() == path and not path.is_symlink(),
            "PRIVATE_PARENT_DIRECTORY_REFUSED")
    info = path.stat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077,
            "PRIVATE_PARENT_DIRECTORY_REFUSED")
    return path


def stop_process(process):
    if process is None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


def local_client(port):
    require(port in {SOURCE_PORT, TARGET_PORT}, "LOCAL_PORT_REFUSED")
    from pymongo import MongoClient
    return MongoClient(f"mongodb://127.0.0.1:{port}/?directConnection=true", serverSelectionTimeoutMS=2000,
                       connectTimeoutMS=2000, socketTimeoutMS=30000)


@contextmanager
def running_mongo(dbpath, port, root, environment):
    require(MONGOD.is_file(), "MONGODB_BINARY_UNAVAILABLE")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", port))
    command = [str(MONGOD), "--dbpath", str(dbpath), "--bind_ip", "127.0.0.1", "--port", str(port),
               "--nounixsocket", "--wiredTigerCacheSizeGB", "0.25", "--setParameter", "diagnosticDataCollectionEnabled=false",
               "--setParameter", "ttlMonitorEnabled=false", "--logpath", str(root / f"mongo-{port}.log")]
    process = None
    client = None
    with (root / f"mongo-{port}-stderr.log").open("xb") as output:
        try:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                                       env=environment, start_new_session=True)
            client = local_client(port)
            until = time.monotonic() + 90
            while True:
                require(process.poll() is None and time.monotonic() < until, "MONGODB_START_FAILED")
                try:
                    client.admin.command("ping")
                    break
                except Exception:
                    time.sleep(0.2)
            hello = client.admin.command("hello")
            build = client.admin.command("buildInfo")
            require(re.fullmatch(r"8\.0\.[0-9]+(?:[-+].*)?", build.get("version", ""))
                    and not hello.get("setName") and hello.get("msg") != "isdbgrid"
                    and hello.get("isWritablePrimary", hello.get("ismaster", False)), "LOCAL_MONGODB_VERSION_REFUSED")
            fcv = client.admin.command({"getParameter": 1, "featureCompatibilityVersion": 1})["featureCompatibilityVersion"]
            require(fcv == {"version": "8.0"}, "SOURCE_FCV_REFUSED")
            parsed = client.admin.command("getCmdLineOpts")["parsed"]
            require(Path(parsed["storage"]["dbPath"]).resolve() == dbpath.resolve()
                    and parsed["net"]["bindIp"] == "127.0.0.1" and parsed["net"]["port"] == port,
                    "UNEXPECTED_LOCAL_MONGODB")
            require(client.admin.command("serverStatus")["pid"] == process.pid, "UNEXPECTED_LOCAL_MONGODB")
            yield client, build["version"]
        finally:
            if client is not None:
                client.close()
            stop_process(process)


def metadata_digest(value):
    from bson import json_util
    return hashlib.sha256(json_util.dumps(value, json_options=json_util.CANONICAL_JSON_OPTIONS,
                                         sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def normalized_indexes(collection):
    result = []
    for index in collection.list_indexes():
        require("buildUUID" not in index, "INCOMPLETE_INDEX_REFUSED")
        item = {key: value for key, value in index.items() if key not in {"ns", "key"}}
        item["key"] = list(index["key"].items())
        result.append(item)
    return sorted(result, key=lambda item: item["name"])


def raw_collection(database, name):
    from bson.codec_options import CodecOptions
    from bson.raw_bson import RawBSONDocument
    return database.get_collection(name, codec_options=CodecOptions(document_class=RawBSONDocument))


def database_fingerprint(database, plan):
    from bson import BSON
    names = sorted(database.list_collection_names())
    require(names == sorted(plan.receipt["expected_collections"]), "SOURCE_COLLECTIONS_MISMATCH")
    result = {}
    total = 0
    expected = plan.receipt.get("expected_document_counts")
    for name in names:
        documents = {}
        for document in raw_collection(database, name).find({}):
            total += 1
            require(total <= plan.receipt["document_limit"], "SOURCE_DOCUMENT_LIMIT")
            key = hashlib.sha256(BSON.encode({"_id": document["_id"]})).hexdigest()
            require(key not in documents, "DUPLICATE_DOCUMENT_IDENTITY")
            documents[key] = hashlib.sha256(document.raw).hexdigest()
        require(expected is None or expected[name] == len(documents), "SOURCE_DOCUMENT_COUNTS_MISMATCH")
        result[name] = {"documents": documents, "count": len(documents),
                        "options": metadata_digest(database[name].options()),
                        "indexes": metadata_digest(normalized_indexes(database[name]))}
    return result


def clone_database(source, target_client, name, baseline, plan):
    from pymongo import IndexModel
    require(re.fullmatch(r"cashout_rehearsal_[a-z0-9_]{4,48}", name)
            and name not in target_client.list_database_names(), "EMPTY_REHEARSAL_DATABASE_REQUIRED")
    destination = target_client[name]
    for info in source.list_collections():
        require(info.get("type") == "collection" and not {"timeseries", "encryptedFields"} & info.get("options", {}).keys(),
                "UNSUPPORTED_COLLECTION_TYPE")
        collection_name = info["name"]
        destination.create_collection(collection_name, **info.get("options", {}))
        batch = []
        batch_size = 0
        for document in raw_collection(source, collection_name).find({}):
            batch.append(document)
            batch_size += len(document.raw)
            if len(batch) >= 100 or batch_size >= 2 * CHUNK:
                destination[collection_name].insert_many(batch, ordered=True, bypass_document_validation=True)
                batch, batch_size = [], 0
        if batch:
            destination[collection_name].insert_many(batch, ordered=True, bypass_document_validation=True)
        for index in source[collection_name].list_indexes():
            if index["name"] == "_id_":
                continue
            options = {key: value for key, value in index.items() if key not in {"key", "ns"}}
            destination[collection_name].create_indexes([IndexModel(list(index["key"].items()), **options)])
    require(database_fingerprint(destination, plan) == baseline, "RESTORED_COPY_COMPARISON_FAILED")
    return destination


def choose_accounts(database):
    members, admins = [], []
    fields = {key: 1 for key in ("id", "username", "email", "status", "is_admin", "active_session_id", "role",
                                 "is_bot", "is_system", "system_account", "account_type", "disabled",
                                 "password_hash", "hashed_password", "password")}
    fields["_id"] = 0
    for account in database.users.find({"status": "approved"}, fields):
        if (account.get("status") != "approved" or account.get("disabled") is True
                or any(account.get(key) for key in ("is_bot", "is_system", "system_account"))
                or account.get("account_type") in {"bot", "system"}
                or account.get("role") in {"bot", "system"}
                or str(account.get("username", "")).casefold() in {"cashoutai_bot", "system", "system_bot"}):
            continue
        if not all(isinstance(account.get(key), str) and 0 < len(account[key]) <= 254
                   for key in ("id", "username", "email", "active_session_id")) or len(account["id"]) > 128:
            continue
        if account.get("is_admin") is True and account.get("role") == "admin":
            admins.append(account)
        elif (not account.get("is_admin") and account.get("role") in {None, "member", "moderator"}
              and not any(account.get(key) for key in ("password_hash", "hashed_password", "password"))):
            members.append(account)
    for member in members:
        for admin in admins:
            if member["id"] != admin["id"] and member["email"].strip().casefold() != admin["email"].strip().casefold():
                return {"member_id": member["id"], "admin_id": admin["id"]}
    raise Refusal("ELIGIBLE_RESTORED_ACCOUNTS_UNAVAILABLE")


def parse_child_result(path):
    require(path.stat().st_size <= 1024 * 1024, "CHILD_OUTPUT_LIMIT")
    text = path.read_text(encoding="utf-8")
    decoder = json.JSONDecoder()
    result = None
    while text.strip():
        try:
            value, offset = decoder.raw_decode(text.lstrip())
        except ValueError:
            raise Refusal("CHILD_RESULT_UNAVAILABLE") from None
        require(isinstance(value, dict), "CHILD_RESULT_UNAVAILABLE")
        result = value
        text = text.lstrip()[offset:]
    require(result is not None and result.get("result") == "PASS", "CHILD_REHEARSAL_FAILED")
    return result


def run_child(command, environment, output_path, seconds):
    process = None
    # Warnings and tracebacks can contain sensitive values. Keep stderr private
    # and separate so harmless diagnostic output cannot corrupt the JSON result.
    with output_path.open("xb") as output, output_path.with_suffix(".stderr.log").open("xb") as errors:
        try:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=output, stderr=errors,
                                       env=environment, cwd=APP_ROOT, start_new_session=True)
            require(process.wait(timeout=seconds) == 0, "CHILD_REHEARSAL_FAILED")
        except subprocess.TimeoutExpired:
            raise Refusal("CHILD_REHEARSAL_TIME_LIMIT") from None
        finally:
            stop_process(process)
    return parse_child_result(output_path)


def public_result(archive_sha, version, baseline, api, browser):
    require(re.fullmatch(r"[0-9a-f]{64}", archive_sha) and re.fullmatch(r"8\.0\.[0-9]+", version),
            "INVALID_AGGREGATE_INPUT")
    require(api.get("result") == "PASS" and api.get("storage") == "real_local_MongoDB_8" and len(api.get("accounts", [])) == 2
            and {row.get("account") for row in api["accounts"]} == {"member", "admin"}
            and all(row.get("recovery") == row.get("single_session") == "PASS" for row in api["accounts"])
            and api.get("real_emails_sent") == 0 and api.get("external_network_attempts") == 0,
            "API_RECOVERY_EVIDENCE_FAILED")
    require(browser.get("result") == "PASS" and browser.get("accounts_exercised") == 1 and browser.get("browser_reset_completed") is True
            and browser.get("real_emails_sent") == 0 and browser.get("external_app_connections") == 0
            and browser.get("record_preservation") == "PASS", "BROWSER_RECOVERY_EVIDENCE_FAILED")
    for result in (api, browser):
        require(type(result.get("captured_emails")) is int and 2 <= result["captured_emails"] <= 20,
                "CAPTURED_EMAIL_EVIDENCE_FAILED")
    return {"schema": "cashout_private_recovery_v1", "result": "PASS", "mode": "restored_snapshot",
            "mongo_version": version, "source_fcv": "8.0", "archive_sha256": archive_sha,
            "source_documents": sum(item["count"] for item in baseline.values()),
            "source_collections": len(baseline), "accounts_exercised": 2, "browser_accounts_exercised": 1,
            "captured_emails": api["captured_emails"] + browser["captured_emails"],
            "real_emails_sent": 0, "external_app_connections": 0, "record_preservation": "PASS",
            "local_snapshot_restore": "PASS", "logical_copy_verified": True,
            "backup_restore_verified": False, "real_member_recovery_verified": True,
            "production_deployment_verified": False, "source_identity": "operator_selected_snapshot",
            "archive_checksum": "computed_after_https_download"}


def execute(plan, root):
    import requests
    import pymongo  # Load driver capability probes before the network audit boundary.
    logging.disable(logging.CRITICAL)
    environment = child_environment(root)
    (root / "tmp").mkdir(mode=0o700)
    required_space = plan.receipt["archive_max_bytes"] + 4 * plan.receipt["expanded_max_bytes"] + 64 * CHUNK
    require(shutil.disk_usage(root).free >= required_space, "INSUFFICIENT_PRIVATE_DISK")
    boundary = NetworkBoundary(plan.receipt["download_host"], resolve_public_addresses(plan.receipt["download_host"]))
    sys.addaudithook(boundary)
    archive = root / "snapshot.tar.gz"
    with requests.Session() as session:
        session.trust_env = False
        archive_sha = download_archive(plan, archive, session, time.monotonic() + 600)
    boundary.local_only = True
    dbpath = extract_archive(archive, root / "raw", plan)
    target_path = root / "target"
    target_path.mkdir(mode=0o700)
    suffix = secrets.token_hex(12)
    api_name, browser_name = f"cashout_rehearsal_{suffix}_api", f"cashout_rehearsal_{suffix}_browser"
    with running_mongo(target_path, TARGET_PORT, root, environment) as (target, version):
        with running_mongo(dbpath, SOURCE_PORT, root, environment) as (source, source_version):
            require(source_version == version, "MONGODB_RUNTIME_MISMATCH")
            database = source["cashoutai"]
            baseline = database_fingerprint(database, plan)
            private_json(root / "baseline-digests.json", baseline)
            selection = choose_accounts(database)
            private_json(root / "selection.json", selection)
            clone_database(database, target, api_name, baseline, plan)
            clone_database(database, target, browser_name, baseline, plan)
            require(database_fingerprint(database, plan) == baseline, "RESTORED_SOURCE_CHANGED")
        # The source listener is stopped before either application process runs.
        selection_path = str(root / "selection.json")
        api = run_child([sys.executable, str(APP_ROOT / "backend/tests/rehearse_restored_app_recovery.py"),
                         "--mode", "exercise", "--restored-copy", "--database", api_name,
                         "--mongo-port", str(TARGET_PORT), "--selection-file", selection_path],
                        environment, root / "api-private-output.json", 300)
        browser = run_child([sys.executable, str(APP_ROOT / "scripts/private_recovery/test_restored_browser.py"),
                             "--frontend-build", str(APP_ROOT / "frontend/build"), "--database", browser_name,
                             "--selection-file", selection_path, "--mongo-port", str(TARGET_PORT), "--http-port", str(HTTP_PORT)],
                            environment, root / "browser-private-output.json", 480)
        require(boundary.denied == 0, "PARENT_NETWORK_BOUNDARY_FAILED")
        return public_result(archive_sha, version, baseline, api, browser)


def main():
    stage = "configuration"
    try:
        require(len(sys.argv) == 1, "COMMAND_ARGUMENTS_REFUSED")
        plan = Plan.from_environment(dict(os.environ))
        parent_directory = private_temp_parent(os.environ)
        # Keep the signed URL only in parent memory; never inherit it in Mongo,
        # application, preview, browser, or verification child environments.
        os.environ.clear()
        os.umask(0o077)
        def interrupted(signum, frame):
            raise Refusal("PRIVATE_REHEARSAL_INTERRUPTED")
        signal.signal(signal.SIGTERM, interrupted)
        signal.signal(signal.SIGINT, interrupted)
        signal.signal(signal.SIGALRM, interrupted)
        signal.alarm(MAX_SECONDS)
        stage = "restored_rehearsal"
        with tempfile.TemporaryDirectory(prefix="cashout_private_recovery_", dir=parent_directory) as temporary:
            result = execute(plan, Path(temporary))
        signal.alarm(0)
    except BaseException as error:
        # Driver, tar, network and browser exceptions can embed account records,
        # paths or signed URLs. They never cross this output boundary.
        result = {"schema": "cashout_private_recovery_v1", "result": "FAIL", "stage": stage,
                  "reason": str(error) if isinstance(error, Refusal) else "PRIVATE_RUNTIME_FAILED"}
        print(json.dumps(result, sort_keys=True), flush=True)
        return 1
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
