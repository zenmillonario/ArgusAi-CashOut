"""Server-owned, deterministic PAPER ledger; prices and fees use microdollars.

This is the Python counterpart of frontend/src/nautilus/practiceEngine.js.
It accepts USD decimal inputs and stores only integer money units. HTTP routes
must authenticate the owner, source quotes/outcomes, and persist atomically.
No input balance, live trade, market price, or exchange fee schedule is inferred.
"""
from copy import deepcopy
from decimal import Decimal
import math
import re

MONEY_SCALE = 1_000_000
STARTING_BALANCE = 100
DEFAULT_ENTRY_BUDGET = 25
MAX_SAFE_INTEGER = 9_007_199_254_740_991
SUPPORTED_ASSETS = ("BTC", "ETH", "SOL", "XRP", "DOGE")


class PracticeError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _fail(code, message):
    raise PracticeError(code, message)


def _safe_result(value):
    if type(value) is not int or abs(value) > MAX_SAFE_INTEGER:
        _fail("AMOUNT_TOO_LARGE", "The amount is too large.")
    return value


def _integer(value, label, minimum=0):
    if type(value) is not int or value < minimum or value > MAX_SAFE_INTEGER:
        _fail("INVALID_VALUE", f"{label} must be a safe integer at least {minimum}.")
    return value


def _identity(value, label):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 240:
        _fail("INVALID_ID", f"{label} is required.")
    return value.strip()


def _side(value):
    if value not in ("YES", "NO"):
        _fail("INVALID_SIDE", "Choose YES or NO.")
    return value


def _asset(value):
    if value not in SUPPORTED_ASSETS:
        _fail("INVALID_ASSET", "Choose a supported bot asset.")
    return value


def to_money_units(value, label="Amount"):
    if type(value) not in (int, float, str):
        _fail("INVALID_AMOUNT", f"{label} must be a dollar amount.")
    if type(value) is float and not math.isfinite(value):
        _fail("INVALID_AMOUNT", f"{label} must be finite.")
    # Numeric exponents are expanded before precision validation, matching JS
    # String(0.000001); values smaller than one microdollar remain invalid.
    text = format(Decimal(str(value)), "f") if type(value) is float else str(value).strip()
    match = re.fullmatch(r"(\d+)(?:\.(\d{0,6}))?", text, re.ASCII)
    if not match:
        _fail("INVALID_AMOUNT", f"{label} must be nonnegative with at most 6 decimal places.")
    units = int(match[1]) * MONEY_SCALE + int((match[2] or "").ljust(6, "0"))
    if units > MAX_SAFE_INTEGER:
        _fail("AMOUNT_TOO_LARGE", f"{label} is too large.")
    return units


def from_money_units(units):
    return _safe_result(units) / MONEY_SCALE


def _price(value, label, allow_zero):
    units = to_money_units(value, label)
    if units > MONEY_SCALE or (not allow_zero and units == 0):
        interval = "between $0 and $1" if allow_zero else "greater than $0 and no more than $1"
        _fail("INVALID_PRICE", f"{label} must be {interval}.")
    return units


def _quantity(value):
    if type(value) is not int or value <= 0 or value > MAX_SAFE_INTEGER:
        _fail("INVALID_QUANTITY", "The number of contracts must be a positive whole number.")
    return value


def _timestamp(value):
    if value is None:
        return None
    if isinstance(value, str) and len(value) <= 80:
        return value
    if type(value) in (int, float) and math.isfinite(value):
        return value
    _fail("INVALID_TIMESTAMP", "A valid timestamp is required.")


def create_account(options=None):
    options = options or {}
    return {
        "version": 1, "mode": "PAPER", "currency": "USD",
        "userId": _identity(options.get("userId", "local-preview"), "User ID"),
        "attemptId": _identity(options.get("attemptId", "attempt-1"), "Attempt ID"),
        "resetCount": 0, "initialBalanceUnits": STARTING_BALANCE * MONEY_SCALE,
        "cashUnits": STARTING_BALANCE * MONEY_SCALE,
        "realizedPnlUnits": 0, "totalFeesUnits": 0,
        "positions": [], "transactions": [], "transactionIds": [],
    }


