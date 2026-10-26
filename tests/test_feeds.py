"""Live ingestion: validation, auth, the Agent Framework match pipeline and incremental publishing."""
import asyncio
import copy
import unittest

from fastapi.testclient import TestClient

from server.app import app, feeds
from server.identity import identity
from server.provider_sim import new_match


class FeedApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.sheet, self.events = new_match(712_345)

    def open_feed(self):
        res = self.client.post("/api/feeds", json=self.sheet)
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()

    def push(self, feed, events, final=False, token=None):
        return self.client.post(feed["events_url"], json={"events": events, "final": final},
                                headers={"Authorization": f"Bearer {token or feed['write_token']}"})

    def test_events_need_the_feed_write_token(self):
        feed = self.open_feed()
        self.assertEqual(self.push(feed, self.events[:5], token="x" * 32).status_code, 401)
        res = self.client.post(feed["events_url"], json={"events": self.events[:5]})
        self.assertEqual(res.json()["detail"]["code"], "bad_token")

    def test_invalid_events_are_rejected_with_a_reason_and_the_rest_accepted(self):
        feed = self.open_feed()
        bad = copy.deepcopy(self.events[:6])
        bad[1]["x"] = 500                       # off the pitch
        bad[2]["player_id"] = "NOBODY"          # not on the roster
        bad[3]["secret"] = 1                    # not part of the contract
        res = self.push(feed, bad).json()
        self.assertEqual(res["accepted"], 3)
        reasons = {r["index"]: r["reason"] for r in res["rejected"]}
        self.assertIn("on the pitch", reasons[1])
        self.assertIn("unknown player", reasons[2])
        self.assertIn("unexpected fields", reasons[3])
        self.assertEqual(res["pipeline"], ["ingest", "interpret", "explain", "render", "narrate", "publish"])
        again = self.push(feed, self.events[:2]).json()  # replays are rejected, not double counted
        self.assertEqual(again["accepted"], 0)
        self.assertTrue(all("duplicate" in r["reason"] or "out of order" in r["reason"] for r in again["rejected"]))

    def test_a_full_match_streams_to_a_complete_timeline_without_real_names(self):
        feed = self.open_feed()
        for i in range(0, len(self.events), 400):
            res = self.push(feed, self.events[i:i + 400], final=i + 400 >= len(self.events))
            self.assertEqual(res.status_code, 200, res.text)
        snap = self.client.get(f"/api/feeds/{feed['feed_id']}?lang=es").json()
        self.assertTrue(snap["summary"]["finished"])
        self.assertGreaterEqual(snap["summary"]["minute"], 90)
        self.assertTrue(snap["timeline"]["moments"] and snap["narrative"]["summaries"])
        self.assertEqual(identity().leaks(snap, feeds.get(feed["feed_id"]).match["roster"]), [])
        self.assertEqual(self.push(feed, self.events[-1:]).status_code, 409)

    def test_bad_match_sheets_are_explained(self):
        res = self.client.post("/api/feeds", json={"home": {"code": "A"}, "away": {}, "roster": {}})
        self.assertEqual(res.status_code, 422)  # wrong shape: names the missing fields
        self.assertTrue(any(e["loc"][-1] == "code" for e in res.json()["detail"]))
        sheet = dict(self.sheet, home=dict(self.sheet["home"], code="A"))
        res = self.client.post("/api/feeds", json=sheet)  # right shape, wrong content: a plain reason
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["detail"]["code"], "bad_team")

    def test_interactive_docs_describe_the_ingestion_contract(self):
        spec = self.client.get("/openapi.json").json()
        for name in ("MatchSheet", "Event", "EventBatch", "IngestAck", "FeedCreated"):
            self.assertIn(name, spec["components"]["schemas"])
        ingest = spec["paths"]["/api/feeds/{feed_id}/events"]["post"]
        self.assertIn("401", ingest["responses"])
        self.assertEqual(self.client.get("/docs").status_code, 200)

    def test_loosely_typed_events_are_rejected_one_by_one(self):
        feed = self.open_feed()
        bad = copy.deepcopy(self.events[:3])
        bad[1]["t"] = "soon"           # wrong type: rejected with a reason, the batch still lands
        res = self.push(feed, bad).json()
        self.assertEqual(res["accepted"], 2)
        self.assertIn("seconds from kick-off", res["rejected"][0]["reason"])

    def test_schema_is_published(self):
        schema = self.client.get("/api/schema").json()
        self.assertIn("Event", schema["$defs"])


class FeedPublishingTests(unittest.TestCase):
    def test_subscribers_receive_only_what_is_new(self):
        async def scenario():
            from server.feeds import validate_create
            sheet, events = new_match(712_346)
            feed = feeds.create(validate_create(sheet), "test")
            q = feeds.subscribe(feed, "fr")
            await feeds.ingest(feed, events[:300])
            first = []
            while not q.empty():
                first.append(q.get_nowait())
            await feeds.ingest(feed, events[300:600])
            second = []
            while not q.empty():
                second.append(q.get_nowait())
            return first, second

        first, second = asyncio.run(scenario())
        kinds = lambda msgs: [k for k, _ in msgs]  # noqa: E731
        self.assertEqual(kinds(first).count("event"), 300)
        self.assertEqual(kinds(second).count("event"), 300)
        self.assertEqual(kinds(first)[-1], "ingest")
        ids_1 = {p["id"] for k, p in first if k == "event"}
        ids_2 = {p["id"] for k, p in second if k == "event"}
        self.assertFalse(ids_1 & ids_2)
        minutes = [p["minute"] for k, p in first + second if k == "state"]
        self.assertEqual(minutes, sorted(set(minutes)))


    def test_ingest_works_while_viewers_are_waiting(self):
        """Regression: a subscriber blocked on its queue holds a future that cannot be copied."""
        async def scenario():
            from server.feeds import validate_create
            sheet, events = new_match(712_347)
            feed = feeds.create(validate_create(sheet), "test")
            q = feeds.subscribe(feed, "en")
            waiter = asyncio.create_task(q.get())
            await asyncio.sleep(0)
            ack = await feeds.ingest(feed, events[:50])
            got = await asyncio.wait_for(waiter, 2)
            return ack, got

        ack, got = asyncio.run(scenario())
        self.assertEqual(ack["accepted"], 50)
        self.assertEqual(got[0], "event")


if __name__ == "__main__":
    unittest.main()
