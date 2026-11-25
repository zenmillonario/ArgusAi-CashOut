"""A fixed, verified-email practice event; ordinary rolling trials stay closed.

The deployment must explicitly enable this campaign and set its start time.
Verification establishes temporary access on the existing account, never a
password, login session, payment, or permanent approval.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import escape
import hashlib
import logging
import os
import re
import secrets
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

try:
    from .account_credentials import password_record
    from .membership import iso_date, utc_datetime, _base_membership_snapshot
except ImportError:
    from account_credentials import password_record
    from membership import iso_date, utc_datetime, _base_membership_snapshot


logger = logging.getLogger(__name__)
CAMPAIGN_ID = "cashoutai-practice-2026"
CAMPAIGN_END = datetime(2026, 12, 1, 5)  # Midnight after Cyber Monday, Eastern.
ELIGIBLE_STATUSES = frozenset(("pending", "approved", "trial", "trial_expired"))
TOKEN_FIELDS = (
    "practice_event_token_hash", "practice_event_token_expires",
    "practice_event_token_campaign", "practice_event_token_email",
    "practice_event_token_credential",
)


def normalized_email(value):
    return str(value or "").strip().lower()


def credential_fingerprint(user):
    field, value = password_record(user)
    return hashlib.sha256((str(field or "") + "\0" + str(value or "")).encode()).hexdigest()


def unchanged(user, fields):
    return {field: user[field] if field in user else {"$exists": False} for field in fields}


@dataclass(frozen=True)
class PracticeEventSettings:
    enabled: bool = False
    starts_at: datetime | None = None
    frontend_url: str = "https://cashoutai.app"

    @classmethod
    def from_env(cls):
        frontend = (os.getenv("FRONTEND_URL") or os.getenv("REACT_APP_FRONTEND_URL")
                    or "https://cashoutai.app").rstrip("/")
        parsed = urlsplit(frontend)
        if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment or parsed.username:
            frontend = "https://cashoutai.app"
        start = utc_datetime(os.getenv("PRACTICE_EVENT_STARTS_AT"))
        return cls(os.getenv("PRACTICE_EVENT_ENABLED", "false").lower() == "true", start, frontend)

    def status(self, now):
        now = utc_datetime(now)
        if now >= CAMPAIGN_END:
            return "ended"
        if not self.enabled or self.starts_at is None or self.starts_at >= CAMPAIGN_END:
            return "disabled"
        return "scheduled" if now < self.starts_at else "open"

    def public(self, now):
        return {"campaign_id": CAMPAIGN_ID, "status": self.status(now), "server_now": iso_date(now),
                "starts_at": iso_date(self.starts_at), "ends_at": iso_date(CAMPAIGN_END),
                "timezone": "America/New_York", "virtual_balance": 100}


def event_membership(user, now, settings=None):
    """A grant cannot bypass current campaign bounds, account status, or email."""
    now = utc_datetime(now) or datetime.utcnow()
    settings = settings or PracticeEventSettings.from_env()
    grant = user.get("practice_event_grant") if isinstance(user, dict) else None
    if not isinstance(grant, dict) or grant.get("campaign_id") != CAMPAIGN_ID:
        return None
    end = utc_datetime(grant.get("ends_at"))
    verified = utc_datetime(grant.get("verified_at"))
    start = utc_datetime(grant.get("starts_at"))
    active = bool(user.get("status") in ("approved", "trial", "trial_expired")
                  and user.get("disabled") is not True and settings.status(now) == "open"
                  and end == CAMPAIGN_END and start is not None and start <= now
                  and verified is not None and verified <= now
                  and grant.get("verified_email") == normalized_email(user.get("email")))
    return {"active": active, "source": "practice_event", "event_id": CAMPAIGN_ID,
            "paid_through": None, "lifetime": False, "plan_id": None,
            "trial_ends_at": iso_date(CAMPAIGN_END)}


def practice_event_summary(user, now=None, settings=None):
    now = utc_datetime(now) or datetime.utcnow()
    settings = settings or PracticeEventSettings.from_env()
    base = _base_membership_snapshot(user, now)
    grant = event_membership(user, now, settings)
    state = "existing_access" if base["active"] else "enrolled" if grant and grant["active"] else "ended" if grant else "not_enrolled"
    return {"campaign_id": CAMPAIGN_ID, "state": state, "ends_at": iso_date(CAMPAIGN_END)}


class VerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    email: str = Field(min_length=3, max_length=254)
    campaign_id: str = Field(min_length=1, max_length=80)


class VerificationConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=32, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


async def ensure_registration_indexes(db):
    """New registrations get normalized unique keys; historical IDs stay intact."""
    for field in ("registration_email_key", "registration_username_key"):
        await db.users.create_index(field, unique=True, sparse=True)


class PracticeEventService:
    def __init__(self, db, *, settings=None, email_sender=None, now=datetime.utcnow):
        self.db = db
        self.settings = settings or PracticeEventSettings.from_env()
        self.email_sender = email_sender
        self.now = now

    async def initialize(self):
        await self.db.practice_event_limits.create_index("expires_at", expireAfterSeconds=0)
        await self.db.users.create_index("practice_event_token_hash", sparse=True)
        await ensure_registration_indexes(self.db)

    def require_open(self, campaign_id=CAMPAIGN_ID):
        if campaign_id != CAMPAIGN_ID or self.settings.status(self.now()) != "open":
            raise HTTPException(409, {"code": "practice_event_closed", "message": "Practice event enrollment is not open. Your account is still saved."})

    async def limit(self, identity, maximum, seconds):
        now = self.now()
        window = int(now.replace(tzinfo=timezone.utc).timestamp()) // seconds
        key = hashlib.sha256((identity + ":" + str(window)).encode()).hexdigest()
        for attempt in range(2):
            try:
                row = await self.db.practice_event_limits.find_one_and_update(
                    {"_id": key}, {"$inc": {"attempts": 1},
                                   "$setOnInsert": {"expires_at": now + timedelta(seconds=seconds * 2)}},
                    upsert=True, return_document=True)
                break
            except Exception as error:
                if getattr(error, "code", None) != 11000 or attempt:
                    raise
        if row["attempts"] > maximum:
            raise HTTPException(429, {"code": "practice_event_rate_limited", "message": "Too many attempts. Please wait before trying again."})

    async def request(self, request, body, tasks):
        self.require_open(body.campaign_id)
        email = normalized_email(body.email)
        if not re.fullmatch(r"[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,63}", email):
            raise HTTPException(422, "Use a valid email address.")
        peer = request.client.host if request.client else "unknown"
        await self.limit("request-ip:" + peer, 5, 60)
        await self.limit("request-email:" + email, 3, 900)
        if self.email_sender is None:
            raise HTTPException(503, "Practice verification email is temporarily unavailable. Your account is saved.")
        result = {"status": "verification_requested", "ends_at": iso_date(CAMPAIGN_END),
                  "message": "If this email belongs to an eligible account, we will send a practice-event verification link. Check your Inbox and spam folder."}
        user = await self.db.users.find_one({"email": {"$regex": rf"^\s*{re.escape(email)}\s*$", "$options": "i"}})
        if not user or user.get("status") not in ELIGIBLE_STATUSES or user.get("disabled") is True:
            return result
        now = self.now()
        self.require_open(body.campaign_id)
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode()).hexdigest()
        expected = {"id": user["id"], **unchanged(user, (
            "email", "status", "disabled", "password_hash", "hashed_password", "practice_event_token_hash"))}
        changed = await self.db.users.update_one(expected, {"$set": {
            "practice_event_token_hash": digest,
            "practice_event_token_expires": min(now + timedelta(hours=1), CAMPAIGN_END),
            "practice_event_token_campaign": CAMPAIGN_ID,
            "practice_event_token_email": email,
            "practice_event_token_credential": credential_fingerprint(user),
            "practice_event_email_status": "pending",
        }})
        if changed.modified_count == 1:
            tasks.add_task(self.send_verification, user["id"], email,
                           user.get("real_name") or user.get("username") or "member", token, digest)
        return result

    async def send_verification(self, user_id, email, name, token, digest):
        user = await self.db.users.find_one({"id": user_id, "practice_event_token_hash": digest})
        if (not user or user.get("status") not in ELIGIBLE_STATUSES or user.get("disabled") is True
                or normalized_email(user.get("email")) != email
                or user.get("practice_event_token_credential") != credential_fingerprint(user)
                or self.settings.status(self.now()) != "open"):
            return
        link = self.settings.frontend_url + "/?" + urlencode({"event_token": token})
        subject = "Verify your email for the CashOutAI practice event"
        plain = (f"Hi {name},\n\nConfirm your email to join the CashOutAI practice event on your existing account:\n{link}\n\n"
                 "Open the link and press Confirm email. This link does not sign you in or change your password. "
                 "It expires in one hour or at the event cutoff, whichever comes first.\n\n"
                 "Event practice access ends Tuesday, December 1, 2026 at 12:00 a.m. Eastern (after Cyber Monday). "
                 "Practice uses a resettable virtual $100 balance; no card or payment is needed for the event. "
                 "Existing paid or complimentary membership remains in effect.\n\n"
                 "If you did not request this, you can ignore this email.\n\nThe CashOutAI Team")
        html = ("<!doctype html><html lang=\"en\"><body style=\"font-family:Arial,sans-serif;line-height:1.6\">"
                f"<h1>Confirm your email for practice access</h1><p>Hi {escape(str(name))},</p>"
                f"<p><a href=\"{escape(link, quote=True)}\">Review and confirm your email</a></p>"
                "<p>This verifies your email for the practice event on your existing account. It does not sign you in or change your password. "
                "The link expires in one hour or at the event cutoff, whichever comes first.</p>"
                "<p>Practice access ends <strong>Tuesday, December 1, 2026 at 12:00 a.m. Eastern</strong>, after Cyber Monday. "
                "Use a resettable virtual $100 balance. No card or payment is needed for the event. Existing paid or complimentary membership remains in effect.</p>"
                "<p>If you did not request this, ignore this email.</p><p>The CashOutAI Team</p></body></html>")
        try:
            outcome = await self.email_sender(email, subject, plain, html, return_outcome=True)
            status = outcome.get("status") if isinstance(outcome, dict) else "sent" if outcome is True else "unknown"
            if status not in ("sent", "failed", "unknown", "unavailable"):
                status = "unknown"
        except Exception:
            status = "unknown"
            logger.warning("Practice verification email outcome is unknown.")
        await self.db.users.update_one({"id": user_id, "practice_event_token_hash": digest},
                                       {"$set": {"practice_event_email_status": status}})

    async def confirm(self, request, body):
        self.require_open()
        peer = request.client.host if request.client else "unknown"
        await self.limit("confirm-ip:" + peer, 20, 60)
        digest = hashlib.sha256(body.token.encode()).hexdigest()
        for _ in range(4):
            now = self.now()
            self.require_open()
            user = await self.db.users.find_one({"practice_event_token_hash": digest})
            expiry = utc_datetime((user or {}).get("practice_event_token_expires"))
            if (not user or user.get("status") not in ELIGIBLE_STATUSES or user.get("disabled") is True
                    or user.get("practice_event_token_campaign") != CAMPAIGN_ID
                    or not expiry or expiry <= now or expiry > CAMPAIGN_END
                    or user.get("practice_event_token_email") != normalized_email(user.get("email"))
                    or user.get("practice_event_token_credential") != credential_fingerprint(user)):
                raise HTTPException(400, {"code": "practice_event_link_invalid", "message": "This link is invalid, expired, already used, or superseded. Request a new link if the event is still open."})
            base = _base_membership_snapshot(user, now)
            changes = {"practice_event_verified_email": normalized_email(user["email"]),
                       "practice_event_verified_at": now}
            if not base["active"]:
                previous = user.get("practice_event_grant")
                grant = (previous if isinstance(previous, dict) and previous.get("campaign_id") == CAMPAIGN_ID
                         else {"campaign_id": CAMPAIGN_ID, "starts_at": self.settings.starts_at,
                               "ends_at": CAMPAIGN_END, "enrolled_at": now})
                changes["practice_event_grant"] = {**grant, "verified_at": now,
                                                   "verified_email": normalized_email(user["email"])}
                if user["status"] in ("pending", "trial_expired", "trial"):
                    changes.update(status="trial", trial_start_date=user.get("trial_start_date") or now,
                                   trial_end_date=CAMPAIGN_END, practice_event_trial=True)
            expected = {"id": user["id"], **unchanged(user, (
                *TOKEN_FIELDS, "email", "password_hash", "hashed_password", "status", "disabled",
                "billing_entitlement", "manual_access_granted", "trial_end_date", "practice_event_grant"))}
            self.require_open()
            changed = await self.db.users.update_one(expected, {
                "$set": changes, "$unset": {field: "" for field in TOKEN_FIELDS},
            })
            if changed.modified_count == 1:
                self.require_open()
                return {"status": "confirmed", "access": "existing" if base["active"] else "practice_event",
                        "username": user.get("username"), "campaign_id": CAMPAIGN_ID,
                        "ends_at": iso_date(CAMPAIGN_END), "sign_in_required": True}
        raise HTTPException(409, "Account access changed while confirming. Request a fresh verification link.")

    def router(self):
        router = APIRouter(prefix="/api/practice-event", tags=["practice event"])

        @router.get("")
        async def config():
            return self.settings.public(self.now())

        @router.post("/request")
        async def request_verification(request: Request, body: VerificationRequest, background_tasks: BackgroundTasks):
            return await self.request(request, body, background_tasks)

        @router.post("/confirm")
        async def confirm_verification(request: Request, body: VerificationConfirm):
            return await self.confirm(request, body)

        return router
