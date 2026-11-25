"""Isolated tests of real server recovery/serialization functions, without Mongo,
email delivery, Firebase or starting the legacy application's background tasks.
The AST loader strips route/rate-limit decorators only; function bodies are the
same source used by server.py. Full deployment integration remains a separate gate.
"""
import ast
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import secrets
import sys
from types import SimpleNamespace
from typing import Optional, List, Dict, Any, Union
import unittest
import uuid

from fastapi import BackgroundTasks, HTTPException, Request, WebSocket
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from membership import active_membership, MEMBERSHIP_REQUIRED, utc_datetime, iso_date
from account_credentials import password_record


def load_auth_slice():
    source = Path(__file__).resolve().parents[1] / "server.py"
    tree = ast.parse(source.read_text())
    names = {
        "redact_auth_fields", "public_socket_message", "UserStatus", "UserRole",
        "User", "AuthenticatedUser", "UserCreate", "UserLogin", "PasswordChange",
        "PasswordResetRequest", "PasswordResetConfirm", "ConnectionManager",
        "validate_new_password", "require_profile_owner", "hash_password", "verify_password",
        "migrate_password_if_needed", "register_user", "login_user",
        "request_password_reset", "direct_password_reset", "confirm_password_reset",
        "send_password_reset_email", "get_users",
    }
    selected = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "AUTH_PRIVATE_FIELDS" for t in node.targets):
            selected.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in names:
            if hasattr(node, "decorator_list"):
                node.decorator_list = []
            selected.append(node)
    namespace = dict(globals())
    namespace["logger"] = logging.getLogger("cashout.auth.test")
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), "exec"), namespace)
    return namespace


def matches(document, filters):
    for key, value in filters.items():
        actual = document.get(key)
        if isinstance(value, dict):
            if "$regex" in value:
                if re.search(value["$regex"], actual or "", re.I if value.get("$options") == "i" else 0) is None:
                    return False
            elif "$gt" in value and (actual is None or actual <= value["$gt"]):
                return False
            elif "$ne" in value and actual == value["$ne"]:
                return False
        elif actual != value:
            return False
    return True


class MemoryUsers:
    def __init__(self, documents):
        self.documents = deepcopy(documents)
        self.writes = 0

    async def find_one(self, filters, projection=None):
        return next((deepcopy(doc) for doc in self.documents if matches(doc, filters)), None)

    def find(self, filters=None):
        result = [deepcopy(doc) for doc in self.documents if matches(doc, filters or {})]
        async def to_list(limit):
            return result[:limit]
        return SimpleNamespace(to_list=to_list)

    async def insert_one(self, document):
        self.documents.append(deepcopy(document))
        self.writes += 1
        return SimpleNamespace(inserted_id=document.get("id"))

    async def update_one(self, filters, update):
        for doc in self.documents:
            if matches(doc, filters):
                before = deepcopy(doc)
                doc.update(update.get("$set", {}))
                for key in update.get("$unset", {}):
                    doc.pop(key, None)
                self.writes += 1
                return SimpleNamespace(matched_count=1, modified_count=int(doc != before))
        return SimpleNamespace(matched_count=0, modified_count=0)

    async def find_one_and_update(self, filters, update):
        # No suspension between match and mutation: models Mongo's atomic CAS.
        for doc in self.documents:
            if matches(doc, filters):
                before = deepcopy(doc)
                doc.update(update.get("$set", {}))
                for key in update.get("$unset", {}):
                    doc.pop(key, None)
                self.writes += 1
                return before
        return None


class FakeManager:
    def __init__(self):
        self.invalidated = []
        self.notifications = []

    async def send_session_invalidation(self, user_id, *_):
        self.invalidated.append(user_id)

    async def send_admin_notification(self, message):
        self.notifications.append(message)


class EmailRecorder:
    def __init__(self):
        self.sent = []

    async def send_email(self, *args):
        self.sent.append(args)
        return True

    async def send_registration_notification(self, *args):
        return True


