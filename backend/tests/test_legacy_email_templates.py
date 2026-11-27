"""Exercise rendered email and provider payloads without credentials or network I/O."""

import ast
import asyncio
import copy
import logging
import os
import re
import unittest
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from types import SimpleNamespace
from typing import Optional


class LegacyEmailTemplateTests(unittest.IsolatedAsyncioTestCase):
    def service(self, send=None):
        """Load only the class; never import the live global email service."""
        path = Path(__file__).resolve().parents[1] / "email_service.py"
        node = next(
            item for item in ast.parse(path.read_text()).body
            if isinstance(item, ast.ClassDef) and item.name == "EmailService"
        )
        self.sent = []

        def record(params):
            self.sent.append(copy.deepcopy(params))
            return send(params) if send else {"id": "synthetic-message"}

        namespace = {
            "Optional": Optional, "asyncio": asyncio, "os": os,
            "datetime": datetime, "timezone": timezone, "escape": escape,
            "logger": logging.getLogger("synthetic-legacy-email"),
            "resend": SimpleNamespace(Emails=SimpleNamespace(send=record)),
        }
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
        instance = namespace["EmailService"].__new__(namespace["EmailService"])
        instance.sender_email = "sender@example.test"
        return instance

    def assert_current_offer(self, message, expected_url):
        self.assertEqual(message["from"], "sender@example.test")
        self.assertEqual(set(re.findall(r'href="([^"]+)"', message["html"])), {expected_url})
        for part in (message["text"], message["html"]):
            self.assertIn(expected_url, part)
            for retired_claim in (
                "$199", "$1,296", "$1296", "$3,969", "$3969", "square.link/",
                "14-day", "14 days", "free trial", "full access", "automatically approved",
                "within 24 hours", "instant support", "successful traders",
                "guaranteed profit", "cash prize", "real-time market data",
            ):
                self.assertNotIn(retired_claim, part.lower())

    async def test_expired_trial_uses_current_catalog_and_manual_existing_account_flow(self):
        service = self.service()
        self.assertTrue(await service.send_trial_upgrade_email("member@example.test", '<script>bad()</script>'))
        self.assertEqual(len(self.sent), 1)
        message = self.sent[0]
        self.assertEqual(message["to"], ["member@example.test"])
        self.assert_current_offer(message, "https://cashoutai.app/?billing=1")
        for part in (message["text"], message["html"]):
            self.assertIn("one-time payments", part)
            self.assertIn("no automatic renewal", part)
            self.assertIn("reviews the Square payment", part)
            self.assertIn("before approving paid access", part)
            self.assertIn("receipt/reference", part)
            self.assertIn("do not need to register again", part)
            self.assertIn("Recover existing account", part)
        self.assertNotIn("<script>", message["html"])
        self.assertIn("&lt;script&gt;", message["html"])
        self.assertIn("<script>", message["text"])

    async def test_trial_welcome_preserves_supplied_original_expiry_including_legacy_formats(self):
        original = datetime(2026, 11, 20, 12, 30, tzinfo=timezone(timedelta(hours=5)))
        for end in (original, "2026-11-20T07:30:00Z", datetime(2026, 11, 20, 7, 30)):
            with self.subTest(expiry=end):
                service = self.service()
                self.assertTrue(await service.send_trial_welcome_email("member@example.test", "Existing member", end))
                self.assertEqual(len(self.sent), 1)
                message = self.sent[0]
                self.assert_current_offer(message, "https://cashoutai.app/?billing=1")
                for part in (message["text"], message["html"]):
                    self.assertIn("November 20, 2026 at 07:30 AM UTC", part)
                    self.assertIn("original expiry and access rules", part)
                    self.assertIn("New trials are currently unavailable", part)
                    self.assertIn("manually reviews the payment", part)
                    self.assertIn("Recover existing account", part)

    async def test_missing_or_malformed_legacy_expiry_does_not_invent_a_new_term(self):
        for end in (None, "", '<img src=x onerror="bad()">'):
            with self.subTest(expiry=end):
                service = self.service()
                self.assertTrue(await service.send_trial_welcome_email("member@example.test", "Member", end))
                message = self.sent[0]
                self.assert_current_offer(message, "https://cashoutai.app/?billing=1")
                for part in (message["text"], message["html"]):
                    self.assertIn("Not available; check Membership in the app", part)
                    self.assertNotIn("<img", part)
                    self.assertNotIn("starts now", part.lower())

    async def test_legacy_trial_admin_notice_reports_status_without_approving_or_changing_record(self):
        service = self.service()
        user = {
            "id": "legacy-member", "username": "existing", "email": "member@example.test",
            "real_name": "<b>Existing</b>", "status": "pending",
            "trial_end_date": "2026-11-20T07:30:00Z",
        }
        before = copy.deepcopy(user)
        self.assertTrue(await service.send_trial_registration_notification("admin@example.test", user))
        self.assertEqual(user, before)
        self.assertEqual(len(self.sent), 1)
        message = self.sent[0]
        self.assert_current_offer(message, "https://cashoutai.app/")
        self.assertIn("Recorded status: pending", message["text"])
        self.assertIn("Original trial expiry: November 20, 2026 at 07:30 AM UTC", message["text"])
        self.assertNotIn("<b>Existing</b>", message["html"])
        self.assertIn("&lt;b&gt;Existing&lt;/b&gt;", message["html"])

    async def test_registration_notice_distinguishes_selected_plan_from_reviewed_payment(self):
        service = self.service()
        self.assertTrue(await service.send_registration_notification("admin@example.test", {
            "real_name": "<img src=x>", "username": "existing", "email": "member@example.test",
            "membership_plan": "1 month (one-time purchase)",
        }))
        self.assertEqual(len(self.sent), 1)
        message = self.sent[0]
        self.assert_current_offer(message, "https://cashoutai.app/")
        for part in (message["text"], message["html"]):
            self.assertIn("Selecting a plan does not confirm payment", part)
            self.assertIn("Record the actual purchased plan and receipt/reference", part)
            self.assertIn("manual review", part)
        self.assertNotIn("<img", message["html"])

    async def test_event_admin_notice_is_informational_and_escapes_member_fields(self):
        service = self.service()
        self.assertTrue(await service.send_event_registration_notification("admin@example.test", {
            "username": "<img src=x>", "email": "member@example.test",
            "password_hash": "must-not-leak", "practice_event_token_hash": "must-not-leak",
        }))
        self.assertEqual(len(self.sent), 1)
        message = self.sent[0]
        self.assertEqual(message["to"], ["admin@example.test"])
        self.assertEqual(message["subject"], "CashOutAI — New Free Event Participant")
        self.assertNotIn("<img", message["html"])
        self.assertIn("&lt;img", message["html"])
        for part in (message["text"], message["html"]):
            self.assertIn("11:59 PM Eastern", part)
            self.assertIn("Awaiting email verification", part)
            self.assertIn("no administrator approval is needed", part)
            self.assertNotIn("must-not-leak", part)

    async def test_account_decisions_keep_existing_identity_without_feature_or_rejection_guesses(self):
        for approved in (False, True):
            with self.subTest(approved=approved):
                service = self.service()
                self.assertTrue(await service.send_approval_confirmation("member@example.test", "<b>Member</b>", approved))
                self.assertEqual(len(self.sent), 1)
                message = self.sent[0]
                self.assert_current_offer(message, "https://cashoutai.app/")
                for part in (message["text"], message["html"]):
                    self.assertIn("do not need to register again", part)
                    self.assertIn("Recover existing account", part)
                    self.assertNotIn("real-time stock quotes", part.lower())
                    self.assertNotIn("reapply", part.lower())
                    self.assertNotIn("Incomplete registration information", part)
                if not approved:
                    self.assertIn("request another review of this existing account", message["text"])
                    self.assertIn("receipt/reference", message["text"])
                self.assertNotIn("<b>Member</b>", message["html"])

    async def test_manual_welcome_reaches_provider_once_with_recovery_and_plain_text_fallback(self):
        service = self.service()
        result = await service.send_general_welcome_email_outcome(
            "member@example.test", "<img src=x>", 'name<"&>', "6 months (one-time purchase)",
        )
        self.assertEqual(result, {"status": "sent", "provider_message_id": "synthetic-message"})
        self.assertEqual(len(self.sent), 1)
        message = self.sent[0]
        self.assertEqual(message["to"], ["member@example.test"])
        self.assert_current_offer(message, "https://cashoutai.app/")
        self.assertIn('name<"&>', message["text"])
        self.assertIn("name&lt;&quot;&amp;&gt;", message["html"])
        self.assertNotIn("<img", message["html"])
        for part in (message["text"], message["html"]):
            self.assertIn("Recover existing account", part)
            self.assertIn("do not need to register again", part)
            self.assertIn("paid-through date", part)

    async def test_manual_welcome_keeps_provider_rejection_and_uncertainty_distinct_without_retry(self):
        class Rejected(Exception):
            status_code = 403

        for error, status in ((Rejected(), "failed"), (TimeoutError(), "unknown")):
            with self.subTest(status=status):
                def fail(params):
                    raise error

                service = self.service(fail)
                outcome = await service.send_general_welcome_email_outcome(
                    "member@example.test", "Member", "existing", "Lifetime",
                )
                self.assertEqual(outcome, {"status": status})
                self.assertEqual(len(self.sent), 1)


if __name__ == "__main__":
    unittest.main()
