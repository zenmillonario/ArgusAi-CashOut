"""Real event routes and account/billing functions with synthetic storage/email.

No server lifespan, external provider, real member, or network connection is
used. Controlled interleavings exercise the actual account CAS operations.
"""
import asyncio
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import os
import re
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import HTTPException

import test_square_billing as billing
import test_manual_billing as manual
from test_account_recovery import noop, request
from test_single_session import Socket
from membership import active_membership, membership_snapshot
from nautilus_api import _member as nautilus_member
from practice_event import CAMPAIGN_END, CAMPAIGN_ID, PracticeEventService, PracticeEventSettings, TOKEN_FIELDS


class EventCollection(billing.Collection):
    @staticmethod
    def apply(row, update, inserted=False):
        billing.Collection.apply(row, update, inserted)
        for key in update.get("$unset", {}):
            row.pop(key, None)

    async def insert_one(self, row):
        row = deepcopy(row)
        row.setdefault("_id", row.get("id"))
        for key in ("registration_email_key", "registration_username_key"):
            if key in row and any(other.get(key) == row[key] for other in self.rows):
                error = RuntimeError("Synthetic normalized registration key conflict")
                error.code = 11000
                raise error
        return await super().insert_one(row)


class PracticeEventTests(unittest.IsolatedAsyncioTestCase):
    asyncTearDown = billing.SquareBillingTests.asyncTearDown
    user = billing.SquareBillingTests.user
    approve = manual.ManualBillingTests.approve

    async def asyncSetUp(self):
        await manual.ManualBillingTests.asyncSetUp(self)
        self.clock = datetime(2026, 11, 26, 12)
        self.environment = patch.dict(os.environ, {
            "PRACTICE_EVENT_ENABLED": "true", "PRACTICE_EVENT_STARTS_AT": "2026-11-25T00:00:00Z",
            "FRONTEND_URL": "https://event.example.test",
            "ADMIN_EMAIL": "admin@example.test",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.db.users = EventCollection(self.db.users.rows)
        self.db.practice_event_limits = EventCollection()
        self.captured = []
        self.admin_notices = []

        async def capture_admin(recipient, data):
            self.admin_notices.append((recipient, deepcopy(data)))
            return True
        self.outcome = {"status": "sent", "provider_message_id": "synthetic-event-email"}

        async def capture(*args, **kwargs):
            self.captured.append(args)
            if isinstance(self.outcome, Exception):
                raise self.outcome
            return self.outcome

        self.event = PracticeEventService(self.db, email_sender=capture, now=lambda: self.clock)
        self.app.include_router(self.event.router())
        self.n.update(practice_event_service=self.event, generate_referral_code=lambda _: "SYNTHETIC",
                      send_registration_confirmation_to_user=noop, send_notification_to_admins=noop,
                      handle_referral_signup=noop, send_trial_upgrade_email=noop,
                      send_password_reset_confirmation=noop, process_login_rewards_async=noop,
                      get_level_from_xp=lambda _: 1,
                      hash_password=lambda password: hashlib.sha256(password.encode()).hexdigest(),
                      email_service=SimpleNamespace(send_email=capture, send_registration_notification=noop,
                                                    send_event_registration_notification=capture_admin))
        self.n["manager"].send_session_invalidation = noop
        test = self

        class ClockDateTime(datetime):
            @classmethod
            def utcnow(cls):
                return test.clock

        self.n["datetime"] = ClockDateTime
        for path, name, model in (
            ("/api/users/register", "register_user", "User"),
            ("/api/users/login", "login_user", "AuthenticatedUser"),
            ("/api/users/reset-password-request", "request_password_reset", None),
            ("/api/users/reset-password-confirm", "confirm_password_reset", None),
        ):
            self.app.add_api_route(path, self.n[name], methods=["POST"],
                                   response_model=self.n[model] if model else None)

    async def verification(self, email="learner@example.test"):
        response = await self.client.post("/api/practice-event/request", json={"email": email, "campaign_id": CAMPAIGN_ID})
        self.assertEqual(response.status_code, 200, response.text)
        return re.search(r"event_token=([A-Za-z0-9_-]+)", self.captured[-1][2]).group(1)

    async def confirm(self, token):
        return await self.client.post("/api/practice-event/confirm", json={"token": token})

    async def enroll(self):
        result = await self.confirm(await self.verification())
        self.assertEqual(result.status_code, 200, result.text)
        return result

    async def test_default_config_fails_closed_until_enabled_with_a_start(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = PracticeEventSettings.from_env()
            self.assertEqual(settings.status(self.clock), "disabled")
        for settings in (PracticeEventSettings(), PracticeEventSettings(enabled=True)):
            self.event.settings = settings
            config = (await self.client.get("/api/practice-event")).json()
            self.assertEqual(config["status"], "disabled")
            self.assertEqual(config["ends_at"], "2026-12-01T05:00:00.000Z")
            result = await self.client.post("/api/practice-event/request", json={
                "email": "learner@example.test", "campaign_id": CAMPAIGN_ID})
            self.assertEqual(result.status_code, 409)
        self.assertFalse(self.captured)
        self.assertEqual((await self.user())["status"], "pending")

    async def test_future_start_and_wrong_campaign_cannot_enroll(self):
        self.event.settings = replace(self.event.settings, starts_at=self.clock + timedelta(hours=1))
        self.assertEqual((await self.client.get("/api/practice-event")).json()["status"], "scheduled")
        for campaign in (CAMPAIGN_ID, "arbitrary-free-plan"):
            result = await self.client.post("/api/practice-event/request", json={"email": "learner@example.test", "campaign_id": campaign})
            self.assertEqual(result.status_code, 409)
        self.assertFalse(self.captured)

    async def test_request_proves_nothing_and_confirmation_keeps_same_identity(self):
        original = await self.user()
        token = await self.verification(" LEARNER@example.test ")
        requested = await self.user()
        self.assertEqual(requested["status"], "pending")
        self.assertFalse(active_membership(requested, self.clock))
        self.assertNotIn(token, str(requested))
        self.assertEqual(requested["practice_event_token_hash"], hashlib.sha256(token.encode()).hexdigest())
        self.assertIn("does not sign you in or change your password", self.captured[-1][2])
        self.assertEqual((await self.client.get("/api/practice-event/confirm", params={"token": token})).status_code, 405)
        result = await self.confirm(token)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["access"], "practice_event")
        self.assertTrue(result.json()["sign_in_required"])
        self.assertNotIn("active_session_id", result.json())
        user = await self.user()
        for field in ("id", "password_hash", "active_session_id", "bio", "followers", "experience_points"):
            self.assertEqual(user[field], original[field], field)
        self.assertEqual(user["trial_end_date"], CAMPAIGN_END)
        self.assertTrue(active_membership(user, self.clock))
        self.assertTrue(all(field not in user for field in TOKEN_FIELDS))
        status = (await self.client.get("/api/billing/status", headers=self.member_headers)).json()
        self.assertEqual(status["practice_event"]["state"], "enrolled")
        self.assertEqual(status["entitlement"]["source"], "practice_event")
        self.assertEqual(status["entitlement"]["trial_ends_at"], "2026-12-01T05:00:00.000Z")

    async def test_real_signup_stays_pending_until_email_confirmation(self):
        result = await self.client.post("/api/users/register", json={
            "username": "new-learner", "email": "new@example.test", "real_name": "New Learner",
            "password": "good-password", "membership_plan": "Practice event", "practice_event_id": CAMPAIGN_ID,
        })
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["status"], "pending")
        user_id = result.json()["id"]
        self.assertFalse(self.captured)
        self.assertEqual(self.admin_notices, [("admin@example.test", {
            "username": "new-learner", "email": "new@example.test",
        })])
        token = await self.verification("new@example.test")
        self.assertEqual((await self.confirm(token)).status_code, 200)
        self.assertEqual(len(self.admin_notices), 1)
        saved = await self.db.users.find_one({"id": user_id})
        self.assertTrue(active_membership(saved, self.clock))
        login = await self.client.post("/api/users/login", json={"username": "new-learner", "password": "good-password"})
        self.assertEqual(login.status_code, 200, login.text)
        self.assertEqual(login.json()["id"], user_id)

    async def test_event_plan_label_and_old_trial_flags_cannot_grant_access(self):
        base = {"username": "new-learner", "email": "new@example.test", "real_name": "New Learner",
                "password": "good-password", "membership_plan": "Practice event"}
        for changes in ({"practice_event_id": "invented"},
                        {"practice_event_id": CAMPAIGN_ID, "is_trial": True},
                        {"practice_event_id": CAMPAIGN_ID, "membership_plan": "7DaysTrial"}):
            result = await self.client.post("/api/users/register", json={**base, **changes})
            self.assertIn(result.status_code, (403, 409), result.text)
        result = await self.client.post("/api/users/register", json=base)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["status"], "pending")
        self.assertFalse(active_membership(await self.db.users.find_one({"id": result.json()["id"]}), self.clock))

    async def test_concurrent_registration_keeps_one_new_identity(self):
        payload = {"username": "new-learner", "email": "new@example.test", "real_name": "New Learner",
                   "password": "good-password", "membership_plan": "Practice event", "practice_event_id": CAMPAIGN_ID}
        results = await asyncio.gather(*(self.client.post("/api/users/register", json=payload) for _ in range(5)))
        self.assertEqual(sum(response.status_code == 200 for response in results), 1)
        self.assertTrue(all(response.status_code in (200, 409) for response in results))
        self.assertEqual(sum(row.get("email") == "new@example.test" for row in self.db.users.rows), 1)
        self.assertEqual(len(self.admin_notices), 1)

    async def test_existing_registration_is_never_recreated(self):
        original = await self.user()
        result = await self.client.post("/api/users/register", json={
            "username": "replacement", "email": "LEARNER@example.test", "real_name": "Other Name",
            "password": "replacement-password", "membership_plan": "Practice event", "practice_event_id": CAMPAIGN_ID,
        })
        self.assertEqual(result.status_code, 409)
        self.assertEqual(await self.user(), original)
        self.assertEqual(self.admin_notices, [])

    async def test_profile_identity_updates_keep_normalized_registration_keys_current(self):
        await self.enroll()
        result = await self.client.put("/api/users/member/profile", headers=self.member_headers,
                                       json={"username": " Renamed-Learner ", "email": " NEW-ADDRESS@example.test "})
        self.assertEqual(result.status_code, 200, result.text)
        user = await self.user()
        self.assertEqual(user["id"], "member")
        self.assertEqual(user["username"], "Renamed-Learner")
        self.assertEqual(user["registration_username_key"], "renamed-learner")
        self.assertEqual(user["email"], "new-address@example.test")
        self.assertEqual(user["registration_email_key"], "new-address@example.test")
        self.assertFalse(active_membership(user, self.clock))
        self.assertEqual((await self.confirm(await self.verification("new-address@example.test"))).status_code, 200)
        self.assertTrue(active_membership(await self.user(), self.clock))

    async def test_profile_identity_updates_reject_case_variants_owned_by_other_members(self):
        await self.enroll()
        before = await self.user()
        for body in ({"username": " OTHER "}, {"email": " OTHER@example.test "}):
            result = await self.client.put("/api/users/member/profile", headers=self.member_headers, json=body)
            self.assertEqual(result.status_code, 400, result.text)
        self.assertEqual(await self.user(), before)

    async def test_request_is_generic_for_missing_disabled_and_rejected_accounts(self):
        self.db.users.rows.extend([
            {"id": "blocked", "_id": "blocked", "email": "blocked@example.test", "status": "pending", "disabled": True},
            {"id": "rejected", "_id": "rejected", "email": "rejected@example.test", "status": "rejected"},
        ])
        bodies = []
        for email in ("learner@example.test", "missing@example.test", "blocked@example.test", "rejected@example.test"):
            result = await self.client.post("/api/practice-event/request", json={"email": email, "campaign_id": CAMPAIGN_ID})
            self.assertEqual(result.status_code, 200)
            bodies.append(result.json())
        self.assertTrue(all(body == bodies[0] for body in bodies))
        self.assertEqual(len(self.captured), 1)

    async def test_verification_link_is_one_use_and_new_request_supersedes_old(self):
        first = await self.verification()
        second = await self.verification()
        self.assertNotEqual(first, second)
        self.assertEqual((await self.confirm(first)).status_code, 400)
        self.assertEqual((await self.confirm(second)).status_code, 200)
        self.assertEqual((await self.confirm(second)).status_code, 400)

    async def test_verification_expires_in_one_hour_or_at_cutoff(self):
        token = await self.verification()
        self.clock += timedelta(hours=1)
        self.assertEqual((await self.confirm(token)).status_code, 400)
        self.clock = CAMPAIGN_END - timedelta(minutes=2)
        token = await self.verification()
        self.assertEqual((await self.user())["practice_event_token_expires"], CAMPAIGN_END)
        self.clock = CAMPAIGN_END
        self.assertEqual((await self.confirm(token)).status_code, 409)
        self.assertEqual((await self.client.get("/api/practice-event")).json()["status"], "ended")
        self.assertEqual((await self.user())["status"], "pending")

    async def test_changed_email_credential_or_access_state_invalidates_link(self):
        original = await self.user()
        for change in ({"email": "changed@example.test"}, {"password_hash": "new-credential"},
                       {"status": "rejected"}, {"disabled": True}):
            with self.subTest(change=change):
                self.db.users.rows[0] = deepcopy(original)
                self.db.practice_event_limits = EventCollection()
                token = await self.verification()
                self.db.users.rows[0].update(change)
                before = await self.user()
                self.assertEqual((await self.confirm(token)).status_code, 400)
                self.assertEqual(await self.user(), before)

    async def test_password_reset_token_cannot_be_used_for_event_or_reverse(self):
        event_token = await self.verification()
        reset = await self.client.post("/api/users/reset-password-confirm", json={
            "token": event_token, "new_password": "replacement-password"})
        self.assertEqual(reset.status_code, 400)
        self.db.users.rows[0].update(reset_token_hash=hashlib.sha256(b"r" * 43).hexdigest(), reset_expires=self.clock + timedelta(hours=1))
        self.assertEqual((await self.confirm("r" * 43)).status_code, 400)
        self.assertEqual((await self.confirm(event_token)).status_code, 200)
        self.assertIn("reset_token_hash", await self.user())

    async def test_hashless_existing_account_keeps_identity_and_uses_separate_recovery(self):
        self.db.users.rows[0].pop("password_hash")
        original = await self.user()
        await self.enroll()
        self.assertNotIn("password_hash", await self.user())
        self.assertEqual((await self.client.post("/api/users/login", json={"username": "learner", "password": "anything"})).status_code, 401)
        reset_request = await self.client.post("/api/users/reset-password-request", json={"email": "learner@example.test"})
        self.assertEqual(reset_request.status_code, 200, reset_request.text)
        token = re.search(r"reset_token=([A-Za-z0-9_-]+)", self.captured[-1][2]).group(1)
        reset = await self.client.post("/api/users/reset-password-confirm", json={"token": token, "new_password": "new-password"})
        self.assertEqual(reset.status_code, 200, reset.text)
        user = await self.user()
        for field in ("id", "bio", "followers", "experience_points"):
            self.assertEqual(user[field], original[field])
        self.assertTrue(active_membership(user, self.clock))
        self.assertEqual((await self.client.post("/api/users/login", json={"username": "learner", "password": "new-password"})).status_code, 200)

    async def test_paid_approval_wins_a_confirmation_race(self):
        token = await self.verification()

        async def approve_between_read_and_confirm(query, update):
            self.db.users.before_update = None
            result = await self.approve()
            self.assertEqual(result.status_code, 200, result.text)

        self.db.users.before_update = approve_between_read_and_confirm
        result = await self.confirm(token)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["access"], "existing")
        user = await self.user()
        self.assertEqual(user["status"], "approved")
        self.assertEqual(membership_snapshot(user, self.clock)["source"], "manual_payment")
        self.assertNotIn("practice_event_grant", user)
        self.assertEqual(len(self.sent), 1)

    async def test_paid_conversion_during_event_survives_the_cutoff(self):
        await self.enroll()
        self.assertEqual((await self.approve(plan="six_months")).status_code, 200)
        before = await self.user()
        self.clock = CAMPAIGN_END
        status = (await self.client.get("/api/billing/status", headers=self.member_headers)).json()
        self.assertTrue(status["entitlement"]["active"])
        self.assertEqual(status["entitlement"]["source"], "manual_payment")
        self.assertEqual(status["practice_event"]["state"], "existing_access")
        self.assertEqual((await self.user())["billing_entitlement"], before["billing_entitlement"])
        cleanup = manual.ManualBillingTests.trial_cleanup(self)
        self.clock += timedelta(seconds=1)
        await cleanup()
        self.assertEqual((await self.user())["status"], "approved")
        self.assertTrue(active_membership(await self.user(), self.clock))
        self.assertFalse(self.trial_emails)

    async def test_expired_paid_history_is_retained_after_event_access_ends(self):
        self.db.users.rows[0].update(status="approved", billing_entitlement={
            "managed_by": "manual_payment", "paid_through": self.clock - timedelta(days=2),
            "plan_id": "monthly", "version": 1,
        })
        paid = deepcopy((await self.user())["billing_entitlement"])
        await self.enroll()
        self.assertEqual(membership_snapshot(await self.user(), self.clock)["source"], "practice_event")
        self.clock = CAMPAIGN_END
        status = (await self.client.get("/api/billing/status", headers=self.member_headers)).json()
        self.assertFalse(status["entitlement"]["active"])
        self.assertEqual(status["entitlement"]["source"], "manual_payment")
        self.assertIsNotNone(status["entitlement"]["paid_through"])
        self.assertEqual(status["practice_event"]["state"], "ended")
        self.assertEqual((await self.user())["billing_entitlement"], paid)

    async def test_existing_active_legacy_trial_keeps_its_original_dates(self):
        self.db.users.rows[0].update(status="trial", trial_start_date=self.clock - timedelta(days=1),
                                   trial_end_date=CAMPAIGN_END + timedelta(days=2))
        original = await self.user()
        result = await self.enroll()
        self.assertEqual(result.json()["access"], "existing")
        user = await self.user()
        self.assertEqual(user["trial_start_date"], original["trial_start_date"])
        self.assertEqual(user["trial_end_date"], original["trial_end_date"])
        self.assertNotIn("practice_event_trial", user)
        self.assertTrue(active_membership(user, CAMPAIGN_END + timedelta(days=1)))

    async def test_existing_paid_lifetime_complimentary_and_legacy_access_are_preserved(self):
        original = await self.user()
        for change in (
            {"status": "approved", "billing_entitlement": {"managed_by": "manual_payment", "paid_through": CAMPAIGN_END + timedelta(days=20)}},
            {"status": "approved", "billing_entitlement": {"managed_by": "manual_payment", "lifetime": True}},
            {"status": "approved", "billing_entitlement": {}, "manual_access_granted": True},
            {"status": "approved"},
        ):
            with self.subTest(change=change):
                self.db.users.rows[0] = {**deepcopy(original), **deepcopy(change)}
                self.db.practice_event_limits = EventCollection()
                before = await self.user()
                result = await self.enroll()
                self.assertEqual(result.json()["access"], "existing")
                user = await self.user()
                self.assertNotIn("practice_event_grant", user)
                self.assertTrue(active_membership(user, CAMPAIGN_END + timedelta(days=1)))
                for field in before:
                    self.assertEqual(user[field], before[field], field)

    async def test_repeated_enrollment_keeps_original_grant_and_shared_deadline(self):
        await self.enroll()
        first = await self.user()
        self.clock += timedelta(hours=2)
        await self.enroll()
        second = await self.user()
        self.assertEqual(second["id"], first["id"])
        self.assertEqual(second["practice_event_grant"]["enrolled_at"], first["practice_event_grant"]["enrolled_at"])
        self.assertEqual(second["trial_start_date"], first["trial_start_date"])
        self.assertEqual(second["trial_end_date"], CAMPAIGN_END)
        self.assertEqual(second["practice_event_grant"]["ends_at"], CAMPAIGN_END)

    async def test_concurrent_confirmation_applies_only_one_grant(self):
        token = await self.verification()
        results = await asyncio.gather(*(self.confirm(token) for _ in range(5)))
        self.assertEqual(sum(result.status_code == 200 for result in results), 1)
        self.assertTrue(all(result.status_code in (200, 400) for result in results))
        self.assertEqual((await self.user())["trial_end_date"], CAMPAIGN_END)

    async def test_exact_cutoff_stops_http_nautilus_and_open_socket_without_cleanup(self):
        await self.enroll()
        self.clock = CAMPAIGN_END - timedelta(microseconds=1)
        self.assertEqual((await self.client.get("/api/member-probe", headers=self.member_headers)).status_code, 200)
        manager = self.n["ConnectionManager"]()
        socket = Socket()
        await manager.connect(socket, "member", "existing-session")
        self.assertTrue(await manager.validate_connection(socket))
        self.clock = CAMPAIGN_END
        self.assertEqual((await self.client.get("/api/member-probe", headers=self.member_headers)).status_code, 403)
        self.assertFalse(await manager.validate_connection(socket))
        self.assertIn(4403, socket.closed)
        with patch("nautilus_api.time.time", return_value=self.clock.replace(tzinfo=timezone.utc).timestamp()):
            with self.assertRaises(HTTPException) as denied:
                await nautilus_member(request(self.member_headers), self.db)
            self.assertEqual(denied.exception.status_code, 403)
        self.assertEqual((await self.user())["status"], "trial")
        self.assertEqual((await self.user())["active_session_id"], "existing-session")
        status = (await self.client.get("/api/billing/status", headers=self.member_headers)).json()
        self.assertFalse(status["entitlement"]["active"])
        self.assertEqual(status["practice_event"]["state"], "ended")

    async def test_disabling_event_does_not_fall_back_to_the_legacy_trial_date(self):
        await self.enroll()
        with patch.dict(os.environ, {"PRACTICE_EVENT_ENABLED": "false"}):
            self.assertFalse(active_membership(await self.user(), self.clock))
            self.assertEqual((await self.client.get("/api/member-probe", headers=self.member_headers)).status_code, 403)

    async def test_missing_or_failed_email_never_grants_access(self):
        sender = self.event.email_sender
        self.event.email_sender = None
        result = await self.client.post("/api/practice-event/request", json={"email": "learner@example.test", "campaign_id": CAMPAIGN_ID})
        self.assertEqual(result.status_code, 503)
        self.assertNotIn("practice_event_token_hash", await self.user())
        self.event.email_sender = sender
        self.outcome = {"status": "failed"}
        await self.verification()
        self.assertEqual((await self.user())["practice_event_email_status"], "failed")
        self.assertFalse(active_membership(await self.user(), self.clock))

    async def test_request_throttles_ip_and_email_without_account_enumeration(self):
        for _ in range(3):
            self.assertEqual((await self.client.post("/api/practice-event/request", json={
                "email": "absent@example.test", "campaign_id": CAMPAIGN_ID})).status_code, 200)
        self.assertEqual((await self.client.post("/api/practice-event/request", json={
            "email": "ABSENT@example.test", "campaign_id": CAMPAIGN_ID})).status_code, 429)
        self.db.practice_event_limits = EventCollection()
        for index in range(5):
            self.assertEqual((await self.client.post("/api/practice-event/request", json={
                "email": f"absent-{index}@example.test", "campaign_id": CAMPAIGN_ID})).status_code, 200)
        self.assertEqual((await self.client.post("/api/practice-event/request", json={
            "email": "sixth@example.test", "campaign_id": CAMPAIGN_ID})).status_code, 429)
        self.assertFalse(self.captured)

    async def test_tokens_grants_and_registration_keys_are_redacted_from_public_data(self):
        await self.verification()
        user = await self.user()
        user.update(practice_event_grant={"verified_email": "private@example.test"}, practice_event_trial=True,
                    registration_email_key="private@example.test", registration_username_key="learner")
        public = self.n["redact_auth_fields"]({"data": user})["data"]
        self.assertFalse(any(key.startswith("practice_event_") or key.startswith("registration_") for key in public))


if __name__ == "__main__":
    unittest.main()
