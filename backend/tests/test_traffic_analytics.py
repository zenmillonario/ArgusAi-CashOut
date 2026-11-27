"""Aggregate traffic endpoint tests using synthetic data only."""
from datetime import datetime
from types import SimpleNamespace
import unittest
import httpx
from fastapi import FastAPI, HTTPException
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from traffic_analytics import create_traffic_router
from practice_event import CAMPAIGN_ID


class Cursor:
    def __init__(self, rows):
        self.rows = iter(rows)
    def __aiter__(self):
        return self
    async def __anext__(self):
        try:
            return next(self.rows)
        except StopIteration:
            raise StopAsyncIteration


class Collection:
    def __init__(self, rows=()):
        self.rows = list(rows)
    def find(self, query, projection=None):
        keys = query.get("_id", {}).get("$in")
        return Cursor([row for row in self.rows if keys is None or row.get("_id") in keys])
    async def update_one(self, query, update, upsert=False):
        row = next((row for row in self.rows if row.get("_id") == query["_id"]), None)
        if row is None:
            row = dict(query)
            self.rows.append(row)
        row["page_opens"] = row.get("page_opens", 0) + update["$inc"]["page_opens"]


class TrafficTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = datetime(2026, 11, 28, 2, 0)
        self.db = SimpleNamespace(app_traffic_daily=Collection(), users=Collection([
            {"created_at": "2026-11-27T08:00:00Z", "last_seen": datetime(2026, 11, 28, 1, 50), "status": "approved",
             "practice_event_grant": {"campaign_id": CAMPAIGN_ID, "verified_at": self.now}, "email": "private@example.test"},
            {"created_at": datetime(2026, 11, 28, 1), "status": "pending"},
            {"created_at": datetime(2026, 11, 28, 1), "status": "approved", "is_bot": True},
        ]))
        async def require_admin(request):
            if request.headers.get("x-test-role") != "admin":
                raise HTTPException(403)
        limiter = Limiter(key_func=get_remote_address)
        app = FastAPI()
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        app.include_router(create_traffic_router(self.db, require_admin, limiter, now=lambda: self.now))
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    async def asyncTearDown(self):
        await self.client.aclose()
    async def test_opens_count_aggregates_only_and_admin_guard(self):
        self.assertEqual((await self.client.post("/api/traffic/open")).status_code, 403)
        for _ in range(2):
            self.assertEqual((await self.client.post("/api/traffic/open", headers={"Origin": "https://cashoutai.app"})).status_code, 200)
        self.assertEqual(self.db.app_traffic_daily.rows, [{"_id": "2026-11-27", "page_opens": 2}])
        self.assertEqual((await self.client.get("/api/admin/traffic")).status_code, 403)
        response = await self.client.get("/api/admin/traffic", headers={"x-test-role": "admin"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["page_opens_today"], 2)
        self.assertEqual(data["registrations_today"], 2)
        self.assertEqual(data["registered_accounts"], 2)
        self.assertEqual(data["recent_member_activity"], 1)
        self.assertEqual(data["verified_event_accounts"], 1)
        self.assertIsNone(data["days"][0]["page_opens"])
        self.assertNotIn("private@example.test", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