def validate_account(account):
    if not isinstance(account, dict) or account.get("version") != 1 or account.get("mode") != "PAPER" or \
       account.get("currency") != "USD" or account.get("initialBalanceUnits") != STARTING_BALANCE * MONEY_SCALE:
        _fail("INVALID_ACCOUNT", "The practice account is invalid.")
    _identity(account.get("userId"), "User ID")
    _identity(account.get("attemptId"), "Attempt ID")
    _integer(account.get("cashUnits"), "Cash")
    _integer(account.get("totalFeesUnits"), "Fees")
    _integer(account.get("resetCount"), "Reset count")
    _safe_result(account.get("realizedPnlUnits"))
    if any(not isinstance(account.get(key), list) for key in ("positions", "transactions", "transactionIds")):
        _fail("INVALID_ACCOUNT", "The practice ledger is invalid.")
    seen = set()
    basis = 0
    for position in account["positions"]:
        _identity(position.get("id"), "Position ID")
        _identity(position.get("contractId"), "Contract ID")
        _asset(position.get("asset"))
        _side(position.get("side"))
        _quantity(position.get("quantity"))
        if position["id"] in seen:
            _fail("INVALID_ACCOUNT", "Duplicate positions in the ledger.")
        seen.add(position["id"])
        _integer(position.get("entryGrossUnits"), "Entry amount", 1)
        _integer(position.get("entryFeeUnits"), "Entry fee")
        _integer(position.get("entryCostUnits"), "Cost basis", 1)
        if position["entryCostUnits"] != position["entryGrossUnits"] + position["entryFeeUnits"]:
            _fail("INVALID_ACCOUNT", "The position cost basis does not balance.")
        basis = _safe_result(basis + position["entryCostUnits"])
    ids = account["transactionIds"]
    if any(not isinstance(item, str) for item in ids) or len(set(ids)) != len(ids) or \
       len(ids) != len(account["transactions"]) or \
       any(tx.get("id") != ids[i] for i, tx in enumerate(account["transactions"])):
        _fail("INVALID_ACCOUNT", "The transaction history is invalid.")
    if _safe_result(account["cashUnits"] + basis) != _safe_result(account["initialBalanceUnits"] + account["realizedPnlUnits"]):
        _fail("INVALID_ACCOUNT", "The practice account does not balance.")
    return account


def _new_transaction(account, transaction_id):
    validate_account(account)
    value = _identity(transaction_id, "Transaction ID")
    if value in account["transactionIds"]:
        _fail("DUPLICATE_TRANSACTION", "This practice transaction was already recorded.")
    return value


def quote_purchase(options=None):
    """fee is an explicitly supplied TOTAL order fee, never a per-contract fee."""
    options = options or {}
    account = options.get("account")
    if account is not None:
        validate_account(account)
    ask_units = _price(options.get("ask"), "Ask price", False)
    budget_units = to_money_units(options.get("budget", DEFAULT_ENTRY_BUDGET), "Budget")
    if budget_units == 0:
        _fail("INVALID_BUDGET", "Choose a budget greater than zero.")
    fee_units = to_money_units(options.get("fee", 0), "Total entry fee")
    available_units = account["cashUnits"] if account is not None else budget_units
    effective_budget_units = min(budget_units, available_units)
    maximum = (effective_budget_units - fee_units) // ask_units if effective_budget_units >= fee_units else 0
    if maximum < 1:
        _fail("INSUFFICIENT_FUNDS", "The available practice cash cannot cover one contract and its fee.")
    count = _quantity(options["quantity"]) if "quantity" in options else maximum
    if count > maximum:
        _fail("INSUFFICIENT_BUDGET", "The order exceeds the available cash or fee-inclusive budget.")
    gross_units = _safe_result(ask_units * count)
    total_cost_units = _safe_result(gross_units + fee_units)
    return {
        "quantity": count, "maxQuantity": maximum, "ask": from_money_units(ask_units),
        "budget": from_money_units(budget_units), "effectiveBudget": from_money_units(effective_budget_units),
        "grossCost": from_money_units(gross_units), "fee": from_money_units(fee_units), "fees": from_money_units(fee_units),
        "totalCost": from_money_units(total_cost_units), "remainingCash": from_money_units(available_units - total_cost_units),
        "canAfford": True, "askUnits": ask_units, "grossUnits": gross_units, "feeUnits": fee_units,
        "totalCostUnits": total_cost_units, "feePolicy": "explicit-total-fee",
    }


