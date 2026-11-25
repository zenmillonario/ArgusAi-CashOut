"""Official-result and atomic virtual settlement tests; no live network/DB."""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

from fastapi import FastAPI
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kalshi_settlements as settlement
import nautilus_api
from nautilus_practice import buy_contracts, create_account, reset_account

NOW = datetime(2026, 11, 25, 18, 5, tzinfo=timezone.utc)
TICKER = "KXBTC15M-26NOV251300-00"
HEADERS = {"X-User-ID": "member-a", "X-Session-ID": "session-a"}


def market(ticker=TICKER, result="yes", **changes):
    row = {"ticker": ticker, "market_type": "binary", "status": "finalized", "result": result,
           "notional_value_dollars": "1.0000", "settlement_bounds_type": "default",
           "settlement_value_dollars": "1.0000" if result == "yes" else "0.0000",
           "close_time": "2026-11-25T18:00:00Z", "settlement_ts": "2026-11-25T18:00:30Z",
           "is_provisional": False}
    row.update(changes)
    return {"market": row}


def ledger(user_id="member-a", side="YES", close_time="2026-11-25T18:00:00Z"):
    account = create_account({"userId": user_id, "attemptId": "attempt-a"})
    account = buy_contracts(account, {"asset": "BTC", "contractId": TICKER, "side": side,
        "budget": 25, "ask": .20, "fee": 0, "transactionId": "buy-a",
        "timestamp": "2026-11-25T17:52:00Z", "contractCloseTime": close_time})
    return {"_id": user_id, "revision": 1, "account": account,
            "operations": [{"id": "buy-a", "requestHash": "preserved"}]}


def value_at(row, path):
    value = row
    for key in path.split("."):
        if isinstance(value, dict):
            value = value.get(key)
        elif isinstance(value, list) and key.isdigit() and int(key) < len(value):
            value = value[int(key)]
        else:
            return None
    return value


def matches(row, query):
    for key, expected in query.items():
        value = value_at(row, key)
        if isinstance(expected, dict):
            if "$exists" in expected and (value is not None) != expected["$exists"]:
                return False
            if "$gt" in expected and not (value is not None and value > expected["$gt"]):
                return False
        elif value != expected:
            return False
    return True


class Cursor:
    def __init__(self, rows):
        self.rows = deepcopy(rows)
    def sort(self, key, direction):
        self.rows.sort(key=lambda row: value_at(row, key), reverse=direction < 0)
        return self
    def limit(self, number):
        self.rows = self.rows[:number]
        return self
    async def to_list(self, length):
        return deepcopy(self.rows[:length])


class Collection:
    def __init__(self, rows):
        self.rows = deepcopy(rows)
        self.writes = 0
    async def find_one(self, query):
        row = next((deepcopy(row) for row in self.rows if matches(row, query)), None)
        await asyncio.sleep(0)
        return row
    async def replace_one(self, query, replacement):
        for index, row in enumerate(self.rows):
            if matches(row, query):
                self.rows[index] = deepcopy(replacement)
                self.writes += 1
                return SimpleNamespace(matched_count=1)
        return SimpleNamespace(matched_count=0)
    def find(self, query):
        return Cursor([row for row in self.rows if matches(row, query)])


