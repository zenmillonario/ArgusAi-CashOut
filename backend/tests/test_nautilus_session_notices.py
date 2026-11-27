"""Accepted PAPER-run announcements, without providers or real broadcasts."""
from copy import deepcopy
from types import SimpleNamespace
import asyncio
import unittest

from fastapi import FastAPI
import httpx

import test_nautilus_api as fixture
import nautilus_api as api
from nautilus_session_notices import NautilusSessionNotices, NOTICE_TYPE, canonical_run_id, notice_id


class CountingChat(fixture.FakeCollection):
    def __init__(self):
        super().__init__()
        self.lookups = 0
        self.inserts = 0
        self.fail_inserts = 0

    async def find_one(self, query):
        self.lookups += 1
        return await super().find_one(query)

    async def insert_one(self, row):
        self.inserts += 1
        if self.fail_inserts:
            self.fail_inserts -= 1
            raise RuntimeError("Synthetic temporary shared-chat outage")
        return await super().insert_one(row)


class SessionNoticeTests(unittest.IsolatedAsyncioTestCase):
    ingest = fixture.NautilusAPITests.ingest
    asyncTearDown = fixture.NautilusAPITests.asyncTearDown

    async def asyncSetUp(self):
        await fixture.NautilusAPITests.asyncSetUp(self)
        await self.client.aclose()
        self.db.nautilus_chat = CountingChat()
        self.deliveries = []
        self.fail_delivery = False

        async def delivery(notice):
            self.deliveries.append(deepcopy(notice))
            if self.fail_delivery:
                raise RuntimeError("Synthetic online delivery failure")

        app = FastAPI()
        app.include_router(api.create_nautilus_router(self.db, on_session_started=delivery))
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    def pulse(self, run_id="PAPER_TEST", asset="BTC", offset=0):
        now = fixture.NOW + offset
        api.time.time.return_value = now
        data = fixture.packet(asset)
        data["server_now"] = now
        data["run"].update(run_id=run_id, updated=now)
        data["market"].update(time=now, close_ts=now + 120)
        data["quote"]["valid_until"] = now + 3
        data["quote"]["last_verified"]["verified_at"] = now
        return data

    async def feed(self, **kwargs):
        return await self.client.get("/api/nautilus/announcements", headers=fixture.HEADERS, **kwargs)

    async def test_new_fresh_run_creates_one_shared_notice_and_public_callback(self):
        result = await self.ingest(self.pulse())
        self.assertEqual(result.status_code, 200, result.text)
        self.assertTrue(result.json()["accepted"])
        self.assertEqual(len(self.db.nautilus_chat.documents), 1)
        self.assertEqual(len(self.deliveries), 1)
        notice = self.deliveries[0]
        self.assertEqual(set(notice), {"id", "type", "asset", "title", "message", "createdAt", "tab"})
        self.assertEqual(notice["id"], notice_id("BTC", "PAPER_TEST"))
        self.assertEqual(notice["type"], NOTICE_TYPE)
        self.assertEqual(notice["tab"], "bot-BTC")
        self.assertIn("was detected", notice["message"])
        self.assertNotIn("PAPER_TEST", str(notice))
        self.assertEqual((await self.feed()).json()["announcements"], [notice])
        chat = await self.client.get("/api/nautilus/chat/BTC", headers=fixture.HEADERS)
        self.assertEqual(len(chat.json()["messages"]), 1)
        self.assertNotIn("sourceRunId", chat.text)
        self.assertNotIn("PAPER_TEST", chat.text)
        self.assertNotIn("authorId", chat.text)

    async def test_heartbeats_and_exact_retries_do_not_repeat_or_query_the_notice(self):
        await self.ingest(self.pulse())
        self.assertEqual(self.db.nautilus_chat.lookups, 1)
        for offset in range(1, 21):
            self.assertEqual((await self.ingest(self.pulse(offset=offset))).status_code, 200)
        duplicate = await self.ingest(self.pulse(offset=20))
        self.assertFalse(duplicate.json()["accepted"])
        self.assertEqual(len(self.deliveries), 1)
        self.assertEqual(self.db.nautilus_chat.lookups, 1)
        self.assertEqual(self.db.nautilus_chat.inserts, 1)

    async def test_stopped_review_replay_or_stale_packets_cannot_announce(self):
        cases = (lambda p: p["run"].update(stopped=True),
                 lambda p: p["run"].update(review=True),
                 lambda p: p["run"].update(fresh=False),
                 lambda p: p["run"].update(updated=p["server_now"] - 20),
                 lambda p: p["market"].update(time=p["server_now"] - 20),
                 lambda p: p["quote"].update(fresh=False),
                 lambda p: p["run"].update(status="REPLAY_PAPER"))
        for index, mutate in enumerate(cases):
            packet = self.pulse(run_id="INELIGIBLE_" + str(index), offset=index)
            mutate(packet)
            self.assertEqual((await self.ingest(packet)).status_code, 200)
        self.assertFalse(self.deliveries)
        self.assertFalse(self.db.nautilus_chat.documents)

    async def test_first_fresh_packet_after_warmup_announces_the_run_once(self):
        warming = self.pulse()
        warming["run"]["fresh"] = False
        await self.ingest(warming)
        self.assertFalse(self.deliveries)
        await self.ingest(self.pulse(offset=1))
        await self.ingest(self.pulse(offset=2))
        self.assertEqual(len(self.deliveries), 1)

    async def test_canonical_identity_never_collapses_paths_or_truncation(self):
        for index, bad in enumerate(("foo/bar", "C:\\private\\run", "../PAPER_TEST", " ", "x" * 161, True)):
            packet = self.pulse(run_id=bad, offset=index)
            self.assertEqual((await self.ingest(packet)).status_code, 200)
            self.assertIsNone(canonical_run_id(bad))
        self.assertFalse(self.deliveries)
        self.assertFalse(self.db.nautilus_chat.documents)
        await self.ingest(self.pulse(run_id="PAPER_TEST", offset=7))
        self.assertEqual(len(self.deliveries), 1)

    async def test_asset_run_pair_is_durable_across_restarts_and_old_run_returns(self):
        await self.ingest(self.pulse(run_id="FIRST"))
        await self.ingest(self.pulse(run_id="SECOND", offset=1))
        await self.ingest(self.pulse(run_id="FIRST", offset=2))
        self.assertEqual(len(self.deliveries), 2)
        restarted = NautilusSessionNotices(self.db)
        document = await self.db.nautilus_snapshots.find_one({"_id": "BTC"})
        self.assertIsNone(await restarted.record(document, "live"))
        self.assertEqual(len(restarted.seen), 1)
        await self.ingest(self.pulse(run_id="FIRST", asset="ETH", offset=3), asset="ETH")
        self.assertEqual(len(self.deliveries), 3)
        self.assertNotEqual(self.deliveries[0]["id"], self.deliveries[-1]["id"])

    async def test_durable_insert_race_across_independent_instances_announces_once(self):
        document = {"_id": "BTC", "snapshot": self.pulse(), "sessionRunId": "PAPER_TEST", "receivedAt": fixture.NOW}
        services = [NautilusSessionNotices(self.db) for _ in range(8)]
        results = await asyncio.gather(*(service.record(document, "live") for service in services))
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(len(self.db.nautilus_chat.documents), 1)
        self.assertTrue(all(len(service.seen) == 1 for service in services))

    async def test_concurrent_publisher_packets_produce_one_accepted_run_notice(self):
        results = await asyncio.gather(*(self.ingest(self.pulse()) for _ in range(6)))
        self.assertTrue(all(result.status_code in (200, 409) for result in results))
        self.assertEqual(len(self.db.nautilus_chat.documents), 1)
        self.assertEqual(len(self.deliveries), 1)

    async def test_failed_notice_insert_recovers_on_exact_accepted_snapshot_retry(self):
        self.db.nautilus_chat.fail_inserts = 1
        first = await self.ingest(self.pulse(run_id="ACCEPTED_RUN"))
        self.assertTrue(first.json()["accepted"])
        self.assertFalse(self.deliveries)
        # An unaccepted different run with the same timestamp must not supply
        # the identity of the recovered side effect.
        retry = await self.ingest(self.pulse(run_id="UNACCEPTED_REPLACEMENT"))
        self.assertFalse(retry.json()["accepted"])
        self.assertEqual(len(self.deliveries), 1)
        self.assertEqual(self.deliveries[0]["id"], notice_id("BTC", "ACCEPTED_RUN"))
        self.assertEqual(self.db.nautilus_chat.documents[0]["sourceRunId"], "ACCEPTED_RUN")

    async def test_stale_retry_cannot_recover_a_missed_live_announcement(self):
        self.db.nautilus_chat.fail_inserts = 1
        packet = self.pulse()
        await self.ingest(packet)
        api.time.time.return_value = fixture.NOW + 60
        retry = await self.ingest(packet)
        self.assertFalse(retry.json()["accepted"])
        self.assertFalse(self.deliveries)
        self.assertFalse(self.db.nautilus_chat.documents)

    async def test_callback_failure_keeps_history_and_never_rebroadcasts(self):
        self.fail_delivery = True
        self.assertEqual((await self.ingest(self.pulse())).status_code, 200)
        await self.ingest(self.pulse(offset=1))
        self.assertEqual(len(self.deliveries), 1)
        self.assertEqual(len((await self.feed()).json()["announcements"]), 1)

    async def test_shared_history_is_bounded_authenticated_and_excludes_normal_chat(self):
        await self.client.post("/api/nautilus/chat/BTC", headers=fixture.HEADERS, json={"text": "A member message"})
        spoof = await self.client.post("/api/nautilus/chat/BTC", headers=fixture.HEADERS,
                                       json={"text": "Fake session", "kind": NOTICE_TYPE})
        self.assertEqual(spoof.status_code, 422)
        for index in range(5):
            await self.ingest(self.pulse(run_id="RUN_" + str(index), offset=index))
        result = (await self.feed(params={"limit": 2})).json()["announcements"]
        self.assertEqual(len(result), 2)
        self.assertGreaterEqual(result[0]["createdAt"], result[1]["createdAt"])
        self.assertTrue(all(row["type"] == NOTICE_TYPE for row in result))
        self.assertEqual((await self.client.get("/api/nautilus/announcements")).status_code, 401)
        self.assertEqual((await self.feed(params={"limit": 51})).status_code, 422)
        self.assertEqual((await self.feed(params={"limit": 0})).status_code, 422)
        self.db.users.documents[0]["status"] = "pending"
        self.assertEqual((await self.feed()).status_code, 403)

    async def test_cache_is_bounded_and_eviction_keeps_durable_deduplication(self):
        service = NautilusSessionNotices(self.db, cache_limit=2)
        for index in range(4):
            document = {"_id": "BTC", "snapshot": self.pulse(run_id="R" + str(index)),
                        "sessionRunId": "R" + str(index), "receivedAt": fixture.NOW}
            self.assertIsNotNone(await service.record(document, "live"))
        self.assertEqual(len(service.seen), 2)
        oldest = {"_id": "BTC", "snapshot": self.pulse(run_id="R0"), "sessionRunId": "R0", "receivedAt": fixture.NOW}
        self.assertIsNone(await service.record(oldest, "live"))
        self.assertEqual(len(service.seen), 2)
        self.assertEqual(len(self.db.nautilus_chat.documents), 4)

    async def test_history_orders_exact_and_fractional_seconds_chronologically(self):
        await self.ingest(self.pulse(run_id="EXACT_SECOND"))
        await self.ingest(self.pulse(run_id="LATER_FRACTION", offset=0.5))
        result = (await self.feed()).json()["announcements"]
        self.assertEqual([notice["id"] for notice in result],
                         [notice_id("BTC", "LATER_FRACTION"), notice_id("BTC", "EXACT_SECOND")])
        self.assertTrue(result[0]["createdAt"].endswith(".500000Z"))
        self.assertTrue(result[1]["createdAt"].endswith(".000000Z"))

    async def test_corrupt_stored_asset_run_binding_is_not_exposed_or_rebound(self):
        await self.ingest(self.pulse())
        row = self.db.nautilus_chat.documents[0]
        row["asset"] = "ETH"
        self.assertEqual((await self.feed()).json()["announcements"], [])
        row["asset"] = ["BTC"]
        self.assertEqual((await self.feed()).json()["announcements"], [])
        row["asset"] = "BTC"
        row["sourceRunId"] = "../../private/run"
        self.assertEqual((await self.feed()).json()["announcements"], [])


if __name__ == "__main__":
    unittest.main()
