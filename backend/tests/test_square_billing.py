"""Square/account integration with synthetic HTTP, Mongo and provider doubles.

These tests run real route/dependency/service bodies without live Square calls,
credentials, a real member database, Firebase, or the legacy server lifespan.
"""
import ast
import asyncio
import base64
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
import hashlib
import hmac
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException
import httpx

from test_account_recovery import load_auth_slice, noop, request
from test_single_session import Socket
from membership import active_membership, membership_snapshot
from nautilus_api import _member as nautilus_member
from stock_alerts import active_membership as stock_membership
from square_billing import (
    BillingAuth, CheckoutRequest, PLANS, PRODUCTION_MERCHANT, SquareBillingService,
    SquareClient, SquareProblem, SquareSettings, add_months,
)

NOW = datetime.utcnow().replace(microsecond=0)
SETTINGS = SquareSettings(
    approval_mode="automatic",
    enabled=True, environment="production", access_token="synthetic-not-a-real-token",
    merchant_id=PRODUCTION_MERCHANT, location_id="TEST_LOCATION",
    signature_key="synthetic-square-signature-key-only-for-tests",
    notification_url="https://app.example.test/api/billing/square/webhook",
    return_url="https://app.example.test/?tab=billing",
)


def matches(row, query):
    for key, expected in query.items():
        if key == "$or":
            if not any(matches(row, branch) for branch in expected):
                return False
            continue
        actual = row.get(key)
        if isinstance(expected, dict) and any(k.startswith("$") for k in expected):
            for operator, operand in expected.items():
                if operator == "$exists" and (key in row) != operand:
                    return False
                if operator == "$in" and actual not in operand:
                    return False
                if operator == "$lte" and (actual is None or actual > operand):
                    return False
                if operator == "$lt" and (actual is None or actual >= operand):
                    return False
                if operator == "$regex":
                    import re
                    if re.search(operand, actual or "", re.I if expected.get("$options") == "i" else 0) is None:
                        return False
        elif actual != expected:
            # Embedded grant equality matters: this must model a real Mongo CAS,
            # not silently ignore non-operator dictionaries.
            return False
    return True


class Cursor:
    def __init__(self, rows):
        self.rows = deepcopy(rows)

    def sort(self, key, direction):
        self.rows.sort(key=lambda row: row.get(key) or datetime.min, reverse=direction < 0)
        return self

    async def to_list(self, limit):
        return deepcopy(self.rows[:limit])


class Collection:
    def __init__(self, rows=()):
        self.rows = deepcopy(list(rows))
        self.writes = 0
        self.before_update = None
        self.after_update = None
        self.indexes = []

    async def create_index(self, *args, **kwargs):
        self.indexes.append((args, kwargs))

    def find(self, query=None):
        return Cursor([row for row in self.rows if matches(row, query or {})])

    async def find_one(self, query, projection=None):
        await asyncio.sleep(0)
        return next((deepcopy(row) for row in self.rows if matches(row, query)), None)

    @staticmethod
    def apply(row, update, inserted=False):
        if inserted:
            row.update(deepcopy(update.get("$setOnInsert", {})))
        row.update(deepcopy(update.get("$set", {})))
        for key, amount in update.get("$inc", {}).items():
            row[key] = row.get(key, 0) + amount

    async def insert_one(self, row):
        if any(item.get("_id") == row.get("_id") for item in self.rows):
            raise RuntimeError("duplicate synthetic insert")
        self.rows.append(deepcopy(row))
        self.writes += 1
        return SimpleNamespace(inserted_id=row.get("_id"))

    async def update_one(self, query, update, upsert=False):
        if self.before_update:
            await self.before_update(query, update)
        for row in self.rows:
            if matches(row, query):
                before = deepcopy(row)
                self.apply(row, update)
                self.writes += int(row != before)
                if self.after_update:
                    await self.after_update(query, update)
                return SimpleNamespace(matched_count=1, modified_count=int(row != before), upserted_id=None)
        if upsert:
            row = {k: v for k, v in query.items() if not isinstance(v, dict)}
            self.apply(row, update, inserted=True)
            await self.insert_one(row)
            return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=row["_id"])
        return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=None)

    async def find_one_and_update(self, query, update, upsert=False, return_document=False):
        for row in self.rows:
            if matches(row, query):
                before = deepcopy(row)
                self.apply(row, update)
                self.writes += 1
                return deepcopy(row) if return_document == True else before
        if upsert:
            row = {k: v for k, v in query.items() if not isinstance(v, dict)}
            self.apply(row, update, inserted=True)
            await self.insert_one(row)
            return deepcopy(row) if return_document == True else None
        return None