async def noop(*args, **kwargs):
    return None


def request(headers=None):
    return Request({"type": "http", "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]})


class AccountRecoveryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.n = load_auth_slice()
        self.original = {
            "id": "member-a", "username": "ariam", "email": "ariam@example.test", "status": "approved",
            "password_hash": hashlib.sha256(b"old-password").hexdigest(),
            "active_session_id": "private-active-session", "is_online": True,
            "session_created_at": datetime.utcnow(), "last_login_date": datetime.utcnow().strftime("%Y-%m-%d"),
        }
        self.users = MemoryUsers([self.original])
        self.n.update({
            "db": SimpleNamespace(users=self.users), "email_service": EmailRecorder(), "manager": FakeManager(),
            "send_password_reset_confirmation": noop, "send_registration_confirmation_to_user": noop,
            "send_notification_to_admins": noop, "handle_referral_signup": noop,
            "process_login_rewards_async": noop, "get_level_from_xp": lambda value: 1,
            "generate_referral_code": lambda username: "TEST1234",
        })
        # Password hashing itself is not re-tested here. Fast deterministic hashes
        # let these tests focus on endpoint ownership, state, races and serialization.
        self.n["hash_password"] = lambda password: hashlib.sha256(password.encode()).hexdigest()

    async def test_email_only_direct_reset_is_disabled_without_a_write(self):
        with self.assertRaises(HTTPException) as caught:
            await self.n["direct_password_reset"]()
        self.assertEqual(caught.exception.status_code, 410)
        self.assertEqual(self.users.writes, 0)

    async def test_request_only_emails_token_and_never_changes_password(self):
        tasks = BackgroundTasks()
        response = await self.n["request_password_reset"](request(), self.n["PasswordResetRequest"](email="ARIAM@example.test"), tasks)
        doc = self.users.documents[0]
        self.assertEqual(doc["password_hash"], self.original["password_hash"])
        self.assertNotIn("reset_token", doc)
        self.assertEqual(len(tasks.tasks), 1)
        token = tasks.tasks[0].args[2]
        self.assertEqual(doc["reset_token_hash"], hashlib.sha256(token.encode()).hexdigest())
        self.assertNotIn(token, json.dumps(response))
        missing_tasks = BackgroundTasks()
        absent_response = await self.n["request_password_reset"](request(), self.n["PasswordResetRequest"](email="absent@example.test"), missing_tasks)
        self.assertEqual(response, absent_response)
        self.assertFalse(missing_tasks.tasks)
        await tasks()
        email = self.n["email_service"].sent[0]
        self.assertIn(f"/?reset_token={token}", email[2])
        self.assertNotIn("/reset-password?", email[2])

    async def test_email_service_unavailable_fails_before_mutating(self):
        self.n["email_service"] = None
        with self.assertRaises(HTTPException) as caught:
            await self.n["request_password_reset"](request(), self.n["PasswordResetRequest"](email="ariam@example.test"), BackgroundTasks())
        self.assertEqual(caught.exception.status_code, 503)
        self.assertEqual(self.users.writes, 0)

    async def test_confirm_is_one_time_atomic_and_revokes_session(self):
        token = "verified-email-token-" + "x" * 32
        self.users.documents[0].update({"reset_token_hash": hashlib.sha256(token.encode()).hexdigest(), "reset_expires": datetime.utcnow() + timedelta(minutes=10)})
        body = self.n["PasswordResetConfirm"](token=token, new_password="new-password")
        results = await asyncio.gather(*[
            self.n["confirm_password_reset"](request(), body, BackgroundTasks()) for _ in range(2)
        ], return_exceptions=True)
        self.assertEqual(sum(isinstance(r, dict) for r in results), 1)
        self.assertEqual(sum(isinstance(r, HTTPException) and r.status_code == 400 for r in results), 1)
        doc = self.users.documents[0]
        self.assertEqual(doc["password_hash"], hashlib.sha256(b"new-password").hexdigest())
        self.assertIsNone(doc["active_session_id"])
        self.assertFalse(doc["is_online"])
        self.assertNotIn("reset_token_hash", doc)
        self.assertNotIn("reset_expires", doc)
        self.assertEqual(self.n["manager"].invalidated, ["member-a"])

    async def test_expired_or_incorrect_tokens_cannot_change_password(self):
        token = "expired-" + "x" * 40
        self.users.documents[0].update({"reset_token_hash": hashlib.sha256(token.encode()).hexdigest(), "reset_expires": datetime.utcnow() - timedelta(seconds=1)})
        for presented in (token, "wrong-" + "z" * 40):
            with self.assertRaises(HTTPException) as caught:
                await self.n["confirm_password_reset"](request(), self.n["PasswordResetConfirm"](token=presented, new_password="new-password"), BackgroundTasks())
            self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(self.users.documents[0]["password_hash"], self.original["password_hash"])
        self.assertEqual(self.users.writes, 0)

    async def test_public_user_and_notifications_exclude_tokens(self):
        public = self.n["User"](**{**self.original, "reset_token_hash": "reset-secret"}).model_dump()
        self.assertNotIn("active_session_id", public)
        self.assertNotIn("session_created_at", public)
        self.assertNotIn("password_hash", public)
        self.assertNotIn("reset_token_hash", public)
        users = await self.n["get_users"]()
        self.assertNotIn("active_session_id", users[0].model_dump())
        message = self.n["public_socket_message"](json.dumps({"type": "user_approval", "user": {
            **self.original, "nested": [{"reset_token": "reset-secret"}],
            "billing_entitlement": {"payment_ids": ["private-payment-id"]},
            "manual_access_granted_by": "private-approving-admin",
            "billing_token": "private-billing-token",
        }}, default=str))
        self.assertNotIn("private-active-session", message)
        self.assertNotIn("reset-secret", message)
        self.assertNotIn("password_hash", message)
        self.assertNotIn("private-payment-id", message)
        self.assertNotIn("private-approving-admin", message)
        self.assertNotIn("private-billing-token", message)
        self.assertIn("ariam", message)

    async def test_only_verified_login_returns_active_session(self):
        body = self.n["UserLogin"](username="ariam", password="old-password")
        result = await self.n["login_user"](body)
        serialized = result.model_dump()
        self.assertIn("active_session_id", serialized)
        self.assertEqual(serialized["active_session_id"], self.users.documents[0]["active_session_id"])
        self.assertNotEqual(serialized["active_session_id"], self.original["active_session_id"])
        self.assertNotIn("password_hash", serialized)
        self.users.documents[0].pop("password_hash")
        with self.assertRaises(HTTPException) as caught:
            await self.n["login_user"](body)
        self.assertEqual(caught.exception.status_code, 401)

    async def test_registration_persists_hash_and_does_not_promote_admin_username(self):
        self.users.documents = []
        body = self.n["UserCreate"](username="admin", email="new@example.test", real_name="New member", membership_plan="Member", password="new-password")
        result = await self.n["register_user"](request(), body, BackgroundTasks())
        self.assertEqual(self.users.documents[0]["password_hash"], hashlib.sha256(b"new-password").hexdigest())
        self.assertEqual(result.status, self.n["UserStatus"].PENDING)
        self.assertFalse(result.is_admin)
        self.assertNotIn("password_hash", result.model_dump())

    async def test_duplicate_registration_preserves_existing_identity_and_social_history(self):
        for status in ("approved", "pending", "rejected", "trial", "trial_expired"):
            original = {
                **self.original, "username": " ExistingMember ", "email": " Member@Example.Test ", "status": status,
                "bio": "Existing profile", "avatar_url": "https://example.test/avatar.png",
                "profile_banner": "existing-banner", "membership_plan": "Lifetime", "role": "member",
                "experience_points": 1500, "level": 3, "achievements": ["existing-badge"],
                "followers": ["friend-a"], "following": ["friend-b"], "referral_code": "EXISTING",
            }
            for name, email in (("existingmember", "new@example.test"), ("different-user", "MEMBER@example.test")):
                with self.subTest(status=status, collision="username" if name == "existingmember" else "email"):
                    self.users.documents = [deepcopy(original)]
                    self.users.writes = 0
                    # Related collections deliberately cannot be deleted by this
                    # public operation; a regression would fail the test.
                    related = {"messages": [{"user_id": original["id"], "content": "Existing message"}],
                               "notifications": [{"user_id": original["id"], "type": "follow"}],
                               "trades": [{"user_id": original["id"], "symbol": "AAPL"}]}
                    self.n["db"] = SimpleNamespace(users=self.users, **deepcopy(related))
                    tasks = BackgroundTasks()
                    body = self.n["UserCreate"](username=" " + name + " ", email=" " + email + " ",
                        real_name="Attempted replacement", membership_plan="Monthly", password="another-password")
                    with self.assertRaises(HTTPException) as error:
                        await self.n["register_user"](request(), body, tasks)
                    self.assertEqual(error.exception.status_code, 409)
                    self.assertIn("password recovery", error.exception.detail)
                    self.assertEqual(self.users.documents, [original])
                    self.assertEqual(self.users.writes, 0)
                    self.assertEqual(tasks.tasks, [])
                    for collection, documents in related.items():
                        self.assertEqual(getattr(self.n["db"], collection), documents)

    async def test_new_registration_normalizes_only_new_submission(self):
        self.users.documents = []
        body = self.n["UserCreate"](username="  NewMember  ", email="  NEW@Example.Test  ",
            real_name="New Member", membership_plan="Monthly", password="new-password")
        result = await self.n["register_user"](request(), body, BackgroundTasks())
        self.assertEqual(result.username, "NewMember")
        self.assertEqual(result.email, "new@example.test")
        self.assertEqual(self.users.documents[0]["id"], result.id)
        self.assertEqual(result.status, self.n["UserStatus"].PENDING)
        self.assertEqual(body.username, "  NewMember  ")

    async def test_new_trials_rejected_before_any_account_or_background_change(self):
        historic_trial = {**self.original, "id": "historic-trial", "username": "trial-member", "email": "trial@example.test",
                          "status": "trial", "membership_plan": "14-Day Trial", "trial_end_date": datetime.utcnow()+timedelta(days=3),
                          "experience_points": 250, "following": ["member-a"]}
        self.users.documents.append(historic_trial)
        before = deepcopy(self.users.documents)
        for plan, flag in (("Monthly", True), ("Yearly", "true"), ("Lifetime", 1),
                           ("14-Day Trial", False), (" trial ", False), ("14 DAY FREE TrIaL", None),
                           ("t r i a l", False), ("14-day tr\u200bial", False),
                           ("ＴＲＩＡＬ", False), ("tríal", False)):
            with self.subTest(plan=plan, flag=flag):
                tasks = BackgroundTasks()
                body = self.n["UserCreate"](username="new-user", email="new@example.test", real_name="New member",
                    membership_plan=plan, is_trial=flag, password="new-password")
                with self.assertRaises(HTTPException) as error:
                    await self.n["register_user"](request(), body, tasks)
                self.assertEqual(error.exception.status_code, 403)
                self.assertIn("trial registrations are currently disabled", error.exception.detail)
                self.assertEqual(self.users.documents, before)
                self.assertEqual(self.users.writes, 0)
                self.assertEqual(tasks.tasks, [])
                self.assertEqual(self.n["manager"].notifications, [])
                self.assertEqual(self.n["email_service"].sent, [])

    async def test_paid_registration_defaults_pending_without_trial_or_verified_payment(self):
        for index, plan in enumerate(("Monthly", "Yearly", "Lifetime")):
            body = self.n["UserCreate"](username=f"paid-{index}", email=f"paid-{index}@example.test", real_name="New member",
                membership_plan=plan, password="new-password")
            result = await self.n["register_user"](request(), body, BackgroundTasks())
            self.assertEqual(result.membership_plan, plan)
            self.assertEqual(result.status, self.n["UserStatus"].PENDING)
            self.assertIsNone(result.trial_start_date)
            self.assertIsNone(result.trial_end_date)
            self.assertFalse(result.is_admin)
        self.assertEqual(self.users.documents[0], self.original)

    async def test_verified_alternate_hash_can_migrate_without_a_second_registration(self):
        old_hash = self.users.documents[0].pop("password_hash")
        self.users.documents[0]["hashed_password"] = old_hash
        with self.assertRaises(HTTPException) as rejected:
            await self.n["login_user"](self.n["UserLogin"](username="ariam", password="incorrect"))
        self.assertEqual(rejected.exception.status_code, 401)
        self.assertEqual(self.users.writes, 0)
        result = await self.n["login_user"](self.n["UserLogin"](username="ariam", password="old-password"))
        self.assertEqual(result.id, self.original["id"])
        self.assertEqual(self.users.documents[0]["password_hash"], old_hash)
        self.assertNotIn("hashed_password", self.users.documents[0])

    async def test_alternate_hash_never_overrides_an_existing_primary_credential(self):
        self.users.documents[0]["hashed_password"] = hashlib.sha256(b"stale-password").hexdigest()
        with self.assertRaises(HTTPException) as rejected:
            await self.n["login_user"](self.n["UserLogin"](username="ariam", password="stale-password"))
        self.assertEqual(rejected.exception.status_code, 401)
        self.assertEqual(self.users.writes, 0)
        self.users.documents[0].pop("password_hash")
        self.users.documents[0]["hashed_password"] = "plaintext-is-not-a-hash"
        with self.assertRaises(HTTPException) as rejected:
            await self.n["login_user"](self.n["UserLogin"](username="ariam", password="plaintext-is-not-a-hash"))
        self.assertEqual(rejected.exception.status_code, 401)
        self.assertEqual(self.users.writes, 0)

    async def test_alternate_migration_cannot_overwrite_a_concurrent_password_reset(self):
        old_hash = self.users.documents[0].pop("password_hash")
        self.users.documents[0]["hashed_password"] = old_hash
        original_update = self.users.update_one
        reset_hash = hashlib.sha256(b"new-reset-password").hexdigest()
        async def raced_update(filters, update):
            if "hashed_password" in filters:
                self.users.documents[0]["password_hash"] = reset_hash
            return await original_update(filters, update)
        self.users.update_one = raced_update
        with self.assertRaises(HTTPException) as rejected:
            await self.n["login_user"](self.n["UserLogin"](username="ariam", password="old-password"))
        self.assertEqual(rejected.exception.status_code, 401)
        self.assertEqual(self.users.documents[0]["password_hash"], reset_hash)
        self.assertEqual(self.users.documents[0]["active_session_id"], self.original["active_session_id"])

    async def test_missing_legacy_hash_recovers_same_identity_without_new_registration(self):
        self.users.documents[0].pop("password_hash")
        self.users.documents[0].update(
            bio="Existing profile", avatar_url="existing-photo", profile_banner="existing-banner",
            following=["mentor"], followers=["friend"], experience_points=1234,
            billing_entitlement={"managed_by": "manual_payment", "lifetime": True, "plan_id": "lifetime"},
        )
        preserved = deepcopy(self.users.documents[0])
        with self.assertRaises(HTTPException) as rejected:
            await self.n["login_user"](self.n["UserLogin"](username="ariam", password="anything"))
        self.assertEqual(rejected.exception.status_code, 401)
        self.assertEqual(self.users.writes, 0)
        tasks = BackgroundTasks()
        await self.n["request_password_reset"](request(), self.n["PasswordResetRequest"](email="ariam@example.test"), tasks)
        token = tasks.tasks[0].args[2]
        await self.n["confirm_password_reset"](request(),
            self.n["PasswordResetConfirm"](token=token, new_password="restored-password"), BackgroundTasks())
        for field in ("id", "email", "username", "status", "bio", "avatar_url", "profile_banner", "following", "followers", "experience_points", "billing_entitlement"):
            self.assertEqual(self.users.documents[0][field], preserved[field], field)
        self.assertEqual(len(self.users.documents), 1)
        self.assertEqual(self.users.documents[0]["password_hash"], hashlib.sha256(b"restored-password").hexdigest())
        result = await self.n["login_user"](self.n["UserLogin"](username="ariam", password="restored-password"))
        self.assertEqual(result.id, preserved["id"])
        self.assertEqual(result.status, self.n["UserStatus"].APPROVED)
        self.assertEqual(self.n["email_service"].sent, [])  # Tasks use a local recorder only.

    async def test_existing_trial_sign_in_accepts_timezone_aware_end_date(self):
        original_end = datetime.now(timezone.utc) + timedelta(days=3)
        self.users.documents[0].update(status="trial", membership_plan="14-Day Trial", trial_end_date=original_end)
        result = await self.n["login_user"](self.n["UserLogin"](username="ariam", password="old-password"))
        self.assertEqual(result.id, self.original["id"])
        self.assertEqual(result.status, self.n["UserStatus"].TRIAL)
        self.assertEqual(result.trial_end_date, original_end)
        self.assertEqual(self.users.documents[0]["trial_end_date"], original_end)

    async def test_existing_trial_can_still_sign_in_with_original_plan_and_expiration(self):
        original_end = datetime.utcnow()+timedelta(days=3)
        self.users.documents[0].update(status="trial", membership_plan="14-Day Trial", trial_end_date=original_end,
                                      bio="Preserved profile", following=["another-member"], experience_points=200)
        result = await self.n["login_user"](self.n["UserLogin"](username="ariam", password="old-password"))
        self.assertEqual(result.id, self.original["id"])
        self.assertEqual(result.status, self.n["UserStatus"].TRIAL)
        self.assertEqual(result.membership_plan, "14-Day Trial")
        self.assertEqual(result.trial_end_date, original_end)
        self.assertEqual(result.bio, "Preserved profile")
        self.assertEqual(result.following, ["another-member"])
        self.assertEqual(result.experience_points, 200)

    async def test_recovery_email_changes_require_correct_member_session(self):
        for headers in ({}, {"X-User-ID": "member-a", "X-Session-ID": "wrong"}, {"X-User-ID": "another-member", "X-Session-ID": "private-active-session"}):
            with self.assertRaises(HTTPException):
                await self.n["require_profile_owner"](request(headers), "member-a")
        user = await self.n["require_profile_owner"](request({"X-User-ID": "member-a", "X-Session-ID": "private-active-session"}), "member-a")
        self.assertEqual(user["id"], "member-a")
        self.assertEqual(self.users.writes, 0)

    async def test_socket_invalidation_never_sends_replacement_session(self):
        class Socket:
            def __init__(self):
                self.messages = []
                self.closed = False
            async def send_text(self, message):
                self.messages.append(message)
            async def close(self, **kwargs):
                self.closed = True
        manager = self.n["ConnectionManager"]()
        socket = Socket()
        manager.active_connections.append(socket)
        manager.user_connections["member-a"] = socket
        await manager.send_session_invalidation("member-a", "replacement-session-secret")
        self.assertNotIn("replacement-session-secret", "".join(socket.messages))
        self.assertTrue(socket.closed)
        self.assertNotIn("member-a", manager.user_connections)
        manager.disconnect(socket, "member-a")  # Repeated cleanup remains safe.


if __name__ == "__main__":
    unittest.main()
