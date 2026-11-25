"""Member-facing Nautilus PAPER display and server-owned practice ledger.

Mount with ``app.include_router(create_nautilus_router(db))``. The publisher is
the only writer of market snapshots; member sessions never receive its secret.
The native engine remains read-only and no route places venue orders.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
from html.parser import HTMLParser
import json
import math
import os
import re
import time
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

try:
    from .membership import active_membership, MEMBERSHIP_REQUIRED
    from .nautilus_practice import (
        PracticeError, buy_contracts, close_position, create_account,
        reset_account, to_money_units,
    )
except ImportError:  # Existing deployment imports server.py as a top-level module.
    from membership import active_membership, MEMBERSHIP_REQUIRED
    from nautilus_practice import (
        PracticeError, buy_contracts, close_position, create_account,
        reset_account, to_money_units,
    )

ASSETS = ("BTC", "ETH", "SOL", "XRP", "DOGE")
MAX_PACKET_BYTES = 4 * 1024 * 1024
MAX_REQUEST_BYTES = 8192
MAX_RECEIPT_AGE = 15.0
MAX_SOURCE_AGE = 5.0
MAX_QUOTE_AGE = 3.0
MAX_CLOCK_SKEW = 2.0
FEE_POLICY = "fees-excluded"
SCALAR = object()


def _fields(names, **nested):
    return {**{name: SCALAR for name in names.split()}, **nested}


# This is an explicit public projection of the 0.0.10.7 native display schema.
# In particular, arbitrary diagnostics, source objects, paths, environment data,
# account identities, or newly added native keys are not passed through.
EMA_VALUE = _fields("basis completed_value period ready value")
EMA_CONTEXT = _fields(
    "basis completed_at completed_ema9_slope_per_min contiguous_completed "
    "current_direction direction_reason forming_at segment_start_ts",
    ema9=EMA_VALUE, ema30=EMA_VALUE,
)
GAP = _fields("start_ts end_ts missing_minutes reason")
PARENT = _fields(
    "compact_return completed_turn_at completed_turn_direction completed_turn_known_at "
    "continuation_direction continuation_edge_id continuation_kind continuation_ready "
    "direction dominant_direction dominant_extreme_at dominant_extreme_price "
    "dominant_known_at dominant_leg_id dominant_origin_price dominant_started_at "
    "dominant_transition elapsed_seconds ema30 ema9 ema9_slope extreme_price "
    "flow_direction height known_at leg_id mature_comparison opening_pullback_ready "
    "opening_value_origin origin_price phase previous_leg_height previous_leg_seconds "
    "previous_slope rail_parent_direction rail_parent_started_at reason started_at tempo weakening"
)
EYE = _fields(
    "completed_bars ema30_minute_slope ema9_minute_slope gap known_at "
    "median_leg_btc median_leg_minutes observed_leg_count reason recent_crossings shape"
)
EDGE = _fields("ceiling clock_matched enough_history high low median sample_count shape side why")
EDGES = {"YES": EDGE, "NO": EDGE}
OBSERVATION = _fields(
    "annotation available basis btc_fill_claim event execution_authority observed_at "
    "paper_event_ts position_id price received_ts run_id side source ticker reason"
)
ENTRY = _fields(
    "available btc_price_at_entry continuation_first_0104 contract_close contract_target "
    "direction edge_profit_policy_0104 entry_policy known_at origin_at origin_price "
    "parent_leg_id phase pocket_observed_extreme policy purpose reason recorded "
    "reference_height reference_seconds source source_at source_ms swing_id tactical_scout tempo terrain",
    destination=("scalar_or_object", _fields("kind")), parent_at_entry=PARENT,
    continuation_proof=_fields(
        "current_contract_bars directional_bars ema30 ema9 fast_slope known_at "
        "median_range origin_price parent_start_at phase recent_progress side source tick_progress"
    ),
)
MARK = _fields(
    "ticker qty bid pnl roi net_pnl net_roi exit_fee gross_proceeds net_liquidation "
    "remaining_basis observed_at source full_lot"
)
TRADE = _fields(
    "key trade_id position_id ticker side position_role entry_ts entry_ask qty "
    "original_qty cost entry_fee entry_basis fees_paid exit_fee net_return_basis "
    "closed exit_ts exit_bid exit_type settlement_payout winning_side net_pnl "
    "net_roi pnl roi inventory_verified state entry_reason exit_reason intent "
    "remaining_qty mark_valid close_ts manager management_lane valid_until "
    "mark_age_seconds mark_observed_at mark_reason current_bid open_pnl open_roi "
    "open_net_pnl open_net_roi display_bid display_pnl display_roi display_net_pnl display_net_roi",
    entry_btc=OBSERVATION, exit_btc=OBSERVATION, mission=ENTRY,
    entry_context=ENTRY, last_verified_mark=MARK,
    protection=_fields("peak_bid stop_bid floor_net_profit minimum_collection mode fresh armed time reason"),
)
PATH = _fields(
    "conditional execution_authority family historical_source_end_ts "
    "historical_source_start_ts id probability reference_alignment "
    "reference_duration_seconds reference_end_ts reference_known_by_ts "
    "reference_start_ts repeated time_stretched horizon_ts",
    reference_ids=(SCALAR, 30), points=(_fields("btc e9 ema9 e30 ema30 time"), 1000),
)
PATTERN = _fields(
    "status conditional execution_authority source_ts key path_id horizon_ts "
    "continuity_generation label reason"
)
GLASS = _fields(
    "version close_ts comparison_ready comparison_wait_reason execution_authority "
    "horizon_end_ts horizon_mode horizon_seconds kind probabilities_calibrated "
    "projection_scope reason source_ts status ticker valid_until",
    observations=_fields("ema9_direction ema9_slope_per_min execution_authority source"),
    active_pattern=PATTERN, paths=(PATH, 12),
    anchor=_fields("btc completed_bars ema9 ema9_basis issued_at segment_start_ts time e9"),
    current_observation=EMA_CONTEXT,
    research={"as_issued": (_fields(
        "version frozen conditional execution_authority run_id ticker close_ts pattern_key "
        "continuity_generation source_ts issued_at_ts horizon_end_ts horizon_mode "
        "horizon_seconds projection_scope label",
        path=PATH, anchor=_fields("time btc e9"),
    ), 16)},
)
HEALTH = _fields("status reason updated", latest_gap=GAP)
QUOTE_VALUES = _fields("yes_bid yes_ask no_bid no_ask ticker verified_at")
SNAPSHOT_SCHEMA = _fields(
    "mode readonly version server_now chart_eye_readonly",
    application=_fields("dashboard_build engine_version ui_protocol"),
    run=_fields("name run_id version fresh updated stopped review status pointer_changed"),
    clock=_fields("verified estimated close_ts valid_until status", clock=_fields("continuous")),
    asset=_fields("symbol normalization source_product actual_spot actual_target"),
    market=_fields("ticker btc close_ts time fresh target e9 e30", ema_context=EMA_CONTEXT),
    quote=_fields(
        "ticker source fresh valid_until reason yes_bid no_bid yes_ask no_ask "
        "exchange_age_sec last_verified_age_seconds", last_verified=QUOTE_VALUES,
    ),
    candles=(_fields("time open high low close known_at source quality complete last_trade_at"), 10000),
    emas=(_fields("time e9 e30 basis segment_start"), 10000),
    targets=(_fields("ticker target start_ts close_ts observed_at"), 1000),
    quotes=(_fields("time ticker yes_bid yes_ask no_bid no_ask"), 10000),
    positions=(TRADE, 500), trades=(TRADE, 4000),
    commands=(_fields("event key reason side time"), 1000),
    accounting=_fields("cash realized_net realized fees_paid closed basis inventory_verified realized_stale final"),
    diagnostics=_fields(
        "sampled_candles candle_note ema_note command_window source_hash "
        "live_bar_display conditional_paths",
        freshness_check=_fields("btc native_quote"),
    ),
    history=_fields(
        "available_completed_minutes completed_minutes contiguous_completed developing_note "
        "developing_status ema30_ready ema9_ready ema_basis forming_adjacent "
        "sampled_display_minutes sampled_display_only segment_start_ts signed_ema9_ready status",
        ema_context=EMA_CONTEXT, gaps=(GAP, 1000), latest_gap=GAP,
    ),
    health={name: HEALTH for name in ("candles", "commander", "engine", "physical", "price", "quotes")},
    feed=(_fields("category text time"), 100),
    contract_exposure=(_fields("ticker yes_qty no_qty inventory_verified pending_settlement net_qty net_side"), 500),
    interpretation={"pilot": _fields("reason"), "battle_plan": {}},
    mission_context=_fields(
        "available continuation_kind continuation_ready current flow_direction policy source_ms valid_until",
        contract=_fields("age_seconds reason remaining_seconds ticker"),
        parent=_fields("age_seconds direction extreme_at extreme_price id known_at origin_price reason side started_at transition"),
        local_arc=_fields("age_seconds direction extreme_price height id origin_price phase relation side tempo"),
    ),
    parent_arc=PARENT, chart_eye_0095=EYE, historical_edge_price_0095=EDGES,
    chart_eye_history_0095=(_fields("at shape", eye=EYE, peak_prices=EDGES), 12),
    observed_edge=_fields("available"), looking_glass=GLASS,
)


def _error(status, message):
    raise HTTPException(status_code=status, detail=message)


def _asset(value):
    if not isinstance(value, str) or value.upper() not in ASSETS:
        _error(404, "This bot asset is not available.")
    return value.upper()


def _number(value):
    return type(value) in (int, float) and abs(value) <= 9_007_199_254_740_991 and math.isfinite(value)


def _public_string(value):
    if len(value) > 2048:
        _error(422, "A snapshot text field is too long.")
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
    # Native reasons occasionally include exceptions. Never display host paths
    # or credential assignments accidentally included in an exception string.
    value = re.sub(r"(?<![\w])(?:[A-Za-z]:[\\/]|/(?:home|Users|workspace|tmp|etc|var|mnt|opt|root)/)[^\s,;]+", "[redacted path]", value)
    return re.sub(r"(?i)\b(?:api[_-]?key|password|secret|access[_-]?token|authorization)\s*[:=]\s*[^\s,;]+", "[redacted credential]", value)


def _project(value, schema, depth=0):
    if depth > 20:
        _error(422, "The snapshot is nested too deeply.")
    if value is None:
        return None
    if schema is SCALAR:
        if isinstance(value, str):
            return _public_string(value)
        if isinstance(value, bool) or _number(value):
            return value
        _error(422, "The snapshot contains an invalid scalar value.")
    if isinstance(schema, tuple):
        if schema[0] == "scalar_or_object":
            return _project(value, schema[1] if isinstance(value, dict) else SCALAR, depth + 1)
        item_schema, limit = schema
        if not isinstance(value, list) or len(value) > limit:
            _error(422, "A snapshot list has an invalid type or length.")
        return [_project(item, item_schema, depth + 1) for item in value]
    if not isinstance(value, dict):
        _error(422, "A snapshot object has an invalid type.")
    return {key: _project(value[key], child, depth + 1) for key, child in schema.items() if key in value}


def sanitize_snapshot(packet, asset, now=None):
    """Return the allowlisted native packet, or fail closed on invalid identity."""
    now = time.time() if now is None else now
    asset = _asset(asset)
    if not isinstance(packet, dict) or packet.get("mode") != "PAPER_ONLY" or packet.get("readonly") is not True:
        _error(422, "Only read-only PAPER_ONLY Nautilus packets are accepted.")
    for field in ("asset", "application", "run", "market", "quote"):
        if not isinstance(packet.get(field), dict):
            _error(422, "The native snapshot is missing a required object.")
    if packet["asset"].get("symbol") != asset:
        _error(422, "The snapshot asset does not match this publisher route.")
    version = packet["application"].get("engine_version")
    if not isinstance(version, str) or not version.endswith("_PAPER_ONLY"):
        _error(422, "The native engine must identify a PAPER_ONLY build.")
    for value in (packet.get("server_now"), packet["run"].get("updated")):
        if not _number(value) or value <= 0 or value > now + MAX_CLOCK_SKEW:
            _error(422, "The snapshot source timestamp is invalid or ahead of the server.")
    for field in ("fresh", "stopped", "review"):
        if type(packet["run"].get(field)) is not bool:
            _error(422, "The native run freshness flags are invalid.")
    for container, key in (("market", "time"), ("market", "close_ts"), ("quote", "valid_until")):
        value = packet[container].get(key)
        if value is not None and (not _number(value) or value <= 0):
            _error(422, "The snapshot has an invalid market timestamp.")
    if _number(packet["market"].get("time")) and packet["market"]["time"] > now + MAX_CLOCK_SKEW:
        _error(422, "The native price timestamp is ahead of the server.")
    for values in (packet["quote"], packet["quote"].get("last_verified") or {}):
        if not isinstance(values, dict):
            _error(422, "The native quote is invalid.")
        for key in ("yes_bid", "yes_ask", "no_bid", "no_ask"):
            value = values.get(key)
            if value is not None and (not _number(value) or not 0 <= value <= 1):
                _error(422, "Native contract prices must be between zero and one dollar.")
        for side in ("yes", "no"):
            bid, ask = values.get(side + "_bid"), values.get(side + "_ask")
            if _number(bid) and _number(ask) and bid > ask:
                _error(422, "The native quote has a crossed bid and ask.")
    result = _project(packet, SNAPSHOT_SCHEMA)
    for key in ("name", "run_id"):
        value = result["run"].get(key)
        if isinstance(value, str):
            # A run identifier is a basename, never a host filesystem location.
            result["run"][key] = re.split(r"[/\\]", value)[-1][:160]
    result["run"]["session_id"] = "PUBLIC_PAPER"
    for candle in result.get("candles") or []:
        if not isinstance(candle, dict) or not _number(candle.get("time")) or not 0 < candle["time"] <= now + MAX_CLOCK_SKEW:
            _error(422, "A native candle has an invalid timestamp.")
        if any(not _number(candle.get(key)) or candle[key] <= 0 for key in ("open", "high", "low", "close")):
            _error(422, "A native candle has invalid price data.")
        if candle["high"] < max(candle["open"], candle["close"], candle["low"]) or candle["low"] > min(candle["open"], candle["close"]):
            _error(422, "A native candle has inconsistent high and low prices.")
    return result


def _iso(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")


def _date_epoch(value):
    try:
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if not isinstance(value, datetime):
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.timestamp()
    except (ValueError, TypeError, OverflowError):
        return None


async def _member(request, db):
    user_id, session_id = request.headers.get("X-User-ID", ""), request.headers.get("X-Session-ID", "")
    if not user_id or not session_id or len(user_id) > 240 or len(session_id) > 240:
        _error(401, "Sign in again to open the bot rooms.")
    user = await db.users.find_one({"id": user_id})
    active = user.get("active_session_id") if user else None
    if not isinstance(active, str) or not active or not hmac.compare_digest(active.encode(), session_id.encode()):
        _error(401, "This session is no longer active. Sign in again.")
    if not active_membership(user, datetime.fromtimestamp(time.time(), timezone.utc)):
        raise HTTPException(403, MEMBERSHIP_REQUIRED)
    return user


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


async def _json_body(request, limit=MAX_REQUEST_BYTES):
    if request.headers.get("content-encoding", "identity").lower() != "identity":
        _error(415, "Compressed request bodies are not accepted.")
    chunks, length = [], 0
    async for chunk in request.stream():
        length += len(chunk)
        if length > limit:
            _error(413, "The request body is too large.")
        chunks.append(chunk)
    try:
        def invalid_constant(_):
            raise ValueError("Non-finite JSON number")
        body = json.loads(b"".join(chunks), parse_constant=invalid_constant, object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError, RecursionError):
        _error(422, "Send a valid JSON object.")
    if not isinstance(body, dict):
        _error(422, "Send a JSON object.")
    return body


def _identity(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 240 or any(ord(c) < 32 for c in value):
        _error(422, label + " is required and must be a short string.")
    return value.strip()


def _age_current(value, now, maximum):
    return _number(value) and -MAX_CLOCK_SKEW <= now - value <= maximum


def trusted_quote(document, asset, contract_id, side, action, now=None):
    """Select an observed native bid/ask. Never accept a browser-supplied mark."""
    now = time.time() if now is None else now
    if not document or not _age_current(document.get("receivedAt"), now, MAX_RECEIPT_AGE):
        _error(409, "The bot feed is offline or stale. Wait for a current native quote.")
    packet = document.get("snapshot") or {}
    run, market, quote = (packet.get(key) or {} for key in ("run", "market", "quote"))
    if packet.get("mode") != "PAPER_ONLY" or packet.get("readonly") is not True or (packet.get("asset") or {}).get("symbol") != asset:
        _error(409, "A verified PAPER feed is required for practice.")
    if run.get("stopped") is not False or run.get("review") is not False or run.get("fresh") is not True:
        _error(409, "This bot is stopped or in review. Live practice fills are unavailable.")
    if market.get("fresh") is not True or not all(_age_current(value, now, MAX_SOURCE_AGE) for value in (packet.get("server_now"), run.get("updated"), market.get("time"))):
        _error(409, "The native source is stale. Wait for a current quote.")
    verified = quote.get("last_verified") or {}
    if not isinstance(contract_id, str) or not contract_id.startswith("KX" + asset + "15M-") or any(value != contract_id for value in (market.get("ticker"), quote.get("ticker"), verified.get("ticker"))):
        _error(409, "This contract is no longer the bot's current native market.")
    if side not in ("YES", "NO") or action not in ("buy", "close"):
        _error(422, "Choose YES or NO for this practice order.")
    close_at, deadline, observed = market.get("close_ts"), quote.get("valid_until"), verified.get("verified_at")
    if not _number(close_at) or now >= close_at:
        _error(409, "This contract has closed. It cannot use a newer contract's quote.")
    if quote.get("source") != "KALSHI_PUBLIC_BOOK" or quote.get("fresh") is not True or not _age_current(observed, now, MAX_QUOTE_AGE) or not _number(deadline) or now > deadline or deadline > observed + MAX_QUOTE_AGE + 0.001:
        _error(409, "The native quote has expired. Wait for the next verified quote.")
    field = side.lower() + ("_ask" if action == "buy" else "_bid")
    price = quote.get(field)
    if not _number(price) or not 0 <= price <= 1 or (action == "buy" and price == 0) or verified.get(field) != price:
        _error(409, "A verified native price is not available for this side.")
    return price


def snapshot_state(document, now=None):
    now = time.time() if now is None else now
    if not document:
        return "offline"
    packet = document.get("snapshot") or {}
    run = packet.get("run") or {}
    if run.get("stopped") is True or run.get("review") is True or not _age_current(document.get("receivedAt"), now, 120):
        return "offline"
    try:
        market = packet.get("market") or {}
        # A source can be displayed while no executable side quote is present.
        side = "YES" if _number((packet.get("quote") or {}).get("yes_ask")) else "NO"
        trusted_quote(document, (packet.get("asset") or {}).get("symbol"), market.get("ticker"), side, "buy", now)
    except HTTPException:
        return "stale"
    return "live"


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def clean_chat_text(value, maximum=1000):
    if not isinstance(value, str) or len(value) > maximum:
        _error(422, f"Chat text must contain at most {maximum} characters.")
    parser = _PlainText()
    parser.feed(value)
    result = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", "".join(parser.parts)).strip()
    if not result:
        _error(422, "Enter a chat message.")
    return result


def _chat_view(document):
    return {key: document[key] for key in ("id", "author", "content", "createdAt", "isAdmin")}


def _account_view(document):
    return {"account": document["account"], "revision": document["revision"], "feePolicy": FEE_POLICY}


async def _get_account(db, user_id):
    document = await db.nautilus_practice.find_one({"_id": user_id})
    if document is not None:
        return document
    initial = {"account": create_account({"userId": user_id, "attemptId": str(uuid4())}), "revision": 0, "operations": []}
    try:
        await db.nautilus_practice.update_one({"_id": user_id}, {"$setOnInsert": initial}, upsert=True)
    except Exception as error:
        # Two tabs can create the first account together; Mongo's unique _id
        # resolves that race. Other persistence failures must not be hidden.
        if getattr(error, "code", None) != 11000:
            raise
    return await db.nautilus_practice.find_one({"_id": user_id})


def _operation(body, kind):
    extras = {"buy": {"asset", "contractId", "side", "budget"}, "close": {"positionId"}, "reset": set()}[kind]
    if set(body) != ({"attemptId", "revision", "transactionId"} | extras):
        _error(422, "The practice request has missing or unsupported fields.")
    for key in ("attemptId", "transactionId"):
        body[key] = _identity(body[key], key)
    if type(body["revision"]) is not int or not 0 <= body["revision"] < 9_007_199_254_740_991:
        _error(422, "A valid account revision is required.")
    if kind == "buy":
        body["asset"] = _asset(body["asset"])
        body["contractId"] = _identity(body["contractId"], "Contract ID")
        if body["side"] not in ("YES", "NO"):
            _error(422, "Choose YES or NO.")
        try:
            units = to_money_units(body["budget"], "Budget")
        except PracticeError as error:
            _error(422, str(error))
        if units <= 0:
            _error(422, "Choose a practice budget greater than zero.")
        body["budget"] = units / 1_000_000
    if kind == "close":
        body["positionId"] = _identity(body["positionId"], "Position ID")
    fingerprint = hashlib.sha256(json.dumps({"kind": kind, **body}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return fingerprint


def _duplicate(document, body, fingerprint):
    receipt = next((row for row in document.get("operations", []) if row["id"] == body["transactionId"]), None)
    if receipt:
        if receipt["requestHash"] != fingerprint:
            _error(409, "This transaction ID was already used for a different request.")
        return True
    return False


def create_nautilus_router(db):
    router = APIRouter(prefix="/api/nautilus", tags=["Nautilus PAPER"])

    @router.get("/bots/{asset}")
    async def get_bot(asset: str, request: Request):
        await _member(request, db)
        asset = _asset(asset)
        document = await db.nautilus_snapshots.find_one({"_id": asset})
        return {"snapshot": document["snapshot"] if document else None, "state": snapshot_state(document), "receivedAt": _iso(document["receivedAt"]) if document else None}

    @router.post("/ingest/{asset}")
    async def ingest(asset: str, request: Request):
        expected = os.environ.get("NAUTILUS_PUBLISHER_KEY", "")
        supplied = request.headers.get("X-Nautilus-Publisher-Key", "")
        if len(expected) < 32:
            _error(503, "The Nautilus publisher secret is not configured.")
        if not supplied or len(supplied) > 512 or not hmac.compare_digest(supplied.encode(), expected.encode()):
            _error(401, "The publisher credential is invalid.")
        asset = _asset(asset)
        packet = sanitize_snapshot(await _json_body(request, MAX_PACKET_BYTES), asset)
        now, source_at = time.time(), packet["server_now"]
        existing = await db.nautilus_snapshots.find_one({"_id": asset})
        if existing and source_at <= existing["sourceAt"]:
            if source_at == existing["sourceAt"]:
                return {"accepted": False, "asset": asset, "receivedAt": _iso(existing["receivedAt"])}
            _error(409, "An older source snapshot cannot replace the current one.")
        document = {"_id": asset, "snapshot": packet, "sourceAt": source_at, "receivedAt": now}
        if existing:
            result = await db.nautilus_snapshots.replace_one({"_id": asset, "sourceAt": existing["sourceAt"]}, document)
            if result.matched_count != 1:
                _error(409, "A newer source snapshot arrived. Publish the next native packet.")
        else:
            try:
                await db.nautilus_snapshots.insert_one(document)
            except Exception as error:
                if getattr(error, "code", None) == 11000:
                    _error(409, "A source snapshot arrived concurrently. Publish the next native packet.")
                raise
        return {"accepted": True, "asset": asset, "receivedAt": _iso(now)}

    @router.get("/chat/{asset}")
    async def get_chat(asset: str, request: Request):
        await _member(request, db)
        asset = _asset(asset)
        cursor = db.nautilus_chat.find({"asset": asset}).sort("createdAt", -1).limit(50)
        documents = await cursor.to_list(length=50)
        return {"messages": [_chat_view(document) for document in reversed(documents)]}

    @router.post("/chat/{asset}")
    async def post_chat(asset: str, request: Request):
        member = await _member(request, db)
        asset = _asset(asset)
        body = await _json_body(request)
        if set(body) != {"text"}:
            _error(422, "Send only the chat text; the server supplies the author.")
        content = clean_chat_text(body["text"])
        name = str(member.get("screen_name") or member.get("username") or "Member")[:80]
        try:
            name = clean_chat_text(name, 80)
        except HTTPException:
            name = "Member"
        document = {"_id": str(uuid4()), "id": str(uuid4()), "asset": asset, "authorId": member["id"], "author": name, "content": content, "createdAt": _iso(time.time()), "isAdmin": member.get("is_admin") is True or member.get("role") == "admin"}
        await db.nautilus_chat.insert_one(document)
        return {"message": _chat_view(document)}

    @router.get("/practice")
    async def get_practice(request: Request):
        member = await _member(request, db)
        return _account_view(await _get_account(db, member["id"]))

    async def mutate(request, kind):
        member = await _member(request, db)
        body = await _json_body(request)
        fingerprint = _operation(body, kind)
        document = await _get_account(db, member["id"])
        if _duplicate(document, body, fingerprint):
            return _account_view(document)
        account = document["account"]
        if document["revision"] != body["revision"] or account["attemptId"] != body["attemptId"]:
            _error(409, "Your practice account changed. Refresh it before trying again.")
        if kind != "reset" and len(account["transactions"]) >= 5000:
            _error(409, "This practice attempt is full. Reset to begin a new attempt.")
        try:
            if kind == "buy":
                quote_document = await db.nautilus_snapshots.find_one({"_id": body["asset"]})
                price = trusted_quote(quote_document, body["asset"], body["contractId"], body["side"], "buy")
                updated = buy_contracts(account, {**body, "ask": price, "fee": 0, "timestamp": _iso(time.time())})
            elif kind == "close":
                position = next((row for row in account["positions"] if row["id"] == body["positionId"]), None)
                if position is None:
                    _error(409, "This practice position is no longer open.")
                quote_document = await db.nautilus_snapshots.find_one({"_id": position["asset"]})
                price = trusted_quote(quote_document, position["asset"], position["contractId"], position["side"], "close")
                updated = close_position(account, {**body, "bid": price, "fee": 0, "timestamp": _iso(time.time())})
            else:
                updated = reset_account(account, {"attemptId": str(uuid4())})
        except PracticeError as error:
            _error(409 if error.code in ("DUPLICATE_TRANSACTION", "INSUFFICIENT_FUNDS") else 422, str(error))
        next_revision = document["revision"] + 1
        receipts = document.get("operations", [])[-255:] + [{"id": body["transactionId"], "attemptId": body["attemptId"], "kind": kind, "requestHash": fingerprint, "revision": next_revision}]
        replacement = {"_id": member["id"], "account": updated, "revision": next_revision, "operations": receipts}
        result = await db.nautilus_practice.replace_one({"_id": member["id"], "revision": body["revision"], "account.attemptId": body["attemptId"]}, replacement)
        if result.matched_count != 1:
            latest = await _get_account(db, member["id"])
            if _duplicate(latest, body, fingerprint):
                return _account_view(latest)
            _error(409, "Another practice action completed first. Refresh the account and try again.")
        return _account_view(replacement)

    @router.post("/practice/buy")
    async def buy(request: Request):
        return await mutate(request, "buy")

    @router.post("/practice/close")
    async def close(request: Request):
        return await mutate(request, "close")

    @router.post("/practice/reset")
    async def reset(request: Request):
        return await mutate(request, "reset")

    return router
