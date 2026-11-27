"""Run the actual FastAPI recovery flow in a disposable, network-denied process.

This is an explicit release rehearsal, not an AST/extracted-handler unit test.
Run it directly with the application's pinned Python dependencies plus
mongomock==4.3.0 and mongomock-motor==0.0.36 installed. It never starts a server.

The real server, route dependencies, SlowAPI decorators, request/response models,
bcrypt functions, email templates, and lifespan all execute. Only Mongo storage,
the final Resend SDK send, and Firebase are replaced. No production credentials,
dotenv file, database, email recipient, or provider connection is used.
"""
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import socket
import sys
import traceback
from types import ModuleType
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse


BACKEND = Path(__file__).resolve().parents[1]
DATABASE_NAME = "cashout_recovery_rehearsal_only"
MONGO_URL = "mongodb://recovery.invalid:27017/" + DATABASE_NAME
FRONTEND_URL = "https://recovery.example.test"
NEW_PASSWORD = "Synthetic-Recovery-Password-2026"
OLD_PASSWORD = "Synthetic-Previous-Password-2026"
MAIL = []
OUTBOUND_ATTEMPTS = []
OUTBOUND_CALLERS = []
MONGO_CONSTRUCTIONS = []
SCENARIOS = []


def deny_network(event, args):
    # asyncio needs an AF_UNIX socketpair for its own event-loop wakeups.
    # Block creation of IP sockets, DNS, and any connect/bind/send operation.
    prohibited = event in {
        "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr",
        "socket.connect", "socket.bind", "socket.sendto", "socket.sendmsg",
    }
    prohibited |= event == "socket.__new__" and args[1] in (socket.AF_INET, socket.AF_INET6)
    if prohibited:
        OUTBOUND_ATTEMPTS.append(event)
        OUTBOUND_CALLERS.append([(frame.name, Path(frame.filename).name, frame.lineno)
                                for frame in traceback.extract_stack(limit=8)[:-1]])
        raise RuntimeError("Network I/O is forbidden in the recovery rehearsal")


def capture_resend(params):
    if any(not address.endswith("@example.test") for address in params["to"]):
        raise AssertionError("A non-synthetic email recipient reached the capture")
    MAIL.append(deepcopy(params))
    return {"id": "captured-only-" + str(len(MAIL))}


def headers(user_id, token):
    return {"X-User-ID": user_id, "X-Session-ID": token}


def preserved(row):
    mutable = {
        "password_hash", "hashed_password", "password", "reset_token_hash",
        "reset_token", "reset_expires", "reset_context_hash", "modified_at", "active_session_id",
        "session_created_at", "is_online", "last_seen",
    }
    return {key: value for key, value in row.items() if key not in mutable}


def reset_token(message):
    match = re.search(r"https://recovery\.example\.test/\?reset_token=[A-Za-z0-9_-]+", message["text"])
    assert match, "The actual reset template did not contain the configured frontend link"
    link = match[0]
    assert link in message["html"]
    assert urlparse(link).netloc == "recovery.example.test"
    return parse_qs(urlparse(link).query)["reset_token"][0]


async def expect(client, method, path, expected, **kwargs):
    response = await client.request(method, path, **kwargs)
    assert response.status_code == expected, (method, path, response.status_code, response.text)
    return response.json()


async def seed(db, bcrypt):
    real_hash = bcrypt.hashpw(OLD_PASSWORD.encode(), bcrypt.gensalt()).decode()
    now = datetime.utcnow()
    for name, credential in (
        ("missing", {}),
        ("primary", {"password_hash": real_hash}),
        ("alternate", {"hashed_password": real_hash}),
        ("sha256", {"password_hash": hashlib.sha256(OLD_PASSWORD.encode()).hexdigest()}),
        ("pending", {}),
        ("untouched", {"password_hash": real_hash}),
    ):
        row = {
            "_id": name, "id": name, "username": "member_" + name,
            "email": name + "@example.test", "real_name": "Synthetic Member",
            "status": "pending" if name == "pending" else "approved",
            "role": "member", "is_admin": False,
            "active_session_id": "saved-session-" + name,
            "session_created_at": now, "is_online": True,
            "created_at": now - timedelta(days=100),
            "last_login_date": now.strftime("%Y-%m-%d"),
            "last_membership_check": now.strftime("%Y-%m-%d"),
            "experience_points": 321, "level": 3, "daily_login_streak": 7,
            "avatar_url": "https://images.example.test/avatar.png",
            "profile_banner": "https://images.example.test/banner.png",
            "bio": "Keep this existing profile", "followers": ["untouched"],
            "following": ["untouched"], "follower_count": 1, "following_count": 1,
            "achievements": ["first_trade"], "total_profit": 12.5,
            "trades_count": 2, "stock_alert_push_enabled": True,
            "membership_plan": "Lifetime Member",
            "billing_entitlement": {"managed_by": "manual_payment", "plan_id": "lifetime", "lifetime": True},
            **credential,
        }
        if name == "missing":
            # This account represents an approved historical member with no
            # managed payment record and no stored password hash.
            row.pop("billing_entitlement")
        await db.users.insert_one(row)
        await db.messages.insert_one({"_id": "post-" + name, "user_id": name, "content": "Saved practice win"})
        await db.trades.insert_one({"_id": "trade-" + name, "user_id": name, "price": 12.5})
        await db.notifications.insert_one({"_id": "notice-" + name, "user_id": name, "read": False})
    return real_hash


