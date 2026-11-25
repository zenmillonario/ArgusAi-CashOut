"""Quote provenance, cache/coalescing and no-fabricated-fill regression tests."""
import ast
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

from fastapi import APIRouter, HTTPException

from test_account_recovery import load_auth_slice
from test_social_endpoints import Collection

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from stock_quotes import FMPQuoteService, QuoteUnavailable, number, iso, utcnow

NOW = datetime(2026, 11, 25, 15, 0, 0, tzinfo=timezone.utc)


def provider_row(symbol="AAPL", **overrides):
    return {"symbol": symbol, "price": 194.25, "change": 1.25, "changePercentage": 0.6477,
            "timestamp": int(NOW.timestamp()), **overrides}


class QuoteAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clock = NOW
        self.tick = 100.0
        self.calls = []
        self.response = None
        self.failure = None
        async def fetch(symbol):
            self.calls.append(symbol)
            await asyncio.sleep(0)
            if self.failure:
                raise self.failure
            return deepcopy(self.response if self.response is not None else [provider_row(symbol)])
        self.service = FMPQuoteService(fetcher=fetch, now=lambda: self.clock, monotonic=lambda: self.tick)

    async def test_normalization_and_simultaneous_consumers_use_one_fetch(self):
        results = await asyncio.gather(*(self.service.get_quote(symbol) for symbol in ["aapl", " AAPL ", "$aapl"]*10))
        self.assertEqual(self.calls, ["AAPL"])
        self.assertTrue(all(r["symbol"] == "AAPL" for r in results))
        self.assertEqual(results[0]["source_timestamp"], "2026-11-25T15:00:00Z")
        self.assertFalse(results[0]["execution_eligible"])
        self.tick += 5.1
        await self.service.get_quote("AAPL")
        self.assertEqual(self.calls, ["AAPL", "AAPL"])

    async def test_timestamp_is_observation_not_receipt_and_percent_alias_is_correct(self):
        self.clock += timedelta(seconds=8)
        self.response = [provider_row(changesPercentage=99)]
        value = await self.service.get_quote("AAPL")
        self.assertNotEqual(value["source_timestamp"], value["received_at"])
        self.assertEqual(value["timestamp"], value["source_timestamp"])
        self.assertEqual(value["age_seconds"], 8)
        self.assertEqual(value["changePercentage"], 0.6477)
        self.assertEqual(value["changesPercentage"], 0.6477)
        self.assertEqual(value["market_status"], "unverified")
        self.assertEqual(value["delay_status"], "unverified")

    async def test_missing_invalid_future_and_stale_timestamps_are_never_invented(self):
        cases = [(None, "timestamp_missing", None), ("not-a-time", "timestamp_invalid", None),
                 ("2026-11-25T15:00:00", "timestamp_invalid", None), (0, "timestamp_invalid", None),
                 (int((NOW+timedelta(minutes=2)).timestamp()), "timestamp_future", "2026-11-25T15:02:00Z"),
                 (int((NOW-timedelta(hours=2)).timestamp()), "stale", "2026-11-25T13:00:00Z")]
        for timestamp, status, expected in cases:
            self.service.cache.clear()
            self.response = [provider_row(timestamp=timestamp, isMarketOpen=True, isDelayed=False)]
            value = await self.service.get_quote("AAPL")
            self.assertEqual(value["status"], status)
            self.assertEqual(value["source_timestamp"], expected)
            self.assertFalse(value["execution_eligible"])
            self.assertEqual(value["market_status"], "unverified")

    async def test_cache_recomputes_age_without_relabeling_receipt(self):
        self.clock += timedelta(seconds=29)
        first = await self.service.get_quote("AAPL")
        self.clock += timedelta(seconds=3)
        self.tick += 3
        cached = await self.service.get_quote("AAPL")
        self.assertEqual(first["status"], "recent")
        self.assertEqual(cached["status"], "stale")
        self.assertTrue(cached["cache_hit"])
        self.assertEqual(cached["received_at"], first["received_at"])
        self.assertEqual(len(self.calls), 1)

    async def test_invalid_price_symbol_and_provider_failure_cannot_make_a_quote(self):
        for row in (provider_row(price=0), provider_row(price=-2), provider_row(price=True),
                    provider_row(price=float("inf")), provider_row(price=float("nan")), provider_row("MSFT")):
            self.service.cache.clear()
            self.response = [row]
            with self.assertRaises(QuoteUnavailable):
                await self.service.get_quote("AAPL")
        before = len(self.calls)
        for symbol in ("", "AAPL?apikey=anything", "AAPL/../../", "AAPL,MSFT", "AAPL.."):
            with self.assertRaises(QuoteUnavailable):
                await self.service.get_quote(symbol)
        self.assertEqual(len(self.calls), before)
        self.service.cache.clear()
        self.failure = RuntimeError("Synthetic provider failure containing a private fixture")
        for _ in range(4):
            with self.assertRaises(QuoteUnavailable) as caught:
                await self.service.get_quote("AAPL")
            self.assertNotIn("private fixture", str(caught.exception.detail()))
        self.assertEqual(len(self.calls), before+1)

    async def test_cache_is_bounded_and_has_no_cross_symbol_price_reuse(self):
        self.service.max_entries = 2
        for symbol in ("AAPL", "MSFT", "NVDA"):
            value = await self.service.get_quote(symbol)
            self.assertEqual(value["symbol"], symbol)
        self.assertEqual(len(self.service.cache), 2)
        await self.service.get_quote("AAPL")
        self.assertEqual(self.calls, ["AAPL", "MSFT", "NVDA", "AAPL"])

    async def test_canceled_caller_does_not_cancel_shared_provider_request(self):
        started, release = asyncio.Event(), asyncio.Event()
        count = 0
        async def fetch(symbol):
            nonlocal count
            count += 1
            started.set()
            await release.wait()
            return [provider_row(symbol)]
        service = FMPQuoteService(fetcher=fetch, now=lambda: NOW)
        one = asyncio.create_task(service.get_quote("AAPL"))
        await started.wait()
        two = asyncio.create_task(service.get_quote("aapl"))
        await asyncio.sleep(0)
        one.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await one
        release.set()
        self.assertEqual((await two)["price"], 194.25)
        self.assertEqual(count, 1)

    async def test_missing_key_never_contacts_provider_and_changes_are_nullable(self):
        service = FMPQuoteService()
        with patch.dict("os.environ", {"FMP_API_KEY": ""}), patch("stock_quotes.httpx.AsyncClient", side_effect=AssertionError("Must not construct a client")):
            with self.assertRaises(QuoteUnavailable) as caught:
                await service.get_quote("AAPL")
            self.assertEqual(caught.exception.code, "provider_not_configured")
        self.response = [{"symbol": "AAPL", "price": 194.25}]
        value = await self.service.get_quote("AAPL")
        self.assertIsNone(value["change"])
        self.assertIsNone(value["changesPercentage"])


