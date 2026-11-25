"""One-login regression tests using real server functions and an isolated ASGI app.

The source loader avoids Mongo startup, external bots, Firebase and email. Tests
use synthetic accounts/devices and exercise atomic filters and controlled races;
no production service or provider is contacted.
"""
import ast
import asyncio
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

from fastapi import APIRouter, Depends, FastAPI, HTTPException, WebSocketDisconnect
import httpx

from test_account_recovery import load_auth_slice, noop, request


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from nautilus_api import _member as nautilus_member


def load_session_slice():
    namespace = load_auth_slice()
    namespace.update({"api_router": APIRouter(prefix="/api"), "app": FastAPI(),
                      "WebSocketDisconnect": WebSocketDisconnect})
    names = {
        "require_legacy_active_session", "check_session_status", "logout_user",
        "websocket_endpoint", "get_user_profile", "get_users", "login_user", "root",
        "register_fcm_token", "get_active_fcm_tokens", "test_notification",
        "send_notification_to_user", "send_notification_to_admins", "post_message_tasks",
    }
    source = BACKEND / "server.py"
    selected = []
    for node in ast.parse(source.read_text()).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in {
            "LEGACY_SESSION_EXEMPT_OPERATIONS", "SESSION_RECHECK_SECONDS"
        } for t in node.targets):
            selected.append(node)
        elif isinstance(node, ast.AsyncFunctionDef) and node.name in names:
            # Keep real route registration; omit the WebSocket decorator because
            # socket tests drive the real endpoint with controllable test peers.
            node.decorator_list = [decorator for decorator in node.decorator_list
                                   if isinstance(decorator, ast.Call)
                                   and isinstance(decorator.func, ast.Attribute)
                                   and isinstance(decorator.func.value, ast.Name)
                                   and decorator.func.value.id == "api_router"]
            selected.append(node)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), "exec"), namespace)
    namespace["app"].include_router(namespace["api_router"], dependencies=[Depends(namespace["require_legacy_active_session"])])
    return namespace


def matches(document, query):
    for field, expected in query.items():
        if field == "$or":
            if not any(matches(document, branch) for branch in expected):
                return False
            continue
        actual = document.get(field)
        if isinstance(expected, dict):
            if "$in" in expected and actual not in expected["$in"]:
                return False
            if "$ne" in expected and actual == expected["$ne"]:
                return False
            if "$lte" in expected and (actual is None or actual > expected["$lte"]):
                return False
            if "$exists" in expected and (field in document) != expected["$exists"]:
                return False
            if "$regex" in expected:
                import re
                if not re.search(expected["$regex"], actual or "", re.I if expected.get("$options") == "i" else 0):
                    return False
        elif actual != expected:
            return False
    return True


class Cursor:
    def __init__(self, documents):
        self.documents = deepcopy(documents)

    async def to_list(self, limit):
        return self.documents[:limit]


class Collection:
    def __init__(self, documents=()):
        self.documents = deepcopy(list(documents))
        self.writes = 0
        self.before_update = None

    async def find_one(self, query, projection=None):
        return next((deepcopy(document) for document in self.documents if matches(document, query)), None)

    def find(self, query=None):
        return Cursor([document for document in self.documents if matches(document, query or {})])

    async def update_one(self, query, update, upsert=False):
        if self.before_update:
            callback, self.before_update = self.before_update, None
            await callback()
        for document in self.documents:
            if matches(document, query):
                before = deepcopy(document)
                document.update(deepcopy(update.get("$set", {})))
                for field in update.get("$unset", {}):
                    document.pop(field, None)
                self.writes += 1
                return SimpleNamespace(matched_count=1, modified_count=int(before != document))
        if upsert:
            if query.get("_id") is not None and any(d.get("_id") == query["_id"] for d in self.documents):
                error = RuntimeError("Synthetic duplicate _id")
                error.code = 11000
                raise error
            self.documents.append({**deepcopy(query), **deepcopy(update.get("$setOnInsert", {})), **deepcopy(update.get("$set", {}))})
            self.writes += 1
        return SimpleNamespace(matched_count=0, modified_count=0)

    async def find_one_and_update(self, query, update):
        # No await between matching and mutation: Mongo's operation is atomic.
        for document in self.documents:
            if matches(document, query):
                previous = deepcopy(document)
                document.update(deepcopy(update.get("$set", {})))
                self.writes += 1
                return previous
        return None