async def recovery_case(db, client, name, bcrypt):
    original = await db.users.find_one({"id": name})
    old_headers = headers(name, original["active_session_id"])
    profile = "/api/users/" + name + "/profile"
    assert (await expect(client, "GET", "/api/users/" + name + "/session-status", 200, headers=old_headers))["valid"]
    await expect(client, "GET", profile, 403 if name == "pending" else 200, headers=old_headers)
    if name in {"missing", "pending"}:
        await expect(client, "POST", "/api/users/login", 401,
                     json={"username": original["username"], "password": OLD_PASSWORD})

    count = len(MAIL)
    generic = await expect(client, "POST", "/api/users/reset-password-request", 200,
                           json={"email": "nobody@example.test"})
    assert len(MAIL) == count
    requested = await expect(client, "POST", "/api/users/reset-password-request", 200,
                             json={"email": "  " + original["email"].upper() + "  "})
    assert requested == generic and len(MAIL) == count + 1
    token = reset_token(MAIL[-1])
    assert MAIL[-1]["to"] == [original["email"]]
    after_request = await db.users.find_one({"id": name})
    assert after_request["reset_token_hash"] == hashlib.sha256(token.encode()).hexdigest()
    assert "reset_token" not in after_request
    assert datetime.utcnow() < after_request["reset_expires"] <= datetime.utcnow() + timedelta(hours=1)
    assert {k: v for k, v in after_request.items() if k not in {"reset_token_hash", "reset_expires", "reset_context_hash"}} == original
    assert (await expect(client, "GET", "/api/users/" + name + "/session-status", 200, headers=old_headers))["valid"]

    # These requests go through actual Pydantic validation and SlowAPI wrappers.
    await expect(client, "POST", "/api/users/reset-password-confirm", 422,
                 json={"token": "short", "new_password": NEW_PASSWORD})
    await expect(client, "POST", "/api/users/reset-password-confirm", 422,
                 json={"token": token, "new_password": "short"})
    await expect(client, "POST", "/api/users/reset-password-confirm", 400,
                 json={"token": token, "new_password": "é" * 40})
    assert (await db.users.find_one({"id": name}))["reset_token_hash"] == after_request["reset_token_hash"]

    await expect(client, "POST", "/api/users/reset-password-confirm", 200,
                 json={"token": token, "new_password": NEW_PASSWORD})
    recovered = await db.users.find_one({"id": name})
    assert recovered["password_hash"].startswith("$2b$12$")
    assert bcrypt.checkpw(NEW_PASSWORD.encode(), recovered["password_hash"].encode())
    assert not bcrypt.checkpw(OLD_PASSWORD.encode(), recovered["password_hash"].encode())
    assert preserved(recovered) == preserved(original)
    assert recovered["active_session_id"] is None and recovered["session_created_at"] is None
    assert recovered["is_online"] is False
    assert not {"reset_token_hash", "reset_token", "reset_expires", "reset_context_hash", "hashed_password", "password"} & recovered.keys()
    assert len(MAIL) == count + 2 and "Password Reset Complete" in MAIL[-1]["subject"]
    assert not (await expect(client, "GET", "/api/users/" + name + "/session-status", 200, headers=old_headers))["valid"]
    await expect(client, "GET", profile, 401, headers=old_headers)
    await expect(client, "GET", profile, 401)
    await expect(client, "POST", "/api/users/reset-password-confirm", 400,
                 json={"token": token, "new_password": OLD_PASSWORD})
    await expect(client, "POST", "/api/users/reset-password-direct", 410,
                 json={"email": original["email"], "new_password": OLD_PASSWORD})
    await expect(client, "POST", "/api/users/login", 401,
                 json={"username": original["username"], "password": OLD_PASSWORD})

    logged_in = await expect(client, "POST", "/api/users/login", 403 if name == "pending" else 200,
                             json={"username": original["username"].upper(), "password": NEW_PASSWORD})
    if name != "pending":
        assert logged_in["id"] == original["id"]
        assert not {"password_hash", "hashed_password", "reset_token_hash", "reset_context_hash", "billing_entitlement"} & logged_in.keys()
        first_session = logged_in["active_session_id"]
        assert first_session != original["active_session_id"]
        await expect(client, "GET", profile, 200, headers=headers(name, first_session))
        second = await expect(client, "POST", "/api/users/login", 200,
                              json={"username": original["username"], "password": NEW_PASSWORD})
        assert second["active_session_id"] != first_session
        await expect(client, "GET", profile, 401, headers=headers(name, first_session))
        await expect(client, "GET", profile, 200, headers=headers(name, second["active_session_id"]))
    assert preserved(await db.users.find_one({"id": name})) == preserved(original)
    assert len(MAIL) == count + 2
    SCENARIOS.append(name + " account: email proof, bcrypt reset, identity preservation, session revocation, access policy")


