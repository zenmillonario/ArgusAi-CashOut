"""Read-only official Kalshi results for the virtual $100 practice ledger.

This module has no authentication keys or order endpoints. A closed market is
not a settled market: only a finalized, ordinary $1 binary contract with a
matching official payout is eligible. Unknown outcomes leave funds reserved.
"""
from __future__ import annotations

import asyncio
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import logging
import re
import time

import httpx

try:
    from .nautilus_practice import PracticeError, settle_position, validate_account
except ImportError:
    from nautilus_practice import PracticeError, settle_position, validate_account

logger = logging.getLogger(__name__)
API_ORIGIN = "https://external-api.kalshi.com/trade-api/v2"
SOURCE = "Kalshi public market result"
ASSETS = ("BTC", "ETH", "SOL", "XRP", "DOGE")
MAX_RESPONSE_BYTES = 256 * 1024
MAX_CACHE_ENTRIES = 256
MAX_INFLIGHT = 16
MAX_CONCURRENT = 4
PENDING_CACHE_SECONDS = 30.0
FINAL_CACHE_SECONDS = 3600.0
LOOKUP_TIMEOUT_SECONDS = 6.0
MAX_ACCOUNT_LOOKUPS = 8
MAX_RECONCILIATIONS = 16
WORKER_BATCH_SIZE = 20
WORKER_INTERVAL_SECONDS = 15.0


def utcnow():
    return datetime.now(timezone.utc)


