"""Exercise the real lifespan with local workers and a synthetic database."""
import ast
import asyncio
from contextlib import asynccontextmanager
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest

from fastapi import FastAPI


class Worker:
    def __init__(self, mode=None, fail_index=False):
        self.settings = SimpleNamespace(mode=mode)
        self.fail_index = fail_index
        self.started = False
        self.stopped = False
        self.shutdown_count = 0
        self.initializations = 0

    async def initialize(self):
        self.initializations += 1
        if self.fail_index:
            raise RuntimeError("Synthetic secondary-index failure")

    async def run(self):
        self.started = True
        try:
            await asyncio.Event().wait()
        finally:
            self.stopped = True

    async def shutdown(self):
        self.shutdown_count += 1


class Collection:
    async def create_index(self, *args, **kwargs):
        raise RuntimeError("Synthetic legacy index conflict")

    async def find_one(self, query):
        return {"id": "existing-admin", "is_admin": True}


class WorkerLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setup_lifespan(self, mode="manual"):
        source = Path(__file__).resolve().parents[1] / "server.py"
        function = next(node for node in ast.parse(source.read_text()).body
                        if isinstance(node, ast.AsyncFunctionDef) and node.name == "lifespan")
        self.cleanup = Worker()
        self.stocks = Worker()
        self.settlements = Worker()
        self.billing = Worker(mode, fail_index=True)
        namespace = {
            "asynccontextmanager": asynccontextmanager, "FastAPI": FastAPI,
            "asyncio": asyncio, "logger": logging.getLogger("cashout.lifespan.test"),
            "db": SimpleNamespace(messages=Collection(), users=Collection()),
            "periodic_cleanup": self.cleanup.run, "stock_alert_service": self.stocks,
            "square_billing_service": self.billing, "nautilus_settlement_service": self.settlements,
        }
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
        return namespace["lifespan"]

    async def test_optional_index_failure_keeps_manual_mode_and_settlement_worker_available(self):
        lifespan = self.setup_lifespan()
        async with lifespan(FastAPI()):
            await asyncio.sleep(0)
            self.assertTrue(self.cleanup.started)
            self.assertTrue(self.stocks.started)
            self.assertTrue(self.settlements.started)
            self.assertFalse(self.billing.started)
            self.assertEqual(self.billing.initializations, 1)
        for worker in (self.cleanup, self.stocks, self.settlements):
            self.assertTrue(worker.stopped)
        self.assertEqual(self.settlements.shutdown_count, 1)

    async def test_shutdown_still_cancels_workers_when_application_context_raises(self):
        lifespan = self.setup_lifespan()
        with self.assertRaisesRegex(RuntimeError, "Synthetic application error"):
            async with lifespan(FastAPI()):
                await asyncio.sleep(0)
                raise RuntimeError("Synthetic application error")
        for worker in (self.cleanup, self.stocks, self.settlements):
            self.assertTrue(worker.stopped)
        self.assertEqual(self.settlements.shutdown_count, 1)

    async def test_only_explicit_automatic_mode_starts_square_worker(self):
        lifespan = self.setup_lifespan("automatic")
        async with lifespan(FastAPI()):
            await asyncio.sleep(0)
            self.assertTrue(self.billing.started)
            self.assertEqual(self.billing.initializations, 0)
        self.assertTrue(self.billing.stopped)
        self.assertEqual(self.settlements.shutdown_count, 1)


if __name__ == "__main__":
    unittest.main()
