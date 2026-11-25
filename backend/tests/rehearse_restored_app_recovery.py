"""Rehearse recovery using the real app and a LOCAL, restored MongoDB 8 copy.

This process never accepts a Mongo URI. It accepts only a numeric loopback port,
a cashout_rehearsal_* database, and a standalone MongoDB 8 server. It does not
download, restore, drop, or export a database. Restore/backup integrity must be
verified separately before using --restored-copy. Never run this on a public host.

Examples (use the application's Python environment):
  python backend/tests/rehearse_restored_app_recovery.py --self-test
  python backend/tests/rehearse_restored_app_recovery.py --mode exercise \
    --mongo-port 27217 --database cashout_rehearsal_synthetic --seed-synthetic
  python backend/tests/rehearse_restored_app_recovery.py --mode serve \
    --mongo-port 27217 --database cashout_rehearsal_restored --restored-copy \
    --selection-file /private/rehearsal-selection.json \
    --frontend-build /private/rehearsal-build

The private selection file is JSON: {"member_id": "...", "admin_id": "..."}.
The frontend must be compiled with an empty REACT_APP_BACKEND_URL so /api is
same-origin. The server binds only 127.0.0.1; external fetches, frames and service
workers are blocked by its Content Security Policy. It is a recovery preview,
not a provider/quote/push/worker integration rehearsal. Output contains only
aggregate results and paths; private operator details and captures use mode 0600.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import importlib
import json
import logging
import os
from pathlib import Path
import re
import secrets
import socket
import stat
import sys
import tempfile
import threading
from types import ModuleType
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit


BACKEND = Path(__file__).resolve().parents[1]
DATABASE_PATTERN = re.compile(r"cashout_rehearsal_[a-z0-9_]{4,48}\Z")
AUTH_CHANGES = frozenset({
    "password_hash", "hashed_password", "password", "reset_token_hash", "reset_token",
    "reset_expires", "modified_at", "active_session_id", "session_created_at", "is_online", "last_seen",
})
LOGIN_CHANGES = AUTH_CHANGES | frozenset({
    "experience_points", "level", "daily_login_streak", "last_login_date",
    "last_membership_check", "achievements",
})


class RehearsalError(Exception):
    """Only fixed, non-sensitive messages may be used with this exception."""


def require(condition, message):
    if not condition:
        raise RehearsalError(message)


@dataclass(frozen=True)
class Configuration:
    database: str
    mongo_port: int
    http_port: int
    mode: str
    seed_synthetic: bool
    restored_copy: bool
    selection_file: Path | None = None
    frontend_build: Path | None = None

    @property
    def origin(self):
        return f"http://127.0.0.1:{self.http_port}"

    @property
    def mongo_uri(self):
        # A single local rehearsal must fail promptly if its server is absent.
        # No pool tuning: use the real driver's default pool behavior.
        return (f"mongodb://127.0.0.1:{self.mongo_port}/?directConnection=true"
                "&serverSelectionTimeoutMS=5000&connectTimeoutMS=5000")

    def validate(self):
        require(bool(DATABASE_PATTERN.fullmatch(self.database)), "A rehearsal-prefixed database is required")
        require(self.mode in {"inspect", "exercise", "serve"}, "Invalid rehearsal mode")
        require(1024 <= self.mongo_port <= 65535 and 1024 <= self.http_port <= 65535,
                "Use explicit unprivileged local ports")
        require(self.mongo_port != self.http_port, "Mongo and HTTP ports must differ")
        require(self.seed_synthetic != self.restored_copy, "Select exactly one data source mode")
        require(self.seed_synthetic or self.selection_file is not None or self.mode == "inspect",
                "A private restored-account selection file is required")
        if self.mode == "serve":
            require(self.frontend_build is not None, "A compiled isolated frontend is required")


def private_json_read(path):
    require(path.is_absolute() and not path.is_symlink(), "Private input must be an absolute regular file")
    info = path.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077,
            "Private input must be owned by this user and mode 0600")
    require(info.st_size < 16384, "Private input is too large")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def private_json_write(path, value):
    encoded = json.dumps(value, indent=2, sort_keys=True).encode()
    # The parent directory is freshly created with mode 0700. Reject symlinks.
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        os.fchmod(handle.fileno(), 0o600)
        handle.write(encoded)


class LoopbackGuard:
    """Process audit guard, not a substitute for an operating-system sandbox."""
    def __init__(self, configuration):
        self.mongo_port = configuration.mongo_port
        self.http_port = configuration.http_port
        self.denied = []

    def __call__(self, event, args):
        denied = False
        if event in {"socket.getaddrinfo", "socket.gethostbyname"}:
            denied = args[0] != "127.0.0.1"
        elif event in {"socket.gethostbyaddr", "socket.getnameinfo", "socket.sendto", "socket.sendmsg"}:
            denied = True
        elif event == "socket.__new__":
            denied = args[1] not in {socket.AF_UNIX, socket.AF_INET}
            # PyMongo adds CLOEXEC at socket creation. It changes descriptor
            # inheritance, not the stream protocol or allowed destination.
            socket_type = args[2] & ~getattr(socket, "SOCK_CLOEXEC", 0)
            denied |= args[1] == socket.AF_INET and socket_type != socket.SOCK_STREAM
        elif event in {"socket.connect", "socket.bind"}:
            sock, address = args[:2]
            if sock.family != socket.AF_UNIX:
                ports = {self.mongo_port, self.http_port} if event == "socket.connect" else {self.http_port}
                denied = not (isinstance(address, tuple) and len(address) == 2
                              and address[0] == "127.0.0.1" and address[1] in ports)
        elif event in {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn"}:
            denied = True
        if denied:
            self.denied.append(event)  # Never retain destinations or credentials.
            raise RehearsalError("An operation outside the isolated rehearsal was blocked")


def canonical_digest(value):
    from bson import json_util
    encoded = json_util.dumps(value, json_options=json_util.CANONICAL_JSON_OPTIONS,
                              sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


async def snapshot(db):
    """Private digests, not an export and not proof of source backup equality."""
    result = {}
    for name in sorted(await db.list_collection_names()):
        collection = db[name]
        documents = {}
        async for row in collection.find({}):
            documents[canonical_digest(row["_id"])] = canonical_digest(row)
        result[name] = {
            "count": len(documents), "documents": documents,
            "options_digest": canonical_digest(await collection.options()),
            "indexes_digest": canonical_digest(await collection.index_information()),
        }
    return result


def validate_server(hello, build_info):
    require(str(build_info.get("version", "")).startswith("8."), "A local MongoDB 8 server is required")
    require(not hello.get("setName") and hello.get("msg") != "isdbgrid", "Only a local standalone target is allowed")
    require(bool(hello.get("isWritablePrimary", hello.get("ismaster", False))), "The isolated target is not writable")


async def seed_synthetic(db):
    require(not await db.list_collection_names(), "Synthetic seeding requires an empty database")
    now = datetime.utcnow()
    for label in ("member", "admin", "unrelated"):
        row = {
            "id": "rehearsal-" + label, "username": "rehearsal_" + label,
            "email": label + "@example.test", "real_name": "Synthetic Recovery Account",
            "status": "approved", "is_admin": label == "admin", "role": "admin" if label == "admin" else "member",
            "active_session_id": secrets.token_urlsafe(32), "session_created_at": now,
            "is_online": True, "created_at": now - timedelta(days=100),
            "last_login_date": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
            "last_membership_check": now.strftime("%Y-%m-%d"),
            "experience_points": 321, "level": 3, "daily_login_streak": 2,
            "achievements": [], "followers": [], "following": [], "bio": "Preserve this profile",
            "membership_plan": "Lifetime Member",
        }
        await db.users.insert_one(row)
        await db.messages.insert_one({"id": "saved-" + label, "user_id": row["id"], "content": "Synthetic saved win"})
        await db.notifications.insert_one({"id": "saved-" + label, "user_id": row["id"], "read": False})
    # Only an explicitly empty synthetic database receives these two rooms.
    # More than 50 rows per room exercises the ordinary latest-message limit.
    await db.nautilus_chat.insert_many([
        {"_id": f"synthetic-chat-{asset}-{index}", "id": f"synthetic-chat-{asset}-{index}",
         "asset": asset, "authorId": "rehearsal-member", "author": "Synthetic Recovery Account",
         "content": "Synthetic room-index fixture", "isAdmin": False,
         "createdAt": (now - timedelta(seconds=index)).isoformat(timespec="milliseconds") + "Z"}
        for asset in ("BTC", "ETH") for index in range(60)
    ])
    return {"member_id": "rehearsal-member", "admin_id": "rehearsal-admin"}


async def verify_synthetic_chat_query(db):
    """Check the real startup index and the unchanged room query on fake data."""
    name = "nautilus_chat_asset_created_at"
    index = (await db.nautilus_chat.index_information()).get(name)
    require(index is not None and index.get("key") == [("asset", 1), ("createdAt", -1)]
            and not index.get("unique", False), "The room-chat startup index is unavailable or incorrect")
    rows = await db.nautilus_chat.find({"asset": "BTC"}).sort("createdAt", -1).limit(50).to_list(length=50)
    require([row["id"] for row in rows] == [f"synthetic-chat-BTC-{number}" for number in range(50)],
            "The ordinary room query did not return the newest 50 messages for its room")
    plan = await db.command("explain", {
        "find": "nautilus_chat", "filter": {"asset": "BTC"},
        "sort": {"createdAt": -1}, "limit": 50,
    }, verbosity="executionStats")

    def uses_index(node):
        if isinstance(node, dict):
            return node.get("indexName") == name or any(uses_index(value) for value in node.values())
        return isinstance(node, list) and any(uses_index(value) for value in node)

    require(uses_index(plan.get("queryPlanner", {}).get("winningPlan", {})),
            "The ordinary room query did not use the expected startup index")
    statistics = plan.get("executionStats", {})
    require(statistics.get("nReturned") == 50, "The explained room query returned an unexpected number of messages")
    return {"result": "PASS", "index": name, "non_unique": True,
            "fixture_rooms": 2, "fixture_messages": 120, "returned_messages": statistics["nReturned"],
            "keys_examined": statistics.get("totalKeysExamined"),
            "documents_examined": statistics.get("totalDocsExamined")}


async def selected_accounts(db, selection, *, require_missing_credential=True):
    require(isinstance(selection, dict) and set(selection) == {"member_id", "admin_id"},
            "Selection must identify a member and an administrator")
    require(selection["member_id"] != selection["admin_id"], "Select two different restored accounts")
    result = {}
    for label in ("member", "admin"):
        identity = selection[label + "_id"]
        require(isinstance(identity, str) and 0 < len(identity) <= 128, "Invalid selected identity")
        row = await db.users.find_one({"id": identity})
        require(row is not None and row.get("status") == "approved", "Selected approved account is unavailable")
        require(bool(row.get("is_admin")) == (label == "admin"), "Selected role does not match the rehearsal")
        require(all(isinstance(row.get(key), str) and row[key] for key in ("username", "email", "active_session_id")),
                "Selected account needs its saved username, email and session")
        if label == "member" and require_missing_credential:
            require(not any(row.get(key) for key in ("password_hash", "hashed_password", "password")),
                    "Select a restored member without a saved credential")
        result[label] = row
    require(len({row["email"].strip().casefold() for row in result.values()}) == 2,
            "Selected accounts must have different email addresses")
    return result


class Captures:
    def __init__(self, accounts, origin, state_dir):
        self.accounts = accounts
        self.origin = origin
        self.state_dir = state_dir
        self.messages = []
        self.provider_attempts = []
        self.lock = threading.Lock()

    def send(self, params):
        recipients = params.get("to")
        matches = [label for label, row in self.accounts.items() if recipients == [row["email"]]]
        require(len(matches) == 1, "Unexpected email recipient reached the isolated capture")
        label = matches[0]
        entry = {"label": label, "text_digest": hashlib.sha256(params["text"].encode()).hexdigest()}
        links = re.findall(re.escape(self.origin) + r"/\?reset_token=[A-Za-z0-9_-]+", params["text"])
        if links:
            require(len(links) == 1 and links[0] in params.get("html", ""), "Reset link does not match the isolated frontend")
            entry["reset_url"] = links[0]
        with self.lock:
            self.messages.append(entry)
            private_json_write(self.state_dir / "captured-links.json", self.messages)
            return {"id": "captured-only-" + str(len(self.messages))}

    def token_for(self, label):
        message = next((entry for entry in reversed(self.messages)
                        if entry["label"] == label and entry.get("reset_url")), None)
        require(message is not None, "The recovery request did not produce a captured link")
        return parse_qs(urlsplit(message["reset_url"]).query)["reset_token"][0]

    def fcm_module(self):
        module = ModuleType("fcm_service")
        owner = self

        class CapturedFCM:
            initialized = False

            async def send_stock_alert(self, *args, **kwargs):
                owner.provider_attempts.append("stock_push_suppressed")
                return {"status": "rejected", "reason": "isolated_rehearsal"}

            async def send_notification(self, *args, **kwargs):
                owner.provider_attempts.append("legacy_push_suppressed")
                return False

            async def send_chat_notification(self, *args, **kwargs):
                return False

            async def send_to_multiple(self, *args, **kwargs):
                return {"success_count": 0, "failure_count": 0, "suppressed": True}

        module.fcm_service = CapturedFCM()
        return module


async def idle_worker():
    await asyncio.Event().wait()


def app_environment(configuration):
    # Deliberately do not inherit MONGO_URL, dotenv, proxy, cloud or provider keys.
    return {
        "MONGO_URL": configuration.mongo_uri, "DB_NAME": configuration.database,
        "MEMBERSHIP_APPROVAL_MODE": "manual", "SQUARE_BILLING_ENABLED": "false",
        "FRONTEND_URL": configuration.origin, "CORS_ORIGINS": configuration.origin,
        "RESEND_API_KEY": "capture-only-not-a-provider-key",
        "SENDER_EMAIL": "capture@example.test", "ADMIN_EMAIL": "admin@example.test",
    }


def load_app(configuration, captures, stack):
    import dotenv
    import resend
    stack.enter_context(patch.dict(os.environ, app_environment(configuration), clear=True))
    stack.enter_context(patch.object(dotenv, "load_dotenv", return_value=False))
    stack.enter_context(patch.object(resend.Emails, "send", captures.send))
    stack.enter_context(patch.dict(sys.modules, {"fcm_service": captures.fcm_module()}))
    require("server" not in sys.modules, "The real app must be imported fresh after isolation")
    sys.path.insert(0, str(BACKEND))
    server = importlib.import_module("server")
    require(server.db.name == configuration.database and server.MONGO_URL == configuration.mongo_uri,
            "The app did not select the isolated database")
    require(server.square_billing_service.settings.mode == "manual", "Automatic billing must remain disabled")
    for target, name in ((server, "periodic_cleanup"), (server.stock_alert_service, "run"),
                         (server.nautilus_settlement_service, "run")):
        stack.enter_context(patch.object(target, name, idle_worker))
    return server


def filtered(row, ignored):
    return {key: value for key, value in row.items() if key not in ignored}


async def request(client, method, path, status=200, **kwargs):
    response = await client.request(method, path, **kwargs)
    require(response.status_code == status, "An actual recovery API response did not match expectations")
    return response.json()


async def await_login_tasks():
    tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()
             and getattr(task.get_coro(), "__qualname__", "") == "process_login_rewards_async"]
    if tasks:
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=30)


async def exercise(server, accounts, captures):
    import bcrypt
    import httpx
    results = []
    for index, (label, original) in enumerate(accounts.items()):
        identity = original["id"]
        old_headers = {"X-User-ID": identity, "X-Session-ID": original["active_session_id"]}
        profile = "/api/users/" + identity + "/profile"
        transport = httpx.ASGITransport(app=server.app, client=("127.0.0.1", 20000 + index))
        async with httpx.AsyncClient(transport=transport, base_url=captures.origin, trust_env=False) as client:
            require((await request(client, "GET", "/api/users/" + identity + "/session-status", headers=old_headers))["valid"],
                    "The copied session is not valid before recovery")
            await request(client, "GET", profile, headers=old_headers)
            current = await server.db.users.find_one({"id": identity})
            before_count = len(captures.messages)
            await request(client, "POST", "/api/users/reset-password-request", json={"email": original["email"]})
            require(len(captures.messages) == before_count + 1, "The reset request did not capture exactly one email")
            token = captures.token_for(label)
            after_request = await server.db.users.find_one({"id": identity})
            ignored = {"reset_token_hash", "reset_token", "reset_expires"}
            require(filtered(after_request, ignored) == filtered(current, ignored), "Recovery request changed unrelated account data")
            require(after_request.get("reset_token_hash") == hashlib.sha256(token.encode()).hexdigest(), "Stored token hash differs")
            require((await request(client, "GET", "/api/users/" + identity + "/session-status", headers=old_headers))["valid"],
                    "Requesting recovery revoked the copied session")
            password = secrets.token_urlsafe(24)
            await request(client, "POST", "/api/users/reset-password-confirm", json={"token": token, "new_password": password})
            recovered = await server.db.users.find_one({"id": identity})
            require(filtered(recovered, AUTH_CHANGES) == filtered(current, AUTH_CHANGES), "Recovery changed identity or saved history")
            require(bcrypt.checkpw(password.encode(), recovered["password_hash"].encode()), "The real password hash did not verify")
            require(not recovered.get("active_session_id"), "Recovery did not revoke the old session")
            require(not {"reset_token_hash", "reset_token", "reset_expires", "hashed_password", "password"} & recovered.keys(),
                    "Recovery left an obsolete credential")
            await request(client, "GET", profile, status=401, headers=old_headers)
            await request(client, "POST", "/api/users/reset-password-confirm", status=400, json={"token": token, "new_password": password})
            first = await request(client, "POST", "/api/users/login", json={"username": original["username"], "password": password})
            await await_login_tasks()
            second = await request(client, "POST", "/api/users/login", json={"username": original["username"], "password": password})
            await await_login_tasks()
            require(first["id"] == identity == second["id"], "Login changed account identity")
            require(first["active_session_id"] != second["active_session_id"], "One-login replacement did not occur")
            await request(client, "GET", profile, status=401,
                          headers={"X-User-ID": identity, "X-Session-ID": first["active_session_id"]})
            await request(client, "GET", profile,
                          headers={"X-User-ID": identity, "X-Session-ID": second["active_session_id"]})
            await request(client, "GET", "/api/billing/admin/payments?limit=1",
                          status=200 if label == "admin" else 403,
                          headers={"X-User-ID": identity, "X-Session-ID": second["active_session_id"]})
            final = await server.db.users.find_one({"id": identity})
            require(filtered(final, LOGIN_CHANGES) == filtered(current, LOGIN_CHANGES), "Login changed non-login account fields")
            require(final.get("experience_points", 0) >= current.get("experience_points", 0), "Login removed existing XP")
            require(set(current.get("achievements", [])) <= set(final.get("achievements", [])), "Login removed an existing achievement")
            results.append({"account": label, "recovery": "PASS", "single_session": "PASS",
                            "legitimate_login_changes": sorted(key for key in LOGIN_CHANGES - AUTH_CHANGES
                                                               if current.get(key) != final.get(key))})
    return results


async def verify_preservation(db, baseline, accounts):
    selected = {row["id"] for row in accounts.values()}
    selected_keys = {canonical_digest(row["_id"]) for row in accounts.values()}
    appended = {}
    for original in accounts.values():
        current = await db.users.find_one({"id": original["id"]})
        require(current is not None and filtered(current, LOGIN_CHANGES) == filtered(original, LOGIN_CHANGES),
                "A selected account changed outside recovery and login")
        require(current.get("experience_points", 0) >= original.get("experience_points", 0), "Existing XP was removed")
        require(set(original.get("achievements", [])) <= set(current.get("achievements", [])), "An existing achievement was removed")
    for name, before in baseline.items():
        seen = set()
        async for row in db[name].find({}):
            key = canonical_digest(row["_id"])
            seen.add(key)
            if key in before["documents"]:
                if name == "users" and key in selected_keys:
                    continue
                require(canonical_digest(row) == before["documents"][key], "An unrelated restored document changed")
            else:
                require(name in {"messages", "notifications"} and row.get("user_id") in selected,
                        "An unexpected record was added to a restored collection")
                appended[name] = appended.get(name, 0) + 1
        require(set(before["documents"]) <= seen, "A restored document was removed")
    for name in set(await db.list_collection_names()) - set(baseline):
        async for row in db[name].find({}):
            require(name in {"messages", "notifications"} and row.get("user_id") in selected,
                    "An unexpected record was added to a new rehearsal collection")
            appended[name] = appended.get(name, 0) + 1
    return appended


def verify_frontend(path):
    require(path.is_absolute() and path.is_dir() and (path / "index.html").is_file(), "Compiled frontend directory is unavailable")
    scripts = list((path / "static" / "js").glob("*.js"))
    require(bool(scripts), "Compiled frontend scripts are unavailable")
    for script in scripts:
        data = script.read_bytes()
        require(b"https://cashoutai.onrender.com" not in data,
                "Rebuild the frontend with an empty REACT_APP_BACKEND_URL")
    return hashlib.sha256((path / "index.html").read_bytes()).hexdigest()


class PrivatePreview:
    """Host/origin guard and browser network policy around the unchanged app."""
    def __init__(self, app, configuration, accounts, captures):
        self.app, self.configuration = app, configuration
        self.accounts, self.captures = accounts, captures

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"}:
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        host = f"127.0.0.1:{self.configuration.http_port}".encode()
        origin = self.configuration.origin.encode()
        valid = headers.get(b"host") == host and headers.get(b"origin", origin) == origin
        valid &= scope.get("client", ("127.0.0.1", 0))[0] == "127.0.0.1"
        if not valid:
            if scope["type"] == "websocket":
                return await send({"type": "websocket.close", "code": 1008})
            await send({"type": "http.response.start", "status": 403, "headers": []})
            return await send({"type": "http.response.body", "body": b"Private rehearsal only"})
        if scope["type"] == "http" and scope["method"] not in {"GET", "HEAD", "OPTIONS"}:
            allowed = {"/api/users/login", "/api/users/reset-password-request", "/api/users/reset-password-confirm"}
            if scope["method"] != "POST" or scope["path"] not in allowed:
                await send({"type": "http.response.start", "status": 403, "headers": []})
                return await send({"type": "http.response.body", "body": b"Recovery actions only"})
            # A copied database may contain many real identities. The preview
            # may change credentials only for the two explicitly selected ones.
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > 16384:
                    await send({"type": "http.response.start", "status": 413, "headers": []})
                    return await send({"type": "http.response.body", "body": b"Request too large"})
                if not message.get("more_body", False):
                    break
            try:
                payload = json.loads(body)
                if scope["path"].endswith("/login"):
                    allowed_value = str(payload["username"]).strip().casefold()
                    allowed_values = {row["username"].strip().casefold() for row in self.accounts.values()}
                elif scope["path"].endswith("/reset-password-request"):
                    allowed_value = str(payload["email"]).strip().casefold()
                    allowed_values = {row["email"].strip().casefold() for row in self.accounts.values()}
                else:
                    allowed_value = str(payload["token"])
                    allowed_values = {parse_qs(urlsplit(entry["reset_url"]).query)["reset_token"][0]
                                      for entry in self.captures.messages if entry.get("reset_url")}
                valid_payload = allowed_value in allowed_values
            except (ValueError, TypeError, KeyError):
                valid_payload = False
            if not valid_payload:
                await send({"type": "http.response.start", "status": 403, "headers": []})
                return await send({"type": "http.response.body", "body": b"Selected rehearsal accounts only"})
            original_receive = receive
            delivered = False

            async def replay_body():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await original_receive()
            receive = replay_body
        csp = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
               "img-src 'self' data: blob:; font-src 'self' data:; "
               f"connect-src 'self' ws://127.0.0.1:{self.configuration.http_port}; "
               "worker-src 'none'; frame-src 'none'; frame-ancestors 'none'; "
               "object-src 'none'; base-uri 'none'; form-action 'self'").encode()

        async def protected_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + [
                    (b"content-security-policy", csp), (b"cache-control", b"no-store"),
                    (b"referrer-policy", b"no-referrer"), (b"x-content-type-options", b"nosniff"),
                ]
            await send(message)
        await self.app(scope, receive, protected_send)


async def run(configuration, state_dir, guard):
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(configuration.mongo_uri)
    try:
        validate_server(await client.admin.command("hello"), await client.admin.command("buildInfo"))
        db = client[configuration.database]
        selection = await seed_synthetic(db) if configuration.seed_synthetic else (
            private_json_read(configuration.selection_file) if configuration.selection_file else None)
        baseline = await snapshot(db)
        require("users" in baseline and baseline["users"]["count"] > 0, "The isolated application database is empty")
        private_json_write(state_dir / "baseline-digests.json", baseline)
        if configuration.mode == "inspect":
            return {"result": "INSPECTED", "collections": len(baseline), "backup_restore_verified": False}
        accounts = await selected_accounts(db, selection, require_missing_credential=configuration.mode == "exercise")
    finally:
        client.close()

    captures = Captures(accounts, configuration.origin, state_dir)
    private_json_write(state_dir / "operator-details.json", {
        "origin": configuration.origin,
        "accounts": {label: {key: row[key] for key in ("username", "email")} for label, row in accounts.items()},
    })
    with ExitStack() as stack:
        server = load_app(configuration, captures, stack)
        try:
            if configuration.mode == "exercise":
                chat_index_evidence = None
                async with server.app.router.lifespan_context(server.app):
                    await server.stock_alert_service.initialize()
                    if configuration.seed_synthetic:
                        chat_index_evidence = await verify_synthetic_chat_query(server.db)
                        chat_indexes = await server.db.nautilus_chat.index_information()
                    results = await exercise(server, accounts, captures)
                    additions = await verify_preservation(server.db, baseline, accounts)
                if configuration.seed_synthetic:
                    # Re-enter the real lifespan to prove repeated startup is
                    # harmless. Never add this fixture to a restored database.
                    async with server.app.router.lifespan_context(server.app):
                        require(await server.db.nautilus_chat.index_information() == chat_indexes,
                                "Repeated startup changed the room-chat index definition")
                        await verify_preservation(server.db, baseline, accounts)
                    chat_index_evidence["repeated_startup"] = "PASS"
                require(not guard.denied, "The rehearsal attempted a forbidden external operation")
                return {"result": "PASS", "storage": "real_local_MongoDB_8", "accounts": results,
                        "captured_emails": len(captures.messages), "real_emails_sent": 0,
                        "external_network_attempts": len(guard.denied), "login_history_additions": additions,
                        "continuous_workers": "idle", "backup_restore_verified": False,
                        "browser_reset_completed": False,
                        **({"synthetic_chat_query": chat_index_evidence} if chat_index_evidence else {})}

            from starlette.staticfiles import StaticFiles
            import uvicorn
            fingerprint = verify_frontend(configuration.frontend_build)
            server.app.mount("/", StaticFiles(directory=configuration.frontend_build, html=True), name="isolated-preview")
            private_json_write(state_dir / "preview-ready.json", {"origin": configuration.origin, "index_sha256": fingerprint})
            preview = PrivatePreview(server.app, configuration, accounts, captures)
            config = uvicorn.Config(preview, host="127.0.0.1", port=configuration.http_port,
                                    loop="asyncio", http="h11", access_log=False, log_config=None,
                                    reload=False, workers=1)
            await uvicorn.Server(config).serve()
            await await_login_tasks()
            additions = await verify_preservation(server.db, baseline, accounts)
            require(not guard.denied, "The preview attempted a forbidden external operation")
            return {"result": "PREVIEW_STOPPED", "captured_emails": len(captures.messages),
                    "login_history_additions": additions, "backup_restore_verified": False,
                    "browser_reset_completed": "requires operator evidence"}
        finally:
            server.client.close()


async def preview_guard_self_test(configuration):
    accounts = {"member": {"email": "member@example.test", "username": "rehearsal_member"}}
    captures = type("SyntheticCaptures", (), {"messages": [
        {"reset_url": configuration.origin + "/?reset_token=synthetic-token"}
    ]})()

    async def target(scope, receive, send):
        if scope["method"] == "POST":
            require(bool(json.loads((await receive())["body"])), "Allowed body was not forwarded")
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    wrapper = PrivatePreview(target, configuration, accounts, captures)
    cases = [
        ("GET", "/", None, b"evil.example", None, 403),
        ("GET", "/", None, None, b"https://evil.example", 403),
        ("DELETE", "/api/users/member", {}, None, None, 403),
        ("POST", "/api/users/reset-password-request", {"email": "other@example.test"}, None, None, 403),
        ("POST", "/api/users/login", {"username": "other"}, None, None, 403),
        ("POST", "/api/users/reset-password-confirm", {"token": "unknown"}, None, None, 403),
        ("POST", "/api/users/reset-password-request", {"email": "member@example.test"}, None, None, 200),
        ("POST", "/api/users/login", {"username": "rehearsal_member"}, None, None, 200),
        ("POST", "/api/users/reset-password-confirm", {"token": "synthetic-token"}, None, None, 200),
        ("GET", "/", None, None, None, 200),
        ("POST", "/api/users/login", {"username": "x" * 20000}, None, None, 413),
    ]
    for method, path, payload, host, origin, status in cases:
        scope = {"type": "http", "method": method, "path": path, "client": ("127.0.0.1", 1000),
                 "headers": [(b"host", host or f"127.0.0.1:{configuration.http_port}".encode()),
                             (b"origin", origin or configuration.origin.encode())]}
        messages = []

        async def receive():
            return {"type": "http.request", "body": json.dumps(payload).encode(), "more_body": False}

        async def send(message):
            messages.append(message)

        await wrapper(scope, receive, send)
        require(messages[0]["status"] == status, "Preview request isolation self-test failed")
        if status == 200:
            require(b"worker-src 'none'" in dict(messages[0]["headers"])[b"content-security-policy"],
                    "Preview did not apply its browser isolation policy")
    return len(cases)


def self_test():
    checks = 0
    good = Configuration("cashout_rehearsal_synthetic", 27217, 4185, "exercise", True, False)
    good.validate()
    for change in ({"database": "emergent_db"}, {"database": "cashout_rehearsal_x/../production"},
                   {"mongo_port": 443}, {"http_port": 27217}, {"seed_synthetic": False},
                   {"restored_copy": True}):
        try:
            Configuration(**{**good.__dict__, **change}).validate()
        except RehearsalError:
            checks += 1
        else:
            raise RehearsalError("Unsafe configuration passed the refusal self-test")
    for hello, build in (({"setName": "atlas-example", "isWritablePrimary": True}, {"version": "8.0.0"}),
                         ({"msg": "isdbgrid", "isWritablePrimary": True}, {"version": "8.0.0"}),
                         ({"isWritablePrimary": True}, {"version": "7.0.0"})):
        try:
            validate_server(hello, build)
        except RehearsalError:
            checks += 1
        else:
            raise RehearsalError("Unsafe server passed the refusal self-test")
    guard = LoopbackGuard(good)
    sys.addaudithook(guard)
    # Match the real driver's stream creation without opening a connection.
    stream_with_cloexec = socket.SOCK_STREAM | getattr(socket, "SOCK_CLOEXEC", 0)
    with socket.socket(socket.AF_INET, stream_with_cloexec):
        pass
    for operation in (lambda: socket.getaddrinfo("example.invalid", 443),
                      lambda: socket.socket().connect(("198.51.100.1", 443)),
                      lambda: socket.socket(socket.AF_INET, stream_with_cloexec).connect(("127.0.0.1", 27017)),
                      lambda: socket.socket().bind(("0.0.0.0", 4185)),
                      lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM),
                      lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM | getattr(socket, "SOCK_CLOEXEC", 0)),
                      lambda: socket.socket(socket.AF_INET, socket.SOCK_RAW),
                      lambda: socket.socket(socket.AF_INET6, socket.SOCK_STREAM)):
        try:
            operation()
        except RehearsalError:
            checks += 1
        else:
            raise RehearsalError("Network isolation self-test failed")
    preview_checks = asyncio.run(preview_guard_self_test(good))
    print(json.dumps({"result": "PASS", "refusal_checks": checks, "preview_boundary_checks": preview_checks,
                      "mongo_or_app_started": False, "real_database_exercise": False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--mode", choices=("inspect", "exercise", "serve"), default="inspect")
    parser.add_argument("--database")
    parser.add_argument("--mongo-port", type=int, default=27217)
    parser.add_argument("--http-port", type=int, default=4185)
    parser.add_argument("--seed-synthetic", action="store_true")
    parser.add_argument("--restored-copy", action="store_true")
    parser.add_argument("--selection-file", type=Path)
    parser.add_argument("--frontend-build", type=Path)
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    configuration = Configuration(args.database or "", args.mongo_port, args.http_port, args.mode,
                                  args.seed_synthetic, args.restored_copy, args.selection_file, args.frontend_build)
    configuration.validate()
    state_dir = Path(tempfile.mkdtemp(prefix="cashout_rehearsal_"))
    os.chmod(state_dir, 0o700)
    if configuration.mode == "serve":
        verify_frontend(configuration.frontend_build)
    # No provider/proxy credentials survive to imports. Match the same explicit
    # environment at app import, while leaving the real Motor constructor intact.
    os.environ.clear()
    os.environ.update(app_environment(configuration))
    guard = LoopbackGuard(configuration)
    sys.addaudithook(guard)
    socket.has_ipv6 = False  # Suppress urllib3's unrelated IPv6 bind capability probe.
    logging.disable(logging.CRITICAL)
    print(json.dumps({"private_state_directory": str(state_dir), "mode": configuration.mode,
                      "preview_origin": configuration.origin if configuration.mode == "serve" else None}), flush=True)
    log_path = state_dir / "private-runtime.log"
    descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as log, redirect_stdout(log), redirect_stderr(log):
            result = asyncio.run(run(configuration, state_dir, guard))
    except Exception as error:
        # Library exceptions may contain URIs/account details; do not print them.
        result = {"result": "FAIL", "error_type": type(error).__name__,
                  "reason": str(error) if isinstance(error, RehearsalError) else "See private runtime prerequisites",
                  "backup_restore_verified": False}
        private_json_write(state_dir / "result.json", result)
        print(json.dumps(result))
        return 1
    private_json_write(state_dir / "result.json", result)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RehearsalError as error:
        print(json.dumps({"result": "REFUSED", "reason": str(error)}))
        raise SystemExit(2)