def buy_contracts(account, options=None):
    options = options or {}
    transaction_id = _new_transaction(account, options.get("transactionId"))
    asset = _asset(options.get("asset"))
    contract_id = _identity(options.get("contractId"), "Contract ID")
    side = _side(options.get("side"))
    timestamp = _timestamp(options.get("timestamp"))
    quote = quote_purchase({**options, "account": account})
    next_account = deepcopy(account)
    position = next((p for p in next_account["positions"] if p["asset"] == asset and p["contractId"] == contract_id and p["side"] == side), None)
    if position is not None:
        position["quantity"] = _safe_result(position["quantity"] + quote["quantity"])
        position["entryGrossUnits"] = _safe_result(position["entryGrossUnits"] + quote["grossUnits"])
        position["entryFeeUnits"] = _safe_result(position["entryFeeUnits"] + quote["feeUnits"])
        position["entryCostUnits"] = _safe_result(position["entryCostUnits"] + quote["totalCostUnits"])
        position["updatedAt"] = timestamp
    else:
        position = {
            "id": f"pos:{len(next_account['transactions']) + 1}:{asset}:{side}",
            "asset": asset, "contractId": contract_id, "side": side, "quantity": quote["quantity"],
            "entryGrossUnits": quote["grossUnits"], "entryFeeUnits": quote["feeUnits"], "entryCostUnits": quote["totalCostUnits"],
            "openedAt": timestamp, "updatedAt": timestamp,
        }
        next_account["positions"].append(position)
    if options.get("contractCloseTime") is not None:
        # Supplied only by the API's authenticated publisher snapshot, never by
        # the member order. Older accounts without this field remain valid.
        position["contractCloseTime"] = _timestamp(options["contractCloseTime"])
    next_account["cashUnits"] -= quote["totalCostUnits"]
    next_account["totalFeesUnits"] = _safe_result(next_account["totalFeesUnits"] + quote["feeUnits"])
    next_account["transactions"].append({
        "id": transaction_id, "type": "BUY", "asset": asset, "contractId": contract_id, "side": side,
        "positionId": position["id"], "quantity": quote["quantity"], "priceUnits": quote["askUnits"],
        "grossUnits": quote["grossUnits"], "feeUnits": quote["feeUnits"], "costBasisUnits": quote["totalCostUnits"],
        "netCashChangeUnits": -quote["totalCostUnits"], "realizedPnlUnits": 0, "timestamp": timestamp,
    })
    next_account["transactionIds"].append(transaction_id)
    return validate_account(next_account)


def _get_position(account, position_id):
    value = _identity(position_id, "Position ID")
    position = next((p for p in account["positions"] if p["id"] == value), None)
    if position is None:
        _fail("POSITION_NOT_FOUND", "This practice position is no longer open.")
    return position


def estimate_position_exit(position, options=None):
    options = options or {}
    count = _quantity(options["quantity"]) if "quantity" in options else position["quantity"]
    if count > position["quantity"]:
        _fail("INVALID_QUANTITY", "You cannot close more contracts than you hold.")
    bid_units = _price(options.get("bid"), "Bid price", True)
    fee_units = to_money_units(options.get("fee", 0), "Total exit fee")
    gross_units = _safe_result(bid_units * count)
    entry_gross_units = position["entryGrossUnits"] * count // position["quantity"]
    entry_fee_units = position["entryFeeUnits"] * count // position["quantity"]
    cost_basis_units = entry_gross_units + entry_fee_units
    net_proceeds_units = gross_units - fee_units
    pnl_units = _safe_result(net_proceeds_units - cost_basis_units)
    return {
        "quantity": count, "bid": from_money_units(bid_units), "grossProceeds": from_money_units(gross_units),
        "fee": from_money_units(fee_units), "fees": from_money_units(fee_units), "netProceeds": from_money_units(net_proceeds_units),
        "costBasis": from_money_units(cost_basis_units), "pnl": from_money_units(pnl_units),
        "returnPct": pnl_units / cost_basis_units * 100 if cost_basis_units else None,
        "bidUnits": bid_units, "grossUnits": gross_units, "feeUnits": fee_units,
        "entryGrossUnits": entry_gross_units, "entryFeeUnits": entry_fee_units, "costBasisUnits": cost_basis_units,
        "netProceedsUnits": net_proceeds_units, "pnlUnits": pnl_units,
    }


def _exit_position(account, options, transaction_type):
    transaction_id = _new_transaction(account, options.get("transactionId"))
    position = _get_position(account, options.get("positionId"))
    estimate = estimate_position_exit(position, options)
    if account["cashUnits"] + estimate["netProceedsUnits"] < 0:
        _fail("INSUFFICIENT_FUNDS", "The available cash and exit proceeds cannot cover the exit fee.")
    timestamp = _timestamp(options.get("timestamp"))
    next_account = deepcopy(account)
    remaining = _get_position(next_account, position["id"])
    remaining["quantity"] -= estimate["quantity"]
    remaining["entryGrossUnits"] -= estimate["entryGrossUnits"]
    remaining["entryFeeUnits"] -= estimate["entryFeeUnits"]
    remaining["entryCostUnits"] -= estimate["costBasisUnits"]
    remaining["updatedAt"] = timestamp
    next_account["positions"] = [p for p in next_account["positions"] if p["quantity"] > 0]
    next_account["cashUnits"] = _safe_result(next_account["cashUnits"] + estimate["netProceedsUnits"])
    next_account["realizedPnlUnits"] = _safe_result(next_account["realizedPnlUnits"] + estimate["pnlUnits"])
    next_account["totalFeesUnits"] = _safe_result(next_account["totalFeesUnits"] + estimate["feeUnits"])
    transaction = {
        "id": transaction_id, "type": transaction_type, "asset": position["asset"], "contractId": position["contractId"],
        "side": position["side"], "positionId": position["id"], "quantity": estimate["quantity"],
        "priceUnits": estimate["bidUnits"], "grossUnits": estimate["grossUnits"], "feeUnits": estimate["feeUnits"],
        "costBasisUnits": estimate["costBasisUnits"], "netCashChangeUnits": estimate["netProceedsUnits"],
        "realizedPnlUnits": estimate["pnlUnits"], "timestamp": timestamp,
    }
    if transaction_type == "SETTLE":
        transaction["officialWinningSide"] = options["officialWinningSide"]
    next_account["transactions"].append(transaction)
    next_account["transactionIds"].append(transaction_id)
    return validate_account(next_account)


