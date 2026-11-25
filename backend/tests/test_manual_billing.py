"""Administrator-reviewed one-time access with synthetic accounts and senders."""
import ast
import asyncio
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
from html import escape
import logging
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Optional
import unittest
from unittest.mock import patch

from fastapi import BackgroundTasks

import test_square_billing as billing
from membership import active_membership, membership_snapshot
from square_billing import ManualApprovalRequest, SquareProblem, SquareSettings, add_months


class ManualBillingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await billing.SquareBillingTests.asyncSetUp(self)
        # Deliberately retain ALL old Square credentials/enable flags. Manual
        # mode must still prevent every provider call and automatic grant.
        self.service.settings = replace(billing.SETTINGS, approval_mode="manual")
        self.sent = []

        async def sender(*args):
            self.sent.append(args)
            return {"status": "sent", "provider_message_id": "synthetic-message"}

        self.service.welcome_sender = sender

    asyncTearDown = billing.SquareBillingTests.asyncTearDown
    auth = billing.SquareBillingTests.auth
    user = billing.SquareBillingTests.user
    checkout = billing.SquareBillingTests.checkout
    event = billing.SquareBillingTests.event
    webhook = billing.SquareBillingTests.webhook

    async def approve(self, reference="square-receipt-001", plan="monthly", user_id="member", **changes):
        body = {"user_id": user_id, "plan_id": plan, "payment_reference": reference,
                "confirm_payment_reviewed": True, **changes}
        return await self.client.post("/api/billing/admin/approve", headers=self.admin_headers, json=body)

    def trial_cleanup(self):
        """Load the real worker operation without starting production services."""
        source = Path(__file__).resolve().parents[1] / "server.py"
        function = next(node for node in ast.parse(source.read_text()).body
                        if isinstance(node, ast.AsyncFunctionDef) and node.name == "check_expired_trials")
        self.trial_emails = []

        async def capture(*args):
            self.trial_emails.append(args)

        self.n["send_trial_upgrade_email"] = capture
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), self.n)
        return self.n["check_expired_trials"]

    def expired_trial(self):
        user = self.db.users.rows[0]
        user.update(status="trial", trial_end_date=self.clock - timedelta(days=1),
                    membership_plan="7DaysTrial")
        return user

    async def test_trial_cleanup_cannot_overwrite_concurrent_paid_approval(self):
        cleanup = self.trial_cleanup()
        original = deepcopy(self.expired_trial())

        async def approve_after_scan(query, update):
            self.db.users.before_update = None
            response = await self.approve()
            self.assertEqual(response.status_code, 200, response.text)

        self.db.users.before_update = approve_after_scan
        await cleanup()
        user = await self.user()
        self.assertEqual(user["status"], "approved")
        self.assertTrue(active_membership(user, self.clock))
        self.assertEqual(user["billing_entitlement"]["managed_by"], "manual_payment")
        for field in ("id", "bio", "followers", "experience_points", "active_session_id"):
            self.assertEqual(user[field], original[field], field)
        self.assertEqual(len(self.sent), 1)
        self.assertFalse(self.trial_emails)
        self.assertFalse(user.get("trial_upgrade_email_sent"))

    async def test_trial_cleanup_cannot_overwrite_concurrent_complimentary_approval(self):
        cleanup = self.trial_cleanup()
        self.expired_trial()

        async def approve_after_scan(query, update):
            self.db.users.before_update = None
            response = await self.client.post("/api/users/approve", headers=self.admin_headers, json={
                "user_id": "member", "admin_id": "admin", "approved": True, "role": "member",
            })
            self.assertEqual(response.status_code, 200, response.text)

        self.db.users.before_update = approve_after_scan
        await cleanup()
        user = await self.user()
        self.assertEqual(user["status"], "approved")
        self.assertTrue(user["manual_access_granted"])
        self.assertTrue(active_membership(user, self.clock))
        self.assertFalse(self.trial_emails)

    async def test_trial_cleanup_skips_a_changed_deadline_or_access_state(self):
        changes = (
            {"trial_end_date": self.clock + timedelta(days=1)},
            {"status": "rejected"},
            {"disabled": True},
            {"manual_access_granted": True},
            {"billing_entitlement": {"managed_by": "manual_payment", "version": 1,
                                     "paid_through": self.clock + timedelta(days=30)}},
        )
        for changed in changes:
            with self.subTest(changed=changed):
                self.db.users.rows[0] = deepcopy(self.pending)
                cleanup = self.trial_cleanup()
                self.expired_trial()

                async def change_after_scan(query, update):
                    self.db.users.before_update = None
                    self.db.users.rows[0].update(deepcopy(changed))

                self.db.users.before_update = change_after_scan
                before = deepcopy(self.db.users.rows[0])
                await cleanup()
                self.assertEqual(await self.user(), {**before, **changed})
                self.assertFalse(self.trial_emails)

    async def test_trial_cleanup_expires_only_due_trials_and_notifies_once(self):
        cleanup = self.trial_cleanup()
        original = deepcopy(self.expired_trial())
        future = {**deepcopy(original), "id": "future", "_id": "future",
                  "trial_end_date": self.clock + timedelta(days=1)}
        self.db.users.rows.append(future)
        approved = deepcopy(self.db.users.rows[2])
        await cleanup()
        await cleanup()
        user = await self.user()
        self.assertEqual(user["status"], "trial_expired")
        self.assertTrue(user["trial_upgrade_email_sent"])
        self.assertFalse(active_membership(user, self.clock))
        self.assertEqual({key: value for key, value in user.items()
                          if key not in {"status", "trial_upgrade_email_sent"}},
                         {key: value for key, value in original.items() if key != "status"})
        self.assertEqual(self.trial_emails, [("learner@example.test", "learner")])
        self.assertEqual(await self.db.users.find_one({"id": "future"}), future)
        self.assertEqual(await self.db.users.find_one({"id": "other"}), approved)

    async def test_overlapping_trial_cleanup_workers_send_one_expiration_email(self):
        cleanup = self.trial_cleanup()
        self.expired_trial()

        async def yield_before_write(query, update):
            await asyncio.sleep(0)

        self.db.users.before_update = yield_before_write
        await asyncio.gather(*(cleanup() for _ in range(5)))
        self.assertEqual((await self.user())["status"], "trial_expired")
        self.assertEqual(len(self.trial_emails), 1)

    async def test_trial_cleanup_preserves_existing_email_marker(self):
        cleanup = self.trial_cleanup()
        self.expired_trial()["trial_upgrade_email_sent"] = True
        await cleanup()
        self.assertEqual((await self.user())["status"], "trial_expired")
        self.assertFalse(self.trial_emails)

    async def test_manual_default_requires_an_explicit_new_automatic_selection(self):
        environment = {
            "SQUARE_BILLING_ENABLED": "true", "SQUARE_ENVIRONMENT": "production",
            "SQUARE_ACCESS_TOKEN": "synthetic-only", "SQUARE_MERCHANT_ID": billing.PRODUCTION_MERCHANT,
            "SQUARE_LOCATION_ID": "TEST_LOCATION", "SQUARE_WEBHOOK_SIGNATURE_KEY": "synthetic-long-secret",
            "SQUARE_WEBHOOK_NOTIFICATION_URL": "https://example.test/webhook",
            "SQUARE_CHECKOUT_RETURN_URL": "https://example.test/return",
        }
        with patch.dict(os.environ, environment, clear=True):
            self.assertEqual(SquareSettings.from_env().mode, "manual")
            self.assertFalse(SquareSettings.from_env().ready)
            for value in ("", "true", "auto", "unrecognized"):
                with patch.dict(os.environ, {"MEMBERSHIP_APPROVAL_MODE": value}):
                    self.assertFalse(SquareSettings.from_env().ready)
            with patch.dict(os.environ, {"MEMBERSHIP_APPROVAL_MODE": "automatic"}):
                self.assertTrue(SquareSettings.from_env().ready)

        # Pending automatic work from an older configuration also stays dormant.
        self.service.settings = billing.SETTINGS
        _, checkout = await self.checkout()
        self.provider.complete(checkout)
        await self.webhook(self.event())
        self.service.settings = replace(billing.SETTINGS, approval_mode="manual")
        self.provider.calls.clear()
        await self.service.process_once()
        self.assertEqual((await self.user())["status"], "pending")
        self.assertFalse(self.provider.calls)
        self.assertEqual((await self.webhook(self.event())).status_code, 503)
        result = await self.client.post("/api/billing/checkout", headers=self.member_headers,
                                       json={"plan_id": "monthly", "idempotency_key": "unique-request-0123456789"})
        self.assertEqual(result.status_code, 503)
        with self.assertRaises(SquareProblem):
            await self.service.verify_payment("pay_1")
        with self.assertRaises(SquareProblem):
            await self.service.apply_grant({"_id": "old-payment"}, checkout)
        plans = (await self.client.get("/api/billing/plans")).json()
        self.assertEqual(plans["approval_mode"], "manual")
        self.assertFalse(plans["automatic_activation_available"])
        self.assertFalse(plans["recurring"])
        status = (await self.client.get("/api/billing/status", headers=self.member_headers)).json()
        self.assertIsNone(status["checkouts"][0]["checkout_url"])
        self.assertFalse(self.provider.calls)

    async def test_admin_review_approves_existing_account_and_one_welcome(self):
        original = await self.user()
        response = await self.approve()
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertFalse(body["duplicate"])
        self.assertEqual(body["welcome_email"]["status"], "pending")
        self.assertEqual(body["entitlement"]["source"], "manual_payment")
        self.assertEqual(body["payment"]["evidence_source"], "admin_review")
        self.assertEqual(body["payment"]["verification_status"], "admin_reviewed")
        self.assertEqual(body["payment"]["reviewed_by"], "admin")
        self.assertIsNone(body["payment"]["verified_at"])
        user = await self.user()
        self.assertEqual(user["status"], "approved")
        self.assertEqual(user["approved_by"], "admin")
        self.assertEqual(user["billing_entitlement"]["paid_through"], add_months(self.clock, 1))
        self.assertFalse(user.get("manual_access_granted"))
        self.assertFalse(user["billing_entitlement"]["legacy_access"])
        for field in ("id", "username", "password_hash", "active_session_id", "bio", "followers", "experience_points"):
            self.assertEqual(user[field], original[field], field)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0], ("learner@example.test", "learner", "learner", "1 month (one-time purchase)"))
        self.assertFalse(self.provider.calls)
        status = (await self.client.get("/api/billing/status", headers=self.member_headers)).json()
        self.assertEqual(status["payments"][0]["welcome_email"]["status"], "sent")
        self.assertEqual(status["username"], "learner")
        self.assertEqual(status["email"], "learner@example.test")
        self.assertEqual(status["selected_plan_id"], "monthly")
        for field in ("reviewed_by", "welcome_recipient", "password_hash", "active_session_id"):
            self.assertNotIn(field, status["payments"][0])

    async def test_automatic_mode_cannot_also_record_manual_paid_approvals(self):
        self.service.settings = billing.SETTINGS
        response = await self.approve()
        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn("manual approval mode", response.json()["detail"])
        self.assertFalse(self.db.billing_payments.rows)
        self.assertEqual((await self.user())["status"], "pending")
        self.assertFalse(self.provider.calls)
        self.assertFalse(self.sent)
        self.service.settings = replace(billing.SETTINGS, approval_mode="manual")
        self.assertEqual((await self.approve()).status_code, 200)
        end = (await self.user())["billing_entitlement"]["paid_through"]
        self.service.settings = billing.SETTINGS
        retry = await self.approve()
        self.assertEqual(retry.status_code, 200, retry.text)
        self.assertTrue(retry.json()["duplicate"])
        self.assertEqual((await self.user())["billing_entitlement"]["paid_through"], end)
        self.assertEqual(len(self.sent), 1)

    async def test_current_admin_session_and_explicit_review_are_required(self):
        body = {"user_id": "member", "plan_id": "monthly", "payment_reference": "review-001",
                "confirm_payment_reviewed": True}
        _, billing_proof = await self.auth()
        for headers, expected in (({}, 401), (self.member_headers, 403),
                                  ({"X-User-ID": "admin", "X-Session-ID": "wrong-session"}, 401),
                                  (billing_proof, 401)):
            response = await self.client.post("/api/billing/admin/approve", headers=headers, json=body)
            self.assertEqual(response.status_code, expected, response.text)
        for changes, expected in (({"confirm_payment_reviewed": False}, 400),
                                  ({"confirm_payment_reviewed": "true"}, 422),
                                  ({"plan_id": "free-trial"}, 400),
                                  ({"amount_cents": 1}, 422), ({"admin_id": "admin"}, 422),
                                  ({"payment_reference": "https://square.link/u/paid"}, 422)):
            response = await self.approve(**changes)
            self.assertEqual(response.status_code, expected, response.text)
        self.assertFalse(self.db.billing_payments.rows)
        self.assertEqual((await self.user())["status"], "pending")
        self.assertFalse(self.sent)

    async def test_repeated_reference_does_not_extend_access_or_send_again(self):
        first = await self.approve(reference=" Receipt-ABC ")
        self.assertEqual(first.status_code, 200, first.text)
        end = (await self.user())["billing_entitlement"]["paid_through"]
        reviewed_at = self.db.billing_payments.rows[0]["reviewed_at"]
        self.clock += timedelta(days=5)
        again = await self.approve(reference="receipt-abc")
        self.assertEqual(again.status_code, 200, again.text)
        self.assertTrue(again.json()["duplicate"])
        self.assertEqual((await self.user())["billing_entitlement"]["paid_through"], end)
        self.assertEqual(self.db.billing_payments.rows[0]["reviewed_at"], reviewed_at)
        self.assertEqual(len(self.db.billing_payments.rows), 1)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual((await self.approve(reference="receipt-abc", user_id="other")).status_code, 409)
        self.assertEqual((await self.approve(reference="receipt-abc", plan="six_months")).status_code, 409)
        self.assertEqual(len(self.db.billing_payments.rows), 1)

    async def test_concurrent_duplicate_approvals_claim_one_term_and_one_email(self):
        results = await asyncio.gather(*(self.approve() for _ in range(8)))
        self.assertTrue(all(result.status_code == 200 for result in results), [result.text for result in results])
        self.assertEqual(sum(not result.json()["duplicate"] for result in results), 1)
        self.assertEqual(len(self.db.billing_payments.rows), 1)
        self.assertEqual((await self.user())["billing_entitlement"]["paid_through"], add_months(self.clock, 1))
        self.assertEqual(len(self.sent), 1)

    async def test_grant_recovers_after_persistence_interruption_without_double_term(self):
        interrupted = False

        async def crash_once(query, update):
            nonlocal interrupted
            if "billing_entitlement" in update.get("$set", {}) and not interrupted:
                interrupted = True
                raise RuntimeError("synthetic interruption after committed user update")

        self.db.users.after_update = crash_once
        with self.assertRaises(RuntimeError):
            await self.approve()
        saved_end = (await self.user())["billing_entitlement"]["paid_through"]
        self.assertFalse(self.sent)
        self.clock += timedelta(minutes=5)
        response = await self.approve()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual((await self.user())["billing_entitlement"]["paid_through"], saved_end)
        self.assertEqual(len(self.sent), 1)

    async def test_calendar_terms_renewal_expiry_and_lifetime(self):
        self.clock = datetime(2027, 1, 31, 12)
        self.assertEqual((await self.approve(plan="six_months")).status_code, 200)
        self.assertEqual((await self.user())["billing_entitlement"]["paid_through"], datetime(2027, 7, 31, 12))
        self.clock = datetime(2027, 3, 15, 12)
        self.assertEqual((await self.approve(reference="renewal-001")).status_code, 200)
        self.assertEqual((await self.user())["billing_entitlement"]["paid_through"], datetime(2027, 8, 31, 12))
        self.clock = datetime(2027, 8, 31, 12)
        self.assertFalse(active_membership(await self.user(), self.clock))
        self.assertEqual((await self.user())["status"], "approved")
        self.clock += timedelta(days=2)
        self.assertEqual((await self.approve(reference="renewal-002")).status_code, 200)
        self.assertEqual((await self.user())["billing_entitlement"]["paid_through"], add_months(self.clock, 1))
        self.assertEqual((await self.approve(reference="lifetime-001", plan="lifetime")).status_code, 200)
        self.clock += timedelta(days=3650)
        self.assertTrue(active_membership(await self.user(), self.clock))
        self.assertTrue(membership_snapshot(await self.user(), self.clock)["lifetime"])

    async def test_concurrent_different_payments_accumulate_both_terms(self):
        results = await asyncio.gather(self.approve(reference="renewal-first"), self.approve(reference="renewal-second"))
        self.assertTrue(all(response.status_code == 200 for response in results), [response.text for response in results])
        user = await self.user()
        self.assertEqual(user["billing_entitlement"]["paid_through"], add_months(add_months(self.clock, 1), 1))
        self.assertEqual(len(user["billing_entitlement"]["payment_ids"]), 2)

    async def test_legacy_and_explicit_independent_access_are_preserved(self):
        response = await self.approve(user_id="other")
        self.assertEqual(response.status_code, 200, response.text)
        other = await self.db.users.find_one({"id": "other"})
        future = self.clock + timedelta(days=1000)
        self.assertTrue(active_membership(other, future))
        self.assertEqual(membership_snapshot(other, future)["source"], "legacy")
        self.db.users.rows[0]["manual_access_granted"] = True
        response = await self.approve(reference="independent-access")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(membership_snapshot(await self.user(), future)["source"], "manual")
        self.assertTrue(active_membership(await self.user(), future))

    async def test_existing_trial_converts_without_a_new_trial_or_profile_reset(self):
        user = self.db.users.rows[0]
        user.update(status="trial_expired", trial_end_date=self.clock - timedelta(days=5), membership_plan="7DaysTrial")
        response = await self.approve(plan="six_months")
        self.assertEqual(response.status_code, 200, response.text)
        updated = await self.user()
        self.assertEqual(updated["status"], "approved")
        self.assertEqual(updated["membership_plan"], "SixMonths")
        self.assertEqual(updated["trial_end_date"], user["trial_end_date"])
        self.assertEqual(updated["active_session_id"], "existing-session")

    async def test_manual_paid_expiry_reaches_member_and_stock_gates_without_losing_account(self):
        self.assertEqual((await self.approve()).status_code, 200)
        self.db.users.rows[0]["billing_entitlement"]["paid_through"] = min(self.clock, datetime.utcnow()) - timedelta(seconds=1)
        user = await self.user()
        self.assertFalse(active_membership(user))
        self.assertFalse(billing.stock_membership(user, datetime.utcnow()))
        self.assertEqual((await self.client.get("/api/member-probe", headers=self.member_headers)).status_code, 403)
        session = await self.client.get("/api/users/member/session-status", params={"session_id": "existing-session"})
        self.assertEqual(session.status_code, 200)
        self.assertTrue(session.json()["valid"])
        status = await self.client.get("/api/billing/status", headers=self.member_headers)
        self.assertEqual(status.status_code, 200)
        self.assertFalse(status.json()["entitlement"]["active"])
        self.assertEqual((await self.user())["active_session_id"], "existing-session")

    async def test_missing_email_configuration_and_rejection_never_undo_access(self):
        self.service.welcome_sender = None
        response = await self.approve()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["welcome_email"]["status"], "unavailable")
        self.assertTrue(active_membership(await self.user(), self.clock))

        async def rejected(*args):
            self.sent.append(args)
            return {"status": "failed"}

        self.service.welcome_sender = rejected
        response = await self.approve(reference="second-payment")
        self.assertEqual(response.status_code, 200)
        history = (await self.client.get("/api/billing/admin/payments", headers=self.admin_headers)).json()["payments"]
        self.assertEqual(next(row for row in history if row["payment_id"] == "second-payment")["welcome_email"]["status"], "failed")
        self.assertTrue(active_membership(await self.user(), self.clock))
        await self.approve(reference="second-payment")
        self.assertEqual(len(self.sent), 1)

    async def test_ambiguous_send_is_unknown_and_retry_cannot_send_twice(self):
        async def ambiguous(*args):
            self.sent.append(args)
            raise TimeoutError("synthetic response lost after possible acceptance")

        self.service.welcome_sender = ambiguous
        response = await self.approve()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.db.billing_payments.rows[0]["welcome_email_status"], "unknown")
        await self.approve()
        self.assertEqual(len(self.sent), 1)
        self.assertTrue(active_membership(await self.user(), self.clock))
        row = self.db.billing_payments.rows[0]
        row.update(welcome_email_status="sending", welcome_email_started_at=self.clock - timedelta(minutes=11))
        self.assertEqual(self.service.payment_view(row)["welcome_email"]["status"], "unknown")
        await self.approve()
        self.assertEqual(len(self.sent), 1)

    async def test_scheduled_but_unstarted_welcome_can_recover_on_approval_retry(self):
        admin = await self.db.users.find_one({"id": "admin"})
        body = ManualApprovalRequest(user_id="member", plan_id="monthly", payment_reference="restart-001",
                                     confirm_payment_reviewed=True)
        first_tasks = BackgroundTasks()
        await self.service.approve_manual(admin, body, first_tasks)
        self.assertEqual(len(first_tasks.tasks), 1)
        self.assertFalse(self.sent)
        # Simulate losing the response process before its background task starts.
        next_tasks = BackgroundTasks()
        response = await self.service.approve_manual(admin, body, next_tasks)
        self.assertTrue(response["duplicate"])
        await next_tasks()
        await first_tasks()
        self.assertEqual(len(self.sent), 1)


