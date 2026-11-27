"""Persisted inbox/reaction contract tests without external services or members."""
import ast
from copy import deepcopy
from datetime import datetime, timedelta
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from fastapi import APIRouter, Depends, FastAPI, Query
import httpx

from test_account_recovery import load_auth_slice
from test_stock_alerts import Collection as BaseCollection, Cursor as BaseCursor, matches
from stock_alerts import active_membership

BACKEND = Path(__file__).resolve().parents[1]


class Cursor(BaseCursor):
    def skip(self, count):
        self.docs = self.docs[count:]
        return self


class Collection(BaseCollection):
    def __init__(self, docs=()):
        super().__init__(docs)
        self.writes = 0

    def find(self, query=None):
        return Cursor([d for d in self.docs if matches(d, query or {})])

    async def update_one(self, query, update, upsert=False):
        before = deepcopy(self.docs)
        result = await super().update_one(query, update, upsert)
        self.writes += int(before != self.docs)
        return result

    async def update_many(self, query, update):
        changed = 0
        for doc in self.docs:
            if matches(doc, query):
                before = deepcopy(doc)
                self.apply(doc, update)
                changed += int(doc != before)
        self.writes += changed
        return SimpleNamespace(modified_count=changed)

    async def delete_one(self, query):
        for index, doc in enumerate(self.docs):
            if matches(doc, query):
                self.docs.pop(index)
                self.writes += 1
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)

    async def delete_many(self, query):
        old = len(self.docs)
        self.docs = [d for d in self.docs if not matches(d, query)]
        count = old - len(self.docs)
        self.writes += count
        return SimpleNamespace(deleted_count=count)

    async def count_documents(self, query):
        return sum(matches(d, query) for d in self.docs)


def load_social_slice():
    namespace = load_auth_slice()
    namespace.update(api_router=APIRouter(prefix="/api"), Query=Query, active_membership=active_membership)
    names = {"require_legacy_active_session", "get_user_notifications", "mark_notification_as_read",
             "mark_all_notifications_as_read", "delete_notification", "get_unread_notification_count",
             "normalize_reaction_type", "add_message_reaction", "remove_message_reaction", "get_message_reactions", "get_community_members"}
    statements = []
    source = BACKEND / "server.py"
    for node in ast.parse(source.read_text()).body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in {
            "REACTION_EMOJI", "REACTION_ALIASES", "LEGACY_SESSION_EXEMPT_OPERATIONS"
        } for target in node.targets):
            statements.append(node)
        elif isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name in names:
            statements.append(node)
    exec(compile(ast.Module(body=statements, type_ignores=[]), str(source), "exec"), namespace)
    app = FastAPI()
    app.include_router(namespace["api_router"], dependencies=[Depends(namespace["require_legacy_active_session"])])
    namespace["app"] = app
    return namespace


class SocialEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.n = load_social_slice()
        self.db = SimpleNamespace(
            users=Collection([
                {"id": "member", "username": "learner", "screen_name": "Learner", "active_session_id": "current-login", "status": "approved"},
                {"id": "author", "username": "coach", "active_session_id": "author-login", "status": "approved"},
            ]),
            notifications=Collection([
                {"id": "mine", "user_id": "member", "type": "follow", "read": False,
                 "created_at": datetime(2026, 11, 25), "data": {"follower_id": "author"}},
                {"id": "theirs", "user_id": "author", "type": "reply", "read": False,
                 "created_at": datetime(2026, 11, 25)},
            ]),
            messages=Collection([{"id": "message-1", "user_id": "author", "content": "Synthetic practice discussion"}]),
            reactions=Collection(),
        )
        self.awards = []
        self.notifications = []
        self.broadcasts = []
        async def award(*args):
            self.awards.append(args)
        async def notify(**kwargs):
            self.notifications.append(kwargs)
        async def broadcast(value):
            self.broadcasts.append(json.loads(value))
        self.n.update(db=self.db, award_xp=award, create_user_notification=notify,
                      manager=SimpleNamespace(broadcast=broadcast))
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.n["app"]), base_url="http://test")
        self.auth = {"X-User-ID": "member", "X-Session-ID": "current-login"}

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_member_directory_allows_ordinary_members_and_excludes_private_or_inactive_records(self):
        self.db.users.docs[0].update(email="private@example.test", real_name="Private Real Name", password_hash="private-hash", location="private-location")
        self.db.users.docs.extend([
            {"id": "pending", "username": "pending", "status": "pending"},
            {"id": "expired", "username": "expired", "status": "trial", "trial_end_date": datetime.utcnow()-timedelta(days=1)},
            {"id": "missing-date", "username": "missing-date", "status": "trial"},
            {"id": "active-trial", "username": "active-trial", "status": "trial", "trial_end_date": datetime.utcnow()+timedelta(days=1)},
        ])
        response = await self.client.get("/api/community/members", headers=self.auth)
        self.assertEqual(response.status_code, 200)
        self.assertEqual({u["id"] for u in response.json()["users"]}, {"member", "author", "active-trial"})
        allowed = {"id", "username", "screen_name", "avatar_url", "level", "is_admin", "role", "is_online", "follower_count"}
        self.assertTrue(all(set(u) == allowed for u in response.json()["users"]))
        for private in ("private@example.test", "Private Real Name", "private-hash", "current-login", "private-location"):
            self.assertNotIn(private, response.text)
        self.assertEqual((await self.client.get("/api/community/members")).status_code, 401)
        self.db.users.docs[0]["status"] = "pending"
        self.assertEqual((await self.client.get("/api/community/members", headers=self.auth)).status_code, 403)

    async def test_member_directory_is_bounded_and_reports_more_members(self):
        self.db.users.docs.extend({"id": f"id-{i}", "username": f"user-{i:03}", "status": "approved"} for i in range(205))
        response = await self.client.get("/api/community/members", headers=self.auth)
        self.assertEqual(len(response.json()["users"]), 200)
        self.assertTrue(response.json()["has_more"])
        self.assertEqual(response.json()["limit"], 200)

    async def test_loading_inbox_preserves_unread_until_explicit_read(self):
        before = deepcopy(self.db.notifications.docs)
        response = await self.client.get("/api/users/member/notifications", headers=self.auth)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([n["id"] for n in response.json()], ["mine"])
        self.assertFalse(response.json()[0]["read"])
        self.assertEqual(self.db.notifications.docs, before)
        self.assertEqual(self.db.notifications.writes, 0)
        count = await self.client.get("/api/users/member/notifications/unread-count", headers=self.auth)
        self.assertEqual(count.json()["count"], 1)
        marked = await self.client.put("/api/users/member/notifications/mine/read", headers=self.auth)
        self.assertEqual(marked.status_code, 200)
        self.assertTrue(self.db.notifications.docs[0]["read"])
        self.assertFalse(self.db.notifications.docs[1]["read"])
        count = await self.client.get("/api/users/member/notifications/unread-count", headers=self.auth)
        self.assertEqual(count.json()["count"], 0)

    async def test_notification_routes_reject_other_member_and_replaced_session(self):
        before = deepcopy(self.db.notifications.docs)
        routes = [("GET", "/api/users/author/notifications"),
                  ("GET", "/api/users/author/notifications/unread-count"),
                  ("PUT", "/api/users/author/notifications/theirs/read"),
                  ("POST", "/api/users/author/notifications/read-all"),
                  ("DELETE", "/api/users/author/notifications/theirs")]
        for method, path in routes:
            response = await self.client.request(method, path, headers=self.auth)
            self.assertEqual(response.status_code, 403, (method, path, response.text))
        self.assertEqual(self.db.notifications.docs, before)
        self.db.users.docs[0]["active_session_id"] = "replacement"
        stale = await self.client.get("/api/users/member/notifications", headers=self.auth)
        self.assertEqual(stale.status_code, 401)
        self.assertEqual(self.db.notifications.writes, 0)

    async def test_read_all_and_delete_affect_only_authenticated_owner(self):
        result = await self.client.post("/api/users/member/notifications/read-all", headers=self.auth)
        self.assertEqual(result.json()["count"], 1)
        self.assertFalse(self.db.notifications.docs[1]["read"])
        forbidden = await self.client.delete("/api/users/member/notifications/theirs", headers=self.auth)
        self.assertEqual(forbidden.status_code, 404)
        deleted = await self.client.delete("/api/users/member/notifications/mine", headers=self.auth)
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual([d["id"] for d in self.db.notifications.docs], ["theirs"])

    async def test_reaction_is_persisted_and_author_notified_once_with_correct_emoji(self):
        path = "/api/messages/message-1/react"
        body = {"user_id": "member", "reaction_type": "rocket"}
        response = await self.client.post(path, headers=self.auth, json=body)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(self.db.reactions.docs), 1)
        self.assertEqual(self.db.reactions.docs[0]["reaction_type"], "rocket")
        self.assertEqual(len(self.notifications), 1)
        self.assertEqual(self.notifications[0]["user_id"], "author")
        self.assertIn("🚀", self.notifications[0]["message"])
        self.assertEqual(self.broadcasts, [{"type": "reaction_updated", "message_id": "message-1"}])
        duplicate = await self.client.post(path, headers=self.auth, json={**body, "reaction_type": "🚀"})
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(len(self.db.reactions.docs), 1)
        self.assertEqual(len(self.awards), 1)
        self.assertEqual(len(self.notifications), 1)
        summary = await self.client.get("/api/messages/message-1/reactions", headers=self.auth)
        self.assertEqual(summary.json()["rocket"][0]["user_id"], "member")
        removed = await self.client.delete(path, headers=self.auth, params=body)
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(self.db.reactions.docs, [])
        self.assertEqual(len(self.broadcasts), 2)

    async def test_reactions_cannot_impersonate_another_member_or_use_unsupported_types(self):
        path = "/api/messages/message-1/react"
        forged = {"user_id": "author", "reaction_type": "heart"}
        self.assertEqual((await self.client.post(path, headers=self.auth, json=forged)).status_code, 403)
        self.assertEqual((await self.client.delete(path, headers=self.auth, params=forged)).status_code, 403)
        bad = await self.client.post(path, headers=self.auth, json={"user_id": "member", "reaction_type": "unsupported"})
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(self.db.reactions.docs, [])
        self.assertEqual(self.notifications, [])
        self.assertEqual(self.broadcasts, [])

    async def test_legacy_emoji_reactions_are_counted_and_removed_by_canonical_type(self):
        self.db.reactions.docs.append({"id": "legacy", "message_id": "message-1", "user_id": "member",
                                       "reaction_type": "❤️", "created_at": datetime(2026, 11, 25)})
        summary = await self.client.get("/api/messages/message-1/reactions", headers=self.auth)
        self.assertIn("heart", summary.json())
        duplicate = await self.client.post("/api/messages/message-1/react", headers=self.auth,
                                           json={"user_id": "member", "reaction_type": "heart"})
        self.assertEqual(duplicate.status_code, 400)
        removed = await self.client.delete("/api/messages/message-1/react", headers=self.auth,
                                           params={"user_id": "member", "reaction_type": "heart"})
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(self.db.reactions.docs, [])


if __name__ == "__main__":
    unittest.main()
