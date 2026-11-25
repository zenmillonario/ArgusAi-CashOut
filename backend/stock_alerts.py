"""Verified thinkorswim -> Zapier stock alerts and a small durable push outbox.

An alert is durable before intake is acknowledged. Unique Mongo `_id` values make
replays idempotent. Each recipient has an atomic attempt record. Known pre-send
failures may retry; an interrupted/uncertain provider call is never blindly
resent. `accepted` means FCM accepted a request, not device delivery.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
import hashlib
import json
import logging
import os
import re
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, StrictBool

logger = logging.getLogger(__name__)
PUSH_TTL_SECONDS = 300
SYMBOL_RE = re.compile(r"[A-Z]{1,6}(?:[.-][A-Z]{1,2})?\Z")
PRICE_PATTERN = r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?|\.[0-9]+"
PUBLIC_FIELDS = ("id", "category", "source", "symbol", "title", "body", "price",
                 "source_timestamp", "received_at", "url")


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(value):
    return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)).isoformat().replace("+00:00", "Z")


def parse_time(value):
    if not value:
        return None
    if not isinstance(value, str) or len(value) > 160:
        raise HTTPException(422, "Use an original email date with a timezone.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            raise HTTPException(422, "Use an ISO or email date with a timezone.")
    if parsed.tzinfo is None:
        raise HTTPException(422, "The original email date must include a timezone.")
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def first_text(payload, *names):
    for name in names:
        value = payload.get(name)
        if value is not None and value != "":
            if not isinstance(value, str):
                raise HTTPException(422, f"{name} must be text.")
            return value.strip()
    return ""


def normalize_stock_alert(payload, now=None):
    """Keep raw email/account data out of the shared feed and push payload."""
    now = now or utcnow()
    if len(json.dumps(payload).encode()) > 100_000:
        raise HTTPException(413, "Stock alert payload is too large.")
    if payload.get("category", "stocks") != "stocks":
        raise HTTPException(422, "Only the Stocks alert pipeline is supported.")
    content = first_text(payload, "body", "content", "text", "message", "email_body", "Body")
    subject = first_text(payload, "subject", "Subject", "title", "email_subject")
    source_time = parse_time(first_text(payload, "source_timestamp", "sent_at", "date", "Date", "email_date"))
    event_id = first_text(payload, "message_id", "email_message_id", "Message-ID", "Message-Id", "event_id", "email_id", "id")
    if not event_id and isinstance(payload.get("headers"), dict):
        event_id = first_text(payload["headers"], "Message-ID", "Message-Id", "message-id")
    if event_id and len(event_id) > 1000:
        raise HTTPException(422, "The email message ID is too long.")
    if not event_id and source_time is None:
        raise HTTPException(422, "Map the original email Message-ID to message_id, or its dated timestamp to source_timestamp.")
    if source_time and source_time > now + timedelta(minutes=5):
        raise HTTPException(422, "The original email timestamp is in the future.")
    symbol = first_text(payload, "symbol", "ticker").upper().removeprefix("$")
    if not symbol:
        combined = subject + "\n" + content
        patterns = [r"\$([A-Z]{1,6}(?:[.-][A-Z]{1,2})?)\b",
                    r"\(([A-Z]{1,6}(?:[.-][A-Z]{1,2})?)\)",
                    r"\b(?:symbol|ticker)\s*[:=]\s*([A-Z]{1,6}(?:[.-][A-Z]{1,2})?)\b",
                    r"\b([A-Z]{1,6}(?:[.-][A-Z]{1,2})?)\s+(?:price\s+)?alert\b"]
        for pattern in patterns:
            match = re.search(pattern, combined, re.I)
            if match and match[1].upper() not in {"PRICE", "STOCK", "EMAIL", "ALERT", "TEST", "YOUR", "NEW"}:
                symbol = match[1].upper()
                break
    if not SYMBOL_RE.fullmatch(symbol):
        raise HTTPException(422, "Map a valid stock ticker to symbol; the email ticker could not be identified safely.")
    supplied_price = payload.get("price")
    price_text = str(supplied_price) if isinstance(supplied_price, (int, float)) and not isinstance(supplied_price, bool) else first_text(payload, "price")
    if not price_text:
        # Reject partial matches such as $1 from $1,234.56 or $12 from $12,34.
        for pattern in (rf"\bLast\s*=\s*\$?({PRICE_PATTERN})(?![\w]|[.,][0-9])",
                        rf"\b(?:trading at|price\s*[:=])\s*\$?({PRICE_PATTERN})(?![\w]|[.,][0-9])",
                        rf"\$\s*({PRICE_PATTERN})(?![\w]|[.,][0-9])"):
            match = re.search(pattern, content + "\n" + subject, re.I)
            if match:
                price_text = match[1]
                break
    price = None
    if price_text:
        try:
            numeric = Decimal(price_text.removeprefix("$").replace(",", ""))
            if not numeric.is_finite() or numeric <= 0 or numeric > 1_000_000_000:
                raise InvalidOperation
            price = format(numeric, "f")
        except InvalidOperation:
            raise HTTPException(422, "The alert price must be a positive number.")
    # Content is only hashed, never stored or rebroadcast as a trusted admin post.
    canonical = json.dumps([symbol, price, " ".join(subject.split()), " ".join(content.split()),
                            iso(source_time) if source_time else None], separators=(",", ":"), ensure_ascii=False)
    content_digest = hashlib.sha256(canonical.encode()).hexdigest()
    identity = ("email:" + event_id) if event_id else ("dated-content:" + content_digest)
    alert_id = hashlib.sha256(("schwab_thinkorswim\0" + identity).encode()).hexdigest()
    title = f"{symbol} stock alert"
    body = f"{symbol} alert triggered" + (f" at ${price}." if price else ".") + " Open Stocks to review."
    return {"_id": alert_id, "id": alert_id, "category": "stocks", "source": "schwab_thinkorswim",
            "symbol": symbol, "title": title, "body": body, "price": price,
            "source_timestamp": iso(source_time) if source_time else None, "received_at": iso(now),
            "url": "/?" + urlencode({"tab": "stocks", "alert": alert_id, "symbol": symbol}),
            "content_digest": content_digest, "identity_kind": "email_message_id" if event_id else "dated_content",
            "created_at": now, "push_expires_at": min(now + timedelta(seconds=PUSH_TTL_SECONDS),
                source_time + timedelta(seconds=PUSH_TTL_SECONDS)) if source_time else now + timedelta(seconds=PUSH_TTL_SECONDS),
            "audience_ready": False}


def require_webhook_secret(request):
    expected = os.getenv("STOCK_ALERT_WEBHOOK_SECRET", "")
    if len(expected) < 32:
        raise HTTPException(503, "Stock alert intake is not configured.")
    supplied = request.headers.get("x-stock-alert-secret", "")
    if not supplied:
        authorization = request.headers.get("authorization", "")
        if authorization.startswith("Bearer "):
            supplied = authorization[7:].strip()
    if not supplied or len(supplied) > 512 or not secrets.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(401, "Stock alert authentication failed.")


def active_membership(user, now):
    try:
        from .membership import active_membership as effective_membership
    except ImportError:
        from membership import active_membership as effective_membership
    return effective_membership(user, now)


def public_alert(document):
    return {key: document.get(key) for key in PUBLIC_FIELDS}


class StockPreferences(BaseModel):
    stocks_enabled: StrictBool

    class Config:
        extra = "forbid"


class StockAlertService:
    def __init__(self, db, require_owner, active_tokens, provider=None, now=utcnow):
        self.db = db
        self.require_owner = require_owner
        self.active_tokens = active_tokens
        self.provider = provider
        self.now = now

    async def member(self, request):
        user_id = request.headers.get("x-user-id", "")
        if not user_id or len(user_id) > 240:
            raise HTTPException(401, "Please sign in again.")
        member = await self.require_owner(request, user_id)
        if not active_membership(member, self.now()):
            raise HTTPException(403, {"code": "membership_required",
                                     "message": "An active membership is required. Open billing to review access."})
        return member

    async def ingest(self, request, payload):
        require_webhook_secret(request)
        candidate = normalize_stock_alert(payload, self.now())
        inserted = False
        try:
            result = await self.db.stock_alerts.update_one({"_id": candidate["id"]}, {"$setOnInsert": candidate}, upsert=True)
            inserted = result.upserted_id is not None
        except Exception as error:
            if getattr(error, "code", None) != 11000:
                raise
        saved = await self.db.stock_alerts.find_one({"_id": candidate["id"]})
        if saved["content_digest"] != candidate["content_digest"]:
            raise HTTPException(409, "This email ID already identifies a different alert. Check the Zapier field mapping.")
        return {"accepted": True, "alert_id": saved["id"], "duplicate": not inserted,
                "dispatch_status": "recorded", "message": "Stock alert saved. Push acceptance is tracked separately."}

    async def initialize(self):
        await self.db.stock_alerts.create_index([("created_at", -1)])
        await self.db.stock_alerts.create_index([("audience_ready", 1), ("created_at", 1)])
        await self.db.stock_alert_deliveries.create_index([("status", 1), ("next_attempt_at", 1)])
        await self.db.stock_alert_deliveries.create_index([("alert_id", 1)])

    async def prepare_audience(self, alert):
        if alert["push_expires_at"] <= self.now():
            await self.db.stock_alerts.update_one({"_id": alert["id"]}, {"$set": {"audience_ready": True, "push_status": "expired"}})
            return
        # A cursor, rather than a fixed to_list limit, prevents silently dropping
        # members when the community grows. Jobs are idempotent across workers.
        async for user in self.db.users.find({"stock_alert_push_enabled": True, "status": {"$in": ["approved", "trial"]}}):
            if not active_membership(user, self.now()) or not isinstance(user.get("active_session_id"), str) or not user["active_session_id"]:
                continue
            for token in await self.active_tokens([user["id"]]):
                fingerprint = hashlib.sha256(user["active_session_id"].encode()).hexdigest()
                if token.get("session_fingerprint") != fingerprint:
                    continue
                context = hashlib.sha256((user["id"] + "\0" + user["active_session_id"]).encode()).hexdigest()
                job_id = hashlib.sha256((alert["id"] + "\0" + user["id"]).encode()).hexdigest()
                job = {"_id": job_id, "alert_id": alert["id"], "user_id": user["id"],
                       "session_fingerprint": fingerprint, "notification_context": context,
                       "token_fingerprint": hashlib.sha256(token["token"].encode()).hexdigest(),
                       "status": "pending", "attempts": 0, "next_attempt_at": self.now(),
                       "expires_at": alert["push_expires_at"]}
                try:
                    await self.db.stock_alert_deliveries.update_one({"_id": job_id}, {"$setOnInsert": job}, upsert=True)
                except Exception as error:
                    if getattr(error, "code", None) != 11000:
                        raise
        await self.db.stock_alerts.update_one({"_id": alert["id"]}, {"$set": {"audience_ready": True, "push_status": "queued"}})

    async def send_job(self, candidate):
        now = self.now()
        attempt_id = secrets.token_hex(12)
        claimed = await self.db.stock_alert_deliveries.find_one_and_update(
            {"_id": candidate["_id"], "status": {"$in": ["pending", "retry"]}, "next_attempt_at": {"$lte": now}},
            {"$set": {"status": "sending", "attempt_id": attempt_id, "attempt_started_at": now}, "$inc": {"attempts": 1}})
        if not claimed:
            return
        outcome = {"status": "skipped", "reason": "session_or_preference_changed"}
        try:
            if claimed["expires_at"] <= now:
                outcome = {"status": "expired", "reason": "alert_too_old_for_push"}
            else:
                alert = await self.db.stock_alerts.find_one({"_id": claimed["alert_id"]})
                user = await self.db.users.find_one({"id": claimed["user_id"], "stock_alert_push_enabled": True,
                                                     "status": {"$in": ["approved", "trial"]}})
                session = (user or {}).get("active_session_id", "")
                if active_membership(user, self.now()) and isinstance(session, str) and session and hashlib.sha256(session.encode()).hexdigest() == claimed["session_fingerprint"]:
                    devices = await self.active_tokens([user["id"]])
                    device = next((d for d in devices if d.get("session_fingerprint") == claimed["session_fingerprint"]
                                   and hashlib.sha256(d["token"].encode()).hexdigest() == claimed["token_fingerprint"]), None)
                    if device:
                        owner = await self.db.fcm_tokens.find_one({"_id": "token-owner:" + claimed["token_fingerprint"]})
                        if not owner or owner.get("owner_user_id") != user["id"] or owner.get("owner_session_fingerprint") != claimed["session_fingerprint"]:
                            device = None
                            outcome = {"status": "skipped", "reason": "device_ownership_changed"}
                    if device:
                        # Last auth/preference check immediately before the send.
                        current = await self.db.users.find_one({"id": user["id"], "active_session_id": session,
                                                               "stock_alert_push_enabled": True,
                                                               "status": {"$in": ["approved", "trial"]}})
                        if active_membership(current, self.now()):
                            data = {"type": "stock_alert", "category": "stocks", "alert_id": alert["id"],
                                    "symbol": alert["symbol"], "title": alert["title"], "body": alert["body"],
                                    "source": alert["source"], "source_timestamp": alert["source_timestamp"] or "",
                                    "received_at": alert["received_at"], "url": alert["url"],
                                    "expires_at": iso(claimed["expires_at"]),
                                    "notification_context": claimed["notification_context"]}
                            provider = self.provider
                            if provider is None:
                                from fcm_service import fcm_service
                                provider = fcm_service
                            remaining = (claimed["expires_at"] - self.now()).total_seconds()
                            if remaining <= 0:
                                outcome = {"status": "expired", "reason": "alert_too_old_for_push"}
                            else:
                                outcome = await provider.send_stock_alert(device["token"], data,
                                    ttl_seconds=max(1, int(remaining)))
            if outcome["status"] == "retryable":
                outcome = {"status": "retry", "reason": outcome.get("reason", "provider_not_ready"),
                           "next_attempt_at": self.now() + timedelta(seconds=30)}
            await self.db.stock_alert_deliveries.update_one({"_id": claimed["_id"], "attempt_id": attempt_id, "status": "sending"},
                                                           {"$set": {**outcome, "updated_at": self.now()}})
        except asyncio.CancelledError:
            # The recovery pass marks abandoned attempts unknown after restart.
            raise
        except Exception:
            logger.warning("Stock push attempt ended with an uncertain outcome")
            await self.db.stock_alert_deliveries.update_one({"_id": claimed["_id"], "attempt_id": attempt_id, "status": "sending"},
                {"$set": {"status": "unknown", "reason": "attempt_interrupted", "updated_at": self.now()}})

    async def tick(self):
        await self.db.stock_alert_deliveries.update_many(
            {"status": "sending", "attempt_started_at": {"$lt": self.now() - timedelta(minutes=2)}},
            {"$set": {"status": "unknown", "reason": "worker_interrupted"}})
        alerts = await self.db.stock_alerts.find({"audience_ready": False}).sort("created_at", 1).limit(20).to_list(20)
        for alert in alerts:
            await self.prepare_audience(alert)
        jobs = await self.db.stock_alert_deliveries.find({"status": {"$in": ["pending", "retry"]},
            "next_attempt_at": {"$lte": self.now()}}).sort("next_attempt_at", 1).limit(50).to_list(50)
        for job in jobs:
            await self.send_job(job)

    async def run(self):
        try:
            await self.initialize()
        except Exception:
            logger.warning("Stock alert indexes could not be initialized; worker will retry durable jobs")
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("Stock alert dispatch paused after a database/provider error")
            await asyncio.sleep(5)

    def router(self):
        router = APIRouter(prefix="/api/stocks", tags=["stocks"])

        @router.get("/notification-preferences")
        async def preferences(request: Request):
            member = await self.member(request)
            return {"stocks_enabled": member.get("stock_alert_push_enabled") is True}

        @router.put("/notification-preferences")
        async def update_preferences(request: Request, value: StockPreferences):
            member = await self.member(request)
            result = await self.db.users.update_one({"id": member["id"], "active_session_id": member["active_session_id"]},
                {"$set": {"stock_alert_push_enabled": value.stocks_enabled}})
            if not result.matched_count:
                raise HTTPException(401, "This session is no longer active.")
            return {"stocks_enabled": value.stocks_enabled}

        @router.get("/alerts")
        async def alerts(request: Request, limit: int = Query(50, ge=1, le=100), symbol: str = ""):
            await self.member(request)
            query = {}
            if symbol:
                symbol = symbol.upper()
                if not SYMBOL_RE.fullmatch(symbol):
                    raise HTTPException(422, "Use a valid stock symbol.")
                query["symbol"] = symbol
            found = await self.db.stock_alerts.find(query).sort("created_at", -1).limit(limit + 1).to_list(limit + 1)
            return {"alerts": [public_alert(value) for value in found[:limit]], "has_more": len(found) > limit}

        @router.get("/alerts/{alert_id}")
        async def detail(request: Request, alert_id: str):
            await self.member(request)
            if not re.fullmatch(r"[a-f0-9]{64}", alert_id):
                raise HTTPException(404, "Stock alert not found.")
            found = await self.db.stock_alerts.find_one({"_id": alert_id})
            if not found:
                raise HTTPException(404, "Stock alert not found.")
            return {"alert": public_alert(found)}

        @router.get("/alerts/{alert_id}/dispatch")
        async def dispatch_status(request: Request, alert_id: str):
            member = await self.member(request)
            if not member.get("is_admin"):
                raise HTTPException(403, "Administrator access required.")
            if not re.fullmatch(r"[a-f0-9]{64}", alert_id):
                raise HTTPException(404, "Stock alert not found.")
            alert = await self.db.stock_alerts.find_one({"_id": alert_id})
            if not alert:
                raise HTTPException(404, "Stock alert not found.")
            counts = {}
            async for job in self.db.stock_alert_deliveries.find({"alert_id": alert_id}):
                counts[job["status"]] = counts.get(job["status"], 0) + 1
            return {"alert_id": alert_id, "audience_ready": alert["audience_ready"], "counts": counts,
                    "accepted_is_delivery_receipt": False, "unknown_automatically_retried": False}

        return router