def load_quote_slice(service):
    namespace = load_auth_slice()
    namespace.update(api_router=APIRouter(prefix="/api"), stock_quote_service=service, QuoteUnavailable=QuoteUnavailable,
                     quote_number=number, quote_now=utcnow, quote_iso=iso)
    names = {"PaperTrade", "PaperTradeCreate", "Position", "PositionAction", "get_stock_price", "get_current_stock_price",
             "update_positions_pnl", "get_user_positions", "position_action", "close_position", "format_price_display", "format_pnl_display"}
    statements = []
    source = BACKEND / "server.py"
    for node in ast.parse(source.read_text()).body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            if hasattr(node, "decorator_list"):
                node.decorator_list = []
            statements.append(node)
    exec(compile(ast.Module(body=statements, type_ignores=[]), str(source), "exec"), namespace)
    return namespace


class Records(Collection):
    async def insert_one(self, doc):
        self.docs.append(deepcopy(doc))
        self.writes += 1
        return SimpleNamespace(inserted_id=doc.get("id"))


class QuoteMutationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.failure = None
        self.price = 75.0
        async def fetch(symbol):
            if self.failure:
                raise self.failure
            return [provider_row(symbol, price=self.price)]
        self.service = FMPQuoteService(fetcher=fetch, now=lambda: NOW)
        self.n = load_quote_slice(self.service)
        self.position = {"id": "position-1", "user_id": "member", "symbol": "AAPL", "quantity": 10,
                         "avg_price": 100.0, "entry_price": 100.0, "current_price": 105.0, "unrealized_pnl": 50.0,
                         "is_open": True, "stop_loss": 90.0, "take_profit": 110.0}
        self.db = SimpleNamespace(positions=Records([self.position]), paper_trades=Records(), users=Records())
        async def performance(user):
            return {}
        self.n.update(db=self.db, calculate_user_performance=performance)

    async def test_provider_failure_preserves_position_and_previous_numbers(self):
        self.failure = RuntimeError("Synthetic failure")
        result = await self.n["get_user_positions"]("member")
        row = self.db.positions.docs[0]
        self.assertTrue(row["is_open"])
        self.assertEqual(row["quantity"], 10)
        self.assertEqual(row["current_price"], 105.0)
        self.assertEqual(row["unrealized_pnl"], 50.0)
        self.assertEqual(row["valuation_status"], "unavailable")
        self.assertEqual(row["price_provenance"], "legacy_unverified")
        self.assertEqual(self.db.paper_trades.docs, [])
        self.assertEqual(result[0]["quote"]["status"], "unavailable")
        self.assertFalse(result[0]["execution_eligible"])

    async def test_nonfinite_derived_valuation_preserves_prior_position_numbers(self):
        self.price = 1e308
        result = await self.n["get_user_positions"]("member")
        self.assertEqual(result[0]["current_price"], 105.0)
        self.assertEqual(result[0]["unrealized_pnl"], 50.0)
        self.assertEqual(result[0]["valuation_status"], "unavailable")
        self.assertEqual(result[0]["quote"]["code"], "valuation_invalid")
        self.assertTrue(result[0]["is_open"])
        self.assertEqual(self.db.paper_trades.docs, [])

    async def test_observation_can_value_but_cannot_trigger_stop_or_take_profit(self):
        for price in (75.0, 125.0):
            self.price = price
            self.service.cache.clear()
            result = await self.n["get_user_positions"]("member")
            self.assertEqual(result[0]["current_price"], price)
            self.assertEqual(result[0]["price_provenance"], "provider_observation")
            self.assertEqual(result[0]["valuation_as_of"], "2026-11-25T15:00:00Z")
            self.assertEqual(result[0]["quote"]["status"], "recent")
            self.assertTrue(result[0]["is_open"])
            self.assertEqual(self.db.paper_trades.docs, [])

    async def test_explicit_quote_based_mutations_fail_before_any_trade_or_position_write(self):
        before = deepcopy(self.db.positions.docs)
        for operation in (self.n["close_position"]("position-1", "member"),
                          self.n["position_action"]("position-1", self.n["PositionAction"](action="SELL_ALL"), "member")):
            with self.assertRaises(HTTPException) as error:
                await operation
            self.assertEqual(error.exception.status_code, 503)
            self.assertEqual(error.exception.detail["code"], "quote_not_execution_eligible")
        self.assertEqual(self.db.positions.docs, before)
        self.assertEqual(self.db.positions.writes, 0)
        self.assertEqual(self.db.paper_trades.docs, [])

    async def test_unavailable_quote_cannot_close_and_manual_journal_remains_explicit(self):
        self.failure = QuoteUnavailable("provider_unavailable", "Synthetic unavailable", "AAPL")
        with self.assertRaises(HTTPException):
            await self.n["close_position"]("position-1", "member")
        self.assertEqual(self.db.paper_trades.docs, [])
        result = await self.n["position_action"]("position-1", self.n["PositionAction"](action="SELL_ALL", price=103.5), "member")
        self.assertEqual(result["price_source"], "manual_journal")
        self.assertFalse(result["price_verified"])
        self.assertEqual(self.db.paper_trades.docs[0]["price_source"], "manual_journal")
        self.assertFalse(self.db.positions.docs[0]["is_open"])

    async def test_stock_route_uses_shared_quote_and_does_not_call_profile_fallback(self):
        result = await self.n["get_stock_price"](" aapl ")
        self.assertEqual(result["symbol"], "AAPL")
        self.assertEqual(result["changesPercentage"], 0.6477)
        self.assertEqual(result["timestamp"], result["source_timestamp"])
        self.assertEqual(result["source"], "FMP /stable/quote")
        self.assertIn("formatted_price", result)
        source = (BACKEND / "server.py").read_text()
        self.assertNotIn("get_mock_stock_price", source)
        self.assertNotIn("financialmodelingprep.com/stable/profile", source)


if __name__ == "__main__":
    unittest.main()
