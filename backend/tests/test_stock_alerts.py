"""Stocks intake/dispatch contract tests; isolated Mongo and Firebase doubles.

No email, Zapier, WhatsApp, Firebase account, device, or production API is used.
"""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException, Request
import httpx

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from stock_alerts import StockAlertService, normalize_stock_alert, require_webhook_secret

NOW = datetime(2026, 11, 25, 12, 0, 0)
SECRET = "synthetic-stock-secret-for-isolated-tests-only"


def matches(doc, query):
    for key, expected in query.items():
        actual = doc.get(key)
        if isinstance(expected, dict):
            for op, value in expected.items():
                if op == "$in" and actual not in value:
                    return False
                if op == "$lte" and (actual is None or actual > value):
                    return False
                if op == "$lt" and (actual is None or actual >= value):
                    return False
        elif actual != expected:
            return False
    return True


class Cursor:
    def __init__(self, docs):
        self.docs = deepcopy(docs)

    def sort(self, key, direction):
        self.docs.sort(key=lambda d: d[key], reverse=direction < 0)
        return self

    def limit(self, limit):
        self.docs = self.docs[:limit]
        return self

    async def to_list(self, length):
        return self.docs[:length]

    def __aiter__(self):
        self.iterator = iter(self.docs)
        return self

    async def __anext__(self):
        try:
            return next(self.iterator)
        except StopIteration:
            raise StopAsyncIteration


class Collection:
    def __init__(self, docs=()):
        self.docs = deepcopy(list(docs))

    async def create_index(self, *args, **kwargs):
        return None

    def find(self, query=None):
        return Cursor([d for d in self.docs if matches(d, query or {})])

    async def find_one(self, query):
        return next((deepcopy(d) for d in self.docs if matches(d, query)), None)

    def apply(self, doc, update):
        doc.update(deepcopy(update.get("$set", {})))
        for key, increment in update.get("$inc", {}).items():
            doc[key] = doc.get(key, 0) + increment

    async def update_one(self, query, update, upsert=False):
        for doc in self.docs:
            if matches(doc, query):
                self.apply(doc, update)
                return SimpleNamespace(matched_count=1, upserted_id=None)
        if upsert:
            new = {**deepcopy(query), **deepcopy(update.get("$setOnInsert", {}))}
            self.apply(new, update)
            self.docs.append(new)
            return SimpleNamespace(matched_count=0, upserted_id=new.get("_id"))
        return SimpleNamespace(matched_count=0, upserted_id=None)

    async def update_many(self, query, update):
        for doc in self.docs:
            if matches(doc, query):
                self.apply(doc, update)

    async def find_one_and_update(self, query, update):
        for doc in self.docs:
            if matches(doc, query):
                previous = deepcopy(doc)
                self.apply(doc, update)
                return previous
        return None


class Provider:
    def __init__(self):
        self.calls = []
        self.outcome = {"status": "accepted"}

    async def send_stock_alert(self, token, data, ttl_seconds):
        self.calls.append({"token": token, "data": data, "ttl": ttl_seconds})
        await asyncio.sleep(0)
        return deepcopy(self.outcome)


