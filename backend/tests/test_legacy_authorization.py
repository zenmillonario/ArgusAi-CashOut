"""Legacy authorization and identity-preservation regressions, no external I/O.

Register the real routes and the production router dependency in an isolated ASGI
app. Forged actor IDs must fail before the legacy handlers can mutate a record.
"""
import ast
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from fastapi import APIRouter, Depends, FastAPI
import httpx

from test_account_recovery import load_auth_slice
from test_social_endpoints import Collection as BaseCollection

BACKEND = Path(__file__).resolve().parents[1]


class Collection(BaseCollection):
    async def find_one(self, query, projection=None):
        return await super().find_one(query)

    def apply(self, document, update):
        super().apply(document, update)
        for field, value in update.get("$addToSet", {}).items():
            values = value.get("$each", []) if isinstance(value, dict) else [value]
            existing = document.setdefault(field, [])
            for item in values:
                if item not in existing:
                    existing.append(deepcopy(item))

    def find(self, query=None, projection=None):
        cursor = super().find(query)
        if projection:
            included = {field for field, value in projection.items() if value and field != "_id"}
            if included:
                cursor.docs = [{k: v for k, v in doc.items() if k in included} for doc in cursor.docs]
            else:
                cursor.docs = [{k: v for k, v in doc.items() if projection.get(k) != 0} for doc in cursor.docs]
        return cursor


def load_legacy_slice():
    namespace = load_auth_slice()
    namespace.update(api_router=APIRouter(prefix="/api"))
    names = {
        "require_legacy_active_session", "require_authenticated_admin",
        "get_users", "get_pending_users", "get_user_profile",
        "check_email_config", "test_email_service", "fcm_status",
        "get_pending_cash_prizes", "get_trial_expired_users", "get_all_trial_users",
        "remove_user", "allow_rejected_user_reregistration", "award_user_xp",
        "delete_message", "cleanup_debug_messages", "create_message",
        "follow_user", "unfollow_user", "update_user_theme", "get_user_referrals",
        "get_user_positions", "get_user_trades", "get_user_trade_history", "get_user_performance",
        "create_paper_trade", "position_action", "close_position", "change_password",
        "check_achievements", "review_cash_prize",
    }
    selected = []
    source = BACKEND / "server.py"
    for node in ast.parse(source.read_text()).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in {"LEGACY_SESSION_EXEMPT_OPERATIONS", "ACHIEVEMENTS"} for t in node.targets):
            selected.append(node)
        elif isinstance(node, ast.ClassDef) and node.name not in {"ConnectionManager", "FCMToken"}:
            selected.append(node)
        elif isinstance(node, ast.AsyncFunctionDef) and node.name in names:
            selected.append(node)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), "exec"), namespace)
    app = FastAPI()
    app.include_router(namespace["api_router"], dependencies=[Depends(namespace["require_legacy_active_session"])])
    namespace["app"] = app
    return namespace


class LegacyAuthorizationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        asyncio.get_running_loop().slow_callback_duration = 1
        self.n = load_legacy_slice()
        self.users = Collection([
            {"id": "member", "username": "member", "email": "member@example.test", "status": "approved",
             "active_session_id": "member-session", "is_admin": False, "show_location": False, "location": "Private location"},
            {"id": "other", "username": "other", "email": "other@example.test", "status": "approved",
             "active_session_id": "other-session", "show_location": False, "location": "Other private location"},
            {"id": "admin", "username": "admin", "email": "admin@example.test", "status": "approved",
             "active_session_id": "admin-session", "is_admin": True},
            {"id": "rejected", "username": "returning", "email": "returning@example.test", "status": "rejected",
             "password_hash": "unchanged-password-hash", "active_session_id": "old-rejected-session",
             "avatar_url": "data:image/png;base64,old", "following": ["member"], "experience_points": 123,
             "billing_entitlement": {"managed_by": "manual_payment", "plan_id": "six_month", "paid_through": "2026-01-01T00:00:00Z"}},
        ])
        self.messages = Collection([{"id": "message-1", "user_id": "other", "content": "Existing discussion"}])
        self.invalidations = []
        async def invalidated(*args):
            self.invalidations.append(args)
        self.n.update(db=SimpleNamespace(users=self.users, messages=self.messages),
                      manager=SimpleNamespace(send_session_invalidation=invalidated), email_service=None)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.n["app"]), base_url="http://test")
        self.auth = {"X-User-ID": "member", "X-Session-ID": "member-session"}
        self.admin = {"X-User-ID": "admin", "X-Session-ID": "admin-session"}

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_member_cannot_read_admin_data_or_trigger_diagnostics(self):
        for path in ("/api/users", "/api/users/pending", "/api/email/check", "/api/email/test",
                     "/api/fcm/status", "/api/admin/cash-prizes/pending?admin_id=admin",
                     "/api/admin/trial-expired-users", "/api/admin/trial-users"):
            response = await self.client.get(path, headers=self.auth)
            self.assertEqual(response.status_code, 403, (path, response.text))
        self.assertEqual(self.users.writes, 0)

    async def test_forged_admin_ids_cannot_mutate_accounts_rewards_or_messages(self):
        operations = [
            ("DELETE", "/api/users/other?admin_id=admin", None),
            ("POST", "/api/admin/allow-reregistration?user_id=rejected&admin_id=admin", None),
            ("POST", "/api/users/member/award-xp", {"action": "invented", "points": 99999}),
            ("DELETE", "/api/messages/message-1?user_id=admin", None),
            ("DELETE", "/api/messages/cleanup/debug?user_id=admin", None),
        ]
        before = deepcopy(self.users.docs)
        for method, path, body in operations:
            response = await self.client.request(method, path, headers=self.auth, json=body)
            self.assertEqual(response.status_code, 403, (method, path, response.text))
        self.assertEqual(self.users.docs, before)
        self.assertEqual(self.users.writes, 0)
        self.assertEqual(self.messages.writes, 0)

    async def test_private_reads_and_writes_cannot_select_another_member(self):
        operations = [
            ("GET", "/api/positions/other", None),
            ("GET", "/api/trades/other", None),
            ("GET", "/api/trades/other/history", None),
            ("GET", "/api/users/other/performance", None),
            ("GET", "/api/users/other/referrals", None),
            ("POST", "/api/users/other/follow", {"target_user_id": "member"}),
            ("POST", "/api/users/other/unfollow", {"target_user_id": "member"}),
            ("POST", "/api/users/other/theme", {"theme_name": "golden"}),
            ("POST", "/api/trades?user_id=other", {"symbol": "AAPL", "action": "BUY", "quantity": 1, "price": 100}),
            ("POST", "/api/positions/position-1/action?user_id=other", {"action": "SELL_ALL"}),
            ("POST", "/api/positions/position-1/close?user_id=other", None),
            ("POST", "/api/users/change-password?user_id=other", {"current_password": "anything", "new_password": "replacement"}),
        ]
        for method, path, body in operations:
            response = await self.client.request(method, path, headers=self.auth, json=body)
            self.assertEqual(response.status_code, 403, (method, path, response.text))
        self.assertEqual(self.users.writes, 0)

    async def test_message_author_must_match_current_login(self):
        response = await self.client.post("/api/messages", headers=self.auth,
                                          json={"user_id": "admin", "content": "Forged administrator message"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.messages.writes, 0)
        self.assertEqual(len(self.messages.docs), 1)

    async def test_location_privacy_is_applied_to_json_and_owner_can_edit_existing_value(self):
        own = await self.client.get("/api/users/member/profile", headers=self.auth)
        other = await self.client.get("/api/users/member/profile", headers={"X-User-ID": "other", "X-Session-ID": "other-session"})
        self.assertEqual(own.status_code, 200)
        self.assertEqual(own.json()["location"], "Private location")
        self.assertEqual(other.status_code, 200)
        self.assertIsNone(other.json()["location"])
        self.assertNotIn("Private location", other.text)
        self.users.docs[0]["show_location"] = True
        shared = await self.client.get("/api/users/member/profile", headers=self.admin)
        self.assertEqual(shared.json()["location"], "Private location")

    async def test_admin_listing_still_works_and_expired_term_does_not_lock_out_management(self):
        self.users.docs[2]["billing_entitlement"] = {
            "managed_by": "manual_payment", "paid_through": "2020-01-01T00:00:00Z", "lifetime": False,
        }
        response = await self.client.get("/api/users", headers=self.admin)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn("admin-session", response.text)
        private_room = await self.client.get("/api/users/admin/profile", headers=self.admin)
        self.assertEqual(private_room.status_code, 403)

    async def test_even_an_admin_cannot_claim_another_admin_actor(self):
        response = await self.client.post("/api/admin/allow-reregistration?user_id=rejected&admin_id=member", headers=self.admin)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.users.writes, 0)
        response = await self.client.delete("/api/messages/message-1?user_id=member", headers=self.admin)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.messages.writes, 0)

    async def test_reopen_review_preserves_identity_credentials_history_and_requires_reapproval(self):
        before = deepcopy(self.users.docs[3])
        response = await self.client.post("/api/admin/allow-reregistration?user_id=rejected&admin_id=admin", headers=self.admin)
        self.assertEqual(response.status_code, 200, response.text)
        after = self.users.docs[3]
        for field in ("id", "username", "email", "password_hash", "avatar_url", "following", "experience_points", "billing_entitlement"):
            self.assertEqual(after[field], before[field], field)
        self.assertEqual(after["status"], "pending")
        self.assertIsNone(after["active_session_id"])
        self.assertEqual(after["reopened_by"], "admin")
        self.assertEqual(self.invalidations, [("rejected", "old-rejected-session")])
        self.assertEqual(len(self.users.docs), 4)
        self.assertEqual(len(self.messages.docs), 1)
        self.assertEqual(self.messages.writes, 0)
        self.assertEqual(response.json()["user_id"], "rejected")

    async def test_admin_lists_accept_legacy_iso_and_timezone_aware_trial_dates(self):
        self.users.docs.append({
            "id": "trial", "username": "trial", "email": "trial@example.test", "status": "trial",
            "trial_start_date": "2026-11-01T10:00:00Z",
            "trial_end_date": datetime.now(timezone.utc) + timedelta(days=1),
            "created_at": "2026-11-01T10:00:00-04:00",
        })
        self.users.docs.append({
            "id": "expired", "username": "expired", "email": "expired@example.test", "status": "trial_expired",
            "trial_end_date": "2020-11-01T10:00:00Z", "created_at": datetime(2020, 10, 1),
        })
        for path in ("/api/users/pending", "/api/admin/trial-users", "/api/admin/trial-expired-users"):
            response = await self.client.get(path, headers=self.admin)
            self.assertEqual(response.status_code, 200, (path, response.text))
        self.assertEqual(self.users.writes, 0)

    async def test_referral_badge_keeps_xp_without_creating_a_cash_award(self):
        self.users.docs[0].update(successful_referrals=1, achievements=[], achievement_progress={},
                                  cash_prizes=[{"historical": True}], pending_cash_review=[{"historical": True}])
        awards, announcements = [], []
        async def award(*args):
            awards.append(args)
        async def announced(*args, **kwargs):
            announcements.append((args, kwargs))
        async def forbidden_cash(*args, **kwargs):
            self.fail("A referral must not create a cash award")
        self.n.update(award_xp=award, share_achievement_in_chat=announced,
                      create_user_notification=announced, create_pending_cash_prize=forbidden_cash)
        await self.n["check_achievements"]("member", "referral_success", {})
        self.assertIn("referral_master", self.users.docs[0]["achievements"])
        self.assertEqual(awards, [("member", "achievement_unlocked", 200)])
        self.assertEqual(self.users.docs[0]["cash_prizes"], [{"historical": True}])
        self.assertEqual(self.users.docs[0]["pending_cash_review"], [{"historical": True}])
        self.assertFalse(self.n["ACHIEVEMENTS"]["referral_master"]["cash_prize_eligible"])
        self.assertNotIn("max_cash_prize", self.n["ACHIEVEMENTS"]["referral_master"])

    async def test_cash_reward_approval_is_disabled_even_for_admin(self):
        response = await self.client.post("/api/admin/cash-prizes/review?admin_id=admin", headers=self.admin,
            json={"user_id": "member", "achievement_id": "referral_master", "status": "approved", "amount": 400})
        self.assertEqual(response.status_code, 410, response.text)
        self.assertEqual(self.users.writes, 0)
        self.assertEqual(self.messages.writes, 0)

    async def test_replaced_session_cannot_use_admin_privileges(self):
        self.users.docs[2]["active_session_id"] = "replacement"
        response = await self.client.get("/api/users", headers=self.admin)
        self.assertEqual(response.status_code, 401)
        response = await self.client.post("/api/admin/allow-reregistration?user_id=rejected&admin_id=admin", headers=self.admin)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.users.writes, 0)


if __name__ == "__main__":
    unittest.main()