async def token_lifecycle_case(db, client):
    original = await db.users.find_one({"id": "untouched"})
    for _ in range(2):
        await expect(client, "POST", "/api/users/reset-password-request", 200,
                     json={"email": original["email"]})
    old_token, current_token = (reset_token(message) for message in MAIL[-2:])
    assert old_token != current_token
    await expect(client, "POST", "/api/users/reset-password-confirm", 400,
                 json={"token": old_token, "new_password": NEW_PASSWORD})
    # Expire only this disposable fixture to exercise the endpoint's real query.
    await db.users.update_one({"id": "untouched"}, {"$set": {"reset_expires": datetime.utcnow() - timedelta(seconds=1)}})
    await expect(client, "POST", "/api/users/reset-password-confirm", 400,
                 json={"token": current_token, "new_password": NEW_PASSWORD})
    after = await db.users.find_one({"id": "untouched"})
    assert after["password_hash"] == original["password_hash"]
    assert after["active_session_id"] == original["active_session_id"]
    assert preserved(after) == preserved(original)
    SCENARIOS.append("Superseded and expired links rejected without credential or session changes")


async def legacy_login_case(db, client, name, bcrypt):
    original = await db.users.find_one({"id": name})
    response = await expect(client, "POST", "/api/users/login", 200,
                            json={"username": original["username"], "password": OLD_PASSWORD})
    migrated = await db.users.find_one({"id": name})
    assert response["id"] == original["id"]
    assert migrated["password_hash"].startswith("$2b$")
    assert bcrypt.checkpw(OLD_PASSWORD.encode(), migrated["password_hash"].encode())
    assert "hashed_password" not in migrated
    assert preserved(migrated) == preserved(original)
    SCENARIOS.append(name + " credential: real login verifies and migrates hash on existing identity")


async def exercise(server, db, bcrypt, httpx, asyncio):
    await seed(db, bcrypt)
    users_before = await db.users.count_documents({})
    history_before = {name: await db[name].find().sort("_id", 1).to_list(None)
                      for name in ("messages", "trades", "notifications")}
    all_workers = {"periodic_cleanup", "StockAlertService.run", "NautilusSettlementService.run"}
    async with server.app.router.lifespan_context(server.app):
        await asyncio.sleep(0)
        worker_tasks = {task.get_coro().__qualname__: task for task in asyncio.all_tasks()
                        if task.get_coro().__qualname__ in all_workers}
        assert set(worker_tasks) == all_workers
        assert server.square_billing_service.settings.mode == "manual"
        assert not any(task.get_coro().__qualname__ == "SquareBillingService.run" for task in asyncio.all_tasks())
        assert len(await db.stock_alerts.index_information()) >= 3
        assert len(await db.billing_credentials.index_information()) >= 2
        assert server.db is db
        assert server.stock_alert_service.db is db
        assert server.square_billing_service.db is db
        assert server.nautilus_settlement_service.db is db

        for index, name in enumerate(("missing", "primary", "pending"), start=1):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app, client=("198.51.100." + str(index), 1000)),
                                         base_url="https://asgi.example.test") as client:
                await recovery_case(db, client, name, bcrypt)
                other = await expect(client, "GET", "/api/users/untouched/session-status", 200,
                                     headers=headers("untouched", "saved-session-untouched"))
                assert other["valid"], "Recovery revoked an unrelated member's session"

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app, client=("198.51.100.10", 1000)),
                                     base_url="https://asgi.example.test") as client:
            for name in ("alternate", "sha256"):
                await legacy_login_case(db, client, name, bcrypt)
            await token_lifecycle_case(db, client)

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app, client=("198.51.100.20", 1000)),
                                     base_url="https://asgi.example.test") as client:
            count = len(MAIL)
            for _ in range(5):
                await expect(client, "POST", "/api/users/reset-password-request", 200, json={"email": "absent@example.test"})
            await expect(client, "POST", "/api/users/reset-password-request", 429, json={"email": "absent@example.test"})
            assert len(MAIL) == count
            SCENARIOS.append("Real SlowAPI reset-request limit rejects request six; unknown email sends nothing")

        assert await db.users.count_documents({}) == users_before
        for name, expected in history_before.items():
            assert await db[name].find().sort("_id", 1).to_list(None) == expected
        assert not OUTBOUND_ATTEMPTS, (OUTBOUND_ATTEMPTS, OUTBOUND_CALLERS)
    assert all(task.done() for task in worker_tasks.values())
    assert not server.nautilus_settlement_service.inflight
    SCENARIOS.append("Actual startup and shutdown: all three workers isolated; history unchanged; no IP sockets or DNS")


