"""Bounded, shared FMP last-price reads; never a simulated quote source.

Five-second cache and in-flight coalescing are local to one Python process.
This adapter does not establish realtime entitlement, an open exchange session,
order-book liquidity, or execution suitability. Provider observations may be
shown with provenance; this integration deliberately cannot authorize fills.
"""
import asyncio
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
import math
import os
import re
import time

import httpx

SOURCE = "FMP /stable/quote"
CACHE_SECONDS = 5.0
ERROR_CACHE_SECONDS = 2.0
RECENT_SECONDS = 30.0
MAX_CACHE_ENTRIES = 256
MAX_INFLIGHT = 64
SYMBOL = re.compile(r"[A-Z0-9][A-Z0-9.-]{0,19}\Z")


def utcnow():
    return datetime.now(timezone.utc)


def iso(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class QuoteUnavailable(Exception):
    def __init__(self, code, message, symbol, status_code=503):
        super().__init__(message)
        self.code, self.message, self.symbol, self.status_code = code, message, symbol, status_code

    def detail(self):
        return {"code": self.code, "message": self.message, "symbol": self.symbol,
                "source": SOURCE, "status": "unavailable"}


def normalize_symbol(value):
    if not isinstance(value, str):
        raise QuoteUnavailable("invalid_symbol", "Use a valid stock symbol.", "", 422)
    symbol = value.strip().upper().removeprefix("$")
    if not SYMBOL.fullmatch(symbol) or ".." in symbol or symbol.endswith((".", "-")):
        raise QuoteUnavailable("invalid_symbol", "Use a valid stock symbol.", symbol[:20], 422)
    return symbol


def number(value, positive=False):
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    if not math.isfinite(result) or (positive and result <= 0):
        return None
    return result


def observation_time(value):
    if value is None or value == "":
        return None, "missing"
    if isinstance(value, bool):
        return None, "invalid"
    try:
        # FMP's timestamp is Unix seconds. Do not silently reinterpret an invalid
        # millisecond or timezone-free field as a current market observation.
        if isinstance(value, (int, float)) or (isinstance(value, str) and re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value)):
            seconds = float(value)
            if not math.isfinite(seconds) or seconds <= 0:
                return None, "invalid"
            parsed = datetime.fromtimestamp(seconds, timezone.utc)
        elif isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return None, "invalid"
            parsed = parsed.astimezone(timezone.utc)
        else:
            return None, "invalid"
        return parsed, "valid"
    except (ValueError, TypeError, OverflowError, OSError):
        return None, "invalid"


def normalize_quote(payload, symbol, received):
    if not isinstance(payload, list):
        raise QuoteUnavailable("provider_response_invalid", "The quote provider returned an unavailable response.", symbol, 502)
    row = next((item for item in payload if isinstance(item, dict) and isinstance(item.get("symbol"), str) and item["symbol"].strip().upper() == symbol), None)
    if row is None:
        raise QuoteUnavailable("quote_unavailable", "No verified provider quote is available for this symbol.", symbol, 404)
    price = number(row.get("price"), positive=True)
    if price is None:
        raise QuoteUnavailable("provider_price_invalid", "The provider did not return a valid positive price.", symbol, 502)
    observed, timestamp_status = observation_time(row.get("timestamp"))
    change = number(row.get("change"))
    percent = number(row.get("changePercentage"))
    if percent is None:
        percent = number(row.get("changesPercentage"))
    return {"symbol": symbol, "price": price, "change": change, "changePercentage": percent,
            "changesPercentage": percent, "source": SOURCE,
            "source_timestamp": iso(observed) if observed else None,
            "timestamp": iso(observed) if observed else None,
            "received_at": iso(received), "timestamp_status": timestamp_status,
            "market_status": "unverified", "delay_status": "unverified",
            "execution_eligible": False,
            "execution_reason": "Market-session state and realtime data entitlement have not been verified."}


def describe_quote(quote, now, cache_hit):
    value = deepcopy(quote)
    observed, _ = observation_time(value["source_timestamp"])
    age = (now - observed).total_seconds() if observed else None
    if value["timestamp_status"] != "valid":
        status = "timestamp_" + value["timestamp_status"]
    elif age < -5:
        status = "timestamp_future"
    elif age > RECENT_SECONDS:
        status = "stale"
    else:
        status = "recent"
    value.update(status=status, age_seconds=round(age, 3) if age is not None else None, cache_hit=cache_hit)
    return value


class FMPQuoteService:
    def __init__(self, fetcher=None, now=utcnow, monotonic=time.monotonic, max_entries=MAX_CACHE_ENTRIES):
        self.fetcher = fetcher or self._fetch
        self.now = now
        self.monotonic = monotonic
        self.max_entries = max_entries
        self.cache = OrderedDict()
        self.inflight = {}

    async def _fetch(self, symbol):
        key = os.getenv("FMP_API_KEY", "")
        if not key:
            raise QuoteUnavailable("provider_not_configured", "Stock quotes are not configured.", symbol)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get("https://financialmodelingprep.com/stable/quote",
                                            params={"symbol": symbol, "apikey": key})
            if response.status_code == 429:
                raise QuoteUnavailable("provider_rate_limited", "The quote provider is temporarily rate limited.", symbol, 429)
            if response.status_code != 200:
                raise QuoteUnavailable("provider_unavailable", "The quote provider is unavailable for this request.", symbol)
            return response.json()
        except QuoteUnavailable:
            raise
        except Exception:
            # Do not log request URLs or exception text that may include API keys.
            raise QuoteUnavailable("provider_unavailable", "The quote provider could not be reached.", symbol) from None

    def _cache(self, symbol, value, lifetime):
        self.cache[symbol] = (self.monotonic() + lifetime, value)
        self.cache.move_to_end(symbol)
        while len(self.cache) > self.max_entries:
            self.cache.popitem(last=False)

    async def _load(self, symbol):
        try:
            payload = await self.fetcher(symbol)
            quote = normalize_quote(payload, symbol, self.now())
            self._cache(symbol, quote, CACHE_SECONDS)
            return quote
        except QuoteUnavailable as error:
            self._cache(symbol, error, ERROR_CACHE_SECONDS)
            raise
        except Exception:
            error = QuoteUnavailable("provider_unavailable", "The quote provider could not be reached.", symbol)
            self._cache(symbol, error, ERROR_CACHE_SECONDS)
            raise error from None

    async def get_quote(self, raw_symbol):
        symbol = normalize_symbol(raw_symbol)
        cached = self.cache.get(symbol)
        if cached and cached[0] > self.monotonic():
            self.cache.move_to_end(symbol)
            if isinstance(cached[1], QuoteUnavailable):
                raise cached[1]
            return describe_quote(cached[1], self.now(), True)
        if cached:
            self.cache.pop(symbol, None)
        task = self.inflight.get(symbol)
        coalesced = task is not None
        if task is None:
            if len(self.inflight) >= MAX_INFLIGHT:
                raise QuoteUnavailable("quote_service_busy", "The quote service is busy. Try again shortly.", symbol)
            task = asyncio.create_task(self._load(symbol))
            self.inflight[symbol] = task
            def done(completed):
                if self.inflight.get(symbol) is completed:
                    self.inflight.pop(symbol, None)
                # Retrieve failure even if every HTTP caller canceled its request.
                if not completed.cancelled():
                    completed.exception()
            task.add_done_callback(done)
        # A canceled browser request must not cancel other consumers' shared work.
        value = await asyncio.shield(task)
        return describe_quote(value, self.now(), coalesced)


stock_quote_service = FMPQuoteService()