class MarketVerificationTests(unittest.TestCase):
    def test_exact_final_yes_and_no_are_verified_with_evidence(self):
        for side in ("yes", "no"):
            found = settlement.verify_market(market(result=side), "BTC", TICKER, NOW)
            self.assertEqual(found.winning_side, side.upper())
            self.assertEqual(found.evidence()["contractId"], TICKER)
            self.assertEqual(found.evidence()["marketStatus"], "finalized")

    def test_unsupported_uncertain_and_contradictory_results_stay_reserved(self):
        invalid = [
            {"status": state} for state in ("active", "closed", "determined", "disputed", "amended", "settled")
        ] + [
            {"ticker": "KXETH15M-26NOV251300-00"}, {"result": ""}, {"result": "scalar"},
            {"result": "YES"}, {"market_type": "scalar"}, {"settlement_value_dollars": "0.0000"},
            {"settlement_value_dollars": "0.5000"}, {"notional_value_dollars": "2.0000"},
            {"notional_value_dollars": True}, {"notional_value_dollars": "NaN"},
            {"settlement_value_dollars": None}, {"settlement_bounds_type": "floor"},
            {"settlement_bounds_type": None}, {"is_provisional": True}, {"is_provisional": "false"},
            {"settlement_ts": None}, {"settlement_ts": "2026-11-25T18:06:00Z"},
            {"settlement_ts": "2026-11-25T17:59:00Z"}, {"settlement_ts": "2026-11-25T18:00:30"},
            {"close_time": "invalid"},
        ]
        for change in invalid:
            with self.subTest(change=change):
                self.assertIsNone(settlement.verify_market(market(**change), "BTC", TICKER, NOW))
        for bad in (None, [], {}, {"market": []}):
            self.assertIsNone(settlement.verify_market(bad, "BTC", TICKER, NOW))
        self.assertIsNone(settlement.verify_market(market(), "ETH", TICKER, NOW))

    def test_only_five_exact_asset_prefixes_and_safe_tickers_are_allowed(self):
        for asset in settlement.ASSETS:
            self.assertTrue(settlement.valid_ticker(asset, "KX" + asset + "15M-26NOV251300-00"))
        for ticker in ("https://other.test", TICKER + "/../", TICKER + "?x=1", TICKER.lower(), "KXBTC-TEST"):
            self.assertFalse(settlement.valid_ticker("BTC", ticker))


