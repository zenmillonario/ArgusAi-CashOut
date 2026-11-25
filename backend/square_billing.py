"""One-time memberships, with explicit administrator approval by default.

Manual receipts record an administrator's review, never Square API verification.
The optional automatic integration requires a separate, explicit mode selection.
Durable receipts and a compare-and-swap user update make either path retry-safe
without requiring Mongo multi-document transactions.
"""
from __future__ import annotations

import asyncio
import base64
import calendar
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
from urllib.parse import quote, urlsplit

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

try:
    from .membership import iso_date, membership_snapshot, utc_datetime
    from .account_credentials import password_record
except ImportError:
    from membership import iso_date, membership_snapshot, utc_datetime
    from account_credentials import password_record

logger = logging.getLogger(__name__)
PRODUCTION_MERCHANT = "VMNWS6K9Y9SN5"
SQUARE_VERSION = "2026-11-18"
TOKEN_TTL = timedelta(minutes=20)
MAX_WEBHOOK_BYTES = 256 * 1024
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,192}$")
PLAN_CATALOG = (
    {"id": "monthly", "label": "1 month", "membership_label": "Monthly",
     "amount_cents": 9900, "currency": "USD", "term_months": 1,
     "manual_payment_url": "https://checkout.square.site/merchant/VMNWS6K9Y9SN5/checkout/SGEVW3GCMZ2X4WSWREYY2RF2"},
    {"id": "six_months", "label": "6 months", "membership_label": "SixMonths",
     "amount_cents": 49900, "currency": "USD", "term_months": 6,
     "manual_payment_url": "https://checkout.square.site/merchant/VMNWS6K9Y9SN5/checkout/FEYSOTOHEO6HE6N4ONWO4F7C"},
    {"id": "lifetime", "label": "Lifetime", "membership_label": "Lifetime",
     "amount_cents": 89900, "currency": "USD", "term_months": None,
     "manual_payment_url": "https://checkout.square.site/merchant/VMNWS6K9Y9SN5/checkout/7YFX27AOC4IUYZ5DXP4W3VBL"},
)
PLANS = {plan["id"]: plan for plan in PLAN_CATALOG}
BILLABLE_STATUSES = frozenset(("pending", "approved", "trial", "trial_expired"))


def _https_url(value):
    try:
        parsed = urlsplit(value)
        return bool(parsed.scheme == "https" and parsed.hostname and not parsed.username
                    and not parsed.password and not parsed.fragment and parsed.port in (None, 443))
    except (ValueError, TypeError):
        return False


def _square_url(value):
    if not isinstance(value, str) or not _https_url(value):
        return False
    parsed = urlsplit(value)
    return (parsed.hostname in ("square.link", "sandbox.square.link")
            and bool(re.fullmatch(r"/u/[A-Za-z0-9_-]+", parsed.path))
            and not parsed.query)


def _id(value):
    return isinstance(value, str) and ID_PATTERN.fullmatch(value) is not None


def _money(value, expected):
    return (isinstance(value, dict) and type(value.get("amount")) is int
            and value["amount"] == expected and value.get("currency") == "USD")


def add_months(value, months):
    total = value.year * 12 + value.month - 1 + months
    year, month = total // 12, total % 12 + 1
    return value.replace(year=year, month=month, day=min(value.day, calendar.monthrange(year, month)[1]))


@dataclass(frozen=True)
class SquareSettings:
    approval_mode: str = "manual"
    enabled: bool = False
    environment: str = ""
    access_token: str = ""
    merchant_id: str = ""
    location_id: str = ""
    signature_key: str = ""
    notification_url: str = ""
    return_url: str = ""

    @classmethod
    def from_env(cls):
        return cls(
            approval_mode=os.getenv("MEMBERSHIP_APPROVAL_MODE", "manual").strip().lower(),
            enabled=os.getenv("SQUARE_BILLING_ENABLED", "").lower() == "true",
            environment=os.getenv("SQUARE_ENVIRONMENT", "").strip(),
            access_token=os.getenv("SQUARE_ACCESS_TOKEN", "").strip(),
            merchant_id=os.getenv("SQUARE_MERCHANT_ID", "").strip(),
            location_id=os.getenv("SQUARE_LOCATION_ID", "").strip(),
            signature_key=os.getenv("SQUARE_WEBHOOK_SIGNATURE_KEY", "").strip(),
            notification_url=os.getenv("SQUARE_WEBHOOK_NOTIFICATION_URL", "").strip(),
            return_url=os.getenv("SQUARE_CHECKOUT_RETURN_URL", "").strip(),
        )

    @property
    def mode(self):
        # Stale Square credentials or the previous enable flag alone must never
        # opt this deployment into automatic payment handling.
        return "automatic" if self.approval_mode == "automatic" else "manual"

    @property
    def ready(self):
        return bool(self.mode == "automatic" and self.enabled and self.environment in ("sandbox", "production")
                    and self.access_token and _id(self.merchant_id) and _id(self.location_id)
                    and len(self.signature_key) >= 16 and _https_url(self.notification_url)
                    and _https_url(self.return_url)
                    and (self.environment != "production" or self.merchant_id == PRODUCTION_MERCHANT))

    @property
    def namespace(self):
        return self.environment + ":" + self.merchant_id


class SquareProblem(Exception):
    """Only an application-defined code is stored or logged, never provider data."""
    def __init__(self, code, retry=True):
        self.code, self.retry = code, retry
        super().__init__(code)