def close_position(account, options=None):
    return _exit_position(account, options or {}, "CLOSE")


def settle_position(account, options=None):
    """Call only after the route verifies the official outcome for this contract."""
    options = options or {}
    validate_account(account)
    winner = _side(options.get("officialWinningSide"))
    position = _get_position(account, options.get("positionId"))
    return _exit_position(account, {
        **options, "officialWinningSide": winner, "bid": 1 if winner == position["side"] else 0,
        "quantity": position["quantity"],
    }, "SETTLE")


def estimate_trade(options=None):
    options = options or {}
    count = _quantity(options.get("quantity"))
    ask_units = _price(options.get("ask"), "Ask price", False)
    entry_fee_units = to_money_units(options.get("entryFee", 0), "Total entry fee")
    entry_gross_units = _safe_result(ask_units * count)
    return estimate_position_exit({
        "quantity": count, "entryGrossUnits": entry_gross_units, "entryFeeUnits": entry_fee_units,
        "entryCostUnits": _safe_result(entry_gross_units + entry_fee_units),
    }, {"bid": options.get("bid"), "fee": options.get("exitFee", 0)})


def calculate_account_summary(account, marks_by_position_id=None):
    validate_account(account)
    marks = marks_by_position_id if marks_by_position_id is not None else {}
    if not isinstance(marks, dict):
        _fail("INVALID_MARKS", "Position marks must be an object.")
    missing = []
    known_value = 0
    known_pnl = 0
    cost_basis = 0
    positions = []
    for position in account["positions"]:
        cost_basis = _safe_result(cost_basis + position["entryCostUnits"])
        mark = marks.get(position["id"])
        estimate = None
        if mark is not None:
            values = mark if isinstance(mark, dict) else {"bid": mark, "fee": 0}
            if any(key in values and values[key] != position[key] for key in ("contractId", "asset", "side")):
                _fail("MARK_MISMATCH", "The quote does not match this practice position.")
            if values.get("bid") is not None:
                estimate = estimate_position_exit(position, values)
                known_value = _safe_result(known_value + estimate["netProceedsUnits"])
                known_pnl = _safe_result(known_pnl + estimate["pnlUnits"])
        if estimate is None:
            missing.append(position["id"])
        positions.append({
            **deepcopy(position),
            "entryPrice": from_money_units(position["entryGrossUnits"]) / position["quantity"],
            "averageCost": from_money_units(position["entryCostUnits"]) / position["quantity"],
            "costBasis": from_money_units(position["entryCostUnits"]),
            "currentBid": estimate["bid"] if estimate else None,
            "value": estimate["netProceeds"] if estimate else None,
            "unrealizedPnl": estimate["pnl"] if estimate else None,
            "returnPct": estimate["returnPct"] if estimate else None,
        })
    complete = not missing
    return {
        "mode": "PAPER", "currency": "USD", "attemptId": account["attemptId"], "resetCount": account["resetCount"],
        "initialBalance": STARTING_BALANCE, "cash": from_money_units(account["cashUnits"]),
        "costBasis": from_money_units(cost_basis),
        "equity": from_money_units(_safe_result(account["cashUnits"] + known_value)) if complete else None,
        "realizedPnl": from_money_units(account["realizedPnlUnits"]),
        "unrealizedPnl": from_money_units(known_pnl) if complete else None,
        "totalPnl": from_money_units(_safe_result(account["realizedPnlUnits"] + known_pnl)) if complete else None,
        "totalFees": from_money_units(account["totalFeesUnits"]), "knownPositionValue": from_money_units(known_value),
        "positions": positions, "missingMarks": missing, "hasCompleteMarks": complete, "feePolicy": "explicit-total-fee",
    }


def reset_account(account, options=None):
    validate_account(account)
    options = options or {}
    next_id = _identity(options.get("attemptId", f"attempt-{account['resetCount'] + 2}"), "Attempt ID")
    if next_id == account["attemptId"]:
        _fail("INVALID_ATTEMPT", "A reset must start a new practice attempt.")
    next_account = create_account({"userId": account["userId"], "attemptId": next_id})
    next_account["resetCount"] = _safe_result(account["resetCount"] + 1)
    return next_account