def iso(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parsed_time(value):
    if not isinstance(value, str) or len(value) > 80:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None


def valid_ticker(asset, ticker):
    return (asset in ASSETS and isinstance(ticker, str) and len(ticker) <= 128
            and re.fullmatch(r"KX" + asset + r"15M-[A-Z0-9]+(?:-[A-Z0-9]+)*", ticker) is not None)


def dollars(value):
    # The provider contract specifies decimal strings. Do not coerce booleans,
    # missing values, NaN, infinity, or a different numeric protocol to money.
    if not isinstance(value, str) or len(value) > 24 or not re.fullmatch(r"\d+(?:\.\d{1,6})?", value):
        return None
    try:
        result = Decimal(value)
        return result if result.is_finite() else None
    except InvalidOperation:
        return None


@dataclass(frozen=True)
class VerifiedSettlement:
    asset: str
    ticker: str
    winning_side: str
    close_at: datetime
    settled_at: datetime
    verified_at: datetime

    def evidence(self):
        return {"source": SOURCE, "marketStatus": "finalized", "contractId": self.ticker,
                "winningSide": self.winning_side, "closeTime": iso(self.close_at),
                "settledAt": iso(self.settled_at), "verifiedAt": iso(self.verified_at),
                "notionalDollars": "1.0000",
                "yesPayoutDollars": "1.0000" if self.winning_side == "YES" else "0.0000"}


def verify_market(payload, asset, ticker, now=None):
    """Return explicit final evidence; never infer a result from price/strike."""
    now = now or utcnow()
    if not valid_ticker(asset, ticker) or not isinstance(payload, dict):
        return None
    market = payload.get("market")
    if not isinstance(market, dict) or market.get("ticker") != ticker:
        return None
    if (market.get("market_type") != "binary" or market.get("status") != "finalized"
            or market.get("result") not in ("yes", "no")
            or market.get("settlement_bounds_type") != "default"
            or ("is_provisional" in market and market["is_provisional"] is not False)
            or dollars(market.get("notional_value_dollars")) != Decimal(1)):
        return None
    expected = Decimal(1) if market["result"] == "yes" else Decimal(0)
    if dollars(market.get("settlement_value_dollars")) != expected:
        return None
    close_at, settled_at = parsed_time(market.get("close_time")), parsed_time(market.get("settlement_ts"))
    if close_at is None or settled_at is None or not close_at <= settled_at <= now:
        return None
    return VerifiedSettlement(asset, ticker, market["result"].upper(), close_at, settled_at, now)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate result field")
        result[key] = value
    return result


class KalshiSettlementResolver:
    """Bounded, coalesced read-only lookups shared by every member in a process."""
    def __init__(self, fetcher=None, now=utcnow, monotonic=time.monotonic,
                 max_cache_entries=MAX_CACHE_ENTRIES):
        self.fetcher = fetcher or self._fetch
        self.now, self.monotonic = now, monotonic
        self.max_cache_entries = max_cache_entries
        self.cache = OrderedDict()
        self.inflight = {}
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async def _fetch(self, ticker):
        # Both paths and the origin are constants. No member-supplied URL,
        # credential, redirect, or trading operation is accepted.
        async with httpx.AsyncClient(timeout=4.0, follow_redirects=False) as client:
            for prefix in ("/markets/", "/historical/markets/"):
                async with client.stream("GET", API_ORIGIN + prefix + ticker,
                                         headers={"Accept": "application/json"}) as response:
                    if response.status_code == 404 and prefix == "/markets/":
                        continue
                    if response.status_code != 200:
                        return None
                    raw = bytearray()
                    async for chunk in response.aiter_bytes():
                        raw.extend(chunk)
                        if len(raw) > MAX_RESPONSE_BYTES:
                            return None
                    def invalid_constant(_):
                        raise ValueError("Non-finite result field")
                    return json.loads(raw, object_pairs_hook=_unique_object,
                                      parse_constant=invalid_constant)
        return None

    async def _load(self, asset, ticker):
        result = None
        try:
            # Queue time also counts, so an unavailable provider cannot build
            # an unbounded backlog behind the four permitted connections.
            async with asyncio.timeout(LOOKUP_TIMEOUT_SECONDS):
                async with self.semaphore:
                    result = verify_market(await self.fetcher(ticker), asset, ticker, self.now())
        except asyncio.CancelledError:
            raise
        except Exception:
            # No provider response body or request details in logs.
            result = None
        key = (asset, ticker)
        ttl = FINAL_CACHE_SECONDS if result else PENDING_CACHE_SECONDS
        self.cache[key] = (self.monotonic() + ttl, result)
        self.cache.move_to_end(key)
        while len(self.cache) > self.max_cache_entries:
            self.cache.popitem(last=False)
        return result

    async def get_outcome(self, asset, ticker):
        if not valid_ticker(asset, ticker):
            return None
        key = (asset, ticker)
        cached = self.cache.get(key)
        if cached and cached[0] > self.monotonic():
            self.cache.move_to_end(key)
            return cached[1]
        if cached:
            self.cache.pop(key, None)
        task = self.inflight.get(key)
        if task is None:
            if len(self.inflight) >= MAX_INFLIGHT:
                return None
            task = asyncio.create_task(self._load(asset, ticker))
            self.inflight[key] = task
            def done(completed):
                if self.inflight.get(key) is completed:
                    self.inflight.pop(key, None)
                if not completed.cancelled():
                    completed.exception()
            task.add_done_callback(done)
        return await asyncio.shield(task)

    async def shutdown(self):
        tasks = list(self.inflight.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


class NautilusSettlementService:
    """Reconcile server-owned PAPER ledgers with optimistic concurrency.

The worker scans only accounts with positions, in bounded keyset pages. Member
refreshes share this same resolver. A reset or any concurrent account write
invalidates the original revision and prevents old results crossing attempts.
"""
    def __init__(self, db, resolver=None, now=utcnow):
        self.db, self.now = db, now
        self.resolver = resolver or KalshiSettlementResolver(now=now)
        self.inflight = {}
        self.contract_cursors = OrderedDict()
        self.worker_cursor = None

    def _contracts(self, user_id, account):
        eligible = set()
        for position in account["positions"]:
            # New entries persist the native contract close time. Legacy
            # positions without it are resolved from the official market.
            close_at = parsed_time(position.get("contractCloseTime"))
            if close_at is not None and close_at > self.now():
                continue
            key = (position["asset"], position["contractId"])
            if valid_ticker(*key):
                eligible.add(key)
        ordered = sorted(eligible)
        last = self.contract_cursors.get(user_id)
        if last is not None:
            ordered = [key for key in ordered if key > last] + [key for key in ordered if key <= last]
        selected = ordered[:MAX_ACCOUNT_LOOKUPS]
        if selected:
            self.contract_cursors[user_id] = selected[-1]
            self.contract_cursors.move_to_end(user_id)
            while len(self.contract_cursors) > MAX_CACHE_ENTRIES:
                self.contract_cursors.popitem(last=False)
        return selected

    async def _reconcile(self, user_id):
        document = await self.db.nautilus_practice.find_one({"_id": user_id})
        if document is None:
            return None
        account = document.get("account")
        try:
            validate_account(account)
        except (PracticeError, TypeError, KeyError, AttributeError):
            logger.warning("A practice ledger could not be verified for settlement")
            return document
        revision = document.get("revision")
        if account["userId"] != user_id or type(revision) is not int or not 0 <= revision < 9_007_199_254_740_991:
            return document
        contracts = self._contracts(user_id, account)
        if not contracts:
            return document
        results = await asyncio.gather(*(self.resolver.get_outcome(*key) for key in contracts), return_exceptions=True)
        outcomes = {key: result for key, result in zip(contracts, results) if isinstance(result, VerifiedSettlement)}
        updated = deepcopy(account)
        settled = False
        for position in account["positions"]:
            outcome = outcomes.get((position["asset"], position["contractId"]))
            opened_at = parsed_time(position.get("openedAt"))
            if outcome is None or opened_at is None or not opened_at < outcome.close_at:
                continue
            identity = "\0".join((account["attemptId"], position["asset"], position["contractId"], position["id"]))
            transaction_id = "settle:" + hashlib.sha256(identity.encode()).hexdigest()
            try:
                updated = settle_position(updated, {"positionId": position["id"],
                    "transactionId": transaction_id, "officialWinningSide": outcome.winning_side,
                    "timestamp": iso(outcome.settled_at), "fee": 0})
            except PracticeError:
                logger.warning("A practice settlement could not be applied; position remains reserved")
                continue
            updated["transactions"][-1]["settlementEvidence"] = outcome.evidence()
            settled = True
        if not settled:
            return document
        replacement = {**document, "account": updated, "revision": revision + 1}
        result = await self.db.nautilus_practice.replace_one(
            {"_id": user_id, "revision": revision, "account.attemptId": account["attemptId"]}, replacement)
        if result.matched_count == 1:
            return replacement
        # No retry against stale state. The next refresh/worker round reconciles
        # the latest ledger; a reset is never undone and cash is never doubled.
        return await self.db.nautilus_practice.find_one({"_id": user_id})

    async def reconcile(self, user_id):
        task = self.inflight.get(user_id)
        if task is None:
            if len(self.inflight) >= MAX_RECONCILIATIONS:
                return await self.db.nautilus_practice.find_one({"_id": user_id})
            task = asyncio.create_task(self._reconcile(user_id))
            self.inflight[user_id] = task
            def done(completed):
                if self.inflight.get(user_id) is completed:
                    self.inflight.pop(user_id, None)
                if not completed.cancelled():
                    completed.exception()
            task.add_done_callback(done)
        return await asyncio.shield(task)

    async def tick(self):
        query = {"account.positions.0": {"$exists": True}}
        if self.worker_cursor is not None:
            query["_id"] = {"$gt": self.worker_cursor}
        rows = await self.db.nautilus_practice.find(query).sort("_id", 1).limit(WORKER_BATCH_SIZE).to_list(WORKER_BATCH_SIZE)
        if not rows:
            self.worker_cursor = None
            return
        for row in rows:
            self.worker_cursor = row["_id"]
            await self.reconcile(row["_id"])

    async def run(self):
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("Practice settlement paused after a database/provider error")
            await asyncio.sleep(WORKER_INTERVAL_SECONDS)

    async def shutdown(self):
        tasks = list(self.inflight.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await self.resolver.shutdown()