class SquareClient:
    def __init__(self, settings):
        self.settings = settings

    async def request(self, method, path, body=None):
        if not self.settings.ready:
            raise SquareProblem("square_unconfigured")
        base = ("https://connect.squareup.com" if self.settings.environment == "production"
                else "https://connect.squareupsandbox.com")
        headers = {"Authorization": "Bearer " + self.settings.access_token,
                   "Square-Version": SQUARE_VERSION, "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
                response = await client.request(method, base + path, headers=headers, json=body)
            if response.status_code >= 400:
                # Retrying GETs is safe; CreatePaymentLink always uses the same
                # persisted idempotency key and exact body, including after timeout.
                retry = response.status_code in (401, 403, 404, 408, 409, 429) or response.status_code >= 500
                raise SquareProblem("square_http_" + str(response.status_code), retry=retry)
            if response.status_code >= 300:
                raise SquareProblem("square_unexpected_redirect", retry=False)
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("errors"):
                raise SquareProblem("square_invalid_response")
            return payload
        except (httpx.HTTPError, ValueError, TypeError):
            raise SquareProblem("square_unavailable") from None

    async def location(self):
        return (await self.request("GET", "/v2/locations/" + quote(self.settings.location_id, safe=""))).get("location")

    async def create_link(self, body):
        return await self.request("POST", "/v2/online-checkout/payment-links", body)

    async def payment(self, payment_id):
        return (await self.request("GET", "/v2/payments/" + quote(payment_id, safe=""))).get("payment")

    async def order(self, order_id):
        return (await self.request("GET", "/v2/orders/" + quote(order_id, safe=""))).get("order")


class BillingAuth(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=512)


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: str = Field(min_length=1, max_length=32)
    idempotency_key: str = Field(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


class ManualApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    user_id: str = Field(min_length=1, max_length=240)
    plan_id: str = Field(min_length=1, max_length=32)
    payment_reference: str = Field(min_length=3, max_length=192, pattern=r"^[A-Za-z0-9_-]+$")
    confirm_payment_reviewed: bool = Field(strict=True)


class SquareBillingService:
    def __init__(self, db, require_owner, verify_password, settings=None, provider=None, now=datetime.utcnow,
                 welcome_sender=None):
        self.db, self.require_owner, self.verify_password = db, require_owner, verify_password
        self.settings = settings or SquareSettings.from_env()
        self.provider = provider or SquareClient(self.settings)
        self.now = now
        self.welcome_sender = welcome_sender
        self._location_checked_at = None

    def plans(self):
        return {
            "plans": [{k: v for k, v in plan.items() if k != "membership_label"} for plan in PLAN_CATALOG],
            "approval_mode": self.settings.mode,
            "automatic_checkout_available": self.settings.ready,
            "automatic_activation_available": self.settings.ready and self.settings.environment == "production",
            "environment": self.settings.environment if self.settings.environment in ("sandbox", "production") else None,
            "recurring": False,
        }

    async def initialize(self):
        # _id supplies payment/event/checkout uniqueness even before secondary
        # indexes are ready. TTL indexes remove credentials and rate-limit buckets.
        await self.db.billing_credentials.create_index("expires_at", expireAfterSeconds=0)
        await self.db.billing_rate_limits.create_index("expires_at", expireAfterSeconds=0)
        await self.db.billing_events.create_index([("namespace", 1), ("status", 1), ("next_attempt_at", 1)])
        await self.db.billing_payments.create_index([("user_id", 1), ("received_at", -1)])
        await self.db.billing_checkouts.create_index([("namespace", 1), ("status", 1), ("next_attempt_at", 1)])
        await self.db.billing_checkouts.create_index([("namespace", 1), ("order_id", 1)])

    async def _rate_limit(self, identity, maximum, seconds):
        now = self.now()
        window = int(now.timestamp()) // seconds
        key = hashlib.sha256((identity + ":" + str(window)).encode()).hexdigest()
        try:
            # Motor/PyMongo accept True for ReturnDocument.AFTER.
            row = await self.db.billing_rate_limits.find_one_and_update(
                {"_id": key}, {"$inc": {"attempts": 1},
                               "$setOnInsert": {"expires_at": now + timedelta(seconds=seconds * 2)}},
                upsert=True, return_document=True)
        except Exception as error:
            if getattr(error, "code", None) == 11000:
                return await self._rate_limit(identity, maximum, seconds)
            raise
        if row["attempts"] > maximum:
            raise HTTPException(429, detail={"code": "billing_rate_limited", "message": "Too many attempts. Please try again later."})

    async def authenticate(self, request, body):
        username = body.username.strip()
        peer = getattr(getattr(request, "client", None), "host", "unknown")
        await self._rate_limit("auth-ip:" + str(peer), 30, 60)
        await self._rate_limit("auth-name:" + username.casefold(), 8, 900)
        user = await self.db.users.find_one({"username": {"$regex": "^" + re.escape(username) + "$", "$options": "i"}})
        # A fixed bcrypt hash equalizes the missing-user verification path. This
        # is not a credential for any account; a real user record is still required.
        dummy = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOY8eDCgHv5fW7zYZ9OLaDmjmSAEjOnIm"
        _, stored_hash = password_record(user)
        candidate = stored_hash or dummy
        valid = (len(body.password.encode("utf-8")) <= 72
                 and await asyncio.to_thread(self.verify_password, body.password, candidate))
        if not stored_hash or not valid or not user or user.get("status") not in BILLABLE_STATUSES or user.get("disabled") is True:
            raise HTTPException(401, detail={"code": "billing_auth_failed", "message": "Unable to verify this account. Check your credentials or contact support."})
        token = secrets.token_urlsafe(32)
        expires = self.now() + TOKEN_TTL
        await self.db.billing_credentials.insert_one({
            "_id": hashlib.sha256(token.encode()).hexdigest(), "user_id": user["id"], "scope": "billing",
            "credential_fingerprint": hashlib.sha256(candidate.encode()).hexdigest(),
            "created_at": self.now(), "expires_at": expires,
        })
        return {"billing_token": token, "expires_at": iso_date(expires), "user_id": user["id"], "scope": "billing"}

    async def actor(self, request, admin=False):
        if admin or not request.headers.get("x-billing-token"):
            user_id = request.headers.get("x-user-id", "")
            if not user_id or len(user_id) > 240:
                raise HTTPException(401, "Please sign in again.")
            user = await self.require_owner(request, user_id)
        else:
            token = request.headers.get("x-billing-token", "")
            if not 32 <= len(token) <= 160:
                raise HTTPException(401, "Billing sign-in has expired.")
            proof = await self.db.billing_credentials.find_one({"_id": hashlib.sha256(token.encode()).hexdigest()})
            if not proof or proof.get("scope") != "billing" or not utc_datetime(proof.get("expires_at")) or utc_datetime(proof["expires_at"]) <= self.now():
                raise HTTPException(401, "Billing sign-in has expired.")
            user = await self.db.users.find_one({"id": proof["user_id"]})
            _, current_hash = password_record(user)
            fingerprint = hashlib.sha256((current_hash or "").encode()).hexdigest()
            if not secrets.compare_digest(fingerprint, proof["credential_fingerprint"]):
                raise HTTPException(401, "Billing sign-in has expired.")
        if not user or user.get("status") not in BILLABLE_STATUSES or user.get("disabled") is True:
            raise HTTPException(403, "This account requires administrator review.")
        if admin and (not user.get("is_admin") or user.get("status") != "approved"):
            raise HTTPException(403, "Administrator access required.")
        return user

    @staticmethod
    def _manual_key(reference):
        normalized = reference.strip().casefold()
        digest = hashlib.sha256(normalized.encode()).hexdigest()
        return "production:" + PRODUCTION_MERCHANT + ":manual:" + digest

    async def approve_manual(self, admin, body, background_tasks):
        """Record the owner's review and apply exactly one purchased term.

        This route never calls Square and cannot establish provider verification.
        The reference is the durable idempotency key, including across accounts.
        """
        if self.settings.mode != "manual":
            existing_manual = await self.db.billing_payments.find_one({"_id": self._manual_key(body.payment_reference)})
            if not existing_manual or existing_manual.get("evidence_source") != "admin_review":
                raise HTTPException(409, "New manual paid approval requires manual approval mode. Automatic approval mode is selected.")
        if not body.confirm_payment_reviewed:
            raise HTTPException(400, "Review the completed Square payment and confirm the member, plan and amount first.")
        plan = PLANS.get(body.plan_id)
        if not plan:
            raise HTTPException(400, "Choose a supported paid membership plan.")
        user = await self.db.users.find_one({"id": body.user_id})
        if not user:
            raise HTTPException(404, "Member not found.")
        if user.get("status") not in BILLABLE_STATUSES or user.get("disabled") is True:
            raise HTTPException(409, "This account requires administrator review before access can be approved.")
        await self._rate_limit("manual-approval:" + admin["id"], 120, 3600)
        # A reference already recorded by the optional automatic integration is
        # not a new manually reviewed payment. Do not grant the term a second time.
        existing = await self.db.billing_payments.find({
            "namespace": "production:" + PRODUCTION_MERCHANT,
            "payment_id": {"$regex": "^" + re.escape(body.payment_reference) + "$", "$options": "i"},
        }).to_list(3)
        if any(row.get("evidence_source") != "admin_review" for row in existing):
            raise HTTPException(409, "This reference already has a payment record. Review that record before changing access.")
        now = self.now()
        row = {
            "_id": self._manual_key(body.payment_reference),
            "namespace": "production:" + PRODUCTION_MERCHANT,
            "merchant_id": PRODUCTION_MERCHANT, "environment": "production",
            "payment_id": body.payment_reference, "user_id": user["id"], "plan_id": plan["id"],
            "amount_cents": plan["amount_cents"], "amount_source": "plan_catalog", "currency": "USD",
            "term_months": plan["term_months"], "membership_label": plan["membership_label"],
            "status": "reviewed", "review_required": False, "received_at": now,
            "evidence_source": "admin_review", "verification_status": "admin_reviewed",
            "confirm_payment_reviewed": True, "reviewed_by": admin["id"], "reviewed_at": now,
            "welcome_email_status": "pending", "welcome_email_requested_at": now,
            "welcome_email_updated_at": now, "welcome_recipient": user.get("email"),
        }
        inserted = await self._insert_once(self.db.billing_payments, row)
        saved = await self.db.billing_payments.find_one({"_id": row["_id"]})
        if (saved.get("user_id") != user["id"] or saved.get("plan_id") != plan["id"]
                or saved.get("evidence_source") != "admin_review"):
            raise HTTPException(409, "This Square reference is already assigned to a different member or plan.")
        if saved.get("review_required"):
            raise HTTPException(409, "This payment record needs administrator review before it can be approved.")
        outcome = await self.apply_grant(saved, saved)
        if outcome != "granted":
            raise HTTPException(409, "Access could not be applied. Review the account and saved payment record.")
        saved = await self.db.billing_payments.find_one({"_id": row["_id"]})
        if saved.get("welcome_email_status") == "pending":
            if not self.welcome_sender or not saved.get("welcome_recipient"):
                await self.db.billing_payments.update_one(
                    {"_id": saved["_id"], "welcome_email_status": "pending"},
                    {"$set": {"welcome_email_status": "unavailable", "welcome_email_updated_at": self.now(),
                              "welcome_email_reason": "email_not_configured" if not self.welcome_sender else "member_email_missing"}})
            else:
                # Multiple request retries can queue this task. Its atomic claim
                # below permits one send only, without a permanent worker.
                background_tasks.add_task(self.send_manual_welcome, saved["_id"])
        saved = await self.db.billing_payments.find_one({"_id": row["_id"]})
        user = await self.db.users.find_one({"id": user["id"]})
        return {"user_id": user["id"], "duplicate": not inserted,
                "entitlement": membership_snapshot(user, self.now()),
                "payment": self.payment_view(saved, admin=True), "welcome_email": self.welcome_view(saved)}

    async def send_manual_welcome(self, payment_key):
        """Claim one welcome attempt; never infer delivery or blindly resend.

        A timeout/crash after the claim is ambiguous. It stays sending/unknown for
        administrator review; approving the same payment again cannot resend it.
        """
        now = self.now()
        row = await self.db.billing_payments.find_one_and_update(
            {"_id": payment_key, "status": "granted", "evidence_source": "admin_review",
             "welcome_email_status": "pending"},
            {"$set": {"welcome_email_status": "sending", "welcome_email_started_at": now,
                      "welcome_email_updated_at": now}}, return_document=True)
        if not row:
            return
        status, reason, message_id = "unknown", "send_outcome_unknown", None
        try:
            user = await self.db.users.find_one({"id": row["user_id"]})
            if not self.welcome_sender or not row.get("welcome_recipient"):
                status, reason = "unavailable", "email_not_configured"
            elif not user or user.get("disabled") is True or user.get("status") != "approved":
                status, reason = "unavailable", "account_requires_review"
            else:
                plan = PLANS[row["plan_id"]]
                outcome = await self.welcome_sender(
                    row["welcome_recipient"], user.get("real_name") or user.get("username") or "member",
                    user.get("username") or "", plan["label"] + " (one-time purchase)")
                if isinstance(outcome, dict) and outcome.get("status") in ("sent", "failed", "unknown", "unavailable"):
                    status = outcome["status"]
                    message_id = outcome.get("provider_message_id")
                    reason = {"sent": None, "failed": "provider_rejected", "unknown": "send_outcome_unknown",
                              "unavailable": "email_not_configured"}[status]
                elif outcome is True:
                    status, reason = "sent", None  # Accepted by the configured sender, not proof of delivery.
                # Older boolean-only senders cannot distinguish a rejection from
                # an accepted send followed by a timeout. False remains unknown.
        except asyncio.CancelledError:
            await self.db.billing_payments.update_one(
                {"_id": payment_key, "welcome_email_status": "sending"},
                {"$set": {"welcome_email_status": "unknown", "welcome_email_reason": "send_interrupted",
                          "welcome_email_updated_at": self.now()}})
            raise
        except Exception:
            logger.warning("Membership welcome outcome is unknown; administrator review required.")
        changes = {"welcome_email_status": status, "welcome_email_reason": reason,
                   "welcome_email_updated_at": self.now()}
        if isinstance(message_id, str) and 0 < len(message_id) <= 240:
            changes["welcome_provider_message_id"] = message_id
        await self.db.billing_payments.update_one(
            {"_id": payment_key, "welcome_email_status": "sending"}, {"$set": changes})

    def welcome_view(self, row):
        status = row.get("welcome_email_status")
        started = utc_datetime(row.get("welcome_email_started_at"))
        if status == "sending" and started and self.now() - started >= timedelta(minutes=10):
            status = "unknown"
        return {"status": status, "requested_at": iso_date(row.get("welcome_email_requested_at")),
                "updated_at": iso_date(row.get("welcome_email_updated_at"))}

    async def _location(self):
        if not self.settings.ready:
            raise SquareProblem("square_unconfigured")
        if self._location_checked_at and self.now() - self._location_checked_at < timedelta(seconds=60):
            return
        location = await self.provider.location()
        if (not isinstance(location, dict) or location.get("id") != self.settings.location_id
                or location.get("merchant_id") != self.settings.merchant_id
                or location.get("currency") != "USD" or location.get("status") != "ACTIVE"):
            raise SquareProblem("square_seller_mismatch", retry=False)
        self._location_checked_at = self.now()

    def _checkout_key(self, checkout_id):
        return self.settings.namespace + ":checkout:" + checkout_id

    async def create_checkout(self, user, body):
        if not self.settings.ready:
            raise HTTPException(503, detail={"code": "square_unconfigured", "message": "Automatic checkout is unavailable. Shared payment links require manual review."})
        if body.plan_id not in PLANS:
            raise HTTPException(400, "Choose a supported paid membership plan.")
        if membership_snapshot(user, self.now()).get("lifetime"):
            raise HTTPException(409, "This account already has lifetime access.")
        await self._rate_limit("checkout:" + user["id"], 12, 3600)
        plan = PLANS[body.plan_id]
        digest = hashlib.sha256((self.settings.namespace + "\0" + user["id"] + "\0" + body.idempotency_key).encode()).hexdigest()
        checkout_id = digest[:32]  # Square Order.reference_id has a 40-character limit.
        now = self.now()
        request_body = {
            "idempotency_key": digest,
            "order": {"location_id": self.settings.location_id, "reference_id": checkout_id,
                      "line_items": [{"uid": "cashout-membership", "name": "CashOut AI — " + plan["label"],
                                      "quantity": "1", "base_price_money": {"amount": plan["amount_cents"], "currency": "USD"}}],
                      "metadata": {"cashout_checkout": checkout_id, "cashout_plan": plan["id"]}},
            "checkout_options": {"allow_tipping": False, "enable_coupon": False, "enable_loyalty": False,
                                 "ask_for_shipping_address": False, "redirect_url": self.settings.return_url},
        }
        row = {"_id": self._checkout_key(checkout_id), "checkout_id": checkout_id, "namespace": self.settings.namespace,
               "user_id": user["id"], "plan_id": plan["id"], "amount_cents": plan["amount_cents"], "currency": "USD",
               "term_months": plan["term_months"], "membership_label": plan["membership_label"],
               "environment": self.settings.environment, "merchant_id": self.settings.merchant_id,
               "location_id": self.settings.location_id, "request_key": digest, "request_body": request_body,
               "created_at": now, "status": "preparing", "attempts": 0, "next_attempt_at": now,
               "lease_until": datetime.min}
        await self._insert_once(self.db.billing_checkouts, row)
        saved = await self.db.billing_checkouts.find_one({"_id": row["_id"]})
        if saved.get("user_id") != user["id"] or saved.get("request_key") != digest or saved.get("plan_id") != plan["id"]:
            raise HTTPException(409, "Use the original plan when retrying this checkout, or begin a new checkout.")
        if saved["status"] in ("fulfilled", "canceled"):
            raise HTTPException(409, "This checkout has completed or was canceled. Refresh billing status.")
        if saved["status"] in ("preparing", "retry"):
            await self.prepare_checkout(saved)
            saved = await self.db.billing_checkouts.find_one({"_id": row["_id"]})
        if saved["status"] == "review":
            raise HTTPException(503, detail={"code": "checkout_review_required", "message": "Checkout is unavailable and requires administrator review."})
        return {"checkout_id": checkout_id, "plan_id": plan["id"],
                "status": "ready" if saved["status"] == "ready" else "preparing",
                "checkout_url": saved.get("checkout_url") if saved["status"] == "ready" else None}

    async def _insert_once(self, collection, row):
        try:
            result = await collection.update_one({"_id": row["_id"]}, {"$setOnInsert": row}, upsert=True)
            return result.upserted_id is not None
        except Exception as error:
            if getattr(error, "code", None) != 11000:
                raise
            return False

    async def prepare_checkout(self, candidate):
        now, lease = self.now(), secrets.token_hex(16)
        saved = await self.db.billing_checkouts.find_one_and_update(
            {"_id": candidate["_id"], "status": {"$in": ["preparing", "retry"]},
             "next_attempt_at": {"$lte": now}, "lease_until": {"$lte": now}},
            {"$set": {"lease": lease, "lease_until": now + timedelta(seconds=60)}, "$inc": {"attempts": 1}},
            return_document=True)
        if not saved:
            return
        try:
            if saved["namespace"] != self.settings.namespace or saved["location_id"] != self.settings.location_id:
                raise SquareProblem("checkout_configuration_changed", retry=False)
            await self._location()
            result = await self.provider.create_link(saved["request_body"])
            link = result.get("payment_link") if isinstance(result, dict) else None
            if not isinstance(link, dict) or not _id(link.get("id")) or not _id(link.get("order_id")) or not _square_url(link.get("url")):
                raise SquareProblem("square_invalid_checkout_response")
            if self.settings.environment == "production" and urlsplit(link["url"]).hostname != "square.link":
                raise SquareProblem("square_checkout_environment_mismatch", retry=False)
            outcome = {"status": "ready", "order_id": link["order_id"], "payment_link_id": link["id"],
                       "checkout_url": link["url"], "next_reconcile_at": now + timedelta(minutes=2),
                       "reason": None}
        except SquareProblem as error:
            outcome = {"status": "retry" if error.retry else "review", "reason": error.code,
                       "next_attempt_at": now + timedelta(seconds=min(900, 15 * 2 ** min(saved["attempts"], 6)))}
        await self.db.billing_checkouts.update_one({"_id": saved["_id"], "lease": lease},
                                                  {"$set": {**outcome, "lease_until": datetime.min}})

    async def receive_webhook(self, request):
        if not self.settings.ready:
            raise HTTPException(503, "Square verification is not configured.")
        length = 0
        chunks = []
        async for chunk in request.stream():
            length += len(chunk)
            if length > MAX_WEBHOOK_BYTES:
                raise HTTPException(413, "Webhook is too large.")
            chunks.append(chunk)
        raw = b"".join(chunks)
        signature = request.headers.get("x-square-hmacsha256-signature", "")
        expected = base64.b64encode(hmac.new(self.settings.signature_key.encode(),
                    self.settings.notification_url.encode() + raw, hashlib.sha256).digest()).decode()
        if not signature or len(signature) > 128 or not hmac.compare_digest(signature.encode(), expected.encode()):
            raise HTTPException(403, "Invalid Square signature.")
        try:
            event = json.loads(raw)
        except (ValueError, UnicodeError):
            raise HTTPException(400, "Invalid Square event.") from None
        if not isinstance(event, dict) or event.get("merchant_id") != self.settings.merchant_id:
            raise HTTPException(403, "Square merchant does not match.")
        if not _id(event.get("event_id")):
            raise HTTPException(400, "Square event ID is required.")
        kind = event.get("type")
        if kind not in ("payment.created", "payment.updated", "refund.created", "refund.updated"):
            return {"accepted": True, "event_id": event["event_id"], "verification_status": "ignored"}
        data = event.get("data") or {}
        obj = data.get("object", {}) if isinstance(data, dict) else {}
        record = obj.get("payment" if kind.startswith("payment.") else "refund", {}) if isinstance(obj, dict) else {}
        payment_id = record.get("id" if kind.startswith("payment.") else "payment_id") if isinstance(record, dict) else None
        if not _id(payment_id):
            raise HTTPException(400, "Square payment ID is required.")
        digest = hashlib.sha256(json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        now = self.now()
        row = {"_id": self.settings.namespace + ":event:" + event["event_id"], "namespace": self.settings.namespace,
               "event_id": event["event_id"], "event_type": kind, "payment_id": payment_id,
               "payload_digest": digest, "received_at": now, "status": "queued",
               "attempts": 0, "next_attempt_at": now, "lease_until": datetime.min}
        inserted = await self._insert_once(self.db.billing_events, row)
        saved = await self.db.billing_events.find_one({"_id": row["_id"]})
        if saved["payload_digest"] != digest:
            raise HTTPException(409, "This Square event ID has conflicting content.")
        return {"accepted": True, "event_id": event["event_id"], "duplicate": not inserted,
                "verification_status": saved["status"]}

    async def _observe_payment(self, payment, event):
        payment_id = payment["id"]
        amount = payment.get("amount_money") or {}
        if not isinstance(amount, dict):
            amount = {}
        now = self.now()
        row = {"_id": self.settings.namespace + ":payment:" + payment_id,
               "namespace": self.settings.namespace, "payment_id": payment_id,
               "environment": self.settings.environment, "merchant_id": self.settings.merchant_id,
               "order_id": payment.get("order_id"),
               "amount_cents": amount.get("amount") if type(amount.get("amount")) is int and 0 <= amount["amount"] <= 10**12 else None,
               "currency": amount.get("currency"), "status": "observed", "review_required": False,
               "received_at": now, "provider_created_at": iso_date(payment.get("created_at")),
               "event_id": event.get("event_id"), "user_id": None, "plan_id": None}
        await self._insert_once(self.db.billing_payments, row)
        # A verification lease can have created a minimal receipt before these
        # provider fields became available. Preserve already-verified fields.
        await self.db.billing_payments.update_one({"_id": row["_id"], "status": "observed"}, {"$set": {
            key: row[key] for key in ("order_id", "amount_cents", "currency", "provider_created_at")}})
        return await self.db.billing_payments.find_one({"_id": row["_id"]})

    async def _review(self, payment_row, reason):
        # A later refund never erases a verified receipt or silently revokes access.
        changes = {"review_required": True, "reason": reason, "last_checked_at": self.now()}
        if payment_row.get("status") not in ("granted", "sandbox_verified"):
            changes["status"] = "review"
        await self.db.billing_payments.update_one({"_id": payment_row["_id"]}, {"$set": changes})
        return "review", reason

    async def verify_payment(self, payment_id, event=None):
        # Different event IDs for the same payment share one verification lease.
        # This also serializes refund review against a simultaneous grant attempt.
        if not self.settings.ready:
            raise SquareProblem("square_unconfigured")
        if not _id(payment_id):
            raise SquareProblem("invalid_payment_id", retry=False)
        now, lease = self.now(), secrets.token_hex(16)
        row = {"_id": self.settings.namespace + ":payment:" + payment_id,
               "namespace": self.settings.namespace, "payment_id": payment_id,
               "environment": self.settings.environment, "merchant_id": self.settings.merchant_id,
               "received_at": now, "status": "observed", "review_required": False,
               "user_id": None, "plan_id": None, "verification_lease_until": datetime.min,
               "event_id": (event or {}).get("event_id")}
        await self._insert_once(self.db.billing_payments, row)
        claimed = await self.db.billing_payments.find_one_and_update(
            {"_id": row["_id"], "$or": [{"verification_lease_until": {"$exists": False}},
                                       {"verification_lease_until": {"$lte": now}}]},
            {"$set": {"verification_lease": lease, "verification_lease_until": now + timedelta(seconds=60)}},
            return_document=True)
        if not claimed:
            raise SquareProblem("payment_verification_in_progress")
        try:
            return await self._verify_payment(payment_id, event, lease)
        finally:
            await self.db.billing_payments.update_one(
                {"_id": row["_id"], "verification_lease": lease},
                {"$set": {"verification_lease_until": datetime.min}})

    async def _verify_payment(self, payment_id, event=None, lease=None):
        event = event or {}
        await self._location()
        payment = await self.provider.payment(payment_id)
        if not isinstance(payment, dict) or payment.get("id") != payment_id:
            raise SquareProblem("square_invalid_payment_response")
        row = await self._observe_payment(payment, event)
        if payment.get("location_id") != self.settings.location_id:
            return await self._review(row, "payment_location_mismatch")
        refunds = payment.get("refunded_money")
        if (event.get("event_type", "").startswith("refund.") or payment.get("refund_ids")
                or (refunds is not None and not _money(refunds, 0))):
            return await self._review(row, "refund_requires_review")
        if payment.get("status") != "COMPLETED":
            if row.get("status") == "granted":
                return await self._review(row, "payment_status_changed")
            await self.db.billing_payments.update_one({"_id": row["_id"]}, {"$set": {
                "status": "awaiting_completion", "reason": "payment_not_completed", "last_checked_at": self.now()}})
            return "observed", "payment_not_completed"
        if payment.get("source_type") not in ("CARD", "BANK_ACCOUNT", "WALLET", "BUY_NOW_PAY_LATER", "SQUARE_ACCOUNT"):
            return await self._review(row, "payment_source_requires_review")
        order_id = payment.get("order_id")
        if not _id(order_id):
            return await self._review(row, "unmatched_order")
        order = await self.provider.order(order_id)
        if not isinstance(order, dict) or order.get("id") != order_id:
            raise SquareProblem("square_invalid_order_response")
        checkout_id = order.get("reference_id")
        checkout = (await self.db.billing_checkouts.find_one({"_id": self._checkout_key(checkout_id)})) if _id(checkout_id) else None
        if not checkout:
            return await self._review(row, "unmatched_order")
        if not checkout.get("order_id") and checkout.get("status") in ("preparing", "retry"):
            raise SquareProblem("checkout_mapping_pending")
        if (checkout.get("order_id") != order_id or checkout.get("namespace") != self.settings.namespace
                or checkout.get("location_id") != self.settings.location_id or order.get("location_id") != self.settings.location_id):
            return await self._review(row, "checkout_binding_mismatch")
        expected = checkout["amount_cents"]
        metadata, lines = order.get("metadata") or {}, order.get("line_items") or []
        if (not isinstance(metadata, dict) or not isinstance(lines, list)
                or not _money(payment.get("amount_money"), expected) or not _money(payment.get("total_money"), expected)
                or (payment.get("tip_money") is not None and not _money(payment["tip_money"], 0))
                or not _money(order.get("total_money"), expected)
                or order.get("state") not in ("OPEN", "COMPLETED")
                or metadata.get("cashout_checkout") != checkout_id or metadata.get("cashout_plan") != checkout["plan_id"]
                or len(lines) != 1 or not isinstance(lines[0], dict) or lines[0].get("quantity") != "1"
                or not _money(lines[0].get("base_price_money"), expected)):
            return await self._review(row, "payment_or_order_mismatch")
        if row.get("user_id") and (row["user_id"] != checkout["user_id"] or row.get("plan_id") != checkout["plan_id"]):
            return await self._review(row, "payment_identity_conflict")
        claimed = await self.db.billing_checkouts.find_one_and_update(
            {"_id": checkout["_id"], "$or": [{"claimed_payment_id": {"$exists": False}}, {"claimed_payment_id": payment_id}]},
            {"$set": {"claimed_payment_id": payment_id}}, return_document=True)
        if not claimed:
            return await self._review(row, "checkout_already_has_payment")
        # The trusted member mapping comes solely from our persisted checkout.
        await self.db.billing_payments.update_one({"_id": row["_id"]}, {"$set": {
            "user_id": checkout["user_id"], "plan_id": checkout["plan_id"], "checkout_id": checkout_id,
            "amount_cents": expected, "currency": "USD",
            "evidence_source": "square_api", "verification_status": "provider_verified",
            "verified_at": row.get("verified_at") or self.now(), "last_checked_at": self.now(),
            "status": row["status"] if row["status"] == "granted" else "verified"}})
        row = await self.db.billing_payments.find_one({"_id": row["_id"]})
        if (row.get("verification_lease") != lease
                or not utc_datetime(row.get("verification_lease_until"))
                or utc_datetime(row["verification_lease_until"]) <= self.now()):
            raise SquareProblem("payment_verification_lease_expired")
        if row.get("review_required"):
            # Once flagged, contradictory/refund evidence needs human review.
            return "review", row.get("reason", "manual_review_required")
        if self.settings.environment == "sandbox":
            await self.db.billing_payments.update_one({"_id": row["_id"]}, {"$set": {"status": "sandbox_verified", "reason": "test_payment_no_access"}})
            await self.db.billing_checkouts.update_one({"_id": checkout["_id"]}, {"$set": {"status": "fulfilled"}})
            return "sandbox_verified", "test_payment_no_access"
        outcome = await self.apply_grant(row, checkout)
        if outcome == "granted":
            await self.db.billing_checkouts.update_one({"_id": checkout["_id"]}, {"$set": {"status": "fulfilled"}})
        return outcome, None

    async def apply_grant(self, payment, checkout):
        """One atomic user mutation contains both grant and applied-payment ID.

        A crash before it can retry. A crash after it finds the ID and completes
        bookkeeping without adding the term twice. Competing renewals use CAS.
        """
        manual = payment.get("evidence_source") == "admin_review"
        if not manual and not self.settings.ready:
            raise SquareProblem("square_unconfigured")
        for _ in range(12):
            receipt = await self.db.billing_payments.find_one({"_id": payment["_id"]})
            if not receipt:
                raise SquareProblem("payment_record_missing")
            if receipt.get("review_required"):
                return "review"
            if manual:
                if (receipt.get("evidence_source") != "admin_review"
                        or receipt.get("confirm_payment_reviewed") is not True
                        or not receipt.get("reviewed_by") or not utc_datetime(receipt.get("reviewed_at"))
                        or receipt.get("user_id") != checkout.get("user_id")
                        or receipt.get("plan_id") != checkout.get("plan_id")):
                    raise SquareProblem("admin_review_record_invalid", retry=False)
            elif (receipt.get("verification_lease") != payment.get("verification_lease")
                    or not utc_datetime(receipt.get("verification_lease_until"))
                    or utc_datetime(receipt["verification_lease_until"]) <= self.now()):
                raise SquareProblem("payment_verification_lease_expired")
            if not manual and await self.db.billing_payments.find_one({"_id": self._manual_key(receipt["payment_id"])}):
                await self._review(receipt, "payment_already_manually_reviewed")
                return "review"
            user = await self.db.users.find_one({"id": checkout["user_id"]})
            if not user or user.get("status") not in BILLABLE_STATUSES or user.get("disabled") is True:
                await self._review(payment, "account_requires_review")
                return "review"
            current = user.get("billing_entitlement")
            previous = current if isinstance(current, dict) and current.get("managed_by") in ("square", "manual_payment") else {}
            applied = previous.get("payment_ids", [])
            if not isinstance(applied, list):
                await self._review(payment, "entitlement_requires_review")
                return "review"
            if payment["_id"] in applied:
                await self.db.billing_payments.update_one({"_id": payment["_id"]}, {"$set": {
                    "status": "granted", "granted_at": receipt.get("granted_at") or self.now(),
                    "reason": None, "entitlement": membership_snapshot(user, self.now())}})
                return "granted"
            if current is not None and not previous:
                await self._review(payment, "entitlement_requires_review")
                return "review"
            now = self.now()
            existing_end = utc_datetime(previous.get("paid_through"))
            base = max(now, existing_end) if existing_end else now
            lifetime = (previous.get("lifetime") is True or checkout["term_months"] is None
                        or ("billing_entitlement" not in user and membership_snapshot(user, now)["lifetime"]))
            end = existing_end if lifetime else add_months(base, checkout["term_months"])
            legacy = previous.get("legacy_access") is True or (user["status"] == "approved" and "billing_entitlement" not in user)
            grant = {"managed_by": "manual_payment" if manual else "square", "version": previous.get("version", 0) + 1,
                     "legacy_access": legacy, "lifetime": lifetime, "paid_through": end,
                     "plan_id": "lifetime" if lifetime else checkout["plan_id"],
                     "payment_ids": applied + [payment["_id"]], "updated_at": now}
            expected = {"id": user["id"], "status": user["status"],
                        "disabled": user["disabled"] if "disabled" in user else {"$exists": False},
                        "billing_entitlement": current if "billing_entitlement" in user else {"$exists": False}}
            changes = {"billing_entitlement": grant, "status": "approved"}
            if not legacy:
                changes["membership_plan"] = "Lifetime" if lifetime else checkout["membership_label"]
            if user["status"] != "approved":
                changes.update(approved_at=now, approved_by=receipt["reviewed_by"] if manual else "square_verified_payment")
            result = await self.db.users.update_one(expected, {"$set": changes})
            if result.modified_count:
                # Deliberately loop: recovery and the normal path use the same
                # already-applied branch rather than two bookkeeping algorithms.
                continue
        raise SquareProblem("entitlement_update_contention")

    async def process_event(self, candidate):
        now, lease = self.now(), secrets.token_hex(16)
        saved = await self.db.billing_events.find_one_and_update(
            {"_id": candidate["_id"], "status": {"$in": ["queued", "retry", "processing"]},
             "next_attempt_at": {"$lte": now}, "lease_until": {"$lte": now}},
            {"$set": {"status": "processing", "lease": lease, "lease_until": now + timedelta(seconds=60)},
             "$inc": {"attempts": 1}}, return_document=True)
        if not saved:
            return
        try:
            status, reason = await self.verify_payment(saved["payment_id"], saved)
            outcome = {"status": "review" if status == "review" else "processed", "result": status,
                       "reason": reason, "processed_at": self.now(), "lease_until": datetime.min}
        except SquareProblem as error:
            outcome = {"status": "retry" if error.retry else "review", "reason": error.code,
                       "lease_until": datetime.min,
                       "next_attempt_at": now + timedelta(seconds=min(900, 15 * 2 ** min(saved["attempts"], 6)))}
        await self.db.billing_events.update_one({"_id": saved["_id"], "lease": lease}, {"$set": outcome})

    async def reconcile_checkout(self, candidate):
        now, lease = self.now(), secrets.token_hex(16)
        saved = await self.db.billing_checkouts.find_one_and_update(
            {"_id": candidate["_id"], "status": "ready", "next_reconcile_at": {"$lte": now},
             "lease_until": {"$lte": now}},
            {"$set": {"lease": lease, "lease_until": now + timedelta(seconds=60),
                      "next_reconcile_at": now + timedelta(minutes=5)}}, return_document=True)
        if not saved:
            return
        try:
            if now - saved["created_at"] >= timedelta(days=7):
                await self.db.billing_checkouts.update_one({"_id": saved["_id"], "lease": lease}, {"$set": {
                    "next_reconcile_at": datetime.max, "reconcile_paused": True,
                    "reconcile_reason": "seven_day_window_ended"}})
                return
            await self._location()
            order = await self.provider.order(saved["order_id"])
            if not isinstance(order, dict) or order.get("id") != saved["order_id"]:
                raise SquareProblem("square_invalid_order_response")
            if order.get("state") == "CANCELED":
                await self.db.billing_checkouts.update_one({"_id": saved["_id"], "lease": lease}, {"$set": {
                    "status": "canceled", "reason": "square_order_canceled"}})
                return
            # This only discovers payment IDs. verify_payment independently reads
            # payment/order and repeats every check; an OPEN order is not proof.
            tenders = order.get("tenders") or []
            if not isinstance(tenders, list):
                raise SquareProblem("square_invalid_order_response")
            for tender in tenders[:8]:
                payment_id = tender.get("payment_id") if isinstance(tender, dict) else None
                if _id(payment_id):
                    await self.verify_payment(payment_id, {"event_id": None})
        except SquareProblem:
            pass  # The next scheduled reconciliation retries; no access is inferred.
        finally:
            await self.db.billing_checkouts.update_one({"_id": saved["_id"], "lease": lease},
                                                      {"$set": {"lease_until": datetime.min}})

    async def process_once(self):
        if not self.settings.ready:
            return
        now = self.now()
        checkouts = await self.db.billing_checkouts.find({"namespace": self.settings.namespace,
            "status": {"$in": ["preparing", "retry"]}, "next_attempt_at": {"$lte": now},
            "lease_until": {"$lte": now}}).sort("next_attempt_at", 1).to_list(5)
        for item in checkouts:
            try:
                await self.prepare_checkout(item)
            except Exception:
                logger.warning("Deferred one checkout; durable lease retained.")
        events = await self.db.billing_events.find({"namespace": self.settings.namespace,
            "status": {"$in": ["queued", "retry", "processing"]}, "next_attempt_at": {"$lte": now},
            "lease_until": {"$lte": now}}).sort("next_attempt_at", 1).to_list(20)
        for item in events:
            try:
                await self.process_event(item)
            except Exception:
                logger.warning("Deferred one payment event; durable lease retained.")
        ready = await self.db.billing_checkouts.find({"namespace": self.settings.namespace, "status": "ready",
            "next_reconcile_at": {"$lte": now}, "lease_until": {"$lte": now}}).sort("next_reconcile_at", 1).to_list(5)
        for item in ready:
            try:
                await self.reconcile_checkout(item)
            except Exception:
                logger.warning("Deferred one checkout reconciliation; durable lease retained.")

    async def run(self):
        while True:
            try:
                await self.initialize()
                break
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("Billing indexes unavailable; will retry initialization.")
                await asyncio.sleep(15)
        while True:
            try:
                await self.process_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                # An unhandled storage failure leaves a durable lease. Another
                # worker can recover it; never acknowledge a missing persistence.
                logger.warning("Billing worker deferred a cycle; durable records retained.")
            await asyncio.sleep(5)

    def payment_view(self, row, admin=False):
        fields = ("payment_id", "plan_id", "amount_cents", "currency", "status", "verified_at",
                  "review_required", "environment", "reason", "received_at",
                  "evidence_source", "verification_status", "reviewed_at")
        if admin:
            fields += ("user_id", "order_id", "checkout_id", "event_id", "granted_at", "reviewed_by")
        result = {field: row.get(field) for field in fields}
        for field in ("verified_at", "received_at", "granted_at", "reviewed_at"):
            if field in result:
                result[field] = iso_date(result[field])
        result["welcome_email"] = self.welcome_view(row)
        return result

    async def status(self, user):
        try:
            from .practice_event import practice_event_summary
        except ImportError:
            from practice_event import practice_event_summary
        # Re-read after authentication: grants can complete during the request.
        user = await self.db.users.find_one({"id": user["id"]})
        if not user or user.get("status") not in BILLABLE_STATUSES or user.get("disabled") is True:
            raise HTTPException(403, "This account requires administrator review.")
        payments = await self.db.billing_payments.find({"user_id": user["id"]}).sort("received_at", -1).to_list(50)
        checkouts = await self.db.billing_checkouts.find({"user_id": user["id"],
            "namespace": self.settings.namespace}).sort("created_at", -1).to_list(20)
        selected_plan = next((plan["id"] for plan in PLAN_CATALOG
                              if plan["membership_label"].casefold() == str(user.get("membership_plan") or "").casefold()), None)
        return {"user_id": user["id"], "username": user.get("username"), "email": user.get("email"),
                "membership_plan": user.get("membership_plan"), "selected_plan_id": selected_plan,
                "approval_mode": self.settings.mode, "account_status": user["status"],
                "entitlement": membership_snapshot(user, self.now()),
                "practice_event": practice_event_summary(user, self.now()),
                "payments": [self.payment_view(row) for row in payments],
                "checkouts": [{"checkout_id": row["checkout_id"], "plan_id": row["plan_id"], "status": row["status"],
                               "environment": row["environment"],
                               "created_at": iso_date(row["created_at"]),
                               "checkout_url": row.get("checkout_url") if row["status"] == "ready" and self.settings.ready else None}
                              for row in checkouts]}

    def router(self):
        router = APIRouter(prefix="/api/billing", tags=["billing"])

        @router.get("/plans")
        async def plans():
            return self.plans()

        @router.post("/auth")
        async def auth(request: Request, body: BillingAuth):
            return await self.authenticate(request, body)

        @router.get("/status")
        async def status(request: Request):
            return await self.status(await self.actor(request))

        @router.post("/checkout")
        async def checkout(request: Request, body: CheckoutRequest):
            return await self.create_checkout(await self.actor(request), body)

        @router.post("/square/webhook")
        async def webhook(request: Request):
            return await self.receive_webhook(request)

        @router.post("/admin/approve")
        async def admin_approve(request: Request, body: ManualApprovalRequest, background_tasks: BackgroundTasks):
            return await self.approve_manual(await self.actor(request, admin=True), body, background_tasks)

        @router.get("/admin/payments")
        async def admin_payments(request: Request, limit: int = 50):
            await self.actor(request, admin=True)
            limit = min(100, max(1, limit))
            rows = await self.db.billing_payments.find({}).sort("received_at", -1).to_list(limit + 1)
            result = []
            for row in rows[:limit]:
                item = self.payment_view(row, admin=True)
                user = await self.db.users.find_one({"id": row["user_id"]}) if row.get("user_id") else None
                item["username"] = user.get("username") if user else None
                result.append(item)
            return {"payments": result, "has_more": len(rows) > limit}

        return router
