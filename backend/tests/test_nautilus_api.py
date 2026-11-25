"""Isolated router tests: no Mongo server, local bots, or network is contacted."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
import httpx

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
import nautilus_api as api

NOW = 1_900_000_000.0
SECRET = "unit-test-publisher-secret-32-characters"
HEADERS = {"X-User-ID": "member-a", "X-Session-ID": "session-a"}


def packet(asset="BTC"):
    ticker = "KX" + asset + "15M-TEST"
    return {
        "mode": "PAPER_ONLY", "readonly": True, "version": "CLEAN-ROOM 0.0.10.7",
        "application": {"engine_version": "0.0.10.7_PAPER_ONLY", "dashboard_build": "0.0.8.4", "ui_protocol": 1},
        "server_now": NOW,
        "asset": {"symbol": asset, "normalization": 1},
        "run": {"run_id": "PAPER_TEST", "name": "PAPER_TEST", "updated": NOW, "fresh": True, "stopped": False, "review": False},
        "market": {"ticker": ticker, "time": NOW, "close_ts": NOW + 120, "btc": 60000, "fresh": True},
        "quote": {"ticker": ticker, "source": "KALSHI_PUBLIC_BOOK", "fresh": True, "valid_until": NOW + 3, "yes_bid": 0.18, "yes_ask": 0.20, "no_bid": 0.80, "no_ask": 0.82, "last_verified": {"ticker": ticker, "verified_at": NOW, "yes_bid": 0.18, "yes_ask": 0.20, "no_bid": 0.80, "no_ask": 0.82}},
        "candles": [{"time": NOW - 60, "open": 60000, "high": 60010, "low": 59990, "close": 60002}],
        "positions": [], "trades": [], "emas": [], "targets": [], "quotes": [],
    }


def _matches(document, query):
    for key, expected in query.items():
        value = document
        for part in key.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        if value != expected:
            return False
    return True


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    def sort(self, key, direction):
        self.documents.sort(key=lambda row: row[key], reverse=direction < 0)
        return self

    def limit(self, count):
        self.documents = self.documents[:count]
        return self

    async def to_list(self, length):
        return deepcopy(self.documents[:length])


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = deepcopy(documents or [])

    async def find_one(self, query):
        result = next((deepcopy(row) for row in self.documents if _matches(row, query)), None)
        # Let concurrent requests both observe a prior revision, exercising CAS.
        await asyncio.sleep(0)
        return result

    async def insert_one(self, document):
        if any(row.get("_id") == document.get("_id") for row in self.documents):
            error = RuntimeError("duplicate")
            error.code = 11000
            raise error
        self.documents.append(deepcopy(document))
        return SimpleNamespace(inserted_id=document.get("_id"))

    async def update_one(self, query, update, upsert=False):
        if any(_matches(row, query) for row in self.documents):
            return SimpleNamespace(matched_count=1)
        if upsert:
            self.documents.append({**deepcopy(query), **deepcopy(update.get("$setOnInsert", {}))})
        return SimpleNamespace(matched_count=0)

    async def replace_one(self, query, replacement):
        for index, document in enumerate(self.documents):
            if _matches(document, query):
                self.documents[index] = deepcopy(replacement)
                return SimpleNamespace(matched_count=1)
        return SimpleNamespace(matched_count=0)

    def find(self, query):
        return FakeCursor([deepcopy(row) for row in self.documents if _matches(row, query)])


class NautilusAPITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clock = patch.object(api.time, "time", return_value=NOW)
        self.clock.start()
        self.environment = patch.dict(api.os.environ, {"NAUTILUS_PUBLISHER_KEY": SECRET})
        self.environment.start()
        self.db = SimpleNamespace(
            users=FakeCollection([{"_id": "member-a", "id": "member-a", "username": "Alice", "status": "approved", "active_session_id": "session-a", "is_admin": False}]),
            nautilus_snapshots=FakeCollection(), nautilus_practice=FakeCollection(), nautilus_chat=FakeCollection(),
        )
        app = FastAPI()
        app.include_router(api.create_nautilus_router(self.db))
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.environment.stop()
        self.clock.stop()

    async def ingest(self, data=None, asset="BTC"):
        return await self.client.post("/api/nautilus/ingest/" + asset, json=data or packet(asset), headers={"X-Nautilus-Publisher-Key": SECRET})

    async def account(self):
        response = await self.client.get("/api/nautilus/practice", headers=HEADERS)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def operation(self, view, transaction="tx1", **fields):
        return {"attemptId": view["account"]["attemptId"], "revision": view["revision"], "transactionId": transaction, **fields}

    async def buy(self, view, transaction="buy-1", **fields):
        body = self.operation(view, transaction, asset="BTC", contractId="KXBTC15M-TEST", side="YES", budget=25)
        body.update(fields)
        return await self.client.post("/api/nautilus/practice/buy", headers=HEADERS, json=body)

    async def test_session_and_membership_are_required(self):
        self.assertEqual((await self.client.get("/api/nautilus/practice")).status_code, 401)
        self.assertEqual((await self.client.get("/api/nautilus/practice", headers={**HEADERS, "X-Session-ID": "wrong"})).status_code, 401)
        user = self.db.users.documents[0]
        user["status"] = "pending"
        self.assertEqual((await self.client.get("/api/nautilus/practice", headers=HEADERS)).status_code, 403)
        user.update(status="trial", trial_end_date=datetime.fromtimestamp(NOW - 1, timezone.utc))
        self.assertEqual((await self.client.get("/api/nautilus/practice", headers=HEADERS)).status_code, 403)
        user["trial_end_date"] = datetime.fromtimestamp(NOW + 60, timezone.utc).isoformat()
        self.assertEqual((await self.client.get("/api/nautilus/practice", headers=HEADERS)).status_code, 200)

    async def test_publisher_identity_allowlist_and_ordering(self):
        denied = await self.client.post("/api/nautilus/ingest/BTC", json=packet(), headers=HEADERS)
        self.assertEqual(denied.status_code, 401)
        data = packet()
        data.update(account={"email": "private@example.test"}, env={"key": "hidden"})
        data["run"].update(path="/private/work", active_session_id="must-not-leak", name="/home/private/run")
        data["market"]["api_key"] = "must-not-leak"
        self.assertEqual((await self.ingest(data)).status_code, 200)
        response = await self.client.get("/api/nautilus/bots/BTC", headers=HEADERS)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "live")
        self.assertNotIn("must-not-leak", response.text)
        self.assertNotIn("private", response.text)
        self.assertNotIn("account", response.json()["snapshot"])
        repeated = await self.ingest()
        self.assertEqual(repeated.status_code, 200)
        self.assertFalse(repeated.json()["accepted"])
        older = packet()
        older["server_now"] -= 1
        self.assertEqual((await self.ingest(older)).status_code, 409)
        future = packet()
        future["server_now"] += 20
        self.assertEqual((await self.ingest(future)).status_code, 422)
        invalid = packet()
        invalid["mode"] = "LIVE"
        self.assertEqual((await self.ingest(invalid)).status_code, 422)
        self.assertEqual((await self.ingest(packet("ETH"), "BTC")).status_code, 422)

    async def test_chat_is_asset_scoped_and_author_is_server_owned(self):
        response = await self.client.post("/api/nautilus/chat/BTC", headers=HEADERS, json={"text": "<b>Hello</b><script>doBadThing()</script>\x00 team"})
        self.assertEqual(response.status_code, 200)
        message = response.json()["message"]
        self.assertEqual(message["content"], "Hello team")
        self.assertEqual(message["author"], "Alice")
        self.assertFalse(message["isAdmin"])
        self.assertNotIn("authorId", message)
        btc = await self.client.get("/api/nautilus/chat/BTC", headers=HEADERS)
        eth = await self.client.get("/api/nautilus/chat/ETH", headers=HEADERS)
        self.assertEqual(len(btc.json()["messages"]), 1)
        self.assertEqual(eth.json()["messages"], [])
        spoof = await self.client.post("/api/nautilus/chat/BTC", headers=HEADERS, json={"text": "hello", "author": "Admin"})
        self.assertEqual(spoof.status_code, 422)
        long = await self.client.post("/api/nautilus/chat/BTC", headers=HEADERS, json={"text": "a" * 1001})
        self.assertEqual(long.status_code, 422)

    async def test_trade_uses_native_prices_and_duplicate_is_idempotent(self):
        await self.ingest()
        original = await self.account()
        self.assertEqual(original["account"]["cashUnits"], 100_000_000)
        tampered = await self.buy(original, ask=0.001)
        self.assertEqual(tampered.status_code, 422)
        response = await self.buy(original)
        self.assertEqual(response.status_code, 200)
        bought = response.json()
        self.assertEqual(bought["account"]["cashUnits"], 75_000_000)
        self.assertEqual(bought["account"]["positions"][0]["quantity"], 125)
        self.assertEqual(bought["feePolicy"], "fees-excluded")
        duplicate = await self.buy(original)
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(duplicate.json()["revision"], 1)
        self.assertEqual(duplicate.json()["account"]["cashUnits"], 75_000_000)
        self.assertEqual((await self.buy(original, budget=50)).status_code, 409)
        close = self.operation(bought, "close-1", positionId=bought["account"]["positions"][0]["id"])
        closed = await self.client.post("/api/nautilus/practice/close", headers=HEADERS, json=close)
        self.assertEqual(closed.status_code, 200)
        self.assertEqual(closed.json()["account"]["cashUnits"], 97_500_000)
        self.assertEqual(closed.json()["account"]["realizedPnlUnits"], -2_500_000)
        self.assertEqual(closed.json()["account"]["positions"], [])

    async def test_two_concurrent_requests_do_not_double_spend(self):
        await self.ingest()
        account = await self.account()
        first, second = await asyncio.gather(self.buy(account, "one", budget=75), self.buy(account, "two", budget=75))
        self.assertEqual(sorted([first.status_code, second.status_code]), [200, 409])
        final = await self.account()
        self.assertEqual(final["account"]["cashUnits"], 25_000_000)
        self.assertEqual(final["revision"], 1)
        self.assertEqual(len(final["account"]["transactions"]), 1)

    async def test_concurrent_same_transaction_returns_single_receipt(self):
        await self.ingest()
        account = await self.account()
        first, second = await asyncio.gather(self.buy(account), self.buy(account))
        self.assertEqual([first.status_code, second.status_code], [200, 200])
        self.assertEqual((await self.account())["account"]["cashUnits"], 75_000_000)

    async def test_reset_is_idempotent_and_old_attempt_cannot_buy_or_close(self):
        await self.ingest()
        initial = await self.account()
        bought = (await self.buy(initial)).json()
        old_close = self.operation(bought, "old-close", positionId=bought["account"]["positions"][0]["id"])
        reset_body = self.operation(bought, "reset-1")
        reset = await self.client.post("/api/nautilus/practice/reset", headers=HEADERS, json=reset_body)
        self.assertEqual(reset.status_code, 200)
        restarted = reset.json()
        self.assertEqual(restarted["account"]["cashUnits"], 100_000_000)
        self.assertEqual(restarted["revision"], 2)
        self.assertNotEqual(restarted["account"]["attemptId"], bought["account"]["attemptId"])
        self.assertEqual((await self.buy(bought, "late-buy")).status_code, 409)
        self.assertEqual((await self.client.post("/api/nautilus/practice/close", headers=HEADERS, json=old_close)).status_code, 409)
        repeated = await self.client.post("/api/nautilus/practice/reset", headers=HEADERS, json=reset_body)
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.json()["revision"], 2)
        self.assertEqual(repeated.json()["account"]["resetCount"], 1)

    async def test_stale_stopped_review_expired_and_wrong_contract_reject_fills(self):
        await self.ingest()
        account = await self.account()
        stored = self.db.nautilus_snapshots.documents[0]
        original = deepcopy(stored)
        for mutator in (
            lambda d: d.update(receivedAt=NOW - 16),
            lambda d: d["snapshot"]["run"].update(stopped=True),
            lambda d: d["snapshot"]["run"].update(review=True),
            lambda d: d["snapshot"]["market"].update(time=NOW - 6),
            lambda d: d["snapshot"]["market"].update(close_ts=NOW),
            lambda d: d["snapshot"]["quote"].update(valid_until=NOW - 1),
            lambda d: d["snapshot"]["quote"]["last_verified"].update(verified_at=NOW - 4),
            lambda d: d["snapshot"]["quote"].update(yes_ask=None),
        ):
            stored.clear()
            stored.update(deepcopy(original))
            mutator(stored)
            self.assertEqual((await self.buy(account)).status_code, 409)
        stored.clear()
        stored.update(original)
        self.assertEqual((await self.buy(account, contractId="KXETH15M-TEST")).status_code, 409)
        self.assertEqual((await self.account())["account"]["cashUnits"], 100_000_000)

    async def test_request_limits_and_nonfinite_numbers(self):
        headers = {"X-Nautilus-Publisher-Key": SECRET, "Content-Type": "application/json"}
        for raw in ('{"mode":NaN}', '{"mode":1,"mode":2}'):
            response = await self.client.post("/api/nautilus/ingest/BTC", headers=headers, content=raw)
            self.assertEqual(response.status_code, 422)
        oversized = await self.client.post("/api/nautilus/chat/BTC", headers=HEADERS, content=b"x" * (api.MAX_REQUEST_BYTES + 1))
        self.assertEqual(oversized.status_code, 413)
        data = packet()
        data["candles"][0]["high"] = 2
        self.assertEqual((await self.ingest(data)).status_code, 422)


class PublisherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        location = BACKEND.parent / "scripts" / "publish_nautilus.py"
        spec = importlib.util.spec_from_file_location("publisher_under_test", location)
        cls.publisher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.publisher)

    def test_only_https_or_explicit_local_development(self):
        normalize = self.publisher.backend_base
        self.assertEqual(normalize("https://example.test/api/"), "https://example.test")
        for value in ("http://example.test", "https://name:secret@example.test", "https://example.test?key=value", "file:///tmp/site", "https://example.test/#x"):
            with self.assertRaises(ValueError):
                normalize(value)
        self.assertEqual(normalize("http://127.0.0.1:8000", True), "http://127.0.0.1:8000")
        with self.assertRaises(ValueError):
            normalize("http://example.test", True)

    def test_fixed_five_source_ports_and_redirect_denial(self):
        self.assertEqual(self.publisher.ASSET_PORTS, {"BTC": 8787, "ETH": 8788, "SOL": 8789, "XRP": 8790, "DOGE": 8791})
        with self.assertRaises(self.publisher.HTTPError):
            self.publisher.NoRedirect().redirect_request(SimpleNamespace(full_url="https://example.test"), None, 302, "redirect", {}, "https://other.test")

    def publish_with_acknowledgement(self, acknowledgement, status=200):
        class Response:
            def __init__(self, body, status=200):
                self.body = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.status = status
            def read(self, limit):
                return self.body[:limit]
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
        local_requests, remote_requests = [], []
        def local_open(request, timeout):
            local_requests.append(request)
            return Response(packet())
        def remote_open(request, timeout):
            remote_requests.append(request)
            return Response(acknowledgement, status)
        with patch.object(self.publisher, "build_opener", side_effect=[
                SimpleNamespace(open=local_open), SimpleNamespace(open=remote_open)]):
            result = self.publisher.publish_one("BTC", "https://example.test", SECRET)
        self.assertEqual(len(local_requests), 1)
        self.assertEqual(len(remote_requests), 1)
        self.assertNotIn(SECRET, str(local_requests[0].headers))
        self.assertEqual(remote_requests[0].get_header("X-nautilus-publisher-key"), SECRET)
        return result

    def test_publisher_requires_an_explicit_matching_acceptance(self):
        result = self.publish_with_acknowledgement({"accepted": True, "asset": "BTC", "receivedAt": "2026-11-25T20:00:00Z"})
        self.assertEqual(result, (True, "snapshot accepted"))

    def test_unchanged_source_is_not_reported_as_newly_published(self):
        result = self.publish_with_acknowledgement({"accepted": False, "asset": "BTC", "receivedAt": "2026-11-25T20:00:00Z"})
        self.assertEqual(result, (False, "source unchanged; no new snapshot accepted"))

    def test_malformed_wrong_asset_and_missing_receipt_acknowledgements_fail(self):
        for response in (b"not json", [], {},
                         {"accepted": True, "asset": "ETH", "receivedAt": "2026-11-25T20:00:00Z"},
                         {"accepted": 1, "asset": "BTC", "receivedAt": "2026-11-25T20:00:00Z"},
                         {"accepted": True, "asset": "BTC"},
                         {"accepted": True, "asset": "BTC", "receivedAt": "not a date"},
                         {"accepted": True, "asset": "BTC", "receivedAt": "2026-11-25T20:00:00"}):
            with self.subTest(response=response):
                self.assertEqual(self.publish_with_acknowledgement(response),
                                 (False, "invalid or oversized backend acknowledgement"))

    def test_unsuccessful_http_status_cannot_report_acceptance(self):
        result = self.publish_with_acknowledgement({"accepted": True, "asset": "BTC", "receivedAt": "2026-11-25T20:00:00Z"}, status=503)
        self.assertEqual(result, (False, "backend did not accept the packet"))


if __name__ == "__main__":
    unittest.main()