class Socket:
    def __init__(self, on_accept=None, on_receive=None):
        self.messages = []
        self.closed = []
        self.accepted = False
        self.on_accept = on_accept
        self.on_receive = on_receive
        self.receive_started = asyncio.Event()
        self.closed_event = asyncio.Event()

    async def accept(self):
        self.accepted = True
        if self.on_accept:
            await self.on_accept()

    async def send_text(self, text):
        self.messages.append(json.loads(text))

    async def receive_text(self):
        self.receive_started.set()
        if self.on_receive:
            return await self.on_receive()
        await self.closed_event.wait()
        raise WebSocketDisconnect(code=4001)

    async def close(self, code=1000, reason=""):
        self.closed.append(code)
        self.closed_event.set()


class SessionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        asyncio.get_running_loop().slow_callback_duration = 1
        self.n = load_session_slice()
        self.initial = "synthetic-initial-login"
        self.current = "synthetic-current-login"
        self.users = Collection([
            {"id": "member", "username": "learner", "email": "member@example.test",
             "password_hash": hashlib.sha256(b"test-password").hexdigest(),
             "active_session_id": self.initial, "status": "approved", "is_online": True,
             "is_admin": True, "last_login_date": datetime.utcnow().strftime("%Y-%m-%d")},
            {"id": "other", "username": "other", "email": "other@example.test",
             "active_session_id": "synthetic-other-login", "status": "approved", "is_online": True},
        ])
        self.devices = Collection()
        self.n.update({"db": SimpleNamespace(users=self.users, fcm_tokens=self.devices),
                       "manager": self.n["ConnectionManager"](), "SESSION_RECHECK_SECONDS": 0.01,
                       "hash_password": lambda password: hashlib.sha256(password.encode()).hexdigest(),
                       "process_login_rewards_async": noop, "get_level_from_xp": lambda value: 1,
                       "award_xp": noop, "handle_message_mentions": noop})
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.n["app"]), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()

    def headers(self, token=None, user="member"):
        return {"X-User-ID": user, "X-Session-ID": token or self.initial}

    async def test_replaced_session_blocked_on_real_legacy_reads_current_allowed(self):
        self.users.documents[0]["active_session_id"] = self.current
        for path in ("/api/users", "/api/users/member/profile"):
            for headers in ({}, self.headers()):
                response = await self.client.get(path, headers=headers)
                self.assertEqual(response.status_code, 401)
            response = await self.client.get(path, headers=self.headers(self.current))
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(self.current, response.text)
        response = await self.client.get("/api/")
        self.assertEqual(response.status_code, 200)

    async def test_gate_is_wired_to_legacy_router_and_has_no_prefix_bypasses(self):
        tree = ast.parse((BACKEND / "server.py").read_text())
        mounts = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == "include_router"
                  and node.args and isinstance(node.args[0], ast.Name) and node.args[0].id == "api_router"]
        self.assertEqual(len(mounts), 1)
        self.assertTrue(any(keyword.arg == "dependencies" and "require_legacy_active_session" in ast.unparse(keyword.value)
                            for keyword in mounts[0].keywords))
        for method, route in (("POST", "/api/bot/message/extra"), ("GET", "/api/users/login"),
                              ("POST", "/api/users/approve"), ("GET", "/api/email/test")):
            scope = {"type": "http", "method": method, "headers": [], "route": SimpleNamespace(path=route)}
            with self.assertRaises(HTTPException) as caught:
                await self.n["require_legacy_active_session"](self.n["Request"](scope))
            self.assertEqual(caught.exception.status_code, 401)
        scope = {"type": "http", "method": "OPTIONS", "headers": [], "route": SimpleNamespace(path="/api/users")}
        await self.n["require_legacy_active_session"](self.n["Request"](scope))

    async def test_status_headers_and_legacy_query_return_only_validity(self):
        self.users.documents[0]["active_session_id"] = self.current
        stale = await self.client.get("/api/users/member/session-status", headers=self.headers())
        current = await self.client.get("/api/users/member/session-status", headers=self.headers(self.current))
        legacy = await self.client.get("/api/users/member/session-status", params={"session_id": self.current})
        anonymous = await self.client.get("/api/users/member/session-status")
        for response in (stale, current, legacy, anonymous):
            self.assertEqual(response.status_code, 200)
            self.assertEqual(set(response.json()), {"valid", "message"})
        self.assertFalse(stale.json()["valid"])
        self.assertFalse(anonymous.json()["valid"])
        self.assertTrue(current.json()["valid"])
        self.assertTrue(legacy.json()["valid"])

    async def test_stale_logout_is_noop_current_logout_revokes_only_its_session(self):
        self.users.documents[0]["active_session_id"] = self.current
        socket = Socket()
        await self.n["manager"].connect(socket, "member", self.current)
        stale = await self.client.post("/api/users/logout?user_id=member", headers=self.headers())
        self.assertEqual(stale.status_code, 200)
        self.assertEqual(self.users.documents[0]["active_session_id"], self.current)
        self.assertFalse(socket.closed)
        missing = await self.client.post("/api/users/logout?user_id=member")
        self.assertEqual(missing.status_code, 401)
        current = await self.client.post("/api/users/logout?user_id=member", headers=self.headers(self.current))
        self.assertEqual(current.status_code, 200)
        self.assertIsNone(self.users.documents[0]["active_session_id"])
        self.assertIn(4001, socket.closed)
        again = await self.client.post("/api/users/logout?user_id=member", headers=self.headers(self.current))
        self.assertEqual(again.status_code, 200)

    async def test_logout_racing_replacement_cannot_clear_new_login(self):
        async def replace_before_write():
            self.users.documents[0]["active_session_id"] = self.current
        self.users.before_update = replace_before_write
        response = await self.client.post("/api/users/logout?user_id=member", headers=self.headers())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.users.documents[0]["active_session_id"], self.current)

    async def test_concurrent_logins_revoke_exact_predecessors_after_commit(self):
        paused, release = asyncio.Event(), asyncio.Event()
        base = self.n["ConnectionManager"]
        initial = self.initial
        class DelayedInvalidation(base):
            async def send_session_invalidation(manager, user_id, revoked_session_id=None):
                if revoked_session_id == initial:
                    paused.set()
                    await release.wait()
                await super().send_session_invalidation(user_id, revoked_session_id)
        manager = DelayedInvalidation()
        self.n["manager"] = manager
        original_socket = Socket()
        await manager.connect(original_socket, "member", self.initial)
        body = self.n["UserLogin"](username="learner", password="test-password")
        first_task = asyncio.create_task(self.n["login_user"](body))
        await asyncio.wait_for(paused.wait(), 1)
        first_session = self.users.documents[0]["active_session_id"]
        self.assertNotEqual(first_session, self.initial)  # Commit precedes notification.
        first_socket = Socket()
        await manager.connect(first_socket, "member", first_session)
        second = await self.n["login_user"](body)
        second_socket = Socket()
        await manager.connect(second_socket, "member", second.active_session_id)
        release.set()
        first = await asyncio.wait_for(first_task, 1)
        self.assertEqual(first.active_session_id, first_session)
        self.assertEqual(self.users.documents[0]["active_session_id"], second.active_session_id)
        self.assertTrue(original_socket.closed)
        self.assertTrue(first_socket.closed)
        self.assertFalse(second_socket.closed)
        self.assertIs(manager.user_connections["member"], second_socket)
        rejected = await self.client.get("/api/users", headers=self.headers(first.active_session_id))
        self.assertEqual(rejected.status_code, 401)

    async def test_outbound_delivery_revalidates_sessions_across_workers(self):
        old_socket, new_socket = Socket(), Socket()
        manager = self.n["manager"]
        await manager.connect(old_socket, "member", self.initial)
        self.users.documents[0]["active_session_id"] = self.current
        await manager.connect(new_socket, "member", self.current)
        await manager.broadcast(json.dumps({"type": "message", "content": "synthetic private update"}))
        self.assertFalse(any(message.get("content") == "synthetic private update" for message in old_socket.messages))
        self.assertTrue(old_socket.closed)
        self.assertTrue(any(message.get("content") == "synthetic private update" for message in new_socket.messages))
        self.assertFalse(new_socket.closed)

    async def test_quiet_socket_is_revalidated_without_waiting_for_a_heartbeat(self):
        socket = Socket()
        task = asyncio.create_task(self.n["websocket_endpoint"](socket, "member", self.initial))
        await asyncio.wait_for(socket.receive_started.wait(), 1)
        self.users.documents[0]["active_session_id"] = self.current
        await asyncio.wait_for(task, 1)
        self.assertIn(4001, socket.closed)
        self.assertTrue(self.users.documents[0]["is_online"])

    async def test_handshake_race_and_old_disconnect_preserve_replacement_presence(self):
        async def replace():
            self.users.documents[0]["active_session_id"] = self.current
        handshake = Socket(on_accept=replace)
        await self.n["websocket_endpoint"](handshake, "member", self.initial)
        self.assertIn(4001, handshake.closed)
        self.assertFalse(any(message["type"] == "online_users" for message in handshake.messages))
        self.assertTrue(self.users.documents[0]["is_online"])
        self.users.documents[0]["active_session_id"] = self.initial
        async def replace_then_disconnect():
            await replace()
            raise WebSocketDisconnect()
        old = Socket(on_receive=replace_then_disconnect)
        await self.n["websocket_endpoint"](old, "member", self.initial)
        self.assertTrue(self.users.documents[0]["is_online"])
        self.assertFalse(any(message["type"] == "user_left" for message in old.messages))

    async def test_nautilus_rejects_replaced_member_session(self):
        self.users.documents[0]["active_session_id"] = self.current
        with self.assertRaises(HTTPException) as caught:
            await nautilus_member(request(self.headers()), self.n["db"])
        self.assertEqual(caught.exception.status_code, 401)
        current = await nautilus_member(request(self.headers(self.current)), self.n["db"])
        self.assertEqual(current["id"], "member")

    async def test_fcm_registration_rejects_wrong_actor_and_replaced_session(self):
        wrong = await self.client.post("/api/fcm/register-token", headers=self.headers(),
                                       json={"user_id": "other", "token": "synthetic-device"})
        self.assertEqual(wrong.status_code, 403)
        self.users.documents[0]["active_session_id"] = self.current
        stale = await self.client.post("/api/fcm/register-token", headers=self.headers(),
                                       json={"user_id": "member", "token": "synthetic-device"})
        self.assertEqual(stale.status_code, 401)
        self.assertEqual(self.devices.writes, 0)

    async def test_fcm_registration_is_bound_without_storing_session_credential(self):
        response = await self.client.post("/api/fcm/register-token", headers=self.headers(),
                                          json={"user_id": "member", "token": "synthetic-device"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.devices.documents[0]["session_fingerprint"], hashlib.sha256(self.initial.encode()).hexdigest())
        self.assertNotIn(self.initial, json.dumps(self.devices.documents, default=str))
        self.assertEqual(len(await self.n["get_active_fcm_tokens"](["member"])), 1)
        self.users.documents[0]["active_session_id"] = self.current
        self.assertEqual(await self.n["get_active_fcm_tokens"](["member"]), [])

    async def test_late_fcm_registration_cannot_become_replacement_device(self):
        async def replace_before_device_write():
            self.users.documents[0]["active_session_id"] = self.current
        self.devices.before_update = replace_before_device_write
        response = await self.client.post("/api/fcm/register-token", headers=self.headers(),
                                          json={"user_id": "member", "token": "synthetic-old-device"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(await self.n["get_active_fcm_tokens"](["member"]), [])

    async def test_late_browser_registration_cannot_reclaim_newer_token_owner(self):
        async def another_account_registers_during_older_request():
            response = await self.client.post("/api/fcm/register-token", headers=self.headers("synthetic-other-login", "other"),
                                              json={"user_id": "other", "token": "shared-browser-token"})
            self.assertEqual(response.status_code, 200)
        self.devices.before_update = another_account_registers_during_older_request
        response = await self.client.post("/api/fcm/register-token", headers=self.headers(),
                                          json={"user_id": "member", "token": "shared-browser-token"})
        self.assertEqual(response.status_code, 200)
        owner = next(d for d in self.devices.documents if d.get("_id", "").startswith("token-owner:"))
        self.assertEqual(owner["owner_user_id"], "other")
        self.assertEqual(owner["owner_session_fingerprint"], hashlib.sha256(b"synthetic-other-login").hexdigest())

    async def test_historical_devices_cannot_hide_the_current_registration(self):
        self.devices.documents = [
            {"user_id": "member", "token": "synthetic-old-device", "session_fingerprint": f"old-{index}"}
            for index in range(1001)
        ] + [{"user_id": "member", "token": "synthetic-current-device",
              "session_fingerprint": hashlib.sha256(self.initial.encode()).hexdigest()}]
        current = await self.n["get_active_fcm_tokens"](["member"])
        self.assertEqual([item["token"] for item in current], ["synthetic-current-device"])

    async def test_legacy_push_paths_are_suppressed_and_current_device_filter_is_preserved(self):
        self.devices.documents = [
            {"user_id": "member", "token": "synthetic-current-device", "session_fingerprint": hashlib.sha256(self.initial.encode()).hexdigest()},
            {"user_id": "member", "token": "synthetic-stale-device", "session_fingerprint": "older-fingerprint"},
            {"user_id": "other", "token": "synthetic-unbound-device"},
        ]
        selected = await self.n["get_active_fcm_tokens"](["member", "other"])
        self.assertEqual([item["token"] for item in selected], ["synthetic-current-device"])
        deliveries = []
        async def send_notification(**kwargs):
            deliveries.append([kwargs["token"]])
            return True
        async def send_to_multiple(**kwargs):
            deliveries.append(kwargs["tokens"])
            return {"success_count": len(kwargs["tokens"])}
        provider = SimpleNamespace(initialized=True, send_notification=send_notification, send_to_multiple=send_to_multiple)
        with patch.dict(sys.modules, {"fcm_service": SimpleNamespace(fcm_service=provider)}):
            await self.n["send_notification_to_user"]("member", "Synthetic", "Test")
            await self.n["send_notification_to_admins"]("Synthetic", "Test")
            await self.n["post_message_tasks"](
                SimpleNamespace(user_id="coach", reply_to_id=None, content_type="text", content="Synthetic notice"),
                SimpleNamespace(id="message"), {"id": "coach", "username": "coach", "is_admin": True}, None
            )
        self.assertEqual(deliveries, [])
        self.users.documents[0]["active_session_id"] = None
        self.assertEqual(await self.n["get_active_fcm_tokens"](["member", "other"]), [])


if __name__ == "__main__":
    unittest.main()