def request(headers=None):
    return Request({"type": "http", "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]})


def payload(event="email-001"):
    return {"message_id": event, "subject": "AAPL price alert", "body": "Last = $194.25", "source_timestamp": "2026-11-25T12:00:00Z"}


class StockAlertTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.environment = patch.dict(os.environ, {"STOCK_ALERT_WEBHOOK_SECRET": SECRET})
        self.environment.start()
        self.clock = NOW
        self.db = SimpleNamespace(users=Collection([
            {"id": "member", "active_session_id": "synthetic-session", "status": "approved", "stock_alert_push_enabled": True},
            {"id": "quiet", "active_session_id": "quiet-session", "status": "approved"},
            {"id": "stale", "active_session_id": "new-session", "status": "approved", "stock_alert_push_enabled": True},
        ]), stock_alerts=Collection(), stock_alert_deliveries=Collection(), messages=Collection())
        self.devices = [
            {"user_id": "member", "token": "current-device", "session_fingerprint": hashlib.sha256(b"synthetic-session").hexdigest()},
            {"user_id": "quiet", "token": "quiet-device", "session_fingerprint": hashlib.sha256(b"quiet-session").hexdigest()},
            {"user_id": "stale", "token": "old-device", "session_fingerprint": hashlib.sha256(b"old-session").hexdigest()},
        ]
        async def owner(req, user_id):
            user = await self.db.users.find_one({"id": user_id})
            if not user or user["active_session_id"] != req.headers.get("x-session-id"):
                raise HTTPException(401, "Session changed")
            return user
        async def tokens(ids):
            result = []
            for u in self.db.users.docs:
                if u["id"] in ids and u.get("active_session_id"):
                    fingerprint = hashlib.sha256(u["active_session_id"].encode()).hexdigest()
                    result += [deepcopy(d) for d in self.devices if d["user_id"] == u["id"] and d.get("session_fingerprint") == fingerprint]
            return result
        self.db.fcm_tokens = Collection([{"_id": "token-owner:" + hashlib.sha256(d["token"].encode()).hexdigest(),
                                        "owner_user_id": d["user_id"], "owner_session_fingerprint": d["session_fingerprint"]}
                                       for d in self.devices])
        self.provider = Provider()
        self.community_messages = []

        async def broadcast(message):
            self.community_messages.append(json.loads(message))

        self.service = StockAlertService(self.db, owner, tokens, self.provider, now=lambda: self.clock,
                                         community_broadcast=broadcast)
        self.app = FastAPI()
        self.app.include_router(self.service.router())
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test")
        self.auth = {"X-User-ID": "member", "X-Session-ID": "synthetic-session"}
        self.webhook = request({"X-Stock-Alert-Secret": SECRET})

    async def asyncTearDown(self):
        await self.client.aclose()
        self.environment.stop()

    async def ingest(self, value=None):
        return await self.service.ingest(self.webhook, value or payload())

    async def test_intake_requires_secret_and_rejects_wrong_category(self):
        for req in (request(), request({"X-Stock-Alert-Secret": "wrong"})):
            with self.assertRaises(HTTPException) as error:
                await self.service.ingest(req, payload())
            self.assertEqual(error.exception.status_code, 401)
        with patch.dict(os.environ, {"STOCK_ALERT_WEBHOOK_SECRET": ""}):
            with self.assertRaises(HTTPException) as error:
                await self.ingest()
            self.assertEqual(error.exception.status_code, 503)
        with self.assertRaises(HTTPException):
            await self.ingest({**payload(), "category": "chat"})
        self.assertEqual(self.db.stock_alerts.docs, [])
        require_webhook_secret(request({"Authorization": "Bearer " + SECRET}))

    async def test_duplicate_email_is_one_alert_and_one_send(self):
        first = await self.ingest()
        second = await self.ingest()
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        await self.service.tick()
        await self.service.tick()
        await self.ingest()
        await self.service.tick()
        self.assertEqual(len(self.db.stock_alerts.docs), 1)
        self.assertEqual(len(self.provider.calls), 1)
        self.assertEqual(len(self.db.messages.docs), 1)
        self.assertEqual(len(self.community_messages), 1)
        self.assertEqual(self.db.messages.docs[0]["highlighted_tickers"], ["AAPL"])
        self.assertIn("194.25", self.db.messages.docs[0]["content"])
        self.assertFalse(self.db.messages.docs[0]["is_admin"])
        self.assertEqual(self.community_messages[0]["type"], "message")
        self.assertEqual(self.db.stock_alert_deliveries.docs[0]["status"], "accepted")
        with self.assertRaises(HTTPException) as error:
            await self.ingest({**payload(), "body": "Last = $199.99"})
        self.assertEqual(error.exception.status_code, 409)

    async def test_community_retry_is_independent_of_push_and_does_not_duplicate(self):
        await self.ingest()
        original = self.db.messages.update_one
        async def fail(*args, **kwargs):
            raise RuntimeError("synthetic chat storage failure")
        self.db.messages.update_one = fail
        await self.service.tick()
        self.assertEqual(len(self.provider.calls), 1)
        self.assertEqual(self.db.messages.docs, [])
        self.assertTrue(self.db.stock_alerts.docs[0]["community_pending"])
        self.db.messages.update_one = original
        await self.service.tick()
        await self.service.tick()
        self.assertEqual(len(self.db.messages.docs), 1)
        self.assertEqual(len(self.community_messages), 1)
        self.assertEqual(len(self.provider.calls), 1)
        self.assertFalse(self.db.stock_alerts.docs[0]["community_pending"])

    async def test_existing_alerts_are_not_automatically_backfilled(self):
        old = normalize_stock_alert(payload(), NOW)
        self.db.stock_alerts.docs.append(old)
        await self.service.tick()
        self.assertEqual(self.db.messages.docs, [])
        self.assertEqual(self.community_messages, [])

    async def test_repeated_prices_with_different_email_ids_remain_distinct(self):
        a = await self.ingest(payload("email-1"))
        b = await self.ingest(payload("email-2"))
        self.assertNotEqual(a["alert_id"], b["alert_id"])
        await self.service.tick()
        self.assertEqual(len(self.provider.calls), 2)

    async def test_safe_date_fallback_and_no_invented_tickers_or_times(self):
        value = payload(); value.pop("message_id")
        a = normalize_stock_alert(value, NOW)
        b = normalize_stock_alert({**value, "source_timestamp": "2026-11-25T11:59:00Z"}, NOW)
        self.assertNotEqual(a["id"], b["id"])
        for invalid in ({"body": "Last = $10", "subject": "Price alert", "message_id": "x"},
                        {"symbol": "AAPL", "body": "Last = $10"},
                        {**payload(), "source_timestamp": "2026-11-25T12:00:00"},
                        {**payload(), "source_timestamp": "2027-01-01T12:00:00Z"}):
            with self.assertRaises(HTTPException):
                normalize_stock_alert(invalid, NOW)

    async def test_grouped_prices_are_not_silently_truncated(self):
        for content in ("Last = $1,234.56", "Last = 1,234.56", "price: $1,234.56", "Last = .04",
                        "Last = $1,234.56.", "Trading at $1,234.56.", "Last = $1,234.56, then reverse"):
            alert = normalize_stock_alert({**payload(), "body": content}, NOW)
            self.assertEqual(alert["price"], "0.04" if content.endswith(".04") else "1234.56")
        for content in ("Last = $12,34", "Last = $1e3", "Last = $12.34.56"):
            self.assertIsNone(normalize_stock_alert({**payload(), "body": content}, NOW)["price"])
        self.assertEqual(normalize_stock_alert({**payload(), "price": 1234.56}, NOW)["price"], "1234.56")

    async def test_only_opted_in_current_session_receives_context_bound_stock_data(self):
        await self.ingest()
        await self.service.tick()
        self.assertEqual([c["token"] for c in self.provider.calls], ["current-device"])
        data = self.provider.calls[0]["data"]
        self.assertEqual(data["type"], "stock_alert")
        self.assertEqual(data["category"], "stocks")
        self.assertEqual(data["notification_context"], hashlib.sha256(b"member\0synthetic-session").hexdigest())
        self.assertNotIn("synthetic-session", json.dumps(data))
        self.assertEqual(self.provider.calls[0]["ttl"], 300)

    async def test_optout_or_replaced_session_between_queue_and_send_suppresses(self):
        await self.ingest()
        alert = self.db.stock_alerts.docs[0]
        await self.service.prepare_audience(alert)
        self.db.users.docs[0]["stock_alert_push_enabled"] = False
        await self.service.tick()
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(self.db.stock_alert_deliveries.docs[0]["status"], "skipped")
        self.db.users.docs[0]["stock_alert_push_enabled"] = True
        await self.ingest(payload("second"))
        await self.service.prepare_audience(self.db.stock_alerts.docs[1])
        self.db.users.docs[0]["active_session_id"] = "replacement"
        await self.service.tick()
        self.assertEqual(self.provider.calls, [])

    async def test_reused_browser_token_cannot_receive_for_previous_owner(self):
        await self.ingest()
        await self.service.prepare_audience(self.db.stock_alerts.docs[0])
        self.db.fcm_tokens.docs[0]["owner_user_id"] = "another-account"
        await self.service.tick()
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(self.db.stock_alert_deliveries.docs[0]["status"], "skipped")

    async def test_provider_unconfigured_retries_but_unknown_never_automatically_retries(self):
        self.provider.outcome = {"status": "retryable", "reason": "provider_not_configured"}
        await self.ingest()
        await self.service.tick()
        self.assertEqual(self.db.stock_alert_deliveries.docs[0]["status"], "retry")
        self.clock += timedelta(seconds=31)
        self.provider.outcome = {"status": "accepted"}
        await self.service.tick()
        self.assertEqual(len(self.provider.calls), 2)
        await self.ingest(payload("uncertain"))
        self.provider.outcome = {"status": "unknown", "reason": "timeout"}
        await self.service.tick()
        await self.service.tick()
        self.assertEqual(len(self.provider.calls), 3)
        self.assertEqual(self.db.stock_alert_deliveries.docs[-1]["status"], "unknown")

    async def test_crashed_send_is_unknown_and_parallel_workers_claim_once(self):
        await self.ingest()
        await self.service.prepare_audience(self.db.stock_alerts.docs[0])
        job = deepcopy(self.db.stock_alert_deliveries.docs[0])
        await asyncio.gather(self.service.send_job(job), self.service.send_job(job))
        self.assertEqual(len(self.provider.calls), 1)
        self.db.stock_alert_deliveries.docs[0].update(status="sending", attempt_started_at=NOW-timedelta(minutes=3))
        await self.service.tick()
        self.assertEqual(self.db.stock_alert_deliveries.docs[0]["status"], "unknown")
        self.assertEqual(len(self.provider.calls), 1)

    async def test_stale_alert_remains_in_feed_without_push(self):
        await self.ingest({**payload(), "source_timestamp": "2026-11-25T10:00:00Z"})
        await self.service.tick()
        self.assertEqual(self.provider.calls, [])
        response = await self.client.get("/api/stocks/alerts", headers=self.auth)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["alerts"]), 1)
        self.assertNotIn("content_digest", response.text)
        self.assertNotIn("email-001", response.text)

    async def test_expired_trial_cannot_read_or_receive_even_before_status_cleanup(self):
        self.db.users.docs[0].update(status="trial", trial_end_date=NOW-timedelta(seconds=1))
        self.assertEqual((await self.client.get("/api/stocks/alerts", headers=self.auth)).status_code, 403)
        await self.ingest()
        await self.service.tick()
        self.assertEqual(self.provider.calls, [])
        self.db.users.docs[0]["trial_end_date"] = "2026-11-25T12:00:20Z"
        self.assertEqual((await self.client.get("/api/stocks/alerts", headers=self.auth)).status_code, 200)
        await self.ingest(payload("trial-then-expires"))
        await self.service.prepare_audience(self.db.stock_alerts.docs[-1])
        self.clock += timedelta(seconds=21)
        await self.service.tick()
        self.assertEqual(self.provider.calls, [])

    async def test_alert_expiring_during_database_reads_is_not_sent(self):
        await self.ingest()
        await self.service.prepare_audience(self.db.stock_alerts.docs[0])
        original_find = self.db.stock_alerts.find_one
        async def delayed_find(query):
            self.clock += timedelta(seconds=301)
            return await original_find(query)
        self.db.stock_alerts.find_one = delayed_find
        await self.service.send_job(deepcopy(self.db.stock_alert_deliveries.docs[0]))
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(self.db.stock_alert_deliveries.docs[0]["status"], "expired")

    async def test_feed_detail_preferences_and_dispatch_are_session_protected(self):
        alert = await self.ingest()
        path = "/api/stocks/alerts/" + alert["alert_id"]
        for route in ("/api/stocks/alerts", path, "/api/stocks/notification-preferences"):
            self.assertEqual((await self.client.get(route)).status_code, 401)
            self.assertEqual((await self.client.get(route, headers=self.auth)).status_code, 200)
        prefs = await self.client.put("/api/stocks/notification-preferences", headers=self.auth, json={"stocks_enabled": False})
        self.assertEqual(prefs.json(), {"stocks_enabled": False})
        invalid = await self.client.put("/api/stocks/notification-preferences", headers=self.auth, json={"stocks_enabled": "true"})
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual((await self.client.get(path+"/dispatch", headers=self.auth)).status_code, 403)
        self.db.users.docs[0]["is_admin"] = True
        status = await self.client.get(path+"/dispatch", headers=self.auth)
        self.assertFalse(status.json()["accepted_is_delivery_receipt"])
        self.db.users.docs[0]["active_session_id"] = "new-session"
        self.assertEqual((await self.client.get(path, headers=self.auth)).status_code, 401)


class FCMTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.messages = []
        self.provider_error = None
        def send(message):
            self.messages.append(message)
            if self.provider_error:
                raise self.provider_error
            return "synthetic-provider-acceptance"
        def missing_app():
            raise ValueError("Not configured")
        sdk = SimpleNamespace(get_app=missing_app, credentials=SimpleNamespace(Certificate=lambda x:x), initialize_app=lambda x:None,
                              messaging=SimpleNamespace(Message=lambda **kw:kw, WebpushConfig=lambda **kw:kw, send=send))
        self.mock_modules = patch.dict(sys.modules, {"firebase_admin": sdk})
        self.mock_modules.start()
        spec = importlib.util.spec_from_file_location("isolated_fcm", BACKEND/"fcm_service.py")
        module = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {"FIREBASE_ADMIN_CREDENTIALS": ""}):
            spec.loader.exec_module(module)
            self.service = module.FCMService()
        self.data = {"type": "stock_alert", "category": "stocks", "alert_id": "a"*64,
                     "notification_context": "b"*64, "title": "AAPL stock alert", "body": "Synthetic fixture"}

    async def asyncTearDown(self):
        self.mock_modules.stop()

    async def test_no_credentials_does_not_claim_sent_and_all_other_push_is_suppressed(self):
        self.assertEqual((await self.service.send_stock_alert("device", self.data))["status"], "retryable")
        self.assertFalse(await self.service.send_notification("device", "Title", "Body", {"type": "admin_message"}))
        self.assertFalse(await self.service.send_chat_notification("device", "someone", "chat", "id"))
        self.assertEqual((await self.service.send_to_multiple(["device"], "Title", "Body"))["success_count"], 0)
        self.assertEqual(self.messages, [])

    async def test_fcm_gets_data_only_and_short_ttl(self):
        self.service.initialized = True
        result = await self.service.send_stock_alert("device", self.data, ttl_seconds=800)
        self.assertEqual(result["status"], "accepted")
        self.assertNotIn("notification", self.messages[0])
        self.assertEqual(self.messages[0]["webpush"]["headers"]["TTL"], "300")

    async def test_provider_error_does_not_turn_into_mock_success(self):
        self.service.initialized = True
        self.provider_error = RuntimeError("404 provider issue")
        result = await self.service.send_stock_alert("device", self.data)
        self.assertEqual(result["status"], "unknown")
        self.provider_error = type("UnregisteredError", (Exception,), {})("gone")
        self.assertEqual((await self.service.send_stock_alert("device", self.data))["status"], "rejected")


if __name__ == "__main__":
    unittest.main()