class ResolverTests(unittest.IsolatedAsyncioTestCase):
    async def test_coalescing_cancellation_cache_and_negative_expiry(self):
        calls, gate = [], asyncio.Event()
        clock = [0.0]
        final = [False]
        async def fetch(ticker):
            calls.append(ticker)
            await gate.wait()
            return market(ticker, status="finalized" if final[0] else "closed")
        resolver = settlement.KalshiSettlementResolver(fetch, now=lambda: NOW, monotonic=lambda: clock[0])
        first = asyncio.create_task(resolver.get_outcome("BTC", TICKER))
        second = asyncio.create_task(resolver.get_outcome("BTC", TICKER))
        await asyncio.sleep(0)
        first.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await first
        gate.set()
        self.assertIsNone(await second)
        self.assertEqual(len(calls), 1)
        self.assertIsNone(await resolver.get_outcome("BTC", TICKER))
        self.assertEqual(len(calls), 1)
        clock[0] = settlement.PENDING_CACHE_SECONDS + 1
        final[0] = True
        self.assertEqual((await resolver.get_outcome("BTC", TICKER)).winning_side, "YES")
        self.assertEqual(len(calls), 2)
        await resolver.get_outcome("BTC", TICKER)
        self.assertEqual(len(calls), 2)

    async def test_cache_and_inflight_concurrency_are_bounded(self):
        gate = asyncio.Event()
        active = [0, 0]
        async def fetch(ticker):
            active[0] += 1
            active[1] = max(active)
            await gate.wait()
            active[0] -= 1
            return market(ticker)
        resolver = settlement.KalshiSettlementResolver(fetch, now=lambda: NOW, max_cache_entries=2)
        tasks = [asyncio.create_task(resolver.get_outcome("BTC", TICKER + "-" + str(i))) for i in range(25)]
        for _ in range(5):
            await asyncio.sleep(0)
        self.assertLessEqual(len(resolver.inflight), settlement.MAX_INFLIGHT)
        self.assertLessEqual(active[1], settlement.MAX_CONCURRENT)
        gate.set()
        results = await asyncio.gather(*tasks)
        self.assertEqual(sum(value is not None for value in results), settlement.MAX_INFLIGHT)
        self.assertLessEqual(len(resolver.cache), 2)

    async def test_timeout_and_provider_failure_do_not_create_outcomes(self):
        async def slow(_):
            await asyncio.Event().wait()
        resolver = settlement.KalshiSettlementResolver(slow, now=lambda: NOW)
        with patch.object(settlement, "LOOKUP_TIMEOUT_SECONDS", .01):
            self.assertIsNone(await resolver.get_outcome("BTC", TICKER))
        async def fail(_):
            raise RuntimeError("private provider detail")
        other = settlement.KalshiSettlementResolver(fail, now=lambda: NOW)
        self.assertIsNone(await other.get_outcome("BTC", TICKER))

    async def test_network_adapter_uses_public_fixed_origin_and_404_historical_fallback(self):
        requests = []
        def handler(request):
            requests.append(request)
            if "/historical/" not in request.url.path:
                return httpx.Response(404)
            return httpx.Response(200, json=market())
        original_client = httpx.AsyncClient
        def client_factory(**kwargs):
            return original_client(transport=httpx.MockTransport(handler), **kwargs)
        with patch.object(settlement.httpx, "AsyncClient", client_factory):
            resolver = settlement.KalshiSettlementResolver(now=lambda: NOW)
            self.assertIsNotNone(await resolver.get_outcome("BTC", TICKER))
        self.assertEqual(len(requests), 2)
        self.assertTrue(all(request.method == "GET" and request.url.host == "external-api.kalshi.com" for request in requests))
        self.assertTrue(all("authorization" not in request.headers for request in requests))
        self.assertIn("/historical/markets/", requests[1].url.path)

    async def test_redirect_oversize_duplicate_and_nonfinite_responses_fail_closed(self):
        cases = [(302, b"", {"location": "https://other.test/"}),
                 (200, b" " * (settlement.MAX_RESPONSE_BYTES + 1), {}),
                 (200, b'{"market":{},"market":{}}', {}),
                 (200, b'{"market":{"notional_value_dollars":NaN}}', {})]
        original_client = httpx.AsyncClient
        for status, body, headers in cases:
            calls = []
            def handler(request):
                calls.append(request)
                return httpx.Response(status, content=body, headers=headers)
            def factory(**kwargs):
                return original_client(transport=httpx.MockTransport(handler), **kwargs)
            with self.subTest(status=status, size=len(body)), patch.object(settlement.httpx, "AsyncClient", factory):
                resolver = settlement.KalshiSettlementResolver(now=lambda: NOW)
                self.assertIsNone(await resolver.get_outcome("BTC", TICKER))
                self.assertEqual(len(calls), 1)