class WelcomeOutcomeTests(unittest.IsolatedAsyncioTestCase):
    def service(self, send):
        path = Path(__file__).resolve().parents[1] / "email_service.py"
        node = next(node for node in ast.parse(path.read_text()).body if isinstance(node, ast.ClassDef) and node.name == "EmailService")
        namespace = {"Optional": Optional, "asyncio": asyncio, "os": os, "datetime": datetime, "escape": escape,
                     "logger": logging.getLogger("synthetic-email"), "resend": SimpleNamespace(Emails=SimpleNamespace(send=send))}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
        instance = namespace["EmailService"].__new__(namespace["EmailService"])
        instance.sender_email = "test@example.test"
        return instance

    async def test_provider_message_id_is_required_and_ambiguous_errors_stay_unknown(self):
        class Rejected(Exception):
            status_code = 403

        for result, expected in (({"id": "synthetic-id"}, "sent"), ({}, "unknown"),
                                 (TimeoutError("synthetic timeout"), "unknown"), (Rejected(), "failed")):
            def send(params):
                if isinstance(result, Exception):
                    raise result
                return result

            service = self.service(send)
            outcome = await service.send_email("member@example.test", "Subject", "Body", return_outcome=True)
            self.assertEqual(outcome["status"], expected)
            self.assertEqual(await service.send_email("member@example.test", "Subject", "Body"), expected == "sent")

    async def test_welcome_escapes_user_html_and_retains_existing_login_in_plain_text(self):
        service = self.service(lambda _: None)
        captured = {}

        async def capture(recipient, subject, body, html_body, **kwargs):
            captured.update(recipient=recipient, subject=subject, body=body, html=html_body)
            return {"status": "sent"} if kwargs.get("return_outcome") else True

        service.send_email = capture
        result = await service.send_general_welcome_email_outcome(
            "member@example.test", "<img src=x onerror=alert(1)>", 'name<"&>', "1 month (one-time purchase)")
        self.assertEqual(result["status"], "sent")
        self.assertNotIn("<img", captured["html"])
        self.assertIn("&lt;img", captured["html"])
        self.assertIn("name&lt;&quot;&amp;&gt;", captured["html"])
        self.assertIn('name<"&>', captured["body"])
        self.assertIn("do not need to register again", captured["body"])
        self.assertNotIn("instant support", captured["html"])
        self.assertNotIn("real-time market data", captured["body"].lower())


if __name__ == "__main__":
    unittest.main()
