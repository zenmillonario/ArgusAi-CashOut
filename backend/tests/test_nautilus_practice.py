"""Run with python -m unittest discover -s backend/tests -p test_nautilus_practice.py."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("nautilus_practice", Path(__file__).resolve().parents[1] / "nautilus_practice.py")
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


class NautilusPracticeTests(unittest.TestCase):
    def buy(self, account=None, **overrides):
        values = {"transactionId": "buy-1", "asset": "BTC", "contractId": "BTC-001", "side": "YES", "ask": 0.2, "budget": 25}
        values.update(overrides)
        return engine.buy_contracts(account if account is not None else engine.create_account(), values)

    def assert_code(self, code, function, *args):
        with self.assertRaises(engine.PracticeError) as caught:
            function(*args)
        self.assertEqual(caught.exception.code, code)

    def test_budget_and_subcent_precision(self):
        account = engine.create_account()
        quote = engine.quote_purchase({"account": account, "ask": "0.051", "fee": 0.4})
        self.assertEqual(quote["quantity"], 482)
        self.assertEqual(quote["totalCostUnits"], 24982000)
        self.assertEqual(quote["remainingCash"], 75.018)
        self.assertEqual(engine.to_money_units(0.000001), 1)
        self.assert_code("INVALID_AMOUNT", engine.to_money_units, 0.0000001)

    def test_spread_fee_loss_and_no_mutation(self):
        original = engine.create_account({"userId": "member-a"})
        before = deepcopy(original)
        bought = self.buy(original, quantity=100, fee=0.5)
        position_id = bought["positions"][0]["id"]
        marked = engine.calculate_account_summary(bought, {position_id: {"bid": 0.18, "fee": 0.25}})
        self.assertEqual(marked["cash"], 79.5)
        self.assertEqual(marked["equity"], 97.25)
        self.assertEqual(marked["unrealizedPnl"], -2.75)
        closed = engine.close_position(bought, {"transactionId": "close-1", "positionId": position_id, "bid": 0.18, "fee": 0.25})
        self.assertEqual(closed["cashUnits"], 97250000)
        self.assertEqual(closed["realizedPnlUnits"], -2750000)
        self.assertEqual(closed["totalFeesUnits"], 750000)
        self.assertEqual(original, before)
        self.assertEqual(len(bought["positions"]), 1)
        self.assertEqual(closed["positions"], [])

    def test_partial_closes_preserve_all_cost_basis(self):
        account = self.buy(ask=0.1, quantity=3, fee=0.01)
        position_id = account["positions"][0]["id"]
        for i in range(3):
            account = engine.close_position(account, {"transactionId": f"close-{i}", "positionId": position_id, "quantity": 1, "bid": 0.11, "fee": 0.001})
        self.assertEqual(account["cashUnits"], 100017000)
        self.assertEqual(account["realizedPnlUnits"], 17000)
        self.assertEqual(sum(tx["costBasisUnits"] for tx in account["transactions"] if tx["type"] == "CLOSE"), 310000)

    def test_all_five_assets_share_cash(self):
        account = engine.create_account()
        for i, asset in enumerate(("BTC", "ETH", "SOL", "XRP")):
            account = self.buy(account, transactionId=f"buy-{i}", asset=asset, contractId=f"{asset}-001")
        self.assertEqual(account["cashUnits"], 0)
        self.assertEqual(len(account["positions"]), 4)
        with self.assertRaises(engine.PracticeError) as caught:
            self.buy(account, transactionId="buy-doge", asset="DOGE", contractId="DOGE-001")
        self.assertEqual(caught.exception.code, "INSUFFICIENT_FUNDS")

    def test_official_settlement_is_explicit(self):
        bought = self.buy(ask=0.1)
        position_id = bought["positions"][0]["id"]
        options = {"transactionId": "settle-1", "positionId": position_id}
        self.assert_code("INVALID_SIDE", engine.settle_position, bought, options)
        win = engine.settle_position(bought, {**options, "officialWinningSide": "YES"})
        loss = engine.settle_position(bought, {**options, "officialWinningSide": "NO"})
        self.assertEqual(win["cashUnits"], 325000000)
        self.assertEqual(win["realizedPnlUnits"], 225000000)
        self.assertEqual(loss["cashUnits"], 75000000)
        self.assertEqual(loss["realizedPnlUnits"], -25000000)

    def test_missing_quotes_keep_equity_unknown(self):
        bought = self.buy()
        summary = engine.calculate_account_summary(bought)
        self.assertIsNone(summary["equity"])
        self.assertIsNone(summary["unrealizedPnl"])
        self.assertEqual(summary["cash"], 75)
        position_id = bought["positions"][0]["id"]
        self.assertEqual(summary["missingMarks"], [position_id])
        self.assert_code("MARK_MISMATCH", engine.calculate_account_summary, bought, {position_id: {"bid": 0.2, "contractId": "OTHER"}})

    def test_duplicate_invalid_and_excess_orders(self):
        bought = self.buy()
        self.assert_code("DUPLICATE_TRANSACTION", self.buy, bought)
        for ask in (0, -0.1, 1.001, float("nan"), float("inf"), None):
            with self.assertRaises(engine.PracticeError):
                self.buy(ask=ask)
        for quantity in (0, -1, 1.5, "1", None, True):
            with self.assertRaises(engine.PracticeError) as caught:
                self.buy(quantity=quantity)
            self.assertEqual(caught.exception.code, "INVALID_QUANTITY")
        with self.assertRaises(engine.PracticeError) as caught:
            self.buy(quantity=126)
        self.assertEqual(caught.exception.code, "INSUFFICIENT_BUDGET")
        tampered = {**bought, "cashUnits": bought["cashUnits"] + 1}
        self.assert_code("INVALID_ACCOUNT", engine.calculate_account_summary, tampered)

    def test_reset_only_the_current_practice_attempt(self):
        bought = self.buy(engine.create_account({"userId": "member-a"}))
        before = deepcopy(bought)
        reset = engine.reset_account(bought, {"attemptId": "fresh"})
        self.assertEqual(reset["userId"], "member-a")
        self.assertEqual(reset["cashUnits"], 100000000)
        self.assertEqual(reset["resetCount"], 1)
        self.assertEqual(reset["positions"], [])
        self.assertEqual(reset["transactions"], [])
        self.assertEqual(bought, before)
        self.assert_code("INVALID_ATTEMPT", engine.reset_account, bought, {"attemptId": bought["attemptId"]})

    def test_net_hypothetical_return(self):
        estimate = engine.estimate_trade({"quantity": 100, "ask": 0.1, "bid": 0.21, "entryFee": 0.5, "exitFee": 0.5})
        self.assertEqual(estimate["pnl"], 10)
        self.assertEqual(estimate["netProceeds"], 20.5)
        self.assertAlmostEqual(estimate["returnPct"], 95.23809523809524)


if __name__ == "__main__":
    unittest.main()