class SettlementLedgerTests(unittest.IsolatedAsyncioTestCase):
    def service(self, documents=None, fetcher=None):
        db = SimpleNamespace(nautilus_practice=Collection(documents or [ledger()]),
            users=Collection([{"_id": "member-a", "id": "member-a", "status": "approved", "active_session_id": "session-a"}]))
        async def fetch(ticker):
            return market(ticker)
        resolver = settlement.KalshiSettlementResolver(fetcher or fetch, now=lambda: NOW)
        return db, settlement.NautilusSettlementService(db, resolver, now=lambda: NOW)

    async def test_winning_and_losing_settlement_releases_cash_once_with_audit(self):
        for side, cash, pnl in (("YES", 200_000_000, 100_000_000), ("NO", 75_000_000, -25_000_000)):
            db, service = self.service([ledger(side=side)])
            result = await service.reconcile("member-a")
            account = result["account"]
            self.assertEqual(account["cashUnits"], cash)
            self.assertEqual(account["realizedPnlUnits"], pnl)
            self.assertEqual(account["positions"], [])
            self.assertEqual(result["revision"], 2)
            self.assertEqual(result["operations"], [{"id": "buy-a", "requestHash": "preserved"}])
            tx = account["transactions"][-1]
            self.assertEqual(tx["type"], "SETTLE")
            self.assertEqual(tx["officialWinningSide"], "YES")
            self.assertEqual(tx["settlementEvidence"]["marketStatus"], "finalized")
            self.assertEqual(await service.reconcile("member-a"), result)
            self.assertEqual(db.nautilus_practice.writes, 1)

    async def test_two_independent_workers_cannot_double_credit(self):
        db, first = self.service()
        second = settlement.NautilusSettlementService(db, first.resolver, now=lambda: NOW)
        await asyncio.gather(first.reconcile("member-a"), second.reconcile("member-a"))
        result = db.nautilus_practice.rows[0]
        self.assertEqual(result["account"]["cashUnits"], 200_000_000)
        self.assertEqual(len(result["account"]["transactions"]), 2)
        self.assertEqual(db.nautilus_practice.writes, 1)

    async def test_reset_wins_race_and_old_attempt_never_reappears(self):
        started, gate = asyncio.Event(), asyncio.Event()
        async def fetch(ticker):
            started.set()
            await gate.wait()
            return market(ticker)
        db, service = self.service(fetcher=fetch)
        pending = asyncio.create_task(service.reconcile("member-a"))
        await started.wait()
        original = db.nautilus_practice.rows[0]
        original["account"] = reset_account(original["account"], {"attemptId": "attempt-b"})
        original["revision"] += 1
        gate.set()
        result = await pending
        self.assertEqual(result["account"]["attemptId"], "attempt-b")
        self.assertEqual(result["account"]["cashUnits"], 100_000_000)
        self.assertEqual(result["account"]["transactions"], [])
        self.assertEqual(db.nautilus_practice.writes, 0)

    async def test_pending_future_malformed_and_postclose_entries_stay_unchanged(self):
        calls = []
        async def fetch(ticker):
            calls.append(ticker)
            return market(ticker, status="determined")
        doc = ledger()
        db, service = self.service([doc], fetch)
        self.assertEqual(await service.reconcile("member-a"), doc)
        self.assertEqual(db.nautilus_practice.writes, 0)
        future = ledger(close_time="2026-11-25T18:10:00Z")
        db, service = self.service([future], fetch)
        await service.reconcile("member-a")
        self.assertEqual(len(calls), 1)
        late = ledger()
        late["account"]["positions"][0]["openedAt"] = "2026-11-25T18:01:00Z"
        db, service = self.service([late])
        self.assertEqual(await service.reconcile("member-a"), late)
        broken = ledger()
        broken["account"]["cashUnits"] = 0
        db, service = self.service([broken])
        self.assertEqual(await service.reconcile("member-a"), broken)

    async def test_legacy_position_without_close_time_is_resolved(self):
        doc = ledger()
        del doc["account"]["positions"][0]["contractCloseTime"]
        db, service = self.service([doc])
        result = await service.reconcile("member-a")
        self.assertEqual(result["account"]["cashUnits"], 200_000_000)

    async def test_worker_pages_accounts_without_starvation(self):
        docs = [ledger("user-" + str(i).zfill(2)) for i in range(settlement.WORKER_BATCH_SIZE + 2)]
        db, service = self.service(docs)
        await service.tick()
        self.assertEqual(db.nautilus_practice.writes, settlement.WORKER_BATCH_SIZE)
        await service.tick()
        self.assertEqual(db.nautilus_practice.writes, len(docs))
        await service.tick()
        self.assertIsNone(service.worker_cursor)

    async def test_authenticated_refresh_reconciles_same_response_shape(self):
        db, service = self.service()
        app = FastAPI()
        app.include_router(nautilus_api.create_nautilus_router(db, settlement_service=service))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            denied = await client.get("/api/nautilus/practice")
            self.assertEqual(denied.status_code, 401)
            self.assertEqual(db.nautilus_practice.writes, 0)
            result = await client.get("/api/nautilus/practice", headers=HEADERS)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(set(result.json()), {"account", "revision", "feePolicy"})
            self.assertEqual(result.json()["account"]["cashUnits"], 200_000_000)


if __name__ == "__main__":
    unittest.main()