def main():
    # This script is intentionally process-scoped. Clear inherited credentials
    # before importing any app/provider module and never read a dotenv file.
    os.environ.clear()
    os.environ.update({
        "MONGO_URL": MONGO_URL, "DB_NAME": DATABASE_NAME,
        "MEMBERSHIP_APPROVAL_MODE": "manual", "FRONTEND_URL": FRONTEND_URL,
        "RESEND_API_KEY": "synthetic-not-a-real-api-key",
        "SENDER_EMAIL": "capture@example.test", "ADMIN_EMAIL": "admin@example.test",
    })
    sys.addaudithook(deny_network)
    try:
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except RuntimeError:
        pass
    else:
        raise AssertionError("The IP socket denial self-test failed")
    assert OUTBOUND_ATTEMPTS == ["socket.__new__"]
    OUTBOUND_ATTEMPTS.clear()
    OUTBOUND_CALLERS.clear()
    # urllib3 otherwise probes IPv6 support by binding ::1 at import time.
    # No network capability is relevant to this deliberately offline process.
    socket.has_ipv6 = False

    import asyncio
    import bcrypt
    import dotenv
    import httpx
    import motor.motor_asyncio
    from mongomock_motor import AsyncMongoMockClient
    import resend

    fake_client = AsyncMongoMockClient()

    def isolated_client(uri, *args, **kwargs):
        assert uri == MONGO_URL and not args and not kwargs
        MONGO_CONSTRUCTIONS.append("isolated")
        return fake_client

    fcm_module = ModuleType("fcm_service")
    fcm_module.fcm_service = type("ForbiddenFCM", (), {"initialized": False})()
    sys.path.insert(0, str(BACKEND))
    with patch.object(dotenv, "load_dotenv", return_value=False), \
            patch.object(motor.motor_asyncio, "AsyncIOMotorClient", isolated_client), \
            patch.object(resend.Emails, "send", capture_resend), \
            patch.dict(sys.modules, {"fcm_service": fcm_module}):
        server = importlib.import_module("server")
        assert server.email_service is not None and type(server.email_service).__name__ == "EmailService"
        assert server.client is fake_client and server.db.name == DATABASE_NAME
        db = server.db
        asyncio.run(exercise(server, db, bcrypt, httpx, asyncio))
        assert MONGO_CONSTRUCTIONS == ["isolated"]
        assert not OUTBOUND_ATTEMPTS
    fake_client.close()
    print(json.dumps({
        "result": "PASS", "scenarios": SCENARIOS,
        "synthetic_users": 6, "captured_email_messages": len(MAIL),
        "real_emails_sent": 0, "external_network_attempts": len(OUTBOUND_ATTEMPTS),
        "ip_socket_denial_self_test": "PASS", "http_server_started": False,
        "dependencies": {name: importlib.metadata.version(name) for name in (
            "fastapi", "starlette", "pydantic", "slowapi", "bcrypt", "motor", "pymongo", "resend", "mongomock-motor")},
        "limits": ["Synthetic Mongo storage, not Atlas durability or deployed indexes",
                   "Resend SDK send captured locally, not live email delivery",
                   "Actual backend ASGI only, not browser rendering or public routing",
                   "Empty synthetic worker queues; live feeds, quotes, Square, FCM not contacted"],
    }, indent=2))


if __name__ == "__main__":
    main()