class Provider:
    def __init__(self, settings=SETTINGS):
        self.settings = settings
        self.calls = []
        self.orders = {}
        self.payments = {}
        self.links = {}
        self.create_failure_after_accept = False
        self.payment_failure = None
        self.location_override = None

    async def location(self):
        self.calls.append(("location",))
        return deepcopy(self.location_override or {
            "id": self.settings.location_id, "merchant_id": self.settings.merchant_id,
            "currency": "USD", "status": "ACTIVE",
        })

    async def create_link(self, body):
        self.calls.append(("create_link", deepcopy(body)))
        key = body["idempotency_key"]
        if key not in self.links:
            order_id = "order_" + key[:24]
            order = deepcopy(body["order"])
            order.update(id=order_id, state="OPEN", total_money=deepcopy(order["line_items"][0]["base_price_money"]), tenders=[])
            self.orders[order_id] = order
            self.links[key] = {"payment_link": {"id": "link_" + key[:24], "order_id": order_id,
                                               "url": "https://square.link/u/" + key[:24]}}
        await asyncio.sleep(0)
        if self.create_failure_after_accept:
            self.create_failure_after_accept = False
            raise SquareProblem("square_unavailable")
        return deepcopy(self.links[key])

    async def payment(self, payment_id):
        self.calls.append(("payment", payment_id))
        await asyncio.sleep(0)
        if self.payment_failure:
            raise self.payment_failure
        return deepcopy(self.payments[payment_id])

    async def order(self, order_id):
        self.calls.append(("order", order_id))
        await asyncio.sleep(0)
        return deepcopy(self.orders[order_id])

    def complete(self, checkout, payment_id="pay_1", **changes):
        order = self.orders[checkout["order_id"]]
        amount = deepcopy(order["total_money"])
        payment = {"id": payment_id, "order_id": order["id"], "location_id": self.settings.location_id,
                   "status": "COMPLETED", "source_type": "CARD", "amount_money": amount,
                   "total_money": deepcopy(amount), "tip_money": {"amount": 0, "currency": "USD"},
                   "created_at": NOW.isoformat() + "Z"}
        payment.update(changes)
        self.payments[payment_id] = payment
        order["tenders"].append({"payment_id": payment_id})
        return payment


def load_member_routes():
    n = load_auth_slice()
    n.update(api_router=APIRouter(prefix="/api"))
    names = {"require_legacy_active_session", "require_authenticated_admin", "approve_user",
             "change_user_role", "update_user_role", "convert_trial_to_member",
             "UserApproval", "UserRoleUpdate", "ProfileUpdate", "ExistingProfileUpdate",
             "update_user_profile", "check_session_status"}
    selected = []
    source = Path(__file__).resolve().parents[1] / "server.py"
    for node in ast.parse(source.read_text()).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "LEGACY_SESSION_EXEMPT_OPERATIONS" for t in node.targets):
            selected.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in names:
            selected.append(node)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), "exec"), n)
    return n


class SquareBillingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clock = NOW
        self.n = load_member_routes()
        # This isolated runtime omits legacy server packages. Real synthetic
        # credentials use the unchanged SHA verification branch; the missing-
        # account dummy bcrypt comparison is represented as a failed check.
        self.n["bcrypt"] = SimpleNamespace(checkpw=lambda *_: False)
        self.pending = {
            "_id": "member", "id": "member", "username": "learner", "email": "learner@example.test",
            "password_hash": hashlib.sha256(b"test-password").hexdigest(), "status": "pending",
            "active_session_id": "existing-session", "membership_plan": "Monthly",
            "bio": "Keep my profile", "followers": ["coach"], "experience_points": 300,
        }
        self.db = SimpleNamespace(users=Collection([self.pending,
            {"_id": "admin", "id": "admin", "username": "admin", "email": "admin@example.test",
             "status": "approved", "is_admin": True, "active_session_id": "admin-session"},
            {"_id": "other", "id": "other", "username": "other", "email": "other@example.test",
             "status": "approved", "active_session_id": "other-session"},
        ]))
        for name in ("billing_credentials", "billing_rate_limits", "billing_events", "billing_payments", "billing_checkouts"):
            setattr(self.db, name, Collection())
        self.n.update(db=self.db, manager=SimpleNamespace(broadcast=noop, send_admin_notification=noop),
                      email_service=None, award_xp=noop, send_notification_to_user=noop,
                      send_approval_confirmation=noop, send_welcome_email=noop,
                      send_approval_notification=noop, send_rejection_notification=noop)
        self.provider = Provider()
        self.service = SquareBillingService(self.db, self.n["require_profile_owner"], self.n["verify_password"],
                                           settings=SETTINGS, provider=self.provider, now=lambda: self.clock)
        self.app = FastAPI()
        self.app.include_router(self.service.router())
        async def member_probe():
            return {"member_data": True}
        self.n["api_router"].add_api_route("/member-probe", member_probe)
        self.app.include_router(self.n["api_router"], dependencies=[Depends(self.n["require_legacy_active_session"])])
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="https://app.example.test")
        self.member_headers = {"X-User-ID": "member", "X-Session-ID": "existing-session"}
        self.admin_headers = {"X-User-ID": "admin", "X-Session-ID": "admin-session"}

    async def asyncTearDown(self):
        await self.client.aclose()

    async def auth(self):
        response = await self.client.post("/api/billing/auth", json={"username": "learner", "password": "test-password"})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json(), {"X-Billing-Token": response.json()["billing_token"]}

    async def checkout(self, plan="monthly", key=None):
        response = await self.client.post("/api/billing/checkout", headers=self.member_headers,
                                          json={"plan_id": plan, "idempotency_key": key or str(uuid.uuid4())})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        saved = await self.db.billing_checkouts.find_one({"checkout_id": result["checkout_id"]})
        return result, saved

    def event(self, payment_id="pay_1", event_id="event_1", **changes):
        result = {"merchant_id": SETTINGS.merchant_id, "event_id": event_id, "type": "payment.updated",
                  "data": {"object": {"payment": {"id": payment_id}}}}
        result.update(changes)
        return result

    async def webhook(self, event, signature_url=None, tamper=False):
        raw = json.dumps(event, separators=(",", ":")).encode()
        signature = base64.b64encode(hmac.new(SETTINGS.signature_key.encode(),
            (signature_url or SETTINGS.notification_url).encode() + raw, hashlib.sha256).digest()).decode()
        return await self.client.post("/api/billing/square/webhook", content=raw + (b" " if tamper else b""),
                                       headers={"X-Square-Hmacsha256-Signature": signature, "Content-Type": "application/json"})

    async def activate(self, plan="monthly", payment_id="pay_1"):
        _, checkout = await self.checkout(plan)
        self.provider.complete(checkout, payment_id)
        await self.webhook(self.event(payment_id, "event_" + payment_id))
        await self.service.process_once()
        return checkout

    async def user(self):
        return await self.db.users.find_one({"id": "member"})

    async def test_unconfigured_checkout_makes_no_provider_calls(self):
        self.service.settings = SquareSettings()
        plans = (await self.client.get("/api/billing/plans")).json()
        self.assertFalse(plans["automatic_checkout_available"])
        self.assertFalse(plans["automatic_activation_available"])
        self.assertFalse(plans["recurring"])
        self.assertEqual([p["amount_cents"] for p in plans["plans"]], [9900, 49900, 89900])
        response = await self.client.post("/api/billing/checkout", headers=self.member_headers,
            json={"plan_id": "monthly", "idempotency_key": str(uuid.uuid4())})
        self.assertEqual(response.status_code, 503)
        self.assertFalse(self.provider.calls)
        self.assertFalse(self.db.billing_checkouts.rows)
        self.assertFalse(replace(SETTINGS, merchant_id="OTHER_MERCHANT").ready)

    async def test_pending_billing_proof_is_hashed_scoped_and_does_not_change_member_session(self):
        proof, headers = await self.auth()
        self.assertEqual(proof["scope"], "billing")
        saved = self.db.billing_credentials.rows[0]
        self.assertEqual(saved["_id"], hashlib.sha256(proof["billing_token"].encode()).hexdigest())
        self.assertNotIn(proof["billing_token"], str(saved))
        self.assertEqual((await self.user())["active_session_id"], "existing-session")
        self.assertEqual((await self.client.get("/api/billing/status", headers=headers)).status_code, 200)
        self.assertEqual((await self.client.get("/api/member-probe", headers=headers)).status_code, 401)
        forged = {"X-User-ID": "member", "X-Session-ID": proof["billing_token"]}
        self.assertEqual((await self.client.get("/api/member-probe", headers=forged)).status_code, 401)
        denied = await self.client.get("/api/member-probe", headers=self.member_headers)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json()["detail"]["code"], "membership_required")

    async def test_billing_accepts_verified_legacy_hash_and_invalidates_proof_after_reset(self):
        old_hash = self.db.users.rows[0].pop("password_hash")
        self.db.users.rows[0]["hashed_password"] = old_hash
        _, headers = await self.auth()
        self.assertEqual((await self.client.get("/api/billing/status", headers=headers)).status_code, 200)
        self.assertEqual(self.db.users.writes, 0)
        self.db.users.rows[0]["password_hash"] = hashlib.sha256(b"reset-password").hexdigest()
        self.assertEqual((await self.client.get("/api/billing/status", headers=headers)).status_code, 401)
        stale = await self.client.post("/api/billing/auth", json={"username": "learner", "password": "test-password"})
        self.assertEqual(stale.status_code, 401)

    async def test_dummy_verification_never_authenticates_an_existing_hashless_account(self):
        self.db.users.rows[0].pop("password_hash")
        # Even if a supplied password matches the fixed dummy hash, that is not
        # an account credential and must not mint a billing proof.
        self.service.verify_password = lambda *_: True
        response = await self.client.post("/api/billing/auth", json={"username": "learner", "password": "dummy-password"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.db.billing_credentials.rows, [])
        self.assertEqual(self.db.users.writes, 0)
        self.assertEqual((await self.user())["active_session_id"], "existing-session")

    async def test_proof_expiry_password_change_rejection_and_disabled_are_enforced_on_use(self):
        _, headers = await self.auth()
        self.clock += timedelta(minutes=21)
        self.assertEqual((await self.client.get("/api/billing/status", headers=headers)).status_code, 401)
        self.clock = NOW
        _, headers = await self.auth()
        self.db.users.rows[0]["password_hash"] = "changed"
        self.assertEqual((await self.client.get("/api/billing/status", headers=headers)).status_code, 401)
        self.db.users.rows[0]["password_hash"] = self.pending["password_hash"]
        for changes in ({"status": "rejected"}, {"status": "pending", "disabled": True}):
            self.db.users.rows[0].update(changes)
            issued = await self.client.post("/api/billing/auth", json={"username": "learner", "password": "test-password"})
            self.assertEqual(issued.status_code, 401)
            self.assertEqual((await self.client.get("/api/billing/status", headers=headers)).status_code, 403)

    async def test_billing_auth_has_durable_rate_limit_and_generic_failures(self):
        first = await self.client.post("/api/billing/auth", json={"username": "learner", "password": "incorrect"})
        absent = await self.client.post("/api/billing/auth", json={"username": "absent", "password": "incorrect"})
        self.assertEqual(first.status_code, 401)
        self.assertEqual(first.json(), absent.json())
        for _ in range(7):
            await self.client.post("/api/billing/auth", json={"username": "learner", "password": "incorrect"})
        blocked = await self.client.post("/api/billing/auth", json={"username": "learner", "password": "test-password"})
        self.assertEqual(blocked.status_code, 429)
        self.assertFalse(self.db.billing_credentials.rows)
        self.assertEqual(self.db.users.writes, 0)

    async def test_member_binding_prices_and_same_key_retries_are_server_owned(self):
        key = str(uuid.uuid4())
        first, saved = await self.checkout(key=key)
        second, _ = await self.checkout(key=key)
        self.assertEqual(first, second)
        self.assertEqual(len(self.provider.links), 1)
        self.assertEqual(saved["user_id"], "member")
        self.assertEqual(saved["amount_cents"], 9900)
        self.assertEqual(saved["request_body"]["order"]["reference_id"], saved["checkout_id"])
        self.assertLessEqual(len(saved["checkout_id"]), 40)
        self.assertNotIn("learner@example.test", str(saved["request_body"]))
        self.assertNotIn("existing-session", str(saved["request_body"]))
        changed = await self.client.post("/api/billing/checkout", headers=self.member_headers,
            json={"plan_id": "six_months", "idempotency_key": key})
        self.assertEqual(changed.status_code, 409)
        forged = await self.client.post("/api/billing/checkout", headers=self.member_headers,
            json={"plan_id": "monthly", "idempotency_key": str(uuid.uuid4()), "amount_cents": 1, "user_id": "other"})
        self.assertEqual(forged.status_code, 422)
        self.assertFalse(active_membership(await self.user(), self.clock))

    async def test_lost_checkout_response_retries_same_persisted_provider_request(self):
        self.provider.create_failure_after_accept = True
        result, saved = await self.checkout()
        self.assertEqual(result["status"], "preparing")
        self.assertIsNone(result["checkout_url"])
        self.assertEqual(len(self.provider.links), 1)
        original_body = deepcopy(saved["request_body"])
        self.clock += timedelta(minutes=2)
        await self.service.process_once()
        recovered = await self.db.billing_checkouts.find_one({"_id": saved["_id"]})
        self.assertEqual(recovered["status"], "ready")
        self.assertEqual(len(self.provider.links), 1)
        self.assertEqual([call[1] for call in self.provider.calls if call[0] == "create_link"], [original_body, original_body])

    async def test_location_merchant_currency_mismatch_never_produces_checkout(self):
        self.provider.location_override = {"id": SETTINGS.location_id, "merchant_id": "OTHER", "currency": "USD", "status": "ACTIVE"}
        response = await self.client.post("/api/billing/checkout", headers=self.member_headers,
            json={"plan_id": "monthly", "idempotency_key": str(uuid.uuid4())})
        self.assertEqual(response.status_code, 503)
        self.assertFalse(self.provider.links)

    async def test_webhook_signature_raw_body_exact_url_merchant_and_event_dedup(self):
        event = self.event()
        self.assertEqual((await self.webhook(event, tamper=True)).status_code, 403)
        self.assertEqual((await self.webhook(event, signature_url=SETTINGS.notification_url + "/")).status_code, 403)
        self.assertEqual((await self.webhook({**event, "merchant_id": "OTHER"})).status_code, 403)
        accepted = await self.webhook(event)
        duplicate = await self.webhook(event)
        self.assertEqual(accepted.status_code, 200)
        self.assertFalse(accepted.json()["duplicate"])
        self.assertTrue(duplicate.json()["duplicate"])
        self.assertEqual(len(self.db.billing_events.rows), 1)
        changed = await self.webhook(self.event("pay_different"))
        self.assertEqual(changed.status_code, 409)
        self.assertFalse(self.provider.calls)
        self.assertFalse(active_membership(await self.user(), self.clock))

    async def test_only_provider_completed_payment_activates_and_preserves_history(self):
        _, checkout = await self.checkout()
        self.provider.complete(checkout, status="APPROVED")
        await self.webhook(self.event())
        await self.service.process_once()
        self.assertFalse(active_membership(await self.user(), self.clock))
        self.provider.payments["pay_1"]["status"] = "COMPLETED"
        await self.webhook(self.event(event_id="event_2"))
        await self.service.process_once()
        user = await self.user()
        self.assertEqual(user["id"], self.pending["id"])
        self.assertEqual(user["bio"], self.pending["bio"])
        self.assertEqual(user["followers"], self.pending["followers"])
        self.assertEqual(user["experience_points"], self.pending["experience_points"])
        self.assertEqual(user["billing_entitlement"]["paid_through"], add_months(self.clock, 1))
        self.assertFalse(user["billing_entitlement"]["legacy_access"])
        self.assertEqual(user["status"], "approved")
        self.assertEqual(self.db.billing_payments.rows[0]["status"], "granted")
        self.assertEqual((await self.client.get("/api/member-probe", headers=self.member_headers)).status_code, 200)

    async def test_same_payment_under_different_events_never_extends_twice(self):
        await self.activate()
        before = deepcopy((await self.user())["billing_entitlement"])
        for event_id in ("another_event", "third_event"):
            await self.webhook(self.event(event_id=event_id))
        await self.service.process_once()
        self.assertEqual((await self.user())["billing_entitlement"], before)
        self.assertEqual(len(self.db.billing_payments.rows), 1)

    async def test_one_checkout_cannot_grant_two_different_completed_payments(self):
        checkout = await self.activate()
        before = deepcopy((await self.user())["billing_entitlement"])
        self.provider.complete(checkout, "pay_second")
        result = await self.service.verify_payment("pay_second")
        self.assertEqual(result, ("review", "checkout_already_has_payment"))
        self.assertEqual((await self.user())["billing_entitlement"], before)

    async def test_unmatched_dashboard_payment_never_claims_user_from_email_or_metadata(self):
        self.provider.orders["external_order"] = {"id": "external_order", "reference_id": "member",
            "location_id": SETTINGS.location_id, "state": "COMPLETED", "total_money": {"amount": 9900, "currency": "USD"}}
        self.provider.payments["pay_static"] = {"id": "pay_static", "order_id": "external_order",
            "location_id": SETTINGS.location_id, "status": "COMPLETED", "source_type": "CARD",
            "amount_money": {"amount": 9900, "currency": "USD"}, "total_money": {"amount": 9900, "currency": "USD"},
            "buyer_email_address": "learner@example.test", "reference_id": "member"}
        result = await self.service.verify_payment("pay_static")
        self.assertEqual(result, ("review", "unmatched_order"))
        self.assertFalse(active_membership(await self.user(), self.clock))
        self.assertIsNone(self.db.billing_payments.rows[0]["user_id"])
        self.assertNotIn("buyer_email_address", str(self.db.billing_payments.rows))

    async def test_existing_other_members_checkout_reference_cannot_rebind_a_payment(self):
        _, mine = await self.checkout()
        other_user = await self.db.users.find_one({"id": "other"})
        other_result = await self.service.create_checkout(other_user,
            CheckoutRequest(plan_id="monthly", idempotency_key=str(uuid.uuid4())))
        other = await self.db.billing_checkouts.find_one({"checkout_id": other_result["checkout_id"]})
        self.provider.complete(mine)
        # A real local reference is insufficient: its persisted Square order ID
        # must match too. Email and reference changes cannot move the receipt.
        self.provider.orders[mine["order_id"]]["reference_id"] = other["checkout_id"]
        before = deepcopy(self.db.users.rows)
        result = await self.service.verify_payment("pay_1")
        self.assertEqual(result, ("review", "checkout_binding_mismatch"))
        self.assertEqual(self.db.users.rows, before)
        self.assertFalse(self.db.billing_payments.rows[0].get("user_id"))

    async def test_mismatched_or_refunded_payment_requires_review_without_grant(self):
        _, checkout = await self.checkout()
        variants = (
            {"amount_money": {"amount": 1, "currency": "USD"}},
            {"amount_money": {"amount": 9900, "currency": "EUR"}},
            {"total_money": {"amount": 9901, "currency": "USD"}},
            {"location_id": "OTHER_LOCATION"},
            {"refunded_money": {"amount": 1, "currency": "USD"}},
            {"refund_ids": ["refund_1"]},
            {"source_type": "EXTERNAL"},
        )
        for index, changes in enumerate(variants):
            with self.subTest(changes=changes):
                payment_id = "bad_" + str(index)
                self.provider.complete(checkout, payment_id, **changes)
                status, _ = await self.service.verify_payment(payment_id)
                self.assertEqual(status, "review")
                self.assertFalse(active_membership(await self.user(), self.clock))

    async def test_malformed_provider_order_is_reviewed_without_starving_other_events(self):
        _, broken = await self.checkout()
        _, valid = await self.checkout("six_months")
        self.provider.complete(broken, "bad_structure")
        self.provider.orders[broken["order_id"]]["metadata"] = ["unexpected"]
        self.provider.complete(valid, "good_structure")
        await self.webhook(self.event("bad_structure", "bad_event"))
        await self.webhook(self.event("good_structure", "good_event"))
        await self.service.process_once()
        self.assertEqual((await self.user())["billing_entitlement"]["paid_through"], add_months(self.clock, 6))
        rows = {row["payment_id"]: row for row in self.db.billing_payments.rows}
        self.assertEqual(rows["bad_structure"]["status"], "review")
        self.assertEqual(rows["good_structure"]["status"], "granted")

    async def test_provider_failure_retries_from_durable_event_without_access(self):
        _, checkout = await self.checkout()
        self.provider.complete(checkout)
        await self.webhook(self.event())
        self.provider.payment_failure = SquareProblem("square_unavailable")
        await self.service.process_once()
        self.assertEqual(self.db.billing_events.rows[0]["status"], "retry")
        self.assertFalse(active_membership(await self.user(), self.clock))
        self.provider.payment_failure = None
        self.clock += timedelta(minutes=2)
        await self.service.process_once()
        self.assertEqual(self.db.billing_events.rows[0]["status"], "processed")
        self.assertTrue(active_membership(await self.user(), self.clock))

    async def test_crash_after_atomic_user_grant_recovers_without_double_term(self):
        _, checkout = await self.checkout()
        self.provider.complete(checkout)
        await self.webhook(self.event())
        failed = False
        async def fail_bookkeeping(query, update):
            nonlocal failed
            if not failed and update.get("$set", {}).get("status") == "granted":
                failed = True
                raise RuntimeError("synthetic interrupted bookkeeping")
        self.db.billing_payments.before_update = fail_bookkeeping
        await self.service.process_once()
        first = deepcopy((await self.user())["billing_entitlement"])
        self.assertEqual(first["paid_through"], add_months(NOW, 1))
        self.assertEqual(self.db.billing_events.rows[0]["status"], "processing")
        self.clock += timedelta(seconds=61)
        await self.service.process_once()
        self.assertEqual((await self.user())["billing_entitlement"], first)
        self.assertEqual(self.db.billing_payments.rows[0]["status"], "granted")
        self.assertEqual(self.db.billing_events.rows[0]["status"], "processed")

    async def test_crash_before_user_grant_retries_and_does_not_lose_verified_payment(self):
        _, checkout = await self.checkout()
        self.provider.complete(checkout)
        await self.webhook(self.event())
        failed = False
        async def fail_before_grant(query, update):
            nonlocal failed
            if not failed and "billing_entitlement" in update.get("$set", {}):
                failed = True
                raise RuntimeError("synthetic storage outage")
        self.db.users.before_update = fail_before_grant
        await self.service.process_once()
        self.assertFalse(active_membership(await self.user(), self.clock))
        self.assertEqual(self.db.billing_payments.rows[0]["status"], "verified")
        self.clock += timedelta(seconds=61)
        await self.service.process_once()
        self.assertTrue(active_membership(await self.user(), self.clock))
        self.assertEqual(len((await self.user())["billing_entitlement"]["payment_ids"]), 1)

    async def test_concurrent_renewals_add_each_term_once(self):
        _, monthly = await self.checkout()
        _, six_months = await self.checkout("six_months")
        self.provider.complete(monthly, "pay_monthly")
        self.provider.complete(six_months, "pay_six")
        results = await asyncio.gather(self.service.verify_payment("pay_monthly"), self.service.verify_payment("pay_six"))
        self.assertEqual([item[0] for item in results], ["granted", "granted"])
        entitlement = (await self.user())["billing_entitlement"]
        self.assertEqual(entitlement["paid_through"], add_months(self.clock, 7))
        self.assertEqual(len(entitlement["payment_ids"]), 2)
        self.assertFalse(entitlement["legacy_access"])

    async def test_lifetime_never_shortens_and_legacy_lifetime_cannot_buy_again(self):
        _, monthly = await self.checkout()
        await self.activate("lifetime", "pay_lifetime")
        self.provider.complete(monthly, "pay_old_monthly")
        await self.service.verify_payment("pay_old_monthly")
        self.assertTrue(membership_snapshot(await self.user(), self.clock)["lifetime"])
        self.assertEqual((await self.user())["membership_plan"], "Lifetime")
        self.db.users.rows[0] = {**deepcopy(self.pending), "status": "approved", "membership_plan": "Lifetime"}
        response = await self.client.post("/api/billing/checkout", headers=self.member_headers,
            json={"plan_id": "monthly", "idempotency_key": str(uuid.uuid4())})
        self.assertEqual(response.status_code, 409)
        self.assertTrue(membership_snapshot(await self.user(), self.clock)["lifetime"])
        self.assertFalse(membership_snapshot({**self.pending, "membership_plan": "Lifetime"}, self.clock)["active"])

    async def test_legacy_approved_access_is_grandfathered_without_changing_original_plan(self):
        self.db.users.rows[0].update(status="approved", membership_plan="Yearly")
        await self.activate()
        user = await self.user()
        self.assertTrue(user["billing_entitlement"]["legacy_access"])
        self.assertEqual(user["membership_plan"], "Yearly")
        self.assertTrue(active_membership(user, self.clock + timedelta(days=400)))
        self.assertEqual(membership_snapshot(user, self.clock)["source"], "legacy")

    async def test_refund_after_grant_flags_review_without_erasing_or_revoking_access(self):
        await self.activate()
        grant = deepcopy((await self.user())["billing_entitlement"])
        self.provider.payments["pay_1"]["refunded_money"] = {"amount": 9900, "currency": "USD"}
        await self.webhook(self.event(event_id="refund_followup"))
        await self.service.process_once()
        receipt = self.db.billing_payments.rows[0]
        self.assertEqual(receipt["status"], "granted")
        self.assertTrue(receipt["review_required"])
        self.assertEqual(receipt["reason"], "refund_requires_review")
        self.assertEqual((await self.user())["billing_entitlement"], grant)

    async def test_rejected_or_disabled_member_is_not_activated_by_later_payment(self):
        _, checkout = await self.checkout()
        self.provider.complete(checkout)
        self.db.users.rows[0]["status"] = "rejected"
        self.assertEqual((await self.service.verify_payment("pay_1"))[0], "review")
        self.assertEqual((await self.user())["status"], "rejected")
        self.assertNotIn("billing_entitlement", await self.user())

    async def test_sandbox_verifies_without_real_access_and_environment_filters_checkout_urls(self):
        self.service.settings = replace(SETTINGS, environment="sandbox")
        self.provider.settings = self.service.settings
        plans = (await self.client.get("/api/billing/plans")).json()
        self.assertTrue(plans["automatic_checkout_available"])
        self.assertFalse(plans["automatic_activation_available"])
        _, checkout = await self.checkout()
        self.provider.complete(checkout)
        self.assertEqual(await self.service.verify_payment("pay_1"), ("sandbox_verified", "test_payment_no_access"))
        self.assertEqual((await self.user())["status"], "pending")
        self.assertNotIn("billing_entitlement", await self.user())
        await self.checkout("six_months")
        self.service.settings = SETTINGS
        status = (await self.client.get("/api/billing/status", headers=self.member_headers)).json()
        self.assertEqual(status["checkouts"], [])
        self.assertEqual(status["payments"][0]["environment"], "sandbox")
        self.assertFalse(status["entitlement"]["active"])

    async def test_missing_webhook_is_reconciled_from_known_order_tender(self):
        _, checkout = await self.checkout()
        self.provider.complete(checkout)
        self.clock += timedelta(minutes=3)
        await self.service.process_once()
        self.assertTrue(active_membership(await self.user(), self.clock))
        self.assertEqual(self.db.billing_payments.rows[0]["status"], "granted")
        self.assertFalse(self.db.billing_events.rows)

    async def test_abandoned_reconciliation_stops_after_seven_days_but_late_webhook_works(self):
        _, checkout = await self.checkout()
        self.clock += timedelta(days=8)
        before = len(self.provider.calls)
        await self.service.process_once()
        self.assertEqual(len(self.provider.calls), before)
        saved = await self.db.billing_checkouts.find_one({"_id": checkout["_id"]})
        self.assertTrue(saved["reconcile_paused"])
        self.assertEqual(saved["status"], "ready")
        self.provider.complete(checkout)
        await self.webhook(self.event())
        await self.service.process_once()
        self.assertTrue(active_membership(await self.user(), self.clock))

    async def test_canceled_checkout_stops_polling_without_grant(self):
        _, checkout = await self.checkout()
        self.provider.orders[checkout["order_id"]]["state"] = "CANCELED"
        self.clock += timedelta(minutes=3)
        await self.service.process_once()
        saved = await self.db.billing_checkouts.find_one({"_id": checkout["_id"]})
        self.assertEqual(saved["status"], "canceled")
        self.assertFalse(active_membership(await self.user(), self.clock))

    async def test_paid_expiry_blocks_all_member_gates_but_preserves_session_and_billing(self):
        await self.activate()
        self.db.users.rows[0]["billing_entitlement"]["paid_through"] = min(self.clock, datetime.utcnow()) - timedelta(seconds=1)
        user = await self.user()
        self.assertFalse(active_membership(user))
        self.assertFalse(stock_membership(user, datetime.utcnow()))
        self.assertEqual((await self.client.get("/api/member-probe", headers=self.member_headers)).status_code, 403)
        session = await self.client.get("/api/users/member/session-status", params={"session_id": "existing-session"})
        self.assertEqual(session.status_code, 200)
        self.assertTrue(session.json()["valid"])
        billing = await self.client.get("/api/billing/status", headers=self.member_headers)
        self.assertEqual(billing.status_code, 200)
        self.assertFalse(billing.json()["entitlement"]["active"])
        with self.assertRaises(HTTPException) as rejected:
            await nautilus_member(request(self.member_headers), self.db)
        self.assertEqual(rejected.exception.status_code, 403)
        manager = self.n["ConnectionManager"]()
        socket = Socket()
        await manager.connect(socket, "member", "existing-session")
        await manager.send_personal_message('{"type":"chat","content":"private"}', socket)
        self.assertEqual(socket.closed, [4403])
        self.assertFalse(socket.messages)
        self.assertEqual((await self.user())["active_session_id"], "existing-session")

    async def test_admin_tracking_requires_current_admin_and_survives_admin_paid_expiry(self):
        await self.activate()
        self.assertEqual((await self.client.get("/api/billing/admin/payments", headers=self.member_headers)).status_code, 403)
        _, proof = await self.auth()
        self.assertEqual((await self.client.get("/api/billing/admin/payments", headers=proof)).status_code, 401)
        self.db.users.rows[1]["billing_entitlement"] = {"managed_by": "square", "paid_through": NOW - timedelta(days=1)}
        response = await self.client.get("/api/billing/admin/payments", headers=self.admin_headers)
        self.assertEqual(response.status_code, 200)
        row = response.json()["payments"][0]
        self.assertEqual(row["username"], "learner")
        self.assertEqual(row["payment_id"], "pay_1")
        self.assertNotIn("password_hash", row)
        self.assertNotIn("active_session_id", row)

    async def test_ordinary_member_cannot_spoof_admin_on_approval_conversion_or_role_routes(self):
        self.db.users.rows[0]["status"] = "approved"
        cases = (
            ("/api/users/approve", {"user_id": "other", "approved": True, "admin_id": "admin"}),
            ("/api/users/change-role", {"user_id": "member", "new_role": "admin", "admin_id": "admin"}),
            ("/api/users/member/role", {"role": "admin", "admin_id": "admin"}),
            ("/api/admin/convert-trial?user_id=other&admin_id=admin", None),
        )
        before = deepcopy(self.db.users.rows)
        for path, body in cases:
            with self.subTest(path=path):
                response = await self.client.post(path, headers=self.member_headers, json=body)
                self.assertEqual(response.status_code, 403, response.text)
                self.assertEqual(self.db.users.rows, before)

    async def test_manual_admin_approval_is_distinct_from_verified_payment(self):
        response = await self.client.post("/api/users/approve", headers=self.admin_headers,
            json={"user_id": "member", "approved": True, "admin_id": "admin"})
        self.assertEqual(response.status_code, 200, response.text)
        user = await self.user()
        self.assertTrue(user["manual_access_granted"])
        self.assertEqual(user["manual_access_granted_by"], "admin")
        self.assertEqual(membership_snapshot(user, self.clock)["source"], "manual")
        self.assertFalse(self.db.billing_payments.rows)

    async def test_profile_writes_cannot_overwrite_access_or_payment_fields(self):
        await self.activate()
        before = await self.user()
        poison = {"status": "approved", "role": "admin", "is_admin": True,
                  "manual_access_granted": True, "billing_entitlement": {"lifetime": True},
                  "membership_plan": "Lifetime"}
        put = await self.client.put("/api/users/member/profile", headers=self.member_headers,
            json={**poison, "screen_name": "New screen name"})
        post = await self.client.post("/api/users/member/profile", headers=self.member_headers,
            json={**poison, "bio": "Updated bio"})
        self.assertEqual(put.status_code, 200, put.text)
        self.assertEqual(post.status_code, 200, post.text)
        user = await self.user()
        for field in poison:
            self.assertEqual(user.get(field), before.get(field), field)
        self.assertEqual(user["bio"], "Updated bio")

    def test_calendar_month_terms_and_managed_expiry_do_not_fall_back(self):
        self.assertEqual(add_months(datetime(2027, 1, 31), 1), datetime(2027, 2, 28))
        self.assertEqual(add_months(datetime(2028, 1, 31), 1), datetime(2028, 2, 29))
        self.assertFalse(membership_snapshot({"status": "approved", "membership_plan": "Lifetime",
            "billing_entitlement": {"managed_by": "square", "paid_through": NOW - timedelta(days=1)}}, NOW)["active"])
        self.assertFalse(membership_snapshot({"status": "approved", "billing_entitlement": None}, NOW)["active"])


if __name__ == "__main__":
    unittest.main()
